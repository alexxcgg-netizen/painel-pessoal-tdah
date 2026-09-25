# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

## 2026-09-25 - Redesenho visual da tela de login/PIN

Só camada visual (`templates/login.html`, `templates/configurar_pin.html`, `static/css/login.css`,
toggle de máscara em `static/js/login.js`); autenticação, POST `/login {pin}`, bloqueio 429 e
redirect intactos. Fundo `#000` sem aurora, destaque único `#8e8ea0` (o `--cor-acento` do painel,
sai o verde `#41aa75`), erro `#e5746f`. 6 slots 48x56 em IBM Plex Mono: dígito aparece ~400 ms e
vira ponto; preenchimento com fade + escala 0.96→1; barra fina corre em `#espera` enquanto
verifica; erro pisca uma vez e limpa; bloqueado = slots cinza + mensagem de minutos;
`prefers-reduced-motion` sem animação. Teste `tests/test_login_visual.py`.

## 2026-09-25 - Fase 9: volta ao painel antigo (pedido do dono), só Finanças nova

O dono não gostou do redesign "Conversa" (4 abas, verde sobre preto) e pediu o painel de antes.
`templates/` e `static/` voltaram ao commit `14a0939` (último antes da mudança visual; código do
app idêntico ao merge da Etapa A `77c559e`): 8 abas, cores por aba, Hoje/Tarefas/Vida/Aviação/
Construtora/Assistente como eram. `app.py` também voltou (sai o filtro `?estado=` de `/api/tasks`).
**Exceção: aba Finanças fica a nova** (topo com resumo, gasto por categoria, evolução do mês,
fatura x conta; "Últimos dias" agora recolhível), no destaque cinza do tema antigo.
Dependências da Finanças nova mantidas: `rotas/f9_financas.py` (`por_dia_mes`), 5 tokens no
`tokens.css` antigo (`--cor-alerta`, `--cor-texto-2`, `--fonte-base`, `--raio-cartao`,
`--raio-pequeno`), service worker v24 (acima da v23 já instalada). Bugs antigos corrigidos (com
aval do dono): comentário do `tokens.css` que anulava `--cor-bg` (fundo transparente/claro →
escuro como desenhado) e `bancos.css` preso a `#tab-bancos` (ícone de banco gigante). Teste
`tests/test_fase9_volta_painel.py`. As entradas "Etapa C" abaixo descrevem o que foi revertido.

## 2026-09-25 - Fase 9 (Etapa C, parte 3): polimento final

- **Topo em 2 linhas** (todas as abas): título curto + ícones de voz (com ponto de aviso
  crítico via `/api/sobrecarga`), hiperfoco (popover 25/50/90), relógio da visão do dia (só no
  Hoje) e ⚙; linha 2 = campo de captura com botão de enviar em ícone. Lua/avião/olho/exportar/sair
  foram para a folha ⚙ (mesmos ids/handlers). "Pendências do assistente" depois da conversa,
  recolhidas; a conversa avisa "Tenho N pendências".
- **Tarefas**: seletor Pendentes | Hoje | Concluídas (concluídas voltaram a aparecer, com
  reabrir), `GET /api/tasks?estado=pendentes|concluidas&limite=` (sem parâmetro = igual antes),
  frase-resumo e gráfico real de concluídas nos últimos 7 dias, checkbox redondo.
- **Viagens**: aviãozinho animado na linha do tempo (desliza até hoje, balanço leve,
  `prefers-reduced-motion`), marcos passagem/hotel/seguro/embarque, "faltam N dias"; cálculo
  puro em `static/js/secoes/vida/viagens-aviao.js` com testes `node --test`.
- **Componentes**: brilhos coloridos removidos de cartões/badges/botões/linha do tempo (barra de
  vidro intocada), checkbox estilo Conversa, "últimos dias" de Finanças como lista leve.
- Service worker v23. Suíte: 3776 Python + 240 JS ok; só a falha antiga dependente de data.

## 2026-09-25 - Fase 9 (Etapa C, parte 2): Hoje, Finanças e Vida no estilo Conversa

- **Hoje** (`#conversa-hoje`): o topo da aba virou uma conversa com o assistente — saudação,
  cartão do gasto do mês com gráfico de área do acumulado (mês anterior tracejado) e
  hoje/fatura/conta, "em foco agora", "próximos"; chips de pergunta que usam o chat existente. As
  seções antigas continuam na página, recolhidas.
- **Finanças**: `GET /api/financas/resumo` ganhou `por_dia_mes` e `por_dia_mes_anterior`. Topo da
  aba com frase-resumo calculada em código, gasto por categoria (barras), evolução do mês (SVG) e
  fatura x conta; metas e Construtora recolhidas.
- **Vida** (`#vida-grupos`, variante "Grupos" escolhida pelo dono): 7 grupos (Aviação em
  destaque, Rotina, Saúde, Pessoas, Coisas, Mundo, Mente) com contador e mini gráfico; a aba abre
  só nos grupos e mostra uma seção por vez (`window.VidaGrupos.abrirSecao`). Deep link da Aviação
  abre o grupo.
- Service worker v22 (precache dos arquivos novos).

## 2026-09-25 - Fase 9 (Etapa C, parte 1): visual "Conversa" e 4 abas

O dono escolheu a direção **"Conversa"** (app como chat de assistente, com cartões e gráficos)
no segundo laboratório (20 direções de apps reais; as 10 de HUD da 1ª rodada foram recusadas).

- **C1 tokens**: paleta Conversa em `static/css/ui/tokens.css` (fundo `#0e0f0e`, cartão
  `#111312`, acento `#159C82`, alerta `#e0928f`), fonte Inter, raios; brilho/LED colorido
  removidos (a barra de vidro da navegação ficou igual, a pedido do dono).
- **Bug antigo corrigido**: um comentário do `tokens.css` continha `--surface*/`, que fechava o
  comentário cedo e anulava `--cor-bg` — o fundo do app era transparente (branco em vários
  navegadores) desde a Fase 8. Teste que acusa `*/` perdido em qualquer CSS.
- **8 abas → 4** (decisão delegada pelo dono): Hoje (+Assistente, +resumo/agenda/plano do
  dia/devo sair/fechamento do Painel), Tarefas, Finanças (+Construtora em `#secao-construtora`),
  Vida (+Aviação no topo em `#secao-aviacao`, +saúde/medicamentos/peso/datas/memória/notas/
  decisões/brain dump/esperando resposta do Painel). Botão ⚙ no cabeçalho abre `#sheet-config`
  (custo de IA, modo teste, exportar CSV, regras do assistente). Nomes antigos (voz, links,
  `showTab("painel")`) redirecionam para o destino novo. Carregamentos de dados num lugar só
  (`static/js/nucleo/navegacao.js`).
- `bancos.css` saiu de `#tab-bancos` (aba extinta na Etapa A) para `#tab-gastos` — o ícone de
  banco aparecia gigante. Teste que acusa CSS/JS/template preso a aba removida.
- Service worker v20.

## 2026-09-25 - Fase 9 (Etapa A): Finanças numa aba só, sincronização sem duplicar

Bancos e Gastos viraram uma aba só, **Finanças**, com um único botão **Sincronizar**. A
sincronização do Nubank não duplica mais, o cartão fica separado da conta corrente e os
gastos aparecem com nome legível.

- **Sincronização idempotente** (`rotas/f8_banco.py`, `pluggy_client.py`): upsert pelo id da
  transação Pluggy (`novas`/`atualizadas`/`sem_mudanca`) + reconciliação por conta: dentro do
  período devolvido pelo Pluggy, linha cujo id não voltou é apagada (`removidas`). Causa das
  duplicadas no deploy: reconexão do item fez o Pluggy reimportar o histórico com ids novos.
  Nunca reconcilia se a busca veio truncada ou vazia; nunca toca em `expenses`.
  `get_transactions` agora devolve `(transacoes, truncado)`.
- **Cartão x conta**: `bank_accounts.tipo` = `cartao` (Pluggy `CREDIT`, saldo = fatura em
  aberto) ou `conta` (`BANK`, saldo = dinheiro). Colunas novas em `bank_transactions`
  (migração `202609251300_f9_sync.sql`): `estabelecimento`, `categoria_pluggy`,
  `descricao_original`, `tipo_operacao`, `estorno_de_external_id`.
- **Sinal do valor**: no cartão o Pluggy manda compra com amount positivo + `DEBIT`; saída é
  decidida por `tipo_operacao`, não pelo sinal. Parcelas futuras (até 2027) não entram.
