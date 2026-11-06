# Leva "avisos no app" (06/11/2026)

Pedido do Alex: "2 sim boa pode ligar gostei de todos. a apple nao derruba tambem." Ele escolheu a opção
2: o app nativo do iPhone dá um jeito de avisar sozinho, mesmo sem o push remoto da Apple (APNs), que
não existe na conta grátis. Junto vai o estilo de texto que ele votou no artefato "Avisos do Painel"
(doc `notificacoes/alex`): **C "Amigo" + 1 emoji por assunto**, cada aviso chegando sozinho, a repetição
com "De novo" como já é hoje e o tamanho do texto livre.

## O que muda

### 1. O app agenda os avisos que têm hora certa (aviso local, sem Apple no meio)
- `GET /api/app/avisos` (token do widget, só no header) devolve os avisos de hora conhecida de hoje e de
  amanhã: se arrumar, hora de sair, "daqui 15 min" e "5 min pra sair" dos compromissos de saída, o
  "faltam 30 min" e o "daqui a pouco" das tarefas com hora, e o "bora pro voo".
  - A conta é a mesma do servidor (`plano_se_arrumar`, `passos_da_saida`, `_saida_do_voo`).
  - Os textos saem dos mesmos geradores.
- O app apaga o que tinha agendado e agenda de novo (`UNTimeIntervalNotificationTrigger`). Depois conta
  pro painel o que ficou agendado (`POST /api/app/avisos/agendados`).
- **Sem aviso duplicado:** na hora de mandar o push do navegador, o servidor pula o aviso que o app
  agendou para aquele mesmo minuto (tolerância de 6 min). Isso só vale se o app sincronizou nas últimas 36 h.
  - Ele continua marcando o aviso como enviado.
  - A insistência ("De novo", "Última chamada") continua igual, pelo push do navegador. Ver memória
    "avisos não reduzir".
- Se o horário mudou e o app ainda não sincronizou, as horas não batem: o servidor manda pelo navegador
  como sempre. Na dúvida, o aviso sai.
- O que não tem hora marcada (gasto fora do padrão, conta da construtora, conversa do chat, tarefa
  parada...) continua só no push do navegador. O app não tem como saber disso antes.
- Na dúvida, o app não agenda e o servidor manda. Isso vale para:
  - tipo desligado em Assistente > Avisos;
  - hiperfoco que cobre o horário;
  - aviso que já saiu hoje.

### 2. Quando o app acorda pra sincronizar (tudo de graça)
- Quando o app abre, volta pra tela ou vai pro segundo plano (pega o que ele acabou de mudar no painel).
- Depois de tocar em Feito/Adiar na notificação.
- **Atualização em segundo plano** (`BGAppRefreshTask`, a cada ~30 min no mínimo; quem decide a
  frequência é o iOS).
- **Visita** (chegou/saiu de um lugar) e **mudança grande de lugar** (~500 m, com "Sempre").
- **GPS sempre ligado**: botão no Configurar, **desligado por padrão** porque gasta bateria. Ligado, o
  app fica vivo no segundo plano com GPS de baixa precisão e sincroniza a cada 5 min (avisos e ilha).

### 3. Botões e toque
- Os avisos de tarefa trazem **Feito** e **Adiar 1 h**, que vão para `POST /api/app/aviso/acao`. É a
  mesma lógica do `/api/push/acao`, só que com o token do widget.
- Tocar no aviso para a insistência (como `/api/push/aberto`) e abre a aba certa dentro do app.

### 4. Texto novo (estilo C + emoji), vale pro navegador também
- 🪞 Começa a se arrumar / 🚗 Bora, hora de sair / ⏰ tarefa com hora (título = a própria tarefa).
- 🍽️ Hora de comer / ✈️ Bora pro voo / 💧 Bora uma água? / 🧹 tarefa parada.
- ☀️ Bom dia / 🌙 Fecha o dia comigo?
- Os parentes próximos entram junto: 📅 compromisso da agenda, 🔒 inegociável.
- O emoji entra só na hora de mandar (`notificacoes.com_emoji`). O banco guarda o título sem ele. A
  repetição fica "⏰ De novo · Pagar a fatura".

## Decisões que o Alex pode vetar
1. Aviso sem hora marcada continua no navegador. Não dá pra prever, e sem APNs o app não recebe nada.
2. GPS sempre ligado começa desligado.
3. Hiperfoco que começa depois que o app já agendou não segura o aviso local até a próxima sincronização.
4. A repetição continua pelo navegador. O app só agenda o primeiro aviso.
5. Tarefa com hora ganha o próprio nome como título (no lugar de "Tá na hora"), porque a tela bloqueada
   mostra primeiro o título.

## Não faz
- Não mexe em quantos avisos saem nem quando, só em quem entrega e no texto.
- Nada de endereço no app nem no GitHub: o `.ipa` com endereço continua só local.
