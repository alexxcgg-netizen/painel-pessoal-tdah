# Histórico de Versões (Changelog) - Painel Pessoal (Alex)

Este arquivo documenta as mudanças relevantes no painel pessoal, por dia de trabalho.
Serve como memória base para futuras sessões de IA - sem isso, cada sessão nova tem que
reconstruir contexto lendo o `git log` inteiro. Ver também `README.md` pra visão geral das
features e da integração com o painel da construtora (`financeiro-construtora`, outro repo).

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
