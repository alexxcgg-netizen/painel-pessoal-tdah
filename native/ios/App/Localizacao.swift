//
//  Localizacao.swift
//  Leva "onde eu estou" (2026-11-04, docs/briefings/2026-11-04-onde-eu-estou.md)
//
//  O iPhone avisa o painel quando o Alex chega num lugar e fica, e quando sai dele
//  (CLLocationManager.startMonitoringVisits, autorização "Sempre"). O iOS acorda o app mesmo
//  fechado pra entregar a visita; por isso o gerente nasce no didFinishLaunching (AppDelegate).
//  Nada de startUpdatingLocation contínuo (bateria): só as visitas.
//
//  Avisos no app (06/11): com "Sempre", também a mudança grande de lugar (~500 m, quase sem bateria)
//  acorda o app pra conferir os avisos agendados (AvisosLocais.swift). E o botão "GPS sempre ligado"
//  (Configurar, desligado por padrão) liga o GPS de baixa precisão em segundo plano: o app fica
//  acordado e confere o painel a cada 5 min (avisos e ilha). Gasta mais bateria, por isso é opção.
//
//  GPS mais esperto (06/11, leva "painel esperto" frente 3, docs/briefings/2026-11-06-painel-esperto.md):
//    - Cerca nos lugares: o painel manda até 20 lugares (GET /api/localizacao/cercas: casa, lugar das saídas
//      de hoje e de amanhã cedo, apelidos). Entrou/saiu na hora (mais rápido que a visita) vai pra mesma fila
//      e o mesmo POST de visita, com `fonte: "cerca"`. Roda com "Sempre", igual às visitas.
//    - Sabe que está dirigindo (CMMotionActivityManager, permissão "Movimento"): de carro o GPS vira de estrada
//      sozinho (automotiveNavigation, ~10 m, a cada ~1 km); parado ou andando por ~5 min volta pro econômico.
//      O botão "GPS sempre ligado" é o interruptor geral: desligado, nada disso roda. Sem a permissão
//      Movimento, fica como antes (só o econômico).
//    - Viagem acompanhada: SÓ dirigindo E com o painel dizendo `acompanhar` (viagem planejada em andamento ou
//      compromisso de saída no ao vivo - AoVivoAPI guarda), a posição vai pro painel a cada ~5 min ou ~10 km
//      (POST /api/localizacao/posicao). O painel apaga tudo quando a viagem acaba. Fora disso, nunca sai daqui.
//
//  Cada visita vai pra POST /api/localizacao/visita com o token do widget no header (nunca na
//  URL). Sem rede ou PC desligado: fica numa fila no UserDefaults (até 50, a mais velha sai) e vai
//  quando der (próxima visita ou quando o app abre). Posição de viagem não entra em fila: sem rede, perde.
//

import CoreLocation
import CoreMotion
import SwiftUI
import UIKit

