//
//  WidgetsDia.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  Dia (médio, jeito do Calendário: data grande e as próximas três coisas), Hoje (grande, jeito do Lembretes:
//  a lista do dia, a bolinha marca feito sem abrir o app no iOS 17+) e Conta (pequeno: em quantos dias vence a
//  próxima conta, sem valor). Dados: "agenda", "hoje" e "proxima_conta" de GET /api/widget.
//  Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import AppIntents
import SwiftUI
import WidgetKit

// MARK: - Dia

struct DiaMedio: View {
    let payload: PainelWidgetPayload
    let agora: Date

    private var diaDaSemana: String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "pt_BR")
        f.dateFormat = "EEEE"
        let nome = f.string(from: agora).components(separatedBy: "-").first ?? ""
        return nome.uppercased()
    }

    private var proximos: [ItemAgenda] {
        (payload.agenda ?? []).filter { item in
            guard !item.concluido else { return false }
            let fim = PainelEstilo.hojeAs(item.fim ?? item.hora, em: agora) ?? agora
            return fim > agora
        }
    }

    private static func cor(_ tipo: String) -> Color {
        switch tipo {
        case "habito": return .green
        case "tarefa": return .pink
        default: return .orange
        }
    }

    /// "14:30 – 15:15" (ou só "14:30").
    private static func faixa(_ item: ItemAgenda) -> String {
        guard let fim = item.fim, fim != item.hora else { return item.hora }
        return "\(item.hora) – \(fim)"
    }

    var body: some View {
        let tarefas = payload.hoje ?? []
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 0) {
                Text(diaDaSemana)
                    .font(.system(size: 12, weight: .semibold))
                    .tracking(0.3)
                    .foregroundStyle(.red)
                    .widgetAccentable()
                Text("\(Calendar.current.component(.day, from: agora))")
                    .font(.system(size: 44, weight: .regular).monospacedDigit())
                    .lineLimit(1)
                if !tarefas.isEmpty {
                    Text("\(tarefas.filter(\.feita).count) de \(tarefas.count) feitas")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(.secondary)
                        .padding(.top, 6)
                }
            }
            .frame(width: 96, alignment: .leading)

            VStack(alignment: .leading, spacing: 9) {
                if proximos.isEmpty {
                    Text("Nada mais marcado hoje")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(proximos.prefix(3).enumerated()), id: \.offset) { _, item in
                        HStack(alignment: .top, spacing: 8) {
                            RoundedRectangle(cornerRadius: 2, style: .continuous)
                                .fill(Self.cor(item.tipo))
                                .frame(width: 4)
                                .widgetAccentable()
                            VStack(alignment: .leading, spacing: 1) {
                                Text(item.titulo)
                                    .font(.system(size: 14, weight: .semibold))
                                    .lineLimit(1)
                                Text(verbatim: Self.faixa(item))
                                    .font(.system(size: 13).monospacedDigit())
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(.top, 2)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

struct PainelDia: Widget {
    let kind: String = "PainelDia"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            CascaWidget(carga: entrada.carga) { p in
                DiaMedio(payload: p, agora: entrada.date)
            }
        }
        .configurationDisplayName("Dia")
        .description("A data e as próximas três coisas com hora, como o Calendário.")
        .supportedFamilies([.systemMedium])
    }
}

// MARK: - Hoje (lista com caixinha)

struct HojeGrande: View {
    let tarefas: [TarefaHoje]

    static let maximo = 6

    var body: some View {
        let abertas = tarefas.filter { !$0.feita }.count
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                BolaSimbolo(simbolo: "list.bullet", cor: .orange)
                Spacer()
                Text("\(abertas)")
                    .font(.system(size: 28, weight: .bold, design: .rounded).monospacedDigit())
            }
            Text("Hoje")
                .font(.system(size: 20, weight: .bold))
                .foregroundStyle(.orange)
                .widgetAccentable()
                .padding(.top, 6)
                .padding(.bottom, 4)
            if tarefas.isEmpty {
                Text("Nada pra hoje. Pede no chat que eu anoto.")
                    .font(.system(size: 15))
                    .foregroundStyle(.secondary)
                    .padding(.top, 8)
                Spacer(minLength: 0)
            } else {
                ForEach(Array(tarefas.prefix(Self.maximo).enumerated()), id: \.element.id) { n, t in
                    LinhaTarefa(tarefa: t, ultima: n == min(tarefas.count, Self.maximo) - 1)
                }
                Spacer(minLength: 0)
                if tarefas.count > Self.maximo {
                    Text("mais \(tarefas.count - Self.maximo) no painel")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

/// Uma linha do Lembretes: bolinha, título, hora; a separação começa depois da bolinha.
struct LinhaTarefa: View {
    let tarefa: TarefaHoje
    let ultima: Bool

    private var conteudo: some View {
        HStack(spacing: 0) {
            ZStack {
                Circle()
                    .strokeBorder(tarefa.feita ? Color.orange : Color.secondary.opacity(0.5), lineWidth: 1.6)
                if tarefa.feita {
                    Circle().fill(Color.orange).frame(width: 13, height: 13)
                }
            }
            .frame(width: 21, height: 21)
            .widgetAccentable()
            .frame(width: 34, alignment: .leading)

            VStack(alignment: .leading, spacing: 1) {
                Text(tarefa.titulo)
                    .font(.system(size: 15))
                    .foregroundStyle(tarefa.feita ? Color.secondary : Color.primary)
                    .lineLimit(1)
                if tarefa.atrasada == true && !tarefa.feita {
                    Text("atrasada")
                        .font(.system(size: 13))
                        .foregroundStyle(.red)
                } else if let hora = tarefa.hora {
                    Text(hora)
                        .font(.system(size: 13).monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            .overlay(alignment: .bottom) {
                if !ultima {
                    Rectangle().fill(Color.secondary.opacity(0.3)).frame(height: 0.5)
                }
            }
        }
        .contentShape(Rectangle())
    }

    var body: some View {
        if #available(iOSApplicationExtension 17.0, *) {
            Button(intent: MarcarTarefaIntent(tarefaID: tarefa.id, feita: !tarefa.feita)) { conteudo }
                .buttonStyle(.plain)
        } else {
            conteudo
        }
    }
}

struct PainelHoje: Widget {
    let kind: String = "PainelHoje"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            CascaWidget(carga: entrada.carga) { p in
                HojeGrande(tarefas: p.hoje ?? [])
            }
        }
        .configurationDisplayName("Hoje")
        .description("As tarefas do dia; toca na bolinha e marca feito sem abrir o app.")
        .supportedFamilies([.systemLarge])
    }
}

// MARK: - Conta

struct ContaPequeno: View {
    let conta: ProximaConta?
    let agora: Date

    /// O desenho pelo nome da conta (luz, água, internet...); o resto, um papel.
    private static func simbolo(_ nome: String) -> String {
        let n = nome.lowercased()
        if n.contains("luz") || n.contains("energia") || n.contains("celesc") { return "bolt.fill" }
        if n.contains("água") || n.contains("agua") || n.contains("samae") || n.contains("casan") { return "drop.fill" }
        if n.contains("internet") || n.contains("wifi") || n.contains("fibra") { return "wifi" }
        if n.contains("cartão") || n.contains("cartao") || n.contains("fatura") { return "creditcard.fill" }
        if n.contains("aluguel") || n.contains("condom") { return "house.fill" }
        if n.contains("celular") || n.contains("telefone") || n.contains("plano") { return "iphone" }
        if n.contains("carro") || n.contains("ipva") || n.contains("seguro") { return "car.fill" }
        return "doc.text.fill"
    }

    var body: some View {
        if let conta {
            VStack(alignment: .leading, spacing: 0) {
                ZStack {
                    Circle().fill(Color.yellow).widgetAccentable()
                    Image(systemName: Self.simbolo(conta.nome))
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(.black)
                }
                .frame(width: 30, height: 30)
                Spacer(minLength: 4)
                Text(conta.nome)
                    .font(.system(size: 15, weight: .semibold))
                    .lineLimit(1)
                quando(conta.emDias)
                if let dias = conta.emDias, dias > 0 {
                    Text("vence \(PainelEstilo.diaCurto(daqui: dias, de: agora))")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(.secondary)
                        .padding(.top, 6)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                BolaSimbolo(simbolo: "checkmark", cor: .green)
                Spacer(minLength: 4)
                Text("Nenhuma conta")
                    .font(.system(size: 15, weight: .semibold))
                Text("vencendo por agora")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder
    private func quando(_ dias: Int?) -> some View {
        if let dias, dias > 0 {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("\(dias)").font(PainelEstilo.numero(34))
                Text(dias == 1 ? "dia" : "dias")
                    .font(.system(size: 16, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
            }
        } else if let dias {
            Text(dias == 0 ? "hoje" : "vencida")
                .font(PainelEstilo.numero(30))
                .foregroundStyle(dias == 0 ? Color.orange : Color.red)
                .widgetAccentable()
        } else {
            Text("sem data")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(.secondary)
        }
    }
}

struct PainelConta: Widget {
    let kind: String = "PainelConta"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelProvedor()) { entrada in
            CascaWidget(carga: entrada.carga) { p in
                ContaPequeno(conta: p.proximaConta, agora: entrada.date)
            }
        }
        .configurationDisplayName("Conta que vence")
        .description("Em quantos dias vence a próxima conta. Sem valor.")
        .supportedFamilies([.systemSmall])
    }
}
