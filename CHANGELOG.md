# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

<!-- indice:inicio (gerado por scripts/indice_changelog.py - nao editar a mao) -->
## Índice (ler isto primeiro)

Uma linha por entrada, mais nova em cima. Achou o assunto: busque o título (aqui embaixo ou no
arquivo do histórico indicado) e leia só aquela entrada.

- 2026-11-06 - Painel mais esperto: aba Tarefas nova, viagem com posto, GPS, onde estou, voo na véspera
- 2026-11-06 - Tarefa ao vivo na tela bloqueada, Feito no ao vivo e aviso na hora exata
- 2026-11-06 - Avisos no app do iPhone (sem push da Apple) e texto novo dos avisos
- 2026-11-06 - App do iPhone mostra qual versão está instalada
- 2026-11-05 - Leva "agentes": revisor das respostas, preparo do dia de madrugada, contexto que não engole a me…
- 2026-11-05 - Resposta do chat não some mais quando sai do app (SW v103)
- 2026-11-05 - Leva "perfeição": app abre do cache, chat começa antes, verificador mais leve (SW v102)
- 2026-11-05 - Widgets nativos do iPhone, pareamento por código e ícone mostrador (SW v101)
- 2026-11-05 - Conversa de 04/11: lugar do date, hora de sair, tarefa com hora, temperatura da noite
- 2026-11-04 - Cards ao vivo (D), assistente passo a passo, Dynamic Island e widgets (SW v100)
- 2026-11-04 - Pista de SSBL é 01/19 e protótipo dos cards sem cara de IA (SW v99)
- 2026-11-04 - Chat: lugares pelo nome e 3 burrices da conversa de 03/11
- 2026-11-04 - Onde eu estou: o painel sabe quando ele chega e sai de um lugar
- 2026-11-01 - Chat começa com limite de 12 mil tokens: fim da resposta refeita
- 2026-11-01 - Fim do teto padrão de R$ 40 da IA (SW v98)
- 2026-10-31 - Suíte em ~1 min 30 s: faltava porta, não era PC lento
- 2026-10-30 - Testes mais rápidos: banco modelo, só o afetado, cópia separada
- 2026-10-30 - Agenda do iCloud com cache de 60 s (primeiro relatório real do app iOS)
- 2026-10-30 - App iOS: abre configurado (endereço local + token depois do PIN)
- 2026-10-30 - App iOS: tela "Gerar relatório" e teste da Dynamic Island
- 2026-10-30 - Laboratório v4: os "quero" no app (SW v97)
- 2026-10-30 - Treino ao vivo em 3D de verdade: 215 exercícios (SW v96)
- 2026-10-22 - App iOS nativo (.ipa) com widget, build no GitHub Actions
- 2026-10-22 - Leva "painel mais esperto" (SW v93+)
- 2026-10-21 - Carga × sono no treino (SW v92)
- 2026-10-21 - Animação 3D do exercício no treino ao vivo (SW v91)
- 2026-10-21 - Chat dá baixa pelo que ele conta
- 2026-10-21 - Gráfico de carga no card de troca (SW v90)
- 2026-10-21 - Treino ao vivo: ficha com caixinhas + troca de carga pelo chat (SW v89)
- 2026-10-21 - Chat mais humano: balão que vira card + dois planos (SW v88)
- 2026-10-21 - Tempo trecho a trecho na rota + "vai chover depois de lavar o carro" (SW v87)
- 2026-10-20 - Vistoria: servidor saturando (fila do Waitress)
- 2026-10-18 - Memória sob demanda + correções que o chat mostrou
- 2026-10-17 - Aviso que insistia mesmo com o app aberto (SW v86)
- 2026-10-16 - Despertador pedido no chat + relatório do painel + registro de erros (SW v85)
- 2026-10-16 - Raiz do projeto limpa + mapa no AGENTS.md
- 2026-10-16 - CHANGELOG com índice no topo + setembro arquivado
- 2026-10-16 - Barra que sumia com medida impossível + horário solto + título de depois (SW v84)
- 2026-10-15 - Trânsito de verdade + Waze nos cards (SW v83)
- 2026-10-15 - Barra de abas: medida pelo ancoradouro de verdade (SW v82)
- 2026-10-15 - Microfone, barra de abas e o que o chat mostrou (SW v81)
- 2026-10-15 - 4ª leva: mais automação (véspera do voo, despertador, aeroclube, compras, documentos, projeção)
- 2026-10-14 - Cards da IA no app (3ª leva: volta, "pensando", tempo do voo, horas, presente anual)
- 2026-10-14 - Cards da IA no app (2ª leva: date, balada, tabelionato, presente)
- 2026-10-14 - Cards da IA no app (1ª leva: voo, gasto, alteração, concluir, aperto)
- 2026-10-14 - Cards da IA: protótipo aprovado + aprendizado guardado
- 2026-10-14 - Campo e barra no meio da tela (de novo) + card "Alterado" letra por letra
- 2026-10-14 - Cards da IA conversam com a aba Tarefas
- 2026-10-14 - Tarefa não duplica mais; conversa por voz "tipo ChatGPT"
- 2026-10-14 - Tarefa atrasada ganha "pra hoje"
- 2026-10-13 - Avisos que insistem, "Ei Siri, pergunta pro painel" e bugs do print do Alex
- 2026-10-13 - Aba Tarefas vira linha do tempo
- 2026-10-13 - Cards do chat "premium": profundidade, montagem e toque
- 2026-10-13 - Suíte de testes de ~28 min pra ~6 min + bug do iPhone ao voltar pro app
- 2026-10-13 - Painel puxando assunto: fechar o dia e padrões da semana
- 2026-10-13 - Professor de aviação 2: quiz da banca com repetição espaçada
- 2026-10-13 - Aba Tarefas em ordem de horário
- 2026-10-13 - Professor de aviação 1: briefing meteorológico no chat
- 2026-10-13 - Cards interligados (vários assuntos, um fio só)
- 2026-10-13 - Chat AO VIVO + jeito de falar de gente
- 2026-10-13 - Prova de qualidade do chat (`scripts/eval_chat/`)
- 2026-10-13 - Backup automático diário do banco
- 2026-10-13 - Cards do chat: acabamento "premium"
- 2026-10-13 - Voz fala hora/número/sigla certo + chat responde com substância
- 2026-10-09 - Chat mais esperto + voz de verdade (Roberta) + modo conversa
- 2026-10-13 - Widget do iPhone: próximo compromisso + comida do dia
- 2026-10-13 - Voz com barulho em volta, botão de mandar na hora, feriados e foto do prato
- 2026-10-12 - Diário de cada dia: o chat sabe o que foi hoje e o que já passou
- 2026-10-12 - Áudio do chat igual ChatGPT/Gemini: "posso errar que ele entende"
- 2026-10-11 - Excluir tarefa arrastando pro lado (sem concluir)
- 2026-10-11 - Transcrição: corta o eco da lista de vocabulário
- 2026-10-11 - Assistente de vida: "acordei agora, monta meu dia"
- 2026-10-11 - Notificações de verdade + "hora de se arrumar"
- 2026-10-10 - Card da Construtora: 4 números prontos + "Ademir paga"
- 2026-10-10 - Trilha do dia (a "assinatura" das tarefas)
- 2026-10-10 - IA reajusta tarefa sozinha + "tarefa criada" mostra o dia
- 2026-10-10 - Notificações de verdade (service worker na raiz) + cartões de tarefa caprichados
- 2026-10-10 - Notificações ligadas e sempre visíveis
- 2026-10-10 - Transcrição mais fiel + cartão vivo de tarefas
- 2026-10-10 - Voz da Roberta: rápida e sem travar
- 2026-10-09 (tarde) - IA que edita + cartões vivos
- 2026-10-08 - Chat passa para o Claude Haiku 5.5
- 2026-10-08 - Preços do Claude Haiku 5.5 na tabela de custos
- 2026-10-08 - Chat: consulta de voos, gasto por nome e tarefas sem hora (exame de alucinação)
- 2026-10-02 - Tarefas: "Ver mais"
- 2026-10-02 - Restos da reformulação: skeleton, Tomei / Feito hoje, acentos
- 2026-10-01 - Reformulação, etapa 3: acabamento das telas internas
- 2026-10-01 - Reformulação, etapa 2: Início e IA com conteúdo novo
- 2026-10-01 - Reformulação, etapa 1: esqueleto novo (aprovado pela prévia "preto gelo")

**Arquivadas em `docs/historico/CHANGELOG-2026-09.md`:**

- 2026-09-30 - Painel e Vida sólidos + animações mais fluidas
- 2026-09-29 - Troca de aba mais rápida (Tarefas, Gastos, Vida, Painel)
- 2026-09-29 - IA responde só com dados do painel
- 2026-09-29 - Correção de testes no Windows e Linux
- 2026-09-28 - Voz natural (ElevenLabs v4 Turbo) só pra frases curtas
- 2026-09-26/27 - Limpeza: acentos, Finanças com uma lista, app.py e style.css divididos, abas e animações
- 2026-09-26 - Velocidade, cor "Gelo preto" e animações
- 2026-09-26 - Auditoria de uso real (desempenho + categoria duplicada)
- 2026-09-25 - Melhorias de uso diário (M1–M5)
- 2026-09-25 - Redesenho visual da tela de login/PIN
- 2026-09-25 - Fase 9: volta ao painel antigo (pedido do dono), só Finanças nova
- 2026-09-25 - Fase 9 (Etapa C, parte 3): polimento final
- 2026-09-25 - Fase 9 (Etapa C, parte 2): Hoje, Finanças e Vida no estilo Conversa
- 2026-09-25 - Fase 9 (Etapa C, parte 1): visual "Conversa" e 4 abas
- 2026-09-25 - Fase 9 (Etapa A): Finanças numa aba só, sincronização sem duplicar
- 2026-09-25 - Fase 8: visual dark + financeiro/banco unificado
- 2026-09-24 - Modo teste de IA
- 2026-09-24 - Fase 7 (v12): IA híbrida, visual novo, assinaturas e parcelas, assistente proativo
- 2026-09-24 (Fase 7, Etapa 0 / X1) - extracao estrutural do backend
- 2026-09-24 (Fase 7, X2) - frontend dividido por secao (so estrutura)
- 2026-09-23 (Fase 6) - correcoes da revisao independente (codigo + seguranca)
- 2026-09-23 (Fase 6 F1) - polimento da aba Vida
- 2026-09-23 (Fase 6 F2) - polimento do Painel e prazo em Tarefas
- 2026-09-23 (Fase 6 F3) - Viagens (linha do tempo + status de voo), mapa, Cotacoes e Aviacao
- 2026-09-23 (Fase 6 E4) - chat produzindo cards dos modulos novos
- 2026-09-23 (Fase 6 E5) - proatividade unificada e visao do dia
- 2026-09-23 (Fase 6 E2) - modulos Habitos, Projetos, agenda no iCloud e limite do cartao
- 2026-09-23 (Fase 6 E3) - contrato de cards (Padrao Nectar)
- 2026-09-23 (Fase 6 E1) - bugs, memoria visivel e estilo de resposta
- 2026-09-23 (32) - Deploy de teste no Render (plano gratis)
- 2026-09-23 (31) - Fase 5: correcoes da revisao independente (codigo + seguranca)
- 2026-09-23 (30) - Fase 5 Grupo D: polimento visual
- 2026-09-23 (29) - Fase 5 Grupo B: navegacao por voz (best-effort) + offline
- 2026-09-23 (28) - Fase 5 Grupo A: nucleo do classificador de intent
- 2026-09-23 (26) - Fase 5, Grupo C1: historias independentes (US-C1 a US-C7)
- 2026-09-23 (27) - Fase 5 Grupo C (independentes, agente c3): US-C15 a US-C22
- 2026-09-23 (25) - Fase 4: resiliencia, backup e seguranca
- 2026-09-23 (24) - Correcoes da revisao independente da Fase 3
- 2026-09-23 (23) - Fechamento do BRIEFING: guia de Atalhos e credenciais
- 2026-09-23 (22) - Correcoes da revisao independente da Fase 2
- 2026-09-23 (21) - BRIEFING.md Fase 3 (dinheiro, crescimento, burocracia)
- 2026-09-23 (20) - BRIEFING.md Fase 2 + correcoes da revisao da Fase 1
- 2026-09-23 (19) - BRIEFING.md Fase 1: rotina guiada, check-in, hiperfoco, so o essencial, pessoas
- 2026-09-22 (18) - Hidratacao, peso/medidas corporais e correlacao sono x produtividade
- 2026-09-22 (17) - Medicamentos: cadastro estruturado (nome/dosagem/horario) com lembrete
- 2026-09-22 (16) - Tarefa recorrente (diaria/semanal) - remedio, academia, rotina
- 2026-09-22 (15) - Polish final: card de resultado no "devo sair" e dias restantes nas datas importantes
- 2026-09-22 (14) - Assistente proativo: avisa antes, distribui a semana, puxa tarefa quando ocioso
- 2026-09-22 (13) - Agenda com bolinhas verde/vermelha, saldo nos bancos, diario de bordo do voo, rainbow v2
- 2026-09-22 (12) - Fisica de toque de verdade (causa real do "barato") + efeito rainbow
- 2026-09-22 (11) - Rodada de animacoes: ritmo humano no chat, transicao de aba direcional, erro com entrada
- 2026-09-22 (10) - Remove de vez o "negocinho preto" acima do chat (raiz, nao sintoma)
- 2026-09-22 (9) - Fix: barrinha preta flutuando acima do chat (residuo de blur esquecido)
- 2026-09-22 (8) - Decisao final de tema: preto puro + neutro, vidro so na barra + 4 fixes
- 2026-09-22 (7) - Fix do bloco preto atras do campo de chat + laboratorio de estilos no artefato
- 2026-09-22 (6) - Liquid Glass round 6 (transparencia de verdade, removida a mancha branca)
- 2026-09-22 (5) - Liquid Glass round 5 (qualidade do material + barra flutuante) + artefato com testador de co…
- 2026-09-22 (4) - Liquid Glass colorido em (quase) tudo + achado real de CSS
- 2026-09-22 (3) - Loop noturno (ciclo 1): Liquid Glass v2 + palavra surgindo no chat
- 2026-09-22 (2) - Saldo bancario antes/depois + Notas com tags + auditoria de deploy
- 2026-09-22 (1) - "Liquid Glass" nos paineis + pesquisa de concorrentes (Nectar, Pierre, Zapia, Luzia, Base44)
- 2026-09-21 (11) - Noticias sob demanda (Google News RSS) + confirmado que Saude ja conecta
- 2026-09-21 (10) - Cobranca generica (Apple) identificavel pelo chat + gastos fixos enxergam o banco
- 2026-09-21 (9) - Assistente financeiro de verdade + botao de acao no Telegram
- 2026-09-21 (8) - Colar trecho exportado do WhatsApp no chat
- 2026-09-21 (7) - Aprendizado bem mais profundo, 100% por tras das cameras
- 2026-09-21 (6) - Aprendizado de padrao pessoal + catch-up de fim do dia
- 2026-09-21 (5) - Bot do Telegram + 3 features de "funcionario particular"
- 2026-09-21 (4) - De app de rotina pra assistente: 4 features de proatividade
- 2026-09-21 (3) - Nova identidade: fonte Sora + esmeralda/ametista
- 2026-09-21 (2) - Polimento visual a partir do feedback do Alex
- 2026-09-21 - Contas a pagar da construtora, auditoria noturna de qualidade
- 2026-09-20 - Gráficos técnicos e paleta final
- 2026-09-19 - Deploy real, login, gráficos, identidade visual
- 2026-09-18 - Chat vira o centro do app, integrações externas
- 2026-09-17 - Estrutura inicial (v1)
<!-- indice:fim -->

## 2026-11-06 - Painel mais esperto: aba Tarefas nova, viagem com posto, GPS, onde estou, voo na véspera
Pedido do Alex antes do `.ipa`: "quero algo mais, espero mais, realmente um assistente". Briefing com respostas,
decisões e vetos: `docs/briefings/2026-11-06-painel-esperto.md`. Protótipo aprovado (dados inventados):
https://claude.ai/artifact/WXSEtwp14Y1UwGEc86TYTX (v1 -> v2 com o card de rota com mapa, pedido dele -> v3 com
"Mais esperto"). Feito em 5 frentes em paralelo; SW v104 (mesmo bump da leva do ao vivo). Cenas em `docs/CARDS.md`.

- **Aba Tarefas nova** (`static/js/secoes/tarefas/tarefas.js`, `linha-do-tempo-tarefas.js`, `folha-tarefa.js`,
  `tarefas.css`, `templates/secoes/tarefas/tarefas.html`): lista estilo Ajustes por grupo (Atrasadas / Manhã /
  Tarde / Noite / Sem hora / Amanhã / dias seguintes), caixinha 44 px que marca feito, toque abre a folha (dia,
  hora, nome, Feito, Apagar e os extras que a tarefa já tinha), régua do dia com chuva (`/api/clima/hoje`) e
  arrastar de 15 em 15 min; tudo com Desfazer. Rotas `POST /api/tasks/<id>/mover` e `/titulo`
  (`rotas/tarefas_acoes.py`). Mudar hora/dia de saída (date, balada, tarefa com lugar) refaz o "sai às" pela mesma
  função do chat (`app.replanejar_saida`, usada também pelo `ajustar_tarefa` e pela `/hora` antiga).
- **Viagem planejada** (`viagem_planejada.py`, tool `planejar_viagem`, card `viagem` em `cards-viagem.js`): card de
  rota com mapa + chuva/lento/posto por cima, 3 saídas comparadas (trocar não chama API), postos ao longo da rota
  abertos na hora que passa (Places searchAlongRoute), paradas pela autonomia, noite, Maps/Waze. Tabelas `veiculo`,
  `abastecimentos`, `viagens_planejadas`; `combustivel.py` + tool `registrar_abastecimento` (consumo real de
  tanque cheio a tanque cheio; tanque sempre "estimativa"). XC40 com 49 L (dito por ele; "acho que é 49"). Rota comum nunca ganha
  posto (veto dele); trânsito do card de rota calculado pra hora real de saída. Cota: `posto_rota` 600,
  `horario_lugar` 300, e as buscas que escapavam passam a contar.
- **GPS do iPhone** (`Localizacao.swift` reescrito, `viagem_acompanhada.py`, `rotas/localizacao_viagem.py`):
  cercas (até 20, `GET /api/localizacao/cercas`) que mandam chegada/saída pela rota da visita (`fonte: "cerca"`),
  Movimento (dirigindo liga o GPS de estrada sozinho), viagem acompanhada (`POST /api/localizacao/posicao` só
  dirigindo e com viagem/compromisso ativo; posições apagadas no fim), ao vivo da viagem (`AtividadeViagem.swift`,
  kind `viagem` no `/api/ao-vivo`, ganha de tarefa/compromisso). Conserto: desligar o botão não parava o GPS.
- **Onde estou** (`onde_vou.py`, `diario_lugares.py`, `rotas/onde_vou.py`, `cards-onde.js`): "Indo pro X?" ao sair
  perto da hora de uma saída, diário do dia (só lugar e tempo, no fechamento e em `consultar_diario`), tempos reais
  (mediana das últimas 6 saídas, a partir de 3, só adianta, até 30 min; "Meu tempo / Padrão"), recado de atraso com
  texto pronto e link do WhatsApp (nunca manda sozinho). Cerca + visita do mesmo lugar viram uma estadia só.
- **Mais esperto** (`voo_vespera.py`, `rotinas_esperto.py`, `hora_certa.py`, `rotas/esperto.py`,
  `cards-esperto.js`): voo decidido na véspera (20h e 06:30; voa / no limite / não dá; TAF de SBNF pro SSBL; nunca
  inventa quando o TAF não cobre), rotina descoberta (3 semanas), tarefa adiada 3 vezes (passos / mudar o dia /
  apagar), pergunta na hora certa (chegou em casa depois das 18h; saiu da academia sem treino). Avisos novos só se
  somam aos de hora fixa. Fila única de avisos de evento: aviso local do app com botão Amanhã (`painel-casa`) e push
  como reserva sem duplicar; `indo_pra`/`atraso_recado` também pelo app.
- Testes novos: `test_tarefas_acoes`, `test_tarefas_aba_nova`, `test_viagem_planejada`, `test_viagem_acompanhada`,
  `test_onde_vou`, `test_esperto`, JS `cards_viagem`, `cards_onde`, `cards_esperto`, `tarefas_linha_do_tempo`.
  Checagens novas no `native/ios/checar_projeto.py`. Swift não compila aqui: o build do `.ipa` é a prova.

## 2026-11-06 - Tarefa ao vivo na tela bloqueada, Feito no ao vivo e aviso na hora exata
Pedido do Alex depois do aviso local funcionar: juntar tudo num `.ipa` só em vez de instalar a cada mudança, e
"aquela notificação ao vivo na tela de bloqueio" pra tarefa, "só as próximas 2 horas e 30 min" e com animação.
Escolheu junto: Feito no ao vivo, widget com tarefa e aviso na hora exata. Briefing com as decisões:
`docs/briefings/2026-11-06-ao-vivo-tarefa.md`. Protótipo (dados inventados):
https://claude.ai/artifact/Ffcd6UiKMiNR4ZLFZqMYyv. Do PWA, só o aviso pro app em `nucleo/api.js` (SW v104).

- **Ao vivo de tarefa** (`rotas/ao_vivo.py`): a próxima tarefa de hoje com hora entra quando faltam até 150 min
  (`TAREFA_JANELA_MIN`) e fica até 20 min depois da hora (`TAREFA_DEPOIS_MIN`). Um passo só (`"hora"`), cor coral,
  ícone de relógio, `tag` = `tarefa_horario-<id>` pro botão. Compromisso de saída ganha se já começou ou se o 1º
  passo dele vem antes da hora da tarefa. Fora: feita, refeição (`Comer: ...`), modelo de repetida, arquivada,
  tarefa que já é de saída (segue o desenho de saída). `proxima_tarefa` vai junto sempre que houver (pro widget).
