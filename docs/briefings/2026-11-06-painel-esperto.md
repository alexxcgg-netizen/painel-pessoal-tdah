# Leva 06/11 (3) - painel mais esperto: viagem, combustível, GPS, onde estou e aba Tarefas

Pedido do Alex (06/11), antes de gerar o `.ipa`: "quero algo mais, espero mais, realmente um assistente".
- Gostou muito do card de rota com chuva no caminho (date de sábado, 100% de chuva na rota) -> ir mais fundo.
- Viagem de carro ("daqui pra Curitiba"): trânsito, chuva e coisas do tipo no trajeto.
- Pouco combustível: onde parar. Viagem longa (ex. Mato Grosso, ~1000 km): onde parar pra abastecer, postos
  bons e abertos no horário que ele vai passar, pela autonomia do carro dele (Volvo XC40 T5 Twin Engine
  R-Design 2020, híbrido plug-in).
- "Saber onde eu fui ou estou indo, ver no Maps, se conectar."
- Aba Tarefas "muito simples, com cara de IA": tocar na tarefa e apagar, trazer a de amanhã pra hoje.
- Depois: "vai fundo, também vê se dá pra melhorar ainda mais o GPS".

Respostas dele (perguntas antes da leva):
- tanque: **registro de abastecimento** (ele fala "enchi o tanque" / foto da nota; o painel conta os km e
  aprende o consumo real);
- paradas em viagem longa: **só pra abastecer**;
- onde estou: **adivinhar pra onde vou + diário do dia + viagem acompanhada**, e "ser muito mais esperto,
  melhorar mais ainda o planejamento";
- Tarefas: **tocar e agir + régua do dia + visual novo sem cara de IA** (deslizar já existe).

Fluxo: protótipo no artefato (dados inventados) -> veredito dele -> app -> um `.ipa` só no fim, junto com a
leva do ao vivo de tarefa (`2026-11-06-ao-vivo-tarefa.md`).

## O que já existe (mapa do código, 06/11)
- Card `rota` (`cards.card_rota`, `cards-tipos.js` `tempoRota`/`mapaRota`): ferramenta `estimar_trajeto`,
  `maps_client.trajeto` (até 8 pontos, uma chamada por trecho com lentidão), `clima_rota.tempo_na_rota`
  (Open-Meteo grátis, ponto a cada 20 km, máx 12, na hora que ele passa; rota >= 25 km, até 16 dias).
- Trechos lentos/parados no caminho (`trechos_lentos`, `nomear_lentidao`), cota contada em `uso_maps`.
- `carro.py` (Atalho "partida no carro"), `posto_no_meio_do_caminho` (ponto do meio em linha reta, 1 posto).
- `viagem.custo_combustivel`; nada guardado de carro (consumo/tanque) nem abastecimento.
- `visitas` (iPhone, 30 dias), `onde_estou.lugares_com_coordenada` (apelidos + casa + paradas do dia, raio 150 m),
  `checar_atraso`. Sem "pra onde vou" e sem diário de lugares (`diario.py` não usa visitas).
- Tarefas: `tarefas.js` + `linha-do-tempo-tarefas.js` + `arrastar-excluir.js` (deslizar = apagar com desfazer);
  ações "pra amanhã"/"pra hoje" (só atrasadas). Sem rota pra mudar data/título livre na aba.

## Frentes

### 1. Carro e combustível
- Tabela `veiculo` (um carro: nome, tanque_l, consumo_km_l estrada/cidade padrão, reserva_km) e
  `abastecimentos` (data, km do hodômetro se ele disser, litros, valor, cheio sim/não, lugar).
- Chat: "enchi o tanque", "abasteci 30 L por 180", foto da nota (o leitor de nota fiscal já existe) ->
  `registrar_abastecimento`. O consumo real sai de tanque cheio a tanque cheio.
- Quanto sobra no tanque = último tanque cheio - km rodados desde então (rotas planejadas/feitas pelo painel +
  hodômetro quando ele falar) / consumo. Sempre mostrado como **estimativa**, com a margem.
