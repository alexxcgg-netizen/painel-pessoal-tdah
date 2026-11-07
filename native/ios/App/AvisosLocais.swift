//
//  AvisosLocais.swift
//  Leva "avisos no app" (2026-11-06, docs/briefings/2026-11-06-avisos-app.md)
//
//  A conta grátis da Apple não tem push remoto (APNs). Aviso LOCAL tem: o app agenda e o iPhone toca
//  na hora certa, mesmo com o app fechado e o PC desligado.
//
//  sincronizar():
//    1. GET /api/app/avisos (token do widget no header): os avisos de hora conhecida de hoje e de
//       amanhã (se arrumar, hora de sair, tarefa com hora, voo), com a mesma conta e o mesmo texto do
//       servidor;
//    2. troca tudo que estava agendado ("painel-*") pelo que veio;
//    3. POST /api/app/avisos/agendados com o que ficou agendado. O servidor não manda esses pelo
//       navegador, pra não chegar dois.
//  Sem rede ou com o painel desligado, o que já estava agendado fica como está.
//
//  Quem chama: abrir/voltar/sair do app (PainelApp.swift), Feito/Adiar no aviso, a atualização em
//  segundo plano (BGAppRefreshTask, de ~30 em ~30 min quando o iOS deixa), visita e mudança grande
//  de lugar, e o GPS sempre ligado (Localizacao.swift).
//
//  Botões "Feito" / "Adiar 1 h" nos avisos de tarefa -> POST /api/app/aviso/acao. O toque no aviso
//  para a insistência e abre a aba certa dentro do app.
//
//  07/11 (frente C, docs/briefings/2026-11-07-lugar-certo-e-avisos.md):
//    - fila do painel: depois de agendar, GET /api/app/avisos/pendentes (atraso, insistência, aviso da IA...)
//      vira aviso LOCAL ("fila-<id>", na hora ou na hora marcada) e POST .../pendentes/entregues conta o que
//      ficou. O navegador só manda o que o app não pegou em 3/15 min. Toda chance de acordar passa por aqui;
//    - botões por assunto: "hora" (Feito / +15 min / Amanhã), "saida" (Abrir rota / +15 min), "soneca"
//      (+15 min). "+15 min" = o app avisa de novo daqui 15 min com o mesmo texto (sem mexer na tarefa).
//

import BackgroundTasks
import Foundation
import SwiftUI
import UIKit
import UserNotifications
import WidgetKit

struct AvisoDoPainel: Decodable {
    let id: String
    let tag: String
    let tipo: String
    let quando_ts: Double
    let titulo: String
    let corpo: String
    let acoes: Bool
    /// "tarefa" (Feito / Adiar 1 h), "casa" (Feito / Amanhã - "Chegou em casa", hora_certa.py) ou "" (sem botão).
    /// Opcional: servidor antigo não manda e o app segue só com `acoes`.
    /// 07/11: também "hora", "saida", "soneca" (AvisosLocais.categoriaDe).
    let categoria: String?
    /// Link do Waze pro botão "Abrir rota" (categoria "saida"). Opcional.
    let rota: String?
    let url: String
}

private struct RespostaAvisos: Decodable {
    let avisos: [AvisoDoPainel]
}

/// Item da fila do painel (07/11): aviso sem hora conhecida que o app mostra como aviso local.
struct AvisoPendente: Decodable {
    let id: Int
    let ident: String
    let tag: String
    let tipo: String
    let titulo: String
    let corpo: String
    let quando_ts: Double
    let categoria: String?
    let rota: String?
    let url: String
}

private struct RespostaPendentes: Decodable {
    let avisos: [AvisoPendente]
}

