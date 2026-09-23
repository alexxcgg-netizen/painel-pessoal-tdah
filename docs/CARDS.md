# Contrato de cards (Fase 6 - "Padrão Nectar")

Fonte única do formato de resposta da aba Hoje. Toda ação ou consulta feita
pelo chat (`POST /api/chat`) ou pela captura (`POST /api/capture` e
`POST /api/atalho/capturar`) devolve **dado estruturado renderizado como card**
em vez de só prosa. Este documento é complementar ao contrato do classificador
de intent (`docs/INTENT.md`): o intent decide **o que fazer**; o contrato de
cards descreve **como o resultado volta pra tela**.

Regra de evolução (mesma do `INTENT.md`): **só aditivo**. Um `type` novo, um
campo novo em `data` ou um `tipo` novo de action podem ser *adicionados*;
nome/tipo de campo já publicado nunca muda. O frontend trata qualquer `type`
que não conhece com o card fallback (ver abaixo), então um backend mais novo
nunca quebra um frontend mais velho (PWA com cache antigo).

Código de referência:

| Parte | Onde |
| :--- | :--- |
| Montagem dos cards no servidor (builders, mapeamento tool -> card, modo visitante) | `cards.py` |
| Rota de chat / captura (envelope do contrato) | `app.py` (`chat()`, `_executar_captura`) |
| Desfazer por token | `app.py` (`POST /api/desfazer/<token>`), tabela `acoes_desfazer` (`db.py`) |
| Registro `type -> renderizador` + fallback no front | `static/js/cards.js` (`Cards.registrar`); renderizadores em `static/js/cards-tipos.js` |
| Estilo dos cards | `static/css/style.css` (bloco "Cards do contrato") |
| Testes | `tests/test_cards.py`, `tests/js/cards.test.js` |

## Envelope da resposta

```json
{
  "cards": [
    { "type": "transacao", "id": "c1", "data": { }, "actions": [ ] }
  ],
  "resumo_texto": "Registrei o gasto no mercado.",
  "passos": [
    { "modulo": "Finanças", "descricao": "Registrou o gasto \"mercado\"", "ms": 14 }
  ]
}
```

- `cards`: lista (pode ser vazia). Ordem = ordem em que devem aparecer.
  - `type` (string, obrigatório): um dos tipos da tabela abaixo.
  - `id` (string, obrigatório): único **dentro da resposta** (`c1`, `c2`...) -
    serve só de chave de DOM, não é id de banco.
  - `data` (objeto, obrigatório): formato específico do `type`.
  - `actions` (lista, obrigatório, pode ser vazia): botões/links do card.
  - `desfeito` (bool, opcional, **aditivo** - só no `GET /api/chat/historico`):
    `true` quando o Desfazer daquele card já foi usado; o front mostra o card
    apagado com "Desfeito".
- `resumo_texto` (string): a frase curta que acompanha os cards (no chat, a
  resposta da IA; na captura, uma frase gerada no servidor). Aparece como
  bolha de texto acima dos cards.
- `passos` (lista): o que o servidor fez pra chegar na resposta, na ordem.
  Cada passo: `{ "modulo": str, "descricao": str, "ms": int }` e, opcional,
  `"erro": true` quando aquela etapa falhou. `modulo` é um rótulo humano
  (`Tarefas`, `Finanças`, `Metas`, `Lembretes`, `Saúde`, `Agenda`, `Hábitos`,
  `Projetos`, `Viagens`, `Captura`, `Assistente`...). É daqui que sai a linha
  "13 passos · 31 s · Tarefas, Finanças" do `resumo_final`.

### Compatibilidade com clientes antigos (campos legados)

Os campos antigos **continuam presentes** enquanto existir frontend/cliente
que dependa deles (PWA com `app.js` antigo em cache do service worker,
Telegram, Atalhos do iPhone):

