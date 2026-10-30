//
//  Relatorio.swift
//  Tela "Gerar relatório" do app (2026-10-30)
//
//  Não há Mac nem simulador no PC: este relatório é o jeito de saber o que o app consegue fazer no
//  iPhone de verdade. Só olha (não pede permissão nenhuma) e manda pro painel com o token do widget.
//  Endereço e token NUNCA entram no relatório, nem no texto copiado: só o tipo de endereço.
//

import ActivityKit
import AVFoundation
import CoreLocation
import Network
import Photos
import SwiftUI
import UIKit
import UserNotifications
import WebKit
import WidgetKit

enum EstadoLinha {
    case ok, atencao, falha, info

    var icone: String {
        switch self {
        case .ok: return "checkmark.circle.fill"
        case .atencao: return "exclamationmark.triangle.fill"
        case .falha: return "xmark.octagon.fill"
        case .info: return "info.circle"
        }
    }

    var cor: Color {
        switch self {
        case .ok: return Color(red: 0.62, green: 0.86, blue: 0.69)
        case .atencao: return Color(red: 1.0, green: 0.83, blue: 0.43)
        case .falha: return Color(red: 1.0, green: 0.62, blue: 0.56)
        case .info: return .secondary
        }
    }
}

struct LinhaRelatorio: Identifiable {
    let id = UUID()
    let grupo: String
    let titulo: String
    let valor: String
    let estado: EstadoLinha
}

@MainActor
final class Relatorio: ObservableObject {
    @Published var linhas: [LinhaRelatorio] = []
    @Published var rodando = false
    @Published var envio = ""
    @Published var ilhaLigada = false
    @Published var ilhaResposta = ""

    private var dados: [String: Any] = [:]
    private var atividade: Activity<IlhaTesteAtributos>?

    var grupos: [String] {
        var vistos: [String] = []
        for l in linhas where !vistos.contains(l.grupo) { vistos.append(l.grupo) }
        return vistos
    }

    var texto: String {
        linhas.map { "[\($0.grupo)] \($0.titulo): \($0.valor)" }.joined(separator: "\n")
    }

    private func add(_ grupo: String, _ titulo: String, _ valor: String, _ estado: EstadoLinha = .info,
                     chave: String, dado: Any? = nil) {
        linhas.append(LinhaRelatorio(grupo: grupo, titulo: titulo, valor: valor, estado: estado))
        dados[chave] = dado ?? valor
    }

    func gerar() async {
        rodando = true
        envio = ""
        linhas = []
        dados = ["gerado_em": ISO8601DateFormatter().string(from: Date())]
        aparelho()
        assinatura()
        grupoDoApp()
        await widgets()
        ilha()
        await permissoes()
        await rede()
        await paginaWeb()
        rodando = false
        await enviar()
    }

    // MARK: Aparelho

