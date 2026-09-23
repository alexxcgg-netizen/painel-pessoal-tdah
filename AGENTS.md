# AGENTS.md — regras operacionais + padrões descobertos (painel-pessoal-tdah)

Este arquivo é complementar ao `CLAUDE.md` (que tem as regras gerais do projeto, incluindo
o isolamento em relação ao `financeiro-construtora`). `CLAUDE.md` é a regra principal;
este arquivo guarda duas coisas específicas:

1. **Regras operacionais obrigatórias pra qualquer história/tarefa a partir da Fase 5**
   (seção abaixo).
2. **Padrões, pegadinhas e convenções descobertos durante o trabalho** — uma seção viva
   que cada história deve alimentar, não só `TODO.md`/`progress.txt`. Se você (agente)
   tropeçou em algo não-óbvio do código, descobriu uma convenção implícita, ou bateu numa
   pegadinha que outro agente provavelmente vai bater de novo — anote aqui, curto, com o
   arquivo/linha de referência quando fizer sentido.

## Regras obrigatórias a partir da Fase 5 (pedido explícito do Alex, 2026-09-23)

Valem pra toda história daqui pra frente. Histórias que já passaram (`"passes": true` no
`prd.json` antes desta regra existir) não precisam ser refeitas.

### 1. Atualizar este arquivo (AGENTS.md) a cada história
Além de `TODO.md`/`CHANGELOG.md`/`progress.txt`, toda história que terminar deve deixar
uma linha na seção "Padrões descobertos" abaixo se encontrou algo que vale a pena um
próximo agente saber antes de mexer na mesma área do código. Não precisa forçar uma
entrada se não descobriu nada novo — é pra ser útil, não burocracia por burocracia.

### 2. Checagem de segredo antes de cada commit
Antes de QUALQUER `git commit` (não só no fim da história), rodar:
```
gitleaks detect --source . --no-banner --redact
```
(`gitleaks` já está instalado e no PATH). Se detectar algo, **não commitar** — investigar
primeiro (pode ser falso positivo, ex: uma chave de exemplo claramente fake num `.env.example`
já existente; se for, ok seguir, mas confirme que é isso mesmo antes). Se for credencial
real ou dado sensível de teste (CPF real, número de cartão, etc) que acabou de ser
digitado/gerado num teste, remover do arquivo antes de commitar — nunca "commitar e
remover depois", porque já fica no histórico do git.

### 3. Auditoria de dependência nova antes de fechar a história
Se a história adicionou uma biblioteca nova:
- **Python** (`requirements.txt` mudou): rodar
  `.venv/bin/pip install -r requirements.txt && .venv/bin/pip-audit` (pip-audit já
  instalado no venv compartilhado) antes de marcar `"passes": true`. Vulnerabilidade
  crítica/alta encontrada → trocar de versão/lib se der, ou documentar no `notes` da
  história por que foi aceita mesmo assim (ex: sem fix disponível, risco não se aplica ao
  nosso uso).
- **JS/Node** (novo `package.json` ou dependência nova nele - hoje o projeto NÃO usa npm,
  é JS vanilla + Node só como test runner; se alguma história introduzir isso de fato):
  rodar `npm audit` no diretório com o `package.json` antes de fechar a história.
- História sem lib nova nenhuma: esta regra não se aplica, pode pular.

### 4. Smoke-test depois de integrar cada grupo (não é por história individual)
Isso é responsabilidade de quem faz a integração de um grupo inteiro na `main` (não de
cada história isolada) — depois do merge de um grupo (A, B, C ou D) e da suíte de testes
completa passando, também confirmar que o app de fato sobe e a tela principal carrega:
```
ANTHROPIC_API_KEY=teste-fake .venv/bin/python -c "
import tempfile
from pathlib import Path
import db
tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(tmp.name) / 'painel.db'  # NUNCA import app contra data/painel.db real (ver regra 6) - esse arquivo ja existe de verdade neste checkout
import app
"
```
**Nunca rode isso com `DB_PATH` apontando pro `data/painel.db` real** - já existe um banco
de verdade neste checkout (não é hipotético), e `init_db()`/qualquer import de `app.py`
escreveria nele de verdade. Sempre sobrescreva `db.DB_PATH` pra um diretório temporário
antes de importar `app`, igual todo o resto (regra 6). O objetivo é só confirmar "o
processo sobe sem erro de import/sintaxe que teste unitário isolado pode não pegar", não
um teste completo de UI - pra abrir de verdade e ver a tela renderizando, ver regra 5
(Playwright), que já sobe o servidor em thread com `DB_PATH` isolado do mesmo jeito.
Se o smoke-test falhar, é bloqueador — não considerar a integração daquele grupo concluída
até resolver.

