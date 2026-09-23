# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

## 2026-09-23 (22) - Correcoes da revisao independente da Fase 2

Um agente separado (so leitura) revisou o commit da Fase 2 com ~700 requisicoes de lixo e
cenarios reproduzidos. Tudo que era bug real foi corrigido, com teste de regressao em
`tests/test_vida_revisao.py`.

- **"Cheguei em casa" dava erro 500 com evento do iCloud no dia**: o iCloud manda horario com
  fuso e o resto do app usa hora local sem fuso. Agora `caldav_client` converte uma vez na
  entrada e `_agenda_pendente_de_hoje` garante hora local sem fuso (tambem corrige o "vai sair a
  noite" e o aviso de chuva).
- **Numero gigante (`1e999`) dava 500** em manutencao, treino e no Atalho de localizacao
  (bateria): `_inteiro_no_intervalo` agora recusa infinito.
- **"Sono ruim seguido" podia avisar duas vezes no mesmo dia** quando o dado de hoje chegava
  depois: a sequencia agora e identificada pela primeira noite ruim de verdade
  (`vida.sequencia_noites_ruins`).
- **Ficha de treino casava pedaco de palavra** ("Braco" em "abraco", "Perna" em
  "Pernambucanas"): agora e palavra inteira. "Treino de voo/pouso" nao e academia (nem mostra
  ficha, nem poe fone e garrafa na saida de casa).
- **"!" abria vazio** se a ficha foi criada pelo chat depois de abrir a aba: recarrega a lista
  quando falta alguma.
- **Data de criacao em UTC** comparada com a data local (item de "pra responder" criado as 22h
  aparecia "ha -1 dia" e o lembrete atrasava um dia): pra responder, aprender, manutencao e
  contas pessoais agora leem `criado_em` em hora local.
- **Aviso segurado pelo hiperfoco ignorava o modo silencioso** ao sair: agora so o que ja era
  urgente (rotina da manha, hora de dormir) fura o silencio.
- **Atalho de localizacao/uso de apps sem token ficava aberto pra qualquer um**: sem
  `PAINEL_ATALHOS_TOKEN`, so aceita quem esta logado no painel. Comparacao do token em tempo
  constante (`hmac.compare_digest`).
- Lista de memorias: texto longo nao empurra mais o botao de apagar pra outra linha.
- Detalhes: "acabou o" sozinho nao vira item "o"; a resposta de compras devolve o nome limpo;
  lugar curtido so aparece na viagem se a cidade bate por palavra inteira; dica sono x humor nao
  diz "mais pra 'ok' ... e mais pra 'ok'"; hora de voo invalida nao quebra o aviso pos-voo.
  Service worker v8.

## 2026-09-23 (21) - BRIEFING.md Fase 3 (dinheiro, crescimento, burocracia)

Fase 3 do `BRIEFING.md`. Cofre de documentos e CalDAV ficaram de fora a pedido do Alex.

- **Projecao do fim do mes** (`vida.projecao_fim_do_mes`): o "quanto sobra" da aba Gastos ganha
  uma linha "No ritmo de R$ X/dia, deve sobrar R$ Y no fim do mes (com R$ Z de contas que ainda
  vencem)". Conta = gasto real ate hoje + ritmo diario x dias restantes + contas pessoais que
  ainda vencem no mes. Estimativa explicada, nao previsao magica.
- **Meta com previsao** (`vida.previsao_meta`): pelos depositos dos ultimos 90 dias, "No ritmo
  atual (R$ X/mes), bate em DD/MM/AAAA". Sem deposito recente, nao inventa data.
- **Quero aprender** (`aprender`): lista de temas com nota; domingo 10h, se algum esta parado ha
  7+ dias, um push "20 minutos hoje?". Botoes "mexi hoje" e "aprendi". Tool `registrar_aprender`.
- **Salvos pra ver depois** (`salvos`, `leitura.py`): cola o link, o servidor le a pagina e o Haiku
  resume em 3 pontos. So busca http/https de endereco publico (nunca rede interna/localhost,
  checado tambem a cada redirecionamento, no maximo 3), pagina ate 1,5MB. Se nao der pra ler ou
  resumir, o link fica salvo mesmo assim. Tool `salvar_link`.
- **Seu progresso** (`/api/progresso?dias=30`): so fatos, sem nota - tarefas feitas, dias com
  rotina da manha, treinos por semana, copos de agua por dia, sono medio, humor mais comum, % das
  metas.
- **Revisao mensal** (`/api/revisao-mensal`): dia 1 as 9h, push com o resumo do mes anterior no
  mesmo tom ("Agosto fechou: 42 tarefas feitas, 11 treinos, ..."). Tambem aparece na aba Vida.
- **Burocracia**: lembrete com cara de prazo de documento (CNH, passaporte, IR, IPVA, CMA,
  licenca, RG...) avisa com 30 dias de antecedencia, nao so na ultima semana. Casamento por
  palavra inteira ("ir" nao pega "vou ir"; "rg" nao pega "Jorge"). O chat tambem foi orientado a
  registrar esses prazos como lembrete.
- **Aviacao**: validade de licenca/CMA entra pela burocracia; novo push "Como foi o voo?" 2h depois
  da decolagem (ou 19h sem horario) se o voo do dia ainda nao tem diario.
- **Uso do celular** (`POST /api/atalho/app`, token `PAINEL_ATALHOS_TOKEN`): automacao "App
  abriu/fechou" do Atalhos (uma por app) - o Screen Time nao e legivel pelo Atalhos. Sessao sem
  "fechou" ou com mais de 3h nao conta (melhor subestimar). Domingo 19h, push com a semana no
  celular; aba Vida mostra os 7 dias.
- Visual: link salvo mostra so o dominio embaixo do titulo; campos de aprender/salvos ocupam a
  largura toda. Cache do service worker v7.

## 2026-09-23 (20) - BRIEFING.md Fase 2 + correcoes da revisao da Fase 1

Fase 2 inteira do `BRIEFING.md` (saude, localizacao, viagem, casa, comunicacao) e as correcoes
que uma revisao independente (agente separado, so leitura) achou no commit da Fase 1. Tudo que e
pessoal e nao e "painel do dia" foi pra uma aba nova **Vida** (a Painel estava virando rolagem
infinita): pra responder, compras, pessoas, treino, contas, assinaturas, manutencao, viagens,
lugares, mensagem dificil e vale a pena.

**Fase 2**
- **Agua/pausa**: push nas 9h/11h/13h/15h/17h de dia util, pulado se bebeu agua na ultima hora.
  Some durante o hiperfoco (pedido do Alex) - nao acumula.
- **Treino**: ficha por grupo muscular (`treino_fichas`, salvar o mesmo grupo substitui) e registro
  leve (`treinos`). `/api/tasks` manda `fichas_treino` - tarefa "Treino peito" ganha o botao **!**
  que abre a ficha ali mesmo; titulo generico ("Academia") mostra todas. Tools
  `salvar_ficha_treino` e `registrar_treino`.
- **Sintoma -> medico**: orientacao no prompt do chat (nunca diagnostica, sugere medico/dentista,
  urgencia se grave, oferece criar a tarefa de marcar consulta). Sem consulta recorrente fixa.
- **Sono ruim 3+ noites** (<6h no Saude ou "ruim" no check-in): um aviso por sequencia, depois das 8h.
- **Sono x humor/energia** (`aprendizado.dica_sono_humor`), cruzando `saude_dados` com o check-in -
  aparece na Saude hoje so com diferenca real (meio ponto na escala 1-3).
- **Localizacao via Atalhos** (`POST /api/atalho/local`, token `PAINEL_ATALHOS_TOKEN`): devolve a
  mensagem pro proprio Atalho mostrar. Chegou em casa: se ainda tem compromisso, "Proximo: X as
  14:00 - sai ate 13:30"; a noite, o que ficou pendente; meio do dia sem nada, silencio. Saiu de
  casa: checklist (carteira; carregador com bateria < 50%; fone e garrafa em dia de academia;
  bigode e cavanhaque sexta/sabado a noite se vai sair - agenda depois das 19h ou "vou sair hoje"
  no chat, tool `marcar_saida_noite`). Mercado: a lista de compras, so se tiver item. Mesma
  mensagem nao repete em 2h (geofence oscila na porta).
- **Chuva x compromisso**: 7h30, se a chuva prevista pega um compromisso do dia (precisa
  `CIDADE_PADRAO`).
- **Pre-voo**: vespera (19h+) e manha do voo: fone, carta WAC, cartas dos aerodromos, plano de voo,
  peso e balanceamento.
- **Viagens** (`viagens`/`viagem_itens`): mala montada pela IA (Haiku, com destino, dias e clima
  previsto) como checklist marcavel; aviso de documento 3 dias antes e no dia; lugares que voce
  curtiu na cidade aparecem junto. **Lugares** (`lugares`) e tools `registrar_viagem`/`registrar_lugar`.
- **Manutencao por tempo** (`manutencoes`): aviso uma semana antes, "feita hoje" reinicia.
- **Lista de compras** (`compras`): "acabou o cafe" vira "cafe", sem duplicar. Tool `adicionar_compras`.
- **Mensagem dificil** (`/api/mensagem-dificil`, Sonnet): versao direta e versao gentil, com copiar.
- **Pra responder** (`responder`): lembra todo dia as 10h a partir do dia seguinte ate "respondi".

**Correcoes da revisao da Fase 1**
- Hiperfoco perdia avisos de janela curta (22h, fechamento, rotina da manha...): agora ficam
  guardados e saem quando o foco acaba (`vida.AVISOS_JANELA_CURTA`, so no mesmo dia).
- Pagar conta com atraso marcava o mes seguinte como pago: o vencimento que passou ha ate 10 dias
  sem pagar continua sendo "o atual" (aparece "venceu ha X dias").
- "So o essencial" deixava remedio esquecido de dias atras ganhar de tarefa de hoje: instancia de
  rotina de dia passado nao concorre mais.
- "Trocar" podia devolver a tarefa recusada: recusadas do dia ficam de fora.
- Rotina da noite zerava a meia-noite: depois da meia-noite ainda conta como a noite anterior.
- Riscos: check-in com dois toques rapidos nao colide mais; valor infinito (`1e999`) recusado;
  contagem do hiperfoco nao depende do fuso do celular; fim do foco nao apaga um bloco novo;
  "Jo" nao casa mais com "Joao" por prefixo; passos novos entram depois do ultimo passo feito.
- Layout: com 3 botoes na tarefa, as acoes descem pra linha de baixo em vez de estourar o card.
- Nome duplicado `_compromissos_de_hoje` (achado no teste no navegador) quebrava a agenda.

48 testes novos (`tests/test_vida_fase2.py`). Validado no navegador (Playwright, 390px).

## 2026-09-23 (19) - BRIEFING.md Fase 1: rotina guiada, check-in, hiperfoco, so o essencial, pessoas

Primeira rodada do `BRIEFING.md` (assistente de vida, agora versionado no repo junto com o
`TODO.md` de progresso). O Alex respondeu todas as perguntas antes (regra 3 do briefing); o que
ja existia no painel ficou de fora, e as decisoes tomadas sem perguntar estao no fim do `TODO.md`.
Logica pura nova em `vida.py` (testavel sem banco), rotas em `app.py`, frontend em
`static/js/vida.js` (arquivo novo, carregado depois do `app.js`).

- **Rotina guiada**: `rotina_itens`/`rotina_marcacoes`, itens padrao semeados uma vez (manha:
  agua, remedio, check-in, olhar o essencial; noite: fechamento, separar o de amanha, celular
  longe). Push "Bom dia" as 7h com os itens (horario em `configuracoes.rotina_manha_hora`) e o
  push das 22h que ja existia agora lista a rotina da noite. Card na aba Hoje aparece so no
  horario (5h-12h / 20h-3h) e some quando tudo foi marcado.
