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