- Dados de fábrica do XC40 só com fonte conferida (pesquisa em andamento; o que não for confirmado fica como
  "a confirmar" e o consumo real dele substitui).

### 2. Viagem planejada (curta e longa)
- Ferramenta nova `planejar_viagem` (base: `exec_estimar_trajeto`): origem/destino, saída (agora ou data/hora).
  - rota com trânsito e trechos lentos; chuva/neblina/rajada na hora que ele passa (já existe);
  - **paradas pra abastecer** pela autonomia: onde o tanque chega na reserva, procura posto **ao longo da rota**
    (Places "search along route") aberto na hora que ele passa, prefere posto grande de rodovia;
  - hora de chegada com as paradas; custo estimado de combustível;
  - **melhor horário pra sair** (compara 2-3 saídas: menos chuva/trânsito);
  - noite/serra/neblina no caminho viram aviso;
  - card novo `viagem` (linha do trajeto com km, chuva e paradas), botão abrir no Maps/Waze com as paradas.
- Respeita a regra "tem que ser grátis": cota por SKU contada em `uso_maps` (e passar a contar também as buscas
  de lugar que hoje escapam).

### 3. GPS mais esperto (iPhone)
- **Cerca nos lugares** (`CLCircularRegion`, até 20): casa, apelidos salvos, destino/parada das tarefas do dia.
  Entrou/saiu na hora (mais rápido que a visita). O painel manda a lista (`GET /api/localizacao/cercas`).
- **Detectar que está dirigindo** (`CMMotionActivityManager`, permissão "Movimento"): de carro liga o GPS
  sozinho (precisão de rodovia, `activityType = .automotiveNavigation`), parado desliga. Substitui o botão manual.
- **Viagem acompanhada**: só durante viagem planejada ou dirigindo pra um compromisso, a posição vai pro painel a
  cada ~5 min/~10 km (`POST /api/localizacao/posicao`), guardada só durante a viagem e apagada no fim.
- **Ao vivo da viagem** (mesma família da tarefa ao vivo): chegada, próximo posto, chuva à frente.

### 4. Onde estou e pra onde vou
- **Adivinhar pra onde vai**: saiu de um lugar (cerca/visita) perto da hora de uma tarefa com lugar -> assume o
  destino, calcula trânsito e chuva, liga o ao vivo, avisa se vai atrasar (já existe `checar_atraso`).
- **Diário do dia**: lugares e quanto tempo ficou (só o lugar, nunca o caminho), no fechamento do dia e na
  ferramenta `consultar_diario`.

### 5. Planejamento mais esperto
- A IA olha a semana: chuva/trânsito no horário de cada saída, sugere mudar a hora de sair quando melhora muito,
  junta saídas no mesmo caminho, lembra de abastecer antes de viagem marcada se a estimativa do tanque não chega.

### 6. Aba Tarefas nova
- Visual sem cara de IA (régua dos cards: nativo, sem brilho/neon/emoji/maiúsculas espaçadas).
- **Tocar e agir**: folha de ações (apagar, hoje, amanhã, escolher dia, mudar hora, editar título), com desfazer.
  Rota nova `POST /api/tasks/<id>/mover` (data e/ou hora) e `POST /api/tasks/<id>/titulo`.
- **Régua do dia**: as tarefas com hora numa linha do tempo, chuva e trânsito em cima das saídas; arrastar pra
  outro horário (com desfazer).

### 7. Mais esperto (escolhidas por ele, 06/11, das 8 propostas)
- **Aprende teus tempos reais**: hora do aviso de sair x hora que saiu de casa (cerca/visita) e duração real de
  cada trajeto por faixa de horário; depois de 3+ amostras, o "sai às X" usa a média dele (mostra de onde veio:
  "tu costuma sair 10 min depois do aviso"). Sem amostra suficiente, segue o padrão de hoje.
- **Atrasado? Recado pronto**: GPS + trânsito dizem que vai chegar depois da hora -> aviso cedo com a mensagem
  pronta ("chego uns 10 min atrasado") e botão que abre o WhatsApp com o texto. Nunca manda sozinho.
