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

## Funcionalidades (v1)

- Captura de texto livre, classificado automaticamente em tarefa ou gasto
- Lista de tarefas pendentes, marcar como concluida
- Quebra de tarefa grande em passos menores (Sonnet)
- Resumo do dia, tom neutro e factual
- Lista de gastos categorizados
- Aba "Construtora": hoje e um stub (`/api/construtora/resumo`); passa a mostrar dados reais quando o painel da construtora expuser sua propria API

## Integracao com o painel da construtora

Os dois projetos ficam em repositorios e pastas separados de proposito — cada um estruturado e programado pro seu contexto especifico. A unica conexao entre eles e via HTTP: o painel da construtora expoe um endpoint read-only (ex: `/api/resumo`, protegido por API key) e este painel consome via `CONSTRUTORA_API_URL` + `CONSTRUTORA_API_KEY` no `.env`. Nenhum banco de dados e compartilhado entre os dois.

## Roadmap

**Fase 1.5** — notificacao push via PWA (exige gerar VAPID keys e um endpoint de subscription; ainda nao implementado)

**Fase 2** — comando de voz livre; integracao com Home Assistant (luz/temperatura/cortina do quarto ligada a rotina ou tarefa)
