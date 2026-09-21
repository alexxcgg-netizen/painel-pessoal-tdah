# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

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