- **Descrição** (`financas_descricao.py`, puro): tabela local razão social → nome conhecido
  (Arcos Dourados → McDonald's, Raia362 → Droga Raia...), casamento por palavra inteira
  (sem "Praia" → Droga Raia), "Pix · Nome", categorias do Pluggy em português, estorno com a
  compra original quando houver vínculo. Sem IA (`precisa_ia()` só sinaliza).
- **Extrato e resumo** (`rotas/f9_financas.py`): `GET /api/financas/extrato?antes=&dias=15`
  (janelas de 15 dias, `proximo_antes`) e `GET /api/financas/resumo` (gasto do mês sem
  pagamento de fatura/transferência, por categoria, fatura, saldo, patrimônio).
  `/api/patrimonio` passou a tratar o cartão como dívida (`fatura_aberta`).
- **Tela**: aba Finanças única, botão Sincronizar único (sai Pluggy Connect da interface; rotas
  `/api/bancos/conectar/*` ficam no backend), últimos 15 dias + "Carregar mais 15 dias",
  extrato completo e assinaturas recolhidos. **Importar OFX removido** (rota, `bank_ofx.py`,
  template, JS, CSS, testes).
- Verificado com a conta real (banco temporário): 413 transações (384 cartão, 29 conta),
  3 sincronizações seguidas = 0 novas na 2ª e 3ª; setembro R$ 1.122,75, fatura
  R$ 2.377,35, conta R$ 7,25.

## 2026-09-25 - Fase 8: visual dark + financeiro/banco unificado

Fechamento da Fase 8: tema escuro mais sóbrio no visual todo, e no financeiro a
sincronização com o Nubank (via Pluggy) passa a aparecer junto dos gastos manuais, com
aviso quando algo parece estar duplicado, e as assinaturas ganham um interruptor pra
avisar antes de cobrar.

- **D1** Tema escuro neutro: tokens `--cor-bg` / `--cor-superficie` / `--cor-superficie-2`
  / `--cor-borda` / `--cor-texto` / `--cor-texto-fraco` / `--cor-acento` / `--cor-sucesso`
  em `static/css/ui/tokens.css`; aurora e vidro colorido de fundo neutralizados.
- **D2** Humor "Ruim/Ok/Bom" com inicial maiúscula; LED de tarefa concluída mais sóbrio.
- **D3** Hiperfoco subiu pro topo, ao lado do comando de voz
  (`templates/secoes/topo/captura.html`); chat também subiu de posição.
- **D4** Checkbox marcado usa `--cor-sucesso`.
- **D5** "Visão do dia" recolhida por padrão, com reloginho mostrando o próximo horário.
- **D6** Clima já existia antes desta fase (`clima.py`, `/api/clima/hoje`, `#clima-chip`) -
  nada mudou aqui.
- **F1** `rotas/f8_banco.py`: `POST /api/bancos/sincronizar-nubank` (usa o item já
  conectado via `PLUGGY_ITEM_ID_NUBANK`, sem passar pelo Connect de novo) e
  `GET /api/gastos/unificados`, que junta gasto manual e gasto do Nubank com selo de
  origem.
- **F2** `GET /api/gastos/proximas-cobrancas` + bloco novo na aba Gastos
  (`#gastos-proximas-cobrancas-box`) com aviso de possível duplicidade (nome
  normalizado, ±R$0,50, ±5 dias) entre cobrança prevista e gasto já lançado.
- **F3** Interruptor "Avisar antes de cobrar" por assinatura (migração
  `202609251200`, desligado por padrão) + gatilho
  `assistente/gatilhos/f8_aviso_cobranca.py` (avisa 3/2/1 dias antes, mensagem
  "amanhã" no último dia, idempotente - não avisa duas vezes pro mesmo ciclo).
- **Dedup** A lista antiga de "próximas cobranças" dentro da seção Assinaturas
  (`#lista-proximas-cobrancas` / `#proximas-cobrancas-vazio`,
  `templates/secoes/gastos/assinaturas.html` + `criarItemProximaCobranca` em
  `static/js/secoes/gastos/assinaturas.js`) foi removida por duplicar o bloco novo da
  F2. Criar/editar assinatura e o interruptor da F3 continuam intactos.

Pendências pra próxima sessão:
- O item Pluggy `ce7aa441` está devolvendo `404 ITEM_NOT_FOUND` com as credenciais
  atuais - parece ter sido conectado em outra aplicação Pluggy. Precisa reconectar pelo
  botão "Conectar banco" do painel.
- Compra parcelada ainda não tem o interruptor de aviso (só assinatura tem).
- Aba Tarefas continua só listando pendentes.

Variável de ambiente nova: `PLUGGY_ITEM_ID_NUBANK` (`PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET`
já existiam) - só o nome documentado no `.env.example`, nunca o valor real.

## 2026-09-24 - Modo teste de IA

- Toggle "Modo teste de IA" no card **Custo de IA** (aba Painel): liga uma resposta de
  exemplo fixa no chat (`_resposta_exemplo_teste_ia`, `app.py`) no lugar de chamar a IA de
  verdade, pra conferir o formato visual (cards `tarefas_criadas`/`transacao`/`lembrete`) no
  celular pelo Render sem gastar chamada real. Config persistida (`configuracoes.modo_teste_ia`,
  `GET`/`POST /api/configuracoes/teste-ia`), então continua ligado entre sessões até desligar
  de novo.
- Bypass total logo no início de `_processar_mensagem_chat` (antes até da regra local) - com
  o modo ligado, nem `/api/chat`, nem o Telegram, nem `/api/atalho/capturar` chamam IA. Nada é
  gravado no banco nem no histórico do chat: os cards de exemplo usam `cards.novo_card`/
  `cards.envelope` direto (sem `card_*`, sem `conn.execute`), e a resposta não passa por
  `salvar_mensagem_chat` de propósito - senão a conversa falsa entraria no contexto que
  `_historico_chat_para_ia` manda pra próxima chamada REAL, contaminando o histórico de
  verdade com dado fake.

### Padrões descobertos
- **Listener de `change` num toggle que carrega/salva config assíncrona precisa ser anexado
  ANTES do primeiro `await`, não depois.** `loadTesteIA()` (`static/js/secoes/painel/custo-ia.js`)
  primeiro fazia `await apiFetch(GET)` e só then anexava o `addEventListener("change", ...)`.
  Um clique do usuário nesse intervalo (por menor que seja) muda o estado NATIVO do checkbox
  sem disparar nenhum listener (o evento já aconteceu antes dele existir) - o POST nunca sai,
  e o checkbox fica mentindo pro usuário até a próxima visita à aba. Só foi pego rodando o
  Playwright de verdade contra o servidor de verdade (não apareceria num teste unitário que
  mocka `apiFetch`); ver o mesmo padrão de guarda (`dataset.wired`) já usado em
  `avisos.js:wireFormSilencio`.

## 2026-09-24 - Fase 7 (v12): IA híbrida, visual novo, assinaturas e parcelas, assistente proativo

**Resumo para o Alex.** A Fase 7 rodou em 47 faixas paralelas (mais a Etapa 0), integradas na branch
`fase7/integracao`. Rollback: tag local `pre-fase-7` / commit `789171d`.
- A IA virou **híbrida**: cada função (chat, captura, nota fiscal...) tem um arquivo em
  `ia/config.d/` que diz qual modelo usar (Claude, GPT-6 Luna/Sol ou Gemini). Tudo nasce
  `ativo: false`, então nada muda até você aprovar o teste A/B (`scripts/ab_teste_ia.py`).
- **Teto único de R$ 40/mês** para toda chamada de IA, com gasto contado uma vez só e um card
  novo "Custo de IA" no Painel (por função, projeção, CSV).
- O chat ficou mais barato: resumo fixo do histórico + cache de prompt, e datas ("sexta que
  vem") calculadas em código, não pela IA. Contas de dinheiro também (`calculos.py`).
- **Assinaturas e compras parceladas**: "assinei Netflix 55 por mês", "comprei geladeira 3000
  em 12x no nubank" viram cadastro sem IA, com Desfazer e seção nova junto do cartão.
- **Assistente proativo**: a "Caixa" no topo da Hoje junta perguntas ("Pagou a luz?"),
  briefing da manhã e da noite, regras em português ("me avisa se gastar mais de 300 com
  mercado"), replanejar o dia, sinais do iPhone e propostas de memória. Tela nova
  "Assistente" com liga/desliga de cada aviso e horário de silêncio.
- **Telegram** por webhook (texto, link, voz, foto de nota), **widget do iPhone** (Scriptable,
  Widgy, Glimpse, Atalhos e base WidgetKit) e "tomei um copo de água" sem IA.
- **Visual novo** sem trocar cor, fonte nem animação: cards com profundidade, botão
  "adicionar" grande que abre um painel de baixo (bottom sheet), seções recolhíveis, toque
  de 44px e foco visível em todo o app.
- A Construtora no painel mostra só gastos, entradas e o tempo até a próxima conta.
- Pendências que dependem de você estão em `TODO.md` ("Pendências abertas pós-Fase 7").

### IA (A1-A15)
- **Núcleo** (A1, `ia/core.py`): `chamar_ia(funcao, ...)` lê `ia/config.d/<funcao>.json`
  (formato em `ia/config.d/README.md`), usa `alvo` se `ativo` senão `modelo_atual`, tenta os
  `fallback` em ordem, 1 retry em erro de rede, valida JSON contra schema (raiz sempre objeto)
  e consulta o teto antes. `registrar_adapter()` para dublês. Exceções `FalhaChamadaIA`
  (`TetoEstourado`, `ErroProvedor`, `RespostaInvalida`, herdam de `ValueError`; C1).
- **Adapters** `ia/adapters/{anthropic,openai,gemini}.py` (A2/A3/A15): erro de rede sobe como
  exceção (retry no núcleo), erro de API vira `Resposta(ok=False)`. Anthropic: `cache_control`
  só no `contexto_fixo`; esforço vazio ou Haiku não manda effort/thinking. OpenAI:
  `reasoning_effort`, `service_tier="flex"` (`ia/lote.py`), converte imagem e PDF
  (`file_data` data URI, C1). Gemini: SDK `google-genai` com import tardio.
- **Medição e teto** (A4): tabela `uso_ia` (só metadados), `ia/medicao.py`, `ia/teto.py`
  (`teto_permite`, `nivel_alerta` 80%/100%), preços em `ia/precos.json` lidos só por
  `ia/precos.py` (fonte única; câmbio fixo R$ 5,50). Gasto do mês com fonte única
  `ia.medicao.gasto_mes_atual` (`uso_ia` + `api_usage` legado só antes da 1ª linha de
  `uso_ia` do mês; C1).
- **Histórico do chat** (A5, `ia/historico.py`): resumo fixo (`chat_resumo_historico`,
  reconstruído acima de ~6.000 tokens ou na virada do dia) + últimas mensagens na íntegra
  (máx. 20, sem buraco, C1).
- **Chat** (A6, `ia/funcoes/chat.py`): contexto do dia fora do system, 4 breakpoints de cache,
  limites de saída (chat 500 → refaz com 1500), `resolver_data_relativa`/`resolver_quando_data`.
  Opções novas entram por `claude_client.opcoes_chat(...)` (contextvar) para não quebrar os
  40+ dublês de 4 argumentos. Chat com tools continua no SDK Anthropic direto.
- **Migrações** A7 (captura/intent/resumo/essencial + `resolver_data`), A8 (planejamento:
  mala, link truncado em 12.000 caracteres, quebra de tarefa, plano do dia) e A9 (nota fiscal
  e cotação PDF com `confianca` < 0,7 refazendo 1x) passaram a usar `chamar_ia`, com mesma
  assinatura. O teto passou a valer nessas rotas.
- **A10**: `construtora_cliente.py` (cache 60s, timeout 5s, `CONSTRUTORA_API_MOCK=1`; só
  `gastos_do_mes`, `entradas_do_mes`, `proxima_conta`) e regra local `a10_agua.py`.
- **A11** A/B (`scripts/ab_teste_ia.py`, `--dry-run`, `docs/ab-teste.md`); **A12** suíte
  paralela `scripts/suite.sh` (`TESTES_JOBS`, `TESTES_TIMEOUT`), `tests/conftest.py` e
  `docs/testes.md`; **A13** `calculos.py` (Decimal, `ROUND_HALF_EVEN`, `docs/calculos.md`);
  **A14** `ia/roteador_chat.py` (local/luna/padrão, flag `ia/roteador_chat.json` desligada).

### Finanças, Telegram e widgets (N1-N3)
- **N1** assinaturas e compras parceladas: migração `202609241300_n1_assinaturas.sql`,
  `financas_recorrentes.py`, regra local `n1_financas.py`, rotas `rotas/n1_financas.py`
  (`/api/financas/*`, `POST /api/financas/desfazer/<token>`), contrato em
  `docs/contrato-assinaturas.md`. C1: valida antes do INSERT e lê tolerando linha ruim;
  cards em `cards.py` (valor escondido no modo visitante) e Desfazer geral também funciona.
- **N2** `telegram_captura.py` + `POST /api/telegram/webhook` (segredo, um chat permitido,
  idempotência por `update_id`, voz via Groq). `TELEGRAM_MODO` e `TELEGRAM_BOT_TOKEN_CAPTURA`
  (C1) garantem que webhook e polling nunca rodam juntos no mesmo bot
  (`docs/telegram-captura.md` §7).
- **N3** `GET /api/widget` e `GET /widget` (`PAINEL_WIDGET_TOKEN`, sem R$ por padrão),
  `scriptable/scriptable-widget.js` (4 tamanhos, cache do último JSON bom), docs
  `docs/widget-*.md` (Widgy, API Widget, Glimpse, Atalhos, comparativo) e
  `native/widgetkit/` (Swift não compilado, precisa de Mac).

### Assistente proativo (P1a-P9)
- **Caixa** (P1a/P1b): `assistente/caixa.py`, tabela `assistente_itens` (dedupe por
  `chave_unica`), `POST /api/tick` (`PAINEL_TICK_TOKEN`, cron externo a cada 5 min,
  `docs/tick.md`), `GET /api/assistente/saude`. A `origem` é `<arquivo do gatilho>:<resto>`;
  a Caixa acha o `ao_resolver` pelo prefixo. Faixa compacta no topo da Hoje, selo na barra e
  aba "Assistente" (Caixa, Regras, Avisos).
- **Gatilhos** em `assistente/gatilhos/`: P2 perguntas (conta, reunião, tarefa vencida,
  lembrete, espera), P3 briefing manhã/noite (07:30/21:00, `rotas/p3_briefing.py`), P4 regras
  em português (`assistente/regras.py`, tabela `p4_regras`, IA só se o parser local falhar),
  P5 replanejar o dia (sugestão das 14h com flag desligada), P7 `POST /api/sinal`
  (`PAINEL_SINAL_TOKEN`, `docs/atalhos-sinais.md`), P9 memória viva (domingo à noite, números
  em código e IA só redige).
- **Central de avisos** (P8, `assistente/avisos.py`): ~50 tipos, canal push/caixa/ambos,
  silêncio 22h-7h. C1: a Caixa respeita tipo desligado, `TIPO_POR_ORIGEM` mapeia a origem
  (faixa P nova precisa cadastrar lá) e o fechamento antigo das 21h fica calado com a P3.
- Vida amorosa/relacionamento nunca vira pergunta, regra nem memória (filtro por palavra).

### Visual (V0a-V6)
- **Componentes** (V0a-V0d): `static/css/ui/tokens.css` (forma, espaço, elevação, `--anel-foco`,
  `--toque-min`) e o guia `docs/MASTER.md`; `ui/componentes/{botao,card,chip,campo,
  lista-item,secao,bottom-sheet,navegacao}.css`; `static/js/ui/secao-recolhivel.js`
  (estado em `localStorage` por `data-secao-id`) e `static/js/ui/bottom-sheet.js`
  (`abrirBottomSheet`/`fecharBottomSheet`, foco preso, ESC, `data-fecha-ao-enviar` +
  `bottomsheet:sucesso`). Autor escreve só `<div class="bottom-sheet" hidden>`.
- **Telas**: V1 Hoje (brain dump num toque, botões do topo), V2 Painel (card "Custo de IA",
  `rotas/v2_custo_ia.py`, memória recolhível), V3 Hábitos/Projetos/Agenda/Tarefas, V4 demais
  seções da Vida, V5 Viagens/Lugares/Cotações/Aviação, V6 Gastos/Bancos/Construtora
  (seção "Assinaturas e parcelas", `id="assinaturas-financas-box"`).

### Polimento (C1, C2, C3a-c)
- **C1 backend**: chat com A5 + `medir_uso`, teto único, mensagens de erro certas (402 teto,
  502 provedor), construtora só pelo cliente novo (nunca lucro/margem/VGV),
  `calculos.percentual_meta_exibicao` (1 casa), fuzz de 184 cenários (`scripts/ralph-c1-backend/
  fuzz.py`, 15 erros 500 corrigidos), conftest com SDKs apontando para `127.0.0.1:9`.
- **C2 visual** (V0-V3, P1b): abas com `#tab-x:not([hidden])`, componentes com guarda
  `[hidden]`, sheet vai para o `<body>` enquanto aberto, adicionar em sheet em Datas,
  Medicamentos, Esperando e Diário, 44px em tudo, checkbox do app, Avisos recolhíveis.
- **C3a Vida, C3b Viagens/Aviação, C3c Finanças**: sheets só no componente (sem CSS
  provisório), bloco interno em vez de card dentro de card, nada de botão nativo, números em
  mono, validação pt-BR de valor (`type=text inputmode=decimal`), Leaflet com 180px, listas
  tolerantes a resposta fora do formato. Fuzz de UI com 56, 71 e 98 cenários.

### Integração (M1)
- `style.css`: foco global com `var(--anel-foco)`, `[hidden] { display: none !important }`,
  animação da aba com fill `backwards`, comentário que engolia `.garantia-chip` corrigido.
- Desfazer da N1 pela rota própria (`Cards.urlDesfazer`), reabertura rápida de sheet sem timer
  velho, placeholder a 4,82:1 (`.campo` em `--superficie-1`), seção recolhida com `inert`.
- Consolidação final (`fase7/m1-final`): este CHANGELOG (os `changelog.d/*.md` foram
  apagados, ver `changelog.d/README.md`), "Aprendizados da Fase 7" no `AGENTS.md`, `TODO.md`,
  `STATUS.md`, `.env.example` (`TELEGRAM_MODO`, `TELEGRAM_BOT_TOKEN_CAPTURA`), service
  worker v15, `docs/MASTER.md` (campo em `--superficie-1`), "Seu progresso" com percentual
  em pt-BR e `docs/tick.md` com `<TOKEN>` (gitleaks zerado).

## 2026-09-24 (Fase 7, Etapa 0 / X1) - extracao estrutural do backend

Mudanca estrutural pura (zero mudanca de comportamento) pra ~20 faixas paralelas nao
editarem o mesmo arquivo. Branch `fase7/e0-backend`.
- `claude_client.py` dividido em `ia/legado.py` + `ia/funcoes/{chat,captura,planejamento,
  visao}.py`; `claude_client.py` vira fachada que reexporta tudo (codigo movido sem
  alteracao, AST identico).
- `rotas/`: Blueprints com carga automatica (`rotas.registrar_todas(app)` no fim do
  `app.py`), `rotas._base.app_modulo()`, e `ROTAS_COM_TOKEN`/`PREFIXOS_COM_TOKEN` por
  modulo liberados no `_verificar_autenticacao` (a rota checa o proprio token).
- `migracoes/*.sql` aplicadas pelo `db.init_db()` (uma vez so, tabela
  `migracoes_aplicadas`, uma transacao por arquivo, `db.ErroMigracao` com o nome).
- `classificador_local/` (regras em `regras/*.py`) como primeira camada de
  `_classificar_intent`, da captura e do chat - com `regras/` vazio nada muda.
- `assistente/gatilhos/` com `executar_todos(conn, agora)` (sem endpoint ainda).
- Testes: `tests/test_fase7_infra_{rotas,migracoes,classificador,gatilhos}.py`.

## 2026-09-24 (Fase 7, X2) - frontend dividido por secao (so estrutura)

Mudanca estrutural pura pra ~10 faixas de visual rodarem em paralelo sem editar o mesmo
arquivo. Zero mudanca de comportamento/visual: HTML renderizado de `/` identico (fora os
acrescimos vazios abaixo), mesmos globais JS, mesmo DOM depois de abrir todas as abas,
screenshots Hoje/Vida iguais. Branch `fase7/e0-frontend`. Mapa: `docs/agentes/mapa-frontend.md`.
- `templates/index.html` so faz `{% include %}`: `head.html`, `secoes/topo/`,
  `abas/<aba>.html` -> `secoes/<aba>/<secao>.html` (uma por h2), `navegacao.html`, `scripts.html`.
- `app.js`/`vida.js` -> `static/js/nucleo/*.js` (compartilhado + `init.js` com a carga inicial)
  e `static/js/secoes/<aba>/<secao>.js` (mesmos nomes do HTML). Ordem de carga conferida por
  analise estatica e no navegador.
- `static/css/fase7.css` (depois do `style.css`) importa camadas vazias: `ui/tokens.css`,
  `ui/componentes/*.css`, `secoes/<aba>.css`, `secoes/<aba>/<secao>.css`.
- Vazios pras faixas: aba `assistente` (escondida, sem botao), `#caixa-assistente` no topo da
  Hoje, `secoes/assistente/{caixa,regras,avisos}` (HTML/JS/CSS), `ui/bottom-sheet.js`,
  `ui/secao-recolhivel.js`.
- Service worker v14 com todos os arquivos novos no precache; teste
  `tests/test_fase7_estrutura_frontend.py` guarda isso.

## 2026-09-23 (Fase 6) - correcoes da revisao independente (codigo + seguranca)

Revisao independente da Fase 6 (seguranca + codigo) achou 14 pontos; todos
reproduzidos antes e corrigidos com teste de regressao que falhava antes
(`tests/test_fase6_revisao_visitante.py`, `tests/test_fase6_revisao_seguranca.py`,
`tests/js/cards.test.js`) ou verificacao headless (XSS, barra do chat).
Branch `fase6/fix-revisao`.

### ALTO
- **1. Visitante conseguia Desfazer**: `POST /api/desfazer/<token>` -> 403 no
  modo visitante, e `cards.mascarar_cards` tira a action `desfazer` de todo
  card (resposta do chat e `/api/chat/historico`) - o token nem sai mais.
- **2. XSS armazenado no mapa**: `bindPopup(l.nome)` (Leaflet trata string
  como HTML) -> `bindPopup(<span>)` com `textContent`. Confirmado no headless:
  antes `window.__xss` disparava, depois o nome aparece escapado.
- **3. Saude vazando no visitante**: `saude_dia` (agua/passos/sono/treino) e
  `saude_treino` (sessoes) entraram em `cards.CAMPOS_SENSIVEIS` - card sai com
  `oculto: true`, renderizador mostra "Dados de saude ocultos no modo visitante."

### MEDIO
- **4. Teto mensal de IA ignorado**: `/api/chat`, brain dump "assistente" e
  Telegram (todos via `_processar_mensagem_chat`) checam
  `resumo_custo_api(conn)["teto_estourado"]` dentro do `_TETO_IA_LOCK` antes da
  IA -> 402 com `TETO_IA_MSG` (consulta local sem IA continua funcionando).
  Texto do chat/brain dump/Telegram limitado a `TAMANHO_MAX_TEXTO_CHAT = 4000`
  caracteres (400 amigavel; `maxlength` no input do chat).
  `MAX_CONTENT_LENGTH = 20MB` + handler 413 em JSON - cobre a foto de nota
  fiscal (10MB -> ~13,4MB em base64) e o PDF de cotacao (15MB multipart),
  testados.
- **5. Envenenamento do banco de padroes**: `/api/intent/corrigir` -> 403 no
  visitante; no chat, frase com verbo de acao/assunto fora do banco
  (`aprendizado.exige_ia`, mesmos `_VERBO_ACAO`/`_FORA_DO_BANCO`) nunca vira
  consulta local, nem por padrao aprendido ("Gastei 80 no mercado" com padrao
  consultar/habitos gravado agora vai pra IA e registra o gasto).
- **6. Memorias gravaveis no visitante**: POST/PUT/DELETE `/api/memorias` -> 403.
- **7. Lockout de login atras do proxy**: `ProxyFix(x_for=1, x_proto=1)` so
  com `PAINEL_ATRAS_DE_PROXY=1` (nova variavel; `render.yaml` = "1",
  `.env.example` comentada, `deploy/DEPLOY.md` manda ligar na VPS com Caddy).
  Sem a variavel, `X-Forwarded-For` e ignorado (nao da pra fugir do bloqueio).
- **8. Nominatim repetindo em falha**: rede/429/5xx grava `geocode_status =
  "erro"` + `lugares.geocode_tentar_depois` (6h, `app.GEOCODE_ESPERA_APOS_ERRO`);
  4xx (400/403/404) grava `"recusado"` (definitivo - nao existe rota de
  renomear lugar). GET faz no maximo 1 geocode e so de lugar vencido
  (`db.proximo_lugar_para_geocodificar`); timeout 8s -> 4s.

### BAIXO
- **9. Leaflet sem SRI**: `integrity` sha256 + `crossOrigin="anonymous"` no JS
  e CSS 1.9.4 - hashes calculados sobre os arquivos baixados do jsdelivr,
  iguais aos do unpkg, e carregados de verdade no headless com SRI ligado.
- **10. AviationStack**: erro fica 30 min em cache (`voo_status.CACHE_TTL_ERRO`)
  sem apagar o ultimo dado bom (continua aparecendo "dado de HH:MM (rede
  falhou agora)"); tela mostra "Confirme no app da companhia." (plano gratis e
  HTTP - so exibicao).
- **11. `/configurar-pin` aberto no Render**: com `RENDER` definido e sem PIN
  (nem `PAINEL_PIN_INICIAL`), o boot levanta `RuntimeError` com mensagem clara
  (`_exigir_pin_em_hospedagem_publica`); `deploy/RENDER.md` explica o erro.
- **12. Agenda/brain dump no visitante**: POST/DELETE `/api/agenda/eventos` ->
  403, tool `agendar_evento` do chat devolve erro no visitante,
  `POST /api/brain-dump/<id>/converter` -> 403 (item continua pendente).
  Habitos/projetos continuam liberados (decisao documentada da Fase 6).

### Codigo/visual
- **13. Sobreposicao na aba Hoje**: `.chat-form` sticky ganhou fundo de vidro
  quase opaco (mesmo material da tabbar) + `bottom` 6rem -> 5.5rem - o
  "Como voce ta hoje?" passa por tras da barra em vez de aparecer entre o
  input e os botoes (conferido no headless 390x844, sem `full_page`).
- **14. CSS duplicado**: `.card-contrato .meta-progresso` num bloco so.

### Nao corrigido (decisao do orquestrador)
- Valor em R$ no push de limite do cartao - texto pedido pelo Alex.

### Testes antigos ajustados (mudanca de comportamento intencional)
- `test_fase6_e4_chat.test_brain_dump_visitante_nao_vaza_valor` ->
  `test_brain_dump_visitante_nao_converte` (agora 403).
- `test_fase6_f3_lugares_mapa`: erro de rede grava `"erro"` temporario em vez
  de deixar `NULL`.

Service worker -> **v13**.

## 2026-09-23 (Fase 6 F1) - polimento da aba Vida

Faixa 1 do Grupo F da Fase 6: polimento visual/interativo de 5 secoes da aba Vida
(e das duas que fisicamente moram dentro do HTML da aba Painel - ver nota abaixo),
sem mudar nenhuma logica de negocio nem endpoint.

- **US-F1 (Saude hoje - botao de agua)**: botao "+1 copo de agua" maior, com cor
  propria (`--cor-financeiro`) e feedback forte ao toque - glow no botao, "+1"
  flutuante que sobe e some, e o contador agora cresce visivelmente de verdade
  (existia uma chamada a `pulsarSucesso` sem nenhuma regra CSS por tras dela -
  achado real, corrigido).
- **US-F2 (Peso e medidas)**: tipo por `<select>` com os mais comuns (peso,
  cintura, quadril, peito, biceps, coxa, % de gordura, "outro..." com texto
  livre), valor por stepper (+/-) e unidade tambem por seletor (com "outra...").
  Grafico de evolucao novo (SVG, reusa `charts.js`) do tipo mais recente com 2+
  pontos. Dado antigo (tipo/unidade digitados a mao antes desta historia)
  continua aparecendo sem nenhuma migracao.
- **US-F3 (Pessoas)**: avatar com iniciais, chip de status ("em dia"/"atrasada
  Xd"/"novo(a)"), barra visual de "quanto falta pro prazo de contato estourar"
  e um novo toggle "ver conversas" (reusa `GET /api/conversas`, que ja existia
  sem lugar nenhum na UI). "Falei hoje" continua em 1 toque.
- **US-F4 (Treino - ficha guiada)**: "montar ficha" deixa de ser um textarea
  livre e vira adicionar exercicio um a um (nome/series/reps/carga), com lista
  pendente editavel antes de salvar. Formato interno novo (`nome|series|reps|carga`
  por linha) cabe no MESMO campo TEXT que ja existia - fichas antigas (texto
  puro) continuam exibidas exatamente como antes, sem perda.
- **US-F5 (Garantia de produtos)**: chip de status por urgencia e barra de %
  do prazo ja decorrido; lista reordenada por proximidade do vencimento
  (inclusive ja vencido) em vez da ordem de compra.
- **Achado de arquitetura (documentado em `AGENTS.md`)**: o HTML de "Saude hoje"
  e "Peso e medidas" mora fisicamente dentro de `<section id="tab-painel">`,
  nao de `tab-vida`, apesar de ser conteudo conceitual de Vida - relevante pra
  quem trabalhar em paralelo nas duas abas (risco de merge no mesmo arquivo).
- Testes: nenhum teste Python/JS novo foi necessario (nenhuma logica de negocio
  nova - todas as 5 historias reusam dado que os endpoints existentes ja
  devolviam). Verificacao real foi Playwright headless (390px) por historia,
  com banco semeado (dado "antigo" incluso pra confirmar retrocompatibilidade
  em F2 e F4). Suite completa (`unittest` + `node --test`) rodada apos cada
  commit: 1645 testes Python (6 falhas conhecidas de horario de voo/agrupamento,
  pre-existentes, sem regressao) + 86/86 JS.

## 2026-09-23 (Fase 6 F2) - polimento do Painel e prazo em Tarefas

Faixa 2 do Grupo F da Fase 6: polimento visual das secoes "Devo sair ate que horas",
Datas importantes/Medicamentos, Esperando resposta/Diario de decisao e Mensagem dificil/Vale
a pena (todas na aba Painel/Vida) + prazo opcional em Tarefas. So apresentacao (HTML/CSS/JS) -
nenhuma regra financeira/calculo mudou; a unica rota nova e o formulario direto de tarefa
(US-F10), que reusa o insert minimo ja existente (`criar_tarefa_de_brain_dump`, Fase 5 US-C6)
em vez de duplicar logica.

- **US-F6 (Devo sair ate que horas)**: origem/destino eram 2 `<input>` soltos sem nada
  indicando que sao os 2 pontos de uma mesma rota - viraram uma trilha vertical + 2 pontos
  (mesma linguagem visual da `.linha-do-tempo` da agenda), com um rotulo "Chegar ate" acima
  do campo de data/hora (`--form-cor` tingindo o foco na cor da secao). So `templates/
  index.html`/`static/css/style.css` - `#viagem-form` continua com os mesmos ids, JS (`app.js`)
  intocado.
- **US-F7 (Datas importantes / Medicamentos)**: `#lembrete-data` virou `<input type="date">`
  nativo (seletor em vez de texto livre "dd/mm/aaaa" + mascara - `#voo-data`, aviacao/F3,
  continua com a mascara antiga, nao mudou). A lista de lembretes agora ordena por
  `dias_restantes` (o backend ja calculava, so nao ordenava por ele) e o selo de contagem
  virou pill de 2 niveis: cor da secao (`--cor-bancos`) ate 7 dias, `--danger` so quando ja
  venceu de verdade. Medicamentos ganharam um selo "em Xh/foi ha Xh" (proxima dose,
  calculo 100% client-side a partir do relogio do navegador - nenhum aviso/push mudou).
- **US-F8 (Esperando resposta / Diario de decisao)**: a lista de esperas trocou de
  `/api/esperas` pra `/api/esperas/prioridade` - MESMO endpoint que ja existia desde a Fase 5
  (US-C5) pro calculo de prioridade, so que nenhuma tela usava; agora mostra "esperando ha N
  dia(s)" (pill, critico depois de 5 dias - o mesmo limiar do push) e uma estrela pra marcar/
  desmarcar `importante` (`/api/esperas/<id>/importante`, tambem ja existia sem UI). Diario de
  decisao ganhou selo de status (RESOLVIDA/AGUARDANDO) e a data da decisao, que antes nao
  aparecia. Modo visitante continua ocultando o diario e o Vale a pena - protecao no
  SERVIDOR (`_modo_visitante_ativo()`), reverificado manualmente (403 nas 2 rotas com
  visitante ligado).
- **US-F9 (Mensagem dificil / Vale a pena)**: as 2 versoes da mensagem dificil (Direta/Mais
  gentil) viraram cartoes com selo de cor propria e botao "Copiar" com icone (antes era link
  de texto solto). Vale a pena: a inclinacao (`vale`/`nao_vale`/`depende`, contrato ja pronto
  desde a faixa E1 - `claude_client.DECISAO_PROMPT`) virou um banner de veredito no TOPO do
  card (semaforo verde/vermelho/ambar), com pros/contras em colunas lado a lado em vez de 2
  listas empilhadas - nenhum prompt/contrato de IA mudou, so a apresentacao.
- **US-F10 (Tarefas: prazo opcional)**: `POST /api/tasks` novo - titulo + `due_date`
  OPCIONAL, sem passar pela IA (reusa `criar_tarefa_de_brain_dump`). Formulario direto na aba
  Tarefas (antes so dava pra criar tarefa via chat/captura). Corrigido tambem um gap real:
  uma tarefa com `due_date` mas sem `due_at`/`hora` nao mostrava NENHUM prazo na lista
  (`criarItemTarefa` so olhava `due_at`/`hora`) - agora cai num rotulo curto
  (hoje/amanha/dd/mm) e ganha a tag "atrasada" quando ja passou. O chat ja suportava prazo
  opcional desde antes (`quando`/`quando_data`, testes existentes) - nada mudou la.

Testes: `tests/test_fase6_f2_painel.py` (9 casos novos, so US-F10 - as outras 4 historias
foram so front-end, verificadas com Playwright headless, antes/depois lado a lado). Suite
completa (`unittest discover`) sem regressao alem das falhas pre-existentes conhecidas
(horario de voo real, `test_ligado_segura_ate_a_janela_passar_e_agrupa` - 6 no total, todas
ja documentadas neste AGENTS.md); `node --test tests/js/*.test.js` 86/86.

## 2026-09-23 (Fase 6 F3) - Viagens (linha do tempo + status de voo), mapa, Cotacoes e Aviacao

Faixa extra do Grupo F da Fase 6 (`grupo-f3-extra.json`, US-F11 a US-F15) - todas passaram,
nenhuma ficou blocked. Trabalho isolado em worktree separado (`fase6/f3-extra`), enquanto F1
(aba Vida) e F2 (Painel/Tarefas) rodaram em paralelo nos seus proprios worktrees.

- **US-F11 (Viagens: linha do tempo de planejamento, regra pratica)**: marcos genericos de
  prazo a partir da data de ida (`vida.marcos_planejamento_viagem` - pura conta de
  calendario, nunca IA/rede), nacional (3 marcos: passagem/hospedagem/check-in) vs
  internacional (5 marcos, tambem documento/visto e seguro viagem) - coluna nova
  `viagens.internacional`. Fonte/raciocinio dos numeros (mercado brasileiro de viagem,
  pesquisado via WebSearch) documentado em `tasks/fase6/progress-f3.txt`. Reaproveita o card
  `projeto_viagem` (US-E13) via `GET /api/viagens/<id>/timeline-card` (`cards.card_viagem`,
  sem duplicar calculo); a linha do tempo em si reusa a classe `.linha-do-tempo` ja existente
  (agenda/visao do dia, US-E5) numa versao "mini", com marcador HOJE proprio (pill) alem da
  barra do card. Aviso "regra pratica, nao preco em tempo real" sempre visivel na tela.
- **US-F12 (Viagens: status do voo por numero)**: numero do voo comprado (`viagens.numero_voo`)
  + status em tempo real (atraso/portao/terminal) via **AviationStack** (`voo_status.py`,
  novo) - a UNICA das 4 APIs pesquisadas (AviationStack, AeroDataBox/RapidAPI, FlightAware
  AeroAPI, Amadeus Self-Service) sem exigir cartao de credito no cadastro gratuito (100
  req/mes, so HTTP nao HTTPS - limitacao documentada). Amadeus Self-Service morreu de vez em
  2026-07-17. Cache de 3h (`voo_status_cache`) pra caber no limite gratuito. Chave opcional
  via `AVIATIONSTACK_API_KEY` (`.env.example`) - sem ela, card mostra "status em tempo real:
  configurar chave". Comparacao completa em `TODO.md` ("API de voo (Fase 6)"). Testes sempre
  com a API mockada.
- **US-F13 (Lugares que Gostei: mapa via OpenStreetMap)**: geocodificacao server-side via
  **Nominatim** (`geocode_nominatim.py`, novo) respeitando a politica de uso (maximo 1 req/s,
  User-Agent proprio sem dado pessoal, cache permanente em `lugares.lat/lng/geocode_status` -
  nunca repete a mesma consulta). Mapa com **Leaflet 1.9.4** fixado via `cdn.jsdelivr.net`,
  carregado sob demanda (so ao clicar "ver no mapa"), tiles do OpenStreetMap publico. Sem CSP
  no app (nada a liberar) e service worker sem mudar de versao. Achado real: o CDN falha
  especificamente dentro do Chromium do Playwright deste sandbox (mesmo o backend alcancando
  via `requests`/`curl`) - fallback textual confirmado funcionando, nome do lugar sempre
  aparece independente de rede.
- **US-F14 (Cotacoes: grafico de comparacao)**: SVG inline (barras horizontais, fornecedor
  mais barato destacado) reaproveitando o padrao visual `.card-grafico` ja usado em
  `saude_treino`. Gap real corrigido: `/api/cotacoes` nunca tinha ganhado a checagem de modo
  visitante que todo outro endpoint financeiro ja tem desde a US-C20 - agora segue o mesmo
  padrao (`GET` lista/detalhe escondidos, escrita bloqueada com 403).
- **US-F15 (Aviacao: METAR e voo mais visuais)**: `metar.categoria_voo` classifica teto/
  visibilidade nos limiares PADRAO FAA/AIM (os mesmos que aviationweather.gov publica em
  todo METAR) - chip colorido com as cores padrao de carta aeronautica (verde/azul/vermelho/
  magenta), testado com METARs reais cobrindo CAVOK, vento variavel, calmaria e BKN/OVC nos
  limites exatos de cada faixa. Seta de vento SVG rotacionada pelo grau decodificado.
  "Proximos voos" ganhou icone de status (agendado/realizado) - so visual, logica intocada em
  `voos.py`. `resumo_falado()` continua nunca mencionando categoria.
- **Achados de processo**: gap de especificidade CSS (`[hidden]` perdendo pra uma classe com
  `display` != `none` declarada depois) achado e corrigido na verificacao headless da US-F13;
  pegadinha de teste real (`GET` com efeito colateral de rede escapando do escopo de um mock)
  achada rodando a suite completa antes de fechar a US-F14, corrigida - ambos documentados em
  `AGENTS.md`.

Arquivos novos: `voo_status.py`, `geocode_nominatim.py`,
`tests/test_fase6_f3_viagens.py`, `tests/test_fase6_f3_lugares_mapa.py`,
`tests/test_fase6_f3_cotacoes_grafico.py`. Historico completo, decisoes e o que NAO foi
confirmado em `tasks/fase6/progress-f3.txt`.

## 2026-09-23 (Fase 6 E4) - chat produzindo cards dos modulos novos

Faixa 4 do Grupo E da Fase 6: a aba Hoje (chat) passa a devolver CARD pros modulos da E2
(Habitos, Projetos, Viagens, agenda iCloud, saude) e resolve consulta conhecida sem gastar API.

- **US-E7 (consulta -> card, classificador local)**: banco "pergunta -> onde buscar"
  (`aprendizado.consulta_conhecida`) virou a segunda camada local de `_classificar_intent`
  (depois do padrao aprendido, antes da IA). O chat chama `_classificar_intent(...,
  somente_local=True)` antes do tool-use e, se resolveu, executa as MESMAS tools
  (`_plano_local_chat`) - "me mostra o projeto da viagem e a meta" (projeto_viagem + meta),
  "como foram meus treinos nos ultimos 7 dias?" (saude_treino), "tomei um copo de agua"
  (+1 copo, card `saude_dia` novo com Desfazer), "como encaixo meu treino hoje?" (sugestao com
  horario real a partir de agora + memoria `sua_rotina` na caixa "Com a sua rotina em
  mente"), "como estao meus habitos?" (habito). O banco cresce sozinho: resposta da IA feita
  so com ferramentas de consulta grava o padrao (3 repeticoes = local). Tools novas
  `consultar_projeto/meta/treinos/habitos/saude_dia`; tools da E2 agora devolvem `_efeito`
  -> cards habito/projeto_viagem/agenda/saude_treino com Desfazer por entidade (habito,
  marcacao do dia, projeto, etapa, etapa concluida, viagem, copo de agua, treino; evento so
  com uid criado pelo painel). Adaptadores `cards.semana_seg_dom` (seg->dom) e
  `cards.projeto_para_card` (`posicao_hoje` 0-100 -> `hoje_fracao` 0..1); composicao do
  projeto extraida pra `vida.projeto_detalhado` (fonte unica da rota e do card). Card de
  consulta sem Desfazer, com `data.consulta` (aditivo) e fora do `resumo_final`.
- **US-E6 (brain dump -> cards)**: `/api/brain-dump/<id>/converter` ganhou `tipo:
  "assistente"` (botao "Processar" no item) que manda o despejo inteiro pro MESMO
  `_processar_mensagem_chat` - viagem, gastos, salario, habitos, lembrete e reuniao
  misturados viram um card cada (8+) + `resumo_final` com os modulos tocados, cada um com
  Desfazer independente, renderizados na aba Hoje. tarefa/gasto/nota tambem devolvem o
  contrato de cards. Item reservado antes da IA e devolvido se ela falhar. `max_tokens` do
  chat 600 -> 1500 (8-9 tool_use numa rodada).
- Docs: `docs/CARDS.md` (type `saude_dia`, campo `consulta`, tabela "quem gera cada card",
  entidades de Desfazer novas), `docs/INTENT.md` (banco local + formato dos `parametros`).
- Testes: `tests/test_fase6_e4_chat.py` (43, IA e iCloud mockados, fuzz do banco local),
  `tests/js/cards.test.js` (+6). Headless 390px conferido (consultas, agua + desfazer,
  sugestao, habitos, brain dump com 9 cards, link pra aba Vida com destaque).

## 2026-09-23 (Fase 6 E5) - proatividade unificada e visao do dia

Faixa 5 do Grupo E da Fase 6 (depois de E1+E2+E3 integrados): unifica a proatividade num so
pipeline e estende a linha do tempo que ja existia numa visao do dia de verdade.

- **US-E8 (Proatividade unificada)**: 6 avisos novos em `notificacoes.py`, todos entrando na
  MESMA lista de `app.verificar_e_notificar()` e passando pelo pipeline unico ja existente
  (silencioso -> hiperfoco -> modo viagem -> agrupamento -> `_despachar()`, dedup em
  `notificacoes_enviadas`) - nenhum caminho paralelo de envio. `habitos_passaram_batido`
  (habito com horario, 1h sem marcar - reusa `vida.habito_passou_batido`, ja preparada na
  US-E12); `tarefas_horario_passou` (30min apos a hora, ainda pendente, complementa
  `tarefas_com_horario_chegando`); `cartoes_perto_ou_estourados` (>=90%/>=100% do limite
  manual, US-E15, reusa `vida.fracao_limite_cartao`); `renda_perto_de_acabar` (>=70%/>=100%
  da renda do mes ja gasta); `projetos_juntando_poeira` (21+ dias sem toque, US-E13, reusa
  `vida.calcular_projeto`); `mes_seguinte_apertado` (custos fixos recorrentes vs media de
  renda dos ultimos 3 meses, checado so nos ultimos 3 dias do mes). Revisao de tom: os avisos
  ja existentes no sistema ja eram diretos/sem diminutivo/sem coach - nenhuma migracao de
  texto foi necessaria alem dos 6 novos.
- **US-E9 (Visao do dia)**: secao nova em `#tab-hoje` (aba Hoje, abaixo do chat) - seletor
  Dia/Semana/Mes, linha de status, card "Em foco agora" (proxima tarefa/habito com horario,
  "em N min", botao "Comecar foco" ligado ao hiperfoco ja existente via `POST /api/hiperfoco`,
  check de concluir), "Hoje · N itens · M concluidas", e a linha do tempo do dia. `GET
  /api/visao-dia/hoje` junta agenda do iCloud + eventos do calendario "Painel" + tarefas (tudo
  via `_eventos_de_hoje_com_seguranca`, ja existente) com habitos com horario (`_habitos_do_dia_com_horario`,
  novo). `GET /api/visao-dia/periodo?tipo=semana|mes` agrega tarefas+habitos+eventos criados
  por dia (agenda do iCloud fica fora da agregacao de periodo - custo de N chamadas de rede
  instaveis, ver decisao em `tasks/fase6/progress-e5.txt`). A linha do tempo REUSA a marcacao
  visual que a agenda de hoje (aba Painel) ja tinha - virou a classe compartilhada
  `.linha-do-tempo` (`style.css`) + a funcao JS compartilhada `criarItemLinhaDoTempo`
  (`app.js`, extraida de `loadAgenda()`) - nao ha duas implementacoes de linha do tempo no
  projeto.

Testes: `tests/test_fase6_e8_proatividade.py` (29 casos), `tests/test_fase6_e9_visao_dia.py`
(28 casos), `tests/js/visao_dia.test.js` (8 casos) - todos com relogio/data controlados
explicitamente, sem depender da hora real de quando o teste roda. Suite completa sem
regressao (as 6 falhas pre-existentes de horario de voo/agrupamento, conhecidas e documentadas
no AGENTS.md, continuam as mesmas). Verificacao visual headless (Playwright, 390px) das duas
telas. Decisoes e "nao confirmado" completos em `tasks/fase6/progress-e5.txt`.

## 2026-09-23 (Fase 6 E2) - modulos Habitos, Projetos, agenda no iCloud e limite do cartao

Faixa 2 do Grupo E da Fase 6: 4 modulos novos e independentes que a proatividade (US-E8) e os
cards da faixa E3 vao consumir - nenhum mexe no formato de resposta do `/api/chat`/`/api/capture`
(isso e a faixa E3) nem nas tools/telas ja existentes de outras faixas em paralelo.

- **US-E12 (Habitos)**: modulo novo, deliberadamente SEPARADO da Rotina guiada
  (`rotina_itens`/`rotina_marcacoes`, que continua so manha/noite). Tabelas
  `habitos`/`habito_marcacoes`; habito com nome, meta livre, frequencia (`diario` / `dias_semana`
  / `n_vezes_semana` - "qualquer dia conta" ate bater a meta da semana) e horario opcional de
  lembrete. `GET/POST /api/habitos`, `DELETE /api/habitos/<id>`, `POST
  /api/habitos/<id>/marcar`. Chat tools `registrar_habito`/`marcar_habito`. Tela nova na aba Vida
  com os 7 circulos da semana (`static/js/vida.js`, `.habito-semana`/`.habito-circulo` em
  `style.css`). Funcao pura `vida.habito_passou_batido` (horario + 1h sem marcar) fica pronta pra
  US-E8 consumir. Decisao: habito NAO e ocultado no modo visitante (nao e dado sensivel).
- **US-E13 (Projetos)**: modulo generico novo (`projetos`/`projeto_etapas`) - checklist de
  etapas ordenadas, prazo final, status `no_rumo`/`atrasado` (calculado) ou `pausado` (manual,
  nunca sobrescrito). `vida.calcular_projeto` da o %, proxima etapa pendente, posicao de HOJE
  entre inicio e prazo (0-100, pra barra com marcador) e dias sem toque. Rotas
  `/api/projetos` (GET/POST/DELETE), `/status`, `/etapas`, `/etapas/<id>/concluir`. Chat tools
  `criar_projeto`/`adicionar_etapa`/`concluir_etapa`. **Viagens NAO migram pra Projetos**:
  `vida.converter_viagem_para_projeto` + `GET /api/viagens/<id>/como-projeto` so emprestam o
  mesmo formato de dado (calculado em cima de `viagens`/`viagem_itens` direto) pro card reusar o
  visual, sem duplicar persistencia. Tela ficou na aba Vida (mesma leva de Habitos).
- **US-E14 (Agenda no iCloud)**: `caldav_client.py` ganhou escrita (antes so lia) - `criar_evento`
  e `apagar_evento`, restritos a UM calendario proprio chamado "Painel" (criado automaticamente
  se nao existir, achado por `get_display_name()`). Tabela local `eventos_criados` (uid, titulo,
  inicio, fim) e a fonte da verdade: `apagar_evento` SO roda se o uid estiver registrado ali -
  nunca toca em evento que o painel nao criou, em nenhum outro calendario. Sem
  ICLOUD_USERNAME/ICLOUD_APP_PASSWORD configurados, erro claro (`NaoConfiguradoError`) em vez de
  quebrar. Rotas `POST/DELETE /api/agenda/eventos`, `GET /api/agenda/eventos-criados`. Chat tool
  `agendar_evento`. Testes sempre com CalDAV mockado (nunca iCloud real).
- **US-E15 (limite do cartao)**: coluna `bank_accounts.limite` (manual - Open Finance nao manda
  isso). `GET /api/bancos` ganhou `gasto_ciclo` (mes-calendario) e `limite_info`
  (`{fracao, sobra}` ou `null` sem limite configurado - nunca inventa aviso) pra cada cartao.
  `POST /api/bancos/<id>/limite` (respeita modo visitante). Funcao pura
  `vida.fracao_limite_cartao` trava a fracao num teto de 150% pra dado sujo nao virar numero
  absurdo. UI: caixa de limite (barra + input) dentro de cada cartao em Bancos.
- Testes novos em `tests/test_fase6_e2_modulos.py` (56 casos: rotas, funcoes puras, chat tools,
  CalDAV mockado, fuzzing leve de campos invalidos). Suite completa (`unittest discover` + `node
  --test`) sem regressao - as 2 falhas de horario de voo que apareceram nesta rodada
  (`test_ligado_segura_ate_a_janela_passar_e_agrupa`,
  `test_verificar_nao_notifica_voo_com_hora_de_sair_distante`) sao pre-existentes e dependentes
  do relogio real (confirmado rodando as mesmas duas isoladas num `git stash` antes desta leva -
  falham igual sem nenhuma mudanca desta sessao).
- `AGENTS.md`: nova secao "Padroes descobertos" com a pegadinha de `page.evaluate("showTab(...)")`
  nao recarregar dado da aba (precisa de `page.click` de verdade no botao da tabbar), o
  `data=`/`json=` do `_corpo_json()`, e como a lib `caldav` monta o ICS via kwargs.

## 2026-09-23 (Fase 6 E3) - contrato de cards (Padrao Nectar)

Aba Hoje vira centro de controle: toda acao/consulta do chat e da captura devolve dado
estruturado renderizado como CARD (referencia: app Nectar), em vez de so prosa. Branch
`fase6/e3-cards`, historias US-E2 a US-E5 (`tasks/fase6/grupo-e3-cards.json`, decisoes em
`tasks/fase6/progress-e3.txt`).

- **Contrato (`docs/CARDS.md`, fonte unica, so aditivo)**: `{cards: [{type, id, data,
  actions}], resumo_texto, passos}` em `/api/chat`, `/api/capture` e `/api/atalho/capturar`.
  Campos legados mantidos (`resposta`/`acoes` no chat, JSON da classificacao na captura) -
  PWA com cache antigo, Telegram (so texto, via `_processar_mensagem_chat`) e Atalhos
  continuam funcionando. Formato de `data` de todos os types, actions (`abrir_aba`,
  `desfazer`, `despertar`) e passos (`{modulo, descricao, ms}`) documentados.
- **Backend (`cards.py`)**: executores de tool do chat devolvem `"_efeito"` (chave privada
  que `RegistroExecucao` tira antes da IA ver) e `cards_dos_efeitos` e o unico mapeamento
  efeito -> card (le a linha do banco pelo id). Tarefas da mesma resposta viram um card so;
  2+ cards ganham `resumo_final`. Cards gravados em `chat_mensagens.cards_json`
  (criptografado) e devolvidos no historico.
- **Modo visitante no servidor**: card sem `valor`/`saldo`/`valor_*`, prosa com `R$ •••`.
- **Front (`static/js/cards.js` + `cards-tipos.js`)**: registro type -> renderizador puro
  (string HTML escapada, testado em Node), fallback "Este trecho nao pode ser exibido. Os
  dados foram preservados." pra type desconhecido/erro. Cards: `tarefas_criadas` (checkbox
  conclui/reabre), `transacao`, `lembrete` (contagem regressiva viva + "Desperta voce" =
  push no dia), `meta`, `resumo_final` (passos recolhiveis), e os renderizadores prontos de
  `agenda` (barra do dia 06h-22h), `projeto_viagem` (marcador HOJE), `saude_treino`
  (barras SVG), `sugestao` ("Com a sua rotina em mente") e `habito` (S T Q Q S S D) - o
  dado real desses ultimos e ligado pela US-E7b.
- **Desfazer por token (US-E5)**: `POST /api/desfazer/<token>` reverte os ids EXATOS
  gravados em `acoes_desfazer` no momento da acao (tudo ou nada; saldo otimista revertido
  junto; 409 se ja desfeito). Cada card do brain dump e independente. Evento de agenda so
  se o uid estiver em `eventos_criados` (regra da US-E14; sem `apagar_evento_painel` no
  CalDAV ainda -> 501). Link de cada card abre a aba e destaca o item
  (`data-entidade`/`data-id` nas listas).
- Rotas novas: `/api/desfazer/<token>`, `/api/lembretes/<id>/despertar`,
  `/api/tasks/<id>/reabrir`. Colunas/tabelas novas: `chat_mensagens.cards_json`,
  `lembretes.despertar`, `acoes_desfazer`. Service worker v11.
- Testes: `tests/test_cards.py` (contrato, visitante, desfazer por tipo) e
  `tests/js/cards.test.js` (registro, fallback, cada renderizador). Conferido em Chromium
  headless 390px (app so tem tema escuro).

## 2026-09-23 (Fase 6 E1) - bugs, memoria visivel e estilo de resposta

Faixa E1-base da Fase 6 (Grupo E), 5 historias - branch `fase6/e1-base`, um commit por
historia (`git log` tem o detalhe completo de cada uma; `tasks/fase6/progress-e1.txt` tem
a investigacao/decisao de cada uma por extenso).

- **US-E1a (bug): as duas secoes de Manutencao da aba Vida viram uma so.** `manutencoes`
  (por tempo, generica) e `manutencoes_veiculo` (por km/data, US-C14) eram tabelas/telas
  separadas - agora e uma tabela so (`manutencoes`, coluna `tipo` nova: casa/carro/
  equipamento/outro), com migracao idempotente em `init_db` pros bancos que ja tinham as
  duas. Carro continua com semantica de HISTORICO (registro novo por manutencao feita);
  os demais tipos continuam com edicao no lugar ("feita hoje"). Rotas `/api/manutencoes-
  veiculo/*` removidas, tudo em `/api/manutencoes` com `tipo` no corpo.
- **US-E1b (bug): lista de compras separa itens juntos numa entrada so.** "acabou cafe e
  acucar" agora vira 2 itens com checkbox proprio (antes virava 1 item so). Funcao unica
  `vida.dividir_itens_compra` (virgula + conjuncao "e" isolada, com variacoes "e tambem"/
  "e acabou(aram)") plugada no ponto de entrada unico que ja existia (`_adicionar_compras`,
  usado pelo formulario, API e chat tool) - nome composto sem a conjuncao isolada ("pao de
  queijo") continua 1 item.
- **US-E1c (bug): loop suave na animacao de fundo (rainbow).** Causa real: `@keyframes
  auroraShine` (a camada de "brilho" diagonal) tinha 0% diferente de 100% - um keyframe
  assimetrico sempre da um pulo visivel na virada do ciclo. Virou ida-e-volta (0%/100%
  iguais), mesmo padrao ja usado nas outras 3 camadas do fundo. `prefers-reduced-motion`
  ja cobria essa camada, sem mudanca.
- **US-E10: memoria visivel "O que eu lembro sobre voce" (aba Painel).** 3 grupos fixos e
  editaveis (Sua rotina / Seus planos / Fora do painel), estendendo a tabela `memorias`
  que ja existia (coluna `categoria` nova) - seed idempotente por categoria vazia (nunca
  sobrescreve edicao/remocao do Alex). Primeiro caso de edicao inline no projeto (span
  vira input no lugar, Salvar/Cancelar - documentado no AGENTS.md). "Fora do painel"
  chega no prompt do chat de graca, sem wiring nova (`list_memorias` ja alimenta o
  contexto do `CHAT_SYSTEM_PROMPT` sem filtro de categoria).
- **US-E11: estilo de resposta do assistente.** `CHAT_SYSTEM_PROMPT` (chat) e
  `DECISAO_PROMPT` (card dedicado "vale a pena?") ganham: direto por padrao, so expande
  com pedido explicito; qualquer pros/contras (nao so a frase literal "vale a pena") pede
  recomendacao final explicita, nunca fica em aberto; contexto de que a construtora e
  socia com o pai e um socio (mencionar so quando pesar na decisao); nunca citar valor em
  R$ especifico da construtora (fica so no financeiro-construtora, sistema separado).
  **Nao mexido de proposito:** a injecao factual pre-existente de um numero real da
  construtora em plano-do-dia/resumo-do-dia (`_construtora_contexto_resumo`, feature
  v3.99.14/16 ja sancionada) - a leitura foi que a regra e sobre o assistente nunca
  *inventar/repetir* numero numa resposta livre, nao sobre remover uma feature shippada
  de mostrar dado que ja vem pronto da API externa; ver `progress-e1.txt` pra decisao
  completa e a pergunta que ficou em aberto pro Alex confirmar.

Suite completa (unittest discover + node --test) sem regressao em nenhuma das 5 historias -
mesmas 6 falhas pre-existentes conhecidas em todos os commits (5 de horario de voo +
1 de notificacao agrupada, ambas ja instaveis antes desta faixa comecar, confirmadas
isoladas contra a branch antes de qualquer mudanca).

## 2026-09-23 (32) - Deploy de teste no Render (plano gratis)

Pra o Alex testar o estado atual no iPhone com URL publica HTTPS, sem esperar a VPS
definitiva (`deploy/DEPLOY.md`). Um tunel temporario a partir do ambiente de nuvem da IA foi
tentado antes e nao funciona: a rede de la so libera HTTPS via proxy na porta 443, e o
`cloudflared` precisa da porta 7844 direto.

- **`render.yaml`** (Blueprint): gunicorn com 1 worker (SQLite + `_TETO_IA_LOCK` e lock de
  processo), timeout 120s (chamada de IA com foto), `healthCheckPath: /healthz`,
  `SECURE_COOKIES=true`, e `PAINEL_PIN_INICIAL`/`ANTHROPIC_API_KEY` como `sync: false` (o
  Render pede na criacao, nunca vai pro Git).
- **`PAINEL_PIN_INICIAL`** (novo, `app._aplicar_pin_inicial`): sem terminal no plano gratis
  pra rodar `scripts/resetar_pin.py`, quem abrisse a URL nova primeiro escolheria o PIN -
  e subdominio novo de `onrender.com` e varrido por robo em minutos (certificado aparece nos
  logs de Certificate Transparency). A variavel define o PIN no boot so se ainda nao houver
  um (nunca sobrescreve); PIN invalido derruba o boot de proposito (subir com
  `/configurar-pin` aberto seria pior). Testes em `tests/test_pin_inicial.py`.
- **`deploy/RENDER.md`**: passo a passo pra leigo (criar conta, Blueprint, preencher PIN e
  chave, instalar na Tela de Inicio, o que testar, erros comuns).
- Limitacoes conhecidas e documentadas: disco efemero (dados somem a cada deploy e quando o
  servico dorme depois de ~15 min parado), agendador/Telegram nao sobem com gunicorn (so no
  `python app.py`) - de proposito pra teste, nada dispara mensagem real.
- Validado simulando o Render: copia limpa do repo (sem `data/`, nunca o banco real) subindo
  pelo mesmo comando do `render.yaml` - healthz ok, PIN inicial aplicado, `/configurar-pin`
  fechado, login com PIN certo/errado ok.

## 2026-09-23 (31) - Fase 5: correcoes da revisao independente (codigo + seguranca)

Depois de integrar os 4 grupos da Fase 5 na main, revisao independente de codigo e de
seguranca (mesmo padrao ja usado nas fases anteriores) encontrou 6 vulnerabilidades reais
(4 bloqueadoras, 1 achada pelos dois agentes de forma independente) e 4 itens "deve
corrigir em breve". Todos corrigidos nesta rodada, direto na main:

- **Modo visitante incompleto (US-C20/US-C22, o achado mais serio - encontrado pelos DOIS
  agentes de revisao de forma independente)**: `/api/diario-decisoes` (GET/POST/resultado)
  nunca tinha entrado no escopo do modo visitante - segredo aparecia inteiro na resposta.
  Corrigido com o mesmo padrao ja usado em `/api/decisoes`. Alem disso, `/api/patrimonio`,
  `/api/bancos` e `/api/bancos/<id>/transacoes` (dado consolidado das contas bancarias,
  Fase 4) nunca tinham sido trazidas pro escopo nenhuma vez - corrigido (GET devolve vazio/
  `oculto: true`, nunca o dado real).
- **Export de dados ignorava o modo visitante**: os 4 endpoints de export
  (`/api/expenses/exportar-csv`, `/api/backup/exportar`, `/api/backup/exportar-json`,
  `/api/backup/exportar-csv-completo`) devolviam o dado real completo mesmo com o modo
  visitante ligado - agora bloqueados com 403, mesma mensagem padrao.
  - **Frontend**: `loadDecisoes()` e `loadBancos()` (que tambem recarrega `/api/patrimonio`)
    agora tambem escutam `modo-visitante-mudou` (`static/js/app.js`) - o dado sensivel
    parado em cache no DOM de uma leitura anterior tambem some da tela, nao so da resposta
    HTTP. Verificado com Playwright headless (fluxo real: login, dado secreto visivel,
    ativa modo visitante, dado some do DOM em ambas as telas).
- **PIN do modo visitante sem limite de tentativas**: diferente do `/login`, desativar o
  modo visitante com o PIN errado nao tinha nenhum bloqueio - agora reusa o MESMO mecanismo
  (`auth.verificar_bloqueio`/`registrar_tentativa`) do login, 5 tentativas erradas bloqueiam
  por 5 minutos.
- **Teto mensal de gasto com IA (US-A6) checado em so 1 dos 2 endpoints caros**: o
  classificador de intent (`_classificar_intent`) respeitava o teto, mas a extracao de nota
  fiscal por foto (`/api/notas-fiscais/extrair`, usa Sonnet - a chamada mais cara do app)
  nao checava. Corrigido com o mesmo padrao (`resumo_custo_api(conn)["teto_estourado"]`
  antes de chamar a API).
- **TOCTOU no teto de gasto (MEDIO)**: checar o teto e so depois logar o gasto, sem nenhum
  lock, deixava uma janela teorica pra duas requisicoes concorrentes passarem do teto ao
  mesmo tempo. `_TETO_IA_LOCK` (um `threading.Lock` de processo) agora serializa checar ->
  chamar a IA -> logar nos dois pontos que respeitam o teto - app de usuario unico, entao
  o lock nunca fica sob disputa real, so fecha a janela.
- **Anexo de garantia so validado pela extensao do nome do arquivo (MEDIO)**: `.pdf`/`.jpg`/
  `.png` no nome nao prova nada sobre o conteudo real. Adicionada checagem de magic bytes
  (`_conteudo_bate_com_extensao`) - PDF/JPG/PNG de verdade, ou rejeitado com 400.
- **9 arquivos de teste sem a trava de producao (MEDIO)**: `db.garantir_banco_nao_producao()`
  (criada na propria Fase 5 depois de um quase-incidente, ver entrada anterior) tinha sido
  esquecida em `test_garantias.py`, `test_modo_visitante.py`, `test_modo_visitante_telas.py`,
  `test_sinal_sobrecarga.py`, `test_ideias_presente.py`, `test_modo_viagem.py`,
  `test_gasto_categoria_atipico.py`, `test_previa_noite.py` e `test_vida_rotas.py` -
  adicionada em todos, logo apos `db.DB_PATH` ser trocado pro caminho temporario.
- Testes de regressao novos cobrindo cada achado (`test_modo_visitante_telas.py`:
  patrimonio/bancos/transacoes/diario-decisoes/exports; `test_modo_visitante.py`: bloqueio
  de tentativas; `test_garantias.py`: magic bytes). Suite completa (unittest + `node --test`)
  sem regressao, `gitleaks detect` sem achado, `pyflakes` limpo.
- Achados menores documentados e conscientemente NAO corrigidos nesta rodada (BAIXO/nice-
  to-have, escopo de uma proxima fase): `/api/atalho/resumo` chama `_token_atalho_valido`
  sem `obrigatorio=True` (inconsistente com o padrao do resto dos `/api/atalho/*`, mas
  pre-existente e de fora do escopo da Fase 5); `MAX_CONTENT_LENGTH` do Flask nao
  configurado; a listagem de `/api/garantias` devolve o anexo em base64 inteiro (nenhuma
  tela ainda renderiza ou baixa esse anexo, entao sem exposicao real hoje).

## 2026-09-23 (30) - Fase 5 Grupo D: polimento visual

Branch `fase5/grupo-d-polimento` (agente IA autonomo, worktree isolado, `tasks/fase5/
grupo-d-polimento.json`). So comecou depois dos Grupos A, B e C integrados na main (regra
do proprio grupo, pra nao gerar conflito de CSS/HTML em cima de tela que ainda tava sendo
criada). US-D1 a US-D3, todas passando.

- **US-D1 - Animacao/transicao nas telas de captura/rotina/financeiro**: quase toda tela
  nova do Grupo C ja seguia o padrao visual existente (herda `fadeInUp`/stagger de
  `secao-secundaria`/`dica-colapsavel`/`form-linha`/`li.item`). Gap real: `.card-vida`
  (usado por `sobrecarga-box`, `previa-noite-box`, `revisao-periodo-box`, `patrimonio-box` -
  novos - e tambem por `rotina`/`checkin`/`essencial`/`progresso`/`fim-mes`/`custo-ia` -
  antigos) nao tinha nenhuma animacao de entrada, aparecia com corte seco ao sair de
  `[hidden]`. Adicionado `fadeInUp 0.35s var(--ease-bounce) both`, a mesma curva ja usada
  nos irmaos.
- **US-D2 - Animacao na navegacao por voz e widget de tela bloqueada**: o estado "ouvindo"
  (US-B1) ja tinha feedback visual; gap real era o estado "processando" (entre fim da
  escuta e a resposta de `/api/intent/classificar`) sem nenhum feedback alem de um texto
  pequeno. Corrigido reaproveitando o MESMO padrao ja usado em todo formulario do app
  (`setBotaoCarregando`), em vez de inventar animacao nova. Widget de tela bloqueada
  (US-C1, `scriptable/widget_lockscreen.js`) conferido e ja estava certo - o proprio arquivo
  documenta por que nunca usa cor customizada nos slots de lock screen (iOS renderiza
  monocromatico ali).
- **US-D3 - Espacamento/hierarquia geral e micro-interacao de confirmacao**: telas novas do
  Grupo C ja seguiam o mesmo padrao de espacamento das antigas. Gap real: a confirmacao de
  nota fiscal por foto (US-C8/US-C9) salvava e escondia a caixa na hora, sem nenhum
  `pulsarSucesso` - corrigido pulsando `#nf-valor` e adiando o `hidden=true` em 250ms (mesmo
  tempo ja usado no "saindo" de item apagado/convertido).
- Cada historia verificada com Playwright headless (Chromium pre-instalado, ver AGENTS.md
  pra pegadinha do `executable_path`) alem da suite de testes completa (unittest 1417
  testes, so as 5 falhas pre-existentes de horario de voo; `node --test` 29/29).

## 2026-09-23 (29) - Fase 5 Grupo B: navegacao por voz (best-effort) + offline

Branch `fase5/grupo-b-voz-offline` (agente IA autonomo, worktree isolado). US-B1 a US-B6
do `tasks/fase5/grupo-b-voz-offline.json`, todas passando. Depende do contrato/classificador
do Grupo A (`/api/intent/classificar`, ver entrada anterior e `docs/INTENT.md`) - este grupo
so consome, nunca duplica a logica de classificacao.

- **US-B1 - Comando de voz no navegador**: botao `#comando-voz-btn` (secao propria, separado
  do `#chat-mic` do chat) usa `window.SpeechRecognition`/`webkitSpeechRecognition` -
  melhor esforco, com mensagem clara ("use os Atalhos da Siri") e botao desabilitado quando o
  navegador nao suporta, em vez de falhar silenciosamente (instabilidade conhecida em PWA
  standalone no iOS Safari, dispositivo principal do Alex - validacao manual real ainda
  pendente, sem iPhone no ambiente de execucao). Texto reconhecido vai pro classificador de
  intent e a acao e roteada pra um fluxo JA EXISTENTE do painel (nunca duplicado):
  `registrar_tarefa`/`registrar_gasto` -> `enviarCaptura()`, `consultar`/`corrigir_ultimo` ->
  `enviarChat()`, `navegar_tela` -> `showTab()`, `registrar_checkin` -> abre a aba com o
  check-in de 1 toque (o contrato nao fixa formato de parametro confiavel pra
  campo/valor do check-in).
- **US-B2 - Confirmacao antes de acao destrutiva**: `precisa_confirmacao=true` do contrato e
  sempre respeitado. O contrato fechado ainda nao tem nenhuma acao literalmente destrutiva -
  `corrigir_ultimo` (sobrescreve o ultimo item) e tratado como quase-destrutiva
  (`ACOES_DESTRUTIVAS`, constante isolada e facil de estender).
- **US-B3 - Dialogo de correcao de 2 turnos**: quando a confianca vem baixa, a caixa de
  confirmacao tambem oferece 6 botoes "Era X" (uma por acao real do contrato). Escolher uma
  chama o endpoint novo `POST /api/intent/corrigir`, que reusa
  `aprendizado.confirmar_padrao_intent(..., forcar_confianca_alta=True)` - mesmo mecanismo da
  US-A4, sem logica paralela.
- **US-B4 - Captura via Atalhos/Siri**: `POST /api/atalho/comando-voz` (mesmo token
  `X-Webhook-Token`/`PAINEL_ATALHOS_TOKEN` dos outros `/api/atalho/*`) reusa
  `_classificar_intent` (extraida de `app.py` como fonte unica, compartilhada com
  `/api/intent/classificar`) e devolve `{..., "fala": "..."}` - frase curta pronta pro Atalho
  falar de volta com "Falar Texto". So classifica, nunca executa a acao sozinho (fora do
  escopo desta historia). Documentado em `README.md`.
- **US-B5 - Fallback offline**: comando de voz reusa a MESMA fila da Fase 4
  (`static/js/fila-offline.js`, tipo `"comando_voz"`) - sem rede, o texto ja transcrito fica
  salvo e sincroniza sozinho, igual captura/check-in ja fazem. `voz-comando.js` entrou no
  precache do service worker (`v10`).
- **US-B6 - Classificacao local (avaliacao de viabilidade)**: Core ML/Neural Engine de
  verdade exige app nativo ou WebNN (suporte de navegador limitadissimo em 2026) - inviavel
  numa PWA. Implementada a alternativa que o proprio criterio de aceite permitia:
  `classificarLocalmente()`, uma heuristica de palavras-chave (bag-of-words simples,
  explicitamente NAO e Core ML/ML de verdade) que resolve so o caso mais inequivoco
  (navegar pra uma tela conhecida) 100% offline e sem custo de IA.
- Novo arquivo `static/js/voz-comando.js` (logica pura testavel em Node + wiring de
  navegador) e `tests/js/voz_comando.test.js`. Testes de backend novos em
  `tests/test_app.py` (`IntentCorrigirTestCase`, `AtalhoComandoVozTestCase`). Verificacao
  visual headless com Playwright (botao, fallback de nao-suporte, dialogo de
  confirmacao/correcao) - ver `AGENTS.md` pra pegadinha de como simular "sem suporte" nesse
  Chromium pre-instalado.

## 2026-09-23 (28) - Fase 5 Grupo A: nucleo do classificador de intent

Branch `fase5/grupo-a-nucleo-intent` (agente IA autonomo, worktree isolado). US-A1 a US-A6
do `tasks/fase5/grupo-a-nucleo-intent.json`, todas passando. Objetivo: dar ao Grupo B
(navegacao por voz) um classificador de comando -> acao real, com camada de economia local
e teto de gasto - ver `docs/INTENT.md` pro contrato completo.

- **US-A1/US-A2 - Contrato + classificador real**: `POST /api/intent/classificar` com lista
  fechada de 7 acoes (`registrar_tarefa`, `registrar_gasto`, `registrar_checkin`,
  `navegar_tela`, `consultar`, `corrigir_ultimo`, `desconhecido`). `claude_client.classify_intent`
  (Haiku, mesmo padrao de `classify_capture`) classifica de verdade; confianca abaixo de 0.6
  volta `precisa_confirmacao: true` em vez de deixar o chamador agir direto.
- **US-A3 - Padrao aprendido local**: tabela `padroes_intent_aprendidos` - texto normalizado
  repetido e confirmado 3x pela IA resolve local, sem gastar API (`aprendizado.padrao_intent_confiavel`/
  `confirmar_padrao_intent`, mesmo principio silencioso do resto de `aprendizado.py` - nunca
  declara "aprendi isso" pro usuario).
- **US-A4 - Correcao da Fase 4 alimenta o padrao**: `db.registrar_correcao_classificacao`
  agora tambem grava um padrao de confianca alta direto (sem esperar 3 repeticoes) - corrigir
  uma vez ja evita repetir o erro num comando parecido.
- **US-A5 - Visor de custo de API**: reaproveitada a tabela `api_usage` ja existente (ganhou
  coluna `feature`) em vez de criar uma tabela nova - `GET /api/ia/custo` resume gasto do mes
  atual e dos ultimos 30 dias (USD) por feature; card novo na aba Financeiro
  (`static/js/app.js::loadCustoIA`). De quebra, corrigido um bug pre-existente: o total de
  custo no cabecalho usava `fmtMoeda` (BRL) pra um valor que sempre foi USD - `fmtUSD` novo,
  os dois lugares corrigidos.
- **US-A6 - Teto mensal configuravel**: `configuracoes.teto_mensal_ia_usd`, editavel no mesmo
  card financeiro. Aviso aos 80%/100% pelo canal de notificacao ja existente (push + Telegram,
  `verificar_e_notificar`), mesmo padrao de dedup de `orcamentos_perto_ou_estourados`. Com o
  teto estourado, `/api/intent/classificar` para de chamar a API (so resolve por padrao
  aprendido da US-A3) ate o mes virar - documentado no card e em `docs/INTENT.md`
  (`teto_ia_estourado`, campo aditivo ao contrato da US-A1).
- **Fragilidade de teste pre-existente, so documentada (nao corrigida - fora do escopo das
  historias)**: `vida.rotina_manha_devida` (e o equivalente pros voos, ja conhecido) dispara
  notificacao real quando o relogio do container cai dentro de uma janela de poucos minutos
  (07:00-07:05 por padrao) - isso incha falhas nao relacionadas em QUALQUER suite completa que
  rodar durante essa janela (contagem de mock off-by-one em dezenas de testes). Confirmado
  como falso-positivo (mesmos testes passam limpos fora da janela). Recomendacao pra uma
  historia futura: mockar `datetime.now()` nesses testes tambem, como ja e feito pro
  silencio noturno (`notificacoes.dentro_do_horario_silencioso`).
## 2026-09-23 (26) - Fase 5, Grupo C1: historias independentes (US-C1 a US-C7)

Leva de 7 historias totalmente independentes do nucleo de intent (rodaram em worktree/branch
isolada, `fase5/grupo-c1`), cada uma conferida contra `TODO.md`/`CHANGELOG.md` antes de criar
algo do zero (a maioria estende mecanismo ja existente em vez de duplicar).

- **US-C1 - Widget de tela de bloqueio**: `GET /api/atalho/resumo` ganhou `resumo_curto`/
  `linha_extra` (texto compacto pra accessoryInline/Rectangular do iOS 16+). Script novo
  `scriptable/widget_lockscreen.js` (sem cor customizada - o iOS renderiza monocromatico
  nesses slots) + `docs/WIDGET_TELA_BLOQUEIO.md`.
- **US-C2 - Diario de decisao**: tabela `diario_decisoes` (decisao, contexto, data,
  revisao_em, resultado) - nome escolhido pra NAO colidir com a tabela `decisoes` da Fase 1
  ("vale a pena?", efemera). CRUD em `/api/diario-decisoes`, chat tool `registrar_decisao`,
  secao na aba Painel (mesmo padrao visual de Notas).
- **US-C3 - Revisao trimestral/anual**: `GET /api/revisao-periodo` reaproveita `_fatos_periodo`
  (a mesma funcao ja usada por `/api/revisao-mensal` e `/api/progresso` - financeiro, tarefas
  concluidas, saude) e soma as decisoes do diario (US-C2) do periodo. Tela na aba Vida.
- **US-C4 - Notificacao agrupada**: integrado ao MESMO endpoint/mecanismo do modo silencioso
  configuravel (`/api/configuracoes/silencio` ganhou `agrupar`/`agrupar_janela_min`) -
  desligado por padrao (nao muda comportamento de quem nunca configurou). Ligado: avisos
  nao-urgentes ficam numa fila persistida (mesmo padrao de `avisos_adiados`/hiperfoco) ate a
  janela configurada passar, ai viram UMA mensagem so (`notificacoes.montar_mensagem_agrupada`).
  Urgente nunca agrupa.
- **US-C5 - Priorizacao de contato**: reaproveita a tabela/logica de esperas pendentes (nao
  cria sistema de contatos novo) - coluna nova `esperas.importante` + `vida.priorizar_esperas`
  (tempo parado + bonus de 5 dias se importante) em `GET /api/esperas/prioridade`.
- **US-C6 - Brain dump**: tabela `brain_dump` (texto, processado) - captura em
  `POST /api/brain-dump`, lista em `GET`, conversao em `/api/brain-dump/<id>/converter`
  (tarefa/nota/gasto, sempre com o Alex escolhendo o tipo - nunca salva sem revisao). Secao na
  aba Painel.
- **US-C7 - Sugestao por energia**: coluna nova `tasks.esforco` (baixa/media/alta, sem valor =
  tratado como media) + `vida.tarefas_compativeis_com_energia`. 3 botoes na aba Tarefas
  (`GET /api/tarefas/sugestao-energia?nivel=`), tag clicavel em cada tarefa pra marcar o
  esforco (mesmo padrao de `criarSeletorCategoriaGasto`).

Suite completa (1174 testes) sem nenhuma regressao - as 5 falhas pre-existentes de
notificacao de voo sensivel a horario continuam as mesmas de antes desta leva.

## 2026-09-23 (27) - Fase 5 Grupo C (independentes, agente c3): US-C15 a US-C22

Agente isolado em worktree proprio (`fase5/grupo-c3`), cobrindo so US-C15 a US-C22 do
`tasks/fase5/grupo-c-independentes.json`. Ver `tasks/fase5/progress-grupo-c.txt` pro relato
completo por historia.

**US-C15 - Ideias de presente**
- Tabela `ideias_presente` (pessoa, ideia, ocasiao, comprado) + CRUD (`db.py`/`app.py`,
  `GET/POST /api/ideias-presente`, `POST .../<id>/comprado`, `DELETE .../<id>`).
- Chat tool `registrar_ideia_presente` (mesmo padrao de `registrar_lugar`).
- Secao nova na aba Vida (reaproveita `itemSimples`/`ligarForm` de `vida.js`).
- `tests/test_ideias_presente.py` (11 casos: CRUD via db.py, via API, autenticacao, chat tool).

**US-C16 - Modo viagem**
- Toggle `GET/POST /api/modo-viagem`, estado em `configuracoes` (chave `modo_viagem`,
  JSON `{ativo, data_inicio, data_fim}` - mesmo padrao de `hiperfoco_ate`/`avisos_adiados`).
  `viagem.modo_viagem_ativo(estado, hoje)` (pura, testavel): toggle liga na hora; com
  datas, expira sozinho fora da janela sem precisar desligar na mao.
- `verificar_e_notificar` suprime `rotina_manha`/`hora_de_dormir`/`fechamento_noturno`/
  `manutencao` (rotina domestica) enquanto ativo - resto continua normal (nunca marca
  como notificado, entao volta a valer sozinho quando o modo acabar, mesmo espirito do
  horario silencioso).
- Botao novo no cabecalho (mesmo padrao visual do de horario silencioso).
- Ajuste de calculo de horario por fuso (mencionado na AC como opcional "se fizer
  sentido"): avaliado e descartado por ora - o campo `destino` e texto livre, sem
  geocoding nao da pra saber o fuso de verdade sem arriscar inventar; ficou so a
  supressao de notificacao, documentado em `progress-grupo-c.txt`.
- `tests/test_modo_viagem.py` (16 casos: funcao pura, API, supressao real em
  `verificar_e_notificar`).

**US-C17 - Alerta de gasto fora do padrao (categoria)**
- Estende o mecanismo ja existente de gasto atipico (`notificacoes.gasto_dia_semana_atipico`,
  que compara o TOTAL do dia com o mesmo dia da semana) com um segundo angulo, no mesmo
  arquivo: `notificacoes.gastos_fora_do_padrao_categoria` compara cada gasto INDIVIDUAL de
  hoje com a media + desvio-padrao historico da mesma categoria (janela de 3 meses, minimo
  5 amostras) - pega um gasto pontual fora do normal mesmo quando o dia inteiro nao chama
  atencao. Categoria sem variacao historica (desvio-padrao 0, ex: sempre a mesma assinatura)
  usa 50% acima da media constante como limiar, ja que "X desvios" nao faz sentido com
  variancia zero.
- `aprendizado.media_e_desvio_padrao` (helper estatistico puro novo, reaproveitando o padrao
  do modulo - so estatistica sobre o proprio historico, sem IA).
- Wired em `verificar_e_notificar` logo apos o alerta por dia da semana, dedup por gasto
  (`ja_notificado_alguma_vez` - o mesmo gasto nunca avisa duas vezes).
- `tests/test_gasto_categoria_atipico.py` (11 casos: helper estatistico, deteccao pura,
  integracao real em `verificar_e_notificar`).

**US-C18 - Cofre de garantia**
- Tabela `garantias` (produto, data_compra, prazo_garantia_meses, nota_fiscal_anexo opcional,
  notificado) + CRUD (`GET/POST /api/garantias`, `DELETE .../<id>`). `POST` aceita JSON (sem
  anexo) ou `multipart/form-data` com arquivo `nota_fiscal` (PDF/JPG/PNG, ate 5MB) - guarda
  o anexo como base64 na propria linha, sem OCR/extracao (isso e escopo de US-C8/US-C9,
  fora desta historia). `vida.somar_meses` novo (extraido de `proxima_data_manutencao`,
  que passou a reusar - mesmo calculo de "daqui a N meses" pros dois casos).
- `notificacoes.garantias_vencendo`: avisa 15 dias antes do vencimento (ou se ja venceu).
  Dedup pela PROPRIA coluna `notificado` da garantia (pedido explicito da AC), nao pela
  tabela generica `notificacoes_enviadas` - `verificar_e_notificar` marca a coluna depois
  de mandar de verdade.
- Decisao: nota_fiscal_anexo NAO entra na criptografia de campo da Fase 4 - esse escopo foi
  restrito explicitamente a Open Finance + saude (ver Decisoes da Fase 4 no `TODO.md`), uma
  nota fiscal de eletrodomestico tem o mesmo nivel de sensibilidade de `cotacoes`/
  `contas_pessoais` (ja sem criptografia).
- Secao nova na aba Vida (form com upload de arquivo opcional).
- `tests/test_garantias.py` (21 casos: `somar_meses`, CRUD via db.py/API inclusive upload,
  validacao, o alerta puro e a integracao real em `verificar_e_notificar`).

**US-C19 - Modo visitante (mecanismo central)**
- `GET/POST /api/modo-visitante`: estado so em `session` do Flask (cookie assinado pelo
  servidor) - NUNCA no banco, nem sobrevive a reinicio de sessao/logout de proposito.
  Ativar e 1 toque (`{"ativar": true}`, sem PIN - precisa ser rapido pra dar tempo de
  esconder a tela). Desativar exige o PIN de verdade (`auth.verificar_pin`) - senao quem
  ja esta com o celular desbloqueado conseguiria desligar sozinho.
- `app._modo_visitante_ativo()`: helper generico que qualquer rota pode chamar pra decidir
  se manda o dado real ou um estado neutro - US-C20 usa em financeiro/saude/decisoes.
- Botao novo no cabecalho (icone de olho) + painel com campo de PIN pra desativar.
- `tests/test_modo_visitante.py` (9 casos: liga sem PIN, nega desligar sem/com PIN errado,
  desliga com PIN certo, nao grava linha nenhuma no banco, some no logout, isolado por
  sessao/cliente - nunca vaza pra outro navegador logado).

**US-C20 - Modo visitante aplicado nas telas sensiveis**
- Gate feito no SERVIDOR em cada rota (usando `app._modo_visitante_ativo()` da US-C19),
  nunca so CSS - o requisito explicito era o dado real nao ir nem pra resposta HTTP:
  - **Financeiro**: `GET /api/expenses`, `/api/incomes`, `/api/orcamentos`, `/api/gastos-fixos`,
    `/api/expenses/historico`, `/api/gastos/resumo-semanal`, `/api/sobra-do-mes` retornam
    lista vazia/zero. `GET /api/summary/today` nem chama a IA quando o modo visitante esta
    ativo (o resumo em texto livre poderia mencionar valor gasto por inferencia - mais
    seguro nao gerar o texto nenhum do que tentar "limpar" o prompt).
  - **Saude**: `GET /api/saude/hoje` e `GET /api/medidas` retornam dado nulo/vazio (+ flag
    `oculto: true` no primeiro, pra UI diferenciar de "sem dado ainda").
  - **Diario de decisao**: `GET /api/decisoes` retorna lista vazia; `POST /api/decisao`
    (criar analise nova) fica bloqueado com 403 enquanto o modo estiver ativo.
  - Fora de escopo desta leva (documentado, nao silenciado): `/api/expenses/exportar-csv`
    (acao deliberada de export, nao "tela"), `/api/medicamentos` e check-in de energia/sono/
    humor (saude adjacente, mas fora dos 2 componentes visiveis da secao "Saude hoje" +
    "Peso e medidas" que a AC cobre).
- UI: cada uma das 3 telas troca pra "Oculto no modo visitante" (nunca so esconde via CSS -
  o servidor ja manda vazio, a UI so escolhe qual mensagem mostrar) e reage na hora ao
  evento `modo-visitante-mudou` (nao precisa trocar de aba pra ver o efeito).
- `tests/test_modo_visitante_telas.py`: verifica o BODY BRUTO da resposta HTTP (nao o DOM
  renderizado) em cada rota, incluindo que um valor/categoria/produto especifico inserido
  no banco nao aparece em lugar nenhum da resposta quando o modo esta ativo, que volta a
  aparecer normal ao desativar com o PIN, e que a IA nao e chamada nos dois casos sensiveis
  (resumo do dia e criar decisao) - 9 casos, 100% ok.

**US-C21 - Previa da noite anterior**
- `GET /api/previa-noite`: resumo FACTUAL (sem IA) do dia anterior a partir de dado ja
  existente - sono (`saude_dados.sono_horas` se o Atalho mandou, senao o check-in de 1
  toque da manha), hidratacao (`hidratacao_registros`) e quantos dos medicamentos ativos
  foram marcados como tomados ontem (reaproveita a materializacao de tarefa recorrente que
  ja rastreia isso - `recorrente_origem_id` + `due_date` de ontem - nao cria sistema novo).
  Remedio sem instancia materializada nesse dia (recorrencia nao diaria) nao entra na conta.
- Card novo "Como foi a noite" no topo da aba Hoje - mesmo padrao visual `card-vida`.
  Gated por modo visitante tambem (e dado de saude), com `{"oculto": true}` cedo.
- `tests/test_previa_noite.py` (10 casos: cada fonte de dado isolada, combinacao completa,
  API, gate do modo visitante).

**US-C22 - Sinal de sobrecarga**
- `notificacoes.sinal_sobrecarga(tarefas_atrasadas, sono_ruim, semana_pesada)`: combina 3
  sinais independentes numa pontuacao simples (1 ponto cada) - tarefas atrasadas so conta a
  partir de 3 (uma unica atrasada e vida normal), sono ruim reaproveita a MESMA deteccao ja
  usada no alerta `sono_ruim` existente (`vida.sequencia_noites_ruins`, 3+ noites seguidas).
  Limiar padrao: pontuacao >= 2 de 3 = `sobrecarregado`.
- **Importante**: o 3o sinal (`semana_pesada`, US-C13 - "semana que vem esta cheia") e de
  OUTRA historia do mesmo grupo (Grupo C), atribuida a outro agente rodando num worktree/
  branch separado (`fase5/grupo-c1` ou `c2`) - nao esta integrada neste branch ainda. O
  parametro existe e a funcao ja combina com ele corretamente (testado com `True`/`False`),
  mas o `GET /api/sobrecarga` chama com `semana_pesada=False` por enquanto. Quando a US-C13
  for mesclada nesta branch/na main, so trocar essa chamada pela funcao real de deteccao -
  documentado com destaque em `progress-grupo-c.txt` pro integrador nao esquecer.
- `GET /api/sobrecarga` + card "Sinal de sobrecarga" na aba Hoje (so aparece quando
  `sobrecarregado` for true).
- `tests/test_sinal_sobrecarga.py` (12 casos: todas as combinacoes de sinais, limiar,
  integracao real via API com tarefa atrasada de verdade no banco).

## 2026-09-23 (25) - Fase 4: resiliencia, backup e seguranca

Leva adicional pos-BRIEFING.md, 4 itens praticamente independentes, feitos por agentes em
paralelo e depois integrados com um merge git de verdade (dois conflitos reais resolvidos a
mao em `app.py`/`tests/test_app.py` - o resto entrou limpo). Revisao independente (2 agentes,
codigo/integracao e seguranca) achou 4 problemas reais, todos corrigidos.

**Item 1 - Backup e exportacao**
- `GET /api/backup/exportar-json`: todas as ~49 tabelas do schema (introspeccao dinamica via
  `sqlite_master`, nunca lista fixa), estrutura `{"versao", "exportado_em", "tabelas": {...}}`.
- `GET /api/backup/exportar-csv-completo`: mesmo dado num `.zip` (um `.csv` por tabela).
- Botao "exportar tudo agora" no cabecalho (toggle igual o de silencio), com as 3 opcoes
  (banco `.db`, JSON, CSV).
- Backup automatico semanal (domingo 3h, via scheduler existente) em `BACKUP_DIR` (padrao
  `data/backups/`), mantem os ultimos 8, manda pro Telegram se ja configurado
  (`telegram_bot.enviar_documento`, novo). Falha (disco cheio, Telegram fora do ar) so loga,
  nunca derruba o scheduler.
- `docs/BACKUP.md` novo.

**Item 2 - Resiliencia offline**
- Fila em IndexedDB (`static/js/fila-offline.js`) so pras 2 acoes criticas pedidas
  (`/api/capture`, `/api/checkin`) - decisao: so no JS da pagina, nao no Service Worker
  (Background Sync API nao existe no Safari/iOS, o aparelho do Alex).
- `apiFetch` ganhou um 3o parametro opcional (`fila`) - sem ele, ~200 chamadas existentes
  continuam identicas. Falha de rede real (nunca uma resposta HTTP de verdade) enfileira,
  mostra card provisorio, sincroniza sozinho (evento `online` + poll de 45s de reforco).
- Idempotencia no servidor por `client_id` (tabela `capture_idempotency`, limpeza automatica
  >7 dias) - reenvio da fila nao duplica tarefa/gasto.
- Banner discreto de "sem conexao" com contador de itens pendentes.

**Item 3 - Criptografia em repouso**
- Fernet (`cryptography`) campo a campo, escopo restrito: `bank_accounts.saldo`,
  `bank_transactions.descricao/valor` (Open Finance) e `saude_dados`, `medidas_corporais.valor`,
  `medicamentos.nome/dosagem/horario` (saude). Chave em `ENCRYPTION_KEY` (opcional - sem ela o
  app funciona 100% normal, so em texto plano, com aviso em 3 lugares: log, `GET
  /api/seguranca/status`, UI). Gerar com `scripts/gerar_chave_criptografia.py`.
- Migracao do dado ja existente na subida do app (uma vez, flag em `configuracoes`).
- Colunas que precisaram virar agregacao/filtro em Python (nao dava mais pra `WHERE`/`SUM`/
  `ORDER BY` direto): resumo bancario, media de passos, correlacao sono x produtividade, sono
  x humor, cobranca generica sem rotulo, ordenacao de medicamento por horario.
- `docs/SEGURANCA.md` novo.

**Item 4 - Correcao rapida de classificacao**
- `POST /api/tasks/<id>/reclassificar` (tarefa -> gasto, apaga subtasks e avisa quantas),
  `POST /api/expenses/<id>/reclassificar` (gasto -> tarefa), `POST /api/expenses/<id>/categoria`
  - tudo em 1-2 toques, sem apagar e recriar.
- Aprendizado leve: correcao vira contexto extra no prompt do `classify_capture` quando um
  texto novo bate por token com uma correcao anterior (`aprendizado.correcao_semelhante`, mesmo
  espirito de `dias_atraso_por_titulo_semelhante`) - a IA continua decidindo, nunca um override
  silencioso em Python (diferente de `apelidos_gasto`, onde o "erro" e so um nome; aqui pode ser
  o tipo inteiro da captura).

**Correcoes da revisao independente**
- `Infinity`/`NaN`/bool passavam pela validacao de `valor` em `/api/tasks/<id>/reclassificar` e
  viravam `expenses.amount = inf`, contaminando soma/media do mes: agora recusado (`400`), mesmo
  padrao `math.isfinite` ja usado no resto do app.
- Export JSON/CSV completo devolvia os campos criptografados como token Fernet cru (ilegivel,
  contradizendo a propria `docs/BACKUP.md`): agora sai descriptografado (rota autenticada, mesmo
  acesso que a tela ja mostra) - o backup `.db` bruto continua cifrado de proposito.
- **`ENCRYPTION_KEY` presente mas malformada (colada errada no `.env`) derrubava o app inteiro
  na subida** quando ja havia dado sensivel gravado (a migracao chamava `criptografar()` num
  loop sem tratamento). Corrigido: `criptografia._fernet()` nunca levanta mais, degrada pro
  mesmo caminho de "sem chave" com um aviso especifico; `configurada()` passou a exigir chave
  presente E valida, pra uma chave invalida nunca marcar a migracao como "ja feita" por engano.
- Achado do proprio processo (nao do codigo): o isolamento por worktree do ambiente so cobre o
  repositorio principal da sessao, nao um repo irmao como este - 3 dos 4 agentes em paralelo
  compartilharam o mesmo checkout sem isolamento de verdade (o 4o percebeu e criou o proprio
  `git worktree`). Nenhum dado se perdeu, mas a integracao precisou de um merge git real.
  Registrado no `TODO.md` pra a proxima sessao saber disso.

## 2026-09-23 (24) - Correcoes da revisao independente da Fase 3

Segundo agente revisor (so leitura) atacou o commit da Fase 3 com scripts. Tudo corrigido, com
teste em `tests/test_vida_revisao.py` (e os scripts de ataque do revisor rodados de novo).

**Seguranca do "Salvos pra ver depois" (`leitura.py` reescrito)**
- **SSRF com barra invertida** (`http://127.0.0.1:porta\@example.com/`): o validador via
  `example.com` mas o `requests` conectava no 127.0.0.1. Agora: URL com `\` ou usuario/senha e
  recusada, os dois parsers (urllib e urllib3) tem que concordar sobre host e porta, e - o
  principal - o host e resolvido uma vez so e a conexao vai **direto pro IP validado** (SNI e
  certificado conferidos no nome original, via adaptador proprio). Isso fecha tambem o
  **DNS rebinding** (publico na checagem, 127.0.0.1 na conexao).
- IPv6 com IPv4 embutido (`::127.0.0.1`, NAT64 `64:ff9b::/96`) recusado.
- **Prazo total de 20s** (servidor que pinga 1 byte/s prendia o unico worker do gunicorn) e
  **sem compressao** (`Accept-Encoding: identity`; pagina compactada mesmo assim e recusada) -
  nada de bomba gzip, independente da versao do urllib3.
- **Parsing linear**: as regex de `<script>`/`<meta>`/`<title>` sem fechar eram quadraticas
  (400KB = 115s de CPU); agora 1,5MB hostil leva menos de 0,2s.
- Charset: do cabecalho, senao do `<meta charset>`, senao utf-8 (antes ISO-8859-1 embaralhava
  acento); charset inexistente nao derruba mais.
- Links estranhos (`http://[::1`, rotulo de 64 letras, `a..b`, redirect pra `http://[::1`)
  davam 500: agora 400 "link invalido" ou "link ficou salvo" conforme o caso.

**Outros**
- `/api/metas` dava 500 com deposito simbolico (R$ 1 numa meta de R$ 1 milhao = data no ano
  2800+): previsao acima de 50 anos vira "sem previsao".
- Deposito `1e999` na meta era aceito e depois derrubava `/api/progresso`: recusado na entrada.
- `/api/revisao-mensal?mes=9999-12` dava 500: ano fora de 2000-2100 e 400.
- **"Como foi o voo?" nunca chegava pra voo das 20h+** (caia no silencio da noite e sumia): voo
  de ontem sem diario pergunta de manha, ate o meio-dia.
- **Responder o "Como foi o voo?" no chat criava um voo duplicado**: `registrar_voo` com mesma
  data e destino de um voo sem diario agora completa o existente.
- **Projecao do fim do mes ignorava conta vencida e nao paga**: entra no "ainda vai sair".
- Revisao mensal sai do dia 1 ao 3 (servidor fora do ar no dia 1 nao perde o mes).
- Detalhes: tema de estudo longo diz "tema muito longo" (antes "informe o tema") e nota longa e
  cortada em 300; "visto" sozinho nao e mais burocracia ("ja tinha visto") - so "visto
  americano/de turista/..."; `app_eventos` guarda so 60 dias; "humor mais comum" virou "humor na
  media" (e uma media).
- Mantido de proposito: progresso usa a mesma data (UTC do SQLite) que a aba Gastos, pra os
  totais baterem entre as telas.

## 2026-09-23 (23) - Fechamento do BRIEFING: guia de Atalhos e credenciais

- **`docs/ATALHOS.md`**: passo a passo das automacoes do iPhone - casa (chegou/saiu com
  bateria), mercado, uso de apps (uma automacao por app, abriu/fechou), Saude, e o que ja existia.
  Inclui os limites reais da Apple (banner obrigatorio na localizacao, Screen Time ilegivel,
  geofence pode atrasar).
- `.env.example`: `PAINEL_ATALHOS_TOKEN` agora explica que localizacao/apps precisam dele e como
  gerar. README aponta pro guia. `TODO.md` ganhou a lista exata de credenciais.
- Bateria do Atalho pode vir quebrada (47.5) ou como texto ("47"): arredonda em vez de ignorar.
- Pessoa com o mesmo nome (sem acento/caixa) pelo formulario atualiza a frequencia em vez de
  duplicar - o chat ja fazia isso, agora os dois usam `_salvar_pessoa`.
- "Quero aprender" recem-criado mostra "adicionado hoje" (antes dizia "mexeu hoje").
- Artifact de demonstracao atualizado com a aba Vida (dados de um servidor real semeado).

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
