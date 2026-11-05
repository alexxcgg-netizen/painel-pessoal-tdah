//
//  Config.swift
//  PainelWidget (WidgetKit extension)
//
//  Onde o widget acha o endereço e o token do painel (2026-11-05, leva dos widgets nativos):
//  - endereço: o cofre (UserDefaults) e, sem nada lá, o arquivo `Painel-endereco.txt` que
//    `scripts/ipa_com_endereco.py` grava dentro da extensão no .ipa local (nunca no GitHub);
//  - token: o cofre. A assinatura grátis do Sideloadly corta o App Group, então o widget não enxerga o
//    token que o app guardou: ele chega pelo pareamento por código (PainelDados.swift / rotas/widget_ios.py)
//    e fica guardado aqui. Com App Group de verdade, o cofre é o mesmo do app e o token já vem pronto.
//
//  Nunca logar nem mostrar o token. Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import Foundation

enum PainelConfig {

    /// Igual ao App Group do project.yml e a `Ajustes.appGroupID` (PainelApp.swift).
    static let appGroupID = "group.com.alexxcgg.painel"

    private enum Chave {
        static let urlBase = "painel_widget_url_base"
        static let token = "painel_widget_token"
        /// Último payload bom (o widget mostra ele quando a rede falha, e reaproveita por 90 s).
        static let ultimoPayload = "painel_widget_ultimo_payload"
        static let ultimoPayloadEm = "painel_widget_ultimo_payload_em"
        /// Sinal de vida do widget, lido pela tela "Gerar relatório" do app (Relatorio.swift).
        static let diagEm = "painel_widget_diag_em"
        static let diagResultado = "painel_widget_diag_resultado"
        /// Pareamento em andamento: id do widget (UUID) e o código de 4 números que ele está mostrando.
        static let parId = "painel_widget_par_id"
        static let parCodigo = "painel_widget_par_codigo"
    }

    /// Com o App Group provisionado é o cofre dividido com o app; sem ele, um cofre só do widget.
    static var defaults: UserDefaults { UserDefaults(suiteName: appGroupID) ?? .standard }

    /// URL base do painel, sem barra no final.
    static var urlBase: String? {
        if let s = defaults.string(forKey: Chave.urlBase)?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
            return s
        }
        return enderecoDeFabrica
    }

    /// O endereço que `scripts/ipa_com_endereco.py` grava dentro da extensão (Bundle.main aqui é o .appex).
    static var enderecoDeFabrica: String? {
        guard let arquivo = Bundle.main.url(forResource: "Painel-endereco", withExtension: "txt"),
              let texto = try? String(contentsOf: arquivo, encoding: .utf8) else { return nil }
        let limpo = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        return URL(string: limpo)?.scheme?.hasPrefix("http") == true ? limpo : nil
    }

    static var token: String? {
        guard let t = defaults.string(forKey: Chave.token), !t.isEmpty else { return nil }
        return t
    }

    static func guardarToken(_ token: String?) {
        if let token, !token.isEmpty {
            defaults.set(token, forKey: Chave.token)
        } else {
            defaults.removeObject(forKey: Chave.token)
        }
    }

    // MARK: - Pareamento

    static var parId: String? {
        get { defaults.string(forKey: Chave.parId) }
        set { defaults.set(newValue, forKey: Chave.parId) }
    }

    static var parCodigo: String? {
        get { defaults.string(forKey: Chave.parCodigo) }
        set { defaults.set(newValue, forKey: Chave.parCodigo) }
    }

    static func limparPar() {
        defaults.removeObject(forKey: Chave.parId)
        defaults.removeObject(forKey: Chave.parCodigo)
    }

    // MARK: - Pedidos

    static func url(_ caminho: String) -> URL? {
        guard var base = urlBase else { return nil }
        while base.hasSuffix("/") { base.removeLast() }
        guard let url = URL(string: base + caminho), url.scheme?.hasPrefix("http") == true else { return nil }
        return url
    }

    static var widgetURL: URL? { url("/api/widget") }

    /// nil sem endereço (ou sem token, quando `comToken`): nada vai pra rede.
    static func pedido(_ caminho: String, metodo: String = "GET", corpo: [String: Any]? = nil,
                       comToken: Bool = true) -> URLRequest? {
        guard let url = url(caminho) else { return nil }
        var pedido = URLRequest(url: url)
        pedido.httpMethod = metodo
        pedido.timeoutInterval = 10
        if comToken {
            guard let token else { return nil }
            pedido.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let corpo, let dados = try? JSONSerialization.data(withJSONObject: corpo) {
            pedido.httpBody = dados
            pedido.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return pedido
    }

    // MARK: - Sinal de vida (lido pelo relatório do app)

    /// `resultado` é só um código curto ("ok", "sem_url", "pareando", "http_401", "rede_-1022"): nada de URL nem token.
    static func registrarBusca(_ resultado: String) {
        defaults.set(Date(), forKey: Chave.diagEm)
        defaults.set(resultado, forKey: Chave.diagResultado)
    }

    // MARK: - Último payload bom

    static func salvarUltimoPayload(_ dados: Data) {
        defaults.set(dados, forKey: Chave.ultimoPayload)
        defaults.set(Date(), forKey: Chave.ultimoPayloadEm)
    }

    static func ultimoPayload() -> (dados: Data, em: Date)? {
        guard let dados = defaults.data(forKey: Chave.ultimoPayload),
              let em = defaults.object(forKey: Chave.ultimoPayloadEm) as? Date else {
            return nil
        }
        return (dados, em)
    }
}