| Rota | Campos legados mantidos | Campos novos (aditivos) |
| :--- | :--- | :--- |
| `POST /api/chat` | `resposta` (== `resumo_texto`), `acoes` (nomes das tools) | `cards`, `resumo_texto`, `passos` |
| `POST /api/capture` e `/api/atalho/capturar` | `tipo`, `titulo`, `valor`, `categoria`, `quando`, `hora`, `prazo`... (o JSON da classificação, como antes) e `duvida`/`texto_original` no caso de dúvida | `cards`, `resumo_texto`, `passos` |
| `GET /api/chat/historico` | `papel`, `texto`, `criado_em`... | `cards` (lista; vazia em mensagens antigas) |

- O Telegram usa `app._processar_mensagem_chat` e continua recebendo só o
  texto (`resposta`) - cards não fazem sentido lá.
- Os Atalhos leem os campos que já liam; os novos são ignorados.
- Quando o frontend antigo não existir mais em nenhum cache, `resposta` pode
  ser marcada como obsoleta aqui (nunca removida sem essa anotação antes).

### Modo visitante (Fase 5, US-C19/C20)

Com `_modo_visitante_ativo()`, a proteção é **no servidor** (o valor não sai
na resposta): `cards.mascarar_visitante` remove os campos de valor dos cards
e marca `data.oculto = true`; `resumo_texto`/`resposta` passam por
`cards.ocultar_valores_texto` (troca `R$ 1.234,56` por `R$ •••`); o legado
`valor` da captura é removido. Campos removidos por tipo:

| type | removidos em modo visitante |
| :--- | :--- |
| `transacao` | `valor`, `saldo` |
| `meta` | `valor_guardado`, `valor_alvo`, `falta` (o `percentual` fica) |

O front mostra `R$ •••` quando `data.oculto` é `true`.

## Actions

Lista de objetos com `tipo` + `rotulo` (texto do botão/link). Tipos:

| tipo | campos | o que o front faz |
| :--- | :--- | :--- |
| `abrir_aba` | `aba` (id da aba: `hoje`, `painel`, `vida`, `tarefas`, `gastos`, `bancos`, `construtora`, `aviacao`), `destaque` opcional `{ "entidade": str, "id": int }` | `showTab(aba)`, espera a lista carregar, rola até `[data-entidade][data-id]` e destaca |
| `desfazer` | `token` (str), `alvo` (lista de `{ "entidade", "id" }` ou `{ "entidade": "evento", "uid" }` - **só informativo**) | `POST /api/desfazer/<token>`; o card vira "Desfeito" |
| `despertar` | `lembrete_id` (int), `ativo` (bool) | `POST /api/lembretes/<id>/despertar` `{ "ativo": bool }` - push no horário (PWA não toca alarme) |

### Desfazer

- O `token` é gerado no servidor no momento em que a ação é executada e
  gravado em `acoes_desfazer` junto com **os ids exatos** do que foi criado
  (nunca "o último"). O servidor confia só no que gravou, nunca no `alvo`
  que o cliente mandaria.
- Um card = um token. Um card com várias entidades (ex: `tarefas_criadas`
  com 3 tarefas) desfaz as 3 juntas; cards diferentes da mesma resposta
  (brain dump) têm tokens independentes.
- Respostas: `200 {"ok": true, "desfeitos": n}`; `404` token desconhecido;
  `409` já desfeito.
- Entidades suportadas: `tarefa` (apaga a tarefa + subtarefas; se for rotina
  recorrente, apaga o modelo e as instâncias), `gasto` e `renda` (apaga e
  reverte o ajuste otimista de saldo, se houve), `lembrete`, `meta` (apaga a
  meta e os depósitos).
- **Aditivo (US-E7, módulos da Fase 6):** `habito` (apaga o hábito criado e
  as marcações), `habito_marcacao` (o token guarda `data` + `feito` - volta
  aquele dia exato pro estado anterior: desmarca o que foi marcado, remarca o
  que foi desmarcado), `projeto` (apaga projeto + etapas), `projeto_etapa`
  (apaga a etapa adicionada), `etapa_concluida` (reabre a etapa), `viagem`
  (apaga viagem + checklist de mala), `hidratacao` (apaga aquele copo),
  `treino` (apaga aquele treino).
