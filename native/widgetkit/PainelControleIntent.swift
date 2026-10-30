//
//  PainelControleIntent.swift
//  Lab v4 / ideia "central" (30/10/2026)
//
//  O que acontece quando tu toca no botão "Anotar no painel" da Central de Controle (iOS 18): o app abre
//  (`openAppWhenRun`) e este intent deixa um recado no App Group ("capturar agora"). O app lê o recado ao
//  ficar ativo e abre o painel já no chat, com o microfone pronto (PainelApp.swift).
//
//  Este arquivo entra nos DOIS alvos (extensão do widget, que mostra o botão, e o app, onde o intent roda):
//  ver native/ios/project.yml. Não compilado aqui — não há Mac com Xcode neste ambiente.
//

import AppIntents
import Foundation

struct CapturarNoPainelIntent: AppIntent {
    static let title: LocalizedStringResource = "Anotar no painel"
    static let description = IntentDescription("Abre o painel pronto pra tu falar ou digitar uma anotação.")
    static let openAppWhenRun: Bool = true

    /// Igual a `Ajustes.appGroupID` (PainelApp.swift) e a `PainelConfig.appGroupID` (Config.swift).
    static let appGroupID = "group.com.alexxcgg.painel"
    static let chavePedido = "painel_capturar_pedido"

    func perform() async throws -> some IntentResult {
        UserDefaults(suiteName: Self.appGroupID)?.set(Date().timeIntervalSince1970, forKey: Self.chavePedido)
        return .result()
    }
}
