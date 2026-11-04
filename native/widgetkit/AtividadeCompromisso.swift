//
//  AtividadeCompromisso.swift
//  Desenho da atividade ao vivo do próximo compromisso (tela bloqueada + Dynamic Island) - 2026-11-04
//
//  Segue a barra aprovada no protótipo D ("ela te avisando passo a passo"): pílula escura, ícone num círculo
//  na cor do assunto, título, contagem na cor do assunto à direita e a fileira de passos
//  Arrumar → Sair → (Parada) → Chegar com o passo de agora em destaque.
//  Os dados: CompromissoAtributos.swift. Quem liga/atualiza/encerra: native/ios/App/AoVivo.swift.
//
//  O passo "agora" é calculado com o relógio na hora de desenhar (o iOS redesenha quando a atividade
//  fica velha - staleDate = o próximo passo), então a fileira anda mesmo sem o app acordar.
//

import ActivityKit
import SwiftUI
import WidgetKit

// MARK: - Peças

private let fundoPilula = Color(red: 24 / 255, green: 24 / 255, blue: 28 / 255)

/// Ícone do assunto num círculo com a cor a 20% sobre o preto (la-ic do protótipo).
struct IconeAssunto: View {
    let icone: String
    let cor: Color
    var tamanho: CGFloat = 30

    var body: some View {
        ZStack {
            Circle().fill(Color.black)
            Circle().fill(cor.opacity(0.2))
            Image(systemName: icone)
                .font(.system(size: tamanho * 0.5, weight: .semibold))
                .foregroundColor(cor)
        }
        .frame(width: tamanho, height: tamanho)
    }
}

/// Contagem até o próximo passo, andando sozinha (Text(timerInterval:)). Depois de chegar: "chegou".
struct ContagemPasso: View {
    let estado: CompromissoAtributos.ContentState
    let agora: Date
    let cor: Color
    var tamanho: CGFloat = 15
    var comRotulo = true

    var body: some View {
        if let p = estado.proximo(em: agora) {
            VStack(alignment: .trailing, spacing: 1) {
                if comRotulo {
                    Text(CompromissoAtributos.ContentState.rotuloContagem(p))
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.white.opacity(0.55))
                }
                Text(timerInterval: CompromissoAtributos.ContentState.intervalo(de: agora, ate: p.em), countsDown: true)
                    .font(.system(size: tamanho, weight: .semibold).monospacedDigit())
                    .foregroundColor(cor)
                    .multilineTextAlignment(.trailing)
            }
        } else {
            Text("chegou")
                .font(.system(size: tamanho, weight: .semibold))
                .foregroundColor(cor)
        }
    }
}

/// A fileira de passos com a linha que enche até o passo de agora (la-passos do protótipo).
struct FileiraPassos: View {
    let passos: [CompromissoAtributos.Passo]
    let atual: Int
    let cor: Color

    private func corBolinha(_ i: Int) -> Color {
        if i == atual && i < passos.count - 1 { return .white }
        if i <= atual { return cor }
        return Color(red: 44 / 255, green: 44 / 255, blue: 48 / 255)
    }

    private func corRotulo(_ i: Int) -> Color {
        if i == atual && i < passos.count - 1 { return .white }
        if i < atual || (i == atual && i == passos.count - 1) { return .white.opacity(0.75) }
        return .white.opacity(0.45)
    }

