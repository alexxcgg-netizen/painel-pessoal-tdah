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
| `saude_dia` | `agua_copos`, `passos`, `sono_horas`, `treino_min` (revisão da Fase 6) |
| `saude_treino` | `sessoes` (revisão da Fase 6) |

O front mostra `R$ •••` quando `data.oculto` é `true` (nos cards de saúde:
"Dados de saúde ocultos no modo visitante.").

Actions que mudam dado (`desfazer`) também saem de todo card no modo
visitante, e `POST /api/desfazer/<token>` responde 403 (revisão da Fase 6).
**Card novo com dado sensível (dinheiro, saúde) entra em `CAMPOS_SENSIVEIS`.**

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

### `assinatura`, `compra_parcelada`, `resumo_financeiro_recorrente` (Fase 7, N1 - ligados na C1)

Contrato completo do `data` em `docs/contrato-assinaturas.md` (faixa N1). Builders em
`cards.py` (`assinatura_para_card`, `compra_parcelada_para_card`,
`resumo_recorrente_para_card`, `card_assinatura`, `card_compra_parcelada`,
`card_resumo_financeiro_recorrente`) - o classificador local da N1 usa os mesmos.

- Além dos campos do contrato N1, o `data` leva os nomes que o renderizador de
  `static/js/cards-tipos.js` (V1) já lê: `cartao`/`em_dias` (assinatura),
  `restantes`/`termina_em` (data ISO da última parcela) (parcela),
  `total_mes`/`n_assinaturas`/`n_parcelas`/`proxima_cobranca {nome, data}` (resumo).
  Pendente pra C2: escolher um nome só e aposentar o outro.
- Modo visitante (`CAMPOS_SENSIVEIS`): somem `valor` (assinatura), `valor_total`/
  `valor_parcela` (parcela) e `total_mensal`/`assinaturas_total`/`parcelas_total`/
  `total_mes`/`proximas_cobrancas`/`proxima_cobranca` (resumo).
- Abrir em: aba `gastos` (seção Assinaturas).
- **Desfazer:** o token da N1 (criar assinatura, cancelar assinatura, criar compra
  parcelada) funciona na rota GERAL `POST /api/desfazer/<token>` desde a C1 - o
  botão não precisa saber de qual faixa é o card. A rota própria
  `POST /api/financas/desfazer/<token>` continua valendo (mesmo token, 409 na outra
  depois de usado numa).

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

## `rota` (aditivo, 2026-10-09)