- `evento` (agenda, US-E14): o registro guarda `{ "entidade": "evento",
  "uid": "..." }`. Só pode ser desfeito se o `uid` estiver na tabela local
  de eventos criados pelo painel (`eventos_criados`, US-E14) - evento que o
  painel não criou **nunca** é apagado (`403`, e nada do token é desfeito:
  tudo ou nada). Ponto de ligação da US-E14: `caldav_client.apagar_evento_painel(uid)`
  (levanta exceção se falhar); enquanto essa função não existir, o desfazer
  de evento registrado devolve `501` sem apagar nada. Quem cria o evento
  chama `db.criar_acao_desfazer(conn, [{"entidade": "evento", "uid": uid}])`
  (ou devolve `"_efeito": {"entidade": "evento", "uid": ...}` no executor e
  registra o builder do card `agenda` em `cards.cards_dos_efeitos`).
- Ajuste otimista de saldo (gasto/renda com banco citado) é revertido junto
  (`conta_id` + `delta` gravados no token, nunca vindos do cliente).
- O link `abrir_aba` rola e destaca `[data-entidade][data-id]` na aba de
  destino - hoje existe em tarefas (`tarefa`), gastos (`gasto`, `meta`) e
  painel (`lembrete`). Lista nova que quiser ser destino: pôr os dois
  atributos no `<li>`.

## Tipos de card

Datas sempre ISO: dia `AAAA-MM-DD`, data-hora local `AAAA-MM-DDTHH:MM`, hora
`HH:MM`. Valor sempre número (reais), nunca string formatada - quem formata é
o front (`fmtMoeda`).

### `tarefas_criadas`

```json
{
  "tarefas": [
    { "id": 12, "titulo": "Levar o carro na oficina", "data": "2026-09-23",
      "hora": "14:00", "quando": "hoje", "recorrencia": null, "concluida": false }
  ]
}
```

- `data`/`hora`/`quando`/`recorrencia` podem ser `null`. `quando` é o texto
  livre original ("essa semana") quando não há `data`.
- Front: lista com checkbox funcional (`POST /api/tasks/<id>/complete`),
  título, data curta ("quarta 23") e link "Abrir Tarefas".
- Actions típicas: `abrir_aba` (tarefas), `desfazer`.

### `transacao`

```json
{
  "id": 5, "entidade": "gasto", "sentido": "saida", "titulo": "Mercado",
  "valor": 45.9, "categoria": "mercado", "data": "2026-09-23",
  "meio": "Nubank", "status": "real",
  "saldo": { "conta": "nubank", "antes": 1000.0, "depois": 954.1 },
  "oculto": false
}
```

- `entidade`: `gasto` | `renda`. `sentido`: `saida` | `entrada` (valor sempre
  positivo; o sinal é do `sentido`).
- `status`: `real` | `planejado`. `meio` e `saldo` podem ser `null` (saldo só
  quando a conta citada tem saldo sincronizado).
- Front: bolinha da categoria, valor grande (`-R$` neutro, `+R$` verde), linha
  "data · meio · categoria", saldo antes -> depois, link "Abrir no extrato".
- Actions típicas: `abrir_aba` (gastos), `desfazer`.

### `lembrete`

```json
{ "id": 3, "titulo": "Renovar CMA", "data": "2026-09-24", "hora": "08:00",
  "recorrente": false, "despertar": false }
```

- `hora` pode ser `null` (os lembretes de hoje são por dia). Sem hora, a
  contagem regressiva conta até `09:00` do dia (mesmo horário do push de
  "Desperta você").
- Front: horário grande em fonte mono, "amanhã · faltam 23h 6min" (contagem
  viva), botões "Desfazer" e "Desperta você", link "Abrir em Lembretes".
- Actions típicas: `desfazer`, `despertar`, `abrir_aba` (painel).