### 5. Verificação visual real (headless) pra história de interface
Toda história que criar/mudar uma TELA (widget, navegação por voz, diário de decisão,
brain dump, qualquer UI nova) precisa ser aberta de verdade num navegador headless antes
de marcar `"passes": true` — teste unitário sozinho não é suficiente pra história de UI.

Ambiente já tem Chromium pré-instalado e Playwright configurado, mas com uma pegadinha de
versão: o pacote `playwright` (Python, já adicionado ao `requirements.txt`) baixado via pip
pode não bater com o Chromium pré-instalado em `/opt/pw-browsers`. Sempre lance passando o
executável explícito, não deixe o Playwright decidir sozinho:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",  # confira se esse caminho ainda existe; se a versao do chromium pre-instalado mudou, ajuste
        headless=True,
    )
    page = browser.new_page()
    page.goto("http://localhost:5000/rota-da-tela-nova")  # subir o app antes (ver regra 4, mesmo principio)
    # screenshot pra conferencia visual, e/ou asserts de texto/elemento renderizado
    page.screenshot(path="/tmp/verificacao-tela.png")
    assert page.inner_text("h1") != ""  # exemplo - trocar pela asserção real da tela
    browser.close()
```

Não precisa de display real nem Xvfb — roda headless direto neste ambiente de nuvem. O
objetivo é confirmar que a tela renderiza (sem erro JS bloqueando, elemento esperado
aparece), não fazer um teste de UI exaustivo.

### 6. Nunca migração/teste contra o banco de produção real
Incidente real na Fase 4: um script de reprodução esqueceu de trocar `db.DB_PATH` antes de
chamar `db.init_db()` e chegou a tocar o banco real (`data/painel.db`). Corrigido
estruturalmente: `db.py` agora tem `db.garantir_banco_nao_producao()`, que levanta
`RuntimeError` se `DB_PATH` ainda apontar pro banco de produção real. Já está chamada logo
depois de toda sobrescrita de `DB_PATH` nos arquivos de teste existentes — ao escrever um
teste NOVO ou um script avulso de migração/reprodução/fuzzing, chame essa função
explicitamente logo depois de trocar `db.DB_PATH` e antes de qualquer `init_db()`/escrita:
```python
db.DB_PATH = Path(tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()  # nunca pule este passo num script novo
db.init_db()
```

## Padrões descobertos (viva - cada história acrescenta aqui quando relevante)

### Fase 6, Grupo F3-extra (Viagens/Lugares/Cotações/Aviação) - US-F11/F12/F13/F14
- **Pegadinha de teste real, pega na própria suíte**: qualquer rota GET com
  efeito colateral de rede (ex: `GET /api/lugares` faz backfill de geocode,
  US-F13) precisa do MESMO mock cobrindo TODAS as chamadas àquela rota no
  teste, não só a primeira. Um teste que faz `with patch(...): self.client.post(...)`
  e SÓ DEPOIS, fora do `with`, chama `self.client.get(...)` numa rota que
  também dispara a mesma dependência externa, escapa do mock silenciosamente
  e acaba batendo na API de verdade - pego numa rodada real da suíte
  completa (`test_erro_de_rede_na_criacao_nao_impede_o_lugar_de_ser_salvo`,
  `tests/test_fase6_f3_lugares_mapa.py`, corrigido envolvendo POST *e* GET
  no mesmo `with`). Rotas GET "inocentes" que na verdade escrevem/chamam
  rede (backfill, cache-refresh, etc) são as mais fáceis de esquecer disso.
- **`hidden` + `display` != `none` numa classe do MESMO elemento é uma
  pegadinha de especificidade CSS real** (achada na verificação headless da
  US-F13, `.lugar-mapa`): `[hidden] { display: none }` é a regra padrão do
  navegador, especificidade (0,1,0) igual a uma classe `.lugar-mapa { display:
  flex }` - quando as duas competem, quem vem DEPOIS na cascata (a
  folha de estilo do app, carregada depois do UA stylesheet) ganha, e o
  elemento "escondido" continua ocupando espaço na tela. Sempre que um
  elemento alternar `display` != `none`/`block` via classe E também usar o
  atributo `hidden` pra escondê-lo, adicionar `.classe[hidden] { display:
  none; }` explícito logo depois - não confiar só no atributo.
- **Card `projeto_viagem` (US-E13) ganhou um campo opcional novo,
  `marcos_planejamento`/`aviso_regra_pratica`** (US-F11, só quando a origem
  é viagem) - o renderizador (`static/js/cards-tipos.js`) já estava pronto
  pra crescer assim: campo ausente = bloco novo simplesmente não aparece,
  card genérico de Projeto nunca muda. Qualquer história futura que precise
  adicionar outro bloco opcional ao mesmo card deve seguir o mesmo padrão
  (campo novo em `cards.projeto_para_card`, checagem de presença no
  renderizador, nunca um `type` de card novo só pra isso).
- **Geocodificação (Nominatim) e qualquer chamada de API externa com
  política de 1 req/s só pode viver no backend** (nunca no navegador
  direto) - além de exigir User-Agent próprio (impossível de garantir vindo
  do `fetch` do navegador, que sempre manda o User-Agent do próprio
  navegador), múltiplas abas/dispositivos abertos ao mesmo tempo
  furariam qualquer throttle client-side. `geocode_nominatim.py` só é
  chamado por `app.py`; o front só lê o resultado já cacheado em
  `lugares.lat/lng/geocode_status`.
- **CDN externo (Leaflet, `cdn.jsdelivr.net`) pode falhar especificamente
  dentro do Chromium do Playwright neste ambiente sandboxed mesmo quando o
  `requests`/`curl` do backend Python alcança o mesmo host sem problema** -
  confirmado testando os dois lados antes de escrever qualquer suposição
  ("`fetch()` do navegador → Failed to fetch" vs "`curl` do shell → HTTP
  200" pro mesmo `cdn.jsdelivr.net`). Ao verificar uma tela que depende de
  CDN externo, sempre confirmar que o fallback/estado de erro renderiza
  direito (nunca assumir que vai carregar liso só porque o backend alcança
  a URL) - documentar quando isso acontecer, não tratar como bug do código.

### Fase 5, Grupo B (navegação por voz) - US-B1 a US-B6
- **`_classificar_intent(conn, texto)` em `app.py` é a fonte única da lógica de
  classificação de intent** - `/api/intent/classificar` (sessão) e
  `/api/atalho/comando-voz` (token, Siri, US-B4) só chamam essa função, nunca
  duplicam a lógica. Qualquer regra nova de classificação nasce ali.
- **O contrato fechado de `docs/INTENT.md` (`claude_client.ACOES_INTENT`) não
  tem nenhuma ação literalmente "destrutiva"** (tipo `deletar_tarefa`) - só
  pode GANHAR uma no futuro (regra: só aditivo). Até lá, `corrigir_ultimo` é
  tratado como quase-destrutiva (sobrescreve o último item) em
  `ACOES_DESTRUTIVAS` (`static/js/voz-comando.js`) - se uma ação de deletar
  de verdade for adicionada ao contrato um dia, adicionar ela lá também.
- **`parametros.tela` de `navegar_tela` é texto livre da IA**, sem enum fixo
  no prompt (`claude_client.INTENT_PROMPT`) - `resolverTela()` em
  `voz-comando.js` faz o de-para por sinônimo/substring normalizado (sem
  acento/caixa). Se `ORDEM_ABAS` (`app.js`) ganhar uma aba nova, adicionar os
  sinônimos dela em `MAPA_TELAS` também.
- **Padrão de UI reusável para "novo botão que fala com o painel"**: o mic
  button de comando de voz (`#comando-voz-btn`) é separado do `#chat-mic`
  existente de propósito - o `#chat-mic` só preenche o campo de texto do
  chat, nunca roteia ação nenhuma; misturar os dois teria quebrado o
  comportamento já testado do chat.
- **Execução de ação classificada NUNCA duplica lógica de captura/chat/nav**:
  `registrar_tarefa`/`registrar_gasto` delegam pro `enviarCaptura()` já
  existente (mesmo pipeline de classify_capture/fila offline/cards),
  `consultar`/`corrigir_ultimo` delegam pro `enviarChat()` já existente
  (tool-use), `navegar_tela` chama `showTab()`. `registrar_checkin` não tem
  formato de parâmetros confiável no contrato pra campo/valor (energia/
  sono/humor) - em vez de adivinhar errado, só abre a aba "hoje" onde o
  check-in de 1 toque (`static/js/vida.js`) já existe.
- **Web Speech API em Chromium headless (Playwright, `/opt/pw-browsers/...`)
  reporta `window.SpeechRecognition` como definido** mesmo sem back-end de
  reconhecimento de verdade (sem microfone/rede pro serviço do Google) - pra
  testar o fallback de "não suportado" (US-B1) é preciso remover a API via
  `page.add_init_script("delete window.SpeechRecognition; ...")` ANTES do
  primeiro load da página, não basta rodar num Chromium sem microfone.
- **`Failed to load resource ... 502` de `/api/summary/today` aparece no
  console mesmo numa página nova/limpa** nesse ambiente sandboxed (proxy de
  rede do container) - pré-existente, sem relação com nenhuma história do
  Grupo B; um smoke-test/Playwright que checa "zero erro de console" precisa
  filtrar mensagens de `Failed to load resource` (falha de rede reportada
  pelo navegador) separado de erro de JS de verdade (exception/throw).
- **`POST /api/intent/corrigir` (novo, US-B3) reusa
  `aprendizado.confirmar_padrao_intent(..., forcar_confianca_alta=True)`**
  - o mesmo mecanismo da US-A4 (correção manual vale mais que repetir 3x) -
  não criar um caminho de "aprendizado" paralelo pra isso.

### Fase 5, Grupo D (polimento visual) - US-D1 a US-D3
- **As telas novas do Grupo C já seguiam o padrão visual na maioria dos
  casos** (reaproveitam `secao-secundaria`, `dica-colapsavel`, `form-linha`,
  `li.item`, `ligarForm`/`pulsarSucesso`) - antes de escrever CSS/JS novo
  pra "aplicar o padrão", vale conferir se o componente já não herda tudo de
  graça por reuso de classe. Boa parte do trabalho de polimento acabou
  sendo achar os poucos componentes que NÃO seguiam o padrão, não recriar
  o padrão do zero.
- **Gap real encontrado (US-D1/US-D3): `.card-vida` (`style.css`) não tinha
  `animation: fadeInUp` nenhuma**, ao contrário de todo outro painel "glass"
  (`.stat-tile`, `li.item`, `#duvida-box`, `#comando-voz-confirmar`) - os
  cards que ligam via `[hidden]` (inclusive os 4 novos do Grupo C:
  `sobrecarga-box`, `previa-noite-box`, `revisao-periodo-box`,
  `patrimonio-box`, e também os antigos: `rotina-box`, `checkin-box`,
  `essencial-box`, `progresso-box`, `fim-mes-box`, `custo-ia-box`)
  apareciam com corte seco. Corrigido adicionando a mesma curva já usada
  nos irmãos (`fadeInUp 0.35s var(--ease-bounce) both`) - a animação
  reinicia sozinha ao sair de `display:none` pra `display:flex`, sem
  precisar de JS extra tipo `pulsarSucesso`.
- **Gap real encontrado (US-D2): o botão de comando de voz
  (`#comando-voz-btn`) só tinha feedback visual pro estado "ouvindo"
  (`.ouvindo`, `pulsarMic`) - o estado "processando" (entre o fim da
  escuta e a resposta do `/api/intent/classificar`) só tinha o texto
  pequeno `mostrarStatus("Entendendo...")`, sem nada no botão em si**
  (o listener `recognition.end` já tira `.ouvindo` antes da chamada assíncrona
  resolver). Corrigido reaproveitando o MESMO padrão já usado em todo
  formulário do app (`setBotaoCarregando`, spinner via `.spinner`/`girar`)
  em vez de inventar uma animação nova - `voz-comando.js` agora chama
  `window.setBotaoCarregando(btn, true/false, ...)` ao redor do
  `await window.apiFetch("/api/intent/classificar", ...)`, dentro de um
  `try/finally` pra nunca deixar o botão preso em "carregando" se a
  chamada falhar.
- **Widget de tela bloqueada (US-C1, `scriptable/widget_lockscreen.js`) já
  estava certo e não precisou de mudança**: o próprio arquivo já documenta
  (comentário no topo) por que NUNCA define cor/gradiente customizado nos
  slots de lock screen - o iOS renderiza esses slots monocromáticos e
  ignora/distorce cor customizada. "Aplicar o padrão visual" ali seria
  piorar, não polir - a US-D2 confirma isso como já resolvido, sem tocar
  no arquivo.
- **Padrão de verificação Playwright pra SPA de aba única (este projeto é
  1 só `index.html` com `<section class="tab-content" hidden>` por aba,
  trocadas via `window.showTab(nome)`, não rotas separadas)**: depois de
  `/configurar-pin` + `/login` (ver seção 5 acima), navegar só precisa de
  `page.evaluate("window.showTab('painel')")` (nomes: hoje/painel/vida/
  tarefas/gastos/bancos/construtora/aviacao, batem com `data-tab` dos
  botões da tabbar) - não precisa de `page.goto` por aba.

### Fase 6, Grupo E2 (módulos: Hábitos, Projetos, agenda iCloud, limite do cartão) - US-E12 a US-E15
- **`page.evaluate("window.showTab('vida')")` NÃO recarrega dado nenhum da
  aba Vida** (nem Hoje, nem Gastos) - só troca o `hidden` da `<section>`.
  `loadVidaAba()`/`loadVidaHoje()`/`loadFimMes()` só disparam dentro do
  listener de **click de verdade** no botão da tabbar
  (`document.querySelectorAll(".tab-btn").forEach(btn => btn.addEventListener("click", ...))`
  em `app.js`, perto do fim do arquivo) - `showTab()` sozinho não acorda
  esse listener. Pra verificação visual Playwright de qualquer coisa
  pré-semeada no banco (não criada pela própria página via formulário) use
  `page.click("button.tab-btn[data-tab='vida']")`, nunca só `evaluate`
  (a nota acima, da Fase 5 Grupo D, vale pra "a seção existe/está anexada
  no DOM", não pra "os dados da aba já carregaram").
- **`self.client.post(url, data={...})` (form-encoded) nunca autentica em
  `/login`** - `_corpo_json()` (`app.py`) lê `request.json`, então todo
  teste/script novo tem que mandar `json={...}`, não `data={...}`, senão
  a rota recebe corpo vazio e falha silenciosamente (nenhum erro de
  sintaxe, só um 401/400 que confunde).
- **`caldav` (biblioteca) monta o VEVENT sozinho a partir de kwargs** -
  `Calendar.add_event(dtstart=..., dtend=..., summary=..., uid=...,
  alarm_trigger=timedelta(minutes=-N), alarm_action="DISPLAY",
  alarm_description=...)` (ver `caldav/lib/vcal.py:create_ical`), nunca
  precisou montar texto ICS na mão em `caldav_client.criar_evento`.
  `Calendar.name` é `@property` **deprecated** (`DeprecationWarning`) -
  achar o calendário "Painel" pelo nome usa `get_display_name()`.
- **`bank_accounts` não tinha nenhuma função de "gasto do mês de UMA
  conta"** antes do limite do cartão (só `total_gastos_bancarios_mes`,
  somando todas as contas juntas) - `db.gasto_mes_conta(conn, id, ano_mes)`
  é nova (US-E15) e generaliza `total_gastos_bancarios_mes`; qualquer
  feature futura de "fatura do cartão" deve reusar essa função, não somar
  `bank_transactions` de novo na mão.
- **`rotina_itens`/`rotina_marcacoes` (Rotina guiada manhã/noite) e
  `habitos`/`habito_marcacoes` (Hábitos, US-E12) são conceitos
  DIFERENTES por decisão do Alex** - não misturar nem reusar tabela: a
  Rotina é uma checklist fixa "de todo dia" com dois `momento`s
  (manha/noite); Hábito tem meta/frequência/horário próprios e é uma
  entidade nova.
- **Viagens (`viagens`/`viagem_itens`) continuam intocadas pelo módulo
  Projetos** (US-E13) - `vida.converter_viagem_para_projeto` só monta um
  dict no MESMO formato de `_projeto_detalhado` (id prefixado
  `"viagem-{id}"`, sem gravar nada em `projetos`/`projeto_etapas`) pro
  card poder reaproveitar o mesmo componente visual; `GET
  /api/viagens/<id>/como-projeto` calcula isso on-the-fly a cada chamada.

### Fase 6, Grupo E3 (contrato de cards, "Padrão Nectar") - US-E2 a US-E5
- **Contrato de resposta da aba Hoje = `docs/CARDS.md` (fonte única, só
  aditivo).** `/api/chat` e `/api/capture` (e `/api/atalho/capturar`)
  devolvem `{cards: [{type, id, data, actions}], resumo_texto, passos}` **além**
  dos campos legados (`resposta`/`acoes` no chat; `tipo`/`titulo`/`valor`...
  na captura) - não remover legado sem anotar em `docs/CARDS.md` antes (PWA
  com `app.js` antigo em cache, Telegram, Atalhos).
- **Executor de tool do chat NUNCA monta card.** Ele grava e devolve
  `"_efeito": {"entidade": "tarefa"|"gasto"|"renda"|"meta"|"lembrete", "id": ...}`;
  `cards.RegistroExecucao` (envolve os executores em `_processar_mensagem_chat`)
  cronometra (vira `passos`), recolhe o efeito e **tira toda chave com `_`**
  antes do resultado voltar pra IA (os testes antigos que comparam
  `resultado == {"ok": True}` continuam valendo). `cards.cards_dos_efeitos`
  é o ÚNICO mapeamento efeito -> card (lê a linha real do banco pelo id).
- **Card novo = 4 lugares**: formato em `docs/CARDS.md`; builder em
  `cards.py` (+ `CAMPOS_SENSIVEIS` se tiver dinheiro); renderizador puro
  `Cards.registrar(type, (data, card, ctx) => html)` em
  `static/js/cards-tipos.js` (todo texto por `Cards.esc`); teste em
  `tests/test_cards.py` + `tests/js/cards.test.js`. Type sem renderizador
  vira o fallback "Este trecho não pode ser exibido..." - nunca quebra.
- **Modo visitante nos cards é no servidor** (`_resposta_contrato` ->
  `cards.mascarar_visitante`): tira `valor`/`saldo` da transação e
  `valor_*`/`falta` da meta, troca `R$ 1.234,56` por `R$ •••` na prosa
  (`resumo_texto`/`resposta`, e no histórico). A captura idempotente grava a
  resposta SEM máscara no cache e mascara na saída (os dois caminhos passam
  por `_resposta_contrato`).
- **`cards.js`/`cards-tipos.js` carregam ANTES de `app.js`** (index.html):
  `app.js` chama `Cards.ligar(#chat-mensagens, {apiFetch, showTab, aoMudar})`
  no carregamento. `fmtMoeda` (const top-level de `app.js`) é resolvido na
  hora da chamada - funciona entre scripts clássicos; em Node cai no
  fallback idêntico.
- **Cards do chat ficam gravados** em `chat_mensagens.cards_json`
  (criptografado em repouso via `criptografia.criptografar`, igual ao resto do
  dado financeiro) - `/api/chat/historico` devolve `cards` por mensagem.
- **Lembrete não tem hora** (tabela `lembretes` só tem `data`): o card
  `lembrete` usa `data.hora` se um dia existir, senão mostra o dia e conta até
  09:00 (`notificacoes.HORA_PADRAO_DESPERTAR`, o mesmo horário do push
  "Desperta você", coluna `lembretes.despertar`).
- **Headless com resposta de contrato sem IA**: `page.route("**/api/chat", ...)`
  devolvendo um envelope montado com `cards.montar_resposta` contra o banco
  temporário do launcher (ids reais) - assim checkbox/despertar/desfazer
  batem no servidor de verdade.
- **Cards de habito/projeto_viagem/agenda/sugestao/saude_treino só têm
  renderizador** (US-E4): quem liga o dado real (US-E7b) monta o card no
  formato de `docs/CARDS.md` num builder de `cards.py` - o front não muda.
  `habito.semana` é SEMPRE segunda->domingo (7 itens); `projeto_viagem` aceita
  `percentual`/`feitas`/`total`/`hoje_fracao` prontos; `agenda.inicio/fim` são
  `AAAA-MM-DDTHH:MM` local.
- **Desfazer é por token, nunca "o último"** (US-E5): `cards.montar_resposta(...,
  criar_token=app._criar_token_desfazer(conn))` grava os ids exatos em
  `acoes_desfazer`; `POST /api/desfazer/<token>` chama `app._desfazer_itens`
  (sem commit, tudo ou nada). Entidade nova desfazível = `db.ENTIDADES_DESFAZIVEIS`
  + ramo em `_desfazer_itens`. Evento só com uid em `eventos_criados` e
  `caldav_client.apagar_evento_painel` existindo (senão 403/501).
- **Link de card destaca item por `data-entidade`/`data-id` no `<li>`** - lista
  nova que queira ser destino precisa desses dois atributos. `showTab` recarrega a
  lista e troca os `<li>`: por isso `destacarItem` (cards.js) continua procurando
  ~3s e re-destaca o elemento novo.
- **`.card-resultado` tem animação com fill-mode `both`** (prende `opacity: 1`):
  pra apagar um card depois de montado, mude a opacidade dos FILHOS
  (`.card-desfeito > *`), não do card.

### Fase 6, Grupo E, faixa 1 (E1-base) - US-E1a a US-E11
- **"O que eu lembro sobre você" (`templates/index.html`) fica na aba
  `painel`, não em `hoje` nem `vida`** - conferir com
  `grep -n 'data-tab\|class="tab-content"' templates/index.html` antes de
  assumir onde uma seção mora só pela ordem em que aparece no arquivo
  fonte (o HTML de várias abas fica concatenado sequencialmente, a divisão
  real é só pelas tags `<section id="tab-X">`).
- **Padrão novo de edição inline num item de lista (US-E10, primeiro caso
  no projeto - antes tudo era só apagar/recriar)**: `criarItemMemoria`
  (`static/js/app.js`) troca o `.item-titulo` (span) por um `<input>` no
  lugar, com botões Salvar/Cancelar substituindo Editar/Apagar durante a
  edição - reusa `ICONE_CORRIGIR` (já existia, é um lápis) pro botão
  "Editar". CSS novo: `.memoria-edit-input` (`style.css`), porque o input
  fica direto dentro de `.item-linha`, sem o `.form-linha` por perto que
  normalmente estiliza input de formulário.
- **Pegadinha de teste Playwright com `has_text` + edição inline**: um
  `Locator` com filtro `has_text="X"` é reavaliado do zero a cada retry
  (`.click()`/`.fill()` etc auto-esperam). Se a ação em teste troca o texto
  do próprio elemento filtrado (ex: span vira input ao clicar "Editar" - o
  texto visível some), o locator para de casar no retry seguinte e a ação
  seguinte trava em timeout, mesmo com a interação tendo funcionado.
  Solução: localizar por posição (`.first`, já que item novo sempre entra
  no topo - `list_memorias`/`list_manutencoes` ordenam por `criado_em
  DESC`) em vez de por texto, quando o teste for editar/interagir com um
  item logo depois de criar ele.
- **`_adicionar_compras` (app.py) já era o único ponto de entrada dos 3
  caminhos (formulário, API genérica, chat tool `adicionar_compras`)** -
  qualquer regra nova de parsing/validação de item de compra (ex:
  `vida.dividir_itens_compra`, US-E1b) só precisa entrar ali uma vez.
- **Rodar a suíte completa em background enquanto edita os MESMOS arquivos
  que ela está lendo contamina o resultado** (o teste inicia num snapshot,
  mas os módulos fonte no disco mudam no meio da execução) - descobri isso
  numa rodada real (6 falhas em vez das 6 esperadas coincidiu por acaso
  numa tentativa, mas outra rodada intermediária deu resultados
  inconsistentes até eu parar de editar). Padrão seguro: `git checkout
  HEAD -- <arquivos da história seguinte>` antes de rodar a suíte de uma
  história que ainda não foi commitada (isola o estado exatamente na
  história que vai ganhar o commit), rodar a suíte só então, e só depois
  restaurar os arquivos da próxima história a partir de uma cópia salva em
  `/tmp` (nunca editar author de novo por cima do que a suíte está lendo).

### Fase 6, Grupo E5 (proatividade unificada + visão do dia) - US-E8/US-E9
- **A linha do tempo vertical (trilha + bolinha colorida por estado) virou
  classe compartilhada `.linha-do-tempo`** (`style.css`, antes era
  `#lista-agenda` sozinho) - `#lista-agenda` (agenda de hoje, aba Painel) e
  `#visao-dia-timeline` (visão do dia, aba Hoje, US-E9) usam a MESMA classe
  + a MESMA função JS `criarItemLinhaDoTempo(ev, agora, proximoJaMarcado)`
  (`app.js`, extraída de dentro de `loadAgenda()`). Um terceiro consumidor
  futuro (ex: linha do tempo na aba Vida) deve reusar os dois, nunca copiar
  o CSS/JS de novo - **e lembrar de somar `class="linha-do-tempo"` no `<ul>`
  novo**, a classe sozinha no CSS não pinta nada sem o elemento carregar
  ela (achado real: o primeiro rascunho desta história renomeou o CSS mas
  esqueceu de acrescentar a classe no `<ul id="lista-agenda">` já
  existente - só foi pego na verificação visual headless, a agenda do
  Painel teria ficado sem a trilha visual silenciosamente, sem nenhum erro
  de JS/teste unitário acusando).
- **`notificacoes.py` NUNCA importa de `app.py`** (é o contrário: `app.py`
  importa `notificacoes`) - por isso as checagens novas da US-E8 que
  precisam do estado de hábito/projeto/cartão (ex: `habitos_passaram_batido`)
  recalculam com as funções de `db.py`/`vida.py` direto (`db.habito_marcado`,
  `db.marcacoes_habito_no_periodo`, `vida.habito_passou_batido`), em vez de
  chamar helpers privados de `app.py` como `_habito_detalhado` (que também
  faz a mesma conta, mas do lado errado da dependência).
- **Teste com "hora" fixa tipo `"00:00"` e relógio REAL (sem mockar
  `datetime.now`)** - comum em testes mais antigos de `tarefas_com_horario_hoje`
  - agora também aciona `tarefas_horario_passou` (US-E8, 30min depois do
  horário) no mesmo tick, já que qualquer hora real do dia está a mais de
  30min de `"00:00"`. Um teste que conta `avisos_enviados` com uma tarefa
  dessas precisa esperar 2 avisos (o "chegou"/`tarefa_horario` E o "passou
  da hora"/`tarefa_horario_passou`), não mais 1 - ver o ajuste em
  `test_notificacoes_verificar_agora_inclui_tarefa_com_horario_chegado`
  (`tests/test_app.py`) pro padrão exato.
- **"Sem nenhum item futuro, escolhe o mais atrasado" é `max()`, não
  `min()`, no horário de início** (`app._proximo_item_em_foco`, US-E9): a
  intuição de "mais atrasado" engana - o item que queremos em destaque é o
  que passou do horário HÁ MENOS TEMPO (o miss mais fresco, `max(inicio)`),
  não o mais antigo (`min(inicio)`, que ficaria preso mostrando a mesma
  tarefa staleada o dia inteiro mesmo com itens mais recentes passando
  batido também).


### Fase 6, Grupo E4 (chat produzindo cards dos módulos) - US-E6/US-E7
- **Consulta que vira card resolve LOCAL antes da IA**: `_processar_mensagem_chat`
  pergunta a `_classificar_intent(conn, texto, somente_local=True)` (padrão
  aprendido -> banco "pergunta -> onde buscar" em `aprendizado.consulta_conhecida`)
  e, se resolveu, chama as MESMAS tools do chat (`_plano_local_chat`) - sem API.
  Teste de chat com texto tipo "tomei um copo de agua"/"me mostra meus habitos"
  **não chama** o `claude_client.chat` mockado: o assert dentro do fake não roda.
  Pra testar o caminho da IA com essas frases, use outra redação.
- **Regra nova no banco local**: só em `aprendizado.consulta_conhecida` +
  plano em `app._plano_local_chat` (fonte -> tool). Verbo de ação ou assunto
  fora do banco (`_VERBO_ACAO`/`_FORA_DO_BANCO`) sempre cai pra IA - quem
  adicionar fonte nova precisa tirar a palavra de `_FORA_DO_BANCO` se estiver lá.
- **Card de consulta**: executor devolve `_efeito` com `"consulta": True` -> sem
  Desfazer, `data.consulta = true` (aditivo) e fora do `resumo_final`.
- **O `ul` global do `style.css` é `display:flex; flex-direction: column`**
  (linha ~1689) - qualquer `<ul>` novo dentro de card que deva ser uma
  FILEIRA (ex: `.card-gotas`) precisa de `flex-direction: row` explícito,
  senão empilha vertical (achado no headless, teste JS não pega).
- **`app.py` não importava `re`** até a E4 - `NameError` só aparece em
  runtime (500 na rota), nunca no import.
- **Não usar `pkill -f <script>`/`grep <script>` + kill numa linha de Bash que
  também LANÇA o mesmo script**: o padrão casa a própria linha de comando do
  shell e mata a chamada inteira (exit 144). Matar por `ps -eo pid,args |
  grep "python /tmp/..."` numa chamada separada.
- **Sugestão de horário usa `app._agora()`** (relógio isolado) - teste que
  depende de "a partir de agora" faz `patch("app._agora", ...)` em vez de
  mockar `datetime` inteiro.