final class Localizacao: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = Localizacao()
    static let chaveFila = "painel_visitas_fila"
    static let maxFila = 50
    static let chaveGps = "painel_gps_sempre"
    static let conferirACada: TimeInterval = 5 * 60

    // cercas
    static let prefixoCerca = "painel-cerca-"
    static let chaveCercasEm = "painel_cercas_em"
    static let chaveCercasAssinatura = "painel_cercas_assinatura"
    static let cercasACada: TimeInterval = 30 * 60
    static let maxRegioes = 20  // limite do iOS por app, contando as que outra parte do app vigiar

    // dirigindo / viagem acompanhada
    static let paradoPor: TimeInterval = 5 * 60
    static let posicaoACada: TimeInterval = 5 * 60
    static let posicaoACadaMetros: CLLocationDistance = 10_000

    @Published private(set) var status: CLAuthorizationStatus = .notDetermined
    @Published private(set) var pendentes = 0
    @Published private(set) var gpsSempre = false
    @Published private(set) var dirigindo = false
    @Published private(set) var statusMovimento: CMAuthorizationStatus = .notDetermined
    @Published private(set) var cercasAtivas = 0

    private let gerente = CLLocationManager()
    private let movimento = CMMotionActivityManager()
    private var enviando = false
    private let iso = ISO8601DateFormatter()
    private var relogioGps: Timer?
    private var ultimaConferida = Date.distantPast
    private var gpsLigado = false
    private var lendoMovimento = false
    private var parouEm: Date?  // primeira vez que o Movimento disse "parado/andando" depois de dirigir
    private var relogioParado: Timer?
    private var ultimaPosicaoEnviada: CLLocation?
    private var enviandoPosicao = false
    private var buscandoCercas = false

    private override init() {
        super.init()
        gerente.delegate = self
        status = gerente.authorizationStatus
        pendentes = lerFila().count
        gpsSempre = Ajustes.defaults.bool(forKey: Localizacao.chaveGps)
        statusMovimento = CMMotionActivityManager.authorizationStatus()
        cercasAtivas = gerente.monitoredRegions.filter { $0.identifier.hasPrefix(Localizacao.prefixoCerca) }.count
        // a permissão Movimento só pode ser pedida com o app na frente: confere toda vez que ele volta
        _ = NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil,
                                                   queue: .main) { [weak self] _ in
            self?.voltouPraFrente()
        }
    }

    /// AppDelegate chama no launch (inclusive quando o iOS relança o app em segundo plano por uma visita,
    /// por uma cerca ou por uma mudança grande de lugar).
    func iniciar() {
        ligarConformePermissao()
        enviarFila()
        atualizarCercas()
    }

    private func voltouPraFrente() {
        statusMovimento = CMMotionActivityManager.authorizationStatus()
        if gpsSempre && gerente.authorizationStatus == .authorizedAlways {
            ligarMovimento()
        }
        atualizarCercas()
    }

    private func ligarConformePermissao() {
        if gerente.authorizationStatus == .authorizedAlways {
            gerente.startMonitoringVisits()
            gerente.startMonitoringSignificantLocationChanges()
            if gpsSempre {
                ligarGps()
                ligarMovimento()
            } else {
                desligarGps()
                desligarMovimento()
            }
        } else {
            gerente.stopMonitoringVisits()
            gerente.stopMonitoringSignificantLocationChanges()
            desligarGps()
            desligarMovimento()
        }
    }

    // MARK: GPS sempre ligado (botão do Configurar) - interruptor geral do GPS esperto

    func definirGpsSempre(_ ligado: Bool) {
        gpsSempre = ligado
        Ajustes.defaults.set(ligado, forKey: Localizacao.chaveGps)
        if ligado && gerente.authorizationStatus != .authorizedAlways {
            pedirPermissao()  // sem "Sempre" o GPS não roda com o app fechado
        }
        ligarConformePermissao()
    }

    private func ligarGps() {
        // precisa do UIBackgroundModes "location" no Info.plist (project.yml), senão o iOS derruba o app
        aplicarModoGps()
        gerente.pausesLocationUpdatesAutomatically = false
        gerente.allowsBackgroundLocationUpdates = true
        gerente.showsBackgroundLocationIndicator = false
        gerente.startUpdatingLocation()
        gpsLigado = true
        if relogioGps == nil {
            relogioGps = Timer.scheduledTimer(withTimeInterval: Localizacao.conferirACada, repeats: true) { [weak self] _ in
                self?.conferirParado()
                self?.conferirPainel(forcar: true)
            }
        }
    }

    private func desligarGps() {
        relogioGps?.invalidate()
        relogioGps = nil
        if gpsLigado {
            gerente.stopUpdatingLocation()
        }
        gpsLigado = false
        gerente.allowsBackgroundLocationUpdates = false
        if dirigindo { mudarDirigindo(false) }
    }

    /// Econômico (antena/wi-fi, quase sem bateria) ou de estrada (dirigindo).
    private func aplicarModoGps() {
        if dirigindo {
            gerente.activityType = .automotiveNavigation
            gerente.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
            gerente.distanceFilter = 1000
        } else {
            gerente.activityType = .other
            gerente.desiredAccuracy = kCLLocationAccuracyThreeKilometers
            gerente.distanceFilter = 500
        }
    }

    // MARK: Movimento (dirigindo?)

    var movimentoDisponivel: Bool { CMMotionActivityManager.isActivityAvailable() }

    private func ligarMovimento() {
        guard movimentoDisponivel, !lendoMovimento else { return }
        let st = CMMotionActivityManager.authorizationStatus()
        statusMovimento = st
        // sem permissão: como antes (só o econômico). Ainda não pedida: só com o app na frente (o iOS pergunta)
        let podePedir = st == .notDetermined && UIApplication.shared.applicationState == .active
        guard st == .authorized || podePedir else { return }
        lendoMovimento = true
        movimento.startActivityUpdates(to: .main) { [weak self] atividade in
            guard let self, let atividade else { return }
            self.statusMovimento = CMMotionActivityManager.authorizationStatus()
            self.avaliar(atividade)
        }
        // relançado no meio do caminho: o que o iPhone viu nos últimos minutos já diz se está dirigindo
        if st == .authorized {
            let agora = Date()
            movimento.queryActivityStarting(from: agora.addingTimeInterval(-3 * 60), to: agora, to: .main) { [weak self] lista, _ in
                guard let self, let ultima = lista?.last else { return }
                self.avaliar(ultima)
            }
        }
    }

    private func desligarMovimento() {
        if lendoMovimento {
            movimento.stopActivityUpdates()
        }
        lendoMovimento = false
        relogioParado?.invalidate()
        relogioParado = nil
        parouEm = nil
        if dirigindo { mudarDirigindo(false) }
    }

    /// Carro (com alguma certeza) liga o modo estrada na hora; parado/andando por ~5 min volta pro econômico.
    /// Sinal fechado costuma vir como "carro + parado": continua dirigindo.
    private func avaliar(_ a: CMMotionActivity) {
        guard gpsSempre, a.confidence != .low else { return }
        if a.automotive {
            parouEm = nil
            relogioParado?.invalidate()
            relogioParado = nil
            if !dirigindo { mudarDirigindo(true) }
        } else if dirigindo && (a.stationary || a.walking || a.running || a.cycling) {
            if parouEm == nil {
                parouEm = Date()
                relogioParado?.invalidate()
                relogioParado = Timer.scheduledTimer(withTimeInterval: Localizacao.paradoPor + 5, repeats: false) { [weak self] _ in
                    self?.conferirParado()
                }
            }
            conferirParado()
        }
    }

    private func conferirParado() {
        guard dirigindo, let p = parouEm, Date().timeIntervalSince(p) >= Localizacao.paradoPor else { return }
        mudarDirigindo(false)
    }

    private func mudarDirigindo(_ sim: Bool) {
        dirigindo = sim
        parouEm = nil
        if !sim {
            ultimaPosicaoEnviada = nil
        }
        if gpsLigado {
            aplicarModoGps()
            gerente.startUpdatingLocation()  // aplica a precisão nova
        }
        if sim {
            // pergunta ao painel se tem viagem/saída pra acompanhar (`acompanhar`) e anda a ilha
            AoVivo.shared.sincronizar()
        }
    }

    // MARK: Viagem acompanhada (posição do carro, só quando o painel pede)

    private func talvezMandarPosicao(_ loc: CLLocation) {
        guard gpsSempre, dirigindo, !enviandoPosicao else { return }
        guard let ate = AoVivoAPI.acompanharAte(), ate > Date() else { return }  // nada sendo acompanhado: não sai daqui
        guard loc.horizontalAccuracy >= 0, loc.horizontalAccuracy <= 200, -loc.timestamp.timeIntervalSinceNow < 120 else { return }
        if let anterior = ultimaPosicaoEnviada {
            let passou = loc.timestamp.timeIntervalSince(anterior.timestamp)
            guard passou >= Localizacao.posicaoACada || loc.distance(from: anterior) >= Localizacao.posicaoACadaMetros else { return }
        }
        guard let base = URL(string: Ajustes.url), base.scheme != nil, !Ajustes.token.isEmpty else { return }
        var pedido = URLRequest(url: base.appendingPathComponent("api/localizacao/posicao"))
        pedido.httpMethod = "POST"
        pedido.setValue("application/json", forHTTPHeaderField: "Content-Type")
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 20
        let corpo: [String: Any] = [
            "lat": loc.coordinate.latitude,
            "lng": loc.coordinate.longitude,
            "velocidade": loc.speed >= 0 ? loc.speed : NSNull(),
            "precisao": loc.horizontalAccuracy,
            "em": iso.string(from: loc.timestamp),
        ]
        guard let dados = try? JSONSerialization.data(withJSONObject: corpo) else { return }
        pedido.httpBody = dados
        enviandoPosicao = true
        let app = UIApplication.shared
        var tarefa: UIBackgroundTaskIdentifier = .invalid
        tarefa = app.beginBackgroundTask(withName: "painel-posicao") {
            if tarefa != .invalid {
                app.endBackgroundTask(tarefa)
                tarefa = .invalid
            }
        }
        URLSession.shared.dataTask(with: pedido) { dados, resposta, erro in
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            var acompanhar: Bool?
            if erro == nil, status == 200, let dados,
               let json = try? JSONSerialization.jsonObject(with: dados) as? [String: Any] {
                acompanhar = json["acompanhar"] as? Bool
            }
            DispatchQueue.main.async {
                self.enviandoPosicao = false
                if let acompanhar {
                    self.ultimaPosicaoEnviada = loc
                    AoVivoAPI.definirAcompanhar(acompanhar)  // false: viagem acabou/chegou, para de mandar
                    AoVivo.shared.sincronizar()  // a ilha refaz km, chegada, posto e chuva
                }
                if tarefa != .invalid {
                    app.endBackgroundTask(tarefa)
                    tarefa = .invalid
                }
            }
        }.resume()
    }

    // MARK: Cercas nos lugares

    private struct Cerca: Decodable {
        let id: String
        let lat: Double
        let lng: Double
        let raioM: Double

        enum CodingKeys: String, CodingKey {
            case id, lat, lng
            case raioM = "raio_m"
        }
    }

    private struct RespostaCercas: Decodable {
        let cercas: [Cerca]
    }

    /// Busca a lista no painel (no máximo a cada 30 min, ou `forcar`) e troca as cercas se mudou.
    func atualizarCercas(forcar: Bool = false) {
        guard gerente.authorizationStatus == .authorizedAlways,
              CLLocationManager.isMonitoringAvailable(for: CLCircularRegion.self), !buscandoCercas else { return }
        let ultima = Ajustes.defaults.object(forKey: Localizacao.chaveCercasEm) as? Date ?? .distantPast
        guard forcar || Date().timeIntervalSince(ultima) > Localizacao.cercasACada else { return }
        guard let base = URL(string: Ajustes.url), base.scheme != nil, !Ajustes.token.isEmpty else { return }
        var pedido = URLRequest(url: base.appendingPathComponent("api/localizacao/cercas"))
        pedido.httpMethod = "GET"
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 15
        buscandoCercas = true
        URLSession.shared.dataTask(with: pedido) { dados, resposta, _ in
            var lista: [Cerca]?
            if (resposta as? HTTPURLResponse)?.statusCode == 200, let dados {
                lista = (try? JSONDecoder().decode(RespostaCercas.self, from: dados))?.cercas
            }
            DispatchQueue.main.async {
                self.buscandoCercas = false
                guard let lista else { return }  // sem rede/painel: fica com as de antes
                Ajustes.defaults.set(Date(), forKey: Localizacao.chaveCercasEm)
                self.registrarCercas(lista)
            }
        }.resume()
    }

    private func registrarCercas(_ lista: [Cerca]) {
        let todas = gerente.monitoredRegions
        let minhas = todas.filter { $0.identifier.hasPrefix(Localizacao.prefixoCerca) }
        let vagas = max(0, Localizacao.maxRegioes - (todas.count - minhas.count))
        let escolhidas = Array(lista.prefix(vagas))
        let assinatura = escolhidas.map { "\($0.id)@\($0.lat),\($0.lng),\($0.raioM)" }.joined(separator: "|")
        if assinatura == Ajustes.defaults.string(forKey: Localizacao.chaveCercasAssinatura) && minhas.count == escolhidas.count {
            cercasAtivas = minhas.count
            return  // nada mudou: não mexe (trocar à toa zera o "dentro/fora" do iOS)
        }
        for r in minhas {
            gerente.stopMonitoring(for: r)
        }
        let maxRaio = gerente.maximumRegionMonitoringDistance
        var n = 0
        for c in escolhidas {
            let centro = CLLocationCoordinate2D(latitude: c.lat, longitude: c.lng)
            guard CLLocationCoordinate2DIsValid(centro) else { continue }
            var raio = max(c.raioM, 100)
            if maxRaio > 0 { raio = min(raio, maxRaio) }
            let regiao = CLCircularRegion(center: centro, radius: raio, identifier: Localizacao.prefixoCerca + c.id)
            regiao.notifyOnEntry = true
            regiao.notifyOnExit = true
            gerente.startMonitoring(for: regiao)
            n += 1
        }
        Ajustes.defaults.set(assinatura, forKey: Localizacao.chaveCercasAssinatura)
        cercasAtivas = n
    }

    /// Entrou/saiu de uma cerca: vira visita (chegada ou saída) na mesma fila, com o centro do lugar.
    private func cerca(_ region: CLRegion, entrou: Bool) {
        guard let r = region as? CLCircularRegion, r.identifier.hasPrefix(Localizacao.prefixoCerca) else { return }
        let agora = iso.string(from: Date())
        let item: [String: Any] = [
            "id": UUID().uuidString,
            "lat": (r.center.latitude * 10000).rounded() / 10000,
            "lon": (r.center.longitude * 10000).rounded() / 10000,
            "precisao": r.radius,
            "chegada": entrou ? agora : "",
            "saida": entrou ? "" : agora,
            "fonte": "cerca",
            "cerca": String(r.identifier.dropFirst(Localizacao.prefixoCerca.count)),
        ]
        DispatchQueue.main.async {
            self.enfileirar(item)
            self.enviarFila()
            AoVivo.shared.sincronizar()
            AvisosLocais.shared.sincronizar(motivo: "cerca")
            self.atualizarCercas()  // saiu de casa: o lugar da próxima tarefa pode ter mudado
        }
    }

    // MARK: Conferir o painel

    /// Avisos e ilha, no máximo 1x a cada ~5 min (o GPS e a mudança de lugar podem chamar seguido).
    private func conferirPainel(forcar: Bool = false) {
        DispatchQueue.main.async {
            let agora = Date()
            guard forcar || agora.timeIntervalSince(self.ultimaConferida) > Localizacao.conferirACada - 30 else { return }
            self.ultimaConferida = agora
            AvisosLocais.shared.sincronizar(motivo: self.gpsSempre ? "gps" : "lugar")
            AoVivo.shared.sincronizar()
            self.atualizarCercas()
        }
    }

    /// Botão da tela Configurar. Negada/bloqueada: só os Ajustes do iPhone mudam.
    func pedirPermissao() {
        switch gerente.authorizationStatus {
        case .notDetermined, .authorizedWhenInUse:
            gerente.requestAlwaysAuthorization()
        default:
            abrirAjustes()
        }
    }

    func abrirAjustes() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
    }

    var descricaoStatus: String {
        switch status {
        case .authorizedAlways: return "Sempre"
        case .authorizedWhenInUse: return "Só com o app aberto"
        case .denied: return "Negada"
        case .restricted: return "Bloqueada"
        case .notDetermined: return "Ainda não pedida"
        @unknown default: return "Desconhecida"
        }
    }

    var descricaoMovimento: String {
        guard movimentoDisponivel else { return "Não tem neste iPhone" }
        switch statusMovimento {
        case .authorized: return "Permitido"
        case .denied: return "Negado"
        case .restricted: return "Bloqueado"
        case .notDetermined: return "Ainda não pedido"
        @unknown default: return "Desconhecido"
        }
    }

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let novo = manager.authorizationStatus
        DispatchQueue.main.async { self.status = novo }
        ligarConformePermissao()
        if novo == .authorizedAlways { atualizarCercas(forcar: true) }
    }

    /// Mudança grande de lugar (~500 m) ou o GPS sempre ligado: confere os avisos (com intervalo mínimo).
    /// A posição só vai pro painel dirigindo e com viagem/saída sendo acompanhada (talvezMandarPosicao).
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        conferirParado()
        if dirigindo, let ultima = locations.last {
            talvezMandarPosicao(ultima)
        }
        conferirPainel()
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        let c = visit.coordinate
        guard CLLocationCoordinate2DIsValid(c) else { return }
        let chegada = visit.arrivalDate == Date.distantPast ? "" : iso.string(from: visit.arrivalDate)
        let saida = visit.departureDate == Date.distantFuture ? "" : iso.string(from: visit.departureDate)
        if chegada.isEmpty && saida.isEmpty { return }
        let item: [String: Any] = [
            "id": UUID().uuidString,
            "lat": (c.latitude * 10000).rounded() / 10000,
            "lon": (c.longitude * 10000).rounded() / 10000,
            "precisao": max(0, visit.horizontalAccuracy),
            "chegada": chegada,
            "saida": saida,
        ]
        DispatchQueue.main.async {
            self.enfileirar(item)
            self.enviarFila()
            AoVivo.shared.sincronizar()  // chegou/saiu de um lugar: passo da atividade ao vivo (AoVivo.swift)
            AvisosLocais.shared.sincronizar(motivo: "visita")  // e confere os avisos agendados
            self.atualizarCercas()
        }
    }

    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        cerca(region, entrou: true)
    }

    func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        cerca(region, entrou: false)
    }

    func locationManager(_ manager: CLLocationManager, monitoringDidFailFor region: CLRegion?, withError error: Error) {}

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: Fila (sempre na main thread)

    private func lerFila() -> [[String: Any]] {
        Ajustes.defaults.array(forKey: Localizacao.chaveFila) as? [[String: Any]] ?? []
    }

    private func gravarFila(_ fila: [[String: Any]]) {
        Ajustes.defaults.set(fila, forKey: Localizacao.chaveFila)
        pendentes = fila.count
    }

    private func enfileirar(_ item: [String: Any]) {
        var fila = lerFila()
        fila.append(item)
        if fila.count > Localizacao.maxFila {
            fila.removeFirst(fila.count - Localizacao.maxFila)
        }
        gravarFila(fila)
    }

    private func tirarDaFila(_ id: String) {
        gravarFila(lerFila().filter { ($0["id"] as? String) != id })
    }

    /// Manda a fila em ordem, uma por vez. Para no primeiro erro de rede/servidor (tenta depois).
    func enviarFila() {
        guard !enviando, let base = URL(string: Ajustes.url), base.scheme != nil, !Ajustes.token.isEmpty,
              let primeiro = lerFila().first, let id = primeiro["id"] as? String else { return }
        enviando = true
        let app = UIApplication.shared
        var tarefa: UIBackgroundTaskIdentifier = .invalid
        tarefa = app.beginBackgroundTask(withName: "painel-visita") {
            if tarefa != .invalid {
                app.endBackgroundTask(tarefa)
                tarefa = .invalid
            }
        }
        mandar(primeiro, base: base) { resultado in
            DispatchQueue.main.async {
                self.enviando = false
                switch resultado {
                case .enviado, .descartar:
                    self.tirarDaFila(id)
                    self.enviarFila()
                case .tentarDepois:
                    break
                }
                if tarefa != .invalid {
                    app.endBackgroundTask(tarefa)
                    tarefa = .invalid
                }
            }
        }
    }

    private enum Resultado {
        case enviado, descartar, tentarDepois
    }

    private func mandar(_ item: [String: Any], base: URL, fim: @escaping (Resultado) -> Void) {
        var pedido = URLRequest(url: base.appendingPathComponent("api/localizacao/visita"))
        pedido.httpMethod = "POST"
        pedido.setValue("application/json", forHTTPHeaderField: "Content-Type")
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 20
        var corpo: [String: Any] = [
            "lat": item["lat"] ?? 0,
            "lon": item["lon"] ?? 0,
            "precisao": item["precisao"] ?? NSNull(),
        ]
        for chave in ["chegada", "saida"] {
            let valor = item[chave] as? String ?? ""
            corpo[chave] = valor.isEmpty ? NSNull() : valor
        }
        // cerca (06/11): de onde veio, pra quem usa chegada/saída no painel ("pra onde vou", "chegou em casa")
        for chave in ["fonte", "cerca"] {
            if let valor = item[chave] as? String, !valor.isEmpty {
                corpo[chave] = valor
            }
        }
        guard let dados = try? JSONSerialization.data(withJSONObject: corpo) else {
            fim(.descartar)
            return
        }
        pedido.httpBody = dados
        URLSession.shared.dataTask(with: pedido) { _, resposta, erro in
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            if erro != nil || status == 0 {
                fim(.tentarDepois)
            } else if (200..<300).contains(status) {
                fim(.enviado)
            } else if status == 400 {
                fim(.descartar)  // dado que o painel nunca vai aceitar: não trava a fila
            } else {
                fim(.tentarDepois)  // 401 (token), 403 (modo visitante), 5xx: guarda
            }
        }.resume()
    }
}

