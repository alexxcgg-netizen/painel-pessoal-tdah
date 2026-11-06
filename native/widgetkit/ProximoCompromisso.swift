//
//  ProximoCompromisso.swift
//  Widgets da tela bloqueada do próximo compromisso de saída/voo - 2026-11-04
//
//  accessoryRectangular ("Date · sai em 1:20:00 · 18°"), accessoryCircular (anel até o próximo passo,
//  andando sozinho) e accessoryInline ("Date · sai 18:45"). Mesmo dado da atividade ao vivo:
//  GET /api/ao-vivo (CompromissoAtributos.swift), com o token do widget; sem rede, o último bom.
//  A timeline ganha uma entrada em cada virada de passo, então "sai em" vira "chega em" na hora certa.
//  Na tela bloqueada o iOS pinta tudo de uma cor só: aqui nada depende da cor do assunto.
//  2026-11-05 (leva dos widgets nativos): retângulo do jeito votado no protótipo ("Sair às 18:45" / "lugar · 25 min
//  de carro"); sem compromisso, a linha e o retângulo mostram o próximo voo; sem token, o código do pareamento.
//  2026-11-06 (docs/briefings/2026-11-06-ao-vivo-tarefa.md): sem compromisso de saída, a próxima tarefa de hoje com
//  hora (`proxima_tarefa` do /api/ao-vivo) vem antes do voo - era "Nada pra sair nas próximas 6 h".
//

import SwiftUI
import WidgetKit

struct ProximoEntry: TimelineEntry {
    let date: Date
    let estado: CompromissoAtributos.ContentState?  // nil = nada nas próximas 6 h
    /// Sem compromisso: o próximo voo (GET /api/widget), pra linha e o retângulo não ficarem vazios.
    var voo: VooWidget? = nil
    /// Widget ainda sem token: o código que o app confirma (PainelDados.swift).
    var codigo: String? = nil
    /// Sem compromisso: a próxima tarefa de hoje com hora (some quando a hora passa).
    var tarefa: AoVivoResposta.ProximaTarefa? = nil

    /// A tarefa que ainda vale nesta entrada da timeline.
    var tarefaQueVem: AoVivoResposta.ProximaTarefa? {
        guard let tarefa, tarefa.em > date else { return nil }
        return tarefa
    }
}

/// Entradas da timeline: agora + cada virada de passo + o fim (já sem compromisso). Usado também pelo
/// widget da tela inicial (PainelWidget.swift).
enum TimelineAoVivo {
    static func datas(_ estado: CompromissoAtributos.ContentState?, agora: Date, ate limite: Date) -> [Date] {
        var datas = [agora]
        guard let estado else { return datas }
        for p in estado.passos where p.em > agora && p.em < limite { datas.append(p.em) }
        if estado.fim > agora && estado.fim < limite { datas.append(estado.fim) }
        return datas.sorted()
    }

    /// O estado que vale numa data (some depois do fim).
    static func estado(_ estado: CompromissoAtributos.ContentState?, em data: Date) -> CompromissoAtributos.ContentState? {
        guard let estado, data < estado.fim else { return nil }
        return estado
    }

    /// Próxima busca: 20 min, ou antes se o compromisso acabar antes disso.
    static func proximaBusca(_ estado: CompromissoAtributos.ContentState?, agora: Date) -> Date {
        let padrao = agora.addingTimeInterval(20 * 60)
        guard let fim = estado?.fim, fim > agora else { return padrao }
        return min(padrao, fim.addingTimeInterval(60))
    }
}

struct ProximoProvider: TimelineProvider {
    static let amostra: CompromissoAtributos.ContentState = {
        let agora = Date()
        return CompromissoAtributos.ContentState(
            titulo: "Date", lugar: "Centro", icone: "heart.fill", cor: "f5a3b8",
            passos: [
                .init(chave: "arrumar", rotulo: "Arrumar", em: agora.addingTimeInterval(40 * 60)),
                .init(chave: "sair", rotulo: "Sair", em: agora.addingTimeInterval(80 * 60)),
                .init(chave: "chegar", rotulo: "Chegar", em: agora.addingTimeInterval(95 * 60)),
            ],
            atual: -1, temp: 18, chuva: 20, fim: agora.addingTimeInterval(105 * 60)
        )
    }()