final class AvisosLocais: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = AvisosLocais()
    static let prefixo = "painel-"
    /// Igual a BGTaskSchedulerPermittedIdentifiers no project.yml (checar_projeto.py confere).
    static let tarefaFundo = "com.alexxcgg.painel.avisos"
    static let categoriaTarefa = "painel-tarefa"
    static let categoriaCasa = "painel-casa"
    // 07/11: botões por assunto (o servidor manda "hora" / "saida" / "soneca" em `categoria`)
    static let categoriaHora = "painel-hora"
    static let categoriaSaida = "painel-saida"
    static let categoriaSoneca = "painel-soneca"
    static let prefixoFila = "fila-"
    static let sonecaMin: TimeInterval = 15
    static let fundoACada: TimeInterval = 30 * 60

    private static let chaveUltima = "painel_avisos_ultima"
    private static let chaveResultado = "painel_avisos_resultado"
    private static let chaveFundo = "painel_avisos_fundo"
    private static let chaveAssinatura = "painel_avisos_assinatura"

    @Published private(set) var permissao: UNAuthorizationStatus = .notDetermined
    @Published private(set) var agendados = 0
    @Published private(set) var ultima: Date?
    @Published private(set) var resultado = ""

    private let centro = UNUserNotificationCenter.current()
    private var rodando = false  // só mexido na main thread
    private var esperando: [(Bool) -> Void] = []

    private override init() {
        super.init()
        let d = Ajustes.defaults
        let t = d.double(forKey: AvisosLocais.chaveUltima)
        ultima = t > 0 ? Date(timeIntervalSince1970: t) : nil
        resultado = d.string(forKey: AvisosLocais.chaveResultado) ?? ""
    }

    /// AppDelegate, no didFinishLaunching (o iOS exige o registro da tarefa de fundo antes do fim do launch).
    func iniciar() {
        centro.delegate = self
        let feito = UNNotificationAction(identifier: "feito", title: "Feito", options: [])
        let adiar = UNNotificationAction(identifier: "adiar", title: "Adiar 1 h", options: [])
        let amanha = UNNotificationAction(identifier: "amanha", title: "Amanhã", options: [])
        let mais15 = UNNotificationAction(identifier: "mais15", title: "+15 min", options: [])
        // abrir o Waze precisa do app na frente
        let rota = UNNotificationAction(identifier: "rota", title: "Abrir rota", options: [.foreground])
        centro.setNotificationCategories([
            UNNotificationCategory(identifier: AvisosLocais.categoriaTarefa, actions: [feito, adiar],
                                   intentIdentifiers: [], options: []),
            UNNotificationCategory(identifier: AvisosLocais.categoriaCasa, actions: [feito, amanha],
                                   intentIdentifiers: [], options: []),
            UNNotificationCategory(identifier: AvisosLocais.categoriaHora, actions: [feito, mais15, amanha],
                                   intentIdentifiers: [], options: []),
            UNNotificationCategory(identifier: AvisosLocais.categoriaSaida, actions: [rota, mais15],
                                   intentIdentifiers: [], options: []),
            UNNotificationCategory(identifier: AvisosLocais.categoriaSoneca, actions: [mais15],
                                   intentIdentifiers: [], options: [])
        ])
        _ = BGTaskScheduler.shared.register(forTaskWithIdentifier: AvisosLocais.tarefaFundo, using: nil) { tarefa in
            guard let tarefa = tarefa as? BGAppRefreshTask else {
                tarefa.setTaskCompleted(success: false)
                return
            }
            self.rodarFundo(tarefa)
        }
        atualizarPermissao()
    }

    // MARK: Permissão

    func atualizarPermissao() {
        centro.getNotificationSettings { ajustes in
            DispatchQueue.main.async { self.permissao = ajustes.authorizationStatus }
        }
    }

    /// Primeira abertura com token: o iOS pergunta uma vez só. Negado: só os Ajustes do iPhone mudam.
    func pedirPermissao(abrirAjustesSeNegado: Bool = false) {
        centro.getNotificationSettings { ajustes in
            switch ajustes.authorizationStatus {
            case .notDetermined:
                self.centro.requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in
                    self.atualizarPermissao()
                    DispatchQueue.main.async { self.sincronizar(motivo: "permissão") }
                }
            case .denied:
                guard abrirAjustesSeNegado else { return }
                DispatchQueue.main.async {
                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                }
            default:
                break
            }
        }
    }

    var descricaoPermissao: String {
        switch permissao {
        case .authorized, .provisional, .ephemeral: return "Ligados"
        case .denied: return "Desligados nos Ajustes"
        case .notDetermined: return "Ainda não pedidos"
        @unknown default: return "?"
        }
    }

    var podeAvisar: Bool { AvisosLocais.liberados.contains(permissao) }

    static let liberados: [UNAuthorizationStatus] = [.authorized, .provisional, .ephemeral]

    // MARK: Sincronizar

    /// Chamar na main thread. `fim(true)` quando conseguiu falar com o painel.
    func sincronizar(motivo: String, fim: ((Bool) -> Void)? = nil) {
        if let fim { esperando.append(fim) }
        guard !rodando else { return }
        guard let base = AvisosLocais.base(), !Ajustes.token.isEmpty else {
            terminar(false, texto: nil)
            return
        }
        rodando = true
        let app = UIApplication.shared
        var tarefa: UIBackgroundTaskIdentifier = .invalid
        tarefa = app.beginBackgroundTask(withName: "painel-avisos") {
            if tarefa != .invalid {
                app.endBackgroundTask(tarefa)
                tarefa = .invalid
            }
        }
        let fechar: (Bool, String) -> Void = { ok, texto in
            DispatchQueue.main.async {
                self.rodando = false
                self.terminar(ok, texto: "\(texto) (\(motivo))")
                if tarefa != .invalid {
                    app.endBackgroundTask(tarefa)
                    tarefa = .invalid
                }
            }
        }
        centro.getNotificationSettings { ajustes in
            DispatchQueue.main.async { self.permissao = ajustes.authorizationStatus }
            guard AvisosLocais.liberados.contains(ajustes.authorizationStatus) else {
                fechar(false, "sem permissão de aviso")
                return
            }
            self.buscar(base: base) { avisos in
                guard let avisos else {
                    fechar(false, "painel não respondeu")
                    return
                }
                self.agendar(avisos) { feitos in
                    self.contarAgendados(feitos, base: base)
                    DispatchQueue.main.async {
                        self.agendados = feitos.count
                        self.recarregarWidgetsSeMudou(avisos)
                    }
                    // 07/11: a fila do painel (o que não tem hora conhecida) vira aviso local agora
                    self.pegarFila(base: base) { pegos in
                        fechar(true, "ok: \(feitos.count) agendados, \(pegos) da fila")
                    }
                }
            }
        }
    }

    /// Lista de avisos diferente da ultima = tarefa criada, feita ou mudada no painel: os widgets acompanham
    /// (em segundo plano o WidgetKit conta isso no orcamento dele, por isso so quando mudou de verdade).
    private func recarregarWidgetsSeMudou(_ avisos: [AvisoDoPainel]) {
        let assinatura = avisos.map { "\($0.id)|\(Int($0.quando_ts))|\($0.titulo)" }.joined(separator: ";")
        let d = Ajustes.defaults
        guard d.string(forKey: AvisosLocais.chaveAssinatura) != assinatura else { return }
        d.set(assinatura, forKey: AvisosLocais.chaveAssinatura)
        WidgetCenter.shared.reloadAllTimelines()
    }

    private func terminar(_ ok: Bool, texto: String?) {
        if let texto {
            let agora = Date()
            ultima = agora
            resultado = texto
            Ajustes.defaults.set(agora.timeIntervalSince1970, forKey: AvisosLocais.chaveUltima)
            Ajustes.defaults.set(texto, forKey: AvisosLocais.chaveResultado)
        }
        agendarFundo()
        let lista = esperando
        esperando = []
        lista.forEach { $0(ok) }
    }

    static func base() -> String? {
        var b = Ajustes.url.trimmingCharacters(in: .whitespacesAndNewlines)
        while b.hasSuffix("/") { b.removeLast() }
        guard let url = URL(string: b), url.scheme?.hasPrefix("http") == true else { return nil }
        return b
    }

    static func pedido(_ caminho: String, base: String, corpo: [String: Any]? = nil) -> URLRequest? {
        guard let url = URL(string: base + caminho) else { return nil }
        var p = URLRequest(url: url)
        p.httpMethod = corpo == nil ? "GET" : "POST"
        p.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        p.timeoutInterval = 15
        if let corpo, let dados = try? JSONSerialization.data(withJSONObject: corpo) {
            p.setValue("application/json", forHTTPHeaderField: "Content-Type")
            p.httpBody = dados
        }
        return p
    }

    private func buscar(base: String, fim: @escaping ([AvisoDoPainel]?) -> Void) {
        guard let p = AvisosLocais.pedido("/api/app/avisos", base: base) else { return fim(nil) }
        URLSession.shared.dataTask(with: p) { dados, resposta, _ in
            guard (resposta as? HTTPURLResponse)?.statusCode == 200, let dados,
                  let r = try? JSONDecoder().decode(RespostaAvisos.self, from: dados) else { return fim(nil) }
            fim(r.avisos)
        }.resume()
    }

    /// Troca os avisos "painel-*" pendentes pelos novos. Devolve os que o iPhone aceitou.
    private func agendar(_ avisos: [AvisoDoPainel], fim: @escaping ([AvisoDoPainel]) -> Void) {
        let agora = Date().timeIntervalSince1970
        let validos = avisos.filter { $0.quando_ts - agora >= 5 }.prefix(50)
        let novos = Set(validos.map { $0.id })
        centro.getPendingNotificationRequests { pendentes in
            let velhos = pendentes.map { $0.identifier }.filter { $0.hasPrefix(AvisosLocais.prefixo) && !novos.contains($0) }
            self.centro.removePendingNotificationRequests(withIdentifiers: velhos)
            let grupo = DispatchGroup()
            let trava = NSLock()
            var aceitos: [AvisoDoPainel] = []
            for aviso in validos {
                let c = UNMutableNotificationContent()
                c.title = aviso.titulo
                c.body = aviso.corpo
                c.sound = .default
                c.threadIdentifier = aviso.tipo
                c.userInfo = ["tag": aviso.tag, "url": aviso.url, "rota": aviso.rota ?? ""]
                if let cat = AvisosLocais.categoriaDe(aviso.categoria, acoes: aviso.acoes) {
                    c.categoryIdentifier = cat
                }
                let gatilho = UNTimeIntervalNotificationTrigger(timeInterval: max(1, aviso.quando_ts - agora), repeats: false)
                grupo.enter()
                self.centro.add(UNNotificationRequest(identifier: aviso.id, content: c, trigger: gatilho)) { erro in
                    if erro == nil {
                        trava.lock()
                        aceitos.append(aviso)
                        trava.unlock()
                    }
                    grupo.leave()
                }
            }
            grupo.notify(queue: .global()) { fim(aceitos) }
        }
    }

    /// "hora" / "saida" / "soneca" / "tarefa" / "casa" -> categoria registrada em iniciar(). Desconhecida: Feito/Adiar
    /// se o aviso é de tarefa (`acoes`), senão sem botão.
    static func categoriaDe(_ categoria: String?, acoes: Bool) -> String? {
        switch categoria ?? "" {
        case "casa": return categoriaCasa
        case "tarefa": return categoriaTarefa
        case "hora": return categoriaHora
        case "saida": return categoriaSaida
        case "soneca": return categoriaSoneca
        default: return acoes ? categoriaTarefa : nil
        }
    }

    // MARK: Fila do painel (07/11)

    /// Busca a fila, agenda cada item ("fila-<id>": na hora marcada ou em 1 s) e conta de volta o que ficou.
    /// `fim(n)` com quantos pegou (0 sem rede: o navegador manda no prazo).
    private func pegarFila(base: String, fim: @escaping (Int) -> Void) {
        guard let p = AvisosLocais.pedido("/api/app/avisos/pendentes", base: base) else { return fim(0) }
        URLSession.shared.dataTask(with: p) { dados, resposta, _ in
            guard (resposta as? HTTPURLResponse)?.statusCode == 200, let dados,
                  let r = try? JSONDecoder().decode(RespostaPendentes.self, from: dados), !r.avisos.isEmpty else {
                return fim(0)
            }
            let agora = Date().timeIntervalSince1970
            let grupo = DispatchGroup()
            let trava = NSLock()
            var pegos: [Int] = []
            for aviso in r.avisos {
                let c = UNMutableNotificationContent()
                c.title = aviso.titulo
                c.body = aviso.corpo
                c.sound = .default
                c.threadIdentifier = aviso.tipo
                c.userInfo = ["tag": aviso.tag, "url": aviso.url, "rota": aviso.rota ?? ""]
                if let cat = AvisosLocais.categoriaDe(aviso.categoria, acoes: false) {
                    c.categoryIdentifier = cat
                }
                let gatilho = UNTimeIntervalNotificationTrigger(timeInterval: max(1, aviso.quando_ts - agora), repeats: false)
                grupo.enter()
                self.centro.add(UNNotificationRequest(identifier: aviso.ident, content: c, trigger: gatilho)) { erro in
                    if erro == nil {
                        trava.lock()
                        pegos.append(aviso.id)
                        trava.unlock()
                    }
                    grupo.leave()
                }
            }
            grupo.notify(queue: .global()) {
                guard !pegos.isEmpty,
                      let q = AvisosLocais.pedido("/api/app/avisos/pendentes/entregues", base: base, corpo: ["ids": pegos]) else {
                    return fim(pegos.count)
                }
                URLSession.shared.dataTask(with: q) { _, _, _ in fim(pegos.count) }.resume()
            }
        }.resume()
    }

    /// "+15 min": o mesmo aviso de novo daqui 15 min (local, não mexe na tarefa).
    private func soneca(_ pedido: UNNotificationRequest) {
        guard let c = pedido.content.mutableCopy() as? UNMutableNotificationContent else { return }
        let gatilho = UNTimeIntervalNotificationTrigger(timeInterval: AvisosLocais.sonecaMin * 60, repeats: false)
        let ident = "soneca-\(pedido.identifier)-\(Int(Date().timeIntervalSince1970))"
        centro.add(UNNotificationRequest(identifier: ident, content: c, trigger: gatilho), withCompletionHandler: nil)
    }

    private func contarAgendados(_ avisos: [AvisoDoPainel], base: String) {
        let itens = avisos.map { ["tag": $0.tag, "quando_ts": Int($0.quando_ts)] as [String: Any] }
        guard let p = AvisosLocais.pedido("/api/app/avisos/agendados", base: base, corpo: ["itens": itens]) else { return }
        URLSession.shared.dataTask(with: p).resume()
    }

    // MARK: Segundo plano (BGAppRefreshTask)

    func agendarFundo() {
        let pedido = BGAppRefreshTaskRequest(identifier: AvisosLocais.tarefaFundo)
        pedido.earliestBeginDate = Date(timeIntervalSinceNow: AvisosLocais.fundoACada)
        try? BGTaskScheduler.shared.submit(pedido)
    }

    var acordadasNoFundo: Int { Ajustes.defaults.integer(forKey: AvisosLocais.chaveFundo) }

    private func rodarFundo(_ tarefa: BGAppRefreshTask) {
        var acabou = false
        let concluir: (Bool) -> Void = { ok in
            DispatchQueue.main.async {
                guard !acabou else { return }
                acabou = true
                tarefa.setTaskCompleted(success: ok)
            }
        }
        tarefa.expirationHandler = { concluir(false) }
        DispatchQueue.main.async {
            Ajustes.defaults.set(self.acordadasNoFundo + 1, forKey: AvisosLocais.chaveFundo)
            AoVivo.shared.sincronizar()  // a ilha também anda
            self.sincronizar(motivo: "fundo") { ok in concluir(ok) }
        }
    }

    // MARK: Toque e botões (UNUserNotificationCenterDelegate)

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // com o app aberto o aviso aparece igual (o Alex pode estar em outra aba)
        completionHandler([.banner, .list, .sound])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        let tag = info["tag"] as? String ?? ""
        let caminho = info["url"] as? String ?? "/"
        let rota = info["rota"] as? String ?? ""
        let acao: String
        switch response.actionIdentifier {
        case "feito": acao = "feito"
        case "adiar": acao = "adiar"
        case "amanha": acao = "amanha"
        case "mais15": acao = "mais15"
        case "rota": acao = "rota"
        case UNNotificationDefaultActionIdentifier: acao = "toque"
        default:
            completionHandler()
            return
        }
        if acao == "toque" {
            DispatchQueue.main.async { Abertura.shared.caminho = caminho }
        }
        if acao == "mais15" {
            soneca(response.notification.request)
        }
        if acao == "rota", let url = URL(string: rota), url.scheme?.hasPrefix("http") == true {
            DispatchQueue.main.async { UIApplication.shared.open(url) }
        }
        guard !tag.isEmpty, let base = AvisosLocais.base(),
              let p = AvisosLocais.pedido("/api/app/aviso/acao", base: base, corpo: ["tag": tag, "acao": acao]) else {
            completionHandler()
            return
        }
        let app = UIApplication.shared
        var tarefa: UIBackgroundTaskIdentifier = .invalid
        tarefa = app.beginBackgroundTask(withName: "painel-aviso-acao") {
            if tarefa != .invalid {
                app.endBackgroundTask(tarefa)
                tarefa = .invalid
            }
        }
        URLSession.shared.dataTask(with: p) { _, _, _ in
            DispatchQueue.main.async {
                let fechar: () -> Void = {
                    completionHandler()
                    if tarefa != .invalid {
                        app.endBackgroundTask(tarefa)
                        tarefa = .invalid
                    }
                }
                // Feito/Adiar/Amanhã mudam a tarefa: tira o "daqui a pouco" que ficou agendado pra ela, e a tarefa
                // ao vivo (se for ela) sai ou anda pra hora nova
                if acao == "toque" || acao == "rota" || acao == "mais15" {
                    fechar()
                } else {
                    AoVivo.shared.sincronizar()
                    self.sincronizar(motivo: acao) { _ in fechar() }
                }
            }
        }.resume()
    }
}

