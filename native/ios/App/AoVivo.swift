//
//  AoVivo.swift
//  Gerente da atividade ao vivo do próximo compromisso (Dynamic Island + tela bloqueada) - 2026-11-04
//
//  Pergunta ao painel (GET /api/ao-vivo, token do widget guardado depois do PIN) qual é o próximo
//  compromisso de saída/voo das próximas 6 h e:
//    - liga a atividade (só com o app aberto: o iOS não deixa ligar em segundo plano);
//    - atualiza a que já existe (mesmo id) - passos, tempo, staleDate no próximo passo;
//    - encerra quando chegou (fica até o fim e some) ou quando o painel diz que não tem mais nada.
//  Sem push de APNs (conta grátis): roda quando o app abre/volta (PainelApp.swift) e quando o iOS acorda
//  o app por uma visita (Localizacao.swift). Entre uma coisa e outra a contagem anda sozinha no iPhone.
//
//  Sem endereço, sem token, sem rede ou painel desligado: não faz nada (nunca derruba o app).
//  Desenho: native/widgetkit/AtividadeCompromisso.swift. Dados: native/widgetkit/CompromissoAtributos.swift.
//

import ActivityKit
import Foundation
import UIKit
import WidgetKit

final class AoVivo {
    static let shared = AoVivo()

    private var rodando = false  // só mexido na main thread
    private var tarefaFundo: UIBackgroundTaskIdentifier = .invalid

    private init() {}

    /// Chamar na main thread (abertura do app, volta pro app, visita do Localizacao).
    func sincronizar() {
        guard !rodando, AoVivoAPI.pedido(base: Ajustes.url, token: Ajustes.token) != nil else { return }
        rodando = true
        let base = Ajustes.url
        let token = Ajustes.token
        // acordado por uma visita, o app tem poucos segundos: pede um tempinho pra terminar a conversa
        tarefaFundo = UIApplication.shared.beginBackgroundTask(withName: "painel-ao-vivo") { [weak self] in
            self?.terminarFundo()
        }
        Task {
            if let resposta = await AoVivoAPI.buscar(base: base, token: token) {
                await self.aplicar(resposta)
            }
            DispatchQueue.main.async {
                self.rodando = false
                self.terminarFundo()
            }
        }
    }

    private func terminarFundo() {
        guard tarefaFundo != .invalid else { return }
        UIApplication.shared.endBackgroundTask(tarefaFundo)
        tarefaFundo = .invalid
    }

    private func aplicar(_ resposta: AoVivoResposta) async {
        let agora = Date()
        let atuais = Activity<CompromissoAtributos>.activities

        guard let estado = resposta.estado, let id = resposta.id, estado.fim > agora else {
            // nada nas próximas 6 h (ou já acabou): tira o que tiver
            for atividade in atuais {
                await atividade.end(nil, dismissalPolicy: .immediate)
            }
            recarregarWidgets(resposta)
            return
        }

        let chegou = estado.chegou(em: agora)
        let conteudo = ActivityContent(state: estado, staleDate: estado.proximo(em: agora)?.em ?? estado.fim)
        var achou = false
        for atividade in atuais {
            let viva = atividade.activityState == .active || atividade.activityState == .stale
            if viva && !achou && atividade.attributes.id == id {
                achou = true
                if chegou {
                    // chegou: mostra "chegou" até o fim e some sozinha
                    await atividade.end(conteudo, dismissalPolicy: .after(estado.fim))
                } else {
                    await atividade.update(conteudo)
                }
            } else {
                // outro compromisso (mudou de plano) ou repetida: sai
                await atividade.end(nil, dismissalPolicy: .immediate)
            }
        }

        if !achou && !chegou && ActivityAuthorizationInfo().areActivitiesEnabled {
            do {
                _ = try Activity<CompromissoAtributos>.request(
                    attributes: CompromissoAtributos(id: id), content: conteudo, pushType: nil)
            } catch {
                // app em segundo plano (só liga com ele aberto) ou o iPhone recusou: tenta na próxima abertura
            }
        }
        recarregarWidgets(resposta)
    }

    /// Os widgets do compromisso só recarregam quando o compromisso mudou de verdade (orçamento do WidgetKit).
    private func recarregarWidgets(_ resposta: AoVivoResposta) {
        guard AoVivoAPI.mudou(resposta) else { return }
        WidgetCenter.shared.reloadTimelines(ofKind: "ProximoCompromisso")
        WidgetCenter.shared.reloadTimelines(ofKind: "PainelWidget")
    }
}
