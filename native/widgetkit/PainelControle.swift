//
//  PainelControle.swift
//  PainelWidget (WidgetKit extension) — Lab v4 / ideia "central" (30/10/2026)
//
//  Botão "Anotar no painel" pra Central de Controle (e tela de bloqueio) do iOS 18: um toque abre o painel
//  já no chat, com o microfone pronto. É um ControlWidget (iOS 18+), então só compila com Xcode 16 / SDK
//  do iOS 18; o `#if compiler(>=6.0)` faz o build antigo simplesmente ignorar este arquivo em vez de quebrar.
//
//  Como colocar o botão (Alex): reconstrói o app (.ipa) → na Central de Controle, "+" no canto → "Adicionar
//  controle" → Painel → "Anotar no painel". O passo a passo completo está em
//  docs/briefings/2026-10-30-lab-v4-avisos.md.
//
//  Não compilado aqui — não há Mac com Xcode neste ambiente. Escrito pela API pública documentada
//  (ControlWidget / ControlWidgetButton / StaticControlConfiguration).
//

#if compiler(>=6.0)
import AppIntents
import SwiftUI
import WidgetKit

@available(iOS 18.0, *)
struct PainelControle: ControlWidget {
    static let kind = "com.alexxcgg.painel.controle.anotar"

    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: Self.kind) {
            ControlWidgetButton(action: CapturarNoPainelIntent()) {
                Label("Anotar", systemImage: "mic.fill")
            }
        }
        .displayName("Anotar no painel")
        .description("Abre o painel pronto pra falar ou digitar uma anotação.")
    }
}
#endif
