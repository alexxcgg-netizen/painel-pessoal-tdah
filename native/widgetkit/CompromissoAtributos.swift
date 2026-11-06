//
//  CompromissoAtributos.swift
//  Compartilhado entre o app (AoVivo.swift liga/atualiza/encerra) e o widget (desenha) - 2026-11-04
//
//  Atividade ao vivo do próximo compromisso de saída ou voo (docs/briefings/2026-11-04-cards-ao-vivo.md):
//  passos Arrumar → Sair → (Parada) → Chegar, contagem até o próximo passo, cor e ícone do assunto, tempo na
//  chegada. Os dados vêm de GET /api/ao-vivo (rotas/ao_vivo.py), com o mesmo token do widget.
//  Sem push de APNs (conta grátis): o app atualiza quando abre e quando o iOS o acorda por uma visita.
//
//  Este arquivo entra nos DOIS alvos (project.yml): só Foundation + ActivityKit, nada de SwiftUI/UIKit.
//
//  2026-11-06 (leva do ao vivo de tarefa, docs/briefings/2026-11-06-ao-vivo-tarefa.md): tarefa com hora nas
//  próximas 2 h 30 vira atividade de UM passo ("hora"), com `tag` pro botão Feito (FeitoAoVivoIntent.swift)
//  e `feito` pro desenho do check antes de sumir. `proxima_tarefa` alimenta o widget da tela bloqueada.
//
//  2026-11-06 (leva "painel esperto", frente 3, docs/briefings/2026-11-06-painel-esperto.md): kind `viagem` - a
//  viagem planejada em andamento (destino, km que faltam, chegada refeita pela posição, próximo posto, chuva à
//  frente). Passos Saída → Chegada + `viagem` com o resto. Desenho: AtividadeViagem.swift. `acompanhar` diz ao
//  app se a posição do carro pode ir pro painel agora (Localizacao.swift).
//

import ActivityKit
import Foundation

struct CompromissoAtributos: ActivityAttributes {
    struct Passo: Codable, Hashable {
        var chave: String   // "arrumar" | "sair" | "parada" | "chegar" | "hora" (tarefa sem saída)
        var rotulo: String  // "Arrumar", "Sair", "Casa do guri", "Chegar"
        var em: Date
    }

    struct ContentState: Codable, Hashable {
        var titulo: String
        var lugar: String?
        var icone: String   // SF Symbol
        var cor: String     // hex sem "#", ex. "f5a3b8"
        var passos: [Passo]
        var atual: Int      // índice do último passo que já passou quando o painel respondeu (-1: nenhum)
        var temp: Int?
        var chuva: Int?
        var fim: Date       // depois disso a atividade some
        var tag: String? = nil    // "tarefa_horario-12": o botão Feito (só tarefa com hora)
        var feito: Bool? = nil    // true depois do Feito: o check aparece e a atividade some
        var viagem: Viagem? = nil // só na viagem acompanhada (kind "viagem")
    }

    /// O miolo da viagem acompanhada (GET /api/ao-vivo, kind "viagem"). Os textos já vêm prontos do painel.
    struct Viagem: Codable, Hashable {
        var faltaKm: Int
        var totalKm: Int
        var barraDesde: Date      // começo da barra: anda sozinha até a chegada e se acerta a cada posição
        var postoKm: Int?
        var postoEm: Date?
        var postoNome: String?
        var chuva: String?        // "daqui 25 min" | "chovendo, mais 12 km" | nil (some)
        var chuvaRotulo: String?  // "Chuva", "Neblina"...
        var posicaoEm: Date?

        enum CodingKeys: String, CodingKey {
            case faltaKm = "falta_km"
            case totalKm = "total_km"
            case barraDesde = "barra_desde"
            case postoKm = "posto_km"
            case postoEm = "posto_em"
            case postoNome = "posto_nome"
            case chuva
            case chuvaRotulo = "chuva_rotulo"
            case posicaoEm = "posicao_em"
        }
    }

    /// kind-ref-data (ex. "tarefa-12-2026-11-07"): mesmo compromisso = mesma atividade, só atualiza.
    var id: String
}

extension CompromissoAtributos.ContentState {
    /// O passo "agora" (último que já passou) no relógio do iPhone. -1 antes de começar.
    func atual(em agora: Date) -> Int {
        var i = -1
        for (n, p) in passos.enumerated() where p.em <= agora { i = n }
        return i
    }

    /// O próximo passo (o que a contagem mira); nil depois de chegar.
    func proximo(em agora: Date) -> CompromissoAtributos.Passo? {
        let i = atual(em: agora) + 1
        return i >= 0 && i < passos.count ? passos[i] : nil
    }

