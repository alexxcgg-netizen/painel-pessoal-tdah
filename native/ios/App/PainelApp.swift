//
//  PainelApp.swift
//  App contêiner do Painel Pessoal (2026-10-22)
//
//  Abre o painel numa WKWebView (a mesma tela do PWA, login pelo PIN de sempre) e guarda, no
//  App Group, a URL e o token que o widget (native/widgetkit/Config.swift) lê. Nada de endereço
//  nem token fica no código: os dois são digitados na tela "Configurar".
//
//  Configurar: abre sozinha na primeira vez; depois, segura o ícone do app → "Configurar"
//  (atalho do ícone - nenhum botão por cima do painel).
//

import SwiftUI
import UIKit
import WebKit
import WidgetKit

enum Ajustes {
    static let appGroupID = "group.com.alexxcgg.painel"  // igual a PainelConfig.appGroupID
    static let chaveURL = "painel_widget_url_base"
    static let chaveToken = "painel_widget_token"
    static let atalhoConfigurar = "configurar"

    static var defaults: UserDefaults { UserDefaults(suiteName: appGroupID) ?? .standard }

    /// `scripts/ipa_com_endereco.py` grava o endereço só na cópia local do .ipa (nunca no GitHub):
    /// com ele o app já abre no painel, sem a tela Configurar. Só preenche se ainda estiver vazio.
    static func aplicarEnderecoDeFabrica() {
        guard url.isEmpty, let arquivo = Bundle.main.url(forResource: "Painel-endereco", withExtension: "txt"),
              let texto = try? String(contentsOf: arquivo, encoding: .utf8) else { return }
        let limpo = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        if URL(string: limpo)?.scheme?.hasPrefix("http") == true { url = limpo }
    }

    static var url: String {
        get { defaults.string(forKey: chaveURL) ?? "" }
        set { defaults.set(newValue, forKey: chaveURL) }
    }

    static var token: String {
        get { defaults.string(forKey: chaveToken) ?? "" }
        set { defaults.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines), forKey: chaveToken) }
    }
}

/// Avisa a tela que o atalho "Configurar" do ícone foi tocado (app aberto ou frio).
final class Abertura: ObservableObject {
    static let shared = Abertura()
    @Published var configurar = false
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions
                     launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        application.shortcutItems = [
            UIApplicationShortcutItem(type: Ajustes.atalhoConfigurar, localizedTitle: "Configurar",
                                      localizedSubtitle: "Endereço e token do widget",
                                      icon: UIApplicationShortcutIcon(systemImageName: "gearshape"))
        ]
        // onde eu estou (04/11): o gerente de localizacao nasce ja no launch, pra visita que acordou
        // o app em segundo plano chegar no delegate
        Localizacao.shared.iniciar()
        return true
    }

    func application(_ application: UIApplication, configurationForConnecting sessao: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        if options.shortcutItem?.type == Ajustes.atalhoConfigurar { Abertura.shared.configurar = true }
        let config = UISceneConfiguration(name: nil, sessionRole: sessao.role)
        config.delegateClass = CenaDelegate.self
        return config
    }
}

final class CenaDelegate: NSObject, UIWindowSceneDelegate {
    func windowScene(_ cena: UIWindowScene, performActionFor atalho: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        let meu = atalho.type == Ajustes.atalhoConfigurar
        if meu { Abertura.shared.configurar = true }
        completionHandler(meu)
    }
}

@main
struct PainelApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    init() { Ajustes.aplicarEnderecoDeFabrica() }

    var body: some Scene {
        WindowGroup {
            Raiz()
        }
    }
}

struct Raiz: View {
    @ObservedObject private var abertura = Abertura.shared
    @ObservedObject private var parear = ParearWidget.shared  // "Liberar este widget?" (ParearWidget.swift)
    @State private var url = Ajustes.url
    @State private var recarregar = 0
    @State private var capturar = false

    /// Botão "Anotar no painel" da Central de Controle (PainelControleIntent.swift) deixa um carimbo no App Group;
    /// vale por 60 s e é consumido uma vez. Lab v4 / ideia "central".
    private func conferirPedidoDeCaptura() {
        let d = Ajustes.defaults
        let t = d.double(forKey: "painel_capturar_pedido")
        guard t > 0 else { return }
        d.removeObject(forKey: "painel_capturar_pedido")
        if Date().timeIntervalSince1970 - t < 60 {
            capturar = true
            recarregar += 1
        }
    }

