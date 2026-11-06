# Leva 06/11 (2) - ao vivo de tarefa, Feito no ao vivo, widget com tarefa, aviso na hora

Pedido do Alex (06/11, depois de confirmar que o aviso local chegou): parar de instalar app a cada
mudança, juntar tudo e soltar UM `.ipa` no fim. Falta "aquela notificação ao vivo na tela de bloqueio".
Respostas dele:
- ao vivo "só as próximas 2 horas e 30 min e também com animações legais, assim, aquelas coisas que eu gosto";
- entra junto: **Feito no ao vivo**, **widget com tarefa**, **aviso na hora exata**.

## O que muda

1. **Ao vivo de tarefa** (`rotas/ao_vivo.py`): além do compromisso de saída/voo (6 h), a próxima tarefa
   de hoje com hora entra quando faltam até **150 min**. Fica até **20 min depois da hora** (se ele não
   marcar) e some. Um passo só, `{"chave": "hora"}`; `tag` = `tarefa_horario-<id>` pro botão.
   - Quem ganha quando tem os dois: o compromisso de saída se já começou (passou do 1º passo) ou se o
     1º passo dele vem antes da hora da tarefa; senão a tarefa.
   - Tarefa que já é compromisso de saída (local/parada/date/balada) segue no desenho de saída.
   - Refeição fica de fora (tem aviso próprio, sem cara de compromisso).
   - `proxima_tarefa` (sempre, mesmo sem nada ao vivo): a próxima tarefa com hora de hoje, pro widget.
2. **Desenho da tarefa ao vivo** (`AtividadeCompromisso.swift`, só animação que o iOS deixa:
   contagem e barra andam sozinhas, transição entre atualizações, nada de animação em loop):
   - tela bloqueada: ícone na cor, título, "às 14:30", contagem "falta 1:12:04" à direita; embaixo a
     barra que enche até a hora (`ProgressView(timerInterval:)`) e o botão **Feito**;
   - na hora: "agora" e o relógio contando o tempo desde a hora; a barra cheia; **tudo fica vermelho** (`--perigo`
     do app, #f47671 - pedido dele depois do protótipo); o check do Feito volta pro coral;
   - Feito: o miolo troca por um check grande na cor (entra com escala+fade), título riscado, e a
     atividade some sozinha em ~4 s;
   - ilha: compacta = ícone + contagem; mínima = anel que esvazia até a hora; expandida = tudo + Feito.
3. **Feito no ao vivo** (iOS 17, `LiveActivityIntent`, arquivo novo `FeitoAoVivoIntent.swift` nos dois
   alvos): marca a tarefa no painel (`POST /api/app/aviso/acao`, `feito`), troca o estado pra "feito" e
   encerra. Sem rede: a atividade volta ao normal (nada se perde, ele marca pelo app).
4. **Widget da tela bloqueada** (`ProximoCompromisso.swift`): sem saída/voo nem ao vivo, mostra a
   próxima tarefa com hora de hoje ("Separar os papéis · 14:30") em vez de "Nada pra sair nas
   próximas 6 h". O anel conta até a hora dela.
5. **Aviso na hora exata** (`avisos_app.py`): terceiro aviso local, `tarefa_agora`, na hora da tarefa
   ("⏰ <tarefa> / É agora."), com Feito/Adiar. Só pelo app (o servidor não manda esse pelo navegador).
   A repetição do `tarefa_horario` que cairia na mesma hora fica quieta quando o app agendou o
   `tarefa_agora` (conta como repetida, não toca dois). Liga/desliga em Assistente > Avisos.

## Decisões (pra ele vetar)
- 20 min depois da hora a atividade some sozinha (não fica pendurada a tarde toda).
- Tarefa ao vivo só HOJE; amanhã de madrugada não liga.
- Cor coral das tarefas (#f0a58f) e ícone de relógio.
- Ligar a atividade continua só com o app aberto (limite do iOS sem push da Apple); a partir daí ela anda
  sozinha. O app já sincroniza ao abrir/voltar, então abrir o app 1 vez nas 2 h 30 antes basta.

## Fora
- Ligar o ao vivo com o app fechado (precisa push da Apple, conta paga).
- Mais de uma tarefa ao vivo ao mesmo tempo.
