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

import ActivityKit
import Foundation

struct CompromissoAtributos: ActivityAttributes {
    struct Passo: Codable, Hashable {
        var chave: String   // "arrumar" | "sair" | "parada" | "chegar"
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

    /// Rótulo pequeno antes da contagem, no jeito D ("sai em", "arrumar em").
    static func rotuloContagem(_ p: CompromissoAtributos.Passo) -> String {
        switch p.chave {
        case "arrumar": return "arrumar em"
        case "sair": return "sai em"
        case "parada": return "parada em"
        default: return "chega em"
        }
    }

    /// "chegar 19:00 · 18° · 60%" (o tempo só quando houver).
    var linhaTempo: String {
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

    enum CodingKeys: String, CodingKey {
        case ativo, id, titulo, kind, icone, cor, lugar, passos, atual, clima, levar
        case fimEm = "fim_em"
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
            fim: fimEm
        )
    }

    /// Muda quando o compromisso muda de verdade (não a cada pergunta): o app só recarrega os widgets aí.
    var assinatura: String {
        let p = (passos ?? []).map { "\($0.chave)@\(Int($0.em.timeIntervalSince1970))" }.joined(separator: ",")
        return "\(ativo)|\(id ?? "")|\(titulo ?? "")|\(p)|\(clima?.temp ?? -99)|\(clima?.chuva ?? -1)"
    }
}

// MARK: - Pedido e cache (App Group)

enum AoVivoAPI {
    static let appGroupID = "group.com.alexxcgg.painel"  // igual a PainelConfig.appGroupID / Ajustes.appGroupID
    private static let chaveUltimo = "painel_aovivo_ultimo"
    private static let chaveAssinatura = "painel_aovivo_assinatura"

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

    /// true quando a assinatura mudou desde a última vez (e grava a nova).
    static func mudou(_ r: AoVivoResposta) -> Bool {
        let nova = r.assinatura
        if defaults?.string(forKey: chaveAssinatura) == nova { return false }
        defaults?.set(nova, forKey: chaveAssinatura)
        return true
    }
}