    var body: some View {
        ZStack {
            Color(red: 0.07, green: 0.07, blue: 0.07).ignoresSafeArea()
            if let endereco = URL(string: url), endereco.scheme != nil {
                PainelWeb(url: capturar ? (URL(string: url + (url.hasSuffix("/") ? "" : "/") + "?capturar=1") ?? endereco) : endereco)
                    .id(recarregar).ignoresSafeArea(edges: .bottom)
            }
        }
        .onAppear {
            if url.isEmpty { abertura.configurar = true }
            conferirPedidoDeCaptura()
            parear.conferir()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
            conferirPedidoDeCaptura()
            Localizacao.shared.enviarFila()
            AoVivo.shared.sincronizar()  // atividade ao vivo do próximo compromisso (AoVivo.swift)
            parear.conferir()  // widget pedindo pra ser liberado? (e acorda os widgets)
        }
        .alert("Liberar este widget?", isPresented: $parear.mostrar) {
            Button("Liberar") { parear.liberar() }
            Button("Agora não", role: .cancel) { parear.agoraNao() }
        } message: {
            Text("O widget está mostrando \(parear.codigoEspacado). Se for o mesmo, libera e ele já começa a mostrar o painel.")
        }
        .sheet(isPresented: $abertura.configurar) {
            Configurar { novaURL in
                url = novaURL
                capturar = false
                recarregar += 1
                WidgetCenter.shared.reloadAllTimelines()
            }
            .interactiveDismissDisabled(url.isEmpty)
        }
    }
}

struct Configurar: View {
    var salvo: (String) -> Void
    @Environment(\.dismiss) private var fechar
    @State private var url = Ajustes.url
    @State private var token = Ajustes.token

    private var urlLimpa: String {
        var limpo = url.trimmingCharacters(in: .whitespacesAndNewlines)
        while limpo.hasSuffix("/") { limpo.removeLast() }
        return limpo
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("https://…", text: $url)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("Endereço do painel")
                } footer: {
                    Text("O mesmo que tu abre no Safari.")
                }
                Section {
                    SecureField("Token do widget", text: $token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("Widget")
                } footer: {
                    Text("Vem sozinho depois que tu entra com o PIN. Fica só neste iPhone.")
                }
                SecaoOndeEstou()
                Section {
                    NavigationLink {
                        TelaRelatorio()
                    } label: {
                        Label("Gerar relatório", systemImage: "waveform.path.ecg")
                    }
                } footer: {
                    // 2026-11-06: qual .ipa está instalado (data do build + commit), pra nunca mais ficar na dúvida
                    Text("Salva antes, se mudou o endereço ou o token.\n\nVersão: \(Bundle.main.object(forInfoDictionaryKey: "PainelBuild") as? String ?? "?")")
                }
            }
            .navigationTitle("Configurar")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Salvar") {
                        Ajustes.url = urlLimpa
                        Ajustes.token = token
                        salvo(urlLimpa)
                        fechar()
                    }
                    .disabled(URL(string: urlLimpa)?.scheme?.hasPrefix("http") != true)
                }
            }
        }
    }
}

struct PainelWeb: UIViewRepresentable {
    let url: URL
    /// A WebView aberta agora, pro relatório perguntar o que a página consegue fazer.
    static weak var atual: WKWebView?

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()  // cookie do login (PIN) fica entre aberturas
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let web = WKWebView(frame: .zero, configuration: config)
        web.isOpaque = false
        web.backgroundColor = .clear
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.allowsBackForwardNavigationGestures = true
        web.uiDelegate = context.coordinator
        web.navigationDelegate = context.coordinator
        web.load(URLRequest(url: url))
        PainelWeb.atual = web
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {}

    func makeCoordinator() -> Coordenador { Coordenador() }

    final class Coordenador: NSObject, WKUIDelegate, WKNavigationDelegate {
        private var buscando = false

        /// Com o PIN digitado, a sessão da página já pode pedir o token do widget ao painel
        /// (/api/widget/instalacao, a mesma rota de Configurações → Widget do iPhone).
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            buscarToken(webView, tentativas: 60)
        }

        private func buscarToken(_ web: WKWebView, tentativas: Int) {
            guard Ajustes.token.isEmpty, !buscando, tentativas > 0,
                  let painel = URL(string: Ajustes.url)?.host, web.url?.host == painel else { return }
            buscando = true
            let js = """
            const r = await fetch('/api/widget/instalacao', {credentials: 'same-origin', redirect: 'error'});
            if (!r.ok) return '';
            const j = await r.json();
            return j.token || '';
            """
            web.callAsyncJavaScript(js, arguments: [:], in: nil, in: .page) { [weak self, weak web] resultado in
                guard let self else { return }
                self.buscando = false
                if case .success(let valor) = resultado, let token = valor as? String, token.count >= 8 {
                    Ajustes.token = token
                    WidgetCenter.shared.reloadAllTimelines()
                    AoVivo.shared.sincronizar()  // primeira vez com token: já liga a atividade se tiver compromisso
                    Task { @MainActor in ParearWidget.shared.conferir() }  // widget esperando o "Liberar"
                } else if let web {
                    // ainda na tela do PIN: tenta de novo daqui a pouco (login nem sempre recarrega a página)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                        self.buscarToken(web, tentativas: tentativas - 1)
                    }
                }
            }
        }

        // microfone/câmera do chat: o iOS ja perguntou ao app (Info.plist); so o host do painel
        // herda sem perguntar de novo - qualquer outro site que abrir aqui volta a perguntar
        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                     initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                     decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            let painel = URL(string: Ajustes.url)?.host
            decisionHandler(painel != nil && origin.host == painel ? .grant : .prompt)
        }
    }
}
