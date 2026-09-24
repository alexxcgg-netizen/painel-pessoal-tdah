# Fase 7 — contrato comum das faixas P (assistente proativo)

O painel deixa de esperar o Alex abrir e passa a **avisar, perguntar e lembrar**. Tudo que o assistente produz vira um item da **Caixa do assistente** (tela Assistente + faixa compacta no topo da aba Hoje) e também sai por push.

## API (contrato em `assistente/contrato.py`: não alterar)
- `enfileirar(tipo, titulo, corpo="", *, opcoes=None, origem="", chave_unica="", repetir=None, vence_em=None) -> id`
  Os tipos são `pergunta | aviso | sugestao | briefing | proposta_memoria`. `chave_unica` evita criar o mesmo item duas vezes. `repetir` segue o formato `{"apos_minutos": [120, 240], "max_por_dia": 3}`.
  **A implementação fica em `assistente/caixa.py` (faixa P1a).**
- `resolver(item_id, resposta, texto="")`: as respostas são `sim | nao | adiar | aceitar | recusar` e opções próprias do item. Também implementado em `assistente/caixa.py` (P1a).
- `aviso_permitido(tipo) -> bool`: devolve False se o tipo está desligado ou se a hora cai no silêncio. **A implementação fica em `assistente/avisos.py` (faixa P8)** e todo mundo consulta antes de mandar push.
- As faixas que só consomem (P2, P3, P4, P5, P7, P9) importam de forma tardia (`from assistente.caixa import enfileirar` dentro da função). Nos testes usam `unittest.mock.patch`. Assim elas não dependem da P1a/P8 já estarem prontas.
- Quando um item é resolvido, quem criou precisa saber (ex.: "Pagou o cartão?" → Sim marca a conta como paga). O mecanismo é o seguinte: o item guarda `origem` (ex.: `p2_conta:123`). A P1a chama o `ao_resolver(conn, item, resposta, texto)` do módulo `assistente/gatilhos/<prefixo>.py` correspondente, se ele existir. O prefixo é o texto de `origem` antes do `_`, ou seja, o nome do arquivo do gatilho.

## Periodicidade
- `POST /api/tick` (faixa P1a, protegido por `PAINEL_TICK_TOKEN`) chama `assistente.gatilhos.executar_todos(conn, agora)`. Essa função carrega sozinha todo `assistente/gatilhos/*.py` que tiver `executar(conn, agora)`. Depois o tick processa repetição e expiração dos itens. A infra de carga automática vem da Etapa 0 (X1).
- Cada faixa P cria o seu `assistente/gatilhos/<faixa>_*.py`. Um gatilho precisa ser **idempotente**: se o tick rodar 2 vezes no mesmo minuto, o item não pode duplicar (use `chave_unica`).
- O `agora` é sempre injetado. Nunca chame `datetime.now()` dentro da lógica, porque isso impede de testar.

## Rotas com token (sem PIN)
Crie em `rotas/<faixa>_*.py` um Blueprint `bp` e declare `ROTAS_COM_TOKEN = {"/api/..."}`. A rota confere o próprio token com `hmac.compare_digest` e responde 401 se ele estiver errado ou ausente. O mecanismo vem da Etapa 0 (X1).

## Política de insistência (padrão)
A pergunta fica na Caixa até o Alex responder ou adiar. O push é reenviado depois de 2 h e de 4 h, no máximo 3 vezes por dia, respeitando o horário de silêncio. O tom é direto e sem cobrança.

## Fora do escopo (decisão do Alex)
Vida amorosa e relacionamento **nunca** viram aviso, pergunta nem proposta de memória. Filtre por palavra-chave e teste isso.

## Flags
Cada faixa tem a flag `assistente.<faixa>.ativo`, guardada na tabela `configuracoes` (use os helpers de `db.py` já existentes: confira com `grep -n "def .*configuracao" db.py`). O padrão é ligado, exceto quando o prompt disser outra coisa.

## Dados
Leia tarefas, contas, agenda, hábitos etc. pelas funções que já existem em `db.py`, `agenda.py`, `vida.py` e `notificacoes.py` (use grep). Só crie tabela nova por migração (`migracoes/`). As fixtures de teste são sintéticas, em pt-BR.
