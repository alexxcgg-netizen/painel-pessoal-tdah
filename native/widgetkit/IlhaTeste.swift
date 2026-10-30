//
//  IlhaTeste.swift
//  Desenho da atividade de teste (Dynamic Island e tela de bloqueio) - 2026-10-30
//
//  Só o teste do relatório. As ilhas de verdade (voo, hora de sair, foco, treino) entram na Fase 2,
//  seguindo o protótipo aprovado.
//

import ActivityKit
import SwiftUI
import WidgetKit

struct IlhaTeste: Widget {
    private let cor = Color(red: 0.56, green: 0.82, blue: 1.0)  // #8fd0ff, a cor do voo nos cards

    private func tempo(_ estado: IlhaTesteAtributos.ContentState) -> Text {
        Text(timerInterval: estado.inicio...estado.fim, countsDown: true)
    }

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: IlhaTesteAtributos.self) { contexto in
            HStack {
                Image(systemName: "checkmark.seal.fill").foregroundColor(cor)
                VStack(alignment: .leading) {
                    Text(contexto.attributes.titulo).font(.headline)
                    Text("A tela de bloqueio funciona.").font(.caption).foregroundColor(.secondary)
                }
                Spacer()
                tempo(contexto.state).font(.title2.monospacedDigit()).foregroundColor(cor)
                    .multilineTextAlignment(.trailing).frame(width: 80)
            }
            .padding()
            .activityBackgroundTint(Color.black.opacity(0.7))
            .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { contexto in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: "checkmark.seal.fill").foregroundColor(cor)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    tempo(contexto.state).font(.title3.monospacedDigit()).foregroundColor(cor)
                        .multilineTextAlignment(.trailing).frame(width: 70)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("\(contexto.attributes.titulo): a ilha aberta funciona.").font(.caption)
                }
            } compactLeading: {
                Image(systemName: "checkmark.seal.fill").foregroundColor(cor)
            } compactTrailing: {
                tempo(contexto.state).font(.caption.monospacedDigit()).foregroundColor(cor)
                    .multilineTextAlignment(.trailing).frame(width: 40)
            } minimal: {
                Image(systemName: "checkmark.seal.fill").foregroundColor(cor)
            }
        }
    }
}
