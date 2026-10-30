//
//  PainelWidget.swift
//  PainelWidget (WidgetKit extension) — Fase 7 / faixa n3e-widgetkit
//
//  Widget nativo iOS que lê o MESMO contrato JSON de `GET /api/widget`
//  (autenticado por `Authorization: Bearer <token>`, ver Config.swift) usado
//  pelos outros clientes do painel. Cobre as famílias de tela inicial
//  (systemSmall/systemMedium) e de tela de bloqueio (accessoryCircular/
//  accessoryRectangular/accessoryInline) — mesma ideia do widget Scriptable
//  já existente em `scriptable/widget_lockscreen.js` e
//  `docs/WIDGET_TELA_BLOQUEIO.md`, mas em SwiftUI/WidgetKit nativo.
//
//  Contrato JSON esperado (definido no prompt desta faixa, N3e):
//  {
//    "versao": 1,
//    "atualizado_em": "2026-09-23T20:10:00Z",
//    "estado": "normal" | "vazio" | "erro",
//    "foco": {"titulo": "Revisar contrato", "em_minutos": 19} | null,
//    "proxima_conta": {"nome": "Cartão", "em_dias": 3} | null,
//    "habitos": {"feitos": 3, "total": 5} | null,
//    "custo_ia": {"percentual_teto": 42} | null,
//    "linhas": ["Foco: Revisar contrato em 19 min", "Conta: Cartão em 3 dias",
//               "Hábitos: 3/5", "IA: 42% do teto"]
//  }
//
//  IMPORTANTE (ver README.md): este código NÃO foi compilado nem testado
//  neste ambiente — não há Mac com Xcode aqui, só leitura cuidadosa da
//  documentação pública do WidgetKit/SwiftUI. Antes de considerar pronto,
//  abra no Xcode, resolva qualquer erro de compilação e confira visualmente
//  as 5 famílias no canvas/preview.
//

import WidgetKit
import SwiftUI

// MARK: - Modelo (Codable do contrato JSON)

enum EstadoPainel: String, Codable {
    case normal
    case vazio
    case erro
}

struct FocoAtual: Codable {
    let titulo: String
    let emMinutos: Int

    enum CodingKeys: String, CodingKey {
        case titulo
        case emMinutos = "em_minutos"
    }
}

struct ProximaConta: Codable {
    let nome: String
    let emDias: Int

    enum CodingKeys: String, CodingKey {
        case nome
        case emDias = "em_dias"
    }
}

struct HabitosDoDia: Codable {
    let feitos: Int
    let total: Int
}

struct CustoIA: Codable {
    let percentualTeto: Int

    enum CodingKeys: String, CodingKey {
        case percentualTeto = "percentual_teto"
    }
}

struct PainelWidgetPayload: Codable {
    let versao: Int
    let atualizadoEm: Date
    let estado: EstadoPainel
    let foco: FocoAtual?
    let proximaConta: ProximaConta?
    let habitos: HabitosDoDia?
    let custoIA: CustoIA?
    let linhas: [String]

    enum CodingKeys: String, CodingKey {
        case versao
        case atualizadoEm = "atualizado_em"
        case estado
        case foco
        case proximaConta = "proxima_conta"
        case habitos
        case custoIA = "custo_ia"
        case linhas
    }

    /// Decoder usado tanto pra resposta ao vivo quanto pro cache do App
    /// Group (`PainelConfig.ultimoPayload`) — os dois são o mesmo JSON.
    static func decodificar(_ dados: Data) throws -> PainelWidgetPayload {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(PainelWidgetPayload.self, from: dados)
    }
}

// MARK: - Estado exibido pelo widget (normal / vazio / erro)

/// Estado local de exibição — não é 1:1 com `EstadoPainel` porque também
/// cobre falha de rede/token ausente, que o backend nunca reporta (ele só
/// fala de si mesmo quando responde). `.normal` sempre carrega o payload
/// completo; `.erro` carrega uma mensagem curta já pronta pra tela pequena.
enum EstadoExibicao {
    case normal(PainelWidgetPayload)
    case vazio
    case erro(String)
}