    var body: some View {
        let n = max(passos.count, 1)
        let progresso = n > 1 ? CGFloat(min(max(atual, 0), n - 1)) / CGFloat(n - 1) : 0
        ZStack(alignment: .top) {
            GeometryReader { geo in
                let coluna = geo.size.width / CGFloat(n)
                let largura = coluna * CGFloat(n - 1)
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.14)).frame(width: largura, height: 2)
                    Capsule().fill(cor).frame(width: largura * progresso, height: 2)
                }
                .offset(x: coluna / 2, y: 5)
            }
            .frame(height: 12)
            HStack(spacing: 0) {
                ForEach(0..<passos.count, id: \.self) { i in
                    VStack(spacing: 6) {
                        Circle()
                            .fill(corBolinha(i))
                            .frame(width: 12, height: 12)
                            .overlay(Circle().stroke(fundoPilula, lineWidth: 2))
                            .scaleEffect(i == atual && i < passos.count - 1 ? 1.25 : 1)
                        Text(passos[i].rotulo)
                            .font(.system(size: 11.5, weight: i == atual ? .semibold : .regular))
                            .foregroundColor(corRotulo(i))
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
    }
}

// MARK: - Atividade

struct AtividadeCompromisso: Widget {
    private func cor(_ e: CompromissoAtributos.ContentState) -> Color { Color(hex: e.cor) }

    private func tituloComLugar(_ e: CompromissoAtributos.ContentState) -> String {
        guard let lugar = e.lugar, !lugar.isEmpty, lugar != e.titulo else { return e.titulo }
        return "\(e.titulo) · \(lugar)"
    }

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: CompromissoAtributos.self) { contexto in
            // Tela bloqueada (e banner nos iPhones sem ilha): a barra do protótipo
            let e = contexto.state
            let agora = Date()
            let c = cor(e)
            VStack(alignment: .leading, spacing: 11) {
                HStack(spacing: 10) {
                    IconeAssunto(icone: e.icone, cor: c)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(tituloComLugar(e))
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(.white)
                            .lineLimit(1)
                        if !e.linhaTempo.isEmpty {
                            Text(e.linhaTempo)
                                .font(.system(size: 12))
                                .foregroundColor(.white.opacity(0.55))
                                .lineLimit(1)
                        }
                    }
                    Spacer(minLength: 6)
                    ContagemPasso(estado: e, agora: agora, cor: c)
                        .frame(minWidth: 64, alignment: .trailing)
                }
                FileiraPassos(passos: e.passos, atual: e.atual(em: agora), cor: c)
            }
            .padding(.horizontal, 14)
            .padding(.top, 13)
            .padding(.bottom, 12)
            .activityBackgroundTint(fundoPilula.opacity(0.78))
            .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { contexto in
            let e = contexto.state
            let agora = Date()
            let c = cor(e)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    IconeAssunto(icone: e.icone, cor: c, tamanho: 36)
                        .padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    ContagemPasso(estado: e, agora: agora, cor: c, tamanho: 20)
                        .frame(minWidth: 72, alignment: .trailing)
                        .padding(.trailing, 4)
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(tituloComLugar(e))
                            .font(.system(size: 15, weight: .semibold))
                            .lineLimit(1)
                        if let p = e.proximo(em: agora) {
                            Text("\(p.rotulo) às \(CompromissoAtributos.ContentState.hora(p.em))")
                                .font(.system(size: 12))
                                .foregroundColor(.white.opacity(0.55))
                                .lineLimit(1)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 8) {
                        FileiraPassos(passos: e.passos, atual: e.atual(em: agora), cor: c)
                        if !e.linhaTempo.isEmpty {
                            Text(e.linhaTempo)
                                .font(.system(size: 12))
                                .foregroundColor(.white.opacity(0.55))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding(.horizontal, 4)
                    .padding(.top, 4)
                }
            } compactLeading: {
                Image(systemName: e.icone)
                    .foregroundColor(c)
            } compactTrailing: {
                if let p = e.proximo(em: agora) {
                    Text(timerInterval: CompromissoAtributos.ContentState.intervalo(de: agora, ate: p.em), countsDown: true)
                        .font(.system(size: 14, weight: .semibold).monospacedDigit())
                        .foregroundColor(c)
                        .multilineTextAlignment(.trailing)
                        .frame(maxWidth: 52)
                } else {
                    Image(systemName: "checkmark")
                        .foregroundColor(c)
                }
            } minimal: {
                Image(systemName: e.icone)
                    .foregroundColor(c)
            }
            .keylineTint(c)
        }
    }
}
