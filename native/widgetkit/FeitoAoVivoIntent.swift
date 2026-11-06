//
//  FeitoAoVivoIntent.swift
//  Botão "Feito" dentro da atividade ao vivo da tarefa (tela bloqueada e ilha) - 2026-11-06
//  docs/briefings/2026-11-06-ao-vivo-tarefa.md
//
//  iOS 17+ (LiveActivityIntent). Entra nos DOIS alvos (project.yml): o iOS roda o perform() no processo do
//  app (por isso o app precisa do arquivo); o widget só precisa do tipo pro Button(intent:). No app
//  (PAINEL_APP, project.yml) usa o endereço e o token do app (AvisosLocais); no widget, se um dia o iOS rodar
//  aqui, usa o token do pareamento (PainelDados.enviar).
//
//  Ordem (otimista, igual aos cards do chat): o check aparece na hora -> POST /api/app/aviso/acao
//  {"tag": "tarefa_horario-<id>", "acao": "feito"} -> deu certo: a atividade termina mostrando o check e some
//  em FeitoAoVivo.someDepois; não deu (sem rede, painel desligado): volta ao normal, nada se perde.
//  Nunca loga token nem endereço. Não compilado aqui (sem Mac): o build é o do GitHub Actions.
//

import ActivityKit
import AppIntents
import Foundation
import WidgetKit

@available(iOS 17.0, *)
struct FeitoAoVivoIntent: LiveActivityIntent {
    static let title: LocalizedStringResource = "Marcar a tarefa ao vivo como feita"
    static let isDiscoverable = false

    @Parameter(title: "Atividade")
    var atividadeID: String

    @Parameter(title: "Aviso")
    var tag: String

    init() {}

    init(atividadeID: String, tag: String) {
        self.atividadeID = atividadeID
        self.tag = tag
    }

    func perform() async throws -> some IntentResult {
        await FeitoAoVivo.marcar(atividadeID: atividadeID, tag: tag)
        return .result()
    }
}

enum FeitoAoVivo {
    /// Quanto tempo o check fica na tela antes da atividade sumir.
    static let someDepois: TimeInterval = 4
    static let chaveResultado = "painel_aovivo_feito"  // "ok 14:02" / "falhou 14:02" (relatório do app)

    static func marcar(atividadeID: String, tag: String) async {
        let atividades = Activity<CompromissoAtributos>.activities.filter { $0.attributes.id == atividadeID }
        for atividade in atividades {
            var e = atividade.content.state
            e.feito = true
            await atividade.update(ActivityContent(state: e, staleDate: nil))
        }
        let ok = await enviar(tag: tag)
        for atividade in atividades {
            var e = atividade.content.state
            e.feito = ok
            if ok {
                await atividade.end(ActivityContent(state: e, staleDate: nil),
                                    dismissalPolicy: .after(Date().addingTimeInterval(someDepois)))
            } else {
                await atividade.update(ActivityContent(state: e, staleDate: e.proximo(em: Date())?.em ?? e.fim))
            }
        }
        guardarResultado(ok)
        if ok { depoisDoFeito() }
    }

    private static func guardarResultado(_ ok: Bool) {
        let f = DateFormatter()
        f.dateFormat = "dd/MM HH:mm"
        UserDefaults.standard.set("\(ok ? "ok" : "falhou") \(f.string(from: Date()))", forKey: chaveResultado)
    }

#if PAINEL_APP
    /// No app: endereço e token do app.
    private static func enviar(tag: String) async -> Bool {
        guard let base = AvisosLocais.base(),
              let pedido = AvisosLocais.pedido("/api/app/aviso/acao", base: base, corpo: ["tag": tag, "acao": "feito"]),
              let r = try? await URLSession.shared.data(for: pedido) else { return false }
        return (r.1 as? HTTPURLResponse)?.statusCode == 200
    }

    /// Tira os avisos que ficaram agendados pra tarefa e atualiza os widgets.
    private static func depoisDoFeito() {
        DispatchQueue.main.async {
            AvisosLocais.shared.sincronizar(motivo: "feito_ao_vivo")
            WidgetCenter.shared.reloadAllTimelines()
        }
    }
#else
    /// No widget: token do pareamento.
    private static func enviar(tag: String) async -> Bool {
        await PainelDados.enviar("/api/app/aviso/acao", corpo: ["tag": tag, "acao": "feito"]) != nil
    }

    private static func depoisDoFeito() {
        WidgetCenter.shared.reloadAllTimelines()
    }
#endif
}
