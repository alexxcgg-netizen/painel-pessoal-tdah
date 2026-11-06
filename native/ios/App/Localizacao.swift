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
//  Cada visita vai pra POST /api/localizacao/visita com o token do widget no header (nunca na
//  URL). Sem rede ou PC desligado: fica numa fila no UserDefaults (até 50, a mais velha sai) e vai
//  quando der (próxima visita ou quando o app abre).
//

import CoreLocation
import SwiftUI
import UIKit

final class Localizacao: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = Localizacao()
    static let chaveFila = "painel_visitas_fila"
    static let maxFila = 50
    static let chaveGps = "painel_gps_sempre"
    static let conferirACada: TimeInterval = 5 * 60

    @Published private(set) var status: CLAuthorizationStatus = .notDetermined
    @Published private(set) var pendentes = 0
    @Published private(set) var gpsSempre = false

    private let gerente = CLLocationManager()
    private var enviando = false
    private let iso = ISO8601DateFormatter()
    private var relogioGps: Timer?
    private var ultimaConferida = Date.distantPast

    private override init() {
        super.init()
        gerente.delegate = self
        status = gerente.authorizationStatus
        pendentes = lerFila().count
        gpsSempre = Ajustes.defaults.bool(forKey: Localizacao.chaveGps)
    }

    /// AppDelegate chama no launch (inclusive quando o iOS relança o app em segundo plano por uma visita
    /// ou por uma mudança grande de lugar).
    func iniciar() {
        ligarConformePermissao()
        enviarFila()
    }

    private func ligarConformePermissao() {
        if gerente.authorizationStatus == .authorizedAlways {
            gerente.startMonitoringVisits()
            gerente.startMonitoringSignificantLocationChanges()
            if gpsSempre { ligarGps() }
        } else {
            gerente.stopMonitoringVisits()
            gerente.stopMonitoringSignificantLocationChanges()
            desligarGps()
        }
    }

    // MARK: GPS sempre ligado (botão do Configurar)

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
        gerente.desiredAccuracy = kCLLocationAccuracyThreeKilometers  // antena/wi-fi: quase sem bateria
        gerente.distanceFilter = 500
        gerente.pausesLocationUpdatesAutomatically = false
        gerente.allowsBackgroundLocationUpdates = true
        gerente.showsBackgroundLocationIndicator = false
        gerente.startUpdatingLocation()
        relogioGps?.invalidate()
        relogioGps = Timer.scheduledTimer(withTimeInterval: Localizacao.conferirACada, repeats: true) { [weak self] _ in
            self?.conferirPainel(forcar: true)
        }
    }

    private func desligarGps() {
        relogioGps?.invalidate()
        relogioGps = nil
        gerente.stopUpdatingLocation()
        gerente.allowsBackgroundLocationUpdates = false
    }

    /// Avisos e ilha, no máximo 1x a cada ~5 min (o GPS e a mudança de lugar podem chamar seguido).
    private func conferirPainel(forcar: Bool = false) {
        DispatchQueue.main.async {
            let agora = Date()
            guard forcar || agora.timeIntervalSince(self.ultimaConferida) > Localizacao.conferirACada - 30 else { return }
            self.ultimaConferida = agora
            AvisosLocais.shared.sincronizar(motivo: self.gpsSempre ? "gps" : "lugar")
            AoVivo.shared.sincronizar()
        }
    }

    /// Botão da tela Configurar. Negada/bloqueada: só os Ajustes do iPhone mudam.
    func pedirPermissao() {
        switch gerente.authorizationStatus {
        case .notDetermined, .authorizedWhenInUse:
            gerente.requestAlwaysAuthorization()
        default:
            if let url = URL(string: UIApplication.openSettingsURLString) {
                UIApplication.shared.open(url)
            }
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

    // MARK: CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let novo = manager.authorizationStatus
        DispatchQueue.main.async { self.status = novo }
        ligarConformePermissao()
    }

    /// Mudança grande de lugar (~500 m) ou o GPS sempre ligado: confere os avisos (com intervalo mínimo).
    /// A posição em si não vai pra lugar nenhum - só as visitas vão pro painel.
    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
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
        }
    }

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
            Text("Com “Sempre”, o iPhone avisa o painel quando tu chega e sai de um lugar (mecânico, casa…). Só o lugar onde tu parou, nunca o caminho.")
        }
    }
}