    private func maquina() -> String {
        var sis = utsname()
        uname(&sis)
        return withUnsafeBytes(of: &sis.machine) { bytes in
            String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self)
        }
    }

    private func aparelho() {
        let g = "Aparelho"
        let info = Bundle.main.infoDictionary ?? [:]
        add(g, "Modelo", maquina(), chave: "modelo")
        add(g, "iOS", UIDevice.current.systemVersion, chave: "ios")
        add(g, "App", "\(info["CFBundleShortVersionString"] ?? "?") (\(info["CFBundleVersion"] ?? "?"))", chave: "app_versao")
        add(g, "Identificador", Bundle.main.bundleIdentifier ?? "?", chave: "bundle_id")
        let janela = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first?.windows.first
        let topo = Double(janela?.safeAreaInsets.top ?? 0)
        add(g, "Área segura no topo", "\(Int(topo)) pt", chave: "safe_area_topo", dado: topo)
        // 59 pt ou mais = recorte da Dynamic Island; entalhe antigo fica em 47-50 (não conferido em todo modelo)
        let temIlha = topo >= 59
        add(g, "Tem Dynamic Island", temIlha ? "sim" : "parece que não", temIlha ? .ok : .atencao,
            chave: "tem_ilha", dado: temIlha)
        add(g, "Modo pouca energia", ProcessInfo.processInfo.isLowPowerModeEnabled ? "ligado" : "desligado",
            chave: "pouca_energia", dado: ProcessInfo.processInfo.isLowPowerModeEnabled)
        let segundoPlano: String
        switch UIApplication.shared.backgroundRefreshStatus {
        case .available: segundoPlano = "liberada"
        case .denied: segundoPlano = "negada"
        case .restricted: segundoPlano = "restrita"
        @unknown default: segundoPlano = "?"
        }
        add(g, "Atualização em segundo plano", segundoPlano, chave: "segundo_plano")
    }

    // MARK: Assinatura

    private func provisao() -> [String: Any]? {
        guard let caminho = Bundle.main.path(forResource: "embedded", ofType: "mobileprovision"),
              let bruto = FileManager.default.contents(atPath: caminho),
              let ini = bruto.range(of: Data("<?xml".utf8)),
              let fim = bruto.range(of: Data("</plist>".utf8)) else { return nil }
        let xml = bruto.subdata(in: ini.lowerBound..<fim.upperBound)
        return (try? PropertyListSerialization.propertyList(from: xml, format: nil)) as? [String: Any]
    }

    private func assinatura() {
        let g = "Assinatura"
        guard let p = provisao() else {
            add(g, "Perfil de instalação", "não achei", .atencao, chave: "provisao", dado: "ausente")
            return
        }
        if let validade = p["ExpirationDate"] as? Date {
            let dias = Int(validade.timeIntervalSinceNow / 86400)
            add(g, "Expira em", "\(dias) dias", dias > 2 ? .ok : .atencao, chave: "provisao_dias", dado: dias)
        }
        let ent = p["Entitlements"] as? [String: Any] ?? [:]
        let grupos = ent["com.apple.security.application-groups"] as? [String] ?? []
        add(g, "App Groups autorizados", grupos.isEmpty ? "nenhum" : grupos.joined(separator: ", "),
            grupos.contains(Ajustes.appGroupID) ? .ok : .falha, chave: "provisao_grupos",
            dado: grupos.joined(separator: ", "))
        let push = ent["aps-environment"] != nil
        add(g, "Push nativo", push ? "liberado" : "não (normal na conta grátis)", chave: "provisao_push", dado: push)
    }

    // MARK: App Group

    private func grupoDoApp() {
        let g = "App Group"
        let pasta = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: Ajustes.appGroupID)
        add(g, "Pasta compartilhada", pasta != nil ? "existe" : "não existe", pasta != nil ? .ok : .falha,
            chave: "grupo_pasta", dado: pasta != nil)
        let marca = UUID().uuidString
        Ajustes.defaults.set(marca, forKey: "painel_relatorio_marca")
        let voltou = Ajustes.defaults.string(forKey: "painel_relatorio_marca") == marca
        add(g, "Grava e lê", voltou ? "sim" : "não", voltou ? .ok : .falha, chave: "grupo_grava", dado: voltou)
        add(g, "Endereço salvo", Ajustes.url.isEmpty ? "não" : "sim", Ajustes.url.isEmpty ? .falha : .ok,
            chave: "tem_endereco", dado: !Ajustes.url.isEmpty)
        add(g, "Token salvo", Ajustes.token.isEmpty ? "não" : "sim", Ajustes.token.isEmpty ? .falha : .ok,
            chave: "tem_chave_widget", dado: !Ajustes.token.isEmpty)
    }

    // MARK: Widgets

    private func widgets() async {
        let g = "Widgets"
        let lista: [WidgetInfo] = await withCheckedContinuation { fim in
            WidgetCenter.shared.getCurrentConfigurations { resultado in
                fim.resume(returning: (try? resultado.get()) ?? [])
            }
        }
        let familias = lista.map { String(describing: $0.family) }.joined(separator: ", ")
        add(g, "Instalados", lista.isEmpty ? "nenhum ainda" : "\(lista.count): \(familias)",
            lista.isEmpty ? .atencao : .ok, chave: "widgets", dado: lista.isEmpty ? "nenhum" : familias)

        // Sinal de vida que o próprio widget grava: é a prova de que app e widget enxergam o mesmo App Group
        let d = Ajustes.defaults
        if let em = d.object(forKey: "painel_widget_diag_em") as? Date {
            let resultado = d.string(forKey: "painel_widget_diag_resultado") ?? "?"
            let min = Int(Date().timeIntervalSince(em) / 60)
            add(g, "Última busca do widget", "há \(min) min: \(resultado)", resultado == "ok" ? .ok : .falha,
                chave: "widget_busca", dado: resultado)
            add(g, "Widget fala com o app", "sim", .ok, chave: "widget_fala_app", dado: true)
            dados["widget_busca_min"] = min
        } else {
            add(g, "Widget fala com o app", lista.isEmpty ? "põe um widget e gera de novo" : "não: o App Group não uniu os dois",
                lista.isEmpty ? .atencao : .falha, chave: "widget_fala_app", dado: false)
        }
        WidgetCenter.shared.reloadAllTimelines()
        if #available(iOS 18.0, *) {
            add(g, "Central de Controle", "disponível neste iOS", .ok, chave: "central", dado: true)
        } else {
            add(g, "Central de Controle", "precisa de iOS 18", .atencao, chave: "central", dado: false)
        }
    }

    // MARK: Dynamic Island

    private func ilha() {
        let g = "Dynamic Island"
        let info = ActivityAuthorizationInfo()
        add(g, "Atividades ao vivo", info.areActivitiesEnabled ? "ligadas" : "desligadas",
            info.areActivitiesEnabled ? .ok : .falha, chave: "ilha_ativas", dado: info.areActivitiesEnabled)
        if !ilhaResposta.isEmpty {
            add(g, "Teste da ilha", ilhaResposta, ilhaResposta.hasPrefix("apareceu") ? .ok : .falha, chave: "ilha_teste")
        }
    }

    func ligarIlha() async {
        guard atividade == nil else { return }
        let agora = Date()
        let estado = IlhaTesteAtributos.ContentState(inicio: agora, fim: agora.addingTimeInterval(120))
        do {
            atividade = try Activity.request(attributes: IlhaTesteAtributos(titulo: "Teste do Painel"),
                                             content: .init(state: estado, staleDate: estado.fim), pushType: nil)
            ilhaLigada = true
            ilhaResposta = ""
        } catch {
            ilhaResposta = "não ligou: \(String(describing: error).prefix(120))"
            await gerar()
        }
    }

    func responderIlha(_ resposta: String) async {
        await atividade?.end(nil, dismissalPolicy: .immediate)
        atividade = nil
        ilhaLigada = false
        ilhaResposta = resposta
        await gerar()
    }

    // MARK: Permissões

    private func nome(_ s: AVAuthorizationStatus) -> String {
        switch s {
        case .authorized: return "liberado"
        case .denied: return "negado"
        case .restricted: return "restrito"
        case .notDetermined: return "ainda não pediu"
        @unknown default: return "?"
        }
    }

    private func permissoes() async {
        let g = "Permissões"
        let mic = nome(AVCaptureDevice.authorizationStatus(for: .audio))
        let cam = nome(AVCaptureDevice.authorizationStatus(for: .video))
        add(g, "Microfone", mic, mic == "negado" ? .atencao : .info, chave: "perm_mic")
        add(g, "Câmera", cam, cam == "negado" ? .atencao : .info, chave: "perm_camera")
        add(g, "Fotos", "\(PHPhotoLibrary.authorizationStatus(for: .readWrite).rawValue)", chave: "perm_fotos")
        add(g, "Localização", "\(CLLocationManager().authorizationStatus.rawValue)", chave: "perm_local")
        let aviso = await UNUserNotificationCenter.current().notificationSettings()
        add(g, "Notificações", "\(aviso.authorizationStatus.rawValue)", chave: "perm_aviso")
    }

    // MARK: Rede

    private func tipoDaRede() async -> String {
        await withCheckedContinuation { fim in
            let monitor = NWPathMonitor()
            monitor.pathUpdateHandler = { caminho in
                monitor.pathUpdateHandler = nil
                monitor.cancel()
                let tipo = caminho.usesInterfaceType(.wifi) ? "wi-fi"
                    : caminho.usesInterfaceType(.cellular) ? "dados móveis"
                    : caminho.status == .satisfied ? "outra" : "sem rede"
                fim.resume(returning: tipo)
            }
            monitor.start(queue: .global())
        }
    }

    private func tipoDoEndereco(_ url: URL) -> String {
        let h = url.host ?? ""
        let lugar = h.hasSuffix(".ts.net") || h.hasPrefix("100.") ? "tailscale"
            : h.hasPrefix("192.168.") || h.hasPrefix("10.") || h.hasSuffix(".local") ? "rede local" : "internet"
        return "\(url.scheme ?? "?") · \(lugar)"
    }

    private func rede() async {
        let g = "Painel"
        add(g, "Rede do iPhone", await tipoDaRede(), chave: "rede")
        guard let base = URL(string: Ajustes.url), base.scheme != nil else {
            add(g, "Conexão", "sem endereço", .falha, chave: "painel_status", dado: "sem_endereco")
            return
        }
        add(g, "Tipo de endereço", tipoDoEndereco(base), chave: "tipo_conexao")
        var pedido = URLRequest(url: base.appendingPathComponent("api/widget"))
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 10
        let ini = Date()
        do {
            let (corpo, resposta) = try await URLSession.shared.data(for: pedido)
            let ms = Int(Date().timeIntervalSince(ini) * 1000)
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            let bom = status == 200
            add(g, "Resposta do painel", "HTTP \(status) em \(ms) ms", bom ? .ok : .falha, chave: "painel_status", dado: status)
            dados["painel_ms"] = ms
            let json = (try? JSONSerialization.jsonObject(with: corpo)) as? [String: Any]
            add(g, "Dados do widget", json?["estado"] as? String ?? "não li", bom && json != nil ? .ok : .falha,
                chave: "painel_estado", dado: json?["estado"] as? String ?? "ilegivel")
        } catch {
            let e = error as NSError
            add(g, "Conexão", "falhou (\(e.domain) \(e.code))", .falha, chave: "painel_erro", dado: "\(e.domain) \(e.code)")
        }
    }

    // MARK: Página (WebView)

    private func paginaWeb() async {
        let g = "Página do painel"
        guard let web = PainelWeb.atual else {
            add(g, "WebView", "não abriu", .atencao, chave: "web_ok", dado: false)
            return
        }
        let js = """
        (function(){var n=navigator,c=document.createElement('canvas');return JSON.stringify({
        carregou:!!document.querySelector('#tab-hoje'),
        microfone:!!(n.mediaDevices&&n.mediaDevices.getUserMedia),
        webgl2:!!c.getContext('webgl2'),
        notificacao:'Notification' in window,
        push:'PushManager' in window,
        service_worker:'serviceWorker' in n,
        sw_ativo:!!(n.serviceWorker&&n.serviceWorker.controller),
        largura:innerWidth,altura:innerHeight})})()
        """
        let bruto: String? = await withCheckedContinuation { fim in
            web.evaluateJavaScript(js) { valor, _ in fim.resume(returning: valor as? String) }
        }
        guard let bruto, let d = (try? JSONSerialization.jsonObject(with: Data(bruto.utf8))) as? [String: Any] else {
            add(g, "WebView", "não respondeu", .falha, chave: "web_ok", dado: false)
            return
        }
        add(g, "Painel carregado", d["carregou"] as? Bool == true ? "sim" : "não (login?)",
            d["carregou"] as? Bool == true ? .ok : .atencao, chave: "web_ok", dado: d["carregou"] as? Bool ?? false)
        let itens: [(String, String, String)] = [
            ("Microfone na página", "microfone", "web_microfone"), ("3D do treino (WebGL2)", "webgl2", "web_webgl2"),
            ("Aviso do navegador", "notificacao", "web_notificacao"), ("Push do navegador", "push", "web_push"),
            ("Service Worker", "service_worker", "web_sw"), ("Service Worker ativo", "sw_ativo", "web_sw_ativo"),
        ]
        for (titulo, chave, destino) in itens {
            let sim = d[chave] as? Bool == true
            add(g, titulo, sim ? "sim" : "não", sim ? .ok : .info, chave: destino, dado: sim)
        }
        add(g, "Tamanho", "\(d["largura"] ?? "?") × \(d["altura"] ?? "?")", chave: "web_tamanho")
    }

    // MARK: Envio

    func enviar() async {
        guard let base = URL(string: Ajustes.url), base.scheme != nil, !Ajustes.token.isEmpty else {
            envio = "Não mandei: falta endereço ou token. Usa o Copiar."
            return
        }
        envio = "Mandando…"
        var pedido = URLRequest(url: base.appendingPathComponent("api/widget/relatorio"))
        pedido.httpMethod = "POST"
        pedido.setValue("application/json", forHTTPHeaderField: "Content-Type")
        pedido.setValue("Bearer \(Ajustes.token)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 10
        do {
            pedido.httpBody = try JSONSerialization.data(withJSONObject: ["dados": dados])
            let (_, resposta) = try await URLSession.shared.data(for: pedido)
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            envio = status == 200 ? "Mandado pro painel. Já consigo ler." : "Painel recusou (HTTP \(status)). Usa o Copiar."
        } catch {
            envio = "Não chegou no painel. Usa o Copiar."
        }
    }
}

