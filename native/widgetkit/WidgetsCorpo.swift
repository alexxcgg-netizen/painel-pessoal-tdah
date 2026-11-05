//
//  WidgetsCorpo.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  Proteína (pequeno: anel do jeito do Fitness no fundo preto; tela bloqueada: medidor redondo) e Água
//  (pequeno: copos do dia e o botão + que registra direto da tela de início, iOS 17+).
//  Dados: "comida" e "agua" de GET /api/widget. Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import AppIntents
import SwiftUI
import WidgetKit

// MARK: - Proteína

/// O anel com a ponta arredondada e a setinha no começo, como os do Fitness.
struct AnelFitness: View {
    let fracao: Double
    var espessura: CGFloat = 13

    var body: some View {
        let f = min(max(fracao, 0), 1)
        ZStack {
            Circle()
                .stroke(PainelEstilo.fit1.opacity(0.22), lineWidth: espessura)
            Circle()
                .trim(from: 0, to: max(f, 0.001))
                .stroke(AngularGradient(colors: [PainelEstilo.fit1, PainelEstilo.fit2], center: .center,
                                        startAngle: .degrees(0), endAngle: .degrees(360 * max(f, 0.05))),
                        style: StrokeStyle(lineWidth: espessura, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .widgetAccentable()
            GeometryReader { geo in
                Image(systemName: "arrow.right")
                    .font(.system(size: espessura * 0.62, weight: .black))
                    .foregroundStyle(.black)
                    .position(x: geo.size.width / 2, y: 0)
            }
        }
        .padding(espessura / 2)
    }
}

struct ProteinaView: View {
    @Environment(\.widgetFamily) private var familia
    let entrada: PainelEntrada

    var body: some View {
        if familia == .accessoryCircular {
            ProteinaMedidor(comida: entrada.carga.payload?.comida)
                .fundoBloqueio()
        } else {
            CascaWidget(carga: entrada.carga, fundo: Color.black) { p in
                ProteinaPequeno(comida: p.comida)
            }
            .environment(\.colorScheme, .dark)
        }
    }
}

struct ProteinaPequeno: View {
    let comida: ComidaDoDia?

    private var rodape: String {
        guard let comida, comida.refeicoes > 0 else { return "nada comido ainda" }
        return "\(PainelEstilo.milhar(comida.kcal)) kcal hoje"
    }

    private var valor: String {
        let g = Int(comida?.proteinaG ?? 0)
        let meta = Int(comida?.metaProteinaG ?? 0)
        return meta > 0 ? "\(g)/\(meta)" : "\(g)"
    }

    var body: some View {
        let g = comida?.proteinaG ?? 0
        let meta = comida?.metaProteinaG ?? 0
        VStack(alignment: .leading, spacing: 0) {
            AnelFitness(fracao: meta > 0 ? g / meta : 0)
                .frame(width: 72, height: 72)
            Spacer(minLength: 4)
            Text("Proteína")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(PainelEstilo.fit2)
            HStack(alignment: .firstTextBaseline, spacing: 1) {
                Text(verbatim: valor)
                    .font(PainelEstilo.numero(22))
                Text("G")
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
            }
            .foregroundStyle(PainelEstilo.fit2)
            .widgetAccentable()
            Text(verbatim: rodape)
                .font(.system(size: 12, weight: .medium).monospacedDigit())
                .foregroundStyle(Color.white.opacity(0.6))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// Tela bloqueada: o medidor aberto embaixo, igual os da Apple.
struct ProteinaMedidor: View {
    let comida: ComidaDoDia?

    var body: some View {
        let g = comida?.proteinaG ?? 0
        let meta = max(comida?.metaProteinaG ?? 0, 1)
        Gauge(value: min(g, meta), in: 0...meta) {
            Image(systemName: "fork.knife")
        } currentValueLabel: {
            Text("\(Int(g))")
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .minimumScaleFactor(0.7)
        }
        .gaugeStyle(.accessoryCircular)
        .widgetAccentable()
    }
}

struct PainelProteina: Widget {
    let kind: String = "PainelProteina"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            ProteinaView(entrada: entrada)
        }
        .configurationDisplayName("Proteína")
        .description("O que tu comeu de proteína hoje contra a meta, no anel.")
        .supportedFamilies([.systemSmall, .accessoryCircular])
    }
}

// MARK: - Água

struct AguaPequeno: View {
    let agua: AguaDoDia?

    private func altura(_ i: Int) -> CGFloat { CGFloat(40 + (i * 37 % 60)) / 100 * 30 }

    var body: some View {
        let copos = agua?.copos ?? 0
        let meta = min(max(agua?.meta ?? 8, 1), 12)
        VStack(alignment: .leading, spacing: 0) {
            CabecalhoWidget(simbolo: "drop.fill", titulo: "Água", cor: .cyan)
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(verbatim: agua == nil ? "–" : String(copos))
                    .font(PainelEstilo.numero(34))
                Text("de \(meta) copos")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
            .padding(.top, 8)
            Spacer(minLength: 4)
            HStack(alignment: .bottom) {
                HStack(alignment: .bottom, spacing: 3) {
                    ForEach(0..<meta, id: \.self) { i in
                        Capsule()
                            .fill(i < copos ? Color.cyan : PainelEstilo.trilho)
                            .frame(width: 7, height: altura(i))
                    }
                }
                .frame(height: 30, alignment: .bottom)
                .widgetAccentable()
                Spacer(minLength: 4)
                BotaoMaisAgua()
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// O "+": no iOS 17+ registra o copo sem abrir o app (MaisAguaIntent); no 16 o toque só abre o app.
struct BotaoMaisAgua: View {
    private var bola: some View {
        ZStack {
            Circle().fill(Color.cyan).widgetAccentable()
            Image(systemName: "plus")
                .font(.system(size: 18, weight: .bold))
                .foregroundStyle(.white)
        }
        .frame(width: 40, height: 40)
    }

    var body: some View {
        if #available(iOSApplicationExtension 17.0, *) {
            Button(intent: MaisAguaIntent()) { bola }
                .buttonStyle(.plain)
                .accessibilityLabel("Mais um copo")
        } else {
            bola
        }
    }
}

struct PainelAgua: Widget {
    let kind: String = "PainelAgua"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            CascaWidget(carga: entrada.carga) { p in
                AguaPequeno(agua: p.agua)
            }
        }
        .configurationDisplayName("Água")
        .description("Os copos do dia e o + direto da tela de início.")
        .supportedFamilies([.systemSmall])
    }
}
