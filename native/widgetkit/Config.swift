//
//  Config.swift
//  PainelWidget (WidgetKit extension) — Fase 7 / faixa n3e-widgetkit
//
//  Config lida do App Group compartilhado com o app principal (o projeto
//  Xcode gerado pelo PWABuilder, ou o app "contêiner" que abriga esta
//  extensão). Nada aqui é hardcoded: o app precisa gravar a URL e o token
//  no App Group ANTES do widget conseguir mostrar dado real; sem isso o
//  widget cai no estado "erro" (ver PainelWidget.swift).
//
//  IMPORTANTE (ver README.md): este arquivo não foi compilado nem testado
//  neste ambiente — não há Mac/Xcode aqui. Escrito e revisado por leitura,
//  seguindo a API pública do WidgetKit/Foundation tal como documentada pela
//  Apple; confira a assinatura de `UserDefaults(suiteName:)` e afins no
//  Xcode antes de assumir que compila sem ajuste.
//

import Foundation

enum PainelConfig {

    /// Precisa bater com o App Group configurado nas Capabilities do app
    /// container E da extensão do widget (Xcode -> target -> Signing &
    /// Capabilities -> App Groups). Sugestão: "group.<seu-bundle-id>.painel"
    /// — troque pelo identifier real escolhido no passo 4 do README.
    static let appGroupID = "group.com.alexxcgg.painel"

    /// Chaves usadas no `UserDefaults` do App Group. O app principal (a
    /// tela de configurações do container gerado pelo PWABuilder, ou uma
    /// tela nova feita à mão) é quem grava essas duas chaves; o widget só
    /// lê. Nunca hardcode URL/token direto no widget — o Alex pode trocar
    /// de rede (casa/trabalho/VPN) ou girar o token sem precisar recompilar.
    private enum Chave {
        static let urlBase = "painel_widget_url_base"
        static let token = "painel_widget_token"
        /// Cache do último payload bom, gravado pelo próprio widget a cada
        /// atualização com sucesso — ver `PainelWidget.swift`. Serve pra
        /// widget não cair pra "vazio"/"erro" só porque a rede falhou uma
        /// vez; mostra o último dado válido (mais antigo) em vez de nada.
        static let ultimoPayload = "painel_widget_ultimo_payload"
        static let ultimoPayloadEm = "painel_widget_ultimo_payload_em"
        /// Sinal de vida do widget, lido pela tela "Gerar relatório" do app (Relatorio.swift).
        static let diagEm = "painel_widget_diag_em"
        static let diagResultado = "painel_widget_diag_resultado"
    }

    private static var defaults: UserDefaults? {
        UserDefaults(suiteName: appGroupID)
    }

    /// URL base do painel, ex: "https://painel.example.com" ou
    /// "http://192.168.1.10:5001" numa rede local. Sem barra no final —
    /// `widgetURL` completa com "/api/widget".
    static var urlBase: String? {
        defaults?.string(forKey: Chave.urlBase)
    }

    /// Token do `Authorization: Bearer <token>` (ver AGENTS.md do painel —
    /// mesma família de token dos outros endpoints `/api/atalho/*`, mas
    /// este novo endpoint usa Bearer em vez de X-Webhook-Token). Nunca
    /// logar nem expor este valor em texto (nem em prints de debug).
    static var token: String? {
        defaults?.string(forKey: Chave.token)
    }

    /// Monta a URL completa do endpoint, ou nil se ainda não configurado
    /// (widget mostra estado "erro" com texto "Configure o painel no app").
    static var widgetURL: URL? {
        guard let base = urlBase, !base.isEmpty else { return nil }
        let semBarraFinal = base.hasSuffix("/") ? String(base.dropLast()) : base
        return URL(string: semBarraFinal + "/api/widget")
    }

    // MARK: - Sinal de vida (lido pelo relatório do app)

    /// `resultado` é só um código curto ("ok", "sem_url", "http_401", "rede_-1022"): nada de URL nem token.
    static func registrarBusca(_ resultado: String) {
        defaults?.set(Date(), forKey: Chave.diagEm)
        defaults?.set(resultado, forKey: Chave.diagResultado)
    }

    // MARK: - Cache do último payload bom (App Group)

    static func salvarUltimoPayload(_ dados: Data) {
        defaults?.set(dados, forKey: Chave.ultimoPayload)
        defaults?.set(Date(), forKey: Chave.ultimoPayloadEm)
    }

    static func ultimoPayload() -> (dados: Data, em: Date)? {
        guard let dados = defaults?.data(forKey: Chave.ultimoPayload),
              let em = defaults?.object(forKey: Chave.ultimoPayloadEm) as? Date else {
            return nil
        }
        return (dados, em)
    }
}