Gerado pelo `estimar_trajeto` do chat (nao vem do banco). `data`: `paradas` (lista de `{nome, endereco}`, da
partida ao fim), `distancia_km`, `duracao_min`, `partir_de_onde_estou` (bool - a primeira parada vira "Onde voce
esta"). `actions`: uma `abrir_link` (`{tipo, rotulo, url}`) com o link universal do Google Maps; o front so
renderiza `abrir_link` quando a `url` comeca com `https://www.google.com/maps/` ou `https://www.windy.com/`,
ou e o deep link do Waze `https://waze.com/ul?` (qualquer outra e ignorada).

**Trânsito + Waze (aditivo, 2026-10-15)**: `data.transito_min` (minutos a mais pelo trânsito; o front só mostra
"+N min de trânsito" com ≥ 3) e `data.lentidao` (até 3 `{nivel: "lento"|"parado", frase}` - a frase vem pronta
do `maps_client.frase_trecho`, ex. "Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz"; **nunca
afirma a causa**). `traco.lentos` = `[{nivel, pontos[[x,y]]}]`, pintado por cima do caminho (âmbar/vermelho) e
aceso só depois que o carrinho passa. Segunda action `abrir_link` pro Waze (`cards.acao_waze`): "Ir com Waze",
ou "Waze até X" quando tem várias paradas (o Waze só vai até a primeira). Os cards `date`/`balada`,
`voo_agendado` e `vespera_voo` ganham o mesmo botão e `transito_min` ("40 min de carro (+12 de trânsito)").

**Dois planos no "Dia montado" (aditivo, 2026-10-21, protótipo aprovado "balão que vira card + pílula")**:
`tarefas_criadas.data.planos = {escolhido: "a"|"b", a: {nome, nota, itens[{id, hora}]}, b: {...}}` quando o
`planejar_dia` mandou `plano_b` (mesmos blocos, outras horas; o A é o gravado). Pílula com fundo que desliza
(`data-acao="dia_plano"`), nota curta, e trocar chama `POST /api/tasks/<id>/hora` por item (otimista, volta se
falhar) e refaz trilha + lista na ordem nova. O histórico (`cards.acertar_plano_escolhido`) marca `escolhido` pelo
que as horas de agora dizem. **Balão que vira card** (`chat.js/juntarBalaoECard`): o primeiro card da resposta
cola embaixo do balão (canto reto, borda na cor do card, card descendo de dentro numa cortina); histórico abre
colado e parado.

**Treino ao vivo (2026-10-21, `treino_vivo.py`, skill `treino-ao-vivo`)**: `treino_agora` = `{sessao_id,
ficha_id, grupo, data, exercicios[{nome, series, reps, carga}], feitos[i], concluido, duracao_min, escolhida_por?}`
(vem do `comecar_treino`). Caixinha por exercício (`data-acao="treino_ex"`, otimista, volta se falhar,
`POST /api/treino/sessoes/<id>/exercicio`), o próximo a fazer em destaque, barra de progresso, contador `n/total`;
o último marcado registra o treino e abre "Subiu ou baixou alguma carga?". Histórico atualiza pelo
`cards.acertar_treino_agora`. `treino_carga` = `{mudancas[{grupo, exercicio, antes, depois, sentido:
subiu|desceu|null}]}` (do `atualizar_carga_treino`): antes riscado → depois com seta, um card por resposta, Desfazer
volta a ficha (entidade `treino_carga`, da última troca pra primeira). Cor `#b5e48c`. Cada linha traz `historico[{data, kg}]`
(tabela `treino_cargas`, um ponto por dia em que a carga em kg mudou - ficha salva grava o ponto de partida; Desfazer
apaga os pontos que a troca criou): com 2+ pontos vira o gráfico `graficoCarga` (área + segmentos verdes/rosados por
subida/descida, último ponto maior, kg do começo e do fim). Carga sem "kg" ("3 placas") não entra no gráfico. Animação do exercício
(aprovada no artefato, no app desde o SW v91): painel `.tv-agora` em cima da lista com o exercício da vez em 3D
(`static/js/exercicio-3d.js`, 43 exercícios, um corpo só + equipamento, músculo acende no empurrão), "Agora · n/total",
séries em tracinhos e "rep x/y". `Exercicio.tipo(nome)` lê o nome livre da ficha; desconhecido = painel escondido (nunca
animação errada). `CardsVivos.preparar` desenha; treino em andamento anima enquanto está na tela (histórico também - ele
abre o chat no meio do treino), concluído ou reduced-motion = pose parada. Marcou: `trocarExercicio` sai/entra pro próximo;
terminou: o painel some.

**Tempo no caminho (aditivo, 2026-10-21)**: rota ≥ 25 km ganha `data.tempo = {total_km, saida, trechos[{tipo, de_km,
ate_km, hora, frase}]}` (`clima_rota.py`: Open-Meteo numa chamada, um ponto a cada ~20 km, na HORA em que ele passa
ali). `tipo` ∈ granizo/trovoada/neblina/chuva_forte/chuva/vento/ok. O front desenha uma barra do km 0 ao fim com
cada trecho pintado (chuva listrada, neblina esfumada; estica em cascata só no `.card-novo`) e lista só os trechos
que não são tempo firme (ou "Tempo firme no caminho todo."). `traco.tempo` = `[{nivel, pontos}]`, faixa larga
translúcida por baixo do lento. Cores: chuva `--cor-cat-1`, forte `--cor-cat-2`, neblina `--text-muted`,
trovoada/granizo `--cor-cat-3`, vento `--cor-cat-6`.

## Cartões vivos (aditivo, 2026-10-09)

Renderizados em `static/js/cards-vivos.js` (rota e saude_treino em `cards-tipos.js`). O HTML já sai no estado
final; a animação só entra em resposta nova (`CardsVivos.animar`). Campos (`data`):

| type | data |
| :--- | :--- |
| `edicao` | `itens: [{rotulo, titulo, mudancas: [{campo, de, para}]}]` + action `desfazer` (volta os valores antigos) |
| `voo_resumo` | `total_min, voos, por_funcao[{nome,min}], por_aeronave[{nome,min}], primeiro_solo{minutos,data}, ultimo{data,aeronave,origem,destino}, dias_sem_voar, simulador_min, meta_horas, meta_definida` |
| `clima` | `lugar, agora{condicao, chovendo_agora, temperatura, sensacao, umidade_pct, vento_kmh}, proximas_horas[{hora, chuva_pct, temp}]` |
| `gastos_resumo` | `periodo{de,ate}, total, quantidade, por_categoria[{categoria,valor}], maiores, categoria_filtrada` (visitante: `oculto`) |
| `dia` | `dia, compromissos[{hora, ate, titulo, origem, concluida, dia_inteiro}], tarefas_sem_hora[]` |
| `viagem_janelas` | `destino, mes, dia_definido, internacional, cenarios{no_feriado?, fora?: {ida, alta{nome,de,ate}?, janelas[{item, inicio, fim, status: agora/em_breve/passou, dias}]}}, fontes` |
| `agua` | `data, copos, meta` + `desfazer` (visitante: `oculto`) |
| `rota` (+) | `traco{w, h, pontos[[x,y]], paradas[[x,y]], lentos[{nivel, pontos}]}` - caminho real já projetado (+ trechos lentos/parados, 2026-10-15) |
| `saude_treino` (+) | `semana[{data, feito, hoje}] (seg..dom), meta_semana` |
| `tarefas_lista` | `de, ate, hoje, so_concluidas, total, feitas, itens[{id, titulo, hora, data, concluida}], atrasadas[...], mais` |
| `tarefas_criadas` (+) | `dia, agenda_do_dia[{id, titulo, hora, concluida, nova}]` - o dia em volta da tarefa nova |

## Linguagem visual dos cards - o que o Alex aprovou (2026-10-14)

Aprendizado vivo: ler antes de criar ou mexer em qualquer card, e acrescentar aqui o que ele
aprovar/recusar nas próximas rodadas. Referência navegável (9 cenas aprovadas):
https://claude.ai/artifact/JzmyFm39GypNtUKXLuS1ph - fonte em `docs/prototipos/cards-ia-v2.html`
(abre direto no navegador; republicar no mesmo artefato a cada rodada).

**Princípios (o que fez ele gostar)**
1. **Cada assunto tem a sua cara, a família é a mesma.** Casca igual (selo colorido + "quando" em
   mono no topo, rodapé com Desfazer + uma informação útil à direita), mas o miolo é desenhado pro
   assunto: voo = cartão de embarque com picote; tabelionato = pasta + carimbo; mercado = cupom
   saindo da impressora; balada = céu de noite; presente = caixa que abre; date = coração que se
   desenha. Nunca um card genérico "título + lista" pra tudo.
2. **Uma cor de destaque por assunto** (`--cor` no card): voo `#8fd0ff`, date `#f5a3b8`, balada
   `#c4a1ff`/`#ff8fd1`, cartório `#7fd9d0`, presente `#ffd36e`, gasto `#b5e48c`, tarefa `#f0a58f`,
   alteração `#aab4f6`, feito `#9fdcb0`. O resto fica nos neutros do app.
3. **A IA pensa no antes, não só registra.** Todo card de compromisso responde "a que horas eu
   saio / começo a me arrumar", contando de trás pra frente (linha *se arrumar → sair → chegar*).
   Liga as pontas da semana (balada na sexta lembra do voo de sábado e calcula o sono).
4. **Interação de verdade dentro do card**: caixinhas que marcam, chave liga/desliga que muda a
   resposta, ideias escolhíveis, botão de conflito ("Passar Mikael pras 8h30" / "Deixa assim") em vez
   de mexer sozinha. No voo: tocar num aeródromo faz o avião ir/voltar até ele e mostra a perna.
5. **Movimento que assenta**: entrada do card por altura (grid-rows 0fr→1fr) + blur/scale com
   `--ease-bounce`; filhos em cascata (~80 ms); números contam (count-up com ease-out cúbico);
   só o pedaço que mudou se mexe (alteração: valor velho sobe riscado, novo cai; hora rola tipo
   placar). Nada piscando sem parar além de detalhe de fundo (estrelas). Sempre com
   `prefers-reduced-motion`.
6. **Resposta antes do card**: linha "pensando" com os passos reais trocando (shimmer), que vira um
   recibo recolhível ("Preparou o voo · 4 passos"); depois o texto palavra por palavra com os dados
   importantes em negrito; o card abre por último. Lembrete simples não precisa de card - vira uma
   pílula na frase.
7. **Dados do mundo dele, não exemplo genérico**: códigos ICAO, NM, VFR, horas até a meta de 150 h.

**Fatos do Alex que os cards usam**
- Voo: origem padrão **SSBL** (Aeroclube de Blumenau) quando ele não disser outra; chegar **45 min
  antes** da decolagem; somar o trajeto de casa até o aeroclube (~65 min) pra dizer a hora de sair.
  Rota pode ter várias pernas; mostrar NM por perna e total (distância ortodrômica entre
  aeródromos - NexAtlas não tem API pública, não depende dela).
- **Se arrumar leva 45 min** (date, balada, qualquer saída "arrumado").
- **Sono: 8 h** antes de acordar pra voo ("na cama até HH:MM" = acordar − 8 h). Aprovado 2026-10-15.
- **Dinheiro que se repete mostra o impacto no ano** (assinatura: "R$ X a mais por mês — R$ 12X num
  ano"; assume cobrança mensal). Aprovado 2026-10-15.
- **Coisa de mercado é sempre no cupom** (`.tx-impressora`), inclusive previsão de compra; "feito"
  vira carimbo no papel. Aprovado 2026-10-15.

**Checagem antes de dar como pronto**: 390 px sem rolagem lateral, nada encavalado (rótulos de
linha do tempo e de rota são o que mais quebra), número longo sem quebrar entre "R$" e o valor
(`&nbsp;`), sem `pageerror`.

### O que já está no app (1ª leva, 2026-10-14)
| Cena | Onde | Dado |
| :--- | :--- | :--- |
| Voo | type novo `voo_agendado` (`cards.card_voo_agendado`, `static/js/cards-aviacao.js`) | `rota_voo.montar` (pernas/NM/horários), `voo_briefing_min`, `_saida_pro_voo` (Maps, opcional), horas do curso. Toque num aeródromo = `data-acao="voo_parada"`. |
| Mercado/gasto | `transacao` de gasto real ganha `mes` + `dias` (`cards._contexto_gasto`) → cupom + barra do teto + 14 barrinhas | orçamento da categoria, gasto do mês, 14 dias. Visitante: `mes`/`dias` saem junto com `valor`. |
| Alteração | `edicao` (mesmo dado): hora → relógio rolando; valor curto → troca no lugar; frase longa → só o pedaço que mudou troca; texto todo novo → antes → depois | - |
| Concluir | type novo `tarefa_feita` (`cards.card_tarefa_feita`) - `registrar_feito` e `ajustar_tarefa(status=concluir)` | feitas/total de hoje (conta a concluída mesmo atrasada), próxima pendente de hoje; "em 1h40" é conta do front (some no histórico de outro dia). Desfazer reabre (ou apaga a que nasceu concluída). |
| Tarefa com aperto | `tarefas_criadas` ganha `aperto` {id, titulo, hora, sugestao} quando a nova cai a < 45 min de outra pendente do dia | Só horário de início é dado real. Sugestão = outra a 60 min da nova, se não apertar uma terceira. Botão → `POST /api/tasks/<id>/hora`. |

### O que já está no app (2ª leva, 2026-10-14)
A IA marca `estilo` no `registrar_tarefa` (só com dia marcado; sem dia vira tarefa comum).
Coluna `tasks.estilo` + `tasks.extras` (JSON: `com_quem`, `lista`, `ideias`, `volta`, e o que o
card guarda depois: `feito` de cada item, `escolha`, `lembrete_id`, `volta_modo`, `uber_tarefa_id`, `anual`, `historico`, `renovado_id`).
O que precisa de rede vai no efeito (`_plano_do_estilo` em `app.py`) e um resumo volta pra IA
(`plano`) - a frase dela bate com o card. Card: `cards.card_compromisso`, front em
`static/js/cards-saidas.js` + `secoes/hoje/cards-saidas.css`.

| Cena | Type | Dado |
| :--- | :--- | :--- |
| Date | `date` | linha se arrumar → sair → chegar (`_saida_pro_compromisso`: Maps se `ENDERECO_CASA`, senão hora − 15), clima na hora (`clima.previsao_na_hora`, `CIDADE_PADRAO`), lista "antes do date" que marca (`POST /api/tasks/<id>/lista`). |
| Balada | `balada` | céu da noite + linha com a volta. **Sono só se o dia seguinte tem compromisso com hora** (`_primeiro_compromisso_do_dia`: voo ou tarefa) - volta padrão 03:00 se ele não disse (pedido do Alex). Como volta: ver 3ª leva (a chave do Uber virou dirigindo/carona/Uber). |
| Tabelionato/documentos | `documentos` | pasta + checklist + carimbo "Pasta pronta"; horário do Google (`maps_client.horario_funcionamento`, Places `regularOpeningHours`) e aviso se a hora marcada cai fora/no almoço. Sem "espera ~20 min" (não há dado real). |
| Presente | `presente` | dias até a data, comprar até = data − 4 (`DIAS_ENTREGA_PRESENTE`); tocar numa ideia cria/troca o lembrete "Comprar presente: X" nesse dia (`POST /api/tasks/<id>/presente`). ≤ 4 dias: avisa que pela internet não chega. Visitante não vê `preco`. |

Desfazer apaga junto o lembrete do presente e a tarefa do Uber. No histórico, o que foi marcado
depois vem de `/api/tasks/estado` (`extras`) → `CardsSaidas.aplicarEstado`.

### O que já está no app (3ª leva, 2026-10-14 - `docs/briefings/2026-10-14-3a-leva.md`)
| Cena | Onde | Dado |
| :--- | :--- | :--- |
| Volta da balada | `balada` ganha `volta_modo` (`dirigindo` padrão / `carona` / `uber`) no lugar de `uber` | Controle de 3 com pílula. Uber cria "Chamar Uber pra voltar" 30 min antes da volta (03:00 se não dita) - `POST /api/tasks/<id>/volta {modo}`; os outros modos apagam a tarefa. `/api/tasks/estado` devolve `volta_modo`. |
| "Pensando" | evento SSE `passo` {texto} (`claude_client.avisar_passo`; `cards.passo_ao_vivo` por tool, emitido no `RegistroExecucao` antes de rodar) | Front (`chat.js`): `criarLinhaPensando` + `reciboPassosHTML` ("N passos · X s", `<details>`). Sub-passos de rede em `_plano_do_estilo`. |
| Tempo na hora do voo | slot `.va-tempo[data-voo-tempo]` no `voo_agendado` (só ≤ 30 h e até 1 h depois da decolagem) preenchido no `CardsAviacao.preparar` | `GET /api/voos/<id>/tempo` → `{previsao: {icao, substituto_de, hora, categoria, vento, teto_ft, visibilidade_m, fenomenos, pode_ter[≤2], aviso} \| null, motivo}`. Nunca inventa: fora do TAF = nada. |
| Horas com 1 toque | type novo `voo_horas` (`cards.card_voo_horas`, publicado por `conversa_proativa.verificar`) | `data`: `id, data, hora, rota\|null, icao, estimativa, sugestoes[3], horas, horas_min (sem este voo), meta_horas`. Chip/Salvar → `POST /api/voos/<id>/horas {horas}` (0 < h ≤ 12) → `{horas, horas_min}`. Sem selo "registrado" (é pergunta). |
| Presente anual | `presente` ganha `anual`, `ano_passado` | `extras.anual` (IA ou regex do título); `conversa_proativa.renovar_presentes_anuais` 1×/dia: ideias não usadas + `historico[{ano, presente}]`, idempotente por `renovado_id`. |

Aprovado/decidido nessa leva (vetável): volta padrão **dirigindo**; recibo dos passos fica dentro
da bolha acima do texto; previsão só dentro de 30 h; estimativa de horas = rota + 12 min de
motor; presente vira anual sozinho pelo título.

### O que já está no app (4ª leva, 2026-10-15 - `docs/briefings/2026-10-15-4a-leva.md`)
Automações: o assistente puxa o assunto sozinho no chat (`conversa_proativa.verificar`, tick de
5 min) e o card traz o próximo passo num toque. Front em `static/js/cards-automacao.js` (+ véspera e
projeção em `cards-aviacao.js`), CSS em `secoes/hoje/cards-automacao.css` (reusa `.sd-linha`,
`.sd-check`, `.sd-status` dos compromissos).

| Cena | Onde | Dado |
| :--- | :--- | :--- |
| Véspera do voo | type `vespera_voo` (`cards.card_vespera_voo`; `conversa_proativa.vespera_do_voo`, 20h-23h30 do dia anterior, só voo **com hora** e sem horas) | `data`: `id, data, hora, rota\|null, icao, acordar, sair, chegar, pouso, trajeto_min, arrumar_min, antecedencia_min, mochila[{texto, feito}]`. Despertador que toca + "Acorda HH:MM" grande, "Pra 8 h de sono, na cama até HH:MM", linha acorda → sai → chega → decola, folgas numa linha, slot do TAF (mesmo do `voo_agendado`) e mochila com ícone que pula a cada item e fecha o zíper (✓ "mochila fechada") no último (`cards.MOCHILA_VOO` = CIV e CMA + `vida.CHECKLIST_PRE_VOO`) → `GET/POST /api/voos/<id>/mochila {i, feito}`. |
| Manhã do voo | `briefing_voo` existente (`conversa_proativa.manha_do_voo`) | A partir de max(06:30, sair − 1h30) e antes de decolar: "Bom dia! Voo hoje às H. Sai às S..." + METAR. Push "Voo hoje". |
| Documento vencendo | type `documento_validade` (`conversa_proativa.documentos_vencendo`, 9h-21h) | `data`: `id, titulo, vence, dias, marco (60/30/7), recorrente`. Carteirinha com anel da contagem (`dias/60`, número conta de 60 até os dias), marcos 60·30·7, cor muda (folga teal → atenção amarelo → urgente coral). "Me lembra de agendar amanhã" → `POST /api/tasks`. Front recalcula `dias` com o relógio (histórico). |
| Compras que acabam | type `compras_previsao` (`conversa_proativa.avisar_compras`, 1×/dia 9h-21h) | `data.itens[≤4]`: `item, chave, intervalo_dias, ultima, prevista, dias`. **Cupom** saindo da impressora (mesmo `.tx-impressora` do gasto): "Previsão · mercado", um item por linha com "acaba em N dias"/"acabou há N dias", barra do ciclo, total "NA LISTA n/N". "Pôr na lista" bate um **carimbo** verde torto "NA LISTA" no item (`POST /api/compras`) / "Ainda tem" (`POST /api/compras/adiar {item}` → `{ate}`). |
| Assinatura mais cara | type `assinatura_subiu` (`conversa_proativa.assinaturas_que_subiram`; o push antigo continua) | `data`: `descricao, categoria, de, para, pct` (sensíveis: `de/para/pct` somem no visitante → `oculto`). **Etiqueta remarcada**: etiqueta velha cinza torta com o preço riscado em coral, etiqueta nova na cor do card cai por cima (número conta do velho pro novo), selo `+N%`; "São R$ X a mais por mês — R$ 12X num ano."; "Mantém" / "Me lembra de cancelar" (`POST /api/tasks`). |
| Projeção das horas | `projecao` em `voo_resumo`, `voo_agendado`, `voo_horas` (`cards.projecao_horas`) | `{ritmo_h_semana, voos_semana, horas_por_voo, falta_h, meta_horas, data_meta, data_meta_mais_um, janela_dias}` ou `null`. **Régua** `.va-proj`: hoje → meta, marco "+1 voo/semana" em `ritmo/(ritmo + h por voo)` do caminho e "no ritmo atual" no fim (data em cima/embaixo pra não encavalar), "faltam X h"; o texto ("No ritmo dos últimos 2 meses (X h/semana), os 150 h chegam lá por mai 2027. Com 1 voo a mais por semana: fev 2027.") vira o `aria-label`. |

O que ele já respondeu num card de automação (tarefa criada, item na lista, "ainda tem", "mantém")
fica guardado no aparelho (`localStorage` `cards-automacao-feito`, só conveniência) pra o histórico
não oferecer o mesmo botão de novo.

Aprovado/decidido nessa leva (vetável): véspera só pra voo com hora, às 20h; manhã a partir de
max(06:30, sair − 1h30); push antigo "Voo amanhã/Pre-voo" só pra voo sem hora; CIV e CMA na mochila;
documentos em 60/30/7 (substitui o aviso único de 8-30 dias); compras com 3+ compras e intervalo
regular de 3-120 dias, avisa ≤ 3 dias antes e larga se passou mais de meio ciclo; "ainda tem" adia
meio ciclo; projeção pelos últimos 60 dias, data acima de 5 anos não aparece.

Acabamento da 4ª leva (pedido: "deixe cards bem legais"): compras foi pro cupom (mercado = cupom,
regra 1) com carimbo; assinatura virou etiqueta de preço remarcada; projeção virou régua; véspera
ganhou despertador, hora de deitar (8 h de sono) e mochila que fecha. **Aprovado pelo Alex
(2026-10-15)**: as 8 h de sono, o impacto anual da assinatura (×12, cobrança mensal) e compras no
cupom.