struct PainelEntry: TimelineEntry {
    let date: Date
    let estado: EstadoExibicao
}

// MARK: - TimelineProvider

struct PainelTimelineProvider: TimelineProvider {

    /// Preview no galeria de widgets (antes de configurar) — dado de
    /// exemplo sintético, nunca dado real do Alex.
    func placeholder(in context: Context) -> PainelEntry {
        PainelEntry(date: Date(), estado: .normal(Self.amostra))
    }

    func getSnapshot(in context: Context, completion: @escaping (PainelEntry) -> Void) {
        if context.isPreview {
            completion(PainelEntry(date: Date(), estado: .normal(Self.amostra)))
            return
        }
        Task {
            let estado = await Self.buscarEstadoAtual()
            completion(PainelEntry(date: Date(), estado: estado))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<PainelEntry>) -> Void) {
        Task {
            let estado = await Self.buscarEstadoAtual()
            let agora = Date()
            let entry = PainelEntry(date: agora, estado: estado)

            // Atualização a cada ~15-30 min (pedido da faixa) — o sistema
            // ainda pode adiar/agrupar por conta própria (orçamento de
            // atualização do WidgetKit é dele, não nosso), isso aqui só
            // pede o próximo horário desejado.
            let minutosAteProximaAtualizacao = 20
            let proxima = Calendar.current.date(
                byAdding: .minute,
                value: minutosAteProximaAtualizacao,
                to: agora
            ) ?? agora.addingTimeInterval(TimeInterval(minutosAteProximaAtualizacao * 60))

            let timeline = Timeline(entries: [entry], policy: .after(proxima))
            completion(timeline)
        }
    }

    /// Busca `/api/widget`; em falha de rede/HTTP, cai pro último payload
    /// bom salvo no App Group (se o backend já respondeu `estado: "erro"`
    /// no corpo, isso é respeitado direto, sem cair no cache). Só vira
    /// `.erro` de verdade quando não há rede/token/URL configurada E
    /// também não há nenhum cache anterior pra mostrar.
    static func buscarEstadoAtual() async -> EstadoExibicao {
        guard let url = PainelConfig.widgetURL else {
            return estadoComFallback(mensagem: "Configure a URL do painel no app")
        }
        guard let token = PainelConfig.token, !token.isEmpty else {
            return estadoComFallback(mensagem: "Configure o token do painel no app")
        }

        var requisicao = URLRequest(url: url)
        requisicao.httpMethod = "GET"
        requisicao.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        requisicao.timeoutInterval = 10

        do {
            let (dados, resposta) = try await URLSession.shared.data(for: requisicao)
            guard let http = resposta as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
                return estadoComFallback(mensagem: "Painel respondeu com erro")
            }
            let payload = try PainelWidgetPayload.decodificar(dados)
            PainelConfig.salvarUltimoPayload(dados)

            switch payload.estado {
            case .vazio:
                return .vazio
            case .erro:
                return .erro(payload.linhas.first ?? "Painel sinalizou um erro")
            case .normal:
                return .normal(payload)
            }
        } catch {
            return estadoComFallback(mensagem: "Sem conexão com o painel")
        }
    }

    /// Cai pro cache do App Group quando a rede falha. Se não houver cache
    /// nenhum ainda (primeira execução, ou nunca funcionou), mostra a
    /// mensagem de erro recebida.
    private static func estadoComFallback(mensagem: String) -> EstadoExibicao {
        guard let cache = PainelConfig.ultimoPayload(),
              let payload = try? PainelWidgetPayload.decodificar(cache.dados),
              payload.estado == .normal else {
            return .erro(mensagem)
        }
        return .normal(payload)
    }

    /// Dado sintético pro placeholder/preview — nunca dado real do Alex.
    static let amostra = PainelWidgetPayload(
        versao: 1,
        atualizadoEm: Date(),
        estado: .normal,
        foco: FocoAtual(titulo: "Revisar contrato", emMinutos: 19),
        proximaConta: ProximaConta(nome: "Cartão", emDias: 3),
        habitos: HabitosDoDia(feitos: 3, total: 5),
        custoIA: CustoIA(percentualTeto: 42),
        linhas: [
            "Foco: Revisar contrato em 19 min",
            "Conta: Cartão em 3 dias",
            "Hábitos: 3/5",
            "IA: 42% do teto",
        ]
    )
}