    func placeholder(in context: Context) -> ProximoEntry {
        ProximoEntry(date: Date(), estado: Self.amostra)
    }

    func getSnapshot(in context: Context, completion: @escaping (ProximoEntry) -> Void) {
        if context.isPreview {
            completion(ProximoEntry(date: Date(), estado: Self.amostra))
            return
        }
        Task {
            let (estado, voo, codigo, tarefa) = await Self.buscarTudo()
            completion(ProximoEntry(date: Date(), estado: TimelineAoVivo.estado(estado, em: Date()), voo: voo,
                                    codigo: codigo, tarefa: tarefa))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ProximoEntry>) -> Void) {
        Task {
            let (estado, voo, codigo, tarefa) = await Self.buscarTudo()
            let agora = Date()
            var proxima = TimelineAoVivo.proximaBusca(estado, agora: agora)
            if codigo != nil { proxima = min(proxima, agora.addingTimeInterval(60)) }
            // passou a hora da tarefa: busca de novo logo depois pra mostrar a seguinte
            if let t = tarefa, t.em > agora { proxima = min(proxima, t.em.addingTimeInterval(60)) }
            var datas = TimelineAoVivo.datas(estado, agora: agora, ate: proxima.addingTimeInterval(1))
            if let t = tarefa, t.em > agora, t.em < proxima, !datas.contains(t.em) { datas.append(t.em) }
            let entradas = datas.sorted().map {
                ProximoEntry(date: $0, estado: TimelineAoVivo.estado(estado, em: $0), voo: voo, codigo: codigo,
                             tarefa: tarefa)
            }
            completion(Timeline(entries: entradas, policy: .after(proxima)))
        }
    }

    /// O painel primeiro (é ele que pareia e traz o token), depois o compromisso.
    static func buscarTudo() async -> (CompromissoAtributos.ContentState?, VooWidget?, String?, AoVivoResposta.ProximaTarefa?) {
        let carga = await PainelDados.carregar()
        if case .parear(let codigo) = carga {
            let ultimo = AoVivoAPI.ultimo()
            return (ultimo?.estado, nil, codigo, ultimo?.proximaTarefa)
        }
        let r = await buscar()
        return (r?.estado, carga.payload?.voo, nil, r?.proximaTarefa)
    }

    /// Rede primeiro; sem rede, a última resposta boa (o fim dela ainda tira o que já passou).
    static func buscar() async -> AoVivoResposta? {
        if let r = await AoVivoAPI.buscar(base: PainelConfig.urlBase, token: PainelConfig.token) {
            return r
        }
        return AoVivoAPI.ultimo()
    }
}

// MARK: - Views

private extension View {
    /// iOS 17+ exige containerBackground também na tela bloqueada (senão aparece o aviso do sistema).
    @ViewBuilder
    func fundoTelaBloqueada() -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            self.containerBackground(Color.clear, for: .widget)
        } else {
            self
        }
    }
}

struct ProximoRetangular: View {
    let entry: ProximoEntry

    /// "Sair às 18:45" (ou o passo que vem: "Chegar às 19:10").
    private func linhaPasso(_ e: CompromissoAtributos.ContentState) -> String {
        guard let p = e.proximo(em: entry.date) else { return e.ehTarefa ? "Agora" : "Chegou" }
        if p.chave == "hora" { return "Às " + CompromissoAtributos.ContentState.hora(p.em) }
        let verbo: String
        switch p.chave {
        case "arrumar": verbo = "Arrumar"
        case "sair": verbo = "Sair"
        case "parada": verbo = p.rotulo
        default: verbo = "Chegar"
        }
        return "\(verbo) às \(CompromissoAtributos.ContentState.hora(p.em))"
    }

