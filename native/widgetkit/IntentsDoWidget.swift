//
//  IntentsDoWidget.swift
//  PainelWidget (WidgetKit extension) - 2026-11-05, leva dos widgets nativos
//
//  Os toques que funcionam sem abrir o app (widget interativo, iOS 17+): marcar/desmarcar tarefa no "Hoje" e
//  "+1 copo" na Água. Roda dentro da extensão, com o token dela (pareamento). Primeiro mexe no último payload
//  guardado, pra o widget redesenhar na hora quando o WidgetKit recarrega depois do perform; se o painel não
//  responder, desfaz a mudança (o widget volta ao que era). Rotas: rotas/widget_ios.py.
//  Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import AppIntents
import Foundation

@available(iOS 17.0, *)
struct MarcarTarefaIntent: AppIntent {
    static let title: LocalizedStringResource = "Marcar tarefa do painel"
    static let isDiscoverable = false

    @Parameter(title: "Tarefa")
    var tarefaID: Int

    @Parameter(title: "Feita")
    var feita: Bool

    init() {}

    init(tarefaID: Int, feita: Bool) {
        self.tarefaID = tarefaID
        self.feita = feita
    }

    func perform() async throws -> some IntentResult {
        let alvo = tarefaID
        let novo = feita
        PainelDados.mexerNoCache { json in Self.marcar(&json, id: alvo, feita: novo) }
        if await PainelDados.enviar("/api/widget/tarefa/\(alvo)", corpo: ["feita": novo]) == nil {
            PainelDados.mexerNoCache { json in Self.marcar(&json, id: alvo, feita: !novo) }
        }
        return .result()
    }

    private static func marcar(_ json: inout [String: Any], id: Int, feita: Bool) {
        guard var lista = json["hoje"] as? [[String: Any]] else { return }
        for i in lista.indices where (lista[i]["id"] as? Int) == id {
            lista[i]["feita"] = feita
        }
        json["hoje"] = lista
    }
}

@available(iOS 17.0, *)
struct MaisAguaIntent: AppIntent {
    static let title: LocalizedStringResource = "Mais um copo de água"
    static let isDiscoverable = false

    init() {}

    func perform() async throws -> some IntentResult {
        PainelDados.mexerNoCache { json in Self.somar(&json, 1) }
        if let r = await PainelDados.enviar("/api/widget/agua", corpo: [:]),
           let copos = r["copos"] as? Int {
            PainelDados.mexerNoCache { json in
                var agua = json["agua"] as? [String: Any] ?? [:]
                agua["copos"] = copos
                if let meta = r["meta"] as? Int { agua["meta"] = meta }
                json["agua"] = agua
            }
        } else {
            PainelDados.mexerNoCache { json in Self.somar(&json, -1) }
        }
        return .result()
    }

    private static func somar(_ json: inout [String: Any], _ n: Int) {
        guard var agua = json["agua"] as? [String: Any] else { return }
        agua["copos"] = max(0, (agua["copos"] as? Int ?? 0) + n)
        json["agua"] = agua
    }
}