// MARK: - Cores (mesmo tema escuro de static/css/style.css)

/// Paleta lida direto de `static/css/style.css` (`:root`), não inventada.
/// `--cor-painel` (esmeralda) é a cor de identidade da aba "Painel" no app
/// web — como este widget é um resumo geral do painel, ela também é o
/// accent aqui. Nas famílias de tela de bloqueio (`accessory*`) o próprio
/// iOS renderiza tudo monocromático e ignora cor customizada (mesma nota já
/// registrada em `docs/WIDGET_TELA_BLOQUEIO.md` pro widget Scriptable) —
/// por isso essas views usam só `.primary`/`.secondary`, nunca `Color(hex:)`.
enum PainelCores {
    static let fundo = Color(hex: "121212")       // --surface
    static let fundoAlt = Color(hex: "181818")    // --surface-2
    static let texto = Color(hex: "eceef3")       // --text
    static let textoMuted = Color(hex: "a7afbc")  // --text-muted
    static let textoFaint = Color(hex: "788292")  // --text-faint
    static let accent = Color(hex: "41aa75")      // --cor-painel (esmeralda)
    static let erro = Color(hex: "ff5c72")        // --danger
    static let borda = Color.white.opacity(0.09)  // --border (aprox., era rgba sobre fundo escuro)
}

extension Color {
    /// Hex de 6 dígitos, sem "#" (ex: "41aa75"). Sem suporte a alpha porque
    /// nenhuma cor da paleta acima precisa disso.
    init(hex: String) {
        var valor: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&valor)
        let r = Double((valor & 0xFF0000) >> 16) / 255.0
        let g = Double((valor & 0x00FF00) >> 8) / 255.0
        let b = Double(valor & 0x0000FF) / 255.0
        self.init(red: r, green: g, blue: b)
    }
}

/// No iOS 17+ o fundo do widget precisa vir de `.containerBackground`, não
/// de `.background` comum (WidgetKit exige isso pra Liquid Glass/redução de
/// transparência do sistema funcionar). Em versões anteriores (16, onde já
/// existem os `accessory*` de tela de bloqueio) `.background` ainda é o
/// jeito certo. Este helper cobre os dois sem duplicar cada view.
private extension View {
    @ViewBuilder
    func fundoDoWidget(_ cor: Color) -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            self.containerBackground(cor, for: .widget)
        } else {
            self.background(cor)
        }
    }
}

// MARK: - View raiz (escolhe layout pela família)

struct PainelWidgetEntryView: View {
    @Environment(\.widgetFamily) private var familia
    let entry: PainelEntry

    var body: some View {
        switch familia {
        case .systemSmall:
            PainelViewPequena(estado: entry.estado)
        case .systemMedium:
            PainelViewMedia(estado: entry.estado)
        // Tela de bloqueio também precisa de `.containerBackground` no iOS 17+, senão o iOS troca o
        // widget inteiro pelo aviso "Please adopt containerBackground API". Fundo transparente: o
        // próprio sistema desenha o vidro da tela de bloqueio.
        case .accessoryCircular:
            PainelViewCircular(estado: entry.estado)
                .fundoDoWidget(.clear)
        case .accessoryRectangular:
            PainelViewRetangular(estado: entry.estado)
                .fundoDoWidget(.clear)
        case .accessoryInline:
            PainelViewLinha(estado: entry.estado)
                .fundoDoWidget(.clear)
        default:
            // Família não coberta por esta faixa (ex: systemLarge) — cai
            // pro layout médio em vez de ficar em branco.
            PainelViewMedia(estado: entry.estado)
        }
    }
}

// MARK: - systemSmall

struct PainelViewPequena: View {
    let estado: EstadoExibicao