### `meta`

```json
{ "id": 2, "titulo": "Reserva de emergência", "valor_guardado": 9000.0,
  "valor_alvo": 15000.0, "percentual": 60.0, "falta": 6000.0,
  "prazo": "2026-12-22", "oculto": false }
```

- Front: "R$ 9.000,00 de R$ 15.000,00", barra, "60% da meta · faltam
  R$ 6.000,00", data planejada.
- Actions típicas: `abrir_aba` (gastos), `desfazer`.

### `resumo_final`

```json
{
  "linhas": [ { "modulo": "Finanças", "texto": "1 gasto registrado" },
              { "modulo": "Tarefas", "texto": "2 tarefas criadas" } ],
  "passos_total": 13, "duracao_ms": 31000,
  "modulos": ["Tarefas", "Finanças", "Hábitos"]
}
```

- Gerado pelo servidor no fim de uma resposta que tocou **2 ou mais cards**
  (brain dump). `texto` nunca tem valor em dinheiro.
- Front: linhas em seta ("→ Finanças: 1 gasto registrado") + linha
  recolhível "13 passos · 31 s · Tarefas, Finanças, Hábitos" que abre a
  lista de `passos` do envelope.

### `agenda` (renderizador pronto; dado real ligado pela US-E14/E7b)

```json
{
  "titulo": "Reunião com o contador",
  "inicio": "2026-09-29T14:00", "fim": "2026-09-29T15:00",
  "lembrar_min_antes": 30, "uid": "abc123@painel", "calendario": "Painel",
  "confirmado": true
}
```

- `fim` pode ser `null` (vira 1h). `lembrar_min_antes` e `uid` podem ser
  `null`. `confirmado`: o evento já está gravado na agenda.
- Front: título, "terça, 29 de setembro, das 14:00 às 15:00", barra do dia
  06h-22h com o bloco marcado, "1h reservada(s)", chip "Lembrar 30 min
  antes", "✓ Está na sua agenda · Desfazer".
- Desfazer: action `desfazer` cujo `alvo` é `[{ "entidade": "evento", "uid" }]`.

### `projeto_viagem` (renderizador pronto; dado real ligado pela US-E13/E7b)

```json
{
  "id": 4, "origem": "viagem", "titulo": "Viagem pra Gramado",
  "inicio": "2026-09-01", "prazo": "2026-12-22",
  "etapas": [ { "titulo": "Comprar passagem", "feito": true, "data": "2026-09-10" },
              { "titulo": "Reservar hotel", "feito": false, "data": "2026-10-15" } ],
  "proximo_marco": { "titulo": "Reservar hotel", "data": "2026-10-15" },
  "status": "no_rumo"
}
```

- `origem`: `projeto` | `viagem`. `status`: `no_rumo` | `atrasado` | `pausado`.
- `data` de cada etapa, `inicio`, `prazo` e `proximo_marco` podem ser `null`.
- Opcionais calculados pelo backend (US-E13, se vierem, o front usa em vez de
  calcular): `percentual`, `feitas`, `total`, `hoje_fracao` (0..1, posição de
  hoje entre `inicio` e `prazo`).
- Front: título, checklist, barra de progresso com marcador HOJE,
  "25% · 2/8 tarefas · 22 dez", próximo marco com bandeira, chip de status
  ("No rumo"), link "Abrir Projetos".

### `saude_treino` (renderizador pronto)

```json
{
  "periodo": "últimos 7 dias",
  "sessoes": [ { "atividade": "Corrida", "fonte": "Apple Saúde", "minutos": 40,
                 "data": "2026-09-22" } ],
  "registrado": true
}
```

- Front: "Sessões registradas: 3 · Tempo de atividade: 1h50", lista (fonte +
  duração), gráfico de barras por atividade (SVG inline), chip "Registrado"
  quando `registrado`.

### `sugestao` (renderizador pronto; "porquê" real ligado pela US-E10/E7b)

