//
//  WidgetsVoo.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  Voo (médio, jeito do Tempo: rota, hora, condição e o vento de hora em hora no aeródromo de saída, previsão do
//  Open-Meteo até 2 dias antes) e Horas de voo (pequeno: quanto falta pra meta; tela bloqueada: medidor redondo).
//  Dados: "voo" e "horas_voo" de GET /api/widget (rotas/widget_ios.py). Não compilado aqui (sem Mac).
//

import SwiftUI
import WidgetKit

// MARK: - Voo

struct VooView: View {
    @Environment(\.colorScheme) private var esquema
    let carga: Carga

    private var ceu: LinearGradient {
        let cores: [Color] = esquema == .dark
            ? [Color(hex: "1d4f8f"), Color(hex: "2f6db3")]
            : [Color(hex: "3a7bd5"), Color(hex: "5a9ee6")]
        return LinearGradient(colors: cores, startPoint: .top, endPoint: .bottom)
    }

    var body: some View {
        CascaWidget(carga: carga, fundo: ceu) { p in
            VooMedio(voo: p.voo)
        }
        .foregroundStyle(.white)
    }
}

struct VooMedio: View {
    let voo: VooWidget?

    private static func maiuscula(_ s: String) -> String {
        s.prefix(1).uppercased() + s.dropFirst()
    }

    var body: some View {
        if let voo {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 5) {
                            Text(voo.origem)
                            if let destino = voo.destino {
                                Image(systemName: "airplane")
                                    .font(.system(size: 12, weight: .semibold))
                                    .widgetAccentable()
                                Text(destino)
                            }
                        }
                        .font(.system(size: 15, weight: .semibold))
                        Text(voo.hora ?? "sem hora")
                            .font(.system(size: voo.hora == nil ? 22 : 44, weight: .light).monospacedDigit())
                            .lineLimit(1)
                    }
                    Spacer(minLength: 8)
                    VStack(alignment: .trailing, spacing: 1) {
                        if voo.condicao != nil {
                            Image(systemName: PainelEstilo.simboloTempo(voo.codigo))
                                .symbolRenderingMode(.multicolor)
                                .font(.system(size: 20))
                                .padding(.bottom, 2)
                        }
                        Text(voo.condicao.map(Self.maiuscula) ?? Self.maiuscula(voo.dia))
                            .font(.system(size: 13, weight: .semibold))
                        if let vento = voo.vento, voo.condicao != nil {
                            Text("\(voo.dia) · \(vento)")
                                .font(.system(size: 13, weight: .medium).monospacedDigit())
                                .opacity(0.85)
                        }
                    }
                    .multilineTextAlignment(.trailing)
                }
                Spacer(minLength: 4)
                if let horas = voo.horas, !horas.isEmpty {
                    HStack(spacing: 0) {
                        ForEach(Array(horas.prefix(6).enumerated()), id: \.offset) { _, h in
                            VStack(spacing: 5) {
                                Text(h.hora)
                                Image(systemName: PainelEstilo.simboloTempo(h.codigo))
                                    .symbolRenderingMode(.multicolor)
                                    .font(.system(size: 18))
                                    .frame(height: 20)
                                Text("\(h.ventoKt) kt").fontWeight(.semibold)
                            }
                            .font(.system(size: 12, weight: .medium).monospacedDigit())
                            .frame(maxWidth: .infinity)
                        }
                    }
                } else {
                    Text(voo.hora == nil ? "Marca a hora do voo pra ver o tempo" : "O tempo aparece 2 dias antes")
                        .font(.system(size: 13, weight: .medium))
                        .opacity(0.85)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        } else {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: "airplane")
                    .font(.system(size: 20, weight: .semibold))
                    .widgetAccentable()
                Spacer(minLength: 2)
                Text("Nenhum voo marcado")
                    .font(.system(size: 17, weight: .semibold))
                Text("nos próximos 7 dias")
                    .font(.system(size: 13, weight: .medium))
                    .opacity(0.85)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        }
    }
}

struct PainelVoo: Widget {
    let kind: String = "PainelVoo"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            VooView(carga: entrada.carga)
        }
        .configurationDisplayName("Voo")
        .description("O próximo voo e o vento de hora em hora, como o Tempo.")
        .supportedFamilies([.systemMedium])
    }
}

// MARK: - Horas de voo

struct HorasView: View {
    @Environment(\.widgetFamily) private var familia
    let entrada: PainelEntrada

    var body: some View {
        if familia == .accessoryCircular {
            HorasMedidor(horas: entrada.carga.payload?.horasVoo)
                .fundoBloqueio()
        } else {
            CascaWidget(carga: entrada.carga) { p in
                HorasPequeno(horas: p.horasVoo)
            }
        }
    }
}

struct HorasPequeno: View {
    let horas: HorasVoo?

    /// "faltam 53,5 h pra 150" ou "meta de 150 h batida".
    private static func falta(_ h: HorasVoo) -> String {
        let meta = PainelEstilo.horas(h.meta)
        if h.total >= h.meta { return "meta de \(meta) h batida" }
        return "faltam \(PainelEstilo.horas(h.meta - h.total)) h pra \(meta)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            CabecalhoWidget(simbolo: "airplane", titulo: "Horas de voo", cor: .blue)
            Spacer(minLength: 4)
            if let horas {
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(PainelEstilo.horas(horas.total))
                        .font(PainelEstilo.numero(34))
                    Text("h")
                        .font(.system(size: 16, weight: .semibold, design: .rounded))
                        .foregroundStyle(.secondary)
                }
                .padding(.bottom, 10)
                BarraFina(fracao: horas.meta > 0 ? horas.total / horas.meta : 0, cor: .blue)
                Text(verbatim: Self.falta(horas))
                    .font(.system(size: 12, weight: .medium).monospacedDigit())
                    .foregroundStyle(.secondary)
                    .padding(.top, 6)
            } else {
                Text("Nenhuma hora registrada ainda")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

struct HorasMedidor: View {
    let horas: HorasVoo?

    var body: some View {
        let total = horas?.total ?? 0
        let meta = max(horas?.meta ?? 150, 1)
        Gauge(value: min(total, meta), in: 0...meta) {
            Image(systemName: "airplane")
        } currentValueLabel: {
            Text("\(Int(total))")
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .minimumScaleFactor(0.7)
        }
        .gaugeStyle(.accessoryCircular)
        .widgetAccentable()
    }
}

struct PainelHoras: Widget {
    let kind: String = "PainelHoras"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            HorasView(entrada: entrada)
        }
        .configurationDisplayName("Horas de voo")
        .description("Quanto falta pra meta de horas de voo.")
        .supportedFamilies([.systemSmall, .accessoryCircular])
    }
}