    var body: some View {
        Group {
            switch estado {
            case .normal(let payload):
                VStack(alignment: .leading, spacing: 6) {
                    rotulo("PAINEL")
                    if let foco = payload.foco {
                        Text(foco.titulo)
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(PainelCores.texto)
                            .lineLimit(2)
                        Text("em \(foco.emMinutos) min")
                            .font(.system(size: 12))
                            .foregroundStyle(PainelCores.textoMuted)
                    } else {
                        Text("Sem foco agora")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(PainelCores.textoMuted)
                    }
                    Spacer(minLength: 4)
                    if let habitos = payload.habitos {
                        rodapeIndicador(
                            texto: "Hábitos \(habitos.feitos)/\(habitos.total)"
                        )
                    }
                    if let custoIA = payload.custoIA {
                        rodapeIndicador(texto: "IA \(custoIA.percentualTeto)%")
                    }
                }
            case .vazio:
                estadoVazio
            case .erro(let mensagem):
                estadoErro(mensagem)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
        .fundoDoWidget(PainelCores.fundo)
    }

    private func rotulo(_ texto: String) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(PainelCores.accent)
                .frame(width: 6, height: 6)
            Text(texto)
                .font(.system(size: 10, weight: .bold))
                .tracking(0.5)
                .foregroundStyle(PainelCores.textoFaint)
        }
    }

    private func rodapeIndicador(texto: String) -> some View {
        Text(texto)
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(PainelCores.textoMuted)
    }

    private var estadoVazio: some View {
        VStack(alignment: .leading, spacing: 6) {
            rotulo("PAINEL")
            Spacer(minLength: 4)
            Text("Tudo em dia")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(PainelCores.textoMuted)
        }
    }

    private func estadoErro(_ mensagem: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            rotulo("PAINEL")
            Spacer(minLength: 4)
            Text(mensagem)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(PainelCores.erro)
                .lineLimit(3)
        }
    }
}

// MARK: - systemMedium

struct PainelViewMedia: View {
    let estado: EstadoExibicao

