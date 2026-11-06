//
//  AtividadeTarefa.swift
//  Desenho da atividade ao vivo de TAREFA com hora (sem saída) - 2026-11-06
//  docs/briefings/2026-11-06-ao-vivo-tarefa.md
//
//  Mesma família da barra de compromisso (AtividadeCompromisso.swift): pílula escura, ícone no círculo na cor,
//  título, contagem na cor à direita. No lugar da fileira de passos: a barra que enche até a hora e o botão
//  Feito (iOS 17, FeitoAoVivoIntent.swift).
//
//  Animação: só o que o iOS deixa numa atividade ao vivo - a contagem e a barra andam sozinhas
//  (Text/ProgressView(timerInterval:)), e a troca pro "feito" entra com transição (check que cresce e assenta,
//  título riscado). Nada em loop (o iOS não roda animação contínua aqui).
//  Passou da hora sem Feito: tudo que é da cor do assunto vira vermelho (a cor chega pronta de
//  AtividadeCompromisso.swift, `corAgora`); o iOS troca com o esmaecer padrão dele quando redesenha na hora.
//

import ActivityKit
import AppIntents
import SwiftUI
import WidgetKit

typealias EstadoAoVivo = CompromissoAtributos.ContentState

/// "falta 1:12:04" até a hora; depois "agora" e o relógio desde a hora; feito: "feito".
struct ContagemTarefa: View {
    let estado: EstadoAoVivo
    let agora: Date
    let cor: Color
    var tamanho: CGFloat = 15
    var comRotulo = true

    var body: some View {
        if estado.estaFeito {
            Text("feito")
                .font(.system(size: tamanho, weight: .semibold))
                .foregroundColor(cor)
                .transition(.opacity)
        } else if let hora = estado.horaTarefa {
            VStack(alignment: .trailing, spacing: 1) {
                if comRotulo {
                    Text(hora > agora ? "falta" : "agora")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.white.opacity(0.55))
                }
                Group {
                    if hora > agora {
                        Text(timerInterval: EstadoAoVivo.intervalo(de: agora, ate: hora), countsDown: true)
                    } else {
                        Text(timerInterval: EstadoAoVivo.intervalo(de: hora, ate: estado.fim), countsDown: false)
                    }
                }
                .font(.system(size: tamanho, weight: .semibold).monospacedDigit())
                .foregroundColor(cor)
                .multilineTextAlignment(.trailing)
            }
        }
    }
}

/// A barra que enche nas 2 h 30 até a hora (anda sozinha). Cheia depois da hora.
struct BarraTarefa: View {
    let estado: EstadoAoVivo
    let cor: Color

    var body: some View {
        if let hora = estado.horaTarefa {
            ProgressView(timerInterval: EstadoAoVivo.intervalo(de: hora.addingTimeInterval(-EstadoAoVivo.janelaTarefa), ate: hora),
                         countsDown: false) {
                EmptyView()
            } currentValueLabel: {
                EmptyView()
            }
            .progressViewStyle(.linear)
            .tint(cor)
            .labelsHidden()
        }
    }
}

/// Botão Feito (iOS 17+). Antes disso, nada: ele marca pelo app ou pelo aviso.
struct BotaoFeitoAoVivo: View {
    let estado: EstadoAoVivo
    let atividadeID: String
    let cor: Color
    var compacto = false

    var body: some View {
        if #available(iOSApplicationExtension 17.0, *) {
            if let tag = estado.tag, !estado.estaFeito {
                Button(intent: FeitoAoVivoIntent(atividadeID: atividadeID, tag: tag)) {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark")
                            .font(.system(size: compacto ? 12 : 13, weight: .bold))
                        Text("Feito")
                            .font(.system(size: compacto ? 13 : 14, weight: .semibold))
                    }
                    .foregroundColor(.black.opacity(0.85))
                    .frame(maxWidth: .infinity, minHeight: compacto ? 32 : 36)
                    .background(Capsule().fill(cor))
                }
                .buttonStyle(.plain)
                .transition(.opacity)
            }
        }
    }
}

/// Check grande que aparece no Feito (cresce e assenta).
struct CheckFeito: View {
    let cor: Color
    var tamanho: CGFloat = 30

    var body: some View {
        ZStack {
            Circle().fill(cor)
            Image(systemName: "checkmark")
                .font(.system(size: tamanho * 0.5, weight: .bold))
                .foregroundColor(.black.opacity(0.85))
        }
        .frame(width: tamanho, height: tamanho)
        .transition(.scale(scale: 0.4).combined(with: .opacity))
    }
}

/// Tela bloqueada (e banner nos iPhones sem ilha).
struct TelaTarefa: View {
    let estado: EstadoAoVivo
    let atividadeID: String
    let agora: Date
    let cor: Color

    private var linha: String {
        if estado.estaFeito { return "Feito. Boa." }
        guard let hora = estado.horaTarefa else { return "" }
        return hora > agora ? "às \(EstadoAoVivo.hora(hora))" : "era às \(EstadoAoVivo.hora(hora))"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(spacing: 10) {
                Group {
                    if estado.estaFeito {
                        CheckFeito(cor: cor)
                    } else {
                        IconeAssunto(icone: estado.icone, cor: cor)
                            .transition(.opacity)
                    }
                }
                VStack(alignment: .leading, spacing: 1) {
                    Text(estado.titulo)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(.white.opacity(estado.estaFeito ? 0.6 : 1))
                        .strikethrough(estado.estaFeito, color: .white.opacity(0.6))
                        .lineLimit(1)
                    Text(linha)
                        .font(.system(size: 12))
                        .foregroundColor(.white.opacity(0.55))
                        .lineLimit(1)
                        .contentTransition(.opacity)
                }
                Spacer(minLength: 6)
                ContagemTarefa(estado: estado, agora: agora, cor: cor)
                    .frame(minWidth: 64, alignment: .trailing)
            }
            if !estado.estaFeito {
                BarraTarefa(estado: estado, cor: cor)
                BotaoFeitoAoVivo(estado: estado, atividadeID: atividadeID, cor: cor)
            }
        }
    }
}

/// Mínima da ilha (quando divide com outra atividade): anel que esvazia até a hora.
struct AnelTarefa: View {
    let estado: EstadoAoVivo
    let cor: Color

    var body: some View {
        if estado.estaFeito {
            Image(systemName: "checkmark").foregroundColor(cor)
        } else if let hora = estado.horaTarefa {
            ProgressView(timerInterval: EstadoAoVivo.intervalo(de: hora.addingTimeInterval(-EstadoAoVivo.janelaTarefa), ate: hora),
                         countsDown: true) {
                EmptyView()
            } currentValueLabel: {
                Image(systemName: estado.icone).font(.system(size: 9, weight: .semibold))
            }
            .progressViewStyle(.circular)
            .tint(cor)
            .foregroundColor(cor)
        }
    }
}