```json
{
  "titulo": "Estudar meteorologia", "inicio": "2026-09-24T19:00",
  "duracao_min": 45, "porque": "Você costuma render melhor à noite e amanhã está livre depois das 18h."
}
```

- `porque` pode ser `null` (a caixa some).
- Front: horário sugerido (grande, mono), duração, caixa "Com a sua rotina em
  mente" com o porquê.

### `saude_dia` (aditivo, US-E7)

```json
{ "data": "2026-09-23", "agua_copos": 3, "passos": 8240, "sono_horas": 7.5,
  "treino_min": 45, "registrado": "agua" }
```

- A saúde do dia num olhar. `agua_copos` = contador do painel
  (`hidratacao_registros`); `passos`/`sono_horas` = Apple Saúde via Atalho
  (`saude_dados`, `null` quando não chegou); `treino_min` = soma dos treinos
  de hoje (`null` sem treino). `registrado`: `"agua"` quando o card nasceu
  de um copo registrado agora (chip "Registrado" + Desfazer daquele copo),
  `null` numa consulta.
- Front: número de copos grande em fonte mono, fileira de 8 gotas (acesas
  até `agua_copos`, "+N" além disso), chips neutros de passos/sono/treino.
- Actions típicas: `desfazer` (quando `registrado`).

### `habito` (renderizador pronto; dado real ligado pela US-E12/E7b)

```json
{
  "id": 7, "nome": "Meditar", "meta": "15 min", "frequencia": "qualquer dia conta",
  "horario": "08:00", "hoje": "2026-09-23",
  "semana": [ { "data": "2026-09-21", "feito": true }, { "data": "2026-09-22", "feito": false },
              { "data": "2026-09-23", "feito": false }, { "data": "2026-09-24", "feito": false },
              { "data": "2026-09-25", "feito": false }, { "data": "2026-09-26", "feito": false },
              { "data": "2026-09-27", "feito": false } ],
  "ativos_antes": 4, "ativos_depois": 5, "contexto": null
}
```

- `semana`: sempre 7 itens, **segunda a domingo** da semana de `hoje`
  (círculos S T Q Q S S D). `horario`, `ativos_antes`, `ativos_depois`,
  `contexto` podem ser `null`.
- Front: nome, meta ("15 min · qualquer dia conta · às 8h"), 7 círculos (hoje
  tracejado, dias feitos acesos), "Hábitos ativos: 4 → 5", caixa de contexto.

### Campo aditivo `consulta` (US-E7)