- **Check-in de 1 toque**: energia/sono/humor, ruim/ok/bom, cada toque salva na hora
  (`checkins`). Tool `registrar_checkin` no chat ("dormi mal").
- **Hiperfoco** (25/50/90 min): em `configuracoes.hiperfoco_ate`. Durante o bloco so passa
  aviso critico (`vida.CRITICOS_HIPERFOCO`: tarefa com hora - inclui remedio -, compromisso
  chegando, voo); o resto fica represado e sai depois, nunca se perde. Push quando o bloco acaba
  (so se acabou ha menos de 30 min). Tool `iniciar_hiperfoco`.
- **So o essencial**: Haiku escolhe 1-3 das tarefas de hoje/atrasadas/sem prazo, guardado por
  dia (`essencial_dia`) pra nao mudar a cada abertura; "trocar" repoe pela heuristica
  (`vida.pontuar_tarefa_essencial`), que tambem e o fallback se a IA falhar ou inventar id.
  "Modo foco no dia" esconde o resto da aba Hoje e reseta sozinho no dia seguinte.
- **Tarefa empacada**: `/api/tasks` ganhou `empacada_dias` (3+ dias atrasada, ou 7+ dias sem
  prazo e sem passo concluido na semana). Botao "quebrar diferente" (`/requebrar`, Sonnet) troca
  so os passos nao feitos, com primeiro passo de 2-5 min. O push de tarefa parada oferece isso.
- **Contas pessoais** (so estrutura, a pedido): nome/dia/valor, aviso 3 dias antes e no dia (uma
  vez cada), "paga" para os avisos daquele vencimento. Dia 31 em mes curto vira o ultimo dia.
- **Assinatura sem uso**: uma vez por mes pergunta "ainda usa?" das recorrencias ja detectadas
  (`_gastos_fixos`); "nao uso mais" cria a tarefa "Cancelar assinatura: X" e nunca mais pergunta.
- **Pessoas**: lista curta com frequencia (`pessoas`), nota leve de conversa (`conversas`), aviso
  "faz X dias" uma vez por ciclo. Tools `registrar_conversa` e `cadastrar_pessoa`.
- **Data importante com sugestao**: aniversario/casamento/etc ganham "Ja pensou em mandar uma
  mensagem ou algo?" no push e na lista.
- **Vale a pena?**: `/api/decisao` (Sonnet) devolve pros/contras/perguntas-chave/inclinacao e guarda
  historico (`decisoes`); o chat tambem responde nesse formato.
- CSS: estilo de input/textarea/botao aplicado tambem aos forms de medicamento, medida e espera
  (estavam com o visual padrao do navegador).

65 testes novos (`tests/test_vida.py`, `tests/test_vida_rotas.py`, com entradas invalidas em
todas as rotas). Validado no navegador (Playwright, 390px): todos os fluxos, sem overflow.

## 2026-09-22 (18) - Hidratacao, peso/medidas corporais e correlacao sono x produtividade

Terceira rodada de perguntas explicitas ao Alex sobre o que falta pro painel virar um
"assistente de vida" de verdade (10 perguntas, respostas curtas e diretas). Do que ele
confirmou como util - "esqueco ate alimentacao" (agua), "seria legal pra eu nao esquecer"
(peso/medidas) e "sinto falta de uma analise do sono detalhada e melhorar pra resolver"
(correlacao) - e descartou explicitamente o resto (calendario Apple - "nosso app ja e
melhor"; lembretes Apple - redundante; screen time/foco - nao expostos pelo iOS mesmo;
diario, cartao de emergencia, vault de documento - "nao me interessa").

**Hidratacao**: tabela `hidratacao_registros`, so timestamp por copo - sem meta/limite (o
pedido era so parar de esquecer, nao gerenciar ml). `POST /api/hidratacao` incrementa o dia,
botao "+1 copo" na Saude hoje com contador. O lembrete pra beber em horario fixo nao ganhou
notificacao nova - a tarefa recorrente que ja existe (rodada 16) ja cobre isso.

**Peso e medidas corporais**: tabela `medidas_corporais` (tipo livre - peso, biceps, cintura
etc -, valor, unidade, data). `GET/POST/DELETE /api/medidas`, unidade padrao 'kg' pra peso e
'cm' pro resto quando nao informada. Frontend mostra so no registro mais recente de cada
tipo quanto subiu/desceu desde o anterior (verde/vermelho), sem repetir a seta em toda
linha do historico.

**Sono x produtividade**: `aprendizado.correlacao_sono_produtividade` cruza
`saude_dados.sono_horas` (ja gravado via Atalho) com taxa de tarefas concluidas no mesmo dia,
agrupado em 4 faixas (<6h, 6-7h, 7-8h, 8h+, minimo 3 amostras por faixa - mesmo principio de
`produtividade_por_dia_semana`). `dica_sono_produtividade` so fala alguma coisa quando a
diferenca entre a melhor e a pior faixa for real (>=15 pontos percentuais), e so sugere
"dormir mais" quando a faixa de MAIS horas for de fato a mais produtiva (nunca inventa causa
que o dado nao mostra). Aparece como frase na Saude hoje via `/api/saude/hoje`.

**Chat**: `registrar_hidratacao` (sem parametro) e `registrar_medida` (tipo/valor/unidade)
entram no dicionario de tools, cada um chamando o mesmo helper que a rota HTTP usa.

21 testes novos (`test_aprendizado.py`, `test_app.py`). 875 testes Python + 112 subtestes,
100% passando.

## 2026-09-22 (17) - Medicamentos: cadastro estruturado (nome/dosagem/horario) com lembrete

Continuacao direta da (16): o Alex pediu explicitamente pra copiar o fluxo de "Medicamentos" do
Apple Saude (nome do remedio, quantos mg, horario de tomar, com lembrete) depois de eu confirmar
por pesquisa que essa parte especifica NAO tem ponte via Atalhos - nem o proprio ecossistema da
Apple expoe Medications externamente (so passos/sono/distancia tem "Log Health Sample"). Em vez
de tentar uma integracao impossivel, o painel ganha seu proprio cadastro de medicamentos, camada
fina por cima da infraestrutura de tarefa recorrente que ja existia.

**Modelo de dados**: tabela nova `medicamentos` (nome, dosagem, horario, recorrencia DEFAULT
'diaria', `tarefa_modelo_id` FK pro modelo recorrente em `tasks`, ativo). Guarda so metadado
estruturado pra exibir bonito - toda a materializacao diaria, bolinha verde/vermelha e aviso
10min antes vem de graca da tarefa recorrente vinculada, sem duplicar nenhuma logica de
agendamento. `_criar_medicamento` (compartilhado entre a rota HTTP e o executor do chat, mesmo
padrao de `_resolver_cotacao_por_titulo`) cria as duas linhas numa tacada so e ja materializa a
instancia de hoje. Sem `PRAGMA foreign_keys` ligado neste banco (confirmado no padrao existente
de `delete_cotacao`), `delete_medicamento` apaga o medicamento E a tarefa-modelo explicitamente -
instancias ja materializadas em dias anteriores ficam no historico normal, so paravam de gerar
novas a partir de hoje.

**Rotas**: `GET/POST /api/medicamentos`, `DELETE /api/medicamentos/<id>`.

**Chat**: tool nova `registrar_medicamento` (nome obrigatorio, dosagem opcional, horario
obrigatorio HH:MM, recorrencia opcional default "diaria") - o system prompt agora distingue
remedio (usa essa tool, guarda dado estruturado) de rotina generica tipo academia (continua
usando `recorrencia` em `registrar_tarefa`).

**Frontend**: secao nova "Medicamentos" na aba Painel, entre "Datas importantes" e "O que eu
lembro sobre voce" - form com nome/dosagem/horario (`<input type="time">`) e lista com botao
Apagar, mesmo padrao visual de `.item`/`.item-linha` ja usado em lembretes/esperas.

9 testes novos em `test_app.py` (lista vazia, criar com/sem dosagem, materializacao da tarefa de
hoje, rejeicao de nome/horario/recorrencia invalidos, apagar remove medicamento + tarefa-modelo,
chat usa o executor de verdade). 854 testes Python + 112 subtestes, 100% passando.

## 2026-09-22 (16) - Tarefa recorrente (diaria/semanal) - remedio, academia, rotina

Pedido explicito do Alex depois de confirmar a visao do projeto (agenda/TDAH e a prioridade,
e o painel e pra SUBSTITUIR o Calendario da Apple de verdade, nao rodar do lado): "toda segunda
tem academia as 7h", remedio diario ("no Apple Saude tem varias coisas que me ajudam, tipo
marcar que tomei remedio - seria bom se ele se conectasse"). Decisao: em vez de tentar integrar
com o Apple Saude/Medications via Shortcuts (superficie incerta - o iOS nao expoe isso de forma
simples como passos/sono), a rotina de remedio vira uma tarefa recorrente dentro do proprio
painel - reusa toda a infraestrutura de agenda/notificacao que ja existe (bolinha verde/vermelha,
aviso 10min antes) sem precisar de nada novo.

**Modelo de dados**: `tasks` ganhou `recorrencia` (TEXT, formato `"diaria"` ou
`"semanal:N,N,..."` com N=dia da semana, 0=segunda...6=domingo) e `recorrente_origem_id`
(aponta de volta pro modelo). Uma linha com `recorrencia` preenchida e devem `due_date` NULL e um
MODELO - nunca aparece ela mesma em lista nenhuma (todas as queries de "tarefas pendentes" sem
filtro de due_date especifico ganharam `AND recorrencia IS NULL`: `/api/tasks`,
`/api/summary/today`, `_tarefas_pendentes_sem_horario_hoje`, `sugerir_tarefa_para_agora`, o
endpoint do widget Scriptable, `notificacoes.tarefas_aguardando_bom_tempo`).

**Materializacao**: `materializar_tarefas_recorrentes(conn)` cria a instancia de HOJE pra cada
modelo cujo padrao bate com o dia da semana (funcao pura `agenda.recorrencia_bate_no_dia`),
idempotente (confere se ja existe antes de criar). Chamada em todo ponto de leitura relevante
(`/api/tasks`, `/api/calendario/hoje`, `_processar_mensagem_chat`, `verificar_e_notificar` - essa
ultima ANTES de qualquer early-return de canal de notificacao, pra rotina aparecer mesmo sem
push/Telegram configurado ainda).

**Chat**: `registrar_tarefa` ganhou o campo opcional `recorrencia` - a IA reconhece "todo
dia"/"toda segunda e quinta" e preenche o padrao certo, ignorando `quando`/`quando_data` (nao
faz sentido pra algo que se repete). Completar a instancia do dia nunca apaga o modelo - ele
regenera sozinho no proximo dia que bater o padrao.

**Frontend**: instancia materializada ganha uma tag "rotina" ao lado do titulo (mesma pilula
visual ja usada pra tag "tarefa" na agenda), pra distinguir de uma tarefa avulsa num relance.

18 testes novos (`test_agenda.py`, `test_app.py`). 845 testes Python + 112 subtestes, 100%
passando.

## 2026-09-22 (15) - Polish final: card de resultado no "devo sair" e dias restantes nas datas importantes