/// Seção da tela Configurar: estado da permissão e o botão de pedir.
struct SecaoOndeEstou: View {
    @ObservedObject private var localizacao = Localizacao.shared

    private var rotuloBotao: String {
        let podePedir = localizacao.status == .notDetermined || localizacao.status == .authorizedWhenInUse
        return podePedir ? "Permitir “Sempre”" : "Abrir Ajustes do iPhone"
    }

    var body: some View {
        Section {
            HStack {
                Text("Localização")
                Spacer()
                Text(localizacao.descricaoStatus).foregroundColor(.secondary)
            }
            if localizacao.status != .authorizedAlways {
                Button(rotuloBotao) {
                    localizacao.pedirPermissao()
                }
            }
            if localizacao.status == .authorizedAlways {
                HStack {
                    Text("Cercas nos teus lugares")
                    Spacer()
                    Text("\(localizacao.cercasAtivas)").foregroundColor(.secondary)
                }
            }
            if localizacao.gpsSempre {
                HStack {
                    Text("Movimento")
                    Spacer()
                    Text(localizacao.descricaoMovimento).foregroundColor(.secondary)
                }
                if localizacao.statusMovimento == .denied {
                    Button("Abrir Ajustes do iPhone") {
                        localizacao.abrirAjustes()
                    }
                }
                HStack {
                    Text("Agora")
                    Spacer()
                    Text(localizacao.dirigindo ? "Dirigindo (GPS de estrada)" : "GPS econômico").foregroundColor(.secondary)
                }
            }
            if localizacao.pendentes > 0 {
                HStack {
                    Text("Esperando o painel")
                    Spacer()
                    Text("\(localizacao.pendentes)").foregroundColor(.secondary)
                }
            }
        } header: {
            Text("Onde eu estou")
        } footer: {
            Text("Com “Sempre”, o iPhone avisa o painel quando tu chega e sai de um lugar (mecânico, casa…). Só o lugar onde tu parou, nunca o caminho. Com o GPS sempre ligado e a permissão Movimento, de carro o GPS vira de estrada sozinho; parou, volta pro econômico. Numa viagem planejada a posição vai pro painel enquanto tu dirige e é apagada quando a viagem acaba.")
        }
    }
}