    func chegou(em agora: Date) -> Bool {
        !passos.isEmpty && atual(em: agora) >= passos.count - 1
    }

    var chegada: Date? { passos.last?.em }

    /// Tarefa com hora (sem saída): um passo só, "hora". Desenho próprio (AtividadeCompromisso.swift).
    var ehTarefa: Bool { passos.count == 1 && passos.first?.chave == "hora" }

    /// A hora da tarefa (ehTarefa).
    var horaTarefa: Date? { ehTarefa ? passos.first?.em : nil }

    /// Começo da barra/anel da tarefa: a janela de 2 h 30 antes da hora (TAREFA_JANELA_MIN no servidor).
    static let janelaTarefa: TimeInterval = 150 * 60

    /// Passou da hora (pedido do Alex, 06/11): a tarefa fica vermelha - o --perigo do app (#f47671).
    static let corPassou = "f47671"

    /// A tarefa já passou da hora e não foi feita? `velha` = o iOS marcou a atividade como velha (staleDate = a hora),
    /// que é quando ele redesenha sozinho, mesmo se o relógio do desenho anterior ainda estava antes da hora.
    func passouDaHora(em agora: Date, velha: Bool = false) -> Bool {
        guard ehTarefa, !estaFeito, let hora = horaTarefa else { return false }
        return hora <= agora || velha
    }

    /// Cor que vale agora: a do assunto, ou vermelho depois da hora da tarefa.
    func corAgora(em agora: Date, velha: Bool = false) -> String {
        passouDaHora(em: agora, velha: velha) ? Self.corPassou : cor
    }

    var estaFeito: Bool { feito == true }

    /// Viagem acompanhada (kind "viagem"): desenho próprio (AtividadeViagem.swift). Ela não "chega" pelo relógio:
    /// quem diz que chegou é o painel (posição perto do destino).
    var ehViagem: Bool { viagem != nil }

    /// Rótulo pequeno antes da contagem, no jeito D ("sai em", "arrumar em").
    static func rotuloContagem(_ p: CompromissoAtributos.Passo) -> String {
        switch p.chave {
        case "arrumar": return "arrumar em"
        case "sair": return "sai em"
        case "parada": return "parada em"
        case "hora": return "falta"
        default: return "chega em"
        }
    }

    /// "chegar 19:00 · 18° · 60%" (o tempo só quando houver).
    var linhaTempo: String {
        if ehTarefa || ehViagem { return "" }  // tarefa não "chega"; viagem tem linha própria
        var partes: [String] = []
        if let c = chegada { partes.append("chegar \(Self.hora(c))") }
        if let temp { partes.append("\(temp)°") }
        if let chuva, chuva > 0 { partes.append("\(chuva)%") }
        return partes.joined(separator: " · ")
    }

    private static let formatoHora: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "pt_BR")
        f.dateFormat = "HH:mm"
        return f
    }()

    static func hora(_ d: Date) -> String { formatoHora.string(from: d) }

    /// Começo seguro pra `Text(timerInterval:)`/`ProgressView(timerInterval:)`: o intervalo nunca pode
    /// ficar ao contrário (fim antes do começo derruba o app/widget).
    static func intervalo(de inicio: Date, ate fim: Date) -> ClosedRange<Date> {
        inicio <= fim ? inicio...fim : fim...fim
    }
}

// MARK: - Resposta de GET /api/ao-vivo

struct AoVivoResposta: Codable {
    struct Clima: Codable {
        let temp: Int?
        let chuva: Int?
    }

    let ativo: Bool
    let id: String?
    let titulo: String?
    let kind: String?
    let icone: String?
    let cor: String?
    let lugar: String?
    let passos: [CompromissoAtributos.Passo]?
    let atual: Int?
    let clima: Clima?
    let levar: [String]?
    let fimEm: Date?
    var tag: String? = nil
    var proximaTarefa: ProximaTarefa? = nil
    var acompanhar: Bool? = nil  // true: a posição do carro pode ir pro painel agora (viagem ou saída)
    var viagem: CompromissoAtributos.Viagem? = nil

    /// A próxima tarefa de hoje com hora (mesmo sem nada ao vivo): o widget da tela bloqueada mostra ela.
    struct ProximaTarefa: Codable, Hashable {
        let id: Int
        let titulo: String
        let em: Date
    }

    enum CodingKeys: String, CodingKey {
        case ativo, id, titulo, kind, icone, cor, lugar, passos, atual, clima, levar, tag, acompanhar, viagem
        case fimEm = "fim_em"
        case proximaTarefa = "proxima_tarefa"
    }

    static func decodificar(_ dados: Data) throws -> AoVivoResposta {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(AoVivoResposta.self, from: dados)
    }