- **Desenho** (`native/widgetkit/AtividadeTarefa.swift`, ligado em `AtividadeCompromisso.swift` por `ehTarefa`):
  contagem "falta" até a hora e "agora" contando desde a hora, barra que enche nas 2 h 30
  (`ProgressView(timerInterval:)`), botão Feito; ilha compacta (ícone + contagem), mínima (anel que esvazia) e
  aberta. Feito: check que cresce e assenta, título riscado, some em 4 s. Só animação que o iOS deixa (nada em loop).
  Passou da hora sem Feito: tudo que é da cor da tarefa fica vermelho (`--perigo` do app, #f47671; pedido dele);
  vale também quando o iOS marca a atividade como velha na hora (`isStale`). O check do Feito volta pro coral.
- **Feito no ao vivo** (`native/widgetkit/FeitoAoVivoIntent.swift`, iOS 17, `LiveActivityIntent` nos dois alvos):
  mostra o check na hora, `POST /api/app/aviso/acao` (`feito`), encerra; sem rede volta ao normal. O app usa o
  próprio token (`#if PAINEL_APP`, flag nova no `project.yml`); resultado no relatório (`aovivo_feito`).
  `AoVivo.swift` não derruba atividade em estado "feito" e não encerra tarefa na hora (fica até o fim).
  Feito/Adiar pelo aviso também atualiza o ao vivo.
- **Widget da tela bloqueada** (`ProximoCompromisso.swift`): sem saída/voo ao vivo, mostra a próxima tarefa com
  hora (título, "Às 14:30", quanto falta; anel nas 3 h antes) antes do voo. Texto vazio virou "Nada com hora por hoje".
- **Aviso na hora exata** (`avisos_app.py`): `tarefa_agora` ("⏰ <tarefa> / Deu 14:30, é agora. Quando terminar,
  toca em Feito."), com Feito/Adiar, só pelo app. Segue o hiperfoco do `tarefa_horario`. A repetição do
  `tarefa_horario` que cairia na mesma hora fica quieta quando o app agendou o `tarefa_agora` (conta como repetida).
  Mexer no "é agora" para a insistência do aviso de tarefa. Liga/desliga em Assistente > Avisos.
- `native/ios/checar_projeto.py` 5c: `LiveActivityIntent` nos dois alvos e `PAINEL_APP` só no app.
- Testes: `tests/test_ao_vivo.py` (`TarefaAoVivoTest`), `tests/test_avisos_app.py` (`EAgoraSemDuplicarTestCase` e
  os de `tarefa_agora`).
- **Bug (print dele, 05:06): marcou Feito/Desfazer no painel dentro do app e a ilha continuou.** O app só conferia
  o ao vivo ao abrir/voltar pro app; escrita feita na própria página não chegava. Agora `nucleo/api.js`
  (`avisarAppNativo`) manda "mudou" pelo canal `window.webkit.messageHandlers.painel` depois de qualquer escrita
  (junta as seguidas em 0,8 s); o app (`PainelApp.swift`, `AvisoDaPagina`, só do host do painel) confere o ao vivo e
  os avisos na hora. Também confere o ao vivo ao ir pro segundo plano, e `AoVivo.sincronizar` pedido no meio de
  outro roda de novo no fim (a resposta em voo podia ser de antes do Feito). No Safari/PWA o canal não existe e
  nada muda. SW v104. Checagem 5d no `checar_projeto.py`; teste `tests/js/avisar_app_nativo.test.js`.
- Contagem da ilha compacta cortava com mais de 1 h ("2:23:..."): espaço 52 -> 64 pt, fonte 13.
- No caso do print: a tarefa das 7:30 estava aberta no painel e houve um Desfazer às 05:06; se o Desfazer foi o
  do Feito dela, a ilha mostrava o estado certo (o Desfazer reabre). Não deu pra confirmar qual tarefa foi desfeita.

## 2026-11-06 - Avisos no app do iPhone (sem push da Apple) e texto novo dos avisos
Pedido do Alex ("2 sim boa pode ligar gostei de todos"): o app nativo avisa sozinho, mesmo sem o push remoto da
Apple (APNs), que a conta grátis não tem. Junto, o texto que ele votou no artefato "Avisos do Painel": estilo C
"Amigo" + 1 emoji por assunto. Briefing com as decisões: `docs/briefings/2026-11-06-avisos-app.md`. Sem JS/CSS,
então sem bump do SW. O app novo só vale depois de um `.ipa` novo.
- **O app agenda os avisos de hora conhecida** (`avisos_app.py`, `rotas/avisos_app.py`, `AvisosLocais.swift`):
  - O app agenda aviso local pro dia de hoje e de amanhã: se arrumar, hora de sair, "daqui 15 min", "5 min pra sair",
    o "faltam 30 min" e o "daqui a pouco" das tarefas com hora, e o "bora pro voo".
  - A conta e o texto são os mesmos do servidor. O iPhone toca mesmo com o app fechado e o PC desligado.
  - Rotas: `GET /api/app/avisos`, `POST /api/app/avisos/agendados` e `POST /api/app/aviso/acao` (Feito, Adiar 1 h,
    toque). Todas usam o token do widget, só no header.
- **Sem aviso duplicado:** o servidor não manda pelo navegador o que o app agendou pro mesmo minuto (folga de 6 min,
  app sincronizado nas últimas 36 h).
  - O aviso continua contado como enviado, e a insistência segue pelo navegador.
  - Se a hora mudou e o app não sincronizou, as horas não batem e o navegador avisa como sempre.
- **Quando o app acorda:**
  - abre, volta, sai, ou toca Feito/Adiar;
  - atualização em segundo plano (`BGAppRefreshTask`, ~30 min, quem decide é o iOS);
  - visita ou mudança grande de lugar;
  - "GPS sempre ligado" (Configurar, desligado por padrão): o app fica acordado e confere a cada 5 min.
  - `project.yml`: `UIBackgroundModes` [fetch, location] e `BGTaskSchedulerPermittedIdentifiers`.
  - `checar_projeto.py` confere os dois.
- **Texto novo** (vale pro navegador também):
  - 🪞 Começa a se arrumar, 🚗 Bora, hora de sair, ⏰ tarefa com hora (com o nome da tarefa no título), 🍽️ Hora de
    comer, ✈️ Bora pro voo, 💧 Bora uma água?, 🧹 E "tarefa"?, ☀️ Bom dia, 🌙 Fecha o dia comigo?
  - Tudo com "tu".
  - O emoji entra só na hora de mandar (`notificacoes.com_emoji`), e a repetição fica "⏰ De novo · …".
  - `_saida_do_voo` separado de `_aviso_voo_sair` (o app usa a mesma conta).
  - `rotas/push.py` ganhou `executar_acao` e `registrar_toque`, que a rota do app reaproveita.
- Relatório do app: agendados, próximo, última conferida, quantas vezes acordou em segundo plano, GPS.
- Widgets recarregam quando o app sai da tela, e também quando a lista de avisos mudou em segundo plano. Antes, a
  tarefa criada no chat só aparecia no widget na próxima busca dele, que o iPhone controla.
- Testes: `tests/test_avisos_app.py` (23), e os testes de texto antigo atualizados.

## 2026-11-06 - App do iPhone mostra qual versão está instalada
O Alex instalou o `.ipa` de 05/11 e a galeria seguiu mostrando o widget de 04/11; não dava pra saber daqui qual versão
estava no iPhone (o relatório saía igual nas duas).
- `build-ios.yml`: cada build sai com número novo (`CURRENT_PROJECT_VERSION` = número da rodada) e com
  `PAINEL_BUILD` = "dd/mm hh:mm · commit". Com tudo "1", instalar por cima deixava a galeria de widgets velha.
- App: "Versão: …" no rodapé de Configurar (`PainelApp.swift`) e `app_build` no "Gerar relatório" (`Relatorio.swift`).
- `project.yml`: `PainelBuild` no Info.plist do app e do widget (build local mostra "local").

## 2026-11-05 - Leva "agentes": revisor das respostas, preparo do dia de madrugada, contexto que não engole a mensagem
Pedido do Alex depois da pesquisa sobre agentes ("pode seguir com tudo"). Briefing com a pesquisa, as medições e as
decisões: `docs/briefings/2026-11-05-agentes.md`. Sem JS/CSS: sem bump do SW.
- **Contexto que engolia a mensagem** (`ia/funcoes/chat.py`, `SUFIXO_CONTEXTO_AGORA`): à noite o bloco "Contexto de
  agora" vem cheio e o modelo respondia a ele, ignorando o pedido (um voo contado à noite não era gravado). O bloco
  agora fecha dizendo que a mensagem seguinte é a que vale. 4 de 4 variantes da frase passaram a gravar (antes 2).
- **Revisor** (`ia/revisor_chat.py`, só código): confere hora de sair/de se arrumar contra o cálculo da ferramenta,
  saída que já passou, conta de intervalo, tempo de trajeto contra a rota e "anotei" sem ferramenta que grava. Achou:
  o modelo refaz a resposta 1 vez com o certo (nas contas, sem chamar ferramenta de novo). Fecho de robô no fim
  ("Se quiser, ...") sai no código. Log `revisor do chat: ...` no servidor. `tests/test_revisor_chat.py` (29).
- **Preparo do dia** (`app.preparar_dia`, 5h30 e 7h05): essenciais e resumo do dia prontos antes de acordar; resumo
  busca construtora e tempo em paralelo (`rotas/resumo.py`, `resumo_do_dia`). `tests/test_preparar_dia.py` (6).
- **Roteador** (`ia/roteador_chat.py`): "o que tu acha", planejar/reorganizar o dia vão pro modelo de conversa;
  `e_continuacao` mantém o modelo numa pergunta curta logo depois de uma conversa.
- **Eval** (`scripts/eval_chat/`): troca de modelo por rodada (`--modelo-registro`/`--modelo-conversa`), expectativas
  velhas corrigidas, 2 casos novos, juiz lê a nota pelo nome do campo, pasta temporária não derruba mais a rodada.
- Teste ajustado: `test_fase7_a6_chat` usava "Registrei tudo." sem ferramenta, que o revisor agora (com razão) refaz.

## 2026-11-05 - Resposta do chat não some mais quando sai do app (SW v103)
Relato do Alex (print): mandou uma mensagem longa (voz) e saiu do app; ao voltar não havia resposta, nem
a de uma segunda pergunta. O banco mostrou que a IA respondeu e gravou as duas. Causa: o iOS congela ou derruba
a conexão do `/api/chat/stream` quando o app vai pro segundo plano; o servidor termina e grava, mas o app só
sincronizava os cards na volta e deixava os pontinhos (ou "a conexão caiu") sem ir buscar a resposta.
- `chat.js`: `chatAoVivo` devolve `CHAT_CAIU` (conexão perdida, mensagem pode ter chegado) em vez de erro e
  **nunca reenvia** (reenviar duplicaria a mensagem). Na volta ao app, se o stream ficou mudo por 2,5 s ele é
  abortado. `recuperarRespostaGravada` consulta `/api/chat/historico` (até ~90 s, a IA ainda pode estar
  pensando), acha a mensagem enviada e, havendo resposta depois dela, redesenha a conversa parada. Sem nada
  gravado, avisa em vez de ficar parado. Se o app sai antes de o stream abrir, também não reenvia.
- Teste novo `tests/test_chat_resposta_gravada.py` (4 casos: stream sem "fim", stream congelado + sair/voltar,
  nada gravado, resposta antiga não vale); sem a correção os 4 falham.
- SW v103.

## 2026-11-05 - Leva "perfeição": app abre do cache, chat começa antes, verificador mais leve (SW v102)
Pedido do Alex antes de dormir (tempo de resposta, IA, verificador, animação; "não me pergunte nada"). Briefing com
as medições e as decisões: `docs/briefings/2026-11-05-perfeicao.md`.
- **Medido antes:** as 131 rotas GET somam ~650 ms (`tests/medir_tempos.py`, cópia do banco de verdade): o servidor
  não era o gargalo. Abrir o app puxava ~220 arquivos revalidados um a um (no-cache + SW rede-primeiro); o waitress
  engasgava no minuto da abertura (764 "queue depth" + 75 "connection limit" de 02 a 04/11).
- **`estaticos.py` (novo):** `/static/...` da página com `?v=<impressão>` + immutable de 1 ano, `fase7.css` com o `?v`
  de cada camada, `X-Versao` em toda resposta de /static/, gzip de texto (página 185 KB → 31 KB). Nunca derruba a
  resposta. **SW v102:** versionado com `X-Versao` igual sai do cache; uma cópia por arquivo; precache 8 por vez;
  `Range` fica com o navegador. `tests/medir_abertura.py` (80 ms de latência, sem SW como o app nativo):
  **2ª abertura 2,5 s → 0,31 s**, 1ª 3,3 s → 2,6 s.
- **Chat:** iCloud, construtora e tempo saem juntos em `_contexto_chat` (antes ~4-5 s em fila antes da IA);
  `POST /api/chat/aquecer` (foco no campo ou microfone, 1 vez a cada 30 s) deixa agenda e construtora no cache.
- **Animação:** carrinho do "Já saí" (card D) por `transform` com `100cqw` em vez de `left`/`width` (mesmo pixel).
- **Verificador:** r1/r2/anim2/volta_segundo_plano com um Chromium por classe (contexto novo por teste),
  `networkidle` trocado por `esperar_carga`, r2 sem a espera fixa de 900 ms (conta o timer de verdade), Geocode sem o
  sleep do throttle. Arquivo sozinho: r2 51→42 s, r1 44→34, anim2 41→25, volta 32→20, r3 38→34.
- Testes: `tests/test_estaticos.py`, `tests/test_contexto_chat_paralelo.py`; `test_service_worker_real.py` confere
  que nada versionado vai à rede depois de recarregar. Proposta não feita: fila rápida sem xdist (briefing).

## 2026-11-05 - Widgets nativos do iPhone, pareamento por código e ícone mostrador (SW v101)
Votos do Alex no artefato "Widgets e ícone" (rodada 2): todos os widgets, todos os da tela bloqueada, StandBy, ícone
"mostrador". Briefing com as decisões: `docs/briefings/2026-11-05-widgets-ios.md`.
- **"Configure a URL do painel no app" resolvido:** a assinatura grátis corta o App Group. Endereço agora vai também
  dentro da extensão (`scripts/ipa_com_endereco.py`); token chega por **pareamento por código** (`rotas/widget_ios.py`:
  `/api/widget/parear*`, 3 abertos, 12/h, 10 min, token entregue uma vez) + alerta "Liberar este widget?" no app
  (`native/ios/App/ParearWidget.swift`).
- **`/api/widget`** ganhou `agua`, `horas_voo`, `hoje`, `voo` (vento do Open-Meteo, `clima.vento_horario`, cache 30 min)
  e `fim` na agenda. Toques: `POST /api/widget/tarefa/<id>` e `POST /api/widget/agua`.
- **Widgets (Swift reescrito):** Próximo, Proteína, Dia, Voo, Hoje (caixinha), Água (+), Horas, Conta; medidores de
  proteína e horas na tela bloqueada; retângulo "Sair às 18:45 / lugar · N min de carro"; linha com o próximo voo.
  Arquivos: `PainelDados.swift`, `PainelEstilo.swift`, `Widgets{Corpo,Dia,Voo}.swift`, `IntentsDoWidget.swift`.
- **Ícone mostrador:** `scripts/icone_mostrador.py` (PWA escuro; iOS claro/escuro/tingido no `AppIcon.appiconset`).
- Testes: `tests/test_widget_ios.py`, `tests/test_ipa_com_endereco.py`. Swift só compila no GitHub Actions
  (`native/ios/checar_projeto.py` passa).

## 2026-11-05 - Conversa de 04/11: lugar do date, hora de sair, tarefa com hora, temperatura da noite
Briefing: `docs/briefings/2026-11-05-conversa-04-11.md`. Testes: `tests/test_conversa_0411.py`.
- **Lugar contado depois** vai pra `tasks.local`: `ajustar_tarefa` ganhou `lugar` e `com_quem` e recalcula o plano
  (antes o lugar ia só pro título e a saída ficava com os 15 min de casa).
- **Hora de sair** (coluna nova `tasks.sai_na_hora`, migração `202611050100`): "saio de casa às 19" = sai na hora e
  chega hora + ida. Vale nos avisos (`notificacoes.plano_se_arrumar`), na ilha/widgets (`tempo.compromissos`), no
  card D (`chegada`) e no que a IA diz (`chega_no_lugar`). Campo `sai_na_hora` em registrar/ajustar.
- **Tarefa com dia ganha hora** (regra do prompt trocada; a velha deixava sem hora a tarefa "solta").
- **`consultar_clima` de outro dia** traz `hora_a_hora` (temperatura + chuva de cada hora; `clima.hora_a_hora_texto`).
- **Quem é quem** vira memória (regra nova; a de memória dizia "raro" e nada entrava desde 08/10).

## 2026-11-04 - Cards ao vivo (D), assistente passo a passo, Dynamic Island e widgets (SW v100)
O Alex aprovou as 3 rodadas do D: "gostei de tudo". Também pediu: "se for atualizar o app já coloca pra ele usar o dynamic
island e widgets". Briefing: `docs/briefings/2026-11-04-cards-ao-vivo.md`. Saiu em 3 frentes paralelas, cada uma com seus
próprios arquivos.
- **Cards D (PWA)** — `cards-d.js` e `cards-d.css`, ambos novos.
  - Pílula escura que abre no toque, com mola `cubic-bezier(.32,1.2,.42,1)`. A contagem vem em segundos do servidor e
    os dígitos rolam tipo placar.
  - **Sai a cara de IA:** fio de luz na borda, luz que segue o dedo, inclinação 3D, selo brilhante, chips com emoji,
    título em degradê e MAIÚSCULAS espaçadas.
  - **Cenas:**
    - tarefa com hora: contagem, "Já saí" e "+10 min";
    - date/balada: cadeia arrumar → sair → (parada) → chegar, tempo em 7 colunas com chegada/volta e o que levar com o
      motivo;
    - voo: seletor por aeródromo, cabeceira/proa/través só na pista conferida (SSBL), teto/vis/vento e METAR;
    - gasto (anel do teto) e tarefa feita (anel em pedaços + lista do dia);
    - lugar salvo, um type novo;
    - chegou: a hora rola da velha pra nova;
    - conta única: "deslize se já pagou".
  - `cards.py` monta `cadeia`, `clima_horas` e `levar`. `clima.py` passou a dar a temperatura na previsão hora a hora.
    Testes: `tests/test_cards_d.py` e `tests/js/cards_d.test.js`.
- **Assistente passo a passo** — migração `202611041100_as_parada_tarefa.sql` com `tasks.parada`.
  - Várias saídas numa frase só: prompt novo, um `registrar_tarefa` por compromisso.
  - **Parada no caminho:** casa → parada (5 min lá) → destino. `tempo.compromissos` expõe
    `parada = {"nome", "min_ate"}`.
  - **Sequência de avisos:**
    1. `saida_preparo`: daqui ~15 min começa a se arrumar, com o tempo e o que levar;
    2. `se_arrumar`;
    3. `saida_porta`: 5 min pra sair, com o que levar;
    4. `hora_de_sair`: "10 min até casa do guri";
    5. a chegada na parada ou no destino, pelo `onde_estou`.
  - **Previsão que piora:** se a chuva na chegada sai de < 70% e vai pra ≥ 70%, adianta a saída 10 min uma vez e
    avisa.
  - Teste: `tests/test_assistente_saida.py`.
- **iPhone** — rota nova `GET /api/ao-vivo`.
  - **Acesso:** só com o token Bearer do widget no header, nunca na URL. Devolve o próximo compromisso de saída ou voo
    das próximas 6 h, com os passos em ISO, a cor/ícone do assunto e o clima na chegada. O lugar aparece só pelo apelido.
  - **Live Activity / Dynamic Island de verdade:** `CompromissoAtributos`, `AtividadeCompromisso`, e `AoVivo.swift` no
    app. É local, sem APNs (a conta é grátis): o app liga, atualiza e encerra a atividade quando abre, quando chega o
    token e a cada visita do CLVisit. A contagem `Text(timerInterval:)` anda sozinha.
  - **Widgets:** o da tela inicial mostra o próximo compromisso. O "Próximo compromisso" novo vai pra tela bloqueada nos
    formatos rectangular, circular e inline.
  - `checar_projeto.py` ganhou 2 checagens. **Nada disso foi compilado ainda:** só o build do GitHub confirma.
- **Consertos de quem fechou a leva:**
  - `rotas/aviacao_lab.py`: o card "vento" recebia a data no lugar do ICAO.
  - O card de saída ignora a cópia da parada em `extras` quando a coluna `tasks.parada` foi limpa (pelo Desfazer).
  - Os dois com teste.

## 2026-11-04 - Pista de SSBL é 01/19 e protótipo dos cards sem cara de IA (SW v99)
- **Pista:** o Alex confirmou que as cabeceiras de SSBL são **01/19**. O padrão antigo, 18/36, vinha de fonte de terceiros e
  estava errado. Mudou `aviacao_lab.PISTA_PADRAO`, o texto da fonte e o reserva do front
  (`cards-aviacao-lab.js`). A cabeceira agora aparece sempre com 2 dígitos ("01"), no card, no desenho da pista e na linha
  do bom-dia (`linha_vento`). A declinação (~20,6° W) continua "não conferida". Os testes foram ajustados para a conta nova:
  290 V a 12 kt dá través de 10 kt na 01. Também entraram teste do padrão e teste JS dos 2 dígitos.
- **Cards sem cara de IA (só protótipo, nada no app):** o artefato https://claude.ai/artifact/HG3Kq8ZjWrgCUfHCHLiFvh
  tem 5 caminhos. O Alex votou no **D (Ao vivo)**: card como atividade ao vivo do iPhone, pequeno no chat, que abre com
  um toque e conta o tempo. Do card atual ele quer manter o tempo (temperatura, casaco, chuva) em date e balada.
  - **Rodada 2:** date e balada com o tempo hora a hora, o que levar e a saída ajustada se a previsão piorar.
  - **Rodada 3:** a sequência de avisos na tela bloqueada (se arrumar → sair → casa do guri → chegar) e o voo com teto,
    vento e cabeceira por aeródromo.
  - Espera o veredito dele antes de ir pro app. O que dá cara de IA, segundo o diagnóstico: brilho correndo na borda, luz
    seguindo o dedo, selo aceso, chips com emoji, título em degradê, MAIÚSCULAS espaçadas e o "pensando" com órbita.

## 2026-11-04 - Chat: lugares pelo nome e 3 burrices da conversa de 03/11
- **Lugares que ele ensina** (regra nova no prompt): "a oficina é a Fulano", "a Celesc é no centro" → `salvar_lugar_apelido`
  na hora, um por lugar. Só o nome basta: `exec_salvar_lugar_apelido` procura no Google (`maps_client.resolver_lugar`,
  viés em Brusque) e guarda "Nome, endereço"; não achou = guarda como ele falou e devolve `obs`. `esquecer=true` tira
  (`vida_assistente.esquecer_apelido`). Lugar de uma vez (balada) usa o nome do lugar como apelido, nunca "balada".
- **A caminho não é feito**: "vim trazer o carro" não dá baixa; "ainda não deixei" reabre na mesma rodada.
- **Horário de "quando chegar em casa"** nunca antes da chegada (conta paradas + `estimar_trajeto`).
- **Hora sem dia**: `ajustar_tarefa` que dá hora a tarefa sem `due_date` põe ela em hoje (antes ficava fora do dia e
  não chamava na hora).
- Texto da manhã: "1 coisa que ficou solta" (era "1 coisa que ficaram soltas"). Teste de recomeço com relógio fixo.

## 2026-11-04 - Onde eu estou: o painel sabe quando ele chega e sai de um lugar
Briefing: `docs/briefings/2026-11-04-onde-eu-estou.md`. O app iOS manda as visitas do iPhone
(`startMonitoringVisits`, permissão "Sempre") pra `POST /api/localizacao/visita` (token do widget só no header;
sem token/errado = 401, visitante = 403). Lógica em `onde_estou.py`, rota em `rotas/onde_estou.py`, tabela `visitas`
(migração `202611041000_loc_visitas.sql`, 30 dias, coordenada com 4 casas).
- **Lugar:** apelidos (`lugares_apelidos`) + casa (`ENDERECO_CASA`), geocodificados uma vez (config `lugares_coordenadas`;
  falha só tenta de novo no dia seguinte). Raio 150 m (visita imprecisa estica até 250 m). Salvar apelido pelo chat já geocodifica.
- **Chegou:** uma mensagem por visita no chat + push/Telegram: "Chegou no mecânico. Agora é: ... Depois: ... às 11h."
  Só fala se tiver tarefa do lugar ou próxima com hora; chegada com mais de 45 min (fila offline) não avisa.
- **Atrasou:** visita aberta (passo de 5 min em `conversa_proativa.verificar`) ou saída há até 30 min: se agora + trajeto
  (Maps, cache de 20 min, só pra tarefa em até 2 h) passa da hora por mais de 10 min, empurra ela e as seguintes de hoje
  (arredondado pra 5 min, o "(até HH:MM)" do título junto). Inegociável e voo são parede. Card `edicao` com Desfazer.
  Uma vez por tarefa por dia. Destino: `local` da tarefa, apelido no título, senão casa.
- **Chat:** contexto ganha "Agora (pelo iPhone): no mecânico desde 07:20" / "saiu de casa às 07:05" (até 2 h).
- **iPhone:** `native/ios/App/Localizacao.swift` (fila de até 50 no UserDefaults, envio em background task, seção
  "Onde eu estou" no Configurar). Não compilado aqui: build pelo `build-ios.yml`.

## 2026-11-01 - Chat começa com limite de 12 mil tokens: fim da resposta refeita
44 de 214 chamadas do chat com Haiku bateram no limite (500 ou 1.000), foram descartadas e refeitas, perdendo de 3 a 6 s cada.
`ia/config.d/chat.json` agora começa em 12.000, no Haiku e na rota `conversa`. A escada 500 -> 4.000 -> 12.000 ficou só pro caso de
config quebrada. O Alex decidiu que custo não importa aqui. Ganho estimado de 15% a 25% do tempo de IA, ainda não medido depois.

## 2026-11-01 - Fim do teto padrão de R$ 40 da IA (SW v98)
Pedido do Alex: tirar o teto de gastos. Sem nada configurado, o gasto agora só é medido: nada bloqueia nem avisa
(`ia.teto.TETO_PADRAO_BRL = 0`, caminho de "sem teto" que já existia em `_fracao_teto`). O teto opcional do card financeiro
continua funcionando igual, e hoje não há nenhum configurado.
- **Card Custo de IA:** sem teto, some a barra e o "% do teto usado". Ficam o gasto, a projeção, o gráfico e a tabela.
- **Widget:** sem teto, `custo_ia` volta `null` em vez de "IA: 0% do teto".
- **Testes:** os da lógica de 80%/100% agora configuram um teto próprio; entrou teste de gasto alto sem teto liberando tudo.

## 2026-10-31 - Suíte em ~1 min 30 s: faltava porta, não era PC lento

Medido: a fila do navegador somava 17.436 conexões em TIME_WAIT, acima das 16.384 portas de saída do Windows, e cada uma
fica presa 30 s neste PC (`TcpTimedWaitDelay`). Duas fontes: o servidor do Flask fecha a conexão a cada pedido (~250 por
página) e o `cache.addAll` do service worker abre uma por arquivo (222). O sintoma era script que não carregava e falha em
teste diferente a cada rodada (`ERR_ADDRESS_IN_USE`, `xxx is not defined`).
- `subir_servidor` em `tests/playwright_helper.py`: waitress nos testes, igual ao painel. `test_servidor_de_teste.py`
  impede a volta do `app.run`.
- Service worker bloqueado por padrão nos testes; `test_service_worker_real.py` instala ele de verdade, confere `ASSETS` e
  recarrega a página com ele no comando.
- `scripts/testes.py`: um pytest por arquivo no navegador, 5 de cada vez, o mais pesado primeiro; portas abaixo de 49152;
  quem só passa sozinho aparece em `so passou sozinho`; limite de 300 s por arquivo e 600 s por fila; testes JS juntos.
- `scripts/testes_afetados.py`: rota pela URL, arquivo citado com a pasta, aviso quando nada liga com o que mudou.
- `test_vel_a2b`: cronômetro dentro da página, do `pointerdown` até o quadro; erro lento e linha que volta inteira.
- Não rodar duas suítes juntas: os relatórios de `data/testes/` têm nome fixo. `unittest discover` saiu do `CLAUDE.md` e do
  `README.md`: não carrega o `conftest.py`, então fica sem rede fechada e sem banco modelo.
Resultado: 11 min -> 63 a 96 s, e 0 ou 1 teste passando só no refazer por rodada (antes 3 a 8). Pico de ~900 conexões.
Rodadas finais, já com tudo acima: 73, 68 e 73 s, nenhum refeito. 19 de 19 quebras de propósito pegas pelos testes.
Detalhes: `docs/testes.md` e `docs/briefings/2026-10-30-testes-rapidos.md`.

## 2026-10-30 - Testes mais rápidos: banco modelo, só o afetado, cópia separada

Medido: `init_db` 330 ms, cópia 0,4 ms; toda página dos testes de navegador perdia 3,3 s repetindo a IA morta.
`tests/banco_modelo.py` troca `init_db` nos testes por cópia de um modelo feito pelo `init_db` real (com testes de
igualdade em `tests/test_banco_modelo.py`); o `conftest.py` tira as repetições da IA; `scripts/testes_afetados.py` escolhe
os testes pela mudança; `scripts/testes.py` roda numa cópia temporária do código pra dar pra seguir mexendo.
Pegadinha: outro trabalho pesado no PC multiplica o tempo (mesmo teste de 3 s pra 38 s) e gera falha falsa de animação.
Medido com o PC ainda ocupado (11 min -> 8 min 44 s): rápida 9 min -> 1 min 52 s, grandes 5 min 48 s -> 26 s,
navegador 11 min -> 8 min 36 s. O gargalo agora é só o navegador. Detalhes em `docs/testes.md`.

## 2026-10-30 - Agenda do iCloud com cache de 60 s (primeiro relatório real do app iOS)

O relatório do app mostrou `/api/widget` levando ~8,4 s. Medido no próprio PC: não era rede, eram duas idas ao iCloud
por chamada (foco e agenda), ~4 s cada, sem cache. `caldav_client.eventos_do_dia` agora guarda 60 s por dia; busca
parcial (calendário que falhou) não entra e criar/apagar evento limpa. Evento criado fora do painel pode demorar até
60 s pra aparecer. Testes: `tests/test_caldav_cache.py`.

## 2026-10-30 - App iOS: abre configurado (endereço local + token depois do PIN)

Pedido dele: instalar e já estar tudo lá. `scripts/ipa_com_endereco.py` grava o endereço (`.env` ou `tailscale serve`) só na cópia local
do .ipa (o GitHub não recebe o endereço); o app lê em `Ajustes.aplicarEnderecoDeFabrica`. Depois do PIN, a própria
página busca o token em `/api/widget/instalacao` e guarda no App Group; o widget acorda sozinho. PIN continua sendo
digitado: a sessão não dá pra levar no arquivo. Testes: `tests/test_ipa_com_endereco.py`.

## 2026-10-30 - App iOS: tela "Gerar relatório" e teste da Dynamic Island

Ideia dele antes de instalar: sem Mac nem simulador aqui, o app conta sozinho o que consegue fazer no iPhone.
- `native/ios/App/Relatorio.swift` (Configurar → Gerar relatório): aparelho, validade da assinatura, App Group,
  widgets, ilha, permissões, conexão com o painel e o que a página consegue fazer dentro do app. Só olha, não pede
  permissão. Endereço e token nunca entram; sem painel no ar, "Copiar tudo".
- Teste real da ilha: `IlhaTeste.swift` + `IlhaTesteAtributos.swift` (contagem de 2 min) e ele responde onde apareceu.
- O widget grava um sinal de vida no App Group (`PainelConfig.registrarBusca`): prova que app e widget se enxergam.
- iOS mínimo sobe pra 16.2 (Live Activities), `NSSupportsLiveActivities` no app.
- Painel: `POST /api/widget/relatorio` (token do widget, descarta chave com cara de segredo/endereço), guarda em
  `diagnostico_cliente` tipo `app_ios`; `scripts/relatorio_painel.py` mostra o último. Testes: `test_relatorio_app_ios.py`.

## 2026-10-30 - Laboratório v4: os "quero" no app (SW v97)

Ele votou no artefato Laboratório do Painel e pediu "faça todos". Briefing geral:
`docs/briefings/2026-10-30-lab-v4-levas.md` (votos, regras); um briefing por grupo com decisões e passos dele
(`docs/briefings/2026-10-30-lab-v4-{foco,tempo,avisos,memoria,dinheiro,aviacao,fechamento}.md`). 7 agentes em
paralelo (worktrees), integrados à mão; conflitos só em listas (tipos de card, ASSETS, scripts, passos do tick).
- **Foco** (`foco_ideias.py`, `recomeco.py`, `cards-foco-ideias.js`): E agora?, Por que travou? (3 adiamentos,
  remédio por motivo, IA barata `remedio_travou`), Pacote de tentação (prêmio em `tasks.extras.pacote`), Um segundo
  antes (pausa antes de app que puxa, via Atalho `/api/atalho/segundo-antes`), Recomeço (`tasks.arquivada_em`).
- **Tempo** (`tempo.py`, `cards-tempo.js`, `secoes/topo/fita.js`): fita no topo, modo espera, calibrador (fator
  achou × levou pelo Parceiro de foco), disjuntor do hiperfoco, checklist da porta.
- **Avisos e manhã** (`manha.py`, `bom_dia.py`, `aviso_cara.py`, `se_entao.py`, `badge.py`, `carro.py`,
  `cards-manha.js`, `nucleo/badge.js`, ControlWidget em `native/`): cartões da manhã, bom dia pelo alarme, aviso
  que muda de cara (sem reduzir aviso), se-então, número no ícone, Central de Controle (não compilado), carro.
- **Memória da IA** (`guardados.py`, `neste_dia.py`, `coincidencias.py`, `cards-memoria.js`): onde guardei,
  o que eu falei sobre…, neste dia (só progresso), coincidências ("não prova de causa").
- **Dinheiro** (`nfce.py`, `email_contas.py`, `cards-dinheiro.js`): cupom que sai da impressora, cupom vira
  itens (link do QR da NFC-e, só gov.br), contas no e-mail (IMAP só leitura, desligado sem `.env`).
- **Aviação** (`aviacao_lab.py`, seção "painel de voo" na aba Aviação, `cards-aviacao-lab.js`): radar de
  validades, previsão do cheque, banca por caderno, voo de cadeira, vento na pista, passaporte. O que não foi
  conferido (CMA, pista/declinação de SSBL) fica configurável e marcado "não conferido".
- **Fechamento** (`medalha.py`, `fechamento_dia.py`, `retrospectiva.py`, `cards-medalha.js`,
  `cards-fechamento.js`): medalha de recorde (Epley) no treino ao vivo, placar do feito, pouso do dia (21h, no
  lugar do fechamento antigo), retrospectiva do mês em stories.
- Migrações novas em `migracoes/202610301000_*`/`202610301200_*` + coluna `tasks.arquivada_em` (`db.py`).
- Acertos da integração: o "eu te chamo" (`tempo.chamar_na_hora`) cala a partir de 25 min antes da saída, porque
  nessa janela quem fala é o aviso de sair que já existia (antes saíam dois pushes juntos). Na aba Aviação,
  alvos ≥ 44 px (link "Abrir Aviação" escondido dentro da própria aba, slider e "Guardar") e texto ≥ 12 px nos
  rótulos dos cards. Os testes do app não chamam mais a IA dos cartões da manhã (`manha._pedir_ia` com mock).
- Pendente conhecido: tarefa arquivada pelo Recomeço ainda aparece como "sem data" em consultas fora da aba
  Tarefas e do E agora.

## 2026-10-30 - Treino ao vivo em 3D de verdade: 215 exercícios (SW v96)

Pedido depois de aprovar o artefato Academia 3D ("todos estão legais") e o teste no iPhone. Briefing:
`docs/briefings/2026-10-29-treino3d-no-app.md`.
- `static/treino3d/treino3d.js` (gerado por `docs/prototipos/academia-3d/academia/build_app.py`, fora do git) +
  `static/treino3d/corpo.json` (MakeHuman CC0) + `static/vendor/three/` (three.js r170, MIT, imports dos addons
  trocados pra caminho local). Corpo esculpido + atlas, músculo principal domina, etiqueta "pega mais em".
- `static/js/treino3d-catalogo.js` (novo): os 215 exercícios + `tipo(nome)` (nome livre da ficha → nome do
  catálogo, null se não casar com segurança) + `acha(nome)`. Substitui o `exercicio-3d.js` (SVG, 43), removido.
- `cards-vivos.js`: o motor é importado só quando um painel aparece (`import()`), um renderizador só; o palco 3D
  muda pro card visível; evento `rep` do motor conta série/rep. Sem WebGL 2 / falha = painel some.
- `cards-tipos.js`: `.tv-fig` virou palco vazio (o 3D entra nele); `data-tipo` = nome do catálogo.
- CSS: `.tv-agora` empilhado (palco largo 1 : 0,95 em cima, igual ao protótipo), brilho de carregando, etiqueta e
  fase do 3D (`.t3-*`), tudo zerado em reduced-motion.
- SW v96: `treino3d-catalogo.js` no precache; motor/corpo/three no cache em tempo de uso.
- Testes: `tests/js/treino3d.test.js` (215 sem repetição, cada nome casa com ele mesmo, ~50 nomes soltos, nomes
  desconhecidos = null, módulo só importa o three local e todo molde do catálogo existe) + `cards.test.js` ajustado.
  Headless 390 px: supino → crucifixo, reduced-motion e sem WebGL.

## 2026-10-22 - App iOS nativo (.ipa) com widget, build no GitHub Actions
- `GET /api/widget` (já existia, `rotas/n3a_widget.py`) agora aceita também a **sessão logada** do painel
  (o app nativo é uma WebView logada pelo PIN); modo visitante continua barrado. Teste em
  `tests/test_fase7_n3a_widget_api.py`.
- `native/ios/`: app contêiner SwiftUI (`App/PainelApp.swift`): WKWebView no painel + tela Configurar
  (endereço e token gravados no App Group `group.com.alexxcgg.painel`, que o widget lê), aberta na
  primeira vez ou pelo atalho do ícone. Microfone/câmera liberados só pro host do painel. Ícone 1024 px
  tirado do `static/icons/icon-512.png`. `project.yml` (XcodeGen) junta o app e o widget de
  `native/widgetkit/` (iOS 16+).
- `.github/workflows/build-ios.yml`: macos-latest, XcodeGen, `xcodebuild` sem assinatura, confere que o
  widget foi embutido, empacota `Painel.ipa` e publica como artefato (30 dias). Roda quando muda
  `native/` ou na mão.
- `docs/IOS_APP.md`: baixar o `.ipa` e instalar pelo Sideloadly no Windows com Apple ID grátis, com os
  limites (7 dias, 3 apps, App Group pode não valer na assinatura grátis). **O Swift nunca foi compilado
  aqui (sem Mac): a primeira execução do workflow é o primeiro build de verdade.**

## 2026-10-22 - Leva "painel mais esperto" (SW v93+)

Pedido do Alex: "o que falta pra deixar o painel mais esperto?" → "faz todos". Briefing com a ordem e as decisões:
`docs/briefings/2026-10-22-leva-ideias-v3.md`. Um commit por item.
- **Como tu tá hoje (SW v93)**: ele não achava onde dizer como está. Card novo `checkin` no chat (energia, sono e
  humor em controle de 3 com a pílula em mola, carinha que sorri/fecha a boca com o humor, frase que muda), cada toque
  salva em `POST /api/checkin` (o check-in de 1-3 que já existia), otimista. A IA pergunta sozinha de manhã
  (`conversa_proativa.perguntar_como_esta`, 7h-11h, 1x/dia, só se ainda não respondeu; push `como_esta`) e o card
  também sai quando ele conta pelo chat (`registrar_checkin` agora devolve o efeito `checkin`, sem Desfazer). Dado de
  saúde: visitante não vê os valores. Testes em `test_conversa_proativa.py` e `tests/js/cards_vivos.test.js`.
- **Botões Feito / Adiar no aviso (SW v94)**: aviso de uma tarefa (`_AVISOS_DE_UMA_TAREFA`) sai com 2 ações
  (`push_client.enviar(acoes=...)` → `actions` no Service Worker). O toque chama `POST /api/push/acao` (feito conclui;
  adiar passa 1 h, ou pra amanhã depois da meia-noite) e o SW mostra uma confirmação silenciosa; se a rede falhar, abre
  o app na tarefa (o plano B que já existia). Como o iOS pode não mostrar botão em PWA, o "Testar aviso" agora manda um
  aviso com botões e grava o que ele tocou (`push_teste_botoes`); a linha de notificações em Configurações diz
  "botões funcionam" ou "sem botão no aviso". Testes em `tests/test_push_acoes.py`.
- **Inegociável + Dia ruim + "hoje pede mais cuidado" (SW v95)**: módulo `dia_ruim.py`. Coluna `tasks.inegociavel`
  (cadeado na lista de tarefas e no chat: ferramenta `travar_tarefa`); tarefa travada nunca vai pra amanhã (fechar o
  dia, `mover_tarefas`) e ganha aviso extra 5 min antes (`tarefa_inegociavel`, passa no hiperfoco). Botão "Dia ruim" no
  Início (e ferramenta `dia_ruim` no chat): mantém o inegociável, encurta treino/estudo ("versão leve · 25 min" /
  "versão curta · 20 min") e empurra o resto; card `dia_ruim` com Como estava / Aliviado, Empurrar e Trazer de volta.
  Tabela `tarefas_adiadas` conta o que foi empurrado. De manhã (7h-10h30), com 2 sinais (dormiu < 6 h, 3+ empurradas
  na semana, gasto atípico ontem, energia baixa) a IA manda o card `alerta_dia`: sinais, cadeado por tarefa, Aliviar o
  resto / Tô bem, segue. Rotas em `rotas/dia_ruim.py`; front `static/js/cards-dia.js` + `cards-dia.css` seguindo o
  protótipo aprovado. Testes em `tests/test_dia_ruim.py` e `tests/js/cards_dia.test.js`.
- **De onde parei (SW v95)**: `de_onde_parei.py`. O batimento que já existia (`POST /api/push/visto`) agora guarda
  a última vez que viu o app na tela; voltou depois de 2 h com tarefa pela metade (passos com pelo menos um feito nos
  últimos 3 dias e um faltando) → a IA deixa no chat o card `de_onde_parei` e o app recarrega a conversa. Barra até
  onde parou, caixinha do próximo passo respirando, marcar risca e anda a barra (`POST /api/subtasks/<id>/marcar`,
  marca e desmarca), Continuar mostra o passo da vez, Deixar pra lá segura o dia (`/api/de-onde-parei/deixar`), tudo
  feito oferece Concluir a tarefa. Uma vez por tarefa por dia; nada no modo visitante. Testes em
  `tests/test_de_onde_parei.py` e `tests/js/cards_dia.test.js`.
- **Parceiro de foco (SW v95)**: `foco.py`. Ferramenta `parceiro_foco` no chat ("vou organizar as fotos"): acha ou
  cria a tarefa e abre o card `foco` com relógio (10 min padrão; 15 ou 25 se ele pedir), um passo de 2 min e o
  passo menor que a IA já deixa escrito. Anel com marcas e ponta que brilha; no meio o relógio espera e pergunta
  (Ainda nisso / Travei / Terminei) e sai 1 push `foco_meio`, que nunca insiste. Travei troca pelo passo menor, sem
  cobrar. Terminei conclui a tarefa e guarda quanto levou (`extras.foco_s`), com o estouro de dois anéis. Deu o
  tempo: NÃO marca sozinho (pergunta Terminei / Mais 5 min). Relógio correndo = filtro do hiperfoco (só passa o
  crítico). A sessão fica no servidor (`configuracoes.foco_sessao`, rotas em `rotas/foco.py`), e o card do
  histórico sincroniza por `GET /api/foco`. Tarefa empurrada 3+ vezes entra no contexto do chat pra IA oferecer o
  passo de 2 min. Testes em `tests/test_foco.py` e `tests/js/cards_dia.test.js`.
- **Quadro dos combinados (SW v95)**: `combinados.py` + ferramenta `quadro_combinados` ("o que eu devo pros outros?").
  Card `combinados` com pílula Pessoas / Empresa. Pessoas junta `esperas` (prometeram pra ele) e `responder` (ele
  deve resposta), mais velho primeiro, com "há N dias" (UTC → hora local antes de contar). Resolvido risca e chama a
  rota que já existia; Cobrar/Responder digita um rascunho e vira Copiar, porque o painel nunca manda nada. Empresa:
  contas atrasadas da API da construtora (`_buscar_contas_a_vencer_construtora`, só leitura), como chegaram e SEM
  total (somar seria refazer conta da empresa); fora do ar → aviso, nunca número inventado. Visitante não vê nada
  disso. Testes em `tests/test_combinados.py` e `tests/js/cards_dia.test.js`.
- **Refeição pela proteína (SW v95)**: a foto do prato agora responde com o card `proteina`, igual ao protótipo. O
  prato é escaneado, o número conta, e o copo com onda enche até o total de proteína do dia contra a meta do perfil.
  Tem "Corrige se errei" (−/+ 5 g → `POST /api/refeicoes/<id>/proteina`) e 3 sugestões pra próxima refeição, que
  saem do que ele mais come nas fotos dos últimos 30 dias (mediana; completa com ovos/frango/iogurte quando não há
  histórico); escolher uma sobe o copo. O texto da resposta é só proteína ("Esse almoço tem uns 39 g... Falta 73
  g"); carbo e gordura ficam numa linha pequena e kcal some da tela (continua gravado). Sem peso no perfil → pede o
  peso em vez de inventar meta. O type antigo `refeicao` continua no front pros cards do histórico. Testes em
  `tests/test_proteina.py`, `tests/test_foto_prato_feriados_voz.py` e `tests/js/cards_dia.test.js`.
- **Diário de bordo (SW v95)**: card `diario_bordo` (protótipo cDiario) com as 3 perguntas depois do voo (tipo
  navegação/TGL/instrumentos, dia/noite, tempo; no TGL os toques) e as barras de quanto falta pra comercial pelos
  mínimos do RBAC 61.101 (150 total, 20 navegação, 10 instrumentos com até 5 h de simulador, 5 noturno), com o
  aviãozinho andando na barra do total e a categoria mais atrasada pulsando. Desfazer volta o voo como estava.
  Migração `202610221500_db_voos_diario_bordo.sql` (voos.natureza/noturno/toques), `diario_bordo.py`,
  `POST /api/voos/<id>/diario`, ferramenta `diario_de_bordo` ("acabei de voar"). A pergunta automática pós-voo e
  a saída do aeroclube agora mandam o diário no lugar do `voo_horas` (que fica pro histórico). Testes em
  `tests/test_diario_bordo.py` e `tests/js/cards_dia.test.js`.
- **A IA propõe o horário + sugestão da semana (SW v95)**: `horario.py` escolhe UM horário olhando agenda (iCloud,
  tarefa com hora = 30 min, voo do briefing ao debriefing), 15 min de folga depois do compromisso anterior, a hora
  em que ele costuma fazer aquilo e o sono (dormiu pouco = noite livre, fim às 21h). `sugerir_horario_livre` usa
  isso, aceita `dia` (amanhã etc.) e o "porque" do card `sugestao` conta o motivo. O resumo de domingo
  (`padroes_semana`) ganhou `sugestao`: um passo concreto pra semana que vem (atrasadas > categoria do diário de
  bordo > dia que mais rendeu > água), no texto e numa caixa no card `semana`. Testes em `tests/test_horario.py`,
  `tests/test_conversa_proativa.py`, `tests/js/cards_rotina.test.js` (e os de sugestão antigos agora com a folga).

## 2026-10-21 - Carga × sono no treino (SW v92)

O Alex cobrou: o card de subir carga tinha que ser o da ideia 4 que ele aprovou ("Treino que vira dado", artefato
"Ideias do Painel"), com sono junto - não só a linha de carga do SW v90. Decisões dele (perguntadas antes): sono pela
pergunta no começo do treino enquanto o Atalho do Saúde não manda; barras no card de troca de carga; barras desde o 2º
treino e a frase das médias só com comparação de verdade.
- `treino_carga`: `historico[{data, kg, sono}]` (`sono` = `saude_dados.sono_horas` do dia) e o gráfico de linha virou
  `barrasCarga` (até 6 treinos, noite de 7 h+ brilha, sem sono tracejada, hoje com contorno; médias 7 h+ × menos com
  2+ de cada lado). Entrada: barras crescem em cascata com quique, a noite boa acende depois (só card novo).
- `treino_agora`: "Dormiu quanto essa noite?" (chips 5/6/7/8 h+, otimista, volta se falhar) →
  `POST /api/treino/sessoes/<id>/sono` (2-14 h, arredonda pra 15 min, recusa visitante) grava no dia da sessão, o
  mesmo campo que o Atalho preenche. Visitante: `sono_horas` (`CAMPOS_SENSIVEIS`) e `historico[].sono` saem.
- Cor do treino corrigida (o Alex notou): `treino_agora`/`treino_carga` e o realce do músculo no 3D estavam no verde
  `#b5e48c` copiado do artefato de demonstração - verde é gasto/compras na linguagem dele. Agora `--cor-painel` (#9aa8f0),
  a mesma do `saude_treino`. Mesma troca no painel do João (mesma paleta).
- Testes: `tests/test_treino_vivo.py` (rota, card, histórico, visitante) e `tests/js/cards.test.js` (barras, frase,
  chips). Captura 390 px sem erro nem rolagem lateral; artefato do treino atualizado com dado inventado.

## 2026-10-21 - Animação 3D do exercício no treino ao vivo (SW v91)

Pedido depois de aprovar o artefato do treino: animação "de vários e vários exercícios" no painel real.
Briefing: `docs/briefings/2026-10-21-animacoes-exercicios.md`.
- `static/js/exercicio-3d.js` (novo): o motor do artefato virou arquivo do app com 43 exercícios (peito, tríceps,
  costas, ombro, bíceps, perna, abdômen), helpers de corpo (`corpo`/`emPe`/`prono`/`supino`, `pernas`, `bracos`),
  `caixa` pra máquina/assento/step, músculos por região (tronco frente/costas só quando visíveis; braço/coxa/canela
  por cápsula). `tipo(nome)` sem acento, o mais específico primeiro ("voador inverso", "agachamento búlgaro",
  "mesa flexora"); remada alta/adutora/esteira = null. `desenhar(tp, t)` puro (testes e pose parada).
- Card `treino_agora`: painel `.tv-agora` em cima da lista (renderer continua puro; cada `li` leva tipo/séries/reps);
  `CardsVivos.preparar` desenha e liga o laço (só na tela, só treino em andamento), `trocarExercicio` faz o
  sai/entra ao marcar, some no fim. Reduced-motion: pose parada, sem troca animada.
- Troca de carga/gráfico NÃO mudou (já existia completa).
- Testes: `tests/js/exercicio.test.js` (todos os tipos sem NaN em 5 pontos, ids únicos, ~40 nomes) + renderer em
  `tests/js/cards.test.js`. Captura 390 px sem erro nem rolagem lateral. SW v91 (`exercicio-3d.js` no precache e no
  `templates/scripts.html` antes do `cards-tipos.js`).

## 2026-10-21 - Chat dá baixa pelo que ele conta

O Alex reclamou que pede baixa e a tarefa fica aberta. No chat do dia, as baixas ditas com todas as
letras ("já fiz X", "já fui lá") funcionaram; o que escapava era a baixa implícita - ele conta
onde está ("estou no banco agora") e a tarefa daquele lugar seguia aberta, além de tarefas que já
tinham passado da hora ficarem paradas enquanto a IA refazia o resto do dia.
- `CHAT_SYSTEM_PROMPT` ganhou "BAIXA PELO QUE ELE CONTA": tarefa de hoje que a fala mostra que
  aconteceu/está acontecendo vira `ajustar_tarefa` status concluir na mesma rodada; antes de refazer
  os horários, as atrasadas que a fala não cobre viram UMA pergunta curta no fim (nunca concluídas
  por chute). Teste em `tests/test_despertador_pedido.py`.

## 2026-10-21 - Gráfico de carga no card de troca (SW v90)

Pedido do Alex: quando conta que mudou a carga, mostrar o gráfico de quando subiu ou baixou (como os
gráficos pequenos que o app já tem).
- Tabela nova `treino_cargas` (migração `202610212100_tv_treino_cargas.sql`): um ponto por exercício por dia
  quando a carga em kg muda. `salvar_ficha_treino` grava o ponto de partida; `atualizar_carga_treino` grava a
  linha de base (data da ficha) e o ponto novo. Desfazer apaga os pontos criados (`historico_ids` no token -
  o `_criar_token_desfazer` filtrava chaves e engolia isso; corrigido).
- `card_treino_carga` manda `historico[{data, kg}]` por linha; `graficoCarga` no front desenha área + segmentos
  de subida/descida, entra se desenhando no card novo, parado no histórico, sem animação com movimento reduzido.
- Testes: histórico vira gráfico e Desfazer tira o ponto; ficha salva só grava carga em kg; JS do gráfico.

## 2026-10-21 - Treino ao vivo: ficha com caixinhas + troca de carga pelo chat (SW v89)

Pedido do Alex: "vou treinar peito" mostra o treino, ele vai marcando, e depois conta se subiu ou baixou carga.
- **`treino_vivo.py`** (puro): lê a linha da ficha (`nome|series|reps|carga` do menu, ou texto livre "supino reto
  4x10 com 20kg"), acha a ficha pelo que ele falou ("peito", "treino A", "peito e tríceps"), rotação ("hoje é qual
  treino?" = a feita há mais tempo), acha o exercício sem chutar quando dois batem.
- **Sessão do dia**: tabela `treino_sessoes` (`migracoes/202610211800_tv_treino_sessoes.sql`), uma por ficha por dia.
  O último exercício marcado registra o treino (`treinos.origem = 'sessao'`, duração desde que a ficha abriu, só se
  ≥ 10 min); desmarcar desfaz. "Treinei peito 1h" depois disso completa o mesmo registro, não conta dois.
- **Chat**: `comecar_treino` (card `treino_agora`) e `atualizar_carga_treino` (card `treino_carga`, antes → depois,
  Desfazer volta a ficha). Ficha colada no chat agora é gravada no formato do menu. Regra no prompt: abre, responde
  curto com o primeiro exercício, e no fim pergunta uma vez da carga se ele não falou.
- Modo visitante recusa marcar e trocar carga. Rota nova `POST /api/treino/sessoes/<id>/exercicio`.
- **Animação do exercício**: o Alex recusou boneco de palito ("tem que ser de outro nível") → skill nova
  `treino-ao-vivo` com a régua; protótipo do supino (manequim 3D projetado em 3/4, banco, barra com anilhas, peito
  acende no empurrão, desce 2 s / sobe 1 s) só no artefato, esperando veredito antes dos outros exercícios.
- Testes: `tests/test_treino_vivo.py` (15) + 2 JS; captura 390 px conferida.

## 2026-10-21 - Chat mais humano: balão que vira card + dois planos (SW v88)

Veredito do Alex nos artefatos de conversa: "balão que vira card" (B) + "dois planos" numa pílula (pedaço do D).
- **Balão que vira card** (`static/js/secoes/hoje/chat.js` `juntarBalaoECard`, CSS no fim de `chat.css`): o
  primeiro card da resposta cola no balão - o balão abre pra largura toda, canto de baixo reto, borda/fundo
  tingidos com a `--card-cor` do card, "ouvir" vai pro canto de cima, e o card desce de dentro numa cortina
  (`clip-path`, 760 ms, `--ease-suave`). Histórico abre colado e parado; reduced-motion sem transição.
- **Dois planos**: `planejar_dia` aceita `plano_b` (+ `plano_a_nome/nota`); só vale se casa os mesmos blocos e
  muda alguma hora (`_planos_do_dia`). Card "Dia montado" ganha a pílula; trocar regrava as horas pela rota de
  hora, refaz a trilha/lista e volta se falhar. Histórico mostra o plano que está valendo.
- **Jeito de responder** no prompt: faz e conta, nunca termina com "Quer que eu…?", não repete aviso, não fala de
  ferramenta/card/sistema, 1 a 3 frases. Digitação ao vivo com respiro maior no ponto (+180 ms) e vírgula (+75).
- `á` literal que a IA devolvia vira o caractere (`_desescapar_unicode`). Água ×4 já era 1 card desde 15/10.
- Testes: `tests/test_dia_dois_planos.py` + JS da pílula; captura 390 px conferida.

## 2026-10-21 - Tempo trecho a trecho na rota + "vai chover depois de lavar o carro" (SW v87)

Pedidos do Alex: numa viagem de 200 km chove num pedaço e no outro não, e a serra pra Curitiba pega neblina;
e "vou lavar o carro às 14" tem que olhar se chove nas horas seguintes e sugerir outro dia.
- **`clima_rota.py`** (novo): pontos do caminho real (polyline) a cada ~20 km (máx. 12), hora em que ele passa
  em cada um, uma chamada multi-ponto ao Open-Meteo (chance, mm, código, visibilidade, rajada, altitude).
  Classifica do pior pro leve (granizo > trovoada > neblina > chuva forte > chuva > vento > firme), junta em
  trechos "do km X ao Y", "na serra" acima de 600 m, nome da estrada pelos 3 piores (`nome_do_trecho`, cota
  própria). Rota < 25 km, fora dos 16 dias ou sem rede = sem a parte do tempo.
- `estimar_trajeto`: parâmetro novo `saida` (HH:MM ou data+hora) e `tempo_no_caminho` (frase pronta) pra IA;
  `maps_client.traco_desenhavel(tempo=)` pinta os trechos no mapa; card `rota` ganha a barra do caminho
  (`docs/CARDS.md`).
- **`consultar_clima(hora, janela_horas)`**: atividade que a chuva estraga (lavar carro ~24 h, varal ~6 h,
  churrasco/trilha = duração) → primeira hora com chuva na janela, em quantas horas, `certeza`
  (quase_certa ≥ 80% com mm previsto, senão provável) e `proximo_dia_seco` (dias seguidos secos pra janela
  longa). Prompt: a IA chama sozinha, só fala se chover e pergunta curto "deixa pra quinta?"; nunca "com certeza"
  fora de quase_certa. Funções puras `clima.analisar_janela` / `dia_seco_pra`.
- Testes: `tests/test_clima_rota.py` + JS do card. Chat: veredito da resposta "balão que vira card + pílula com
  2 planos" guardado (protótipo no artefato), implementação fica pra leva própria.

## 2026-10-20 - Vistoria: servidor saturando (fila do Waitress)

Relatório do painel de 14 a 20/10 cruzado com o CHANGELOG. Briefing: `docs/briefings/2026-10-20-vistoria-servidor.md`.
- **Fila do Waitress enchendo** (1448 avisos, 48 recusas de conexão; em 18/10 19h o Alex repetiu mensagem no chat):
  cada resposta ao vivo do chat segura uma thread e o `iniciar_painel.bat` usava as 4 do padrão. Agora
  `--threads=16` (arquivo local, fora do git) e `db.get_db()` com `timeout=30`. Banco segue sem WAL.
- **Chat** (`ia/funcoes/chat.py`): regra da lista de tarefas sem dia reforçada e descrição de
  `distribuir_tarefas_na_semana` reescrita (a IA respondia "nada foi criado ainda, só confirma").
- Sem ação: barra de abas (15/10, já consertada), avisos "nunca vistos" (quase todos antes de 17/10), aviso h3.
- Conferir em alguns dias com `scripts/relatorio_painel.py`: a fila deve sumir. Sem JS: SW segue v86.

## 2026-10-18 - Memória sob demanda + correções que o chat mostrou

Pedido do Alex: a IA lembrar do passado só quando ele pergunta ("quando foi o dia que arrumei o quartinho?").
Briefing: `docs/briefings/2026-10-18-memoria-sob-demanda.md`.
- **`buscar_na_memoria`** (`memoria.py`): acha QUANDO algo aconteceu em tarefas, chat, diário, notas, esperas,
  decisões e gastos; sem IA, sem tabela nova, nada no contexto até ele perguntar. Ignora a própria pergunta.
- **Prompt**: `LISTA DE TAREFAS SEM DIA` (cria tudo e escolhe dia/hora em vez de "só confirma") e `RESPOSTA CURTA
  DELE CONTINUA O ASSUNTO` (16/10: respondeu "março" e a IA mudou pra cobrar compromisso).
- **Relatório**: falso positivo da barra de abas (agora `vvTopo+vvH`); "nunca abertos" → "nunca vistos".
- **Log do servidor** não grava mais o aviso de HTTP/3 do urllib3-future (refaz sozinho).
- Testes: `test_memoria` (14), `test_log_erros` (+1), `test_relatorio_painel` (+caso). Sem JS: SW segue v86.

## 2026-10-17 - Aviso que insistia mesmo com o app aberto (SW v86)

17 de 19 avisos insistentes foram enviados 3x sem toque registrado. O toque na notificação funcionava, mas
abrir o app direto não contava. Agora o app avisa o servidor que está aberto (`POST /api/push/visto`, ao abrir,
voltar pra frente, focar e a cada 60 s) e isso encerra a insistência de hoje. O relatório chama de "vistos".

## 2026-10-16 - Despertador pedido no chat + relatório do painel + registro de erros (SW v85)

Pedido do Alex: "amanhã quero acordar às 7" vira despertador no iPhone; e um relatório do painel
inteiro pra achar bug. Briefing: `docs/briefings/2026-10-16-despertador-e-relatorio.md`.
- **Despertador**: o iOS não deixa PWA criar alarme (só o app Atalhos), então: ferramenta do chat
  `definir_despertador` guarda o pedido (`despertador.py`), `GET /api/atalho/despertador` o devolve
  (ignora `?ate=`; compromisso que exige acordar antes ganha, e a IA é avisada), card `despertador` com
  botão `shortcuts://run-shortcut?name=Despertador%20do%20Painel` (allowlist estrita). **Alex precisa
  criar o Atalho com esse nome** (`docs/ATALHOS.md` 2c-bis). Aceita "7h"/"7h30"/"07:00".
- **Relatório**: `scripts/relatorio_painel.py` + habilidade `relatorio-painel` (conversa, aparelho,
  servidor, dados; "o que olhar primeiro" por gravidade; só leitura; saída em `data/`).
- **Registro de erros que não existia**: `log_erros.py` grava WARNING+ em `data/erros_servidor.log`
  (antes sumia no console) e o `init.js` manda erro de JavaScript do celular como diagnóstico `erro_js`.
- Testes: `test_despertador_pedido` (8), `test_relatorio_painel` (8), `test_log_erros` (3),
  `test_diagnostico` (+1), `cards_automacao.test.js` (+1).

## 2026-10-16 - Raiz do projeto limpa + mapa no AGENTS.md

Pedido do Alex: o painel bem configurado pra IA não se perder e não ler o que não precisa. Nada apagado.
- `BRIEFING.md`, `STATUS.md`, `TODO.md`, `REGRAS-OPERACAO.md` (todos de setembro, o STATUS ainda dizia
  "ler primeiro" e descrevia o redesenho de 4 abas que foi recusado) foram com `git mv` pra
  `docs/historico/`, com `LEIA-ME.md` explicando. O que ainda pode valer virou `docs/PENDENCIAS.md`
  (nenhum item reconferido - o da chave do Render precisa do Alex).
- `AGENTS.md` (818 linhas): tabela "mexeu em X -> leia a seção Y" no topo; `CLAUDE.md` agora manda
  ler só a seção da área, nunca inteiro. Referência a TODO.md trocada por CHANGELOG.
- `CLAUDE.md`: comando de teste do Windows (`.venv/Scripts/python.exe`); o `.venv/bin` era do Linux antigo.

## 2026-10-16 - CHANGELOG com índice no topo + setembro arquivado

Ideia tirada de um vídeo que o Alex mandou (Claude Code + Obsidian: "índice no topo da nota do dia"),
pedido dele: "cada vez gastar menos, acertar mais". O resto do vídeo o painel já tinha (CLAUDE.md,
AGENTS.md, briefings, memória com links).
- `scripts/indice_changelog.py`: índice gerado no topo (uma linha por entrada, inclusive as arquivadas,
  com o arquivo onde estão); `--arquivar-antes AAAA-MM-DD` move dias velhos pra
  `docs/historico/CHANGELOG-AAAA-MM.md`; `--checar` pro teste.
- Setembro (76 entradas) foi pro histórico: principal de 3.670 pra ~1.170 linhas. Conferido linha a
  linha que nada se perdeu (128 títulos antes e depois).
- `CLAUDE.md`: ler só o índice, rodar o script depois de escrever entrada.
  `tests/test_indice_changelog.py` falha se o índice ficar velho.

## 2026-10-16 - Barra que sumia com medida impossível + horário solto + título de depois (SW v84)

Leitura do chat/diagnóstico de 15/10 (`scripts/ler_chat.py`). Briefing: `docs/briefings/2026-10-16-barra-horario-titulo.md`.
- **Barra de abas (6a camada, `init.js`)**: na tela IA o iOS devolveu medida de transição impossível
  (`vvTopo` = tela inteira, sonda em 0 ou negativa) e a barra desceu 1.912 a 33.984 px - sumiu.
  `_medidaPlausivel`: sonda entre 30% da tela e o fundo, `vv.offsetTop` < 60% da tela, desvio ≤ 60% da
  tela; fora disso a barra fica no lugar (0px), manda retrato `ignorada` e remede em 400 ms (até 5x).
  Com `document.hidden` não mede. Teste: `test_medida_impossivel_no_meio_da_transicao_nao_some_com_a_barra`.
- **Chat - HORARIO SOLTO LOGO DEPOIS**: ele mandou só "18:30" depois da IA criar uma tarefa sem hora e
  a IA não gravou; agora o horário vai pra essa tarefa (`ajustar_tarefa`), só pergunta se houver 2+ sem hora.
- **`ajustar_tarefa` devolvia o título ANTIGO ao renomear** - a IA achou que a troca não tinha pegado e
  pediu pra ele conferir. Agora `titulo` = o novo e `titulo_antes` = o de antes.
- `scripts/ler_chat.py`: não quebra mais no console do Windows (cp1252) ao imprimir o "⚠".

## 2026-10-15 - Trânsito de verdade + Waze nos cards (SW v83)

Pedido do Alex: "o que falta hoje no painel é o trânsito", tudo grátis, avisar de coisa tipo
blitz/acidente nos cards, recalcular "a cada hora". Briefing: `docs/briefings/2026-10-15-transito-waze.md`.
- `maps_client.tempo_de_viagem(partida=, lentidao=)`: `departureTime` (trânsito previsto pra hora de
  sair - antes era o do momento da pergunta), `staticDuration` → `transito_min`, trechos lentos/parados
  (`TRAFFIC_ON_POLYLINE`; `trechos_lentos` junta vizinhos, lento < 1 km some, parado ≥ 300 m), nome dos 2
  piores por Geocoding reverso (`nome_do_trecho`), `destino_ll`. `frase_trecho`/`resumo_transito`: "Parado
  na BR-470, Gaspar (2 km) - pode ser acidente ou blitz" (nunca afirma a causa). `link_waze` (deep link
  oficial). `horario_de_saida` devolve `transito_min`, `lentidao` e `waze`.
- **Trava da cota grátis** (`usar_cota`, tabela `uso_maps`, `COTA_MES`): lentidão 800/mês, trânsito 4.000,
  básico 8.000, nome 8.000. Bateu → faixa de baixo; nada → `CotaEsgotada` (é `RequestException`, então
  todo lugar já trata como "Maps fora").
- Card `rota`: "+N min de trânsito", linhas do trecho parado/lento, trecho pintado no mapinho depois que o
  carrinho passa, botão "Ir com Waze"/"Waze até X". `date`/`balada`/`voo_agendado`/`vespera_voo`: Waze +
  "(+N de trânsito)". IA do chat repete a frase do `transito` sem inventar causa.
- Avisos "Hora de sair" (compromisso com lugar) e "Hora de ir pro voo": recalculam no máximo 1x por hora
  por lugar (antes: 1x por dia / a cada tick de 5 min no voo) e levam o trânsito no texto.
- Tarefa com lugar ganha "ir com Waze" nas ações (`/api/tasks` → `waze`, apelido vira endereço) - o toque
  no aviso "Hora de sair" abre a tarefa com as ações abertas.
- Testes: `tests/test_transito_waze.py` (12) + renderizador da rota em `tests/js/cards.test.js`.

## 2026-10-15 - Barra de abas: medida pelo ancoradouro de verdade (SW v82)

O Alex mandou print às 16:05 com a barra ainda cortada - e o `/api/diagnostico` (da leva abaixo)
tinha o número exato do mesmo minuto: iOS 18.7, app da tela de início, `innerHeight` 956,
`clientHeight` 894 (62 a menos = faixa do relógio), fundo visível 956. A conta "fundo visível −
`clientHeight`" dava 62 e descia a barra 62 px (fundo dela em 1018, fora da tela). Só que a barra
`position: fixed` se prende em 956, não em 894 - `clientHeight` nunca foi o ancoradouro.
- `_medirDesvioTela` (`static/js/nucleo/init.js`) agora usa uma sonda invisível `position: fixed;
  bottom: 0`: o topo dela é onde o fundo das peças fixas fica de verdade. Sem base nem chute -
  desce só quando o fundo visível passa desse ponto em ≥ 48 px (o teclado preso). O diagnóstico
  manda `ancora` no lugar de `normal`.
- Teste novo com os números reais do iPhone (documento 62 px menor que a tela → barra inteira na
  tela; teclado preso +300 continua corrigido). Os testes da "folga de 34 px" eram o mesmo erro de
  medida e agora esperam o deslocamento real.

## 2026-10-15 - Microfone, barra de abas e o que o chat mostrou (SW v81)

Leva feita a partir de briefing próprio (`docs/briefings/2026-10-15-voz-barra-chat.md`), depois do
Alex reclamar que o áudio às vezes não sai / não escuta nada e que a barra de abas ainda aparece pela
metade. A "lista solta" que ele não tinha dito era o eco do Whisper, já corrigido em 2026-10-11
(`tirar_eco_do_prompt`).
- **Microfone**: `getUserMedia` com prazo de 5 s e uma nova tentativa (`_abrirMicrofone`; espera
  400 ms se o aparelho disse que está ocupado, pede `{audio: true}` simples se a restrição falhou);
  a voz da IA para antes de gravar; a barra de gravação aparece na hora e o `AudioContext` é
  acordado/recriado depois (`_contextoAudioVivo`). Detector de voz "surdo" (contexto `interrupted`,
  RMS sempre 0) não joga mais o áudio fora - manda inteiro, sem corte de silêncio. Gravação vazia ou
  < 0,6 s avisa "Gravou muito pouco - tenta de novo" em vez de sumir. Falha mostra aviso claro
  ("O microfone não respondeu/travou. Toca de novo pra falar."). Mesmo tratamento no modo conversa.
- **Barra de abas**: a correção do teclado/volta do segundo plano usava o *menor* desvio visto como
  base - uma primeira medida 0 seguida da folga normal (~34 px) empurrava a barra pra baixo. Agora a
  base é o último desvio pequeno (≤ 60 px) e só desvio ≥ 48 px acima dela mexe na barra.
- **Diagnóstico do aparelho**: `POST /api/diagnostico` (`rotas/diagnostico.py`, tabela
  `diagnostico_cliente`, só número/texto curto, últimas 500) - o iPhone manda medidas da tela ao
  abrir/voltar e as falhas do microfone; `scripts/ler_chat.py` mostra no fim da cópia. Pra próxima
  vez que a barra ou o mic falharem, os números reais estão lá.
- **Cards**: vários copos de água na mesma fala viram 1 card com 1 Desfazer pra todos; card de
  sugestão de horário some quando a mesma resposta já gravou o horário (não contradiz mais).
- **Prompt do chat**: sem horário dito (ou "tu me diz"/"encaixa") a IA escolhe e diz que dá pra
  mudar (voo e compromisso com outra pessoa continuam perguntando); pergunta pendente não se repete
  quando ele muda de assunto; virada do dia (tarefa de antes da meia-noite não "sumiu", compromisso de
  ontem não vale hoje); número no texto sempre em algarismo, inclusive título vindo de áudio.

## 2026-10-15 - 4ª leva: mais automação (véspera do voo, despertador, aeroclube, compras, documentos, projeção)

Leva feita de uma vez a partir de briefing próprio (`docs/briefings/2026-10-15-4a-leva.md`) - ideias
1 a 8 aprovadas pelo Alex (a 9, áudio de bom dia, ficou pra depois). Cards em `docs/CARDS.md`
("4ª leva"); Atalhos em `docs/ATALHOS.md` (2b e 2c).
- **Véspera do voo, só em dia de voo**: 20h-23h30 do dia anterior, voo com hora → chat + push
  "Amanhã tem voo" com card `vespera_voo` (acorda/sai/chega/decola, TAF na hora do voo, mochila que
  marca - `GET/POST /api/voos/<id>/mochila`). No dia: a partir de max(06:30, sair − 1h30) "Bom dia!
  Voo hoje..." com o METAR (card `briefing_voo`). O push antigo "Voo amanhã"/"Pre-voo" ficou só pro
  voo sem hora.
- **Despertador que se ajusta**: `GET /api/atalho/despertador[?ate=HH:MM]` (token do Atalho, entrou
  na lista de rotas sem login) → `{tem, acordar, acordar_iso, titulo, hora, sair, data, mensagem}`.
- **Aeroclube pela localização**: `/api/atalho/local` com `lugar` = `aeroclube`/`ssbl` - chegou
  (voo hoje sem horas) → checklist no chat, uma vez; saiu depois de decolar → pergunta as horas na
  hora (`conversa_proativa.perguntar_horas_agora`).
- **Compras que se repetem**: `conversa_proativa.compras_previstas` (3+ compras, mediana 3-120 dias,
  avisa ≤ 3 dias antes, larga se atrasou mais de meio ciclo) → card `compras_previsao` 1×/dia com
  "Pôr na lista" / "Ainda tem" (`POST /api/compras/adiar`, adia meio ciclo).
- **Assinatura que subiu no chat**: mesmo detector do push; card `assinatura_subiu` (riscado → novo,
  %, "Mantém" / "Me lembra de cancelar"). Valores somem no modo visitante.
- **Documentos 60/30/7**: `conversa_proativa.documentos_vencendo` substitui o aviso único de 8-30
  dias (`app._avisos_fase3`) - um aviso por marco por vencimento, card `documento_validade`
  (carteirinha + anel da contagem) e botão de criar tarefa de agendar.
- **Projeção das horas**: `cards.projecao_horas` (ritmo dos últimos 60 dias, cenário +1 voo/semana)
  no `voo_resumo`, `voo_agendado` e `voo_horas`.
- **Pluggy (item 8)**: nada de código - falta a conta/chave, que só o Alex pode criar (README,
  "Sincronizacao automatica (Pluggy)").
- **Chat + banco não contam duas vezes** (decisão do Alex: "se for igual junta"): gasto do chat com
  o mesmo valor (ao centavo) no mesmo dia local de uma saída do extrato vira uma linha só - fica a do
  banco. `db.gastos_chat_repetidos_no_banco` (1 pra 1, decifra só o extrato dos dias com gasto no
  chat, `so_dias` pra paginação) + `db.total_gasto_real_mes`; ligado em `_gastos_reais_unificados`,
  `_gastos_reais_unificados_para_deteccao`, sobra do mês, `renda_perto_de_acabar`,
  `/api/gastos/unificados` (lista e páginas) e `/api/financas/extrato`/resumo (regra do
  `tipo_operacao`; transferência/fatura não pareia). Nada é apagado. `tests/test_gastos_repetidos.py` (12).
- **Cópia do chat pro Claude Code** (pedido: "toda vez que tu pedir, essa cópia do chat vai pra
  você"): `scripts/ler_chat.py` (sqlite `mode=ro`, cards decifrados e resumidos, número longo/senha
  ocultos, `⚠` em possível correção) → `data/chat_para_claude.md` (gitignored); habilidade
  `.claude/skills/ler-chat`. Texto em vez de PDF/print. `tests/test_ler_chat.py` (6).
- Testes: `tests/test_quarta_leva.py` (25), `tests/js/cards_automacao.test.js` (9);
  `test_pre_voo_vespera_e_dia` e `test_burocracia_com_30_dias` atualizados pro comportamento novo.
  SW v79.
- **Acabamento dos cards** (pedido "deixe cards bem legais"; SW v80): compras no cupom do mercado
  (`.tx-impressora`) com carimbo "NA LISTA" e total n/N; assinatura como etiqueta de preço remarcada
  (velha riscada, nova cai por cima e conta, selo +%, impacto no ano); projeção virou régua
  hoje → +1 voo/semana → ritmo atual; véspera com despertador que toca, "na cama até" (8 h de sono)
  e mochila que pula/fecha o zíper; documento conta de 60 até os dias. `CardsAutomacao.animar`
  (contagem, só fora de reduced motion) chamado pelo `CardsVivos.animar`.

## 2026-10-14 - Cards da IA no app (3ª leva: volta, "pensando", tempo do voo, horas, presente anual)

Leva feita de uma vez a partir de briefing próprio (`docs/briefings/2026-10-14-3a-leva.md`) - pedido
do Alex: "melhora tudo de uma vez em vez de ficar vindo me perguntar". Detalhes em `docs/CARDS.md`.
- **Volta da balada**: a chave do Uber virou "Como tu volta" - dirigindo (padrão: "zero álcool,
  combinado?") / carona (sem lembrete) / Uber (tarefa "Chamar Uber pra voltar" 30 min antes da
  volta, 03:00 se ele não disse). Pílula deslizando em mola; a IA pode mandar `volta_modo`.
  Rota `POST /api/tasks/<id>/volta {modo}` substitui `/uber`.
- **Linha "pensando" com os passos reais**: cada tool avisa no stream (`passo`) o que está fazendo
  ("Anotando "X"", "Calculando o trajeto até o Lume", "Vendo a previsão pras 20h"...). Os pontinhos
  viram órbita + passo com brilho que sobe e empurra o anterior; quando o texto começa, vira o
  recibo recolhível "✓ N passos · X s". Sem ferramenta, continua só os pontinhos.
- **Tempo na hora do voo**: `briefing_voo.previsao_na_hora` lê o segmento do TAF que vale na hora
  (FM troca, BECMG mescla, TEMPO/PROB vira "pode ter"); fora da validade não mostra nada.
  `GET /api/voos/<id>/tempo` (cache 20 min, só ≤ 30 h); o card do voo agendado pede sozinho e
  mostra categoria, vento com seta, teto/visibilidade.
- **Horas do voo com 1 toque**: 20 min depois do pouso estimado (ou hora + 1h30) até 23h30 o chat
  pergunta "quanto deu?" + push, uma vez por voo. Card `voo_horas`: chips perto da estimativa da
  rota (+12 min de motor), "outro" com −/+ de 0,1, barra até a meta anda na hora
  (`POST /api/voos/<id>/horas`). `registrar_voo` com horas preenche o único voo aberto do dia.
- **Presente que volta todo ano**: `anual` (IA, ou título com aniversário/niver/Natal/casamento/
  bodas). Passou a data → cria o do ano seguinte (29/02 → 28/02) com as ideias não usadas e guarda
  o que ele deu; card mostra "↻ todo ano" e "Ano passado: X".
- **Habilidade `cards-ia`** (`.claude/skills/cards-ia/SKILL.md`, pedido do Alex): resumo da
  linguagem visual + contrato + checklist pra qualquer sessão futura criar/ajustar card.
Testes: `tests/test_terceira_leva.py`, `test_cards_saidas.py` (volta), `tests/js/cards_saidas` e
`cards_aviacao`. SW v78.

## 2026-10-14 - Cards da IA no app (2ª leva: date, balada, tabelionato, presente)

Compromisso com cara própria: a IA marca `estilo` no `registrar_tarefa` (date/balada/documentos/
presente) e manda os extras (com quem, lista, ideias, volta). Colunas novas `tasks.estilo` e
`tasks.extras` (migração automática). Detalhes em `docs/CARDS.md` → "2ª leva".
- **Date**: coração que se desenha, "Júlia · Lume", linha se arrumar → sair → chegar com trajeto do
  Maps, fichas de clima na hora (jaqueta ≤ 17°, guarda-chuva ≥ 40%), lista "antes do date" que marca.
- **Balada**: céu com lua/estrelas/cidade, linha com a volta. Sono **só** se o dia seguinte tem voo
  ou tarefa com hora (volta padrão 03:00); < 6 h vira aviso. Chave "Voltar de Uber" (desligada por
  padrão) cria a tarefa de chamar o Uber 30 min antes da volta.
- **Tabelionato/documentos**: pasta que recebe os papéis, carimbo "Pasta pronta" quando tudo foi
  marcado, horário do Google (Places) e aviso se a hora cai fora do expediente/no almoço.
- **Presente**: caixa que abre, contagem, linha hoje → comprar até (data − 4) → o dia; tocar numa
  ideia cria o lembrete de comprar. Em cima da hora: "pela internet não chega".
Rotas novas `POST /api/tasks/<id>/lista|presente|uber` (recusam no modo visitante);
`/api/tasks/estado` devolve `extras` pro histórico. Aviso "hora de se arrumar" conta date/balada
como saída. Testes: `test_cards_saidas.py`, `tests/js/cards_saidas.test.js`. SW v77.

Também hoje: barra de abas cortada no app da tela de início (SW v76) - a folga fixa de ~34pt do
iPhone virou linha de base do desvio medido (`_medirDesvioTela`).

## 2026-10-14 - Cards da IA no app (1ª leva: voo, gasto, alteração, concluir, aperto)

Implementação das 5 cenas do protótipo que usam dado que o painel já tem (tabela em
`docs/CARDS.md` → "O que já está no app"):
- **Voo agendado** (`voo_agendado`): `registrar_voo` sem origem sai de SSBL; `escalas` novas no
  schema da tool e na tabela `voos`; `rota_voo.py` mede as pernas em NM pelas coordenadas do
  `briefing_voo` (aeródromo sem coordenada fica sem NM, nunca inventado) e estima os horários
  (90 kt + 6 min/perna + 15 min/escala). Card: cartão de embarque com o avião percorrendo a rota,
  tocar num aeródromo leva o avião até ele; chega/decola/pousa, hora de sair de casa (Maps, se
  `ENDERECO_CASA`), horas do curso até a meta. Tool nova `ajustar_antecedencia_voo`.
  Desfazer apaga só se o voo ainda não tem horas.
- **Gasto**: cupom saindo da impressora + mês da categoria (barra do teto do orçamento, quanto
  sobra por dia) + 14 dias em barrinhas. Visitante não vê `mes`/`dias`.
- **Alteração**: hora rola os dígitos tipo placar; valor curto troca no lugar (velho sobe riscado,
  novo cai marcado); título longo troca só a palavra que mudou.
- **Concluir** (`tarefa_feita`): check se desenha, título se risca, anel do dia anda uma casa,
  próxima pendente com quanto falta. `registrar_feito` agora tem Desfazer (antes não tinha card).
- **Tarefa com aperto**: tarefa nova a < 45 min de outra pendente → lupa de 3h, faixa apertada,
  botão "Passar X pras HH:MM" (rota nova `POST /api/tasks/<id>/hora`) / "Deixa assim".

**Pro Alex fazer pelo chat**: o banco dele tem `voo_briefing_min=30` e se arrumar = 40 - dizer
"no voo chego 45 min antes" e "me arrumar leva 45 min". Testes novos: `test_voo_agendado.py`,
`test_tarefa_feita.py`, contexto do gasto em `test_cards.py`, JS em `cards*.test.js`. SW v75.

## 2026-10-14 - Cards da IA: protótipo aprovado + aprendizado guardado

Protótipo com 9 cenas (voo, date, balada, tabelionato, presente, mercado, tarefa com aperto,
alteração, concluir), cada uma com card próprio - aprovado pelo Alex cena a cena. Ajustes pedidos
já no protótipo: voo sai de SSBL por padrão, rota com várias pernas e NM por perna, chegar 45 min
antes + trajeto até o aeroclube = hora de sair de casa, tocar num aeródromo faz o avião ir/voltar
até ele; date e balada com a linha "se arrumar → sair → chegar" (se arrumar = 45 min). Princípios
em `docs/CARDS.md` → "Linguagem visual dos cards"; fonte em `docs/prototipos/cards-ia-v2.html`.
**Ainda não está no app** - próximo passo é implementar.

## 2026-10-14 - Campo e barra no meio da tela (de novo) + card "Alterado" letra por letra

Print do Alex (tela IA): campo do chat e barra de abas pendurados no meio da tela, o card
continuando por baixo - o vai-e-volta de 1px da v67 não bastou. 2ª camada em `nucleo/init.js`:
`_medirDesvioTela` mede a diferença entre o fundo VISÍVEL (`visualViewport.offsetTop + height`) e o
fundo do layout (`clientHeight`) e grava `--vv-desvio`; `#tabbar`, `#chat-form` e `.chat-nota`
descem esse tanto (`translate`, soma com o `translateX(-50%)`). Só sem campo em foco e sem zoom;
mede na volta (0/350/900 ms), no `pageshow`, no `focusout` e em resize/scroll do visualViewport.
Normal = 0px. Teste simulando o desvio em `test_volta_do_segundo_plano.py`. **Sem iPhone aqui pra
confirmar - se voltar a acontecer, o próximo passo é logar as medidas reais.**

No mesmo print, o card "Alterado" escrevia o título novo uma letra por linha (grid `auto auto 1fr`:
o "antes" comprido comia a linha). Agora antes / → depois quebram juntos (flex-wrap), a seta colada
no valor novo. SW v74.

## 2026-10-14 - Cards da IA conversam com a aba Tarefas

Print do Alex: concluiu o tricologista na aba Tarefas e o card "Tarefas criadas" no chat continuou
desmarcado. Agora: `apiFetch` (nucleo/api.js) avisa `tarefa:mudou` a cada `/api/tasks/:id/
complete|reabrir` que deu certo (qualquer tela - Tarefas, Início, saudação, o próprio card) e o chat
acerta as caixinhas na hora; o que mudou por fora (aviso, Siri, outro aparelho) vem do novo
`GET /api/tasks/estado?ids=` - chamado ao montar o histórico, ao abrir a aba IA, ao voltar pro app
e depois de resposta com ação. A trilha do "Tarefas criadas" não ouvia mudança nenhuma (só a do card
de tarefas de hoje): ganhou o observer que hasteia o check na bandeira. SW v73.

## 2026-10-14 - Tarefa não duplica mais; conversa por voz "tipo ChatGPT"

**Duplicata.** "Enviar a compra e venda pro Mikael" nasceu 2x: ele já tinha concluído, disse
"9:30 tricologista", e o `planejar_dia` (que só olhava pendentes) "remarcou" criando outra.
`_tarefa_repetida` (app.py): mesmo título (sem acento/caixa) no mesmo dia, pendente OU concluída
nas últimas 12h -> `registrar_tarefa` não cria e devolve `nao_criei` + o caminho certo
(`ajustar_tarefa` pra mudar hora; assunto diferente com a mesma pessoa = título com o assunto,
passa normal). `planejar_dia` pula bloco com o nome exato de uma concluída há pouco
(`ja_feitas_nao_recriei`) - nome exato de propósito, o casamento frouxo poderia engolir tarefa nova.

**Modo conversa (escolhas do Alex: "toque + silêncio" e "só acaba quando eu encerrar").** Não
fecha mais sozinho depois de 12s sem fala (`CONVERSA_ESPERA_FALA_MS = Infinity`) - só no toque ou
saindo do app; 90s calado recomeça a escuta em silêncio, sem tocar o sinal de novo. Na vez dele o
enviar abre numa pílula **"Pronto"** (mola na largura, fade atrasado; volta ao ícone pensando/
falando) - com voz de fundo segurando o silêncio, o toque manda na hora. O silêncio de 1,5s
continua mandando sozinho. SW v72.

## 2026-10-14 - Tarefa atrasada ganha "pra hoje"

O Alex dormiu, a tarefa de ontem amanheceu atrasada e o único botão ("pra amanhã") a jogou pra
quinta - era pra hoje. Atrasada agora tem **"pra hoje"** antes do "pra amanhã"
(`POST /api/tarefas/pra-hoje` -> `conversa_proativa.trazer_para_hoje`): só mexe em aberta com data
antes de hoje; horário que ainda vem hoje fica, o que já passou sai (senão o "Tá na hora" com
insistência disparava no instante de mover). Tarefa de hoje continua só com "pra amanhã". SW v71.

## 2026-10-13 - Avisos que insistem, "Ei Siri, pergunta pro painel" e bugs do print do Alex

- **Quebrar em passos (bug do print)**: os passos iam pro LADO do título (o `.lista-item` antigo é
  flex em linha); a linha da linha do tempo virou coluna e os passos ganharam bolinha própria
  (alvo de 44 px com margem negativa). Novo **"desfazer passos"** nas ações:
  `DELETE /api/tasks/<id>/subtasks` apaga todos os passos, a tarefa fica.
- **"Ouvir" do Início dava "Bom dia" a qualquer hora**: `voz_premium.frase_curta_manha` tinha o
  texto fixo. Agora `saudacao_da_hora` (mesma regra do título do Início) e, depois do meio-dia,
  fala o que ainda falta e a próxima ("Boa tarde, Alex. Ainda faltam 3 tarefas hoje, a próxima é
  academia às 18h."). O fallback `/api/resumo-manha` também.
- **Avisos importantes insistem** (`notificacoes.INSISTENCIA`, tabela `avisos_insistentes`):
  tarefa com hora repete aos +10 e +30 min ("De novo ·" / "Última chamada ·", mesma tag = substitui
  a anterior), compromisso/hora de sair/se arrumar/voo/conta também (intervalos por tipo). Para
  quando ele toca na notificação (o service worker chama `POST /api/push/aberto`) ou conclui a
  tarefa. Silêncio, hiperfoco e o liga/desliga por tipo valem igual. O resto continua 1 vez só.
- **Tocar no aviso abre a tarefa**: `_url_do_aviso` manda `?aba=tarefas&tarefa=ID` nos avisos de
  uma tarefa; `focarTarefaDoAviso` rola até ela, abre concluir / pra amanhã e acende a linha.
  (Imagem/botões dentro da notificação: o iPhone não mostra em app web - limite da Apple.)
- **Textos dos avisos** mais de gente: título "Tá na hora" (era "Lembrete"), "Compromisso
  chegando", acentos que faltavam ("às", "vai", "dá", "tá").
- **`POST /api/atalho/perguntar`**: "Ei Siri, pergunta pro painel" - o texto ditado vai pro mesmo
  chat (memórias, ferramentas, modo voz) e volta só a `fala` limpa (lista vira frase). Exige o
  `PAINEL_ATALHOS_TOKEN` (devolve dado pessoal e age). Montagem em `docs/ATALHOS.md` §5.
- **Memória da IA**: `list_memorias` cortava em 30 - passando disso os fatos MAIS ANTIGOS (perfil,
  rotina, planos) sumiam do prompt e da tela sem aviso. Agora 200 (hoje são 10).
- **Voz menos robô** (escolha do Alex entre 2 rodadas de amostras A/B,
  https://claude.ai/artifact/DWRJQMHLCnoXYKh12rvgJe - ficou a "B da rodada 1"): mesmo modelo
  (flash v2.5, rápido e mesmo custo) e mesma voz, mas `voice_settings` mais solto (estabilidade
  0.35) e áudio 128 kbps (era 64). Saudação do "Ouvir" com exclamação, como na amostra. A versão
  dos ajustes entra na chave do cache (`AJUSTES_VERSAO`) - senão voltava o áudio velho. Rejeitadas:
  multilíngue (1,7 s pra começar) e v3 (2,3 s; com marcação de tom em português puxou sotaque
  nordestino, que o Alex não curte). Achado: o v3 funciona pelo text-to-speech normal também.
  As amostras gastaram ~800 caracteres (uso do mês antes delas: 6.929 de ~9.000). SW v70.

## 2026-10-13 - Aba Tarefas vira linha do tempo

Escolhida pelo Alex entre as prévias ("linha do tempo eu gostei mais"):
https://claude.ai/artifact/V1bNK612xPzqBVXmuX1Guq, com os 4 movimentos ligados.
`static/js/secoes/tarefas/linha-do-tempo-tarefas.js` (nome diferente de `nucleo/linha-do-tempo.js`,
que já existe - scripts clássicos dividem o escopo global).
- **Desenho**: cabeçalho por dia (Atrasadas / Hoje · terça 13 / Amanhã / "sexta 16" / Sem data, com
  "N abertas"), hora grande à esquerda, trilho com uma bolinha por tarefa. Cabeçalho e marcador são
  `<div>` dentro da `<ul>` de propósito: `#lista-tarefas li` continua contando só tarefa (testes).
- **Concluir**: tocar a bolinha (ou "concluir" nas ações) enche de verde, desenha o visto e risca o
  título; ~240 ms depois a linha fecha o espaço. Pegadinha: o `loadTasks()` do sucesso re-renderiza
  a lista e cortava a animação no meio - agora só recarrega depois que a linha saiu.
- **Agora vivo**: marcador com a hora atual entre as tarefas de hoje; a próxima respira com "em 40
  min", a que passou fica avermelhada ("passou há 1h15"), atrasada mostra "ontem"/"seg 12" e "era às
  HH:MM". Atualiza a cada 30 s só com a aba aberta.
- **Cascata e reordenar**: abrir a aba faz a lista entrar em cascata (14 primeiros); quando a lista
  muda, quem já estava desliza pro lugar novo (FLIP com `translate`) e tarefa nova/alterada acende.
  O `<li>` de tarefa que não mudou é reaproveitado (cache por JSON).
- **Ações**: tocar o título abre concluir / pra amanhã (novo, usa `/api/tarefas/adiar`) / quebrar /
  esforço / corrigir. Pegadinha de especificidade: o `card.css` pinta `.btn-com-icone` com 2 ids + 6
  classes (52 px) - as regras da linha usam `:not(#_)` pra somar um id.
- Auditoria R3 (toque >= 44 px, texto >= 12 px): bolinha com alvo de 44 px e o título (que abre as
  ações) com `padding-block`/`margin-block` de 11 px - área de toque maior sem mudar o espaçamento.
- Testes de navegador clicam `.tl-ponto`; parte pura em `tests/js/tarefas_linha_do_tempo.test.js`.
  `prefers-reduced-motion` desliga cascata, respiração, onda e deslize. SW v69.

## 2026-10-13 - Cards do chat "premium": profundidade, montagem e toque

Prévia aprovada pelo Alex com tudo ligado ("não ficou nada exagerado"):
https://claude.ai/artifact/Fc5S8yNRv3NWJUTa5vfthr. Vale pra todo card (histórico também, só a
chegada é exclusiva da resposta nova); `prefers-reduced-motion` desliga inclinação, luz, fio e
montagem.
- **Profundidade e luz** (`cards-premium.js` `ligarToque`, ligado por `Cards.ligar`): o card inclina
  até 4,5° pro lado do dedo/mouse e um brilho segue o toque; segurar 140 ms afunda (`scale .975`).
  Pegadinha: tem que ser `rotate`/`scale` (propriedades separadas) - a chegada anima `transform`
  com fill both e engolia qualquer transform de toque (o `:active` antigo nunca aparecia).
  `.cards-grupo` dá a perspectiva e o JS centra o ponto de fuga no card tocado.
- **Card que se monta**: nasce abrindo do canto de cima (clip-path, lado da bolha da IA), um fio de
  luz corre a borda uma vez (`.card-fio-borda` + `@property --fio-ang`) e as peças de dentro entram
  uma a uma (WAAPI com `translate`, pra não brigar com o transform das animações de cada tipo).
- **Toque que responde**: card com `.card-expande` abre/fecha no toque (gastos: os 3 maiores
  lançamentos, que o servidor já mandava e a tela ignorava); tarefa pendente nos cards de tarefas
  conclui arrastando pra direita (72 px; a caixinha de sempre por baixo faz a chamada).
- **Clima**: curva da temperatura hora a hora em cima das barras de chuva (mesmas 8 colunas, sem
  gap), se desenhando com os pontos pingando. SW v68.

## 2026-10-13 - Suíte de testes de ~28 min pra ~6 min + bug do iPhone ao voltar pro app

- iPhone: sair do app com o teclado aberto e voltar deixava campo do chat, nota e barra de abas
  pendurados no meio da tela. `nucleo/init.js` fecha o teclado ao sair e re-mede a tela na volta,
  no `pageshow` e quando o teclado recolhe. SW v67. Teste: `tests/test_volta_do_segundo_plano.py`.
- `scripts/testes.py`: suíte inteira em 3 filas paralelas (pytest-xdist, dependência nova só de
  teste, sem vulnerabilidade no OSV): rápida (por arquivo), `test_app.py` espalhado teste a teste,
  navegador num processo só. 27min46s -> 6min18s, tudo verde.
- `tests/conftest.py`: hash do PIN rápido só nos testes (scrypt custava ~160 ms por setUp com
  login); a "IA morta" dos testes virou um socket que derruba a conexão na hora (no Windows a porta
  fechada levava 2 s por tentativa, ~15 s por página nos testes de navegador).
- Testes que dependiam da ordem ou do relógio: `test_claude_client.py` usava o banco que estivesse
  apontado (sozinho, o de produção! conferido: nada foi gravado lá) e agora tem banco próprio;
  `test_app.py` não conta mais a "pausa rápida" da água (falhava nos 5 primeiros minutos das
  9h/11h/13h/15h/17h); `test_limpa_a_animacao.py` lê a ordem da lista em vez de supor; prompt do
  chat com a regra de fonte única de volta no topo.

## 2026-10-13 - Painel puxando assunto: fechar o dia e padrões da semana

- `conversa_proativa.py`: duas mensagens que a IA abre sozinha no chat, por template (zero chamada de
  IA): **fechar o dia** (21:00-23:30) com o que foi feito, o que ficou pendurado (atrasadas
  inclusive) e card com "passar pra amanhã"; **padrões da semana** (domingo 19:30-23:30) com os 7
  dias e até 3 observações tiradas dos números (melhor dia, comparação com a semana anterior, água,
  gasto, voo, atrasadas acumulando). Gravadas em `chat_mensagens` (o chat abre com elas) e avisadas
  por push.
- Ligado no `verificar_e_notificar` antes do retorno antecipado do push, então publica no chat mesmo
  sem push configurado. Dedupe `fechar_dia_chat`/`padroes_semana_chat` no `notificacoes_enviadas`;
  o push antigo de template das 21h não sai mais quando o novo já saiu.
- `POST /api/tarefas/adiar` `{ids}`: move pra amanhã só tarefa aberta, não recorrente, com data até
  hoje (mantém o horário). O que ele riscou no próprio card não é adiado.
- Cards `fechar_dia` (anel feitas/total, chips água/voo/quiz/gasto, checkboxes que concluem com
  confete, botão que vira "Passei N pra amanhã") e `semana` (barras com o melhor dia brilhando,
  água cheia x parcial, dia com voo, deltas vs semana anterior). `static/js/cards-rotina.js` +
  `static/css/secoes/hoje/cards-rotina.css`; gasto/água mascarados no modo visitante. SW v66.
- Testes: `tests/test_conversa_proativa.py`, `tests/js/cards_rotina.test.js`.

## 2026-10-13 - Professor de aviação 2: quiz da banca com repetição espaçada

- Ferramentas `fazer_pergunta_aviacao` (a IA escreve a pergunta na própria chamada: enunciado, 4
  alternativas, certa, explicação - sem chamada extra), `revisar_pergunta_aviacao` e
  `responder_pergunta_aviacao` (resposta por texto/voz: "é a B"). Sempre nos 3 temas fixos
  (`estudo.TEMAS`, o enum da ferramenta é testado contra eles).
- `estudo_quiz.py`: caixas de Leitner por pergunta - errou volta amanhã, acertou espaça 3/7/14/30/60
  dias; revisão puxa a mais atrasada; responder de novo uma já respondida e não vencida devolve o
  resultado guardado (não dá pra "farmar" acerto pelo histórico). Linha no contexto do chat:
  revisões vencidas + acertos da semana.
- Card `quiz_aviacao`: alternativas clicáveis (POST `/api/estudo/responder`, `rotas/estudo.py`), a
  certa assenta com tique desenhado + confete, a errada balança 2px, a explicação abre por
  grid-rows, bolinhas de nível da revisão enchem. O card nunca recebe a resposta antes dele responder.
  `Cards.registrarAcao` (novo) deixa um tipo de card tratar o próprio clique.
- Prompt: bloco PROFESSOR (texto curto porque o card já mostra; em modo voz lê enunciado e
  alternativas; corrige como professor). Roteador: "quiz", "me testa", "me faz uma pergunta" vão pro
  Sonnet (pergunta de prova precisa do modelo melhor).
- Testes: `tests/test_estudo_quiz.py`, `tests/js/cards_aviacao.test.js`.

## 2026-10-13 - Aba Tarefas em ordem de horário

- `GET /api/tasks` (lista padrão) agora sai em ordem de agenda: por dia (atrasada e hoje primeiro),
  dentro do dia por horário, tarefa sem horário fecha o dia dela, sem data vai pro fim (a mais nova
  primeiro). Antes era por data de criação e o dia ficava embaralhado (10:00, 10:30, 08:00...).
  Teste: `tests/test_tarefas_ordem.py`.

## 2026-10-13 - Professor de aviação 1: briefing meteorológico no chat

- Ferramenta `briefing_meteo_voo` (chat): METAR + TAF oficiais (aviationweather.gov, `metar.py`)
  decodificados por `briefing_voo.py` - categoria VFR/MVFR/IFR/LIFR, vento, teto, visibilidade,
  QNH, fenômenos traduzidos (`-DZ` -> "chuvisco fraco", `TSRA` -> "trovoada com chuva"), TAF em
  horário de Brasília ("09:00 → amanhã 09:00"). SSBL não publica METAR -> usa SBNF e avisa. Sem
  ICAO usa a origem do próximo voo (hoje/amanhã) ou `ICAO_PADRAO`. Mesma regra do `metar.py`: só
  conversão, nunca "pode voar"; o card sempre diz que a decisão é dele e do instrutor.
- Windy: só link ("Abrir no Windy", coordenada da tabela de aeródromos da região). A API pontual
  deles é paga e a chave de teste devolve dado embaralhado - não serve pra briefing.
- Card `briefing_voo` (`static/js/cards-aviacao.js` + `cards-aviacao.css`): cor do card = categoria,
  selo grande da categoria, rosa dos ventos com a seta que "procura" o vento e assenta (balança de
  leve se tem rajada), réguas de teto/visibilidade com os limiares das categorias, linha do tempo do
  TAF por cor, boletim bruto recolhível. `abrir_link` agora aceita Windy além do Google Maps.
- Prévia com o boletim real: https://claude.ai/artifact/1hy2cidtupDuff2YTLdkqb
- SW v65. Testes: `tests/test_briefing_voo.py`, `tests/js/cards_aviacao.test.js`.

## 2026-10-13 - Cards interligados (vários assuntos, um fio só)

- Resposta com 2+ cards (ex: um áudio com voo + água + viagem + dia) ganha a **costura**: um fio
  de luz na coluna do avatar que sai da IA e liga um card no outro, com um nó na altura do título
  de cada card, na cor dele (`CardsPremium.costurar`, `static/js/cards-premium.js` +
  `cards-premium.css`). Resposta nova: cada trecho se desenha quando o card de baixo chega e no
  fim uma luz percorre o fio todo, piscando cada nó ao passar. Histórico abre com o fio parado;
  `prefers-reduced-motion` não anima. Posição por `offsetTop` (o card ainda está deslocado pela
  animação de entrada) e `ResizeObserver` reposiciona sem reiniciar a animação quando um card
  vivo cresce ou a aba volta a aparecer.
- Prévia: https://claude.ai/artifact/UKM4k81ZWHY2mmcmyc5Ufk (CSS/JS reais, "com o fio / sem o fio").

## 2026-10-13 - Chat AO VIVO + jeito de falar de gente

- **Resposta aparece enquanto a IA escreve**: rota nova `POST /api/chat/stream` (text/event-stream;
  `rotas/chat.py`). O pipeline (`_processar_mensagem_chat`) roda numa thread com conexão própria;
  `claude_client.ao_texto(aviso)` faz o loop de tool-use usar `messages.stream` e avisar `texto`
  (pedaço) e `recomeca` (texto de antes de ferramenta / rodada refeita por limite); no fim vem
  `fim` com o MESMO corpo do `/api/chat` (cards etc.) ou `erro`. Waitress entrega cada evento na
  hora (`send_bytes=1`, medido: 0,4 s entre pedaços = 0,4 s na chegada). `/api/chat`, Telegram e
  testes antigos seguem com `messages.create` (sem aviso ligado nada muda).
- Front (`chat.js`): a bolha dos pontinhos vira a resposta; `criarEscritaAoVivo` pinga palavra por
  palavra com o blur+fade de sempre, ritmo de digitação (±30%, pausa em pontuação) que acelera
  sozinho quando acumula. Stream indisponível → cai no `/api/chat` antigo. Brain dump continua igual.
- **Jeito de falar** (prompt do chat): bloco "JEITO DE FALAR" - português do dia a dia, confirmação
  como pessoa ("Anotei o dentista amanhã às 14h") e nunca como sistema, lista de vícios de IA
  proibidos ("Claro!", "Espero ter ajudado", markdown em conversa...), reagir ao que ele contou,
  ligar os pontos da vida dele, resolver em vez de perguntar. Mensagem com vários assuntos: uma
  ferramenta (= um card) por assunto na mesma rodada e o texto vira só a "costura" (acabou a lista
  "-> Tarefa:"). Modo voz: pontuação pensada pra fala soar humana.
- Testes: `tests/test_chat_ao_vivo.py` (loop em modo stream, recomeça, rota SSE, erro, validação).

## 2026-10-13 - Prova de qualidade do chat (`scripts/eval_chat/`)

- `casos.json`: 33 mensagens realistas (registro rápido, dump de áudio misturando gasto + água + voo
  + tarefa, conversa/estudo de aviação/desabafo) com checagens determinísticas: ferramentas que
  DEVEM ser chamadas (validadas contra `CHAT_TOOLS`), faixa de tamanho, frases com cara de robô
  ("Claro!", "Ótima pergunta"...), excesso de emoji, linhas criadas no banco e qual modelo atendeu.
- `rodar.py`: sem `--rodar` só valida o JSON + estima o custo (e já avisa se o roteador
  `e_conversa` discorda do modelo esperado de algum caso). Com `--rodar` roda cada caso por
  `app._processar_mensagem_chat` contra uma COPIA temporária do banco (snapshot `backup()` a partir
  de conexão somente-leitura; restaurada do zero a cada caso; chat/resumo zerados), com
  CalDAV/Uber/push/Telegram/HTTP de escrita desligados por patch. `--juiz` = nota 1-5 do Haiku
  ("parece gente" / "resolveu"). Trava `--teto-usd` (padrão 1,00). Saída em tabela +
  `resultados/AAAA-MM-DD-HHMM.json` (gitignored). `tests/test_eval_chat.py` (IA mockada).

## 2026-10-13 - Backup automático diário do banco

- Novo `backup_diario.py` (sem dependência nova): snapshot consistente via `sqlite3.backup()` em
  `data/backups/painel-AAAA-MM-DD.db` (ou `BACKUP_DIR`), mantém os 14 mais recentes. Roda todo dia
  às 3h30 e **ao subir o app se o último backup tiver mais de 24 h** (o PC nem sempre está ligado
  de madrugada). Escreve num `.parcial` e só então troca pelo definitivo; qualquer erro só vai pro
  log, nunca derruba o app. Convive com o backup semanal (+ Telegram) que já existia: nomes e
  rotação separados. Registrado em `app.iniciar_scheduler`; `tests/test_backup_diario.py`.

## 2026-10-13 - Cards do chat: acabamento "premium"

Camada nova por cima do registro, sem mexer em renderizador nenhum
(`static/js/cards-premium.js` + `static/css/secoes/hoje/cards-premium.css`; SW v64). Só em
resposta NOVA (`CardsPremium.animar` no chat.js, ao lado do `CardsVivos.animar`); histórico e
`prefers-reduced-motion` ficam no estado final.
- Chegada com profundidade (sobe, desfoque → nítido, overshoot leve) em cascata de 90 ms e um
  brilho na cor do card que atravessa o vidro uma vez.
- Selo de registro (transação, tarefa, lembrete, meta criada, hábito, água...): ícone do topo dá
  um pulinho com onda; consulta pura não ganha.
- Odômetro: valor do gasto, hora do lembrete, valores e % da meta rolam dígito a dígito (com
  motion blur) e voltam pro texto puro no fim; barra da meta enche do zero, meta batida brilha 2x.
- Tarefa concluída pelo card solta confete curtinho na cor do card (`Cards` chama
  `CardsPremium.festejar` depois do OK da API); Desfazer faz o card "expirar" antes de apagar.
- Toque: o card cede um tico (`:active`), menos quando o dedo está num botão/caixinha.
Prévia com o CSS/JS reais: https://claude.ai/artifact/H4fVSg6BKjycZPVDU5t1jT

## 2026-10-13 - Voz fala hora/número/sigla certo + chat responde com substância

- **Voz errava "14:30", "R$ 1.250,90", "180g", "TDAH"** (o `eleven_flash_v2_5` lê o texto cru e a
  normalização automática dele em pt-BR é só do plano Enterprise). Novo `fala_ptbr.py` (sem
  dependência nova): `normalizar()` transforma antes do TTS - horário ("catorze e trinta", "nove
  horas", "meio-dia", "meia-noite e trinta", "1h30min"), dinheiro (reais/centavos, "R$ 2 mil",
  "três milhões de reais"), unidades (kcal→calorias, g, kg, km, kt→nós, ft→pés, NM, hPa, °),
  %, datas (13/10, 13/10/2026, ISO, "primeiro de outubro"), ordinais (2º, 1ª), "3x", "3 x 4",
  "10-12", "~30", número solto com gênero pela palavra seguinte ("duas refeições", "duas mil
  calorias"), dígito a dígito pra telefone/0800, aviação (FL350, pista 09L, QNH 1013, ICAO SBSP
  soletrado) e siglas (TDAH, IFR, VFR, METAR→"métar", TAF, ANAC, ok, app...). Tira markdown,
  emoji, setas e URL. Erro interno → devolve o texto original (nunca derruba a fala).
  `voz_premium.sintetizar` normaliza antes da chave do cache (áudio antigo mal pronunciado não é
  reaproveitado) e a cota mensal conta o texto normalizado. Testes: `tests/test_fala_ptbr.py`.
- **Chat respondia raso**: o prompt mandava "direto e curto SEMPRE" e tudo ia pro Haiku 5.5 com
  500 tokens. Agora (1) prompt separa registro (1 frase, o card mostra o resto) de conversa de
  verdade (pergunta, explicação, conselho, estudo, desabafo → 2-4 parágrafos pessoais, usando o
  que sabe dele, fechando com 1 próximo passo; frases que soam bem em voz alta); (2)
  `ia/roteador_chat.e_conversa()` (independe da flag do roteador antigo) detecta conversa e o
  chat usa o novo bloco opcional `"conversa"` do `ia/config.d/chat.json` (Sonnet 5, 1500 tokens)
  - registro ("gastei", "anota", "marca"...) continua no Haiku barato. `ia/core.py` valida o bloco.
  Regra do `sugerir_tema_estudo` ajustada: não inventa grade de estudo, mas explica conceito
  quando ele pergunta (com aviso pra conferir limite de regulamento na fonte oficial).
  Haiku (registro/papo curto) subiu de 500 pra 1000 tokens de saída pra não cortar resposta.
  Custo: conversa no Sonnet 5 sai ~20x o Haiku por mensagem (centavos); pra desligar, apagar o
  bloco "conversa" do chat.json.

## 2026-10-09 - Chat mais esperto + voz de verdade (Roberta) + modo conversa

- **Tarefa duplicada ao "colocar hora"**: nova tool `ajustar_tarefa` (muda hora/data de tarefa pendente existente;
  0 ou 2+ títulos batendo = erro, nunca chuta). Prompt manda nunca usar `registrar_tarefa` pra isso.
- **Hora de Brasília** em toda mensagem (linha "Agora:" no contexto do chat, `ZoneInfo("America/Sao_Paulo")`).
- **Clima**: `CIDADE_PADRAO=Brusque` no `.env`; tool `consultar_clima` (Open-Meteo `current` + resto do dia, ou
  previsão até 16 dias, qualquer cidade).
- **Trajeto**: tool `estimar_trajeto` (várias paradas, Google Routes). `maps_client.resolver_lugar` usa Places Text
  Search (viés ~50 km em Brusque) - "Aeroclube de Blumenau" vira o endereço exato. "casa" = `ENDERECO_CASA` (.env).
  Chaves `GOOGLE_MAPS_API_KEY` / `ENDERECO_CASA` só no `.env`.
- **Microfone do chat**: grava o áudio inteiro (MediaRecorder) e transcreve no Whisper/Groq
  (`POST /api/voz/transcrever`, reaproveita `telegram_captura.transcrever`); reconhecimento do Safari virou reserva.
- **Voz**: ElevenLabs plano Starter (~35 mil créditos/mês), voz Roberta. `eleven_v4_turbo` custa 0,5 crédito por
  caractere, então `ELEVENLABS_LIMITE_MES=65000` (caracteres). `voz_premium.MAX_CARACTERES` 300 -> 700; o botão
  "ouvir" lê a resposta inteira (`textoParaFala`), não só a primeira frase.
- **Modo conversa** (`static/js/secoes/hoje/conversa.js`, botão `#chat-conversa` ao lado do microfone): ouve ->
  3 s de silêncio encerra a fala (limiar calibrado no ruído do ambiente) -> transcreve -> chat com `modo: "voz"`
  (`MODO_VOZ_INSTRUCAO`: 2-4 frases faladas, sem lista/markdown) -> Roberta fala -> microfone reabre. Encerra no
  toque, com 12 s sem fala ou ao sair do app. Microfone é solto antes de ela falar (no iPhone o som sairia pelo
  alto-falante de ligação). Service worker v42.
- **Correção depois do 1º teste no iPhone** (fala picotada / microfone travando): motor único `criarGravacao` em
  `hoje/chat.js` pros dois botões. Grava sem timeslice (`start()` - pedaços de 0,5-1s geravam mp4 com buracos no
  iPhone), estado por gravação (um "stop" atrasado zerava a gravação nova e travava o botão), detector de silêncio
  com piso de ruído contínuo + histerese (antes calibrava nos primeiros 400ms - se ele já começava falando, o limiar
  ia lá em cima e cortava). "Pode falar…" só aparece com o microfone de fato gravando; o botão de ditado some durante
  a conversa. Service worker v43.

- **Card de rota** (`type: "rota"`, aditivo em docs/CARDS.md): `estimar_trajeto` declara `_efeito` `rota` com as
  paradas, km/tempo e o link do Google Maps (`maps_client.link_rota`, Maps URLs `api=1` com `place_id` de cada
  parada). Action nova `abrir_link` - o front so aceita `https://www.google.com/maps/`. "daqui" = conta parte de
  casa e o link sai sem origem (o Maps usa a localizacao real). Sinal do modo conversa trocado pelo "Suave".
  Service worker v46.

- **Localização do celular** (`static/js/nucleo/localizacao.js`): GPS ao abrir o app e a cada mensagem do chat
  (reaproveita leitura de até 5 min; espera no máximo 2,5 s). Vai no corpo do `POST /api/chat` (`local`), nunca na
  URL. `app._local_do_celular` valida (descarta > 6 h, precisão > 5 km, 0,0) e completa com o endereço aproximado
  via `geocode_nominatim.reverso` (OpenStreetMap, mesma política 1 req/s + cache ~100 m; o Geocoding do Google
  pede faturamento nesse projeto). Contexto do chat ganha "Localização atual do Alex"; `consultar_clima` sem cidade
  usa o GPS; rota "daqui" parte do GPS (`maps_client` aceita "lat,lon"); `registrar_tarefa`/`registrar_lembrete`
  ganham `no_local_atual` -> coluna `local` (migração `202610091200_loc_tarefa_lembrete_local.sql`), mostrada nos
  cards com um pin. Pegadinha: dentro de `_processar_mensagem_chat` o nome `local` já era a regra do
  classificador local - a localização chama `local_gps`. Service worker v47.

- **Extrato da CIV Digital (ANAC) no diário de voo**: não existe API da ANAC (CIV só pelo SACI/Super App com
  gov.br). Importados os 44 voos dos prints do Super App (`fonte = 'civ'`) - somam exatamente 49:24 como o
  consolidado oficial (36:54 instrução, 11:00 solo, 1:30 copiloto); 4 sessões de simulador ficam no diário mas
  fora do total (igual a CIV). Migração `202610091400_civ_voos_aeronave_funcao.sql` (aeronave, funcao, tipo,
  fonte); `voos.eh_simulador` filtra resumo/histórico/"dias sem voar"; `consultar_voos` devolve horas por função
  e por aeronave, HH:MM e simulador à parte. Pegadinha: `chat_consultas._hhmm` já existia (hora de evento) - o
  de horas chama `_horas_hhmm`.

## 2026-10-13 - Widget do iPhone: próximo compromisso + comida do dia

Pedido do Alex: "conseguiríamos colocar widgets?". Ele escolheu o conteúdo: próximo compromisso/tarefa e comida
do dia, e tocar no widget abre o chat.
- Já existia a base (Fase 7: `GET /api/widget` com `PAINEL_WIDGET_TOKEN`, `scriptable/scriptable-widget.js`), mas
  nunca tinha sido ligada.
- `/api/widget`: novo `comida` (`{kcal, proteina_g, refeicoes, meta_kcal, meta_proteina_g}`, via `refeicoes.do_dia`/
  `meta_do_dia`; se falhar vira null e não derruba o resto) e `foco.hora`. Agora são 9 chaves no topo.
- Script do Scriptable (estado normal redesenhado, mesmos tokens do app):
  - pequeno: PRÓXIMO (hora grande + "em 25 min" + título) e COMIDA HOJE (kcal/meta + barra);
  - médio: duas colunas, com proteína e a segunda barra;
  - bloqueio retangular: "14:30 · título" / "1.066 / 2.550 kcal · P 102 g";
  - bloqueio redondo: % da meta de kcal.
  - Barras feitas de stacks, sem DrawContext. `widget.url = <url>/?aba=assistente` (só http/https).
  - Estados vazio/erro/sem conexão e o cache "atualizado há X" ficaram como estavam.
- **Configurações › iPhone › Widget do iPhone**: passos e **Copiar script** / **Copiar ajuste** (`location.origin|token`).
  Vem de `GET /api/widget/instalacao`, que exige login com PIN, é recusada no modo visitante e não abre com o token do
  widget. Assim nada precisa passar do PC pro celular na mão. Service worker v62.
- **Bug no 1º teste no iPhone (sem prévia nenhuma)**: o Scriptable também tem `module` (cada script é um módulo), então
  o guard `typeof module !== "undefined"` fazia o script só exportar e nunca chamar `main()`. Agora roda `main()` a menos
  que seja Node (`process.versions.node`). Teste novo roda o script num `vm` igual ao Scriptable.
- **Copiar script** já sai com `PAINEL_URL`/`TOKEN` preenchidos (`location.origin` + token), então a prévia no app mostra dado
  real e o Parameter virou opcional. Service worker v63.
- Limite do iOS: link de widget abre no Safari, não no app da tela inicial (o login por PIN no Safari dura ~31 dias).
  O painel chega no iPhone pelo Tailscale (`tailscale serve`, porta 8443, só dentro da rede dele).
- **Diagnóstico**: o erro do script aparece no próprio widget e vai pro painel (`POST /api/widget/erro`). As chamadas do
  widget ficam em `data/widget.log` (sem query string, então o token não entra).
- **Tela de bloqueio redesenhada** (Alex: "algo mais bonito ou maior, fica muito pequeno"). O iOS só tem três tamanhos
  fixos ali, então o ganho vem de usar melhor o espaço:
  - redondo: anel de progresso estilo Atividade, desenhado em `DrawContext`, com a % da meta de kcal no meio. Sem comida,
    mostra a hora do próximo. Vazio, erro e sem dados usam o mesmo anel com o trilho vazio.
  - retangular: hora grande + "em X", título e barra de kcal desenhada.
  - **Parameter `proximo` ou `comida`**: o retangular mostra só aquilo, com letra de 26 pt. Dois lado a lado ocupam a fileira
    inteira. `resolverConfig` só trata o Parameter como configuração se tiver "|" ou começar com http, então o formato
    antigo `URL|TOKEN` continua valendo.
  - linha acima do relógio (`accessoryInline`): "14:30 Dentista · 1.066 / 2.550 kcal".
  - Tudo em branco com alfa (o iOS pinta a tela de bloqueio com vibrancy), sem `textColor` e sem fundo.
  - Mocks de `DrawContext`/`Path`/`Point`/`Rect` nos testes JS. A prévia visual foi conferida num shim em canvas
    (Playwright, 390 px).
- **Widgets redesenhados a fundo** (Alex: "vai fundo, animações, cards, cada vez mais bonito"). Widget do iOS não anima
  (o iOS mostra uma "foto" parada), então o "vivo" vem do fundo e da saudação acompanhando a hora, dos anéis e do
  `refreshAfterDate` perto do próximo compromisso. Escolhas dele: fundo que muda com a hora, grande com tudo, criatividade
  livre no resto.
  - API (`/api/widget`): `agenda` (até 6 itens de hoje com horário, `{hora, titulo, em_minutos, tipo, concluido}`,
    fuso do iCloud convertido, nunca derruba o resto) e `comida.carbo_g`/`gordura_g`. São 10 chaves no topo.
    Feito por um subagente Haiku 5.5 e revisado.
  - O "PRÓXIMO" agora sai do 1º pendente da agenda (`proximoDe`). Antes, compromisso do iCloud nunca aparecia, porque o
    `foco` da API só pega tarefa/hábito.
  - Tela de início:
    - fundo desenhado por período (madrugada/manhã/tarde/pôr do sol/noite), com gradiente e dois brilhos suaves;
    - cards de vidro e anéis de comida (kcal por fora, proteína por dentro, dourado quando bate a meta);
    - símbolos da Apple;
    - **grande** novo: saudação, próximo em destaque, "depois" com quanto falta, comida, hábitos em bolinhas, conta.
    - Parameter `comida`/`agenda` muda o foco do pequeno e do médio.
  - Tela de bloqueio (subagente Sonnet 5.5 numa worktree; integrei só o bloco dela):
    - redondo: `aneis`, `proteina`, `contagem` (esvazia nas últimas 2 h) e `habitos`;
    - retangular: `agenda`, `dia` (linha do tempo desenhada), `habitos` e `macros`;
    - símbolos e linha do relógio por modo.
  - Bug de integração: as duas metades criaram uma `imagemPontos` e a do bloqueio sobrescrevia a da tela de início.
    A da tela de início virou `imagemPontosHabitos`.
  - Testes: mocks compartilhados em `tests/js/_scriptable_mocks.js` (fixture `JSON_COMPLETO`),
    `scriptable_widget_inicio.test.js` e `scriptable_widget_bloqueio.test.js`, que inclui uma matriz de modos × famílias ×
    payloads sem undefined/NaN.
  - Simulação no iPhone 17 Pro Max (artefato https://claude.ai/artifact/KvShwwd8LD5LQVdYieEDhy): o script real roda num shim
    da API do Scriptable em canvas/DOM, com controle de horário, cenários e arranjos da tela de bloqueio. O shim imita o
    espaçador "guloso" do SwiftUI. Os fontes ficam no scratchpad da sessão, não no repo.

## 2026-10-13 - Voz com barulho em volta, botão de mandar na hora, feriados e foto do prato

Pedido do Alex: "se tem voz de fundo ela pega e mistura", "depois que paro de falar demora muito pra mandar",
"saber quando é feriado", "mandar foto de um prato e ela dar gramas, carbo, proteína".
- **Voz de fundo** (3 camadas, sem mexer no gravador que já foi sofrido de acertar no iPhone):
  - `getUserMedia` pede `voiceIsolation` (Safari/iOS recente; ignorado onde não existe), além do
    `noiseSuppression`/`echoCancellation` que já tinha.
  - `criarGravacao` (`hoje/chat.js`) acompanha o volume típico da voz DELE (envelope `voz`) e anota os
    `trechos` em que ela estava ativa. Vão como `trechos_voz` pro `/api/voz/transcrever`, e
    `telegram_captura.texto_dos_trechos` descarta o trecho do Whisper que encosta menos de 20% nesses momentos
    (TV, gente conversando longe do microfone). Validação no servidor: `rotas/voz._trechos_voz` (≤200 pares, 0-600 s;
    se vier inválido, segue sem filtro).
  - O prompt de `ia/funcoes/fala.py` (limpeza da fala) tira frase solta de outra pessoa/TV que sobrou.
- **Demora pra mandar**: o silêncio agora é RELATIVO à voz dele (`VOZ_FRACAO_FUNDO = 0.22` do volume típico).
  Antes, a voz de fundo mantinha o som acima do limiar fixo e a gravação só acabava no tempo máximo. O modo conversa
  encerra com 1,5 s de silêncio (era 3 s). Ouvindo, o botão de enviar pulsa e manda na hora (placeholder
  "Pode falar… (➤ manda na hora)").
- **Calendário brasileiro** (`feriados.py`): tudo calculado em código, então não desatualiza.
  - Nacionais fixos (com 20/11) e móveis pela Páscoa (Meeus): Sexta-feira Santa é feriado; Carnaval, Cinzas e
    Corpus Christi são ponto facultativo e o chat nunca diz "é feriado" pra eles.
  - Brusque 04/08. A Data Magna de SC vai pro domingo, então é só comemorativa.
  - Contexto do chat: "HOJE é …" + próximos 45 dias com "muita gente emenda".
  - Tool `consultar_feriados(ano, mes)`.
- **Foto do prato** (`refeicoes.py`, `POST /api/chat/foto`, `ia/funcoes/visao.analisar_prato`, Sonnet 5 visão,
  ~US$ 0,01 por foto):
  - Câmera dentro do campo do chat (`#chat-foto`, `hoje/foto.js`). A foto é reduzida no celular pra ~1280 px JPEG.
    O que estiver escrito no campo vai junto ("só comi metade").
  - A IA estima cada item (gramas pela porção a olho + tabela TACO). A soma, o dia e a meta
    (`vida_assistente.metas_comida`) são calculados em código.
  - Tabela `refeicoes`; card vivo `refeicao` com Desfazer (`ENTIDADES_DESFAZIVEIS`). O card mostra ~kcal contando,
    as macros como fatia das calorias (P/C ×4, G ×9), os itens e "Hoje até agora" contra a meta de kcal e proteína,
    mais a dica e um aviso quando a confiança fica abaixo de 0,6.
  - O que comeu entra no contexto do chat (`refeicoes.linha_contexto`) e nos fatos do diário (`comida`).
  - Foto que não é comida responde "Não vi comida…" e não grava nada. No modo visitante a resposta é 403.
    A foto em si não é guardada.
- `contar()` dos cards vivos formata inteiro com milhar pt-BR (1.250). Service worker v61.
- **iCloud ligado** (o Alex preencheu `ICLOUD_USERNAME`/`ICLOUD_APP_PASSWORD` no `.env`). Teste real: lê os 3
  calendários dele (Pessoal/Trabalho/Lembretes), cria no 'Painel' e apaga. **Bug achado no teste real**: o iCloud
  recusa `event_by_uid` (REPORT por UID -> 412), então o Desfazer de evento nunca apagava nada.
  `caldav_client._achar_por_uid` tenta essa busca, depois `<calendário>/<uid>.ics` e por último varre o 'Painel',
  sempre conferindo o UID antes de apagar.
- Testes: `tests/test_foto_prato_feriados_voz.py` (19) + card `refeicao` em `tests/js/cards_vivos.test.js`.

## 2026-10-12 - Diário de cada dia: o chat sabe o que foi hoje e o que já passou

Pedido do Alex ("o date foi ontem e ele não sabe distinguir ontem de hoje... saber o que aconteceu cada dia").
Três causas encontradas no banco real:
- **Histórico sem data**: o chat mandava as últimas 20 mensagens pra IA sem data nenhuma. O "date às 20h" de
  sábado 10/10 chegava igual a uma mensagem de segunda, e a IA lembrava dele como se fosse hoje. O resumo da A5
  nunca tinha sido gerado (`dia` vazio nunca disparava a virada de dia).
- **Modo visitante esquecido**: ligado com 1 toque em Mais › Configurações em 10/10 e nunca desligado. Desde então o
  chat recusava toda alteração ("o painel está em modo visitante"), e não tinha nada na tela avisando.
- Nenhum registro do que aconteceu em cada dia.

O que mudou:
- **`diario.py` + tabelas `diario_dias` e `diario_anotacoes`**: cada dia que passou vira fatos do banco (tarefas
  feitas e não feitas, gastos, voos, treinos, notas, check-in) + 2 a 5 linhas de resumo escritas por IA
  (`ia/config.d/diario_dia.json`, Haiku) **só com as falas do Alex**. Foi testado com a fala do assistente junto, e o
  resumo copiava o erro dela ("teve date domingo"). O dia é sempre o de Brasília (o banco grava UTC), e tarefa do dia
  marcada como feita até 6h da manhã seguinte conta no dia dela. O agendador fecha os dias (máximo 1 chamada de IA
  por tick, até 3 tentativas, 7 dias pra trás); se a IA falhar, o dia fica só com os fatos.
- **Contexto do chat**: bloco "Diário dos últimos dias" com o nome de cada dia ("ontem (domingo 11/10)"). Mensagem
  antiga que ainda vai na íntegra chega marcada "[ontem (domingo 11/10), 21:54 - dia que já passou]". Mensagem de
  dia que já tem diário sai do histórico, exceto as das últimas 4 h (virada da meia-noite conversando)
  (`app._historico_com_datas`). O resumo da A5 agora recebe a data de cada mensagem. Há também uma regra
  "DATAS - HOJE x DIAS QUE JÁ PASSARAM" no prompt.
- **Tools novas**: `consultar_diario` ("o que eu fiz sábado?") e `anotar_no_diario`, pra quando ele corrige
  ("o date foi ontem"). A anotação vale mais que o resumo e aparece em tudo que lê o dia. `diario.resolver_dia_passado`
  sempre olha pra trás ("sábado" = o último que passou); o resolvedor de tarefa olha pra frente.
- **Modo visitante**: desliga sozinho em 60 min (`MODO_VISITANTE_MINUTOS`; sessão antiga sem hora = já desligado).
  Ligado, mostra um **selo em toda tela**, uma pílula âmbar acima da barra, na altura do +. O toque leva pro PIN
  já focado. A recusa no chat explica como sair. `GET /api/modo-visitante` devolve `minutos_restantes`.
  Service worker v60.
- Validado com IA real numa cópia do banco: "o que eu fiz sábado?" responde o dia certo, e "o date foi ontem" não
  vira mais lembrete de date hoje. Testes: `tests/test_diario.py` (19). `test_assistente_vida` dependia do dia da
  semana (rotina de segunda falhava numa segunda) e foi corrigido.

## 2026-10-12 - Áudio do chat igual ChatGPT/Gemini: "posso errar que ele entende"

- Reclamação do Alex: o áudio "não tá legal" - entende palavra errada, não aceita ele se corrigir no meio, e não
  dá pra ver o que está acontecendo. Escolhas dele: **manda direto** (não cai mais na caixa pra conferir).
- **Barra de gravação** (chat.js `initGravadorChat`): toque no microfone -> o campo vira barra com X (cancelar),
  ponto vermelho pulsando, onda da voz de verdade (RMS do microfone via `criarGravacao().nivel()`, 30 barras da
  direita pra esquerda) e tempo; o enviar fica vermelho e manda o áudio.
- **Manda direto** (`enviarAudio`): bolha dele "Entendendo..." -> Whisper -> **limpeza** -> a bolha ganha o texto
  limpo com um microfone pequeno (assenta com blur-fade) -> `/api/chat` com `audio: true`. Falhou: a bolha
  oferece "Tentar de novo" com o MESMO áudio.
- **Limpeza da fala** (`ia/funcoes/fala.py`, config `limpar_fala` = Haiku 4.5, ~0,6-1,2 s medido): aplica
  autocorreção ("às três, não, às quatro" -> "às quatro"), tira muleta/gagueira e conserta nome mal ouvido com o
  vocabulário dele (`app._vocabulario_do_alex`: apelidos de lugar, aeronaves, pessoas, tarefas abertas). Nunca
  acrescenta nada; saída suspeita (longa/curta demais) ou falha = vai o texto cru. Até 3 palavras nem chama a IA.
  Testado com a IA real: "voo lá em blume nau no PR lon" -> "voo lá em Blumenau no PR-LOM".
- `/api/chat` com `audio: true` (e o modo conversa) ganha `AUDIO_INSTRUCAO`: entender pela intenção, vale o que
  ele disse por último, só perguntar antes de agir se valor/data/nome crítico ficou ambíguo.
- `/api/voz/transcrever` devolve `error` além de `erro` (o painel lê `error`: antes aparecia "Erro inesperado
  (HTTP 502)" em vez da mensagem). SW v59.

## 2026-10-11 - Excluir tarefa arrastando pro lado (sem concluir)

- Pedido do Alex: excluir tarefa sem marcar como concluída. Escolha dele: **arrastar pro lado**, igual ao Mail do
  iPhone (`static/js/secoes/tarefas/arrastar-excluir.js`). Arrasta e aparece "Excluir" vermelho com lixeira; soltar
  no meio deixa aberto (toque fora fecha); arrastar até 56% da largura acende o vermelho (+ vibração) e exclui
  direto. Rolagem vertical continua do navegador (`touch-action: pan-y` + decisão pelos primeiros 9 px). Os filhos
  do item deslizam via `--arrasto` (sem embrulhar - o CSS da aba usa `li.item > .item-linha`).
- Sem "tem certeza?": a linha sai (conteúdo pra esquerda, depois a altura fecha) e um toast "'X' excluída ·
  Desfazer" fica 5 s acima da barra de abas, com barrinha de tempo; o + flutuante sai de cena enquanto isso.
- Backend: `DELETE /api/tasks/<id>` (visitante 403, modelo de rotina 404) e `app.apagar_tarefa_com_desfazer`
  (usado também pela IA): guarda a linha + os passos (subtasks) e o Desfazer devolve tudo com o mesmo id. Dia de
  rotina = **pula só hoje** (tabela nova `tarefas_puladas`; sem ela `materializar_tarefas_recorrentes` recriava a
  tarefa no próximo tick) - o Desfazer tira o pulo. A IA (`apagar_tarefa`) agora apaga tarefa com passos e dia de
  rotina também. SW v58.

## 2026-10-11 - Transcrição: corta o eco da lista de vocabulário

- Print do Alex: a fala terminou com "Bursque, Bblumenau, aeroclube, CIV, ANAC, SSBL, PR-LOM, PT-XXW, Fiorino,
  contabilidade, notas fiscais, Roberta." - não foi ele: é o `PROMPT_TRANSCRICAO` repetido pelo Whisper (alucinação
  conhecida quando o áudio termina em silêncio). `telegram_captura.tirar_eco_do_prompt` corta do fim uma enumeração
  de 4+ itens curtos em que 60%+ batem (aproximado, difflib >= 0,75) com a lista, e a frase de abertura do prompt se
  vier. Fala normal com os mesmos nomes ("passa na contabilidade, pega as notas fiscais, depois Fiorino") fica intacta.

## 2026-10-11 - Assistente de vida: "acordei agora, monta meu dia"

- **Pedido do Alex**: abrir de manhã, contar o dia ("acordei agora, tenho números da empresa, CND, voo em
  Blumenau às 14h, passar na obra") e receber o dia inteiro com hora, incluindo quando comer pra ganhar massa.
- `vida_assistente.py` (novo, puro): perfil (peso da última medida - **lido pelo `db._dnum`, o valor é
  criptografado em repouso**; altura, idade pelo nascimento, objetivo, academia), meta de comida calculada em
  código (Mifflin-St Jeor x1,5 + 350 kcal pra ganhar massa; 2 g/kg de proteína; 5 refeições), rotinas fixas
  (voo: 30 min de briefing antes + 30 de debriefing depois, configuráveis; se arrumar), lugares com apelido
  (`configuracoes.lugares_apelidos`: "obra" -> o loteamento da obra; "aeroclube"; ICAO
  SSBL -> aeroclube) e "acordou hoje às". Tudo vira linhas no contexto do chat.
- Ferramentas novas do chat: `planejar_dia` (cada bloco vira tarefa com hora; tarefa que já existe com o mesmo
  nome só ganha a hora; um card "Dia montado" com a trilha e um Desfazer pra tudo), `registrar_acordei`,
  `atualizar_perfil`, `salvar_lugar_apelido`, `apagar_tarefa` (volta inteira no Desfazer, mesmo id - entidade
  `tarefa_apagada` com a linha guardada na lista fechada `db.TAREFA_RESTAURAVEL`), `ajustar_renda`; `registrar_voo`
  ganhou `hora` no schema (o executor já aceitava).
- **Permissão de editar (pedido do Alex)**: `ajustar_gasto`/`ajustar_renda` corrigem o VALOR que ele digitou
  quando ele diz que errou (`EDICAO_COLUNAS` ganhou `amount` em expenses/incomes e `local` em tasks). Banco
  (bank_transactions) e construtora continuam fora - nem estão na lista. Modo visitante mascara o valor no card.
- Prompt "ASSISTENTE DE VIDA - MONTAR O DIA": começa de quando acordou, durações realistas + folga, trajeto real
  (`estimar_trajeto` entende apelido), voo num bloco só, nunca mais de 4 h sem comer (lanche pra levar no voo),
  academia sugerida só com o ok dele, responde em linhas "HH:MM - o que".
- **Bug achado no teste com a IA real**: o Haiku 5.5 pensa antes de agir e "monta meu dia" gastava >4000 tokens
  só pensando - a rodada voltava cortada e o chat respondia "Beleza." sem montar nada. Degrau novo
  `MAX_TOKENS_CHAT_TETO = 12000` (500 -> 4000 -> 12000, só paga o que gera), `RODADAS_MAX` 4 -> 6, e rodada cortada
  sem texto agora diz que não terminou em vez de "Beleza.".
- Avisos: voo avisa a hora de sair pra chegar no BRIEFING, indo pro aeroclube (origem do voo, não o destino);
  refeição do plano ("Comer: almoço - ...") avisa "Hora de comer" com o que comer, não leva o aviso de 30 min e
  nunca conta como date. Card: "Comer:" vira ícone de prato, "Voo" de avião, "(até HH:MM)" vai pra coluna da hora
  (`Cards.partesTarefa`), dia todo novo sem 13 selos "nova". SW v57.
- Testado com a IA de verdade numa cópia do banco (mensagem dele): monta 13 blocos, trajeto Brusque-aeroclube
  63 min, lanche pra levar antes do briefing, corrige "errei, foi 58" e apaga "já fiz ontem".

## 2026-10-11 - Notificações de verdade + "hora de se arrumar"

- **Bug: NENHUM aviso automático saiu, nunca.** O painel subia com `waitress app:app`, que não chama
  `iniciar_scheduler()` (só o `wsgi.py` chama). O iPhone estava inscrito e `notificacoes_enviadas` estava vazia -
  ontem "Visitar a irmã 17:00" e "Date 20:30" passaram sem aviso. `iniciar_painel.bat` agora sobe `wsgi:app`;
  primeira checagem 30 s depois de subir (não espera 5 min).
- **Heartbeat**: `_AGENDADOR` + `estado_agendador()`; `/api/push/status` devolve `agendador.ligado`. A linha
  Notificações (Mais › Configurações) mostra "Parado - reinicie o painel" se o agendador não rodar - o mesmo
  bug nunca mais fica invisível.
- **Hora de se arrumar / Hora de sair** (pedido do Alex: "demoro 40 minutos pra me arrumar" pra date/festa):
  `notificacoes.plano_se_arrumar` reconhece compromisso de sair pelo título (date, festa, jantar, aniversário,
  balada, happy hour...) e conta de trás pra frente: hora - trajeto (Google, de casa até o `local` da tarefa, 1
  consulta por local por dia e só a menos de 4 h; sem local = 15 min de folga) = sair; menos o tempo de se arrumar
  = começar. Pra esses, o "daqui a pouco" de 10 min sai de cena (chegaria tarde). Tarefa "se arrumar" já marcada
  pelo Alex não duplica. Tempo em `configuracoes.tempo_se_arrumar_min` (padrão 40), muda pelo chat com a tool
  nova `ajustar_tempo_se_arrumar`; o contexto do chat mostra o tempo e o prompt manda organizar o dia de trás
  pra frente dizendo a hora de começar a se arrumar e de sair.
- **Aviso ~30 min antes** de tarefa com hora (`tarefa_preparo`, 15-34 min antes) - 10 min era pouco pra largar o
  que está fazendo. Os três tipos novos furam o horário silencioso (são presos a horário) e aparecem em
  Assistente › Avisos pra desligar.
- **Push melhor**: payload com `url` (`/?aba=tarefas`, `construtora`, `gastos`, `aviacao`...) e `tag`
  (`tipo-id`: repetido substitui em vez de empilhar, com `renotify`), TTL de 6 h. Toque no aviso abre na aba
  certa: app aberto troca de aba sem recarregar (postMessage do SW), fechado abre direto. SW v56.

## 2026-10-10 - Card da Construtora: 4 números prontos + "Ademir paga"

- **Decisão do Alex (substitui a regra A10 "nunca lucro/margem/VGV")**: "Entradas x Gastos" saiu (parecia prejuízo -
  comparava todo gasto, até de obra recém-começada, só com o que já entrou). O card mostra 4 números prontos da
  construtora v3.99.90+: **Dinheiro hoje** (`saldo_caixa`), **A receber das vendas** (`a_receber`), **Lucro das
  obras prontas** (`lucro_obras_fechadas`, verde, com "N obra(s) fechada(s)") e **À venda** (`estoque_a_venda` +
  "N unidades"). `lucro_liquido`/`margem` gerais continuam descartados na lista branca (`app.py`).
- Cada número que não vier some sozinho (`hidden`), o card não quebra; nada é recalculado aqui. De R$ 100 mil pra cima
  sem centavos (`fmtNumeroGrande`, só formatação) - "R$ 1.258.000,00" quebrava linha em 390px.
- Contas com `pagador: "socio"` ganham o selo **"Ademir paga"** e não contam como "Próxima conta" (não saem do caixa);
  o contexto da IA também pula essas na próxima conta e explica quando só sobram elas.
- Contexto do resumo/chat: os 4 números com "(numeros prontos da construtora, nao recalcule)"; se nenhum vier, só a
  próxima conta. Conferido em 390px com o dado real: 48.915,81 / 1.258.000 / 371.009 / 1.160.000 (4 unidades).
- Bug de CSS achado na conferência: as cores de borda por número perdiam pra regra base `.construtora-stat` (mesma
  especificidade, declarada depois) - agora sob `.construtora-stats--4`. SW v55.

## 2026-10-10 - Trilha do dia (a "assinatura" das tarefas)

- `Cards.trilhaDia` (cards-vivos.js, puro): estrada ondulada do começo ao fim do dia, uma bandeirinha fincada na hora
  de cada tarefa (feita = cheia com visto; próxima = tremula; nova = cai do alto com quique) e o marcador "você" andando
  até agora, pintando o caminho percorrido. Entra no `tarefas_lista` (um dia) e no `tarefas_criadas` com
  `agenda_do_dia`. Marcar a caixinha hasteia a bandeira dela e a "próxima" passa pra seguinte. Conferido em quadros
  da animação no Chromium (Playwright). Service worker v54.

## 2026-10-10 - IA reajusta tarefa sozinha + "tarefa criada" mostra o dia

- **"Não consegui renomear a tarefa"** (print do Alex): `_achar` era busca literal; "lavar o carro" não achava
  "Lavar os carros por dentro" e a IA desistia. Agora: igual → contém → parecido por palavras (sem o/os/de/pra,
  plural, acento; escolhe só se ganhar com folga) e, sem achar, devolve `existentes` pra IA tentar de novo. Prompt:
  quando o Alex corrige algo que existe, ajustar na hora. Reproduzido com a mensagem real e a IA de verdade: renomeou
  as duas tarefas do carro sozinha.
- **`tarefas_criadas` com `agenda_do_dia`** (aditivo): o card mostra o dia inteiro com a tarefa nova "pousando" no
  lugar dela (selo NOVA, brilho, entrada depois das outras). Itens animados começam invisíveis no 1º quadro (antes
  apareciam e "piscavam"). Risco do título concluído repetido por linha (`1lh`), funciona em título de 2 linhas.
  Service worker v53.

## 2026-10-10 - Notificações de verdade (service worker na raiz) + cartões de tarefa caprichados

- **Bug antigo: o service worker NUNCA controlou a página.** Registrado de `/static/service-worker.js`, o alcance
  dele era só `/static/`; `serviceWorker.ready` nunca resolvia e o iPhone nunca deixava assinar notificação (a linha
  ficava "Indisponível"). Agora a rota `/service-worker.js` (sem login, `Service-Worker-Allowed: /`, `no-cache`) serve
  o mesmo arquivo e `init.js` registra com `scope: "/"` (e remove o registro velho de `/static/`). O handler de
  `fetch` continua mexendo SÓ em `/static/` - página, login e `/api` vão direto pro servidor (interceptar
  navegação com redirect quebra no Safari). Conferido no Chromium do Playwright: registra em `/`, `ready` resolve,
  página controlada. Service worker v52.
- **Cartões de tarefa**: caixinha redonda com o visto se desenhando (pulinho `--ease-bounce`), risco que atravessa o
  título (background-size), próxima tarefa do dia em destaque com "em 40 min" (relógio a cada minuto), grupos
  "Atrasadas / Hoje / Sem horário" e um grupo por dia em período de vários dias, comemoração quando acaba (anel
  brilha e o número vira um visto) e estado vazio. Datas relativas ("hoje", "amanhã"). Pegadinha: `Cards.parseDia`
  devolve o dia ao MEIO-DIA - comparar com a meia-noite de hoje fazia "hoje" virar "amanhã".

## 2026-10-10 - Notificações ligadas e sempre visíveis

- Chaves VAPID geradas (`scripts/gerar_chaves_push.py`; `vapid_private.pem` fora do git, pública no `.env`).
- `#push-btn` (Mais › Configurações › Avisos) virou uma linha igual às outras e aparece SEMPRE com o estado:
  Indisponível (iPhone sem instalar na Tela de Início - o iOS só libera push pra app instalado), Desligado,
  Bloqueado (Ajustes), Ligado (toque = notificação de teste via `/api/push/testar`). Antes ficava `hidden` sem
  explicar nada. `initPush` roda mesmo sem service worker, espera o `serviceWorker.ready` no máximo 6 s e
  reenvia a inscrição existente pro servidor. Service worker v51.

## 2026-10-10 - Transcrição mais fiel + cartão vivo de tarefas

- **Fala transcrita errada / palavra inventada no fim** ("...à noite tenho um date. Idiota."): o Whisper inventa frase
  em silêncio (testado: só silêncio virava "E aí" / "Legenda Adriana Zanotto"). Agora: `whisper-large-v3` (cheio, mais
  preciso em pt e com `no_speech_prob` útil; US$0,111/h), `verbose_json` + `temperature 0` + prompt curto com o
  vocabulário do Alex (Brusque, Blumenau, aeroclube, CIV, PR-LOM, Fiorino...), e `telegram_captura.texto_dos_trechos`
  descarta trecho marcado como silêncio e trecho que começa depois do FIM da fala que o app mediu (`fala_ate`).
- App: `criarGravacao` mede onde teve voz também no ditado (AudioContext no toque); se não ouviu voz nenhuma, nem manda
  ("Não ouvi nada"). Pegadinha corrigida no detector: o piso de ruído começava no 1º quadro - se ele já começava
  falando, a própria voz virava "ruído" (simulador pegou: fala detectada só aos 5,5 s). Só o fim da fala vai pro
  servidor (cortar o começo por medição arriscaria perder a primeira frase).
- **Cartão `tarefas_lista`** (`consultar_tarefas`): anel feitas/total que enche, frase "2 faltam · 1 atrasada",
  atrasadas em destaque, caixinha pra concluir ali (mesmo `data-tarefa-id` do `tarefas_criadas`); o anel recalcula
  pelo DOM (MutationObserver na classe `.concluida`, que o cards.js só põe depois do servidor confirmar).
  `tarefas_criadas` ganhou entrada animada. Service worker v50.

## 2026-10-10 - Voz da Roberta: rápida e sem travar

- **Demora**: `eleven_v4_turbo` levava ~3,5 s pra gerar ~230 caracteres (medido); `eleven_flash_v2_5` leva ~0,9 s,
  mesmo custo (0,5 crédito/caractere). Padrão virou flash (`.env` `ELEVENLABS_MODELO`); `voz_premium` usa o
  text-to-speech normal pro flash e o text-to-dialogue só pra v4/v3. Timeout do servidor 10 s.
- **"Às vezes não fala / buga"**: tocador de `static/js/nucleo/voz.js` reescrito. Antes, o `onpause` que o modo
  conversa deixava no `<audio>` compartilhado disparava depois e revogava o blob do botão "ouvir" no meio da fala;
  e se a voz do iPhone (plano B) não começasse, a conversa esperava pra sempre. Agora: geração por fala (qualquer
  callback velho é ignorado), `pararVoz` encerra na hora quem espera (`_vozFimAtual`), vigia de tempo no áudio e na
  voz do iPhone, e resposta longa vira 2 partes buscadas em paralelo (a primeira frase toca em ~0,5 s enquanto o resto
  gera). Botão "ouvir" acende já durante a busca. Service worker v49.

## 2026-10-09 (tarde) - IA que edita + cartões vivos

**IA edita, com Desfazer** (nunca apaga, nunca muda valor de dinheiro): `ajustar_tarefa` (hora, dia, título,
concluir/reabrir), `mover_tarefas` (dia inteiro ou manhã/tarde/noite), `ajustar_lembrete`, `ajustar_voo`
(aeronave, função, rota, tempo, observação, data), `ajustar_gasto` (só categoria/descrição), `definir_meta_horas_voo`.
- Desfazer de edição: entidade `edicao` em `acoes_desfazer` guarda os valores ANTIGOS das colunas mudadas;
  `db.EDICAO_COLUNAS` é a lista fechada de tabela/coluna (sem `expenses.amount`). `_desfazer_itens` faz o UPDATE.
- Achar o registro é sempre busca exata no banco (`_achar`): 0 ou 2+ = erro com as candidatas, nunca chute.
- Modo visitante: toda edição recusada no executor.
- Edições da mesma resposta viram UM card `edicao` (antes riscado → depois) com UM Desfazer.

**Cartões vivos** (protótipo aprovado: https://claude.ai/artifact/A81nC3Yim5toSYRtJs34TU), `static/js/cards-vivos.js`
+ `static/css/secoes/hoje/cards-vivos.css`: tipos novos `edicao`, `voo_resumo`, `clima`, `gastos_resumo`, `dia`,
`viagem_janelas`, `agua`; `rota` ganhou o mapa com o caminho REAL do Google (`routes.polyline` →
`maps_client.decodificar_polyline`/`traco_desenhavel`, projetado em 320x200 no servidor) e `saude_treino` os anéis da
semana. Renderizador puro devolve o estado final; `CardsVivos.preparar` (céu em canvas, avião no arco, onda) e
`CardsVivos.animar` (só resposta nova). Céu: chuva/garoa/trovoada/limpo/neblina, noite com estrelas e lua; só anima
visível (IntersectionObserver). Pegadinha: o auto-rolar do chat (MutationObserver em `chat.js`) puxava a tela pro
fim a cada atualização de número/relógio - `CardsVivos` marca `data-vivo-sem-rolar` e `irProFim` ignora.
- Consultas devolvem `_efeito` do card: `consultar_voos`/`registrar_voo` → `voo_resumo` (horas por função/aeronave,
  1º solo, meta em `configuracoes.aviacao_meta_horas`, padrão 150 marcada como exemplo), `consultar_clima` → `clima`,
  `consultar_gastos` → `gastos_resumo` (mascarado no visitante), `consultar_agenda` → `dia`; água → card `agua`
  (meta `configuracoes.agua_meta_copos`, padrão 8).
- **Viagem**: `viagem_compras.py` (puro) + tool `planejar_compras_viagem` → card `viagem_janelas`. Janelas das pesquisas
  (voo nacional 3-8 semanas; feriado 90-120 dias; internacional 2-8 meses / alta 4-10; hotel alta 3-6 meses) e alta
  temporada detectada (Carnaval pela Páscoa, Semana Santa, julho, Natal/Réveillon). Só o mês → dois cenários
  (no feriado / fora) com botão de alternar no card. Não salva a viagem.
- Checagem com a IA de verdade (banco temporário, Haiku 5.5): 10/10 ferramentas certas, incluindo recusar mudar valor.
- Service worker v48.

## 2026-10-08 - Chat passa para o Claude Haiku 5.5

- `ia/config.d/chat.json`: `modelo_atual` = `claude-haiku-5-5` (exame de 30 perguntas: 29/30 nos dois modelos, nenhuma
  invenção; Haiku ~20x mais barato). Para voltar ao Sonnet 5: trocar a linha de volta (uma linha). Acompanhar o gasto real
  em "Custo da IA" por alguns dias.

## 2026-10-08 - Preços do Claude Haiku 5.5 na tabela de custos

- `ia/precos.json`: `claude-haiku-5-5` (até 100 mil tokens: US$ 0,10 entrada / 0,50 saída / cache 0,125 (5 min), 0,20 (1 h),
  leitura 0,01; acima: 0,50 / 2,50 / 0,625 / 1,00 / 0,05). `ia/precos.py` aceita `multiplicador_cache_acima`. O chat
  ainda usa o Sonnet 5; trocar para o Haiku 5.5 é uma linha em `ia/config.d/chat.json` (decisão do dono).

## 2026-10-08 - Chat: consulta de voos, gasto por nome e tarefas sem hora (exame de alucinação)

- `scripts/exame_ia.py` (30 perguntas, banco temporário, chamadas reais só sob demanda): Haiku 5.5 26/30 e Sonnet 5 23/30
  de verdade, **nenhuma invenção**; os erros eram falta de ferramenta.
- Nova tool `consultar_voos` (total de voos/horas, últimos e futuros); `consultar_gastos` agora filtra também pelo
  nome do gasto (netflix, mercado); `consultar_agenda` devolve os títulos das tarefas sem hora.

## 2026-10-02 - Tarefas: "Ver mais"

- Lista de Tarefas monta 10 por vez; botão "Ver mais (N)" acrescenta mais 10 (antes montava até 100 de uma vez).
  Service worker v40.
- **Treino "Desfazer"** agora só apaga o treino marcado pelo botão "Feito hoje" (coluna `treinos.origem = 'botao'`,
  migração `202610021500_t1_treinos_origem.sql`); treino registrado pelo chat ou pela tela de treinos nunca é apagado. Voz escolhida: Roberta (`RGymW84CSmfVugnA5tvA`) - o ID vai só em `ELEVENLABS_VOICE_ID` no Render.

## 2026-10-02 - Restos da reformulação: skeleton, Tomei / Feito hoje, acentos

- **"Carregando…" virou esqueleto sutil** (Início, Meu dia, Construtora, Custo da IA, Visão do dia, Finanças,
  cotações, voos): altura reservada, brilho translateX discreto só enquanto carrega, parado em aba oculta e em
  `prefers-reduced-motion`; texto fica no DOM com `aria-busy`.
- **Medicamentos: "Tomei"** (`POST/DELETE /api/medicamentos/<id>/tomar`): conclui/reabre a tarefa recorrente
  de hoje, então agenda e prévia da noite continuam coerentes; "Tomado às HH:MM" + Desfazer; contador
  "x de y hoje". **Treino: "Feito hoje"** (`/api/treino/fichas/<id>/feito`). Sem tabela nova; otimista;
  modo visitante esconde. Início/Mais mostram "x de y remédios hoje".
- Achados: `_proximo_remedio` comparava horário cifrado (corrigido); botão "Apagar" cortado em Vida (regressão
  da etapa 3).
- Migração `202610021010_r4_rotina_remedio_acento.sql` (só linhas com o texto exato antigo "Remedio…").
  Acentos em templates, JS visível e rótulos dos tipos de aviso. Service worker v39.

## 2026-10-01 - Reformulação, etapa 3: acabamento das telas internas

- Tarefas, Finanças, Meu dia, Vida, Aviação, Construtora, Configurações, Avisos e regras e a folha do + no
  mesmo padrão do Início: rótulo de seção único (13 px CAIXA ALTA + ícone), cards raio 22 sem gradiente nem
  borda dourada, botões/campos 52 px, links soltos viram pílulas de 44 px, ajuda "!" vira (i), estados
  vazios com ícone, acentos corrigidos nos textos de tela.
- Tarefas: chips numa linha própria, "concluir" grande + editar, "quebrar" em linha inteira (nenhuma ação
  removida). Finanças: CSV/Nubank viram botões de 52 px, eixo do gráfico legível, "Evolução do mês" com 1 dia
  mostra o total. Meu dia: números no estilo do Início, avatar sem brilho.
- Início: faixa "assistente ainda não rodou" só com pendência real. IA: placeholder "Pergunta ou fala algo…",
  "ouvir" das bolhas com 44 px. Toast de erro some sozinho em 6 s.
- Teste novo `test_r3_acabamento.py`: em 390 e 320 px nenhum alvo de toque < 44 px, nenhum texto < 12 px,
  sem overflow horizontal, títulos de seção idênticos. Service worker v38.

## 2026-10-01 - Reformulação, etapa 2: Início e IA com conteúdo novo

- **Início**: hero ("Bom dia, Alex!" + resumo real + chip "N atrasadas"/"Tudo em dia" + Ouvir), card "Agora"
  (próxima tarefa/hábito com concluir otimista; vazio → "Planejar o dia" abre a IA com a frase), 3 números
  animados e tocáveis (tarefas, gasto hoje, copos d'água), "Acesso rápido" com 8 cards grandes e dado real,
  depois Só o essencial e Visão do dia. Pendências do assistente viram aviso de 1 linha.
- Rota nova `GET /api/inicio` (sem IA, sem rede; modo visitante esconde gasto/água/remédio), p50 ~7 ms.
- **IA**: estado vazio com 6 sugestões que enviam pelo mesmo fluxo do chat; bolhas na escala nova.
- **Mais**: subtítulos com dado real (hábitos, notas, aviação, saúde, Meu dia).
- `#erro-banner` virou toast fixo (não empurra a tela). Service worker v37.

## 2026-10-01 - Reformulação, etapa 1: esqueleto novo (aprovado pela prévia "preto gelo")

- **Barra de 5**: Início · Tarefas · IA (botão central) · Finanças · Mais, nomes inteiros. Painel ("Meu dia"),
  Vida, Aviação e Construtora saíram da barra e abrem pela tela **Mais** (mesmos ids/loaders; "‹" volta).
- **Topo global removido** de todas as telas. Cada tela tem cabeçalho próprio (`componentes/cabecalho-tela.html`).
  Os 5 botões redondos (silêncio, modo viagem, modo visitante, backup, sair) + notificações + custo da IA
  viraram linhas em Mais › Configurações (`tab-config`), mesmos ids/JS.
- **Botão +** (FAB) em Início/Tarefas/Finanças abre folha com o campo de captura, atalhos (Tarefa, Gasto,
  Lembrete, Nota) e Falar — mesma captura de antes.
- **Chat mudou pra tela IA** com campo fixo acima da barra; pendências/regras/avisos foram pra
  Mais › Avisos e regras (`tab-ajustes-ia`). `showTab` dispara `aba:aberta`.
- **Escala maior**: tokens novos de tipo (12–28), raios (22/18/16/13), toque (≥ 52 px, linhas ≥ 64 px).
- Testes: 7 novos (`test_r1_esqueleto.py`); testes de navegação ajustados pra abrir telas pelo Mais;
  2 testes que falhavam nos dias 1–3 do mês corrigidos. Service worker v36.
- Próximas etapas: conteúdo novo do Início (hero, Agora, números, Acesso rápido) e da IA (sugestões);
  acabamento das telas internas no mesmo padrão.
