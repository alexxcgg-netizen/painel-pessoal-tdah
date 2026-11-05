//
//  PainelDados.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  O que todos os widgets da tela de início leem: o JSON de GET /api/widget (rotas/n3a_widget.py), o
//  pareamento por código quando ainda não tem token (rotas/widget_ios.py) e o cache do último payload bom.
//  Docs: docs/briefings/2026-11-05-widgets-ios.md. Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import Foundation

// MARK: - Modelo (Codable do contrato JSON)

enum EstadoPainel: String, Codable {
    case normal
    case vazio
    case erro
}

struct FocoAtual: Codable {
    let titulo: String
    let emMinutos: Int
    var hora: String? = nil

    enum CodingKeys: String, CodingKey {
        case titulo, hora
        case emMinutos = "em_minutos"
    }
}

struct ProximaConta: Codable {
    let nome: String
    let emDias: Int?

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

struct ComidaDoDia: Codable {
    let kcal: Double
    let proteinaG: Double
    let refeicoes: Int
    var metaProteinaG: Double? = nil

    enum CodingKeys: String, CodingKey {
        case kcal, refeicoes
        case proteinaG = "proteina_g"
        case metaProteinaG = "meta_proteina_g"
    }
}

struct ItemAgenda: Codable {
    let hora: String
    var fim: String? = nil
    let titulo: String
    let emMinutos: Int
    let tipo: String       // "compromisso" | "tarefa" | "habito"
    let concluido: Bool

    enum CodingKeys: String, CodingKey {
        case hora, fim, titulo, tipo, concluido
        case emMinutos = "em_minutos"
    }
}

struct AguaDoDia: Codable {
    let copos: Int
    let meta: Int
}

struct HorasVoo: Codable {
    let total: Double
    let meta: Double
}

struct TarefaHoje: Codable {
    let id: Int
    let titulo: String
    var hora: String? = nil
    let feita: Bool
    var atrasada: Bool? = nil
}

struct HoraDoVoo: Codable {
    let hora: String       // "7h"
    let codigo: Int        // código WMO
    let ventoKt: Int

    enum CodingKeys: String, CodingKey {
        case hora, codigo
        case ventoKt = "vento_kt"
    }
}

struct VooWidget: Codable {
    let data: String
    var hora: String? = nil
    let dia: String        // "hoje", "amanhã", "sábado"
    let origem: String
    var destino: String? = nil
    var condicao: String? = nil
    var vento: String? = nil
    var codigo: Int? = nil
    var horas: [HoraDoVoo]? = nil
}

struct PainelWidgetPayload: Codable {
    let versao: Int
    let atualizadoEm: Date
    let estado: EstadoPainel
    var foco: FocoAtual? = nil
    var proximaConta: ProximaConta? = nil
    var habitos: HabitosDoDia? = nil
    var custoIA: CustoIA? = nil
    var comida: ComidaDoDia? = nil
    var agenda: [ItemAgenda]? = nil
    var agua: AguaDoDia? = nil
    var horasVoo: HorasVoo? = nil
    var hoje: [TarefaHoje]? = nil
    var voo: VooWidget? = nil
    var linhas: [String] = []

    enum CodingKeys: String, CodingKey {
        case versao, estado, foco, habitos, comida, agenda, agua, hoje, voo, linhas
        case atualizadoEm = "atualizado_em"
        case proximaConta = "proxima_conta"
        case custoIA = "custo_ia"
        case horasVoo = "horas_voo"
    }

    static func decodificar(_ dados: Data) throws -> PainelWidgetPayload {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(PainelWidgetPayload.self, from: dados)
    }