Qualquer card que veio de uma **consulta** (nada foi criado - "me mostra o
projeto e a meta") traz `data.consulta = true` e **não** tem action
`desfazer` (só o link da aba). O front usa isso pra não dizer "Meta criada"
num card de meta consultada. Card de consulta também não conta pro
`resumo_final` (ele só aparece quando a resposta **fez** 2+ coisas).

### Quem gera cada card dos módulos (US-E7 / US-E6)

Mapeamento único em `cards.cards_dos_efeitos` (`_card_de_efeito_modulo`);
o executor da tool só declara o `_efeito`. As consultas rodam nos MESMOS
executores tanto pela IA (tool-use) quanto pelo classificador local (sem API,
ver `docs/INTENT.md`).

| Origem (tool do chat / pergunta) | `_efeito` | Card | Desfazer |
| :--- | :--- | :--- | :--- |
| `registrar_habito` | `habito` (+ `ativos_antes`/`ativos_depois`) | `habito` ("Hábitos ativos: 4 → 5") | `habito` |
| `marcar_habito` | `habito_marcacao` (`data`, `feito`) | `habito` (contexto "Marcado como feito hoje.") | `habito_marcacao` |
| `criar_projeto` / `adicionar_etapa` / `concluir_etapa` | `projeto` / `projeto_etapa` / `etapa_concluida` (+ `projeto_id`) | `projeto_viagem` (origem `projeto`) | idem |
| `registrar_viagem` | `viagem` | `projeto_viagem` (origem `viagem`, título "Viagem pra X"; sem checklist o marco é a ida) | `viagem` |
| `agendar_evento` | `evento` (`uid`, `lembrar_min_antes`) | `agenda` (`confirmado: true`, calendário "Painel") | `evento` (só uid em `eventos_criados`) |
| `registrar_treino` | `treino` | `saude_treino` dos últimos 7 dias, `registrado: true` | `treino` |
| `registrar_hidratacao` / "tomei um copo de água" | `hidratacao` | `saude_dia` (`registrado: "agua"`) | `hidratacao` |
| `consultar_projeto` / "me mostra o projeto da viagem" | `projeto`/`viagem` + `consulta` | `projeto_viagem` | - |
| `consultar_meta` / "e a meta?" | `meta` + `consulta` | `meta` | - |
| `consultar_treinos` / "como foram meus treinos nos últimos 7 dias?" | `treinos` (`dias`) | `saude_treino` | - |
| `consultar_habitos` / "como estão meus hábitos?" | `habito` + `consulta` | `habito` | - |
| `consultar_saude_dia` / "quanta água eu tomei hoje?" | `saude_dia` | `saude_dia` | - |
| `sugerir_horario_livre` / "como encaixo meu treino hoje?" | `sugestao` (`titulo`, `inicio`, `duracao_min`, `porque`) | `sugestao` | - |

- **Adaptadores de formato** (puros, `cards.py`): `semana_seg_dom` (o
  `GET /api/habitos` expõe `ultimos_7`, janela móvel; o card quer a semana
  segunda->domingo), `habito_para_card`, `projeto_para_card` (o módulo
  expõe `posicao_hoje` em **0-100**; o card quer `hoje_fracao` em **0..1**;
  `texto`/`feita`/`data_prevista` viram `titulo`/`feito`/`data`).
- `sugestao.porque` = o fato da agenda de hoje ("maior espaço livre das X às
  Y") + a memória da categoria `sua_rotina` (US-E10, "O que eu lembro sobre
  você") que fala do mesmo assunto, quando existir - nunca inventado. O
  horário nunca é no passado (procura a partir de agora).

### Fallback (front)

Qualquer `type` que o registro não conhece, ou qualquer erro dentro de um
renderizador, vira o card neutro **"Este trecho não pode ser exibido. Os
dados foram preservados."** - nunca uma exceção que quebra o resto do chat.
O card original fica guardado no elemento (`data-card-json`) pra depuração.

## Como adicionar um card novo

1. **Contrato**: acrescente o `type` e o formato de `data` aqui (seção "Tipos
   de card"). Só aditivo.
2. **Servidor**: um builder em `cards.py` (`card_<tipo>(...)` devolvendo
   `novo_card(type, data, actions)`); se ele sai de uma tool do chat,
   adicione o ramo da entidade em `cards.cards_dos_efeitos` e faça o executor devolver
   `"_efeito": {"entidade": ..., "id": ...}` (chave com `_` nunca vai pra
   IA - `RegistroExecucao` tira antes). Se tem valor em dinheiro, adicione
   os campos em `cards.CAMPOS_SENSIVEIS`. Se o card tem Desfazer de uma
   entidade nova: acrescente em `db.ENTIDADES_DESFAZIVEIS` e um ramo em
   `app._desfazer_itens` (sem commit - a rota faz tudo numa transação).
3. **Front**: `Cards.registrar("<type>", (data, card, ctx) => htmlString)` em
   `static/js/cards-tipos.js`. Todo texto vindo de `data` passa por `Cards.esc`.
   Estilo no bloco "Cards do contrato" do `style.css`, reusando `.card-contrato`
   e os tokens existentes.
4. **Testes**: builder/mapeamento em `tests/test_cards.py`, renderizador em
   `tests/js/cards.test.js` (pelo menos: renderiza com dado de exemplo, escapa
   HTML, dado faltando não quebra).
5. **Headless**: conferir o card em 390px (ver `AGENTS.md`, regra 5).