- **Voo decidido na véspera**: 24 h antes cruza TAF do aeródromo, sono e o que tem na noite anterior -> "amanhã voa"
  / "amanhã não dá" com o porquê (teto, vento, visibilidade); balada na véspera vira aviso. TAF que não cobre a hora:
  diz que ainda não dá pra saber (nunca inventa).
- **Descobre tuas rotinas**: padrão de 3 semanas (lugar+dia+hora ou tarefa repetida) -> propõe virar rotina com 1
  toque; tarefa adiada 3 vezes -> pergunta: quebrar em passos, mudar o dia ou apagar.
- **Pergunta na hora certa**: além dos avisos de hora fixa (que continuam todos, ver memória "avisos: não reduzir"),
  lembra pelo contexto: chegou em casa de noite com tarefa aberta; saiu da academia -> como foi o treino.
- Recusadas: lembrete pelo lugar, gasto pelo lugar, quieto enquanto dirige.

## Protótipo
https://claude.ai/artifact/WXSEtwp14Y1UwGEc86TYTX (dados inventados; cenas Tarefas, Viagem longa, Viagem curta,
Onde estou, No carro).

Aprovado por ele antes do protótipo (06/11, "já gostei dessas 4 coisas"): as 4 do GPS - cerca nos lugares,
detectar que está dirigindo, viagem acompanhada, ao vivo da viagem.

## Decisões (pra ele vetar)
- Tarefas: tocar abre uma folha de baixo (dia em chips, hora em chips, nome editável, Feito, Apagar); tudo com
  Desfazer no toast de 5 s. A caixinha da esquerda marca feito sem abrir a folha. Deslizar pra apagar continua.
- Régua do dia: 7h às 23h, bolinha por tarefa com hora (coral; saída em rosa), faixa listrada azul onde chove,
  linha vermelha do agora; arrastar muda a hora de 15 em 15 min, com Desfazer. Grupos Atrasadas / Tarde / Noite /
  Sem hora / Amanhã, lista estilo Ajustes do iPhone (sem brilho, sem emoji, sem maiúsculas espaçadas).
- Viagem: **mesmo card de rota de hoje, com o mapa** (pedido dele no veredito v1: "gosto mais do nosso app que
  mostra um mapa com a rota"). Por cima do caminho: chuva, lento e o pino verde do posto; a barra "Tempo no
  caminho" ganha o posto e o trecho de noite. Embaixo: 3 horários de saída com a frase de qual é melhor, linha do
  tempo com hora de cada coisa (escurecer em vermelho), tanque, gasolina/custo/chegada.
- Rota comum (date, compromisso) **não muda** e **nunca ganha posto** (ele vetou a exceção do tanque, 06/11). Só a
  viagem pedida ("vou pra X", "viagem pra Y") ganha as partes novas. No card do compromisso o que pode melhorar é
  só o **trânsito, e tem que ser muito bom e preciso** (pedido dele): tempo com trânsito do Google na hora real de
  sair (não a média), trecho lento/parado com nome da rua/rodovia e quanto atrasa, e reconferir perto da saída
  (o ao vivo já refaz). Nada de trânsito inventado ou "estimado" sem dado: sem dado, não mostra.
- Combustível: tanque 48 L (a confirmar) e consumo começa em 13 km/l estrada / 10 cidade até ter 2 tanques cheios
  registrados; sempre escrito como estimativa. Reserva = 60 km de folga.
- Posto: só aberto na hora que passa, no máximo ~2 min fora da rota, prefere posto de rodovia 24 h. Uma busca de
  posto por parada (cota Enterprise, 1.000/mês).
- Viagem curta: se o tanque estimado não dá ida e volta com folga, entra a parada no posto já na rota.
- Onde estou: ao sair de um lugar perto da saída de uma tarefa com lugar, pergunta "Indo pro X?" com o trajeto
  (É isso / Vou pra outro lugar); diário do dia só com lugar e tempo, some em 30 dias.
- Posição da viagem acompanhada apagada quando a viagem acaba.
