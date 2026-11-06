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
//  2026-11-06: tarefa com hora nas próximas 2 h 30 também (um passo só, "hora"). Ela não "chega": fica até o
//  fim (20 min depois da hora) e some, ou até o Feito (FeitoAoVivoIntent.swift), que mostra o check e some sozinho -
//  por isso atividade em estado "feito" nunca é derrubada aqui.
//
//  2026-11-06 (painel esperto, frente 3): viagem acompanhada (kind "viagem"). Ganha de tarefa e compromisso enquanto
//  está em andamento; atualiza a cada posição nova que o Localizacao.swift manda (em segundo plano: só LIGAR precisa
//  do app aberto). Não "chega" pelo relógio: quem diz que chegou é o painel (some quando ele para de mandar).
//  A resposta também traz `acompanhar` (AoVivoAPI guarda): se a posição do carro pode ir pro painel agora.
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
    private var deNovo = false  // pediram enquanto rodava (ex.: Feito logo depois de abrir): roda mais uma vez no fim
    private var tarefaFundo: UIBackgroundTaskIdentifier = .invalid

    private init() {}

    /// Chamar na main thread (abertura do app, volta/saída do app, recado da página, visita do Localizacao).
    func sincronizar() {
        guard AoVivoAPI.pedido(base: Ajustes.url, token: Ajustes.token) != nil else { return }
        if rodando {
            deNovo = true  // a resposta que está vindo pode ser de antes do Feito
            return
        }
        rodando = true
        deNovo = false
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
                if self.deNovo { self.sincronizar() }
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
            // nada nas próximas 6 h (ou já acabou): tira o que tiver (menos o check do Feito, que some sozinho)
            for atividade in atuais where !atividade.content.state.estaFeito {
                await atividade.end(nil, dismissalPolicy: .immediate)
            }
            recarregarWidgets(resposta)
            return
        }

        // tarefa fica até o fim (ou o Feito); viagem até o painel dizer que chegou (a chegada do relógio é estimativa)
        let chegou = estado.chegou(em: agora) && !estado.ehTarefa && !estado.ehViagem
        // viagem: velha se ficar 20 min sem posição nova (o iOS redesenha; a barra continua andando)
        let velhaEm = estado.ehViagem ? agora.addingTimeInterval(20 * 60) : (estado.proximo(em: agora)?.em ?? estado.fim)
        let conteudo = ActivityContent(state: estado, staleDate: min(velhaEm, estado.fim))
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
            } else if !atividade.content.state.estaFeito {
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