    /// Dado inventado pra galeria de widgets e pro preview - nunca dado real.
    static let amostra = PainelWidgetPayload(
        versao: 1,
        atualizadoEm: Date(),
        estado: .normal,
        foco: FocoAtual(titulo: "Dentista", emMinutos: 40, hora: "14:30"),
        proximaConta: ProximaConta(nome: "Luz", emDias: 3),
        habitos: HabitosDoDia(feitos: 3, total: 5),
        comida: ComidaDoDia(kcal: 1840, proteinaG: 112, refeicoes: 3, metaProteinaG: 160),
        agenda: [
            ItemAgenda(hora: "14:30", fim: "15:15", titulo: "Dentista", emMinutos: 40, tipo: "compromisso", concluido: false),
            ItemAgenda(hora: "17:00", fim: "18:00", titulo: "Academia · peito", emMinutos: 190, tipo: "habito", concluido: false),
            ItemAgenda(hora: "18:45", fim: "19:00", titulo: "Date", emMinutos: 295, tipo: "tarefa", concluido: false),
        ],
        agua: AguaDoDia(copos: 5, meta: 8),
        horasVoo: HorasVoo(total: 96.5, meta: 150),
        hoje: [
            TarefaHoje(id: 1, titulo: "Banco", hora: "09:00", feita: true),
            TarefaHoje(id: 2, titulo: "Ligar pro mecânico", hora: "10:30", feita: true),
            TarefaHoje(id: 3, titulo: "Dentista", hora: "14:30", feita: false),
            TarefaHoje(id: 4, titulo: "Academia · peito", hora: "17:00", feita: false),
            TarefaHoje(id: 5, titulo: "Date", hora: "18:45", feita: false),
        ],
        voo: VooWidget(data: "2026-11-07", hora: "07:30", dia: "sábado", origem: "SSBL", destino: "SBJV",
                       condicao: "céu limpo", vento: "020° 8 kt", codigo: 0,
                       horas: [HoraDoVoo(hora: "6h", codigo: 0, ventoKt: 5), HoraDoVoo(hora: "7h", codigo: 0, ventoKt: 8),
                               HoraDoVoo(hora: "8h", codigo: 2, ventoKt: 9), HoraDoVoo(hora: "9h", codigo: 2, ventoKt: 11),
                               HoraDoVoo(hora: "10h", codigo: 3, ventoKt: 12), HoraDoVoo(hora: "11h", codigo: 3, ventoKt: 14)])
    )
}

// MARK: - O que o widget tem pra mostrar

enum Carga {
    case dados(PainelWidgetPayload)
    case parear(String)   // código de 4 números que o app confirma
    case erro(String)

    var payload: PainelWidgetPayload? {
        if case .dados(let p) = self { return p }
        return nil
    }
}

enum PainelDados {
    /// Os vários widgets pedem quase juntos: dentro de 90 s, o último payload serve pra todos.
    static let reusoSeg: TimeInterval = 90

    static func carregar() async -> Carga {
        guard PainelConfig.urlBase != nil else {
            PainelConfig.registrarBusca("sem_url")
            return cacheOu(.erro("Abre o app Painel uma vez"))
        }
        if PainelConfig.token == nil {
            switch await Pareamento.shared.passo() {
            case .pronto:
                break
            case .codigo(let codigo):
                PainelConfig.registrarBusca("pareando")
                return .parear(codigo)
            case .falhou(let mensagem):
                PainelConfig.registrarBusca("sem_token")
                return cacheOu(.erro(mensagem))
            }
        }
        if let c = PainelConfig.ultimoPayload(), Date().timeIntervalSince(c.em) < reusoSeg,
           let p = try? PainelWidgetPayload.decodificar(c.dados), p.estado != .erro {
            return .dados(p)
        }
        guard let pedido = PainelConfig.pedido("/api/widget") else {
            return cacheOu(.erro("Abre o app Painel uma vez"))
        }
        do {
            let (dados, resposta) = try await URLSession.shared.data(for: pedido)
            let status = (resposta as? HTTPURLResponse)?.statusCode ?? 0
            if status == 401 {
                // token trocado no painel: some daqui e o widget pede um código novo na próxima vez
                PainelConfig.guardarToken(nil)
                PainelConfig.registrarBusca("http_401")
                return cacheOu(.erro("Abre o Painel pra liberar de novo"))
            }
            guard (200...299).contains(status) else {
                PainelConfig.registrarBusca("http_\(status)")
                return cacheOu(.erro("Painel respondeu com erro"))
            }
            let p = try PainelWidgetPayload.decodificar(dados)
            if p.estado == .erro {
                PainelConfig.registrarBusca("payload_erro")
                return cacheOu(.erro(p.linhas.first ?? "Painel com problema agora"))
            }
            PainelConfig.salvarUltimoPayload(dados)
            PainelConfig.registrarBusca("ok")
            return .dados(p)
        } catch {
            PainelConfig.registrarBusca("rede_\((error as NSError).code)")
            return cacheOu(.erro("Sem conexão com o painel"))
        }
    }

