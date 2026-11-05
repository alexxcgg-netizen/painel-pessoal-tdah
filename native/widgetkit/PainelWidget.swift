//
//  PainelWidget.swift
//  PainelWidget (WidgetKit extension) - reescrito em 2026-11-05 (leva dos widgets nativos)
//
//  O provedor que todos os widgets da tela de início usam (PainelDados.carregar: GET /api/widget, pareamento
//  por código, cache) e o widget "Próximo" (kind "PainelWidget", o mesmo de antes, pequeno): quanto falta pra
//  sair pro próximo compromisso, contando sozinho, e os passos; sem compromisso, a próxima coisa da agenda.
//  Os outros widgets: WidgetsDia.swift, WidgetsCorpo.swift, WidgetsVoo.swift. Briefing:
//  docs/briefings/2026-11-05-widgets-ios.md. Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import SwiftUI
import WidgetKit

// MARK: - Entrada e provedor

struct PainelEntrada: TimelineEntry {
    let date: Date
    let carga: Carga
    /// Só o widget "Próximo" busca (GET /api/ao-vivo).
    var compromisso: CompromissoAtributos.ContentState? = nil
}

struct PainelProvedor: TimelineProvider {
    var comCompromisso = false

    func placeholder(in context: Context) -> PainelEntrada {
        PainelEntrada(date: Date(), carga: .dados(.amostra), compromisso: comCompromisso ? ProximoProvider.amostra : nil)
    }

    func getSnapshot(in context: Context, completion: @escaping (PainelEntrada) -> Void) {
        if context.isPreview {
            completion(placeholder(in: context))
            return
        }
        Task {
            let (carga, compromisso) = await buscar()
            completion(PainelEntrada(date: Date(), carga: carga, compromisso: TimelineAoVivo.estado(compromisso, em: Date())))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<PainelEntrada>) -> Void) {
        Task {
            let (carga, compromisso) = await buscar()
            let agora = Date()
            var limite = PainelDados.proximaAtualizacao(carga, agora: agora)
            // virada do dia: Dia, Hoje e Água recomeçam
            if let meiaNoite = Calendar.current.nextDate(after: agora, matching: DateComponents(hour: 0, minute: 0, second: 30),
                                                         matchingPolicy: .nextTime), meiaNoite < limite {
                limite = meiaNoite
            }
            if comCompromisso { limite = min(limite, TimelineAoVivo.proximaBusca(compromisso, agora: agora)) }

            // uma entrada em cada virada (passo do compromisso, começo/fim de cada coisa da agenda)
            var datas = Set(TimelineAoVivo.datas(compromisso, agora: agora, ate: limite.addingTimeInterval(1)))
            for item in carga.payload?.agenda ?? [] {
                for hhmm in [item.hora, item.fim] {
                    if let d = PainelEstilo.hojeAs(hhmm, em: agora), d > agora, d < limite { datas.insert(d) }
                }
            }
            let entradas = datas.sorted().map {
                PainelEntrada(date: $0, carga: carga, compromisso: TimelineAoVivo.estado(compromisso, em: $0))
            }
            completion(Timeline(entries: entradas, policy: .after(limite)))
        }
    }

    private func buscar() async -> (Carga, CompromissoAtributos.ContentState?) {
        let carga = await PainelDados.carregar()
        guard comCompromisso, PainelConfig.token != nil else { return (carga, nil) }
        let compromisso = await ProximoProvider.buscar()
        return (carga, compromisso)
    }
}

// MARK: - Próximo (pequeno)

struct ProximoPequeno: View {
    let entrada: PainelEntrada

    var body: some View {
        CascaWidget(carga: entrada.carga) { p in
            if let c = entrada.compromisso {
                BlocoProximo(estado: c, agora: entrada.date)
            } else {
                ProximoDaAgenda(payload: p, agora: entrada.date)
            }
        }
    }
}

/// Compromisso de saída/voo chegando: "Sair em" e a contagem andando sozinha, os passos e a hora/lugar.
struct BlocoProximo: View {
    let estado: CompromissoAtributos.ContentState
    let agora: Date

    private var cor: Color { Color(hex: estado.cor) }

    private static func rotulo(_ p: CompromissoAtributos.Passo) -> String {
        switch p.chave {
        case "arrumar": return "Arrumar em"
        case "sair": return "Sair em"
        case "parada": return "Parada em"
        default: return "Chega em"
        }
    }