    /// "Cinema · 25 min de carro" (da saída até a chegada); sem saída, a linha do tempo.
    private func linhaLugar(_ e: CompromissoAtributos.ContentState) -> String {
        if let sair = e.passos.first(where: { $0.chave == "sair" }), let chegar = e.chegada, chegar > sair.em {
            let minutos = Int(chegar.timeIntervalSince(sair.em) / 60)
            if let lugar = e.lugar, !lugar.isEmpty { return "\(lugar) · \(minutos) min de carro" }
            return "\(minutos) min de carro"
        }
        return e.linhaTempo
    }

    var body: some View {
        if let e = entry.estado {
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 4) {
                    Image(systemName: e.icone).font(.system(size: 12, weight: .semibold))
                    Text(e.titulo).font(.system(size: 14, weight: .semibold)).lineLimit(1)
                }
                Text(linhaPasso(e))
                    .font(.system(size: 13, weight: .medium).monospacedDigit())
                    .lineLimit(1)
                let lugar = linhaLugar(e)
                if let hora = e.horaTarefa, hora > entry.date {
                    Text(hora, style: .relative)  // "18 min" até a hora da tarefa
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                } else if !lugar.isEmpty {
                    Text(lugar)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else if let t = entry.tarefaQueVem {
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 4) {
                    Image(systemName: "clock.fill").font(.system(size: 12, weight: .semibold))
                    Text(t.titulo).font(.system(size: 14, weight: .semibold)).lineLimit(1)
                }
                Text("Às \(CompromissoAtributos.ContentState.hora(t.em))")
                    .font(.system(size: 13, weight: .medium).monospacedDigit())
                    .lineLimit(1)
                Text(t.em, style: .relative)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else if let voo = entry.voo {
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 4) {
                    Image(systemName: "airplane").font(.system(size: 12, weight: .semibold))
                    Text(voo.destino.map { "\(voo.origem) → \($0)" } ?? voo.origem)
                        .font(.system(size: 14, weight: .semibold)).lineLimit(1)
                }
                Text([voo.dia, voo.hora].compactMap { $0 }.joined(separator: " "))
                    .font(.system(size: 13, weight: .medium).monospacedDigit())
                    .lineLimit(1)
                if let condicao = voo.condicao {
                    Text([condicao, voo.vento].compactMap { $0 }.joined(separator: " · "))
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else if let codigo = entry.codigo {
            VStack(alignment: .leading, spacing: 1) {
                Text("Painel").font(.system(size: 14, weight: .semibold))
                Text("Abre o app e confirma")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                Text(codigo).font(.system(size: 15, weight: .semibold, design: .rounded).monospacedDigit())
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            VStack(alignment: .leading, spacing: 1) {
                Text("Painel").font(.system(size: 14, weight: .semibold))
                Text("Nada com hora por hoje")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct ProximoCircular: View {
    let entry: ProximoEntry

    var body: some View {
        if let e = entry.estado, let p = e.proximo(em: entry.date) {
            // O anel enche do passo anterior até o próximo (antes do primeiro passo: as 3 h antes dele).
            let i = e.atual(em: entry.date)
            let inicio = i >= 0 ? e.passos[i].em : p.em.addingTimeInterval(-3 * 3600)
            ProgressView(timerInterval: CompromissoAtributos.ContentState.intervalo(de: inicio, ate: p.em),
                         countsDown: true) {
                Text(e.titulo)
            } currentValueLabel: {
                VStack(spacing: 0) {
                    Image(systemName: e.icone).font(.system(size: 11, weight: .semibold))
                    Text(CompromissoAtributos.ContentState.hora(p.em))
                        .font(.system(size: 11, weight: .semibold))
                        .minimumScaleFactor(0.7)
                }
            }
            .progressViewStyle(.circular)
        } else if let e = entry.estado {
            Image(systemName: e.icone).font(.system(size: 20, weight: .semibold))
        } else if let t = entry.tarefaQueVem {
            // o anel enche nas 3 h antes da hora da tarefa
            ProgressView(timerInterval: CompromissoAtributos.ContentState.intervalo(
                de: t.em.addingTimeInterval(-3 * 3600), ate: t.em), countsDown: true) {
                Text(t.titulo)
            } currentValueLabel: {
                VStack(spacing: 0) {
                    Image(systemName: "clock.fill").font(.system(size: 11, weight: .semibold))
                    Text(CompromissoAtributos.ContentState.hora(t.em))
                        .font(.system(size: 11, weight: .semibold))
                        .minimumScaleFactor(0.7)
                }
            }
            .progressViewStyle(.circular)
        } else {
            Image(systemName: "checkmark.circle").font(.system(size: 20))
        }
    }
}

struct ProximoLinha: View {
    let entry: ProximoEntry

    var body: some View {
        if let e = entry.estado, let p = e.proximo(em: entry.date) {
            Text(p.chave == "hora" ? "\(e.titulo) · \(CompromissoAtributos.ContentState.hora(p.em))"
                 : "\(e.titulo) · \(p.chave == "sair" ? "sai" : p.rotulo.lowercased()) \(CompromissoAtributos.ContentState.hora(p.em))")
        } else if let e = entry.estado {
            Text(e.ehTarefa ? "\(e.titulo) · agora" : "\(e.titulo) · chegou")
        } else if let t = entry.tarefaQueVem {
            Label("\(t.titulo) · \(CompromissoAtributos.ContentState.hora(t.em))", systemImage: "clock")
        } else if let voo = entry.voo {
            // "✈ sáb. 07:30" ao lado da data
            Label(Self.diaDoVoo(voo) + (voo.hora.map { " \($0)" } ?? ""), systemImage: "airplane")
        } else if let codigo = entry.codigo {
            Text("Painel: confirma \(codigo) no app")
        } else {
            Text("Painel: nada com hora hoje")
        }
    }

    /// "hoje", "amanhã" ou o dia da semana curto ("sáb.").
    static func diaDoVoo(_ voo: VooWidget) -> String {
        if voo.dia == "hoje" || voo.dia == "amanhã" { return voo.dia }
        let ler = DateFormatter()
        ler.locale = Locale(identifier: "pt_BR")
        ler.dateFormat = "yyyy-MM-dd"
        guard let d = ler.date(from: voo.data) else { return voo.dia }
        let f = DateFormatter()
        f.locale = Locale(identifier: "pt_BR")
        f.dateFormat = "EEE"
        return f.string(from: d)
    }
}

struct ProximoEntryView: View {
    @Environment(\.widgetFamily) private var familia
    let entry: ProximoEntry

    var body: some View {
        switch familia {
        case .accessoryCircular:
            ProximoCircular(entry: entry).fundoTelaBloqueada()
        case .accessoryInline:
            ProximoLinha(entry: entry).fundoTelaBloqueada()
        default:
            ProximoRetangular(entry: entry).fundoTelaBloqueada()
        }
    }
}

struct ProximoCompromisso: Widget {
    let kind: String = "ProximoCompromisso"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: ProximoProvider()) { entry in
            ProximoEntryView(entry: entry)
        }
        .configurationDisplayName("Próximo compromisso")
        .description("Quando sair pro próximo compromisso; sem nenhum, a próxima tarefa com hora ou o próximo voo.")
        .supportedFamilies([.accessoryRectangular, .accessoryCircular, .accessoryInline])
    }
}

struct ProximoCompromisso_Previews: PreviewProvider {
    static var previews: some View {
        ProximoEntryView(entry: ProximoEntry(date: Date(), estado: ProximoProvider.amostra))
            .previewContext(WidgetPreviewContext(family: .accessoryRectangular))
    }
}
