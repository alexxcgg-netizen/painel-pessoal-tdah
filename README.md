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
- Visual: fonte Plus Jakarta Sans, paleta vibrante com cor propria por secao, fundo com gradiente animado (aurora), micro-animacoes com efeito "spring" nos botoes e transicoes, numeros que sobem ao carregar, e uma comemoracao (brilho dourado + selo) quando uma meta bate 100%
- Notificacao push (Web Push/VAPID) - ver secao "Notificacoes" abaixo
- Agenda do Calendario da Apple/iCloud (so leitura) aparece na aba Hoje, e entra como contexto no resumo do dia gerado pela IA - ver secao "Calendario" abaixo
- **Plano do dia**: olha suas tarefas pendentes (sem hora) e os compromissos da agenda (com hora fixa) e sugere a melhor ordem pra encaixar tudo, sob demanda (botao "Gerar plano do dia")
- **Devo sair ate que horas?**: calculadora de deslocamento com transito em tempo real (Google Routes API) - informa destino e horario que precisa chegar, ela conta pra tras o tempo de viagem + uma margem de seguranca e diz a que horas sair

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
- `GET /api/bancos/sync-status` — se a sincronizacao automatica (Pluggy) esta configurada
- `POST /api/bancos/conectar/token` — gera o token de curta duracao (30min) que o widget da Pluggy usa
- `POST /api/bancos/conectar/finalizar` — recebe o `item_id` que o widget devolveu e sincroniza contas/transacoes

### Sincronizacao automatica (Pluggy) — codigo pronto, so falta a chave