struct TelaRelatorio: View {
    @StateObject private var r = Relatorio()
    @State private var copiado = false

    var body: some View {
        List {
            Section {
                Button {
                    Task { await r.gerar() }
                } label: {
                    HStack {
                        Label(r.linhas.isEmpty ? "Gerar relatório" : "Gerar de novo", systemImage: "waveform.path.ecg")
                        Spacer()
                        if r.rodando { ProgressView() }
                    }
                }
                .disabled(r.rodando)
            } footer: {
                Text(r.envio.isEmpty ? "Só olha, não muda nada. Não leva teu endereço nem o token." : r.envio)
            }

            Section {
                if r.ilhaLigada {
                    Text("Ligou. Vai pra tela inicial e olha a ilha, depois bloqueia o iPhone e olha a tela de bloqueio. Dentro do app ela não aparece. Volta aqui e responde:")
                        .font(.footnote)
                    Button("Apareceu nos dois") { Task { await r.responderIlha("apareceu na ilha e no bloqueio") } }
                    Button("Apareceu só na ilha") { Task { await r.responderIlha("apareceu só na ilha") } }
                    Button("Apareceu só no bloqueio") { Task { await r.responderIlha("apareceu só no bloqueio") } }
                    Button("Não apareceu", role: .destructive) { Task { await r.responderIlha("não apareceu") } }
                } else {
                    Button {
                        Task { await r.ligarIlha() }
                    } label: {
                        Label("Testar a Dynamic Island", systemImage: "capsule.fill")
                    }
                }
            } header: {
                Text("Teste de verdade")
            } footer: {
                Text(r.ilhaResposta.isEmpty ? "Liga uma contagem de 2 minutos." : "Última resposta: \(r.ilhaResposta)")
            }

            ForEach(r.grupos, id: \.self) { grupo in
                Section(grupo) {
                    ForEach(r.linhas.filter { $0.grupo == grupo }) { linha in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Image(systemName: linha.estado.icone).foregroundColor(linha.estado.cor).font(.footnote)
                            Text(linha.titulo).font(.subheadline)
                            Spacer(minLength: 12)
                            Text(linha.valor).font(.subheadline).foregroundColor(.secondary)
                                .multilineTextAlignment(.trailing).textSelection(.enabled)
                        }
                    }
                }
            }

            if !r.linhas.isEmpty {
                Section {
                    Button {
                        UIPasteboard.general.string = r.texto
                        copiado = true
                    } label: {
                        Label(copiado ? "Copiado" : "Copiar tudo", systemImage: copiado ? "checkmark" : "doc.on.doc")
                    }
                } footer: {
                    Text("Se o painel estiver desligado, copia e cola no chat comigo.")
                }
            }
        }
        .navigationTitle("Relatório")
        .navigationBarTitleDisplayMode(.inline)
    }
}