    var body: some View {
        Group {
            switch estado {
            case .normal(let payload):
                HStack(alignment: .top, spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        rotulo("PAINEL")
                        if let foco = payload.foco {
                            linha(titulo: "Foco", texto: "\(foco.titulo) · \(foco.emMinutos) min")
                        }
                        if let conta = payload.proximaConta {
                            linha(titulo: "Conta", texto: "\(conta.nome) em \(conta.emDias)d")
                        }
                        if payload.foco == nil && payload.proximaConta == nil {
                            Text("Nada urgente agora")
                                .font(.system(size: 13))
                                .foregroundStyle(PainelCores.textoMuted)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                    VStack(alignment: .trailing, spacing: 10) {
                        if let habitos = payload.habitos {
                            barraProgresso(
                                titulo: "Hábitos",
                                valor: "\(habitos.feitos)/\(habitos.total)",
                                fracao: habitos.total > 0
                                    ? Double(habitos.feitos) / Double(habitos.total)
                                    : 0
                            )
                        }
                        if let custoIA = payload.custoIA {
                            barraProgresso(
                                titulo: "IA",
                                valor: "\(custoIA.percentualTeto)%",
                                fracao: Double(custoIA.percentualTeto) / 100.0,
                                estourado: custoIA.percentualTeto >= 100
                            )
                        }
                    }
                    .frame(width: 108)
                }
            case .vazio:
                VStack(alignment: .leading, spacing: 8) {
                    rotulo("PAINEL")
                    Text("Tudo em dia — nada pra mostrar agora")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(PainelCores.textoMuted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            case .erro(let mensagem):
                VStack(alignment: .leading, spacing: 8) {
                    rotulo("PAINEL")
                    Text(mensagem)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(PainelCores.erro)
                        .lineLimit(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .fundoDoWidget(PainelCores.fundo)
    }

    private func rotulo(_ texto: String) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(PainelCores.accent)
                .frame(width: 6, height: 6)
            Text(texto)
                .font(.system(size: 10, weight: .bold))
                .tracking(0.5)
                .foregroundStyle(PainelCores.textoFaint)
        }
    }

    private func linha(titulo: String, texto: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(titulo)
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(PainelCores.textoFaint)
            Text(texto)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(PainelCores.texto)
                .lineLimit(2)
        }
    }

    private func barraProgresso(titulo: String, valor: String, fracao: Double, estourado: Bool = false) -> some View {
        VStack(alignment: .trailing, spacing: 3) {
            Text("\(titulo) \(valor)")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(PainelCores.textoMuted)
            GeometryReader { geo in
                ZStack(alignment: .trailing) {
                    Capsule()
                        .fill(PainelCores.borda)
                    Capsule()
                        .fill(estourado ? PainelCores.erro : PainelCores.accent)
                        .frame(width: geo.size.width * min(max(fracao, 0), 1))
                }
            }
            .frame(height: 5)
        }
    }
}

// MARK: - accessoryCircular (tela de bloqueio)

struct PainelViewCircular: View {
    let estado: EstadoExibicao

    var body: some View {
        // O sistema renderiza esta família monocromática (ver nota em
        // docs/WIDGET_TELA_BLOQUEIO.md sobre o widget Scriptable) — não faz
        // sentido usar Color(hex:) aqui, o iOS ignora mesmo.
        switch estado {
        case .normal(let payload):
            if let habitos = payload.habitos, habitos.total > 0 {
                Gauge(value: Double(habitos.feitos), in: 0...Double(habitos.total)) {
                    Text("Hábitos")
                } currentValueLabel: {
                    Text("\(habitos.feitos)/\(habitos.total)")
                        .font(.system(size: 13, weight: .semibold))
                }
                .gaugeStyle(.accessoryCircular)
            } else if let foco = payload.foco {
                VStack(spacing: 0) {
                    Text("\(foco.emMinutos)")
                        .font(.system(size: 18, weight: .bold))
                    Text("min")
                        .font(.system(size: 9))
                }
            } else {
                Image(systemName: "checkmark.circle")
                    .font(.system(size: 20))
            }
        case .vazio:
            Image(systemName: "checkmark.circle")
                .font(.system(size: 20))
        case .erro:
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 18))
        }
    }
}

// MARK: - accessoryRectangular (tela de bloqueio)

struct PainelViewRetangular: View {
    let estado: EstadoExibicao

    var body: some View {
        switch estado {
        case .normal(let payload):
            VStack(alignment: .leading, spacing: 2) {
                Text(payload.linhas.first ?? "Painel")
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                if payload.linhas.count > 1 {
                    Text(payload.linhas[1])
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        case .vazio:
            Text("Tudo em dia")
                .font(.system(size: 13, weight: .semibold))
        case .erro(let mensagem):
            Text(mensagem)
                .font(.system(size: 12, weight: .medium))
                .lineLimit(2)
        }
    }
}

// MARK: - accessoryInline (tela de bloqueio, ao lado do relógio)

struct PainelViewLinha: View {
    let estado: EstadoExibicao

    var body: some View {
        switch estado {
        case .normal(let payload):
            Text(payload.linhas.first ?? "Painel")
        case .vazio:
            Text("Painel: tudo em dia")
        case .erro:
            Text("Painel indisponível")
        }
    }
}

// MARK: - Definição do Widget

struct PainelWidget: Widget {
    let kind: String = "PainelWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PainelTimelineProvider()) { entry in
            PainelWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Painel")
        .description("Foco atual, próxima conta, hábitos do dia e uso de IA.")
        .supportedFamilies([
            .systemSmall,
            .systemMedium,
            .accessoryCircular,
            .accessoryRectangular,
            .accessoryInline,
        ])
    }
}

struct PainelWidget_Previews: PreviewProvider {
    static var previews: some View {
        PainelWidgetEntryView(entry: PainelEntry(date: .now, estado: .normal(PainelTimelineProvider.amostra)))
            .previewContext(WidgetPreviewContext(family: .systemSmall))
    }
}