    /// O estado da atividade, ou nil quando não tem compromisso (ou veio faltando coisa).
    var estado: CompromissoAtributos.ContentState? {
        guard ativo, let passos, !passos.isEmpty, let fimEm else { return nil }
        var hex = (cor ?? "f0a58f").trimmingCharacters(in: .whitespaces)
        if hex.hasPrefix("#") { hex.removeFirst() }
        return CompromissoAtributos.ContentState(
            titulo: titulo ?? "Compromisso",
            lugar: lugar,
            icone: icone ?? "mappin.and.ellipse",
            cor: hex.count == 6 ? hex : "f0a58f",
            passos: passos,
            atual: atual ?? -1,
            temp: clima?.temp,
            chuva: clima?.chuva,
            fim: fimEm,
            tag: tag,
            viagem: viagem
        )
    }

    /// Muda quando o compromisso muda de verdade (não a cada pergunta): o app só recarrega os widgets aí.
    var assinatura: String {
        // viagem: a chegada muda a cada posição - não recarrega os widgets por isso (orçamento do WidgetKit)
        let p = (viagem == nil ? (passos ?? []) : []).map { "\($0.chave)@\(Int($0.em.timeIntervalSince1970))" }
            .joined(separator: ",")
        let t = proximaTarefa.map { "\($0.id)@\(Int($0.em.timeIntervalSince1970))@\($0.titulo)" } ?? ""
        return "\(ativo)|\(id ?? "")|\(titulo ?? "")|\(p)|\(clima?.temp ?? -99)|\(clima?.chuva ?? -1)|\(t)"
    }
}

// MARK: - Pedido e cache (App Group)

enum AoVivoAPI {
    static let appGroupID = "group.com.alexxcgg.painel"  // igual a PainelConfig.appGroupID / Ajustes.appGroupID
    private static let chaveUltimo = "painel_aovivo_ultimo"
    private static let chaveAssinatura = "painel_aovivo_assinatura"
    private static let chaveAcompanharAte = "painel_aovivo_acompanhar_ate"
    /// Quanto tempo um "acompanhar" do painel vale sem confirmar de novo (o app pergunta a cada ~5 min dirigindo).
    static let acompanharValidade: TimeInterval = 20 * 60

    /// nil sem endereço ou sem token (nada vai pra rede).
    static func pedido(base: String?, token: String?) -> URLRequest? {
        guard var b = base?.trimmingCharacters(in: .whitespacesAndNewlines), !b.isEmpty,
              let t = token, !t.isEmpty else { return nil }
        while b.hasSuffix("/") { b.removeLast() }
        guard let url = URL(string: b + "/api/ao-vivo"), url.scheme?.hasPrefix("http") == true else { return nil }
        var pedido = URLRequest(url: url)
        pedido.httpMethod = "GET"
        pedido.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        pedido.timeoutInterval = 10
        return pedido
    }

    /// Busca e decodifica. nil em qualquer falha (sem rede, painel desligado, 401, JSON estranho).
    static func buscar(base: String?, token: String?) async -> AoVivoResposta? {
        guard let pedido = pedido(base: base, token: token) else { return nil }
        do {
            let (dados, resposta) = try await URLSession.shared.data(for: pedido)
            guard (resposta as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            let r = try AoVivoResposta.decodificar(dados)
            guardar(dados)
            definirAcompanhar(r.acompanhar == true)
            return r
        } catch {
            return nil
        }
    }

    private static var defaults: UserDefaults? { UserDefaults(suiteName: appGroupID) }

    static func guardar(_ dados: Data) {
        defaults?.set(dados, forKey: chaveUltimo)
    }

    /// Última resposta boa (o widget mostra ela quando a rede falha).
    static func ultimo() -> AoVivoResposta? {
        guard let dados = defaults?.data(forKey: chaveUltimo) else { return nil }
        return try? AoVivoResposta.decodificar(dados)
    }

    /// Viagem acompanhada: até quando o app pode mandar a posição do carro (nil/passado = não manda).
    static func acompanharAte() -> Date? {
        defaults?.object(forKey: chaveAcompanharAte) as? Date
    }

    static func definirAcompanhar(_ sim: Bool) {
        if sim {
            defaults?.set(Date().addingTimeInterval(acompanharValidade), forKey: chaveAcompanharAte)
        } else {
            defaults?.removeObject(forKey: chaveAcompanharAte)
        }
    }

    /// true quando a assinatura mudou desde a última vez (e grava a nova).
    static func mudou(_ r: AoVivoResposta) -> Bool {
        let nova = r.assinatura
        if defaults?.string(forKey: chaveAssinatura) == nova { return false }
        defaults?.set(nova, forKey: chaveAssinatura)
        return true
    }
}
