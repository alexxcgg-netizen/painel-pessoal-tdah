# Regras deste repositório (Painel Pessoal do Alex)

## ⚠️ ISTO É O ASSISTENTE PESSOAL DO ALEX — NÃO É O SISTEMA FINANCEIRO DA CONSTRUTORA
Existe um segundo projeto, **`financeiro-construtora`** (repositório e pasta separados,
`/home/user/financeiro-construtora` quando os dois estão clonados na mesma máquina/sessão)
— é o sistema financeiro real de uma construtora (A.N Construtora): dinheiro de verdade,
obras de verdade, contas a pagar de verdade, com um `AGENTS.md` próprio cheio de regras
rígidas (backup antes de escrever, homologação obrigatória, fuzzing de 50-100 cenários por
mudança). **Os dois são projetos diferentes, com donos de dado diferentes, e nunca devem
ser confundidos:**

- Este repositório (`painel-pessoal-tdah`) é de **uso pessoal do Alex** — tarefas, gastos
  pessoais, metas, aviação (ele está fazendo curso de piloto comercial), rotina, saúde.
  Nada aqui é dinheiro de empresa.
- A única ligação entre os dois é uma integração HTTP **somente leitura**: este painel
  consome `GET /api/resumo` e `GET /api/contas_a_vencer` do painel da construtora
  (`CONSTRUTORA_API_URL` + `CONSTRUTORA_API_KEY` no `.env` — ver
  `_buscar_resumo_construtora()` e `_buscar_contas_a_vencer_construtora()` em `app.py`).
  **Nunca** abra, leia ou escreva direto no `construtora.db` a partir daqui, e **nunca**
  reimplemente cálculo financeiro da empresa aqui — os números sempre vêm prontos da API
  de lá, exibidos como chegaram. Ver a seção "Integração com o painel da construtora" no
  `README.md` pros detalhes completos.
- Se alguma tarefa parecer pedir controle de obra, fornecedor de material de construção,
  faturamento de venda de unidade, ou qualquer outra coisa da empresa — é sinal de que ela
  é pro repositório `financeiro-construtora`, não pra este.
- **Se uma sessão de IA estiver trabalhando nos dois projetos ao mesmo tempo** (comum -
  o Alex costuma pedir trabalho nos dois em sequência): confirme sempre em qual
  diretório/repositório um comando vai rodar antes de editar ou commitar — `pwd`/`git
  remote -v` primeiro se houver a menor dúvida.

## O que este projeto é
App pessoal de uso único (um PIN de 6 dígitos, sem múltiplos usuários) pra reduzir carga
mental do dia a dia: captura rápida de tarefa/gasto/meta por texto livre (Claude
classifica), quebra de tarefa grande em passos, resumo factual do dia, chat com tool-use
como tela principal. Ver `README.md` pra lista completa de funcionalidades.

## Convenções deste repositório
- **Stack:** Flask + SQLite no backend, PWA (HTML/CSS/JS puro, sem framework) no
  frontend. `db.py` é o schema; `app.py` concentra quase todas as rotas.
- **`CHANGELOG.md` por dia de trabalho.** Memória entre sessões de IA - atualizar depois
  de qualquer leva de mudanças relevante, não precisa ser a cada commit isolado.
- **Testes antes de considerar pronto.** `.venv/bin/python -m unittest discover -s tests`
  (o venv do projeto já tem as dependências; `pip install -r requirements.txt` numa venv
  nova se não existir ainda). Os testes usam mock nas chamadas à Claude - não gastam nada
  nem precisam de `ANTHROPIC_API_KEY` real. Regra leve mas real: não empurrar mudança que
  quebrou a suíte.
- **Regras mais leves que o `financeiro-construtora`** de propósito (não é dinheiro de
  empresa, é uso pessoal) - mas isso não é desculpa pra pular teste ou deixar rota nova
  sem tratamento de erro. Fuzzing pesado (50-100 cenários por mudança) não é obrigatório
  aqui como é lá, mas vale a pena nos pontos mais expostos a entrada externa (captura por
  texto livre, chat, os endpoints `/api/atalho/*` usados pelos Shortcuts do iPhone).

## Preferência permanente do Alex: atenção obsessiva a detalhe visual/interação
Pedido explícito pra guardar como padrão de toda sessão futura, não só pontual: o Alex presta
atenção em detalhes mínimos de UI/UX e quer que estejam certos - animação, timing, easing,
micro-interação, tudo.
- **Padrão de qualidade**: suave e "premium" (comparação dele mesmo: "carro de luxo"), nunca
  chamativo/brusco/"sinistro". Preferir easing customizado a linear, transições que "assentam"
  (overshoot leve, bounce sutil) a cortes secos. Ver `--ease-bounce`/`--ease-suave`/
  `--ease-snap` já definidos em `static/css/style.css`. Sempre respeitar
  `prefers-reduced-motion` (o app já faz isso em várias animações existentes).
- **Chat com "cara de gente", não de robô**: quer que a resposta do assistente pareça alguém
  digitando de verdade, não um bloco de texto aparecendo mecanicamente. Já existe uma base
  (`escreverPalavraAPalavra` em `app.js`, palavra por palavra com blur+fade) - qualquer
  evolução deve manter esse espírito.
- **Antes de qualquer leva grande de efeito/animação, perguntar o que estiver ambíguo** (ele
  pediu isso explicitamente) em vez de implementar tudo de uma vez e descobrir depois que não
  era bem aquilo.
- **Feedback visual sempre pelo artefato-réplica**: o padrão estabelecido nessa sessão é
  regenerar o artefato (`https://claude.ai/artifact/Ecy9gXXfefAgWkeTA5DojR`) a cada rodada de
  mudança visual/CSS/JS pra ele testar ao vivo antes de considerar fechado - ver `CHANGELOG.md`
  (entradas "Liquid Glass round N") pro histórico completo de idas e vindas nesse processo.