Fecha os dois pontos que ficaram vagos no walkthrough do Alex ("Devo sair até que horas" e "Datas
importantes" pareciam "muito simples", sem ele conseguir dizer exatamente o que faltava) -
resolvidos por julgamento proprio (ele pediu explicitamente pra terminar tudo sem parar pra
confirmar de novo), reaproveitando padroes visuais/de dado que ja existem no app em vez de
inventar comportamento novo.

**"Devo sair até que horas" virou um card de resultado**: `#viagem-resultado` trocou de um `<p
class="resumo-texto">` (paragrafo piano) pro mesmo `.card-resultado` ja usado nos cards do chat
(tarefa/gasto/meta) - eyebrow com icone + destino, o horario de saida em destaque (mesmo tratamento
visual de um valor em R$), duracao/distancia/margem como detalhe. So mudou apresentacao - o calculo
(Google Maps, transito real) ja estava certo.

**"Datas importantes" ganhou "faltam N dias"**: `/api/lembretes` agora calcula `proxima_ocorrencia`
+ `dias_restantes` por item (`notificacoes.proxima_ocorrencia_lembrete`, que ja existia como
`_proxima_ocorrencia` privada - so tornada publica pra servir os dois usos). Corrige de quebra um
bug latente: um lembrete recorrente (tipo exame medico anual) mostrava a data do ANO DE CADASTRO
pra sempre, nunca o proximo aniversario de verdade - agora mostra a proxima ocorrencia calculada,
com "faltam N dias"/"e hoje"/"e amanha" ao lado (mesmo padrao ja usado nas metas), destacado quando
faltam 7 dias ou menos (a mesma janela que ja dispara notificacao push).

6 testes novos (`test_app.py`). 825 testes Python + 112 subtestes, 100% passando. Validado por
revisao de codigo + suite completa - sem screenshot desta vez (o componente `.card-resultado`
reaproveitado ja foi validado visualmente em rodadas anteriores, entao o risco de regressao visual
era baixo).

## 2026-09-22 (14) - Assistente proativo: avisa antes, distribui a semana, puxa tarefa quando ocioso

Pedido grande e explicito do Alex (TDAH): "eu tenho que ser um cara que... ela nao tem que so me
lembrar, ela tem que me ajudar a pensar". Escopo fechado com ele antes de codar (3 perguntas via
AskUserQuestion): os 3 pedacos abaixo, distribuicao sempre com confirmacao antes de criar
("eu digo se vai dar ou nao"), aviso de heads-up nos dois canais (push + Telegram).

**Aviso ANTES do horario, nao so na hora**: `notificacoes.tarefas_com_horario_chegando` ganhou uma
janela de antecedencia (10min por padrao) - uma tarefa com hora marcada agora avisa "Daqui a
pouco: X as HH:MM - ja va se preparando" alguns minutos antes, e so cai na mensagem antiga ("X -
HH:MM") se o tick certo de heads-up foi perdido (scheduler fora do ar etc), nunca fica sem aviso
nenhum. Estendido tambem pra compromisso do calendario do iCloud (novo bloco em
`verificar_e_notificar`, tipo `compromisso_chegando` - so `origem="calendario"`, tarefa ja tem o
aviso acima, senao duplicaria). ID estavel do evento via hash titulo+inicio (`_id_estavel_evento_calendario`,
mesma tecnica de `_id_estavel_conta`), ja que o iCloud nao expoe um id numerico pra gente.

**Distribuir lista de tarefas jogada de uma vez pela semana**: nova funcao PURA em `agenda.py`
(`distribuir_tarefas_na_semana`) - reusa `sugerir_dia_menos_corrido` item a item (carga simulada
que vai aumentando a cada escolha, pra espalhar em vez de empilhar tudo no dia mais vazio) e
`HORARIOS_SUGERIDOS_DIA` (pula almoco 12h-14h e janta 18h-20h de proposito). A IA so extrai a
LISTA de titulos do que o Alex despejou (`distribuir_tarefas_na_semana` como tool) - quem decide
dia/horario e Python determinista, nao a IA "no chute". A proposta fica guardada em
`configuracoes` (chave `plano_semana_pendente`, reaproveitando o mesmo mecanismo ja usado pro
horario silencioso) e SO vira tarefa de verdade com `confirmar_plano_semana`; `cancelar_plano_semana`
descarta sem criar nada. `_contexto_chat` agora menciona um plano pendente (se houver) pro modelo
saber, numa mensagem seguinte, que "pode" significa confirmar aquele plano especifico.

