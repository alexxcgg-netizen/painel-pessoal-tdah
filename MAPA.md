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

## Pendências/Observações

- `static/js/secoes/hoje/visao-do-dia.js`: Arquivo vazio ou comentários apenas (funções estão em `static/js/visao-dia.js`).
- `static/css/secoes/hoje/chat.css`: Referenciado mas não listado — precisa confirmação se existe ou é inline no style.css.
- `ia/funcoes/visao.py`: Mencionado em buscas mas não mapeado (funções de IA para descrição da visão do dia).
- Rotas de chat, hiperfoco, saudação em `app.py`: Procuradas mas não em resultado (grep incompleto, podem estar em rotas/ ou dentro de app.py com @app.route customizado).
- Assistente: Estrutura de gatilhos está implementada mas ponte com IA/LLM não foi explorada aqui (escopo era mapeamento estático).
