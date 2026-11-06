//
//  AtividadeViagem.swift
//  Desenho da atividade ao vivo da VIAGEM acompanhada (tela bloqueada + Dynamic Island) - 2026-11-06
//  docs/briefings/2026-11-06-painel-esperto.md, frente 3 (protótipo aprovado: cena "No carro")
//
//  Mesma família da barra de compromisso e da tarefa (AtividadeCompromisso.swift / AtividadeTarefa.swift):
//  pílula escura, ícone do carro no círculo na cor da viagem, destino e "faltam X km", "chega 19:50" na cor à
//  direita, a barra de progresso e dois quadrinhos embaixo: próximo posto ("em 278 km · 11:15") e chuva à frente
//  ("daqui 25 min" / "chovendo, mais 12 km"; some quando não tem).
//
//  Animação: só o que o iOS deixa numa atividade ao vivo - a barra anda sozinha até a chegada
//  (ProgressView(timerInterval:), começo calculado pelo painel pra bater com os km a cada posição nova) e os
//  números trocam com a transição numérica do sistema quando chega posição nova. Nada em loop.
//  Os dados: CompromissoAtributos.swift (ContentState.viagem). Quem liga/atualiza: native/ios/App/AoVivo.swift.
//

import ActivityKit
import SwiftUI
import WidgetKit

/// Azul da chuva no protótipo (--chuva).
private let corChuva = Color(red: 0x6f / 255, green: 0xb3 / 255, blue: 0xff / 255)

extension CompromissoAtributos.ContentState {
    /// "faltam 802 km" / "falta 1 km" / "chegando".
    var faltaTexto: String {
        guard let v = viagem else { return "" }
        if v.faltaKm < 1 { return "chegando" }
        return v.faltaKm == 1 ? "falta 1 km" : "faltam \(v.faltaKm) km"
    }

    /// "em 278 km · 11:15" (sem hora quando o painel não mandou).
    var postoTexto: String? {
        guard let v = viagem, let km = v.postoKm else { return nil }
        if let em = v.postoEm { return "em \(km) km · \(Self.hora(em))" }
        return "em \(km) km"
    }

    /// Intervalo da barra: do começo calculado pelo painel até a chegada refeita (nunca ao contrário).
    var intervaloViagem: ClosedRange<Date>? {
        guard let v = viagem, let chegada else { return nil }
        return Self.intervalo(de: v.barraDesde, ate: chegada)
    }
}

/// "chega" + hora da chegada na cor da viagem.
struct ChegadaViagem: View {
    let estado: EstadoAoVivo
    let cor: Color
    var tamanho: CGFloat = 15
    var comRotulo = true

    var body: some View {
        if let chegada = estado.chegada {
            VStack(alignment: .trailing, spacing: 1) {
                if comRotulo {
                    Text("chega")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.white.opacity(0.55))
                }
                Text(EstadoAoVivo.hora(chegada))
                    .font(.system(size: tamanho, weight: .semibold).monospacedDigit())
                    .foregroundColor(cor)
                    .contentTransition(.numericText())
            }
        }
    }
}

/// A barra que enche até a chegada (anda sozinha; o painel acerta o começo a cada posição).
struct BarraViagem: View {
    let estado: EstadoAoVivo
    let cor: Color

    var body: some View {
        if let intervalo = estado.intervaloViagem {
            ProgressView(timerInterval: intervalo, countsDown: false) {
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

/// Quadrinho de baixo ("Próximo posto" / "Chuva").
private struct QuadroViagem: View {
    let rotulo: String
    let valor: String
    var corValor: Color = .white

    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(rotulo)
                .font(.system(size: 11))
                .foregroundColor(.white.opacity(0.55))
                .lineLimit(1)
            Text(valor)
                .font(.system(size: 13.5, weight: .semibold).monospacedDigit())
                .foregroundColor(corValor)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .contentTransition(.numericText())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color.white.opacity(0.06)))
    }
}

/// Os quadrinhos (posto e chuva); só os que têm o que dizer.
struct QuadrosViagem: View {
    let estado: EstadoAoVivo

    var body: some View {
        let posto = estado.postoTexto
        let chuva = estado.viagem?.chuva
        if posto != nil || chuva != nil {
            HStack(spacing: 8) {
                if let posto {
                    QuadroViagem(rotulo: "Próximo posto", valor: posto)
                }
                if let chuva {
                    QuadroViagem(rotulo: estado.viagem?.chuvaRotulo ?? "Chuva", valor: chuva, corValor: corChuva)
                        .transition(.opacity)
                }
            }
        }
    }
}

/// Tela bloqueada (e banner nos iPhones sem ilha): o protótipo "No carro".
struct TelaViagem: View {
    let estado: EstadoAoVivo
    let cor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                IconeAssunto(icone: estado.icone, cor: cor)
                VStack(alignment: .leading, spacing: 1) {
                    Text(estado.titulo)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(.white)
                        .lineLimit(1)
                    Text(estado.faltaTexto)
                        .font(.system(size: 12).monospacedDigit())
                        .foregroundColor(.white.opacity(0.55))
                        .lineLimit(1)
                        .contentTransition(.numericText(countsDown: true))
                }
                Spacer(minLength: 6)
                ChegadaViagem(estado: estado, cor: cor)
                    .frame(minWidth: 64, alignment: .trailing)
            }
            BarraViagem(estado: estado, cor: cor)
            QuadrosViagem(estado: estado)
        }
    }
}

/// Mínima da ilha (quando divide com outra atividade): anel que enche até a chegada, com o carro dentro.
struct AnelViagem: View {
    let estado: EstadoAoVivo
    let cor: Color

    var body: some View {
        if let intervalo = estado.intervaloViagem {
            ProgressView(timerInterval: intervalo, countsDown: false) {
                EmptyView()
            } currentValueLabel: {
                Image(systemName: estado.icone).font(.system(size: 9, weight: .semibold))
            }
            .progressViewStyle(.circular)
            .tint(cor)
            .foregroundColor(cor)
        } else {
            Image(systemName: estado.icone).foregroundColor(cor)
        }
    }
}
