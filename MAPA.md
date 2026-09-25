# MAPA - Repositório painel-pessoal-tdah

## D1 - Tokens de Cor

| Arquivo | Linha | Elemento/Função | O que faz |
|---------|-------|-----------------|-----------|
| static/css/ui/tokens.css | 20-115 | :root variáveis | Define raios, espaço (grade 8px), superfícies, bordas, elevação, tipografia, movimento, toque, z-index |
| static/css/style.css | 6-105 | --bg, --surface, --cor-* | Preto puro (#000000), cores por aba (painel verde #41aa75, tarefas roxo #5246d8, financeiro azul #04759a, etc) |
| static/css/style.css | 502-529 | body background | Gradiente radial aurora (roxo, azul, verde) que tinge o fundo |
| static/css/style.css | 175-191 | --glass-* | Vidro tingido: --glass-bg (surface-2), --glass-border (tint + strong), --glass-glow (radial) |
| static/css/fase7.css | 1-28 | @import order | Carrega tokens → componentes → abas → seções |

## D2 - Card "Como você tá hoje" + LED de Conclusão

| Arquivo | Linha | Elemento/Função | O que faz |
|---------|-------|-----------------|-----------|
| templates/secoes/hoje/checkin.html | 1-6 | #checkin-box | Card com título "Como você tá hoje?" e área de linhas de opcões |
| static/css/secoes/hoje/checkin.css | — | .checkin-linha, .checkin-opcao | Estilo das opções (energia, foco, humor, etc) |
| static/js/secoes/hoje/checkin.js | 5-36 | CHECKIN_CAMPOS, loadCheckin() | Define campos e carrega estado via /api/checkin/hoje |
| static/css/ui/componentes/campo.css | 104-160 | input[type=checkbox] | Checkbox customizado (quadrado preto → verde ao marcar) |
| static/css/style.css | 2305 | .linha-do-tempo li.item.concluido | Marca tarefa como concluída na timeline |

## D3 - Topo da Aba Hoje (Chat, Hiperfoco, Comando de Voz)

| Arquivo | Linha | Elemento/Função | O que faz |
|---------|-------|-----------------|-----------|
| templates/abas/hoje.html | 3-11 | {% include ordem %} | Saudação → Sobrecarga → Prévia Noite → Rotina → Checkin → Essencial → Hiperfoco → Chat → Visão do Dia |
| templates/secoes/hoje/chat.html | 1-7 | #chat-mensagens, #chat-form, #chat-mic | Lista de mensagens, input de texto, botão de microfone |
| static/css/secoes/hoje/chat.css | — | .chat-lista, .chat-form | Layout flexível coluna com input fixo embaixo |
| templates/secoes/hoje/hiperfoco.html | 1-12 | #hiperfoco-box, #hiperfoco-ativo | Estado inativo (botão iniciar) e ativo (mostra tempo restante, botão encerrar) |
| static/css/style.css | 1241-1267 | #comando-voz-btn | Botão circular flutuante de comando de voz (reutiliza #comando-voz-btn das abas) |

## D4 - Checkbox (Seletores CSS)

| Arquivo | Linha | Seletor CSS | O que faz |
|---------|-------|-------------|-----------|
| static/css/ui/componentes/campo.css | 109-160 | input[type="checkbox"] | Base: cubo 20px preto, ::before arredondado com check |
| static/css/ui/componentes/campo.css | 140-145 | input[type="checkbox"]:checked | Verde (#5246d8) ao marcar |
| static/css/ui/componentes/campo.css | 150-155 | input[type="checkbox"]:hover:not(:disabled) | Borda mais forte no hover |
| static/css/ui/componentes/campo.css | 160 | input[type="checkbox"]:focus-visible | Anel de foco visível |
| static/css/ui/componentes/campo.css | 168 | input[type="checkbox"]:not(label *)::after | Espaçador invisível se fora de label |

## D5 - Visão do Dia

| Arquivo | Linha | Elemento/Função | O que faz |
|---------|-------|-----------------|-----------|
| templates/secoes/hoje/visao-do-dia.html | — | #visao-dia-periodo-dia, #visao-dia-foco, #visao-dia-timeline | Botões período (dia/semana/mês), box de foco atual, timeline com tarefas |
| static/css/secoes/hoje/visao-do-dia.css | — | .visao-dia-*, .visao-dia-foco-* | Estilo de cards período, status, cards de tarefa na timeline |
| static/js/visao-dia.js | 10-110+ | VisaoDia.init(), formatarDia(), renderVisao(), mudarPeriodo() | Módulo que carrega /api/visao-dia/(hoje|periodo), renderiza timeline e foco |
| static/js/secoes/hoje/visao-do-dia.js | — | loadVisaoDia() | Hook de carga da aba Hoje |

## D6 - Clima

| Arquivo | Linha | Função/Rota | O que faz |
|---------|-------|------------|-----------|
| clima.py | 28-231 | geocodificar_cidade(), previsao_para_data(), previsao_para_cidade_e_data(), previsao_proximos_dias(), resumo_chuva_do_dia(), resumo_chuva_hoje_para_cidade() | Integra Open-Meteo (sem chave), geocodifica, prevê chuva e temp por cidade e data |
| app.py | ~6800+ | @app.route("/api/clima/hoje"), @app.route("/api/clima/metar") | Endpoints que retornam clima do dia e METAR (aviação) |
| static/js/secoes/hoje/saudacao.js | 31-53 | loadClima(), evento de visibilidade | Carrega clima via /api/clima/hoje a cada 5min, exibe em chip na saudação |
| templates/secoes/hoje/saudacao.html | 17-19 | #clima-chip, #clima-texto | Chip com ícone de nuvem e texto "X% chuva, YYZ°C em Cidade" |

## F1 - Banco/Pluggy (OFX, Contas, Transações)

| Arquivo | Linha | Função/Rota | O que faz |
|---------|-------|------------|-----------|
| pluggy_client.py | 20-89 | configurado(), create_connect_token(), get_item(), get_accounts(), get_transactions(), normalizar_transacoes() | Integra Pluggy (open banking), cria token Connect, busca contas e transações |
| bank_ofx.py | 7-28 | decode_ofx(), parse_transactions() | Decodifica OFX de bytes, extrai transações (data, valor, descrição) |
| app.py | 7771-7970 | @app.route("/api/bancos/importar"), @app.route("/api/bancos"), @app.route("/api/bancos/<id>/transacoes"), @app.route("/api/bancos/sync-status"), @app.route("/api/bancos/conectar/token"), @app.route("/api/bancos/conectar/finalizar") | Upload OFX, lista contas, transações, sincroniza Pluggy, fluxo Connect |
| db.py | 125-142 | CREATE TABLE bank_accounts, CREATE TABLE bank_transactions | Armazena contas (id, instituição, saldo, limite) e transações (data, valor, categoria) |
| static/js/secoes/bancos/bancos.js | — | loadBancos(), importarOFX(), sincronizarPluggy() | Carrega contas e botões de ação |
| static/js/secoes/bancos/ofx.js | — | handleOFXUpload() | Processa upload/drop de arquivo OFX |

## F2/F3 - Assinaturas + Avisos Proativos

| Arquivo | Linha | Função/Rota | O que faz |
|---------|-------|------------|-----------|
| financas_recorrentes.py | 155-474 | criar_assinatura(), obter_assinatura(), listar_assinaturas(), atualizar_assinatura(), cancelar_assinatura(), _assinatura_cobra_no_mes() | CRUD de assinaturas (nome, valor, ciclo, data início/fim) e lógica de cobrança mensal |
| rotas/n1_financas.py | 43-132 | @app.route("/api/assinaturas"), CRUD handlers | Endpoints de listar/criar/atualizar/cancelar assinaturas |
| templates/secoes/gastos/assinaturas.html | — | #assinaturas-lista, .assinatura-card | Lista de cards com assinaturas ativas, botões de editar/cancelar |
| static/js/secoes/gastos/assinaturas.js | — | loadAssinaturas(), criar(), atualizar(), cancelar() | Carrega via /api/assinaturas, renderiza cards, submete mudanças |
| assistente/gatilhos/ | — | p2_perguntas.py, p3_briefing.py, p4_regras.py, p5_replanejar.py, p9_memoria.py | Disparam perguntas, briefing, regras, replano, memória em horários configuráveis |
| assistente/avisos.py | 188-430 | TIPO_POR_ORIGEM, tipo_de_origem(), definir_tipo(), aviso_permitido() | Mapeia origem→tipo (assinatura, fatura, lembrete), gere silêncio global, define canal |

## Estrutura (Abas, Service Worker, Donos)

| Arquivo | Linha | Elemento/Função | O que faz |
|---------|-------|-----------------|-----------|
| templates/abas/ | — | assistente.html, aviacao.html, bancos.html, construtora.html, gastos.html, hoje.html, painel.html, tarefas.html, vida.html | Nove abas principais, cada uma com seus includes de seção |
| static/service-worker.js | 34-210 | CACHE_NAME = "painel-pessoal-v15", ASSETS[], event listeners | Precache versioned, network-first/cache-first strategies, limpeza de caches antigos |
| donos.json | — | _comentario, faixas | Mapeia dono de cada arquivo (faixa) — _comentario é informativo, faixas é o dict de padrões |
| scripts/checar_donos.py | — | main(), validar_sobreposicoes(), validar_faixa() | Valida que nenhum arquivo pertence a duas faixas, pode checar diff de um branch |

## Fase 9 - Finanças e abas

### Backend: Rotas e Integrações

| Arquivo | Linhas | Função/Rota | O que faz |
|---------|--------|-------------|----------|
| rotas/f8_banco.py | 36-46 | `_normalizar_nome()`, `_cobranca_bate_com_gasto()` | Normaliza nomes de estabelecimentos, compara cobrança com gasto para duplicatas |
| rotas/f8_banco.py | 71-87 | `cruzar_proximas_cobrancas_com_gastos()` | Junta transações pendentes de fechamento com histórico de gastos |
| rotas/f8_banco.py | 88-120 | `_montar_gastos_unificados()` | Agrega gastos real (cartão + débito) com pendências, monta lista unificada |
| rotas/f8_banco.py | 132-177 | `@bp.route("/api/bancos/sincronizar-nubank", POST)` | Sincroniza transações do Pluggy, normaliza, insere no banco |
| rotas/f8_banco.py | 178-190 | `@bp.route("/api/gastos/unificados", GET)` | Retorna gastos do mês com reais + pendências, pagos separado de pendente |
| rotas/f8_banco.py | 191-206 | `@bp.route("/api/gastos/proximas-cobrancas", GET)` | Lista fechamentos de cartão não batidos, valor em aberto |
| pluggy_client.py | 20-47 | `configurado()`, `_api_key()`, `_headers()` | Verifica config, carrega chave do .env, monta headers de autenticação Pluggy |
| pluggy_client.py | 49-68 | `create_connect_token()`, `get_item()`, `get_accounts()`, `get_transactions()` | Fluxo Connect (token), lista contas, busca transações de uma conta |
| pluggy_client.py | 91-103 | `normalizar_transacoes()` | Converte resposta Pluggy (merchant, category, date) em formato interno |

### Backend: Rotas app.py (Bancos, Gastos, Patrimônio, Metas, Assinaturas)

| Linha | Rota | Método | O que faz |
|-------|------|--------|-----------|
| 1277 | `/api/gastos-fixos` | GET | Lista gastos mensais fixos (aluguel, internet, etc) |
| 1529 | `/api/gastos/resumo-semanal` | GET | Retorna gasto acumulado por dia da semana |
| 6179 | `/api/assinaturas/revisao` | GET | Lista assinaturas para revisão (com data próxima cobrança) |
| 6187 | `/api/assinaturas/revisao` | POST | Atualiza revisão de assinatura (marcada, pendência, motivo) |
| 7771 | `/api/bancos/importar` | POST | Upload de OFX, processa transações |
| 7805 | `/api/bancos` | GET | Lista contas com saldo, limite, último sync |
| 7847 | `/api/bancos/<id>/limite` | POST | Atualiza limite de crédito de uma conta |
| 7891 | `/api/patrimonio` | GET | Retorna patrimônio (contas + investimentos) |
| 7910 | `/api/bancos/<id>/transacoes` | GET | Lista transações de uma conta (últimos 100) |
| 7920 | `/api/bancos/sync-status` | GET | Status do último sync com Pluggy (timestamp, sucesso/erro) |
| 7959 | `/api/bancos/conectar/token` | POST | Gera token de conexão Pluggy |
| 7970 | `/api/bancos/conectar/finalizar` | POST | Finaliza fluxo Connect (salva conta nova no banco) |
| 8009 | `/api/metas` | GET | Lista metas de poupança com progresso |
| 8024 | `/api/metas/<id>/guardar` | POST | Registra depósito em meta |
| 8043 | `/api/metas/<id>/historico` | GET | Histórico de depósitos de uma meta |

### Backend: Tabelas (db.py)

| Linhas | Tabela | Colunas principais | O que armazena |
|--------|--------|-------------------|-----------------|
| 107-123 | `expenses` | id, data, valor, categoria, tipo, descricao, pago, pago_em | Gastos reais (débito + crédito) com categorias |
| 125-133 | `bank_accounts` | id, instituicao, saldo, limite, tipo, sincronizado_em | Contas corrente/poupança, cartões com saldo e limite |
| 134-143 | `bank_transactions` | id, account_id, data, valor, categoria, descricao, pluggy_id | Transações Pluggy normalizado, evita duplicata via pluggy_id |
| 145-160 | `goals` | id, nome, valor_alvo, valor_atual, criado_em, prazo | Metas de poupança com progresso |
| 424-441 | `assinaturas_revisao` | id, assinatura_id, data_proxima_cobranca, em_revisao, motivo_revisao | Rastreamento de assinaturas em revisão |

### Frontend: Abas (templates/abas/*.html)

| Arquivo | Linhas | Elemento | O que faz |
|---------|--------|----------|-----------|
| gastos.html | — | #aba-gastos | Inclui assinaturas, metas, resumo semanal, histórico gastos |
| bancos.html | — | #aba-bancos | Inclui sincronização Pluggy, OFX upload, saldo de contas, transações |
| vida.html | — | #aba-vida | Inclui 20 seções (hábitos, projetos, agenda, compras, pessoas, treino, contas, manutenção, garantia, viagens, lugares, presentes, aprender, salvos, mensagem difícil, vale a pena, progresso, revisão) |
| painel.html | — | #aba-painel | Inclui fechamento, medicamentos, datas, agenda hoje, peso, notas, brain dump, esperando resposta, diário decisão, resumo, memória, devo sair |
| hoje.html | — | #aba-hoje | Chat, hiperfoco, clima, saudação, checkin, essencial, rotina, prévia noite |
| tarefas.html | — | #aba-tarefas | Timeline de tarefas, prioridades, hiperfoco integrado |
| aviacao.html | — | #aba-aviacao | Voos, simulador, docs de aviação |
| construtora.html | — | #aba-construtora | Contas a pagar empresa, cotações materiais |
| assistente.html | — | #aba-assistente | Chat com IA, briefing, regras, avisos |

### Frontend: Navegação e Seções

| Arquivo | Linhas | Elemento | O que faz |
|---------|--------|----------|-----------|
| templates/navegacao.html | 1-44 | nav#tabbar | 9 botões de abas (Hoje, Painel, Vida, Tarefas, Financeiro, Bancos, Construtora, Aviação, Assistente) |
| templates/secoes/bancos/bancos.html | — | #bancos-list, .conta-card | Cards de contas com saldo, limite, botão sincronizar Pluggy |
| templates/secoes/bancos/ofx.html | — | #ofx-upload, input[type=file] | Zona de drop/upload de arquivo OFX |
| templates/secoes/gastos/gastos.html | — | #gastos-chart, #gastos-list | Gráfico de gastos, lista de transações por data |
| templates/secoes/gastos/assinaturas.html | — | #assinaturas-lista, .assinatura-card | Cards de assinaturas com botões editar/cancelar |
| templates/secoes/gastos/metas.html | — | #metas-lista, .meta-card | Cards de metas com progresso barra |

### Frontend: JavaScript (static/js/secoes/)

| Arquivo | Funções top-level | O que faz |
|---------|------------------|-----------|
| static/js/secoes/bancos/bancos.js | `criarItemBanco()`, `criarLimiteCartaoBox()`, `loadBancos()`, `carregarPluggyScript()` | Renderiza cards de conta, limite cartão, carrega via /api/bancos, inicia fluxo Connect |
| static/js/secoes/bancos/ofx.js | `atualizarOfxLabel()` | Controla label do upload OFX (drag/drop feedback) |
| static/js/secoes/gastos/assinaturas.js | `numeroFinancas()`, `fmtMoedaFinancas()`, `fmtDataFinancas()`, `textoFinancas()`, `loadAssinaturas()`, `loadAssinaturasAtivas()`, `loadComprometido()` | Formatadores, renderiza assinaturas, mostra impacto na fatura |
| static/js/secoes/gastos/gastos.js | (funções de gráfico) | Renderiza gráfico de gastos |
| static/js/secoes/gastos/metas.js | (funções de meta) | Renderiza metas e histórico |

### Frontend: CSS

| Arquivo | Linhas | Variáveis/Seletores | O que define |
|---------|--------|---------------------|--------------|
| static/css/ui/tokens.css | 20-152 | `--raio-*`, `--espacamento-*`, `--superficies-*`, `--tipografia-*`, `--movimento-*`, `--z-*` | Tokens globais de design (raios, espaço, cor, tipografia, animação, z-index) |
| static/css/secoes/gastos/* | — | `.gasto-*, .assinatura-*, .meta-*` | Estilo de cards, gráficos e listas de gastos |
| static/css/secoes/bancos/* | — | `.conta-*, .ofx-*` | Estilo de cards de conta e upload OFX |

### Vida - Seções (20 arquivos em templates/secoes/vida/)

| id | Nome | Arquivo | Resumo |
|----|------|---------|--------|
| habitos | Hábitos | habitos.html | Rastreamento diário de hábitos (exercício, meditação, leitura, etc) |
| projetos | Projetos | projetos.html | Lista de projetos em andamento com progresso |
| agenda | Agenda | agenda-painel.html | Calendário de eventos importantes |
| compras | Lista de Compras | lista-de-compras.html | Items a comprar com status |
| pessoas | Pessoas | pessoas.html | Contatos com última vez que conversou |
| treino | Treino | treino.html | Fichas e histórico de exercícios |
| contas | Contas Pessoais | contas-pessoais.html | Credenciais e logins (criptografado) |
| manutencao | Manutenção | manutencao.html | Agendamento de manutenções (carro, casa, etc) |
| garantia | Garantia | garantia.html | Documentos de garantia e validade |
| viagens | Viagens | viagens.html | Destinos planejados com datas |
| lugares | Lugares | lugares.html | Recomendações (restaurante, loja, etc) |
| presentes | Presentes | ideias-de-presente.html | Ideias de presente para amigos/família |
| aprender | Aprender | quero-aprender.html | Tópicos para estudar |
| salvos | Salvos | salvos.html | Bookmarks, artigos, vídeos |
| mensagem_dificil | Mensagem Difícil | mensagem-dificil.html | Rascunhos de mensagens difíceis |
| vale_a_pena | Vale a Pena | vale-a-pena.html | Análise de decisões financeiras |
| progresso | Progresso | seu-progresso.html | Histórico de metas e conquistas |
| revisao | Revisão | revisao-trimestral.html | Checklist de revisão trimestral |
| pra_responder | Pra Responder | pra-responder.html | Perguntas abertas em espera |
| ainda_usa | Ainda Usa | ainda-usa.html | Itens/assinaturas questionáveis |

## Pendências/Observações

- `static/js/secoes/hoje/visao-do-dia.js`: Arquivo vazio ou comentários apenas (funções estão em `static/js/visao-dia.js`).
- `static/css/secoes/hoje/chat.css`: Referenciado mas não listado — precisa confirmação se existe ou é inline no style.css.
- `ia/funcoes/visao.py`: Mencionado em buscas mas não mapeado (funções de IA para descrição da visão do dia).
- Rotas de chat, hiperfoco, saudação em `app.py`: Procuradas mas não em resultado (grep incompleto, podem estar em rotas/ ou dentro de app.py com @app.route customizado).
- Assistente: Estrutura de gatilhos está implementada mas ponte com IA/LLM não foi explorada aqui (escopo era mapeamento estático).
