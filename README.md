# Painel Pessoal / Assistente de TDAH

App pessoal (uso unico, sem autenticacao multiusuario) pra reduzir carga mental do dia a dia: captura rapida de tarefa e gasto por texto livre, quebra de tarefa grande em passos, resumo factual do dia. Inspirado no espirito do [Nectar](https://www.meu-nectar.com/), mas sob controle proprio e sem mensalidade.

## Stack

- Backend: Flask + SQLite
- Frontend: PWA (HTML/CSS/JS puro, sem framework)
- IA: API da Anthropic — Haiku pra classificacao/resumo (barato), Sonnet pra quebra de tarefa (mais raciocinio)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # preencher ANTHROPIC_API_KEY
python app.py
```

Abre em `http://localhost:5001`. Pra instalar como PWA no celular, acessa pelo navegador e usa "Adicionar a tela de inicio".

## Testes

```bash
python -m unittest tests.test_app -v
```

Os testes usam mock nas chamadas a Claude (nao gastam nada nem precisam de `ANTHROPIC_API_KEY` real) e cobrem o fluxo completo: captura, pergunta de esclarecimento quando a IA fica em duvida, completar tarefa, quebra em subtarefas, resumo do dia e acumulo de custo.

## Funcionalidades (v1)

- Captura de texto livre, classificado automaticamente em tarefa, gasto ou **meta financeira**
- Lista de tarefas pendentes, marcar como concluida
- Quebra de tarefa grande em passos menores (Sonnet)
- Resumo do dia, tom neutro e factual
- Aba "Financeiro": gastos categorizados + metas (ex: "quero juntar 15 mil pra uma moto ate dezembro" vira meta com calculo automatico de quanto guardar por mes - a conta e feita em Python, nao pela IA, pra nao ter erro de aritmetica)
- Aba "Bancos": importacao manual de extrato OFX (Nubank, Caixa, Viacredi, Bradesco ou qualquer banco que exporte OFX/QFX), com conta e cartao de credito tratados como contas separadas pra ver a fatura isolada dos gastos da conta
- Aba "Construtora": hoje e um stub (`/api/construtora/resumo`); passa a mostrar dados reais quando o painel da construtora expuser sua propria API
- PWA com icone e meta tags proprias pra iOS (Dynamic Island/safe area respeitados, barra de navegacao fixa embaixo no estilo de app nativo)

## Integracao com o painel da construtora

Os dois projetos ficam em repositorios e pastas separados de proposito — cada um estruturado e programado pro seu contexto especifico. A unica conexao entre eles e via HTTP: o painel da construtora expoe um endpoint read-only (ex: `/api/resumo`, protegido por API key) e este painel consome via `CONSTRUTORA_API_URL` + `CONSTRUTORA_API_KEY` no `.env`. Nenhum banco de dados e compartilhado entre os dois.

## Integracao bancaria (Nubank, Viacredi, etc.)

### O que funciona hoje: importacao de extrato OFX

Todo banco brasileiro relevante (Nubank, Viacredi e praticamente qualquer cooperativa/banco) deixa exportar o extrato em formato OFX pelo app ou internet banking. Na aba **Bancos**:

1. Exporta o extrato em OFX pelo app do banco
2. Escolhe o banco (Nubank/Viacredi/Outro) e seleciona o arquivo
3. Clica em "Importar extrato"

O parser (`bank_ofx.py`) le tanto OFX 1.x (SGML, formato mais comum) quanto OFX 2.x (XML). Cada transacao e identificada pelo `FITID` (id unico que o proprio banco atribui), entao **reimportar o mesmo extrato nao duplica nada** — util pra importar toda semana sobrepondo o periodo anterior sem se preocupar.

Os dados ficam em `bank_accounts` e `bank_transactions` no SQLite, com endpoints:

- `POST /api/bancos/importar` — form-data com `banco` + `arquivo` (o OFX)
- `GET /api/bancos` — lista contas com contagem de transacoes
- `GET /api/bancos/<id>/transacoes` — extrato de uma conta
- `GET /api/bancos/sync-status` — se a sincronizacao automatica esta configurada (hoje sempre `false`)

### O que falta pra sincronizacao automatica (sem precisar importar manualmente)

Conectar direto com Nubank/Viacredi em tempo real exige o **Open Finance Brasil** (ex-Open Banking, regulado pelo Banco Central) — nao da pra "hackear" isso com scraping de senha, e nem seria seguro. O caminho real:

1. Criar conta num agregador certificado de Open Finance, tipo [Pluggy](https://pluggy.ai/) ou [Belvo](https://belvo.com/) — eles ja tem o credenciamento e cuidam do fluxo de consentimento com o Banco Central; e o jeito viavel pra um projeto pessoal (virar credenciado direto no Banco Central e fora de escala pra isso)
2. Pegar `client_id`/`client_secret` do agregador escolhido e colocar em `OPEN_FINANCE_CLIENT_ID` / `OPEN_FINANCE_CLIENT_SECRET` no `.env` (esses nomes de variavel ja sao checados por `/api/bancos/sync-status`)
3. Implementar o fluxo de conexao (o agregador abre uma tela de consentimento hospedada por eles, o usuario loga no banco la, e depois a API do agregador devolve transacoes via webhook ou polling) — isso ainda **nao esta implementado**, fica como proximo passo quando decidir seguir por esse caminho

Ate la, a importacao manual de OFX cobre o essencial sem precisar de conta em nenhum servico externo nem custo.

## Notificacoes

Push notification de verdade (a que chega mesmo com o navegador fechado) exige o app rodando o tempo todo em algum servidor, nao so quando abre no celular - isso e uma decisao de hospedagem (VPS, Raspberry Pi, etc.) que ainda nao foi tomada. Por isso ainda nao foi implementado; fica pra quando decidir onde o painel vai morar de verdade. Ate la, o resumo do dia cumpre o papel de "olhar o que importa" quando voce abre o app.

## Roadmap

**Fase 1.5** — notificacao push via PWA (exige hospedagem fixa + gerar VAPID keys + endpoint de subscription)

**Fase 2** — comando de voz livre; integracao com Home Assistant (luz/temperatura/cortina do quarto ligada a rotina ou tarefa); sincronizacao bancaria automatica via Open Finance (ver secao acima)

**Ideia futura** — se o painel pessoal se provar util, replicar pra outros membros da familia (cada um com seu proprio banco de dados/instancia - nunca compartilhando dados entre si sem pedir)
