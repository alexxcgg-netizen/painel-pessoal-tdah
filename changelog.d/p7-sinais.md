### Fase 7 - faixa P7 (sinais do iPhone via app Atalhos)

- **`POST /api/sinal` (rotas/p7_sinais.py, Blueprint `bp`, `ROTAS_COM_TOKEN =
  {"/api/sinal"}`).** Endpoint genérico pra qualquer automação pessoal do app
  Atalhos: `{"tipo": "cheguei|sai|acordei|dormir|carregando", "lugar": "...",
  "quando": "ISO opcional"}`, autenticado por `Authorization: Bearer` +
  `PAINEL_SINAL_TOKEN` (`hmac.compare_digest`; sem token configurado a rota
  fica sempre fechada, nunca aberta por falta de configuração). Grava em
  `sinais` (`migracoes/202609241240_p7_sinais.sql`: id, tipo, lugar, quando,
  recebido_em) e responde `{"ok": true, "id": ...}` - sem mensagem de
  display. **Não substitui** `/api/atalho/local` (app.py, geofence
  casa/mercado, `X-Webhook-Token`/`PAINEL_ATALHOS_TOKEN`, devolve mensagem
  pro Atalho mostrar): os dois continuam existindo, propósitos diferentes -
  ver tabela comparativa em `docs/atalhos-sinais.md`.
- **`assistente/sinais.py`.** `ultimos_sinais(conn, tipo=None, desde=None)` e
  `sinal_recente(conn, tipo, lugar=None, janela_min=10, agora=None)` - o que
  o motor de regras (faixa P4) vai consultar. A validação/gravação real
  (`token_valido`, `quando_valido`, `gravar`, `TIPOS_VALIDOS`) mora aqui
  também, propositalmente, pra dar pra testar sem depender da infra de
  Blueprint (Etapa 0/X1) estar mesclada - `rotas/p7_sinais.py` fica só com a
  cola Flask fina.
- **Reações simples embutidas** (`reagir`, flag `assistente.p7.reacoes`,
  ligada por padrão, guardada em `configuracoes`): `acordei` tenta chamar
  `assistente.gatilhos.p3_briefing.garantir_briefing(conn, agora)` de forma
  tardia/defensiva (nome de função **palpite** - a P3 ainda não existia
  nesta integração; confirmar o nome real antes de contar com isso em
  produção) - sem a P3, o sinal só fica registrado mesmo, sem erro. `cheguei`
  no mercado põe a lista de compras pendente (`db.list_compras_pendentes`)
  como item na Caixa via `assistente.caixa.enfileirar` (import tardio, P1a),
  no máximo uma vez por dia (`chave_unica`). Qualquer exceção numa reação é
  engolida - nunca derruba a gravação do sinal, que já foi commitada antes.
- `docs/atalhos-sinais.md`: passo a passo das 4 automações (Chegar/Sair de
  local, Alarme parado, Modo Sono, Carregador conectado), tabela comparando
  com `/api/atalho/local` e sugestões de automações úteis pra TDAH.
- `tests/test_fase7_p7_sinais.py`: 46 testes + 11 subtests, 0 falhas - token
  certo/errado/ausente/sem configuração, `quando` válido/inválido/tipo
  errado, gravação (id sequencial, commit visível), `ultimos_sinais`/
  `sinal_recente` (filtro por tipo/lugar/desde, janela de tempo, sinal no
  futuro, `quando` corrompido), reações (flag ligada/desligada, mercado com
  e sem lista, P1a/P3 ausentes não quebram, exceção do `enfileirar`/`P3` não
  quebra) - tudo com dublê de banco em memória e `enfileirar`/P3 mockados
  via `sys.modules`, nenhuma chamada real.
- `tests/test_fase7_p7_rota_sinal.py`: teste HTTP fim-a-fim de `POST
  /api/sinal` (mesmos casos, via `app.test_client()`) - **com skip
  automático** enquanto a infra de rotas por Blueprint (Etapa 0/X1,
  `rotas/__init__.py`/`rotas/_base.py`, branch `fase7/e0-backend`, commit
  `4b68396`) não chegar em `fase7/integracao` (ver
  `scripts/ralph-p7-sinais/progress.txt`). Ativa sozinho assim que a
  integração mesclar essa infra, sem precisar editar nada aqui.