    /// O último payload bom (de qualquer idade) ou a alternativa.
    static func cacheOu(_ alternativa: Carga) -> Carga {
        if let p = cache() { return .dados(p) }
        return alternativa
    }

    static func cache() -> PainelWidgetPayload? {
        guard let c = PainelConfig.ultimoPayload(),
              let p = try? PainelWidgetPayload.decodificar(c.dados), p.estado != .erro else { return nil }
        return p
    }

    /// Pareando: de minuto em minuto (o app ainda recarrega na hora que libera). Erro: 5 min. Normal: 20 min.
    static func proximaAtualizacao(_ carga: Carga, agora: Date = Date()) -> Date {
        switch carga {
        case .parear: return agora.addingTimeInterval(60)
        case .erro: return agora.addingTimeInterval(5 * 60)
        case .dados: return agora.addingTimeInterval(20 * 60)
        }
    }

    // MARK: - Toque dentro do widget (IntentsDoWidget.swift)

    /// POST com o token. nil em qualquer falha.
    static func enviar(_ caminho: String, corpo: [String: Any]) async -> [String: Any]? {
        guard let pedido = PainelConfig.pedido(caminho, metodo: "POST", corpo: corpo),
              let r = try? await URLSession.shared.data(for: pedido),
              (r.1 as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return (try? JSONSerialization.jsonObject(with: r.0)) as? [String: Any]
    }

    /// Mexe no último payload guardado, pra o widget redesenhar na hora com o toque (o cache vale 90 s).
    static func mexerNoCache(_ mudar: (inout [String: Any]) -> Void) {
        guard let c = PainelConfig.ultimoPayload(),
              var json = (try? JSONSerialization.jsonObject(with: c.dados)) as? [String: Any] else { return }
        mudar(&json)
        if let novo = try? JSONSerialization.data(withJSONObject: json) {
            PainelConfig.salvarUltimoPayload(novo)
        }
    }
}

// MARK: - Pareamento por código (rotas/widget_ios.py)

/// Um pedido de cada vez, mesmo com vários widgets pedindo juntos (todos rodam no mesmo processo).
actor Pareamento {
    static let shared = Pareamento()

    enum Passo {
        case pronto
        case codigo(String)
        case falhou(String)
    }

    private var emAndamento: Task<Passo, Never>?

    func passo() async -> Passo {
        if let tarefa = emAndamento { return await tarefa.value }
        let tarefa = Task { await self.fazer() }
        emAndamento = tarefa
        let resultado = await tarefa.value
        emAndamento = nil
        return resultado
    }

    private func fazer() async -> Passo {
        if PainelConfig.token != nil { return .pronto }
        if let id = PainelConfig.parId {
            guard let r = await json(PainelConfig.pedido("/api/widget/parear/\(id)", comToken: false)) else {
                if let codigo = PainelConfig.parCodigo { return .codigo(codigo) }
                return .falhou("Sem conexão com o painel")
            }
            switch r["estado"] as? String {
            case "liberado":
                guard let token = r["token"] as? String, token.count >= 8 else { return .falhou("Painel mandou um token estranho") }
                PainelConfig.guardarToken(token)
                PainelConfig.limparPar()
                return .pronto
            case "esperando":
                if let codigo = r["codigo"] as? String {
                    PainelConfig.parCodigo = codigo
                    return .codigo(codigo)
                }
            case "sem_token":
                return .falhou("Falta o token no painel")
            default:
                break  // expirou: pede outro abaixo
            }
            PainelConfig.limparPar()
        }
        let id = UUID().uuidString
        guard let r = await json(PainelConfig.pedido("/api/widget/parear", metodo: "POST", corpo: ["id": id], comToken: false)),
              let codigo = r["codigo"] as? String else {
            return .falhou("Sem conexão com o painel")
        }
        PainelConfig.parId = id
        PainelConfig.parCodigo = codigo
        return .codigo(codigo)
    }

    private func json(_ pedido: URLRequest?) async -> [String: Any]? {
        guard let pedido, let r = try? await URLSession.shared.data(for: pedido),
              let status = (r.1 as? HTTPURLResponse)?.statusCode, (200...299).contains(status) else { return nil }
        return (try? JSONSerialization.jsonObject(with: r.0)) as? [String: Any]
    }
}