Ja implementado de verdade (nao e mais so um placeholder), usando [Pluggy](https://pluggy.ai/) — agregador de Open Finance Brasil autorizado pelo Banco Central. Pra ativar:

1. Cria uma conta gratuita em [meu.pluggy.ai](https://meu.pluggy.ai/) (uso pessoal, sem custo) e conecta seus bancos por la
2. No [dashboard da Pluggy](https://dashboard.pluggy.ai/), pega o `CLIENT_ID` e `CLIENT_SECRET` da sua aplicacao
3. Cola os dois no `.env`:
   ```
   PLUGGY_CLIENT_ID=...
   PLUGGY_CLIENT_SECRET=...
   ```
4. Reinicia o `python app.py` — a aba **Bancos** passa a mostrar um botao "Conectar banco automaticamente" no topo, junto com o import manual de OFX (que continua funcionando igual, nao foi removido)

**Como funciona por baixo dos panos** (`pluggy_client.py`): o botao abre o widget oficial da Pluggy (`PluggyConnect`, carregado via `cdn.pluggy.ai`) direto no navegador — voce loga no banco *dentro do widget deles*, nunca no nosso servidor, e a gente nunca ve nem guarda sua senha do banco. Quando termina, o widget devolve um `item.id`; nosso backend usa isso pra buscar as contas (`GET /accounts`) e transacoes (`GET /transactions`) na API da Pluggy e gravar nas mesmas tabelas `bank_accounts`/`bank_transactions` que o import de OFX ja usa — os dois caminhos convivem e alimentam o mesmo lugar. Contas do tipo `CREDIT` na Pluggy viram `tipo=cartao` automaticamente (pra separar fatura de conta corrente, como ja fazia no OFX).

Endpoints, request/response e nomes de campo foram conferidos direto no [codigo-fonte do SDK oficial da Pluggy](https://github.com/pluggyai/pluggy-node) antes de escrever, nao inventados. Uma coisa que so da pra confirmar com uma conta real conectada: se o sinal do valor da transacao (`amount`) segue a mesma convencao do OFX (negativo = saiu dinheiro) em todos os tipos de conta, especialmente cartao de credito. Vale conferir os primeiros valores importados antes de confiar cegamente no `total_gasto` da aba Bancos.

## Notificacoes (Web Push) — pronto pra usar, ativa em 1 passo

Ja implementado de ponta a ponta (chaves, banco, service worker, botao). Pra ativar:

```bash
python scripts/gerar_chaves_push.py
```

Isso gera `vapid_private.pem` (fica de fora do git) e imprime duas linhas pra colar no `.env`
(`VAPID_PUBLIC_KEY` e `VAPID_SUBJECT`). Reinicia o `python app.py` e um botao "Ativar
notificacoes" aparece no cabecalho — clica, aceita a permissao do navegador, pronto.

**O que ja funciona hoje, mesmo sem hospedagem fixa**: mandar uma notificacao agora mesmo
funciona sempre que o `python app.py` estiver rodando no momento do envio — o navegador entrega
assim que o aparelho estiver online, mesmo que o servidor ja tenha parado depois. Pra testar,
chama `POST /api/push/testar` (ou eu crio um botao "testar" se quiser) e uma notificacao real
chega no seu navegador/celular.

**O que ainda depende de hospedagem fixa**: notificacao *agendada* (tipo "todo dia as 8h me
lembra do resumo") precisa de algo rodando o tempo todo pra disparar o envio na hora certa -
isso ainda nao esta implementado (precisaria de um agendador tipo APScheduler ou um cron
chamando a API). Assim que decidir onde o painel vai morar de forma fixa (VPS, Raspberry Pi em
casa, etc.), essa parte e rapida de plugar em cima do que ja existe.

## Calendario (Apple/iCloud) — pra notificacao nao atrapalhar compromisso

Voce pediu pra notificacao levar em conta sua agenda, pra nao mandar aviso bem na hora de um
compromisso. Isso tem duas partes, uma pronta hoje e outra que depende do agendador (Fase 1.5):

### O que ja funciona hoje

`caldav_client.py` conecta no Calendario da Apple/iCloud via CalDAV (so leitura, nunca escreve
nada la). Pra ativar:

1. Vai em [appleid.apple.com](https://appleid.apple.com/) → Seguranca → Senhas de app → gera uma
   senha nova (a senha normal da sua Apple ID **nao funciona** aqui por causa do 2FA)
2. Cola no `.env`:
   ```
   ICLOUD_USERNAME=seu-email@icloud.com
   ICLOUD_APP_PASSWORD=a-senha-de-app-gerada
   ```
3. Reinicia o `python app.py` — a aba **Hoje** passa a mostrar "Agenda de hoje" com os
   compromissos do dia, e o resumo diario gerado pela IA passa a mencionar se o dia esta cheio
   ou tranquilo

Alem disso, o botao **"Gerar plano do dia"** (tambem na aba Hoje) usa a agenda como ancora fixa
e sugere a ordem certa de fazer suas tarefas pendentes ao redor dos compromissos - isso ja
resolve boa parte do "me ajuda a organizar o dia" sem precisar de agendador nenhum, porque voce
pede sob demanda quando quiser (nao e automatico).

### O que ainda falta pra notificacao "esperta" de verdade

A funcao `caldav_client.horario_ocupado(inicio, fim)` ja existe e confere se um horario colide
com algum evento — mas ainda nao esta plugada em nada automatico, porque isso so faz sentido
junto com um agendador (ver "Notificacoes" acima: precisa de algo rodando o tempo todo). Quando
essa peca for construida, a logica vai ser: antes de mandar um push, chama
`horario_ocupado()` e, se estiver ocupado, adia o aviso em vez de interromper o compromisso.

**Aviso honesto sobre a lib**: o CalDAV do iCloud e um protocolo que a Apple nunca declarou
oficialmente suportado (funciona, mas as vezes falha sem motivo aparente) - por isso todo o
codigo aqui e tolerante a erro: se a conexao falhar, o resumo do dia e a aba Hoje simplesmente
mostram "sem agenda" em vez de quebrar o resto do app.

## Deslocamento — "devo sair ate que horas?"

O exemplo que voce deu (voo daqui a pouco, preciso saber se da tempo de chegar) e resolvido pela
calculadora na aba Hoje. `maps_client.py` usa a **Google Routes API** com transito em tempo real
(nao e so distancia - considera transito, tipo de via, etc.) pra calcular quanto tempo leva pra
chegar num lugar, e conta pra tras a partir do horario que voce precisa estar la.

### Como ativar

1. Cria um projeto gratis em [console.cloud.google.com](https://console.cloud.google.com/),
   ativa a "Routes API" e gera uma chave de API
2. Cola no `.env`:
   ```
   GOOGLE_MAPS_API_KEY=sua-chave
   ENDERECO_CASA=Rua Exemplo, 123 - Sua Cidade   # opcional, senao pede origem toda vez
   ```
3. Reinicia o `python app.py` — o formulario "Devo sair ate que horas?" na aba Hoje passa a
   funcionar: informa destino + horario que precisa chegar, ele devolve o horario de saida
   (ja com 15min de margem de seguranca por padrao)

**Sobre custo**: uso pessoal (algumas consultas por dia) fica bem dentro dos $200/mes de credito
gratuito que a Google da por conta - na pratica isso e gratis pro seu uso, mas e bom saber que a
API em si nao e ilimitada de graca se um dia usar muito mais que isso.

**O que isso ainda nao faz**: calcular automaticamente "voce tem voo as 14h, preciso avisar
1h30 antes" sozinho, sem voce pedir - isso juntaria a calculadora de deslocamento com o
agendador de notificacoes (que ainda depende de hospedagem fixa, ver secoes acima). Hoje voce
mesmo abre a calculadora quando quiser saber o horario de saida.

## Roadmap

**Fase 1.5** — notificacao agendada automatica, ja levando em conta a agenda pra nao avisar em cima de compromisso (precisa de hospedagem fixa rodando o tempo todo - ver secao "Notificacoes" acima)

**Fase 2** — comando de voz livre; integracao com Home Assistant (luz/temperatura/cortina do quarto ligada a rotina ou tarefa)

**Ideia futura** — se o painel pessoal se provar util, replicar pra outros membros da familia (cada um com seu proprio banco de dados/instancia - nunca compartilhando dados entre si sem pedir)