    /// A hora que mais importa embaixo: a de sair (ou a de chegar, se não tiver saída).
    private var horaDoPe: String {
        let sair = estado.passos.first { $0.chave == "sair" } ?? estado.passos.last
        return sair.map { CompromissoAtributos.ContentState.hora($0.em) } ?? ""
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            CabecalhoWidget(simbolo: estado.icone, titulo: estado.titulo, cor: cor)
            Spacer(minLength: 4)
            if let p = estado.proximo(em: agora) {
                Text(Self.rotulo(p))
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.secondary)
                Text(timerInterval: CompromissoAtributos.ContentState.intervalo(de: agora, ate: p.em), countsDown: true)
                    .font(PainelEstilo.numero(34))
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
            } else {
                Text("Chegou")
                    .font(PainelEstilo.numero(30))
            }
            Spacer(minLength: 6)
            BarrasDosPassos(estado: estado, agora: agora, cor: cor)
            HStack {
                Text(horaDoPe)
                Spacer(minLength: 4)
                Text(estado.lugar ?? "")
                    .lineLimit(1)
            }
            .font(.system(size: 12, weight: .medium).monospacedDigit())
            .foregroundStyle(.secondary)
            .padding(.top, 6)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }
}

/// Um tracinho por passo: cheio os que passaram, enchendo sozinho o de agora (ProgressView com intervalo).
struct BarrasDosPassos: View {
    let estado: CompromissoAtributos.ContentState
    let agora: Date
    let cor: Color

    var body: some View {
        let atual = estado.atual(em: agora)
        HStack(spacing: 3) {
            ForEach(Array(estado.passos.prefix(4).enumerated()), id: \.offset) { i, passo in
                if i <= atual {
                    Capsule().fill(cor).frame(height: 4).widgetAccentable()
                } else if i == atual + 1 {
                    let inicio = i > 0 ? estado.passos[i - 1].em : passo.em.addingTimeInterval(-3 * 3600)
                    ProgressView(timerInterval: CompromissoAtributos.ContentState.intervalo(de: inicio, ate: passo.em),
                                 countsDown: false) {
                        EmptyView()
                    } currentValueLabel: {
                        EmptyView()
                    }
                    .progressViewStyle(.linear)
                    .tint(cor)
                    .widgetAccentable()
                } else {
                    Capsule().fill(PainelEstilo.trilho).frame(height: 4)
                }
            }
        }
        .frame(height: 6)
    }
}

/// Sem compromisso de saída: a próxima coisa da agenda de hoje (ou "nada marcado").
struct ProximoDaAgenda: View {
    let payload: PainelWidgetPayload
    let agora: Date

    private var proximo: ItemAgenda? {
        (payload.agenda ?? []).first { item in
            guard !item.concluido else { return false }
            let fim = PainelEstilo.hojeAs(item.fim ?? item.hora, em: agora) ?? agora
            return fim > agora
        }
    }

    var body: some View {
        if let item = proximo {
            VStack(alignment: .leading, spacing: 0) {
                CabecalhoWidget(simbolo: "calendar", titulo: "Próximo", cor: .red)
                Spacer(minLength: 4)
                Text(item.titulo)
                    .font(.system(size: 15, weight: .semibold))
                    .lineLimit(2)
                Text(item.hora)
                    .font(PainelEstilo.numero(34))
                    .lineLimit(1)
                if let fim = item.fim, fim != item.hora {
                    Text("até \(fim)")
                        .font(.system(size: 12, weight: .medium).monospacedDigit())
                        .foregroundStyle(.secondary)
                        .padding(.top, 2)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                CabecalhoWidget(simbolo: "calendar", titulo: "Próximo", cor: .red)
                Spacer(minLength: 4)
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 30))
                    .foregroundStyle(.green)
                    .widgetAccentable()
                Text("Nada marcado")
                    .font(.system(size: 15, weight: .semibold))
                    .padding(.top, 4)
                Text("o resto do dia é teu")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        }
    }
}

struct PainelWidget: Widget {
    let kind: String = "PainelWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor(comCompromisso: true)) { entrada in
            ProximoPequeno(entrada: entrada)
        }
        .configurationDisplayName("Próximo")
        .description("Quanto falta pra sair pro próximo compromisso, contando sozinho.")
        .supportedFamilies([.systemSmall])
    }
}

struct PainelWidget_Previews: PreviewProvider {
    static var previews: some View {
        ProximoPequeno(entrada: PainelEntrada(date: .now, carga: .dados(.amostra), compromisso: ProximoProvider.amostra))
            .previewContext(WidgetPreviewContext(family: .systemSmall))
    }
}