**Puxar tarefa quando ele diz que ta sem nada pra fazer**: `sugerir_tarefa_para_agora` (tool novo)
acha a tarefa mais proxima com dia marcado NO FUTURO (adianta ela, pedido literal do Alex - "em
vez de fazer isso na terca, faz na segunda") ou, se nao houver nenhuma, cai pra uma tarefa solta
sem data. So sugere (a resposta do modelo tem que ser pergunta, nunca decisao) - se ele topar e
depois contar que fez, isso ja fecha via `registrar_feito` existente, sem precisar de mecanismo
novo pra "mover" a tarefa.

19 testes novos (`test_agenda.py`, `test_notificacoes.py`, `test_app.py`) cobrindo os 3 pedacos +
o reaproveitamento correto do dedup/contexto existente. 823 testes Python + 112 subtestes, 100%
passando.

## 2026-09-22 (13) - Agenda com bolinhas verde/vermelha, saldo nos bancos, diario de bordo do voo, rainbow v2

Rodada baseada num walkthrough completo do Alex aba por aba (aba Hoje/chat/tarefas ok como
estao; Construcao adiada de proposito ate a integracao real; feedback concreto nas outras).

**Agenda: bolinha verde (concluido) / vermelha (perdido)**: `/api/calendario/hoje` so devolvia
tarefas PENDENTES (por design - e a mesma funcao que alimenta plano do dia e notificacoes, que
nao podem ver trabalho ja feito como se ainda faltasse). Em vez de mexer nessa funcao
compartilhada (risco real de regressao em 8 pontos de consumo), criei
`_tarefas_concluidas_com_horario_hoje` separada, so pro `/api/calendario/hoje` mesclar - visual
puro, sem efeito colateral em nenhum outro fluxo. Frontend (`loadAgenda`) agora aplica `.concluido`
(verde, `#42bb91`) em tarefa feita, `.perdido` (vermelho, `--danger`) em tarefa com horario que
passou sem marcar como feita - evento de calendario (sem tarefa por tras) continua no tratamento
neutro `.passado` de sempre, porque nao da pra confirmar presenca num compromisso.

**Bancos: saldo visivel**: `bank_accounts.saldo` ja existia no schema e ja vinha no
`/api/bancos`, so nao aparecia na tela. Adicionado na ponta da linha de cada conta/cartao
(`.banco-saldo`, verde se positivo, vermelho se negativo).

**Aviacao: "observacao" virou diario de bordo**: campo trocado de `<input>` de uma linha pra
`<textarea>`, com placeholder convidando a contar o trajeto (ex: "fui de Blumenau, passei em
Curitiba..."). Descricao ganhou paragrafo proprio na lista (`.voo-diario`, borda lateral colorida)
em vez de ficar espremida na mesma linha da data/horas. Schema de ferramenta do chat
(`claude_client.py`) tambem atualizado - a IA agora pode registrar um relato mais completo quando
o Alex contar por voz/texto, sempre so o que ele de fato disse (sem inventar).

**Rainbow v2 ("mais tecnologico, mais chique")**: pedido vago, interpretado como (a) terceira
mancha radial verde-azulada com ciclo proprio fora de fase das outras duas - o caminho fica mais
organico/mesh-gradient em vez de um ping-pong entre 2 pontos, tipo os fundos animados da Apple
(Fitness/Music); e (b) uma camada extra de brilho diagonal bem sutil (`.aurora::before`,
branco a ~5-9% em `mix-blend-mode: overlay`) cruzando a tela devagar (34s), como o "shine" que
passa em fotos de produto da Apple - acabamento de vidro/metal sem mexer na paleta roxo/verde
nem virar luz piscando. Continua respeitando `prefers-reduced-motion`.

Teste `test_calendario_hoje_ignora_tarefa_concluida` renomeado/reescrito pra
`test_calendario_hoje_marca_tarefa_concluida` (a mudanca de comportamento e intencional e
documentada no proprio teste). 800 testes Python + 112 subtestes, 100% passando.

## 2026-09-22 (12) - Fisica de toque de verdade (causa real do "barato") + efeito rainbow

O Alex achou a rodada anterior "muito simples... clico e ja vai sem nada, como se fosse muito
barato", pediu fluidez tipo iOS e um efeito "rainbow" (fundo trocando bem devagar entre roxo e
verde).

**Causa raiz do "barato" encontrada**: o app inteiro tinha UMA UNICA regra `:active` pra toque
(so em `<button>`, escala 0.94) e ZERO estados de toque em qualquer outro elemento clicavel -
27 blocos `@media (hover: hover)` no CSS, e nenhum equivalente pra toque (celular nao tem hover,
entao nada acontecia visualmente ao tocar em coisas como o cabecalho de cotacao que expande, ou
o label de anexar OFX). Corrigido: `.cotacao-cabecalho` e `.ofx-input-label` ganharam a mesma
fisica de toque dos botoes.

**A fisica de toque em si tambem estava errada, nao so faltando**: existia uma unica curva
(`--ease-bounce`, com overshoot) usada tanto pra afundar quanto pra soltar o botao. Overshoot faz
sentido soltando (a "mola" passa um pouco do ponto e assenta) mas fica estranho/nervoso afundando
numa escala tao pequena (0.94) - nao lia como toque de verdade. Agora sao duas fases distintas,
copiando o padrao real do iOS: afundar e RAPIDO e sem overshoot (~90ms, ease-in reto - sensacao
de "toque registrado na hora") e soltar e um pouco mais lento COM leve overshoot (~220ms, bounce -
sensacao de mola assentando). Opacity leve (0.85) somada ao scale ajuda o toque a ser percebido
mesmo numa amplitude pequena.

**Efeito rainbow**: `.aurora` ganhou uma segunda camada (`::after`) com duas manchas radiais FIXAS
(roxo/ametista e verde/esmeralda - a dupla original da identidade do app, independente de qual
`--accent` estiver ativo) cuja posicao de fundo anima devagar (26s, ida e volta) - as duas manchas
se revezam em qual fica mais "em foco" sem nunca passar por outra cor no meio do caminho (por
isso nao usei `hue-rotate`, que passaria por vermelho/laranja). Respeita
`prefers-reduced-motion` (herda o `animation: none` que ja existia pro `.aurora` base).

Validado com Playwright: regra `button:active` e as duas novas (`cotacao-cabecalho`/
`ofx-input-label`) confirmadas com a fisica de duas fases certa, `aurora::after` rodando o
`rainbowDrift` de 26s em `mix-blend-mode: screen`. 800 testes Python, 100% passando (CSS puro).

## 2026-09-22 (11) - Rodada de animacoes: ritmo humano no chat, transicao de aba direcional, erro com entrada

Depois de fechar o tema (round 8-10), o Alex pediu a proxima etapa: animacoes e efeitos "em
detalhes minimos", "premium, tipo carro de luxo", e que o chat parecesse mais uma pessoa
respondendo que um robo. Registrei essa preferencia como permanente no `CLAUDE.md` (nao e so
pra essa rodada - vale pra qualquer trabalho visual futuro no projeto).

Antes de implementar, perguntei o que priorizar (ele pediu isso: "pergunta antes de comecar")
- resposta: os 4 pontos ao mesmo tempo (chat mais humano, fundo reagindo ao scroll,
micro-interacoes, transicoes entre abas), com uma ressalva clara pro chat: "diferentes ritmos,
mas nao algo devagar".

**Ritmo humano no chat** (`escreverPalavraAPalavra` em `app.js`): antes cada palavra aparecia
num intervalo IDENTICO (metronomo). Agora cada palavra varia +-20% em vez de ser uniforme,
palavras bem curtas (ate 2 letras) saem mais rapido, e pontuacao de fim de frase ganha uma
pausa de verdade (2.2x) - virgula/ponto-e-virgula uma pausa menor (1.1x). A duracao TOTAL nao
mudou (a media do jitter e 1.0x) - mais variado, nao mais lento, exatamente o pedido.

**Transicao direcional entre abas**: trocar pra uma aba mais a direita na barra desliza
entrando pela direita, mais a esquerda entra pela esquerda (`ORDEM_ABAS` + classes
`entra-direita`/`entra-esquerda` em `app.js`, keyframes novos em `style.css`) - em vez do
mesmo fade generico pra qualquer troca, um detalhe que a maioria dos apps premium tem e o
nosso nao tinha.

**Banner de erro com entrada**: antes aparecia sem nenhuma transicao. Ganhou um leve
overshoot-e-assenta (`erroEntra`, usa `--ease-bounce`) - decidi contra um "shake" literal de
proposito, porque lê como alarme/chamativo, o oposto do "premium, nao sinistro" que ele pediu.

**Fundo reagindo ao scroll**: unico ponto onde ele nao tinha certeza da direcao ("me mostra") -
em vez de escolher por ele, montei 3 protótipos SO no artefato-replica (tom que muda com a
posicao do scroll via hue-rotate, paralaxe onde o fundo se move mais devagar que o conteudo, e
um brilho que acompanha a posicao da rolagem tipo farol) com botoes pra alternar entre eles ao
vivo. Nenhum foi aplicado no app real ainda - esperando ele escolher qual (ou nenhum).

Micro-interacoes: o app ja tinha bastante disso (pulso de sucesso, particulas ao concluir
tarefa, numero "pop", checkbox pop, shimmer de carregamento) - essa rodada focou nos 3 pontos
que realmente faltavam (chat, transicao de aba, erro) em vez de duplicar o que ja existia.

Validado com Playwright: classes de direcao corretas ao trocar de aba pra frente/tras, delays
de palavra realmente variados numa resposta real do chat (nao mais um passo fixo), animacao do
banner de erro confirmada via `getComputedStyle`, e os 3 modos de scroll-fx alterando o filtro/
transform/opacidade da aurora conforme a posicao de rolagem. 800 testes Python, 100% passando.

## 2026-09-22 (10) - Remove de vez o "negocinho preto" acima do chat (raiz, nao sintoma)

Terceiro print seguido reclamando da mesma area (acima do "Fala comigo..."): dessa vez "tem um
negocinho preto, ele ta descendo, ta meio estranho" - o degrade round 9 (sem blur) continuava
visivel o bastante pra ler como um elemento estranho.

Em vez de ajustar o degrade de novo, questionei se ele precisava existir: `.chat-lista` (a lista
de bolhas do chat, logo acima do `.chat-form`) ja tem `overflow-y: auto` com `max-height: 58vh`
PROPRIO - ela clipa as mensagens sozinha, dentro da propria caixa. O degrade nunca teve conteudo
de verdade pra esconder (nao tinha bolha "vazando" por baixo do input) - era decoracao pura que,
em 3 rodadas seguidas (retangulo solido -> ::before com blur -> ::before sem blur), sempre acabava
lendo como um elemento fora do lugar. Removido o `::before` inteiro - zero elemento novo, a ultima
bolha agora so termina na borda da lista, como qualquer lista com scroll.

Confirmado de novo (o Alex reforcou por precaucao): Liquid Glass continua SO na barra de abas,
paineis e campos continuam opacos - nada mudou nessa regra, so o elemento fantasma foi removido.

Validado com Playwright: `getComputedStyle(.chat-form, '::before').content` retorna `none`
(elemento nao existe mais), screenshot da mesma zona sem nenhuma forma estranha, `--glass-blur`
ainda `none` pros paineis e a barra ainda com blur de verdade. 800 testes Python, 100% passando.

## 2026-09-22 (9) - Fix: barrinha preta flutuando acima do chat (residuo de blur esquecido)

Print anotado: uma barra preta retangular flutuando por cima da grade de stats, logo acima do
"Fala comigo...", "não faz sentido, tá só atrapalhando".

Causa: o `::before` do `.chat-form` (round 8, esmaece a ultima bolha de chat antes da linha de
input) ainda tinha `backdrop-filter: blur(8px)` sobrando do round 6. Esse blur suavizava as bordas
do retangulo o bastante pra ele ler como um objeto flutuando por conta propria, sem se prender a
nada visualmente - e contradizia a propria regra que o round 8 acabara de fechar (Liquid Glass SO
na barra de abas). Fix: removido o `backdrop-filter` - so sobra o degrade solido (transparente ->
`--bg`), que agora lê como parte do fundo esmaecendo o texto por tras, nao como um bloco a parte.

Confirmado nesse mesmo round: cor "Preto puro", fonte Atual (Sora) e Liquid Glass so na barra
continuam sendo a decisao - nada mudou ali, so o residuo de blur foi removido.

Validado com Playwright (getComputedStyle confirmando backdrop-filter: none, screenshot da zona
stats->chat sem nenhuma forma flutuante). 800 testes Python, 100% passando (CSS puro).

## 2026-09-22 (8) - Decisao final de tema: preto puro + neutro, vidro so na barra + 4 fixes

Depois de testar no comparador do artefato (18 cores x 5 fundos x Liquid Glass on/off por area),
o Alex decidiu e circulou num print: fonte Atual (Sora), cor "Preto puro" (neutro/grafite
#45454a/#08080a), fundo "Preto puro" (#000000/#121212/#181818/#1e1e1e), Liquid Glass ligado SO na
barra de abas (Paineis: OFF, Campos: OFF). Aplicado como novo padrao real do app (nao mais so no
comparador).

**Paineis e campos de texto viraram opacos**: `--glass-bg` deixou de ser um degrade translucido e
virou `var(--surface-2)` fixo, `--glass-blur: none` - `li.item`, `.resumo-texto`, `.grafico-card`,
`.fechamento-box`, `.chat-bolha.assistant`, `.uber-pendente-card`, `#chat-input`/`#captura-input`/
`#duvida-input` (tudo que usava esses tokens) ficou solido de uma vez, sem tocar em cada seletor
individualmente. `--glass-border`/`--glass-shadow` continuam tingidos pela cor de identidade de
cada secao (borda fina + sombra ambiente colorida) - a secao ainda se distingue por cor mesmo
opaca. `#tabbar` nao usa esses tokens (receita propria) - continua com blur de verdade.

**4 ajustes pedidos junto, com print anotado**:
1. *Campos "grudados"*: `.chat-form` (input+mic+enviar) tinha um fundo compartilhado cobrindo os
   3 - pareciam um bloco unico. O degrade que esmaece a ultima bolha de chat virou um `::before`
   plantado SO no espaco vazio acima da linha (nao mais sobre ela) - cada controle mostra so o
   proprio fundo agora, com vao real entre eles.
2. *Falta de profundidade*: com os paineis opacos, a sombra virou a unica pista de "flutuando" -
   trocado `var(--shadow-card)` por `var(--shadow-card-hover)` (mais forte) + um halo colorido
   maior por baixo de cada card/aba.
3. *Titulo "some" com fundo escuro*: `--accent-gradient-titulo` escurecia o accent ainda mais
   (58% accent + 42% preto) - pensado pra accents vividos contra um fundo quase-preto, mas com
   accent JA escuro (preto-puro) contra fundo literalmente preto o titulo ficava com ~1.4:1 de
   contraste (medido, bem abaixo do legivel). Fix: depois de escurecer, mistura de volta 32% de
   `--text` como piso minimo de claridade - funciona pra qualquer accent, claro ou escuro.
4. *Fonte fina demais nas explicacoes*: SO o texto de apoio (`.dica-metas`/`.dica-texto`,
   `.silencio-descricao` - "Considera transito em tempo real...", "Avisos que podem esperar...")
   ganhou `font-weight: 500` (era peso padrao/400) - nada mais na tela mudou de peso.

Validado com Playwright: `getComputedStyle` confirmando fundo/accent/glass-blur aplicados, print
mostrando os 3 controles do chat separados, titulo legivel contra o novo preto, sombra mais
presente. 800 testes Python, 100% passando (CSS puro).

## 2026-09-22 (7) - Fix do bloco preto atras do campo de chat + laboratorio de estilos no artefato

O Alex mandou print anotado apontando um "negocinho preto" atras do `#chat-input`/mic/enviar que
"nao consegue estar separado" das bolhas de chat.

**Causa e fix**: `.chat-form` (a linha do input+mic+enviar, fixa por cima da lista de chat que
rola) usava `background: var(--bg)` solido - um retangulo opaco sem blur nem canto arredondado,
so pra tapar as bolhas rolando por baixo. Com o resto do app em vidro fino (round 6), esse
retangulo de bordas retas ficava destacado, sem se misturar com nada ao redor. Virou um degrade
(transparente no topo -> solido embaixo) com um blur leve - a ultima bolha visivel esmaece
suavemente em vez de cortar numa linha reta, continuando a tapar o texto por baixo o suficiente
pra nao ficar ilegivel sobreposto.

**Artefato virou um laboratorio de estilo de verdade** (pedido explicito: "adiciona mais umas 10
fontes, mais umas 10 cores... e tambem liquid glass em questoes, em alguns lugares so... pra gente
terminar de uma vez"). O widget "Comparar estilos" (so existe no artefato) foi reescrito do zero:
- **Fonte**: 4 -> 13 combinacoes (Atual/Sora, Editorial, Revista, Anterior + Moderno/Space Grotesk,
  Humanista/DM Sans, Tecnico/IBM Plex, Fino/Fraunces, Redondo/Quicksand, Suico/Work Sans,
  Contraste/Bodoni Moda, Mono/JetBrains Mono, Popular/Poppins) - a lista de `<link>` do Google
  Fonts no `<head>` ganhou as familias novas.
- **Cor de destaque**: 4 coloridas + 4 neutras (round 5) -> 9 coloridas (+ rubi, cobre, petroleo,
  indigo, ametista escura) + 9 neutras (+ carvao, marfim frio, bronze fosco, chumbo, preto quase
  puro) = 18 no total.
- **Cor de fundo** (nova secao): 5 opcoes que trocam `--bg`/`--surface`/`--surface-2`/`--surface-3`
  juntos (Atual, Preto puro, Grafite quente, Azul meia-noite, Verde-petroleo escuro) - antes so
  dava pra trocar a cor de destaque, nao o preto de base.
- **Liquid Glass ligado/desligado por area** (nova secao): 3 toggles independentes (Paineis,
  Barra inferior, Campos de texto) que removem blur/vidro so daquela area, pra comparar com/sem
  lado a lado. Implementado sobrescrevendo as propriedades renderizadas direto (`background`,
  `backdrop-filter`) com `!important` nos mesmos seletores que ja usam vidro, em vez de mexer nos
  tokens `--glass-*` - evita de proposito a pegadinha de indirecao de custom properties ja
  documentada no CSS real (nao teria efeito confiavel dentro de `#tab-hoje`/etc, que redeclaram o
  conjunto inteiro).
- O painel do comparador cresceu (agora ocupa quase a tela toda, com scroll) pra caber tudo isso
  sem ficar espremido.

Tudo isso e so pro Alex testar ao vivo e decidir - nenhuma fonte/cor/fundo novo virou padrao do
app de verdade, e nenhum foi validado por `scripts/validate_palette.js` ainda.

Validado com `node --check` nos 4 blocos `<script>`, Playwright confirmando que clicar em fonte/
cor/fundo/toggle atualiza `getComputedStyle` corretamente e se propaga pro app inteiro (nao so
pro widget). 800 testes Python, 100% passando (so o CSS real mudou - `.chat-form` -, o resto foi
so no artefato).

## 2026-09-22 (6) - Liquid Glass round 6 (transparencia de verdade, removida a mancha branca)

O Alex mandou dois prints lado a lado: o `#chat-input` do nosso app (uma mancha branca diagonal
por cima de um fundo cinza opaco) e o Control Center real do iOS. A diferenca principal: o vidro
de verdade da Apple e MUITO mais transparente (da pra ver claramente o que ta atras, so borrado),
quase sem cor propria somada, com borda/brilho finos e discretos - nunca uma mancha de luz
concentrada. Frase-chave: "ele não tem um branco nem nada".

**Causa raiz encontrada**: `--glass-specular`, adicionado no round 5 como um blob radial branco
forte (55% de opacidade) num canto, ficava proporcionalmente enorme e virava uma mancha/risco
diagonal em qualquer elemento largo e baixo - exatamente o `#chat-input`/`#captura-input` do
print. Removido de vez (nao so reduzido).

**Reescrita completa da receita `--glass-*`** pra bater com o material real:
- `--glass-highlight` deixou de ser um blob radial e virou um degrade LINEAR bem fraco (16%→4%→0)
  so na borda de cima - da o "luz pegando a borda" sem virar ponto de luz isolado.
- `--glass-glow` (halo colorido no canto) caiu de 68% pra 30% de opacidade - a identidade de cor
  da secao continua ali, so que discreta, nao dominando.
- O preenchimento base (`--glass-bg`) trocou o degrade tint+surface por uma mistura bem mais
  transparente (`color-mix(var(--glass-tint) 9%, color-mix(var(--surface) 26%, transparent))` -
  antes a cobertura de opacidade chegava a 55-65%, agora fica bem mais baixa) - com isso o
  `backdrop-filter` por tras finalmente aparece de verdade, que e o que faz ler como vidro e nao
  "plastico colorido opaco com brilho em cima".
- Blur/saturacao/brilho do `backdrop-filter` desceram um pouco (42px→36px, 230%→150%, 1.14→1.06)
  - hiper-saturado tambem lia como "processado demais", nao como vidro limpo.
- `--glass-border` e `--glass-shadow` ficaram mais finos e com menos opacidade - uma linha
  discreta, nao uma borda grossa de duas camadas.
- `#tabbar` (que tinha ganhado o mesmo `--glass-specular` no round 5) seguiu a mesma dieta -
  fundo bem menos opaco (0.85/0.88→0.6/0.68), blur/saturacao reduzidos, sombra simplificada.
- `.stat-tile`/`.card-resultado` (opacos, cor validada por acessibilidade - nao mudam a formula de
  fundo) so perderam a referencia ao `--glass-specular` removido, mantendo `--glass-highlight`
  (agora sutil) como unico acabamento de brilho.

Artefato-replica regenerado (mesmo link) com o CSS atual. Comparado visualmente com print do
`#chat-input` antes/depois - a mancha diagonal sumiu, o campo agora le como vidro fino e
transparente em vez de plastico com brilho. 800 testes Python, 100% passando (CSS puro).

## 2026-09-22 (5) - Liquid Glass round 5 (qualidade do material + barra flutuante) + artefato com testador de cores neutras

O Alex mandou print de referencia (barra de abas do Instagram) e disse que o Liquid Glass do
round anterior estava "uma qualidade horrivel" e que a barra inferior (`#tabbar`) precisava
flutuar de verdade, tipo iOS, com sombra dando profundidade - nao ficar colada/reta na borda de
baixo da tela como estava.

**Material do vidro em si ficou mais rico**: os tokens `--glass-*` (topo do `style.css`) ganharam
uma segunda camada de brilho especular menor e mais forte (`--glass-specular`, o "ponto de luz"
concentrado, nao so o halo difuso que ja existia em `--glass-highlight`), uma borda com DUAS
linhas simulando espessura de vidro visto de canto (`--glass-rim` - clara externa, escura
interna), e o blur/saturacao subiram (28px→42px de blur, 190%→230% de saturacao - blur raso era
o que mais lia como "borrado tosco" em vez de vidro de verdade). `--glass-shadow` ganhou uma
camada extra de contato bem curto e escuro (a mesma logica que `--shadow-card` ja usava pros
cards solidos), sem ela os paineis pareciam flutuar de forma generica. `.stat-tile` e
`.card-resultado` tambem ganharam a camada `--glass-specular` e um anel de borda mais definido
(sem mexer na formula de cor de fundo ja validada por acessibilidade).

**`#tabbar` virou uma pilula flutuante de verdade**: antes ficava `bottom: 0`, largura 100%,
sem `border-radius` proprio - colada e reta na borda de baixo. Agora tem margem da borda
(`bottom: calc(0.85rem + safe-area-inset-bottom)`, largura menor que 100%), `border-radius: 999px`
(pilula completa), fundo proprio mais escuro/neutro (nao tingido por `--glass-tint` da secao de
proposito - e a unica peca de chrome visivel o tempo todo, tingir ela mudaria de cor a cada troca
de aba) com `backdrop-filter: blur(46px) saturate(240%)`, e sombra em duas distancias (contato
curto + queda longa) pra realmente ler como "no ar" sobre o conteudo. `body` (padding-bottom) e
`.chat-form` (bottom) foram ajustados pra abrir espaco pra pilula sem esconder conteudo atras
dela. Pra 7 abas caberem numa pilula mais estreita sem quebrar linha, reduzi levemente
font-size/gap/padding dos botoes e troquei `overflow-wrap: anywhere` (que deixava o texto quebrar
em varias linhas, desalinhando os botoes entre si) por `white-space: nowrap` + `text-overflow:
ellipsis` no rotulo - nas larguras de iPhone mais comuns (390-430px) todos os rotulos cabem
inteiros; so no menor tamanho testado (iPhone SE, 375px) "Financeiro"/"Construtora" truncam com
reticencias (nunca quebram feio nem sobrepoe o vizinho).

Tambem reforcei o `.aurora` de fundo (blobs radiais atras de tudo) - opacidade um pouco mais alta
e um quarto blob (dourado, canto inferior-direito) - o Alex citou "o fundo que e feito de
profundidade, ta faltando isso": o vidro sozinho não cria profundidade se não houver o que borrar
atrás dele.

**Artefato-replica regenerado** (mesmo link, `https://claude.ai/artifact/Ecy9gXXfefAgWkeTA5DojR`)
com o CSS/JS atuais coladas verbatim. O widget de comparação de estilo (so existe no artefato, pra
testar ao vivo sem mexer no app de producao) ganhou uma segunda fileira de swatches - 4 combinacoes
neutras (Grafite, Platina, Onix, Titanio - cinza/preto, pedido explicito "mais luxo") ao lado das
4 coloridas que ja existiam, pra comparar lado a lado antes de decidir se alguma vira a paleta
oficial. Nenhuma delas foi rodada no `scripts/validate_palette.js` ainda - isso e so pra
visualizar, nao pra adotar direto.

Validado com `node --check` nos 4 blocos `<script>` do artefato, Playwright servindo por HTTP
(fetch mock quebra em `file://` por CORS) confirmando a pilula flutuante, `getComputedStyle`
trocando de cor ao clicar num swatch neutro, e nenhum log de erro alem de um 404 esperado
(service-worker nao existe fora do app real). 800 testes Python, 100% passando (mudanca so em
CSS, nenhuma logica de backend tocada).

## 2026-09-22 (4) - Liquid Glass colorido em (quase) tudo + achado real de CSS

O Alex pediu de manha (fora do horario noturno, autorizado a trabalhar na hora): Liquid Glass
"em tudo", mas diferente do iOS puro - colorido, usando as cores de identidade que o painel ja
tem por secao, com mais profundidade ainda.

**Vidro tingido por secao**: cada aba (`#tab-hoje`, `#tab-tarefas`, `#tab-gastos`, etc) agora
redefine `--glass-tint` pra sua propria `--cor-X` - tudo que usa os tokens `--glass-*` dentro
dela fica automaticamente tingido, sem marcar elemento por elemento. Cada painel ganhou uma
terceira camada de luz alem do brilho branco especular (`--glass-highlight`): um halo colorido
no canto oposto (`--glass-glow`, "luz atravessando o vidro colorido e saindo do outro lado") -
e a sombra (`--glass-shadow`) passou a levar um brilho ambiente na cor da secao, nao so preto,
pra reforcar o "flutuando".

**Achado real no processo (nao foi so estetica)**: a primeira tentativa de fazer isso nao
funcionou - toda aba renderizava a MESMA cor (verde), nao a cor certa por secao. Investigando
com `getComputedStyle` (nao só olhando a tela), descobri uma pegadinha real e documentada de CSS
custom properties: quando um token composto tipo `--glass-shadow` e definido UMA VEZ no `:root`
e contem `var(--glass-tint)` por dentro, esse `var()` interno so e resolvido lá no `:root`
(usando o `--glass-tint` do `:root`) - um filho la embaixo que so redefine `--glass-tint`
(sem redefinir `--glass-shadow` tambem) herda a STRING JA PRONTA com a cor errada "congelada"
dentro, nao recalcula nada. Fix: cada aba (e tambem `.stat-tile`/`.card-resultado`, que tem cor
propria por tile) redefine o CONJUNTO INTEIRO de tokens compostos, nao so `--glass-tint`.
Documentado com comentario extenso no CSS pra nenhuma sessao futura cair nisso de novo.

Tambem apliquei vidro nos campos de captura/chat (`#captura-input`, `#duvida-input`,
`#chat-input`) e um acabamento (brilho especular, sem trocar a cor) na aba ativa da barra
inferior - essa continua com a cor de marca fixa por decisao antiga e deliberada (documentada no
proprio CSS), nao virou arco-iris por secao.

Testado visualmente com Playwright em todas as 7 abas + `getComputedStyle` pra confirmar a cor
resolvida em cada uma antes e depois do fix. 800 testes, 100% passando (CSS puro, sem mudanca de
logica/schema).

## 2026-09-22 (3) - Loop noturno (ciclo 1): Liquid Glass v2 + palavra surgindo no chat

O Alex foi dormir e pediu trabalho autonomo ate 7:30 da manha, focado em duas coisas que ele
disse que estavam faltando: o Liquid Glass "ta horrivel" (precisa parecer vidro de verdade,
flutuando) e falta de animacao "tipo, ta escrevendo, as palavras vao surgindo".

**Liquid Glass v2** (`static/css/style.css`): a v1 (sessao anterior) so tinha tint translucido +
blur - sem nada capturando luz, lia como "cinza sujo" em vez de vidro. Adicionado
`--glass-highlight` (mancha de luz radial no canto superior-esquerdo, onde a luz bateria) somado
ao tint no `--glass-bg`; `--glass-border` ficou mais claro (32% branco em vez de 16%); `--glass-blur`
ganhou `brightness(1.08)` (vidro de verdade clareia o que ta atras, nao so borra); novo
`--glass-shadow` soma um par de insets (claro no topo, escuro embaixo - "espessura" do vidro) na
sombra normal, aplicado nos mesmos 8 paineis que ja eram glass (nenhum novo elemento virou glass
nessa rodada, so ficou melhor o que ja era). O tabbar (barra de abas) tambem ganhou o highlight e
um inset de brilho na borda de cima.

**"Palavra surgindo" no chat** (`static/js/app.js` + `static/css/style.css`): resposta NOVA do
assistente (nunca o historico recarregado - isso ficaria estranho) entra palavra por palavra, cada
uma com fade-in + blur-out + leve subida, atraso calculado pra sempre terminar em ~700ms
independente do tamanho da resposta (min 8ms/max 24ms por palavra). `prefers-reduced-motion`
desliga a animacao (acessibilidade). Testado via Playwright injetando a funcao real do app.js e
capturando o meio da animacao - efeito renderiza como esperado.

800 testes, 100% passando (mudanca e CSS/JS, sem impacto em logica de backend).

## 2026-09-22 (2) - Saldo bancario antes/depois + Notas com tags + auditoria de deploy

O Alex mandou 30 prints do Nectar (assistente pessoal completo - tarefas, habitos, financas,
agenda, notas, tudo numa mensagem so, com proatividade e widgets nativos). Comparei com o que
ja temos: a maior parte ja existe (mensagem unica virando varias acoes, cutucada proativa que
aprende, Uber com OAuth de verdade - mais robusto que o deles). Peguei os dois pedacos reais que
faltavam e que dao pra fazer sem app nativo:

**Saldo do banco antes -> depois** (`db.py`, `claude_client.py`, `app.py`): `bank_accounts` ganhou
uma coluna `saldo`, atualizada de verdade a cada sincronizacao com a Pluggy (o campo `balance` que
a API ja devolvia e a gente simplesmente descartava). Quando o Alex cita o banco no chat/Telegram
("paguei pelo Pix do Nubank"), `registrar_gasto`/`registrar_renda` acham a conta pelo nome e
ajustam o saldo de forma otimista (ate a proxima sincronizacao reconciliar), devolvendo
antes/depois pra IA falar de volta - so quando o banco foi citado E a conta ja tem saldo
conhecido, nunca inventa um numero.

**Notas com tags** (tabela `notas` nova): pra anotacao mais longa que nao e tarefa/gasto/lembrete
- um roteiro, uma lista, um plano. `salvar_nota` e `consultar_notas` no chat, secao nova na aba
Painel (mesmo padrao visual de "O que eu lembro sobre voce").

**Correcao de bug flagrante achada na auditoria**: `deploy/Caddyfile` ainda dizia "o painel nao
tem login proprio" e chamava o Basic Auth de OBRIGATORIO - isso e de antes do login por PIN
existir (`auth.py`) e contradizia o proprio `DEPLOY.md` (secao 0), que ja documenta o PIN como
suficiente e o Basic Auth como camada extra opcional. Corrigido o comentario. Resto do fluxo de
deploy (`wsgi.py`, `painel.service`, `requirements.txt`, chaves VAPID) conferido e consistente -
nada mais pra ajustar antes de ele migrar pra VPS quando quiser.

O Alex tambem pediu pra investigar a "notificacao push do Safari" que ele confundiu com o
"Notificar-me" do iOS 27 (documentado na entrada anterior) - esclarecido que sao coisas
diferentes: o Web Push de verdade (que ele quer) ja esta 100% implementado (botao "Ativar
notificacoes" + 5 verificacoes proativas rodando), so falta hospedar num dominio com HTTPS
de verdade pra funcionar no iPhone (regra da propria Apple, nao falta de codigo) - ele decidiu
adiar a hospedagem por enquanto e so deixar o sistema pronto.

800 testes (28 novos), 100% passando.

## 2026-09-22 (1) - "Liquid Glass" nos paineis + pesquisa de concorrentes (Nectar, Pierre, Zapia, Luzia, Base44)

O Alex mandou 5 links pra eu avaliar como concorrentes/referencia (meu-nectar.com, Pierre
Finance, Base44, Zapia, Luzia). Entrei em cada um: Pierre Finance e o mais parecido com o
nosso painel (WhatsApp+app+web, Open Finance, categorizacao, deteccao de cobranca duplicada,
metas) - cobra R$39 a R$199/mes por praticamente tudo que a gente ja tem de graca; a unica
diferenca real e usar WhatsApp em vez de Telegram como canal. Zapia e Luzia sao assistentes
generalistas (nao financeiros), Base44 e uma plataforma no-code pra montar agentes (nao um
produto pronto) - nenhum dos tres muda a analise. Nectar nao carregou conteudo real (SPA sem
JS renderizado no fetch).

**CSS "Liquid Glass" (pedido explicito, inspirado no iOS)**: os paineis retangulares (caixa de
resumo, grafico, itens de lista, bolha de chat do assistente, tabbar) deixaram de ser uma
superficie solida e viraram vidro translucido - novo token `--glass-bg` (gradiente com
`color-mix(..., transparent)`) + `--glass-blur` (`backdrop-filter: blur(24px) saturate(165%)`)
+ `--glass-border` (borda mais clara, tipo reflexo). O fundo colorido do `.aurora` (que ja
existia, fixo atras de tudo) agora borra por tras dos cards, dando a sensacao de profundidade/
"flutuando por cima" que o Alex pediu. Deixei de fora, de proposito, os tiles/cards com cor de
secao (`.stat-tile`, `.card-resultado`) - a paleta deles foi validada por acessibilidade
(script `scripts/validate_palette.js`, ver comentario no topo do `style.css`) e mexer na
mistura de cor ali quebraria essa validacao sem rodar o script de novo.

Testado visualmente: subi o app local (Flask + SQLite descartavel, nao e o banco real),
naveguei nas abas Hoje/Tarefas/Financeiro via Playwright/Chromium e conferi print a print que
o efeito renderiza como esperado (cor do aurora visivel atras dos cards, texto ainda legivel).
772 testes, 100% passando (mudanca e so CSS, nao mexe em logica).

O Alex mandou o material da Apple sobre o iOS 27 perguntando se ajudava o painel. Avaliei: a
maioria (App Intents, Foundation Models, Live Activities, Widgets) exige app nativo Swift na App
Store - fora do escopo (o painel e Flask/PWA), sem contar que o ganho de App Intents (acionar
por voz sem frase fixa) ja e coberto de graca pelo Atalho "Ei Siri, anota" que ja existe. A unica
coisa aproveitavel sem reescrever nada e Passkeys via WebAuthn pra trocar o login por PIN por
Face ID/Touch ID direto no PWA - aprovado, mas ainda nao implementado (fica pra proxima sessao).

Tambem investiguei push notification no navegador: descobri que isso ja existe desde o iOS 16.4
(nao e novidade do 27) e exige o painel instalado na Tela de Inicio - mas o bot do Telegram ja
cobre esse papel. O Alex corrigiu: o recurso novo de verdade do iOS 27 e o **"Notificar-me"** do
Safari (Notify Me) - descreve em texto livre o que quer detectar numa pagina, e o Safari checa em
segundo plano usando Apple Intelligence no aparelho, notificando so quando a mudanca acontece.
Exige Apple Intelligence ligado (iPhones mais recentes). E 100% do lado do Safari, nao precisa de
nada no codigo do painel - documentei no README como apontar pra uma pagina existente (ex: aba
Hoje) pra ele testar quando quiser, deixando claro que nao substitui o Telegram (que e instantaneo
e usa a logica exata que construimos) ate ele testar na pratica e decidir se vale mais.

Sem mudanca de codigo/schema - so README, entao sem necessidade de rodar a suite de testes.

## 2026-09-21 (11) - Noticias sob demanda (Google News RSS) + confirmado que Saude ja conecta

O Alex perguntou por outras fontes de dado pro assistente (noticias de Brusque, algum app com API
gratuita) e se o Apple Saude ja conectava. Confirmei que Saude ja conecta (via Atalhos do iPhone,
ja documentado - nao existe API na nuvem da Apple Health, so o caminho local mesmo). Pra noticias,
achei o feed RSS publico do Google News (gratuito, sem chave) e perguntei como ele queria receber -
resumo diario, notificacao proativa, ou so quando perguntasse. Escolheu **so quando perguntar no
chat**, de proposito pra nao virar mais ruido automatico.

**`noticias.py` (modulo novo):** `buscar_manchetes(termo, limite=5)` busca no feed RSS do Google
News (`news.google.com/rss/search`, sem chave/cadastro) e devolve titulo/fonte/link/data - tira o
sufixo redundante " - Nome da Fonte" que o proprio feed repete no titulo. Erro de rede ou XML
malformado nunca derruba quem chamou, devolve lista vazia (mesmo padrao de erro de `clima.py`).

**Tool `consultar_noticias` no chat:** SO dispara quando o Alex pede explicitamente ("tem noticia
de Brusque?") - nunca por conta propria, nunca notificacao proativa (decisao dele). Sem resultado,
a IA diz que nao achou nada - instrucao explicita no prompt pra nunca inventar manchete.

772 testes (14 novos), 100% passando.

## 2026-09-21 (10) - Cobranca generica (Apple) identificavel pelo chat + gastos fixos enxergam o banco

O Alex perguntou se dava pra conectar com as assinaturas do iPhone/iCloud. Pesquisei: nao existe
API (paga ou gratuita) que deixe um app de terceiros ler a lista de assinaturas do Apple ID -
bloqueio de plataforma por privacidade, nao uma peca faltando. Perguntou tambem se tinha algum
outro app/API gratuita que ajudasse o assistente financeiro - resposta honesta: nao, o Pluggy (ja
integrado) ja e a peca que importa. Ele aprovou uma alternativa: reconhecer o PADRAO da cobranca
("apple.com/bill") no extrato e perguntar uma vez qual assinatura e - e pediu pra isso (e tudo mais
que for possivel) rodar sem gastar credito de IA quando puder ser feito por Python puro.

**Descoberta no caminho: gastos fixos/orcamento/sobra do mes so enxergavam `expenses` (digitado no
chat), nunca `bank_transactions` (extrato sincronizado via OFX/Pluggy).** Isso era uma lacuna real -
a maior parte do gasto de quem usa sincronizacao bancaria simplesmente nao entrava na conta.
`app._gastos_reais_unificados()` unifica as duas fontes (normalizando pra um formato so); `_gastos_fixos`
e `_sobra_do_mes` passam a usar isso. Ressalva documentada no README (mesmo espirito do aviso ja
existente na aba Bancos): sem reconciliacao entre as duas fontes, um gasto digitado no chat E
sincronizado depois pelo banco conta duas vezes.

**Reconhecimento de cobranca generica (`gastos.e_cobranca_generica`, zero custo de IA):** so
reconhecimento de texto (`PADROES_COBRANCA_GENERICA`, hoje so "apple.com") - `notificacoes.cobrancas_genericas_sem_rotulo()`
acha cobrancas desse padrao (em expenses OU bank_transactions) sem apelido ainda, avisa uma vez por
descricao+valor. **Rotulagem pelo chat (`rotular_cobranca_generica`, essa parte SIM usa IA - e
conversa em linguagem natural):** "a cobranca da apple de 14,90 e o icloud" salva o apelido
(`apelidos_gasto`, chave descricao normalizada + VALOR exato - nao so descricao, pra "iCloud" e
"Apple Music" nunca se confundirem mesmo com o mesmo texto de cobranca). `gastos.aplicar_apelidos()`
troca a descricao pelo apelido ANTES de agrupar recorrencia, entao o resto da deteccao nem precisa
saber que isso existe.

758 testes (31 novos), 100% passando.

## 2026-09-21 (9) - Assistente financeiro de verdade + botao de acao no Telegram

O Alex perguntou se o painel realmente ajuda como assistente financeiro e o que faltava. Depois de
comparar Claude/Gemini/GPT-5/DeepSeek/o3-mini por custo-beneficio (recomendacao: continuar no
Claude - a diferenca de preco e irrelevante no volume de uso pessoal dele, e trocar de provedor
custaria reescrever `claude_client.py` inteiro por uma economia que nem apareceria na fatura),
aprovou 4 features financeiras + o botao de acao no Telegram que ja tinha sido proposto antes.

**Renda pelo chat (`incomes`, `registrar_renda`).** Ele nao tem salario fixo (dono de construtora -
dinheiro entra de jeito variado), entao em vez de cadastro fixo, ele so conta no chat ("entrou 3000
na conta", "recebi 500 do fulano", "vendi um material e entrou 800") - categoria `venda`/`cliente`/
`reembolso`/`outros`, decidida pela IA.

**Orcamento por categoria (`orcamentos`, `definir_orcamento`).** "Quero gastar no maximo 800 em
mercado por mes" define um limite mensal por categoria - `notificacoes.orcamentos_perto_ou_estourados()`
avisa uma vez quando o gasto real bate 90% ("quase") e de novo quando passa de 100% ("estourado"),
dedup por categoria+nivel+mes via hash estavel (`_id_estavel_orcamento`, mesmo padrao ja usado pras
contas a pagar da construtora) - o mes seguinte, com o gasto zerado, ganha chave nova sozinho.

**Deteccao de gasto recorrente/assinatura (`gastos.detectar_gastos_recorrentes`).** Agrupa gastos
reais por descricao normalizada (igualdade exata, nao palavra em comum - agrupar errado aqui e pior
que nao agrupar) que se repete em 2+ dos ultimos 3 meses com valor parecido (tolerancia de 15%) -
Netflix, academia, aluguel. `consultar_gastos_fixos` no chat devolve a lista e o total mensal
comprometido.

**Quanto sobra pra gastar (`gastos.sobra_do_mes`).** Renda do mes menos gasto real do mes -
retrospectivo (nunca tenta prever gasto futuro), mais o quanto esta so planejado/cogitado como
aviso a parte (reaproveita o `tipo='planejado'` que ja existia, sem duplicar o conceito).
`consultar_sobra_do_mes` no chat.

**Botao de acao no Telegram.** A cobranca de tarefa parada ganha um botao inline "Marcar como
feito" - um toque completa a tarefa sem abrir o app. Feito no Telegram (nao no push web) porque
botao de acao em push de PWA e instavel no iPhone; Telegram suporta isso solido em qualquer
aparelho. `telegram_bot.py` ganhou `processar_callback`/`responder_callback`/`remover_botoes`
(fecha o "carregando" do botao e tira o teclado depois do toque, evitando clique duplo);
`app._telegram_callback_fn` fecha o loop de aprendizado igual o `complete_task_rota` normal.

**Bonus: flakiness real corrigida.** Descobri (rodando a suite completa as 22h) que praticamente
todo teste de `verificar_e_notificar` dependia do relogio de verdade - o modo silencioso padrao
(22:00-07:00, mais de um terco do dia) fazia a suite falhar sempre que rodasse nessa janela, ha
meses sem ninguem perceber. `PainelTestCase.setUp` agora fixa `dentro_do_horario_silencioso` como
"nunca silencioso" por padrao (os 2 testes que testam silencioso de verdade continuam
sobrescrevendo isso com seu proprio patch).

727 testes (82 novos), 100% passando.

## 2026-09-21 (8) - Colar trecho exportado do WhatsApp no chat

O Alex mostrou que ultimamente anota as coisas pra fazer direto no WhatsApp (mensagem pra ele
mesmo), nao no painel - mandou um exemplo real: linhas exportadas no formato "[DD/MM/AAAA,
HH:MM:SS] alex: texto", uma delas com 3 itens soltos dentro da MESMA mensagem colchetada.
Perguntei como ele queria trazer isso pro painel (colar no chat vs integracao direta com WhatsApp
vs importar arquivo de export) - escolheu colar no chat.

**`CHAT_SYSTEM_PROMPT` (claude_client.py) ganhou uma instrucao especifica pro formato de export do
WhatsApp:** reconhecer o padrao "[data, hora] nome: texto" e IGNORAR completamente a data/hora
entre colchetes - isso e so metadado de quando ele anotou, nunca a data em que a tarefa precisa
ser feita (senao toda tarefa colada nasceria "atrasada" do nada, ja que ele as vezes anota com
dias/semanas de antecedencia). Reforça tambem que uma mensagem colchetada com varias linhas soltas
dentro vira uma `registrar_tarefa` por linha, nao uma tarefa so.

**Teste golden-path com o exemplo real do Alex** (`test_chat_cola_trecho_exportado_do_whatsapp`):
simula a classificacao ideal (a que o novo trecho do prompt pede) pro texto exato que ele colou -
confere que as 7 tarefas nascem certas e nenhuma com due_date vindo do colchete. Como isso e uma
mudanca de prompt (comportamento generativo, nao deterministico), nao da pra garantir por teste
automatizado que o modelo real vai classificar exatamente assim - o teste confirma que SE
classificar assim, o app faz a coisa certa; a qualidade real da classificacao pede um teste ao
vivo com a chave da Anthropic de verdade.

645 testes (1 novo), 100% passando.

## 2026-09-21 (7) - Aprendizado bem mais profundo, 100% por tras das cameras

O Alex achou o aprendizado da entrada anterior bom mas raso ("quero ele muito mais esperto,
perceber tudo basicamente"), com uma condicao clara: nada disso pode aparecer na tela ou virar
frase tipo "eu aprendi que...". Continua tudo em `aprendizado.py`, so que 4 sentidos mais fundos,
todos silenciosos - o unico efeito visivel e o COMPORTAMENTO mudando (quando cutuca, que dia
sugere), nunca uma explicacao de si mesmo. `GET /api/aprendizado` (auditoria tecnica, nenhuma tela
chama) segue sendo o unico jeito de ver o que foi aprendido, se alguem quiser checar na mao.

**Aprende por titulo/quem parecido, nao so um numero global.** `dias_atraso_por_titulo_semelhante()`
e `dias_espera_por_quem_semelhante()` agrupam pelo token relevante em comum (mesmo tokenizador de
`gastos.sugerir_categoria`, sem precisar de campo de categoria manual em tarefa/espera - ninguem ia
preencher isso). "Cotar portas com fornecedor" e "cotar vasos com fornecedor" aprendem juntas; duas
tarefas sem nada em comum, cada uma com seu proprio ritmo. `limiar_tarefa()`/`limiar_espera()`
encapsulam o fallback completo: especifico (5+ amostras do mesmo grupo) → global (janela recente) →
padrao fixo.

**Da mais peso ao que e recente.** `dias_atraso_historico_tarefas()`/`dias_espera_historico()`
ganharam um parametro `janela` - o limiar global agora usa so as ultimas 20 amostras (mais recente
primeiro, por data de conclusao/resolucao), nao a mediana de todo o histórico desde sempre. Se voce
mudou de ritmo recentemente, o painel percebe mais rapido.

**Aprende se a propria cutucada funciona.** `_ajustar_pela_eficacia()`: quando a latencia media
entre ser cutucado e resolver e baixa (≤24h - voce age rapido assim que avisado), o limiar cai mais
1 dia (nunca abaixo do piso) - vale a pena avisar cedo, ja que funciona. Quando a resposta e lenta
mesmo depois de avisado, mantem como estava - cutucar mais cedo nao ajudaria em nada.

**Produtividade real por dia da semana, nao so carga agendada.** `produtividade_por_dia_semana()`
mede a taxa de tarefas concluidas NO PRAZO por dia da semana do vencimento (min. 3 amostras por
dia). `agenda.sugerir_dia_menos_corrido()` ganhou um parametro opcional que usa isso como um
desempate leve (peso 0.5, nunca sobrepõe uma carga bem menor) - entre dois dias com carga parecida,
prefere o dia em que voce historicamente da conta melhor.

Tudo ligado direto em `verificar_e_notificar()` (busca ampla + filtro item a item, ja que cada
tarefa/espera pode ter seu proprio limiar agora) e em `exec_registrar_tarefa` (sugestao de dia).
644 testes (34 novos), 100% passando.

## 2026-09-21 (6) - Aprendizado de padrao pessoal + catch-up de fim do dia

Depois do bot do Telegram, o Alex pediu duas coisas: (1) o painel aprender de verdade com o
proprio historico dele - "muito bem minucioso, que nao se perde, que guarda os dados, que pega
padroes" - e (2) um jeito de contar no chat, no fim do dia, coisas que ja fez mas nunca tinha
registrado em tempo real. Ele tambem perguntou se dava pra usar o Neural Engine do iPhone (A19)
pra isso - explicado que um PWA/Flask nao alcanca hardware nativo (precisaria de Core ML/Swift),
e que o problema real (personalizar limiares numericos com base num historico pessoal pequeno) nao
precisa de ML: estatistica pura em cima do que ja esta no banco resolve, com decisao auditavel
(nunca caixa preta) - a escolha deliberada de manter a filosofia "sem IA" do resto do codebase.

**`aprendizado.py` (modulo novo):** `limiar_personalizado()` decide, pra cada tipo de cutucada
(tarefa parada, espera parada), se usa o padrao conservador de sempre ou um valor aprendido - so
aprende com 5+ amostras (`minimo_amostras`), usa a MEDIANA (robusta a um caso fora da curva, ao
contrario da media) arredondada e sempre limitada a um piso/teto de seguranca. `dias_atraso_historico_tarefas()`
e `dias_espera_historico()` extraem a amostra direto de `tasks`/`esperas` (devido/concluido,
criado/resolvido) - nenhuma tabela nova precisa pra isso, o dado ja existia. `latencia_media_horas()`
usa MEDIA (nao mediana) de proposito: aqui um valor extremo e sinal real sobre o quanto a cutucada
esta funcionando, nao ruido pra filtrar.

**Fechamento do loop de aprendizado:** tabela nova `interacoes_aprendizado` registra quando cada
cutucada de `tarefa_parada`/`espera_parada` foi *de fato enviada* (nao so quando a condicao ficou
verdadeira) e, ao ser resolvida, calcula a latencia em horas (`julianday()` do SQLite). `complete_task()`
foi movido de dentro da rota Flask pra `db.py` (rota renomeada pra `complete_task_rota` - so o nome
da funcao Python, a URL `/api/tasks/<id>/complete` continua igual) e `resolver_espera()` passou a
fechar a interacao junto, sem duplicar essa logica em mais de um lugar.

**Limiares aprendidos ligados de verdade:** `verificar_e_notificar()` agora calcula
`dias_minimo` de `tarefas_paradas`/`esperas_paradas` via `limiar_personalizado()` a cada rodada, em
vez do numero fixo de antes (3 e 5 dias) - assim que houver historico suficiente, cobra no ritmo
real de cada um. Endpoint novo `GET /api/aprendizado` mostra o que foi aprendido pra cada tipo
(limiar atual, se veio do padrao ou foi aprendido, quantas amostras, latencia media de resposta) -
transparencia deliberada, pra nunca virar caixa preta.

**Catch-up de fim do dia:** tool nova no chat, `registrar_feito` - "fiz academia, paguei a conta de
luz e resolvi aquele negocio do fornecedor" no fim do dia registra cada coisa mencionada.
`db.marcar_ou_criar_feito()` tenta achar uma tarefa pendente parecida (mesmo match aproximado por
substring usado em cotacoes/esperas) e marca ela concluida (fechando o loop de aprendizado
tambem, via `complete_task()`); sem achar, cria uma tarefa nova ja nascendo concluida - registro
honesto de trabalho feito fora do planejado.

610 testes (57 novos: `tests/test_aprendizado.py` criado do zero + extensoes em `tests/test_app.py`
e `claude_client.py`), todos passando.

## 2026-09-21 (5) - Bot do Telegram + 3 features de "funcionario particular"

Continuação da conversa sobre o que falta pra sentir como um assistente humano dedicado, não só
um app de rotina - o Alex pediu as outras 3 direções primeiro, depois o bot do Telegram.

**Mensagem de fechamento ativa à noite:** `notificacoes.fechamento_noturno_devido()` (janela das
21h, uma hora antes da `hora_de_dormir`) manda o fechamento do dia sozinho por push
(`mensagem_fechamento_noturno()` - concluídas, pendentes e gasto do dia, sem IA) em vez de esperar
você abrir a aba Painel pra ver.

**Voz de volta no chat:** cada resposta do assistente agora tem um botão de "ouvir" (mesmo
mecanismo já usado no METAR/TAF, `SpeechSynthesis` do navegador) - antes só dava pra falar com o
painel, não pra ele falar de volta.

**Esperas - threads pendentes com terceiros:** nova seção "Esperando resposta de" (aba Painel) e
tabela `esperas` - acompanha resposta que você está esperando de fornecedor/corretora/etc,
diferente de tarefa (que é algo que *você* precisa fazer). Registra e resolve por conversa
(`registrar_espera`/`resolver_espera`, tools novas do chat, com match aproximado por nome) ou
manual. Cobra uma vez só depois de 5 dias sem resposta (`notificacoes.esperas_paradas()`), mesmo
padrão de disparo único do `tarefa_parada`.

**Bot do Telegram como canal principal:** novo `telegram_bot.py` - você conversa com o painel
direto pelo Telegram, como mandando mensagem pra uma pessoa. Reaproveita o pipeline de chat
inteiro (extraído de dentro da rota `/api/chat` pra `_processar_mensagem_chat()`, fonte única de
verdade usada pelos dois canais) e long polling (`getUpdates`, sem precisar de URL pública/HTTPS).
`verificar_e_notificar()` agora manda pros dois canais configurados (push web e/ou Telegram, não
precisa mais dos dois - só um já basta). Autorização por `TELEGRAM_CHAT_ID`: mensagem de qualquer
outro chat é ignorada em silêncio, nunca processada.

528 → 553 testes (25 novos), todos passando.

## 2026-09-21 (4) - De app de rotina pra assistente: 4 features de proatividade

Pedido do Alex depois de discutir o que separaria o painel de "app de anotar rotina" pra
"funcionário particular": 4 direções, implementadas uma de cada vez.

**1. Fechar loops (cobrança individual, não só contagem).** `notificacoes.tarefas_paradas()`
identifica tarefas atrasadas há 3+ dias e cobra pelo nome ("X está parada há N dias. Ainda
precisa fazer isso?"), diferente do aviso genérico `tarefas_atrasadas` (que só soma quantas
estão atrasadas). Dispara **uma vez só** por tarefa (`db.ja_notificado_alguma_vez()`, que
ignora a data - ao contrário de `ja_notificou_hoje`) - nunca vira cobrança repetida todo dia
enquanto a tarefa continuar parada.

**2. Puxar padrão (não só total da semana).** `notificacoes.gasto_dia_semana_atipico()`
compara o gasto de hoje com a média do **mesmo dia da semana** nas últimas 4 ocorrências -
pega um dia fora do padrão mesmo quando a semana inteira ainda está dentro da média (o que
`gasto_semana_elevado` sozinho não enxerga).

**3. Decidir dentro de limites (auto-categorização do extrato).** `gastos.sugerir_categoria()`
decide a categoria de uma transação bancária importada (OFX ou Pluggy) sozinho, comparando a
descrição com o histórico de gastos que você já categorizou manualmente - só decide quando
pelo menos 2 gastos passados concordam com folga (≥60% dos votos); em caso de dúvida real,
deixa sem categoria em vez de arriscar. Nova coluna `bank_transactions.categoria`, aplicada em
`importar_extrato()` e `bancos_conectar_finalizar()`.

**4. Timing que respeita você (modo silencioso).** Janela de horário configurável (padrão
22:00-07:00, `GET`/`POST /api/configuracoes/silencio`) em que avisos "soft" (gasto, meta,
lembrete, tarefa parada) ficam represados em vez de tocar o celular - sem marcar como
notificado, então o aviso só atrasa até o silêncio acabar, nunca se perde. Avisos presos a um
instante específico (`tarefa_horario`, `voo_sair`, `hora_de_dormir`) sempre furam o silêncio,
porque adiar a informação a esvazia. Botão novo no cabeçalho (ícone de lua) abre o painel de
configuração.

469 → 505 testes (36 novos), todos passando.

## 2026-09-21 (3) - Nova identidade: fonte Sora + esmeralda/ametista

Depois do polimento visual da rodada anterior, o Alex comparou fonte e cor ao vivo num
artefato-replica (comparador com presets, sem mexer no codigo real) e decidiu a combinacao
final:

- **Tipografia:** as tres familias do round 3 (Libre Bodoni/Jost/Bricolage Grotesque) deram
  lugar a uma unica familia - **Sora** - em `--font-display`/`--font-body`/`--font-numeros`.
  `--font-tech` continua IBM Plex Mono. Aplicado em `style.css`, `login.css` e nos tres
  `<link>` de Google Fonts (`index.html`, `login.html`, `configurar_pin.html`).
- **Cor de destaque:** `--accent` trocou de ametista (`#b85ec9`) pro esmeralda puro
  (`#41aa75`, o mesmo tom ja usado em `--cor-painel` - marca global e aba Painel agora
  compartilham identidade de proposito). `--accent-2` trocou de azul profundo (`#24467d`)
  pro roxo profundo (`#6d3fd1`, o mesmo tom que ja aparecia no gradiente do `.aurora`).
  Os seis `--cor-X` de cada secao (tarefas, financeiro, bancos, construtora, aviacao) nao
  mudaram.
- Mesma cor/fonte tambem atualizada no widget do Scriptable (`scriptable/widget_painel.js`).
- 469 testes passando, artefato-replica regenerado a partir dos arquivos-fonte (mesmo
  processo mecanico de sempre, nunca diverge do codigo real).

## 2026-09-21 (2) - Polimento visual a partir do feedback do Alex

Ajustes de design pedidos direto pelo Alex depois de revisar o artefato-réplica do app:

- **Dicas colapsáveis:** os ~6 parágrafos explicativos mais longos (Fechamento de hoje,
  Datas importantes, O que eu lembro sobre você, Cotações, Registrar voo, METAR/TAF) agora
  começam escondidos atrás de um ícone "!" clicável (`.dica-colapsavel`/`.dica-toggle` em
  `style.css`, `initDicas()` em `app.js`). Na primeira abertura o texto "digita"
  progressivamente (respeitando `prefers-reduced-motion`) em vez de aparecer tudo de uma vez.
- **Tipografia:** `-webkit-font-smoothing`/`text-rendering: optimizeLegibility` no `body`
  (fonte "esgarçada" em telas de alta densidade), `::placeholder` com peso e cor explícitos,
  `font-weight: 600` nos `<select>` de banco/tipo.
- **Input de arquivo customizado:** `#ofx-input` nativo virou visually-hidden e ganhou uma
  `<label>` estilizada (`.ofx-input-label`) que mostra o nome do arquivo escolhido - o texto
  "nenhum arquivo selecionado" do navegador não é estilizável via CSS.
- **Brilho "LED" em repouso:** badges (`.item-badge-proximo`, `.badge-sucesso`,
  `.badge-planejado`), botões primários (`#lembrete-btn`, `#voo-btn`, `#metar-btn`,
  `#importar-btn`, `.item-acoes button.primario`, `.meta-guardar button`) e
  `.stat-tile-valor` agora têm um `box-shadow`/`text-shadow` de brilho mesmo fora do
  `:hover` - antes só acendiam ao passar o mouse.
- **Sombra com mais profundidade:** `--shadow-card`/`--shadow-card-hover` reforçadas de 3
  pra 4 camadas (realce interno + contato colado + duas quedas em raios diferentes) pra
  parecer sombra de verdade em vez do "achatado" que o Alex descreveu como "cara de feito
  por IA". `.tab-btn.active` ganhou uma segunda camada de glow ambiente + `drop-shadow` no
  ícone.
- Artefato-réplica no claude.ai regenerado a partir dos arquivos-fonte atualizados (mesmo
  script de montagem mecânica de sempre - nunca diverge do código real).

## 2026-09-21 - Contas a pagar da construtora, auditoria noturna de qualidade

**Integração com a construtora:** consome o novo `GET /api/contas_a_vencer` do painel da
construtora (`financeiro-construtora` v3.99.16) - aba Construtora mostra a lista de contas
a vencer/vencidas, e o scheduler avisa por push quando uma conta vence hoje, já venceu, ou
vence nos próximos 3 dias (dedup por dia, sem repetir aviso). Entra como contexto no resumo
do dia e no chat.

**Assistente mais esperto (turno anterior do mesmo dia):** sugere o dia menos corrido da
semana pra tarefas sem data fixa, sugere horário livre no dia, calcula custo de combustível
de viagem com distância real (Google Maps), sugere posto no meio do caminho pra abastecer.
Uber por voz com o risco de cobrança errada eliminado (fare travado + confirmação explícita
antes de qualquer corrida de verdade ser pedida - decisão do Alex: "tirar o risco", não
abandonar a feature). Currency de voo (avisa depois de 21 dias sem voar), lembrete de
desacelerar às 22h, rotação de 3 temas de estudo pra aviação, aviso proativo quando o tempo
fica bom pra uma tarefa marcada como dependente do clima. Cotação de fornecedores com leitura
automática de PDF (Claude lê o orçamento escaneado e extrai os itens). Atalhos do iPhone
(captura por voz, PDF direto pro Compartilhar) e widget de tela inicial via Scriptable.

**Auditoria noturna de qualidade (pedido do Alex: "20 ou mais coisas que vc consegue fazer
sem ficar me perguntando"):**
- Cache de 60s nas chamadas pra API da construtora (evita estourar o rate limit de 20 req/min
  de lá quando várias partes do painel pedem o mesmo dado em sequência rápida). Corrigido de
  quebra: a rota `/api/construtora/resumo` tinha uma chamada direta que não passava pelo cache.
- `/healthz` pra monitoramento externo, sem autenticação, sem tocar no banco.
- Índices no SQLite nas colunas mais filtradas/ordenadas (`tasks.completed_at`/`due_date`,
  `expenses.created_at`/`tipo`, `subtasks.task_id`, etc.) - idempotente, sem mudar nenhum
  resultado de query, só a velocidade conforme o histórico cresce.
- Corrigido N+1 real em `GET /api/tasks` (1 query de subtarefas por tarefa em vez de uma
  query só pra todas).
- Export de gastos em CSV e backup/export do banco (cópia consistente via API de backup do
  sqlite3, não uma cópia de arquivo crua) - botões no cabeçalho/aba Gastos.
- Acessibilidade: cabeçalho expansível de cada cotação ganhou `role="button"` +
  `aria-expanded` (era uma `<div>` focável sem semântica de estado pra leitor de tela).
- Dias restantes (além de meses) nas metas financeiras, com aviso de atraso quando o prazo já
  passou e a meta não foi batida.
- Auditorias sem achado (documentadas, não geraram mudança): formatação de moeda/data em
  `app.js` já usa `fmtMoeda`/`fmtDataBr` em todo lugar, sem inconsistência.

## 2026-09-20 - Gráficos técnicos e paleta final

Gráficos redesenhados com a skill de dataviz interna (mais "técnico", menos genérico) e
paleta validada. Troca completa de fontes (Libre Bodoni/Jost/IBM Plex Mono), fundo escurecido
70%, fonte separada pra valores em destaque (Bricolage Grotesque). Menos mistura de cor
(referência: trabalho do Pierre) e textos mais diretos/com personalidade, menos genéricos.

## 2026-09-19 - Deploy real, login, gráficos, identidade visual

Deploy pra VPS com HTTPS (necessário pro push funcionar no iPhone de verdade). Login por PIN
de 6 dígitos imposto pelo servidor. Tarefa/lembrete com horário viram compromisso de agenda e
push de verdade, com deep link pra já abrir o Uber. Gráficos de gasto diário, evolução de
meta e horas de voo. Várias passadas de identidade visual (paleta joia mais escura, tipografia
premium, saudação pessoal, som/vibração em momentos-chave). Horário no voo, separação de
gasto real x planejado.

## 2026-09-18 - Chat vira o centro do app, integrações externas

Chat com tool-use vira a tela principal (antes era só captura por texto). Notificações
proativas, memória durável entre conversas, datas importantes pra vida toda (licença de
piloto, seguro etc). Integração com Open Finance via Pluggy, com Saúde do iPhone via Atalhos,
com agenda do iCloud, e primeira ligação com o resumo financeiro da construtora no contexto
do chat. Aba Aviação: horas voadas, voos agendados, previsão do tempo e decodificação de
METAR/TAF (com leitura em voz alta). Comando de voz no chat via Web Speech API do navegador.
Notificação push funcionando de ponta a ponta.

## 2026-09-17 - Estrutura inicial (v1)

Primeira versão: captura rápida de tarefas/gastos/metas por texto livre (Claude classifica),
rastreio de custo de IA por chamada, pergunta de esclarecimento quando o texto é ambíguo,
testes automatizados com mock das chamadas ao Claude, base pra integração bancária via OFX.