/// Seção da tela Configurar: avisos do app e o GPS sempre ligado.
struct SecaoAvisos: View {
    @ObservedObject private var avisos = AvisosLocais.shared
    @ObservedObject private var localizacao = Localizacao.shared

    private var ultimaTexto: String {
        guard let u = avisos.ultima else { return "nunca" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "pt_BR")
        f.dateFormat = Calendar.current.isDateInToday(u) ? "HH:mm" : "dd/MM HH:mm"
        return f.string(from: u)
    }

    var body: some View {
        Section {
            HStack {
                Text("Avisos")
                Spacer()
                Text(avisos.descricaoPermissao).foregroundColor(.secondary)
            }
            if !avisos.podeAvisar {
                Button(avisos.permissao == .denied ? "Abrir Ajustes do iPhone" : "Ligar avisos") {
                    avisos.pedirPermissao(abrirAjustesSeNegado: true)
                }
            }
            HStack {
                Text("Agendados")
                Spacer()
                Text("\(avisos.agendados)").foregroundColor(.secondary)
            }
            HStack {
                Text("Última conferida")
                Spacer()
                Text(ultimaTexto).foregroundColor(.secondary)
            }
            Toggle("GPS sempre ligado", isOn: Binding(
                get: { localizacao.gpsSempre },
                set: { localizacao.definirGpsSempre($0) }
            ))
        } header: {
            Text("Avisos do app")
        } footer: {
            Text("O iPhone toca na hora certa mesmo com o app fechado e o PC desligado. Com o GPS sempre ligado, o app fica acordado e confere o painel a cada 5 min (avisos e ilha), mas gasta mais bateria.")
        }
        .onAppear {
            avisos.atualizarPermissao()
            UNUserNotificationCenter.current().getPendingNotificationRequests { p in
                let n = p.filter { $0.identifier.hasPrefix(AvisosLocais.prefixo) }.count
                DispatchQueue.main.async { avisos.agendadosVistos(n) }
            }
        }
    }
}

extension AvisosLocais {
    /// O número de verdade que o iPhone tem pendente (a tela abre antes da primeira sincronizada).
    func agendadosVistos(_ n: Int) { agendados = n }
}
