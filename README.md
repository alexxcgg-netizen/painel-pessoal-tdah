# Painel Pessoal / Assistente de TDAH

App pessoal (uso unico - um PIN de 6 digitos, sem contas nem multiplos usuarios) pra reduzir carga mental do dia a dia: captura rapida de tarefa e gasto por texto livre, quebra de tarefa grande em passos, resumo factual do dia. Inspirado no espirito do [Nectar](https://www.meu-nectar.com/), mas sob controle proprio e sem mensalidade.

Historico de mudancas por dia de trabalho: **`CHANGELOG.md`** - memoria base pras proximas sessoes de IA.

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

Abre em `http://localhost:5001` - bom pra testar no proprio computador.

**Isso NAO da pra instalar no celular como PWA com notificacao funcionando** -
`localhost` so existe pro computador que esta rodando o `python app.py`, e o
iPhone exige HTTPS pra registrar o Service Worker/push (nem um IP da rede local
em HTTP resolve isso). Pra usar de verdade no iPhone (instalar na tela de inicio,
receber notificacao), hospeda numa VPS com dominio proprio - passo a passo
completo em [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Login (PIN de 6 digitos)

Na primeira vez que abrir o painel (local ou hospedado), ele pede pra voce
escolher um PIN de 6 digitos - fica guardado com hash no banco (`auth.py`,
`werkzeug.security.generate_password_hash`), nunca em texto puro, e nunca
sai do seu banco de dados nem vai pro git. A partir dai toda pagina e toda
rota `/api/...` (com excecao de `/api/saude/importar`, que usa o proprio
`SAUDE_WEBHOOK_TOKEN`) exige uma sessao autenticada - isso e checado no
servidor (`@app.before_request` em `app.py`) em toda requisicao, entao abrir
o Inspecionar/Console do navegador nao adianta nada pra contornar: quem
decide "entra ou nao" e sempre o backend, nunca o que roda no navegador.

5 tentativas de PIN erradas do mesmo IP bloqueiam novas tentativas por 5
minutos (contador persistido no banco, sobrevive a reinicio do processo -
`login_tentativas`), pra um PIN de 6 digitos (1 milhao de combinacoes) nao
virar forca-bruta viavel. A sessao dura 90 dias (`permanent_session_lifetime`)
depois de logar, entao no dia a dia voce nao fica digitando o PIN toda hora -
so a primeira vez (ou se limpar os dados do navegador, ou apertar o botao de
sair no cabecalho).

Esqueceu o PIN? Nao tem recuperacao pelo navegador de proposito (seria um
jeito de contornar o proprio login) - `python scripts/resetar_pin.py` no
servidor apaga o PIN configurado, e o painel pede pra escolher um novo na
proxima visita.

## Testes

```bash
python -m unittest discover tests -v
```

Os testes usam mock nas chamadas a Claude (nao gastam nada nem precisam de `ANTHROPIC_API_KEY`
real) e cobrem o fluxo completo: captura, pergunta de esclarecimento quando a IA fica em duvida,
completar tarefa, quebra em subtarefas, resumo do dia, acumulo de custo, o loop de tool-use do
chat (`tests/test_claude_client.py`), as regras de notificacao proativa
(`tests/test_notificacoes.py`), a sequencia de uso/streak (`tests/test_streak.py`, com fuzzing de
200 cenarios) e as contas de horas voadas e a previsao do tempo/METAR-TAF com a rede mockada
(`tests/test_voos.py`, `tests/test_clima.py`, `tests/test_metar.py`).

## Funcionalidades (v1)

- **Chat**: a aba Hoje e uma conversa com tool-use - fala o que quiser e a IA decide se registra tarefa/gasto/meta, gera o plano do dia, ou so responde (ver secao "Chat" abaixo)
- Captura rapida de texto livre no topo, classificado automaticamente em tarefa, gasto ou **meta financeira** - continua existindo em paralelo ao chat
- Lista de tarefas pendentes, marcar como concluida
- Quebra de tarefa grande em passos menores (Sonnet)
- Resumo do dia, tom neutro e factual (aba Painel)
- **Notificacoes proativas**: verifica tarefa atrasada, meta fora do ritmo e gasto da semana elevado, e manda push sozinho (ver secao "Notificacoes" abaixo)
- Aba "Financeiro": gastos categorizados + metas (ex: "quero juntar 15 mil pra uma moto ate dezembro" vira meta com calculo automatico de quanto guardar por mes - a conta e feita em Python, nao pela IA, pra nao ter erro de aritmetica)
- Aba "Bancos": importacao manual de extrato OFX (Nubank, Caixa, Viacredi, Bradesco ou qualquer banco que exporte OFX/QFX), com conta e cartao de credito tratados como contas separadas pra ver a fatura isolada dos gastos da conta
- Aba "Construtora": hoje e um stub (`/api/construtora/resumo`); passa a mostrar dados reais quando o painel da construtora expuser sua propria API
- PWA com icone e meta tags proprias pra iOS (Dynamic Island/safe area respeitados, barra de navegacao fixa embaixo no estilo de app nativo)
- Visual: paleta e tipografia inspiradas no Nectar (ver secao "Visual" abaixo), micro-animacoes com efeito "spring" nos botoes e transicoes, numeros que sobem ao carregar, e uma comemoracao (brilho dourado + selo) quando uma meta bate 100%
- Notificacao push (Web Push/VAPID) - ver secao "Notificacoes" abaixo
- Agenda do Calendario da Apple/iCloud (so leitura) aparece na aba Painel, e entra como contexto no resumo do dia e no chat - ver secao "Calendario" abaixo
- Saude (passos, distancia, sono) via Atalhos do iPhone - ver secao "Saude" abaixo
- **Plano do dia**: olha suas tarefas pendentes (sem hora) e os compromissos da agenda (com hora fixa) e sugere a melhor ordem pra encaixar tudo, sob demanda (botao na aba Painel ou pedindo no chat)
- **Devo sair ate que horas?**: calculadora de deslocamento com transito em tempo real (Google Routes API) - informa destino e horario que precisa chegar, ela conta pra tras o tempo de viagem + uma margem de seguranca e diz a que horas sair, com atalho pra abrir a rota no Waze

## Integracao com o painel da construtora

Os dois projetos ficam em repositorios e pastas separados de proposito — cada um estruturado e programado pro seu contexto especifico. A unica conexao entre eles e via HTTP: o painel da construtora expoe dois endpoints read-only (`GET /api/resumo` e `GET /api/contas_a_vencer`, ambos protegidos por API key) e este painel consome via `CONSTRUTORA_API_URL` + `CONSTRUTORA_API_KEY` no `.env`. Nenhum banco de dados e compartilhado entre os dois.

**Ja implementado do lado da construtora** (v3.99.14 e v3.99.16 daquele repositorio):
- `/api/resumo` devolve so o essencial - `tot_entradas`, `tot_saidas`, `lucro_liquido`,
  `margem` (sem detalhamento por obra/categoria, decisao tomada com o Alex).
- `/api/contas_a_vencer` devolve as contas a pagar em aberto (nao pagas) vencendo nos
  proximos 30 dias, mais qualquer conta ja vencida - cada uma com `vencimento`, `valor`,
  `fornecedor`, `descricao`, `dias_ate_vencer`.

Os dois autenticados por header `X-API-Key` comparado contra `PAINEL_EXTERNO_API_KEY` no
`.env` de la. Pra ativar aqui: cola a mesma chave em `CONSTRUTORA_API_KEY` e a URL de onde
aquele painel roda em `CONSTRUTORA_API_URL`.

Esse resumo (e as contas a pagar) tambem entram como contexto no **resumo do dia** e no
**chat** (decisao do Alex, 2026-09-18) - o modelo pode mencionar ou responder perguntas sobre
o financeiro geral da construtora, sempre com os numeros exatamente como vieram de la (nunca
recalculados aqui). A aba **Construtora** mostra a lista de contas a vencer/vencidas direto no
painel, e o scheduler avisa por push quando uma conta vence hoje, ja venceu, ou vence nos
proximos 3 dias (uma vez por dia por conta, sem repetir aviso).

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

**Notificacoes proativas - ja implementado, roda enquanto o `python app.py` estiver de pe**: um
job (`APScheduler`, ver `iniciar_scheduler()` em `app.py`) roda a cada 5min e verifica, em Python
puro (`notificacoes.py`), cinco coisas: tarefas atrasadas (com data), metas financeiras fora do
ritmo pra bater o prazo (compara o quanto ja devia ter guardado, proporcional ao tempo passado,
com o que guardou de verdade), gasto da semana bem acima da media das ultimas semanas, datas
importantes se aproximando (ver secao "Datas importantes" abaixo), e **tarefas com horario
marcado pra hoje cuja hora ja chegou** (`notificacoes.tarefas_com_horario_chegando`) - isso e o
que transforma "cria um lembrete pra mim: quando eu chegar em casa umas 14h, colocar o lixo pra
fora" (dito no chat) num push de verdade chegando por volta das 14h, nao so um item guardado numa
lista que voce so ve se abrir o app. Cada tipo de aviso so dispara uma vez por ocorrencia
(deduplicado na tabela `notificacoes_enviadas`), pra nao virar spam. Da pra forcar uma
verificacao na hora com `POST /api/notificacoes/verificar-agora`.

A checagem roda a cada 5 minutos (em vez de 3h como as outras) especificamente pra esse lembrete
com horario nao atrasar muito - "as 14h" que so vira aviso as 17h nao serve pra nada. As outras
quatro checagens sao lentas por natureza (atraso de dias, nao de minutos) e nao se importam com a
frequencia maior; o dedup evita qualquer reenvio extra.

**O que ainda depende de hospedagem fixa**: isso tudo so roda enquanto o processo do
`python app.py` estiver ligado no seu computador - fecha o terminal, para de verificar. Pra virar
"todo dia as 8h, sem eu precisar deixar o Mac ligado", precisa hospedar o painel em algo que fica
de pe sozinho (VPS, Raspberry Pi em casa, etc.). A logica em si (scheduler + regras) ja esta
pronta, so falta o lugar fixo pra ela rodar.

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

### Tarefa com horario vira compromisso na agenda (mesmo sem iCloud)

Se voce disser um horario especifico ao registrar uma tarefa - pela captura rapida ("hoje as
14h tenho consulta medica") ou pelo chat, mesmo em mensagens separadas e fora de ordem ("hoje as
22h academia" numa mensagem, "hoje as 13h consulta" em outra) - a IA extrai esse horario (campo
`hora`, formato HH:MM, `claude_client.py`) e a tarefa passa a contar como compromisso de horario
fixo na "Agenda de hoje", junto com os eventos do iCloud (se estiver conectado) ou sozinha (se
nao estiver). O que decide a posicao de cada compromisso na lista e sempre o horario, nunca a
ordem em que voce falou - a lista final (`app.py::_compromissos_de_hoje`) e ordenada por horario
antes de ir pro navegador. Essa mesma lista unificada e o que "Gerar plano do dia" usa como
ancora fixa e o que o resumo diario e o contexto do chat enxergam - entao uma tarefa com horario
nunca aparece duplicada como "tarefa solta" em outro lugar.

So conta como compromisso de hoje se a tarefa tiver `due_date` = hoje **e** `hora` preenchida;
uma tarefa so com prazo ("ate sexta") continua sendo tarefa solta, sem horario fixo, do jeito que
sempre foi.

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

Depois do calculo aparece um botao "Abrir no Waze", que abre a navegacao turn-by-turn direto no
app do Waze (com o transito em tempo real dele, que costuma ser melhor em Santa Catarina). Nao
existe API publica do Waze pra rotas/transito, entao o calculo do horario de saida continua vindo
da Google Routes API — o link do Waze e so um atalho pra navegacao (usa o [deep link oficial do
Waze](https://developers.google.com/waze/deeplinks), sem scraping nem API nao documentada).

### E a Uber?

Do lado do link, funciona igual ao Waze: aparece um botao "Pedir Uber" junto do Waze, que abre o
app da Uber (ou a Uber web se nao tiver o app) com origem = sua localizacao atual e destino ja
preenchido, usando o [deep link publico da Uber](https://developer.uber.com/docs/riders/ride-requests/tutorials/deep-links/introduction)
(`m.uber.com/ul/...`) - nao precisa de chave de API nem de OAuth, e nao acessa sua conta.

**O que isso NAO faz**: pedir a corrida sozinho (sem voce confirmar no app), nem ver preco/tempo
de espera antes de abrir, nem confirmar se a corrida foi aceita. Isso exigiria a API de verdade
da Uber (`Ride Requests API`), que precisa de aprovacao formal da Uber como parceiro de negocio -
nao e algo que um app pessoal como esse consegue simplesmente ativar com uma chave, diferente da
Google Maps ou do Waze. Pesquisei antes de prometer isso pronto: hoje a Uber restringe esse tipo
de acesso a parceiros aprovados (apps de terceiros que integram delivery/corrida em escala), nao
a desenvolvedores individuais pedindo pra automatizar a propria conta. O deep link resolve o "abre
ja com o destino preenchido, poupa de digitar" - o resto (pedir, pagar, confirmar) continua sendo
voce, no app da Uber mesmo.

**Sobre custo**: uso pessoal (algumas consultas por dia) fica bem dentro dos $200/mes de credito
gratuito que a Google da por conta - na pratica isso e gratis pro seu uso, mas e bom saber que a
API em si nao e ilimitada de graca se um dia usar muito mais que isso.

**O que isso ainda nao faz**: calcular automaticamente "voce tem voo as 14h, preciso avisar
1h30 antes" sozinho, sem voce pedir - isso juntaria a calculadora de deslocamento com o
agendador de notificacoes (que ainda depende de hospedagem fixa, ver secoes acima). Hoje voce
mesmo abre a calculadora quando quiser saber o horario de saida.

## Saude (passos, distancia, sono) — via Atalhos do iPhone

Nao existe uma API na nuvem da Apple Health pra puxar esses dados de fora (fica tudo no
aparelho, por design de privacidade) - entao o caminho e o app **Atalhos** nativo do iPhone
mandando os dados pra fora periodicamente, sem precisar de Apple Watch nem app na App Store.
Sem Watch, o iPhone sozinho ja rastreia passos/distancia pelo sensor de movimento; sono
normalmente precisa ser registrado manualmente ou por outro app de sono, entao esse dado tende a
aparecer com menos frequencia.

### Como montar o Atalho

1. Abre o app **Atalhos** no iPhone → aba Automacao → "+" → "Criar Automacao Pessoal"
2. Escolhe um gatilho (ex: "Hora do dia", todo dia as 22h)
3. Adiciona a acao **"Obter Amostras de Saude"** (Health Samples) pra cada tipo que quiser
   (Contagem de Passos, Distancia Percorrida a Pe/Corrida, Horas de Sono) com intervalo "Hoje"
4. Adiciona a acao **"Obter Conteudo de URL"** (Get Contents of URL):
   - URL: `http://SEU-IP-OU-DOMINIO:5001/api/saude/importar`
   - Metodo: POST
   - Cabecalhos: `Content-Type: application/json` (e `X-Webhook-Token` se voce configurou um - ver abaixo)
   - Corpo (JSON): `{"passos": [total de passos], "distancia_km": [distancia], "sono_horas": [horas de sono]}`
     (monta os numeros com as acoes de texto/matematica do Atalhos a partir das amostras do passo 3)
5. Desativa "Perguntar Antes de Rodar" pra ela rodar sozinha

Os dados aparecem na aba Hoje, em "Saude hoje", e entram como contexto no resumo do dia (com a
comparacao "acima/abaixo da media dos ultimos dias" calculada em Python, nunca chutada pela IA).

### Protegendo o endpoint (opcional)

Como esse endpoint fica exposto pra receber POST de fora, se um dia voce hospedar o painel em
algo acessivel pela internet (nao so na sua rede local), defina no `.env`:
```
SAUDE_WEBHOOK_TOKEN=escolha-uma-senha-aleatoria
```
e manda o header `X-Webhook-Token` com o mesmo valor no Atalho. Sem essa variavel configurada,
qualquer um que souber a URL pode mandar dados falsos - tranquilo pra uso na sua propria rede,
mas vale configurar antes de expor o painel publicamente.

## Atalhos do iPhone — captura por voz e PDF direto pro Compartilhar

> Localizacao (casa/mercado), bateria e uso de apps: passo a passo em **`docs/ATALHOS.md`**.

Dois Atalhos que falam com o painel sem precisar abrir o navegador nem logar com o PIN toda vez -
mesmo espirito do Atalho de Saude acima, cada um com seu proprio endpoint autenticado por token.

### "Ei Siri, anota" — captura por voz

1. Abre o app **Atalhos** → "+" → "Novo Atalho"
2. Adiciona a acao **"Ditar Texto"** (Dictate Text)
3. Adiciona a acao **"Obter Conteudo de URL"**:
   - URL: `http://SEU-IP-OU-DOMINIO:5001/api/atalho/capturar`
   - Metodo: POST
   - Cabecalhos: `Content-Type: application/json` (e `X-Webhook-Token` se configurou um - ver abaixo)
   - Corpo (JSON): `{"text": [Texto Ditado]}` (usa a variavel do passo 2)
4. Renomeia o Atalho pra algo curto tipo "Anota" e ativa **"Usar com Siri"** nas configuracoes dele
5. A partir dai: "Ei Siri, anota" → fala o que quiser → cai direto como tarefa/gasto/meta, igual
   digitar na captura do painel

### Compartilhar PDF direto pra uma cotacao

1. Abre o app **Atalhos** → "+" → "Novo Atalho"
2. Nas configuracoes do Atalho (icone de engrenagem), ativa **"Mostrar na Folha de Compartilhamento"**
   e restringe o tipo de conteudo aceito a **Arquivos PDF**
3. Adiciona a acao **"Pedir Entrada"** (Ask for Input) do tipo Texto, com a pergunta "Qual cotacao?"
   (voce responde algo tipo "portas" ou "ferro" - nao precisa ser o titulo exato, o painel acha a
   cotacao existente mais parecida ou cria uma nova)
4. Adiciona a acao **"Obter Conteudo de URL"**:
   - URL: `http://SEU-IP-OU-DOMINIO:5001/api/atalho/cotacao-pdf`
   - Metodo: POST
   - Corpo da requisicao: **Form** (nao JSON) com dois campos:
     - `arquivo`: o PDF recebido (Conteudo do Atalho / Shortcut Input)
     - `titulo_cotacao`: a resposta do passo 3
   - Cabecalhos: `X-Webhook-Token` se configurou um (ver abaixo)
5. A partir dai: no PDF recebido no WhatsApp/Email, aperta **Compartilhar** → escolhe esse Atalho →
   fala o titulo da cotacao → o painel le o PDF e extrai fornecedor/valor/prazo sozinho

### Widget de tela inicial (Scriptable)

Existe tambem `GET /api/atalho/resumo` (mesma autenticacao por token, sem IA - so leitura rapida do
banco) que devolve `{tarefas_pendentes, gasto_hoje, proximo_titulo, proximo_hora, resumo_curto,
linha_extra}`. Serve pra montar um widget com o app gratuito **Scriptable** (App Store), mostrando
esse resumo sem precisar abrir o painel. Widget de tela inicial: `scriptable/widget_painel.js`.
Widget de **tela de bloqueio** (usa `resumo_curto`/`linha_extra`, pensados pro espaco minimo desse
formato): `scriptable/widget_lockscreen.js`, guia completo em `docs/WIDGET_TELA_BLOQUEIO.md`.

### Protegendo os tres endpoints (opcional)

Mesma logica do Atalho de Saude:
```
PAINEL_ATALHOS_TOKEN=escolha-uma-senha-aleatoria
```
e manda o header `X-Webhook-Token` com o mesmo valor nos tres Atalhos/widget. Sem essa variavel
configurada, os endpoints ficam abertos - tranquilo na sua rede local, configure antes de expor o
painel publicamente.

## Notificar-me do Safari (iOS 27) — pra testar, ainda nao decidido se vale

O iOS 27 trouxe um recurso novo no Safari chamado **Notificar-me** (Notify Me): dentro de
qualquer site aberto, no menu de tres linhas ao lado da barra de endereco, da pra descrever em
texto livre o que voce quer que ele detecte (ex: "avise quando aparecer uma conta nova a
vencer") e escolher a frequencia de checagem. O Safari fica checando a pagina em segundo plano
nesse intervalo, usando Apple Intelligence **no proprio aparelho** pra decidir se a mudanca
descrita aconteceu, e so notifica quando ocorre de fato.

**Exige Apple Intelligence ligado no aparelho** (recurso limitado aos iPhones mais recentes que
suportam) - sem isso a opcao nem aparece no menu do Safari.

Isso nao e algo que o painel implementa ou controla - e 100% do lado do Safari, apontando pra
qualquer pagina que ja existe hoje (ex: a aba Hoje). Pra testar:

1. Abre a pagina do painel que quer monitorar no Safari do iPhone
2. Toca no menu de tres linhas ao lado da barra de endereco → **Notificar-me**
3. Descreve o que quer detectar e escolhe a frequencia de checagem
4. Confirma se a checagem em segundo plano ainda enxerga a pagina logada (a sessao do painel
   pode expirar entre uma checagem e outra) - isso so da pra confirmar testando de verdade

**Por que ainda nao virou parte oficial do fluxo**: o bot do Telegram (ver secao acima) ja avisa
na hora, com a logica exata que construimos (dedupe, botao de acao, aprendizado) - o Notificar-me
e generico (deteccao por IA em cima do que estiver na tela) e depende de configuracao manual por
pagina. Vale como experimento pra ver se ele reage mais rapido que o esperado ou se serve pra
algum uso que o Telegram nao cobre, mas nao substitui nada do que ja existe.

## Memoria — o que ele lembra sobre voce

Toda vez que voce escreve algo na captura, alem de classificar como tarefa/gasto/meta, a IA
tambem olha se aparece algum fato duravel sobre voce (preferencia, rotina, algo recorrente) que
nao e so o item pontual sendo registrado - tipo "prefere tarefas rapidas de manha" ou "trabalha
home office as quartas". Se aparecer, fica guardado e entra como contexto nas proximas chamadas
de resumo do dia e plano do dia, pra ele "lembrar" de conversa pra conversa em vez de cada
interacao ser isolada. A lista fica visivel na aba Hoje, em "O que eu lembro sobre voce", com
botao pra apagar qualquer coisa que nao fizer sentido - nada fica escondido.

Isso e so a base do que vira memoria de verdade com um chat continuo (ver Roadmap); por enquanto
a captura de texto livre e o unico jeito de alimentar isso.

Pra ele ja comecar "conhecendo voce" em vez de aprender tudo do zero, um banco novo ja nasce com
3 memorias basicas (nome, idade/aniversario, profissao) - ver `PERFIL_INICIAL` em `db.py`. So
roda uma vez (nao duplica se o app reiniciar) e pode ser editado ou apagado como qualquer outra
memoria pela aba Hoje.

## Notas — anotacao mais longa que nao e tarefa nem gasto

Diferente de Memoria (fato solto sobre voce), Notas guarda algo mais longo que voce quer poder
consultar depois - um roteiro de viagem, uma lista de coisas a verificar, um plano. Fala "anota
isso: [o que for]" ou "cria uma nota sobre [assunto] com [detalhes]" na captura, e depois pergunta
de volta ("o que eu anotei sobre Portugal?") que a IA acha pelo titulo, conteudo ou tag. Aparece
na aba Painel, em "Notas", com botao pra apagar.

## Visual

A paleta e a tipografia foram desenhadas em cima do [Nectar](https://www.meu-nectar.com/) de
proposito (`--ng-*` no CSS dele): paineis em cinza-chumbo (nao preto puro), texto quase-branco
(nao branco puro), bordas finas quase invisiveis em vez de linhas solidas, e uma paleta de cores
dessaturadas por secao (lavanda, azul, verde-jade, ambar, coral) em vez de gradiente vibrante
tipo app de tecnologia. Fonte e Inter/SF Pro (a mesma familia que o iOS usa nativamente), com
letter-spacing negativo nos titulos - o objetivo e parecer mais discreto/premium e menos
"aplicativo gritando por atencao".

Cada acao principal usa a cor da propria secao em vez de repetir sempre a mesma (concluir tarefa
= azul, registrar em meta = verde-jade, importar extrato = ambar, saude = uma cor por
metrica) - da mais variedade sem virar um arco-iris aleatorio. Detalhes tambem ganharam atencao:
anel de foco consistente em qualquer elemento navegavel por teclado/VoiceOver, transicao suave
no campo de captura ao focar, sombra dos botoes sempre na cor do proprio botao (`color-mix`) em
vez de uma cor generica fixa.

**Passada de acabamento (icones, tipografia, animacao)**: todo titulo de secao, todo estado vazio
e todo botao principal ganhou um icone SVG proprio (tracejado, no mesmo estilo da barra de abas -
nenhum emoji no app), cada um tingido com a cor da propria secao via `--secao-cor`. Fonte Inter
ganhou a faixa completa de pesos (300 a 900) pra dar mais contraste entre titulo/corpo/numero. O
chat ganhou um avatar (icone de sparkle) nas respostas do assistente e um indicador de "digitando"
com pontinhos animados em vez de spinner + texto. Troca de aba ganhou uma transicao mais viva
(fade + leve translacao/escala) em vez de so opacidade. No caminho, achei e corrigi de novo o
mesmo tipo de bug ja visto antes nesta sessao (`display` fixo no CSS batendo o atributo `hidden`
do navegador) em `.vazio` e `#saude-grid` - agora ha uma verificacao sistematica: qualquer
elemento que define `display` diferente de `none` E tambem usa `hidden` via JS precisa de um par
`seletor[hidden] { display: none; }`.

## Chat — a tela principal agora e conversa

A aba Hoje virou um chat de verdade em vez do painel de numeros: voce escreve o que quiser
("adiciona pagar aluguel dia 5", "gastei 80 no mercado", "monta meu plano do dia") e a Sonnet
decide sozinha, usando [tool use](https://docs.claude.com/en/docs/agents-and-tools/tool-use) da
API da Anthropic, se registra uma tarefa, um gasto, uma meta, gera o plano do dia, ou so responde
em texto - sem voce precisar navegar ate um formulario especifico. As ferramentas
(`registrar_tarefa`, `registrar_gasto`, `registrar_meta`, `gerar_plano_do_dia`,
`registrar_lembrete`, `registrar_memoria`) sao as mesmas operacoes que ja existiam (mais a de
datas importantes, ver abaixo), so que agora tambem acionaveis por conversa. O historico fica
salvo (`chat_mensagens`) e entra como contexto nas proximas mensagens, junto com a memoria
duravel e um resumo factual do que esta acontecendo agora (tarefas pendentes, gasto de hoje,
agenda, saude).

O painel de numeros (resumo, agenda, saude, plano do dia, deslocamento, memoria, datas
importantes) nao sumiu - virou a aba **Painel**, acessivel quando voce quiser ver os dados direto
em vez de perguntar.

**Memoria alimentada pela conversa** (nao so pela captura rapida): se voce revelar algo duravel
no meio de uma conversa no chat ("eu sempre deixo assuntos de dinheiro pra de manha"), o modelo
pode chamar `registrar_memoria` mesmo sem isso ser o pedido principal da mensagem - junto com
qualquer outra ferramenta que tenha usado, nunca no lugar dela. Fecha o item do Roadmap que
faltava aqui.

**Tarefa criada pelo chat agora entra na checagem de atraso**: antes, so tarefa vinda da captura
rapida ganhava uma data estruturada (`due_date`) pra a verificacao proativa de "tarefa atrasada"
funcionar - a ferramenta `registrar_tarefa` do chat so tinha o campo de texto livre. Agora ela
tambem extrai a data em AAAA-MM-DD quando dá pra calcular (e o system prompt do chat sabe a data
de hoje, que antes nao sabia).

**Voz** (v1): botao de microfone ao lado do campo de chat usa a Web Speech API nativa do
navegador (`SpeechRecognition`/`webkitSpeechRecognition`) - grava, transcreve em portugues e
preenche o campo de texto (voce revisa e manda, nao envia sozinho). Sem custo, sem chave nova,
sem depender da Anthropic pra isso. O botao so aparece se o navegador suportar - funciona bem em
Chrome/Android; no Safari/iOS o suporte e mais recente e pode variar por versao do iOS, entao
teste no seu aparelho antes de confiar nisso no dia a dia.

A captura rapida no topo (`Digite algo: tarefa, lembrete, gasto ou meta...`) continua existindo
em paralelo - e mais rapida pra um lancamento pontual sem abrir conversa.

## Bot do Telegram — conversa com o painel sem abrir o app

O chat da aba Hoje e ótimo, mas ainda depende de você abrir o painel. O bot do Telegram e o mesmo
pipeline de conversa (`app._processar_mensagem_chat` - nenhuma logica duplicada, nenhuma tool nova)
só que chega como mensagem de texto direto no seu Telegram, incluindo as notificações proativas
(`verificar_e_notificar`) que hoje só iam por push web. É o canal que faz o painel parecer alguém
te escrevendo, não um app que você precisa lembrar de checar.

### Como ativar

1. Fala com o [@BotFather](https://t.me/BotFather) no Telegram, manda `/newbot`, segue o passo a
   passo (nome + username terminando em `bot`) - ele te devolve um token
2. Manda qualquer mensagem pro bot novo que você acabou de criar (senão ele nunca aparece na lista
   de updates)
3. Abre no navegador `https://api.telegram.org/bot<TOKEN>/getUpdates` (troca `<TOKEN>` pelo token
   do passo 1) - o número em `"chat":{"id": ...}` da resposta é o seu `TELEGRAM_CHAT_ID`
4. Cola os dois no `.env`:
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```
5. Reinicia o `python app.py` - a partir daí, qualquer mensagem que você mandar pro bot é
   processada como se fosse o chat do painel, e as notificações proativas passam a chegar por lá
   também (além do push web, se estiver configurado - os dois convivem)

### Segurança: bot de uma pessoa só

O bot só responde mensagens vindas do `TELEGRAM_CHAT_ID` configurado - qualquer mensagem de outro
chat é ignorada em silêncio (nunca processada, nunca respondida, nunca revela que o bot existe).
Mesmo que o token do bot vaze ou alguém descubra o username, ninguém além de você consegue
conversar com o seu painel por ali.

Usa [long polling](https://core.telegram.org/bots/api#getupdates) (`getUpdates`), não webhook -
funciona rodando de casa, sem precisar expor uma URL pública/HTTPS, o mesmo motivo que o resto do
app já roda assim hoje.

### Botão de ação direto na notificação

A cobrança de tarefa parada chega no Telegram com um botão "Marcar como feito" embaixo da
mensagem - um toque marca a tarefa como concluída na hora, sem abrir o painel nem digitar nada.
Foi feito pro Telegram (não pro push web) de propósito: botão de ação em notificação push de PWA
é instável no iPhone, enquanto o Telegram suporta isso de forma sólida em qualquer aparelho. Depois
do toque, o botão some da mensagem (evita clique duplo acionando a mesma ação de novo).

## Assistente financeiro de verdade — renda, orçamento, gastos fixos e sobra do mês

O Alex não tem salário fixo (dono de construtora - o dinheiro entra de jeitos variados: venda,
pagamento de cliente, qualquer entrada avulsa), então em vez de um cadastro de "salário mensal",
o painel aprende a renda pelo que você mesmo conta no chat.

- **Renda pelo chat**: fala "entrou 3000 na conta", "recebi 500 do fulano" ou "vendi um material e
  entrou 800" - a IA registra como entrada (categoria `venda`, `cliente`, `reembolso` ou `outros`),
  sem formulário nenhum.
- **Orçamento por categoria**: "quero gastar no máximo 800 em mercado por mês" define um limite -
  o painel avisa sozinho quando o gasto real da categoria bate perto (90%) ou passa do limite
  naquele mês, uma vez por categoria+mês (não repete todo dia enquanto continuar no mesmo nível).
- **Gastos fixos/assinaturas**: "quanto eu gasto de fixo por mês?" detecta sozinho gastos que se
  repetem em pelo menos 2 meses com valor parecido (mesma descrição normalizada, não palavra em
  comum - grupo errado aqui é pior que não agrupar) e soma o total comprometido todo mês.
- **Quanto sobra pra gastar**: "quanto sobra esse mês?" calcula renda menos gasto real do mês -
  retrospectivo (o que já entrou menos o que já saiu, sem tentar adivinhar gasto futuro), mais um
  aviso à parte do quanto ainda está só planejado/cogitado (pode ou não virar gasto real).

Gastos fixos, orçamento e sobra do mês enxergam tanto o que foi digitado no chat quanto o extrato
bancário sincronizado (OFX/Pluggy) - sem isso, ficariam cegos pra maior parte do gasto de quem usa
a sincronização automática. Ressalva: as duas fontes não são reconciliadas entre si, então uma
compra digitada no chat E que também aparece depois no extrato conta duas vezes - mesmo cuidado que
a aba Bancos já pedia sobre confiar cegamente no total importado.

### Saldo do banco antes → depois

Se você conectou um banco via Pluggy (ver seção "Bancos"), o saldo de cada conta fica salvo e
atualizado a cada sincronização. Quando você cita o banco no chat/Telegram ao registrar um gasto
ou renda ("paguei a conta de luz pelo Pix do Nubank", "recebi 500 no Itaú"), a IA acha a conta pelo
nome e responde com o saldo antes e depois daquele lançamento - ajuste otimista (o valor exato só é
confirmado de verdade na próxima sincronização com o banco). Sem citar o banco, ou se a conta ainda
não tem saldo sincronizado nenhuma vez, o painel simplesmente não menciona saldo nenhum - nunca
inventa um número.

### Cobrança sem identificar (ex: "APPLE.COM/BILL")

Não existe API (paga ou gratuita) que deixe um app de terceiros ler a lista de assinaturas do seu
Apple ID - é bloqueio de plataforma por privacidade, não uma peça faltando. O painel contorna isso
reconhecendo o *padrão* da cobrança (`gastos.PADROES_COBRANCA_GENERICA`, hoje só "apple.com" -
zero custo de IA, é só reconhecimento de texto) e perguntando uma vez só: "Cobrança de R$14,90 em
'APPLE.COM/BILL' - qual assinatura é essa?". Você responde no chat ("a cobrança da apple de 14,90 é
o iCloud") e o apelido fica salvo (por descrição + valor exato, pra "iCloud" e "Apple Music" nunca
se confundirem mesmo com o mesmo texto de cobrança) - da próxima vez que aparecer, já entra
identificado na detecção de gasto fixo.

## Aprendizado de padrao pessoal — sem IA, so o seu proprio historico

O painel personaliza sozinho o numero de dias que espera antes de cobrar uma tarefa parada ou uma
espera de terceiro, com base no que voce realmente costuma fazer - nao um numero fixo pra sempre.
Sem misturar IA/rede neural nisso de proposito: e estatistica pura (`aprendizado.py`) em cima do
que ja esta salvo em `tasks`/`esperas`, robusta o bastante (usa MEDIANA, nao media) pra um caso fora
da curva nao bagunçar o limiar, e sempre auditavel - nunca caixa preta.

- So aprende com 5+ amostras de historico; antes disso, usa o padrao conservador de sempre (3 dias
  pra tarefa, 5 pra espera)
- Aprende por GRUPO primeiro (tarefas com titulo parecido, esperas com o mesmo fornecedor/pessoa -
  agrupado por palavra em comum, sem precisar de campo de categoria manual), so caindo pro
  aprendizado global quando nao ha amostra especifica suficiente
- O aprendizado global da mais peso ao que e recente (ultimas 20 amostras, nao a mediana de todo o
  histórico desde sempre) - se voce mudou de ritmo, o painel percebe mais rapido
- Tambem aprende se a propria cutucada esta funcionando: quando voce resolve rapido depois de
  avisado, o limiar cai um pouco mais (vale cutucar cedo); quando nao, fica como estava
- A sugestao de melhor dia pra tarefa sem data fixa tambem usa isso - entre dois dias com carga
  parecida, prefere o dia em que voce historicamente da conta melhor (nao so o menos ocupado)
- O valor aprendido fica sempre dentro de um piso/teto de segurança (nunca cobra no mesmo dia, nunca
  para de cobrar de vez)
- Tudo isso roda 100% por tras das cameras - nenhuma tela do painel menciona o que foi aprendido, o
  efeito aparece so no comportamento (quando cutuca, que dia sugere). `GET /api/aprendizado` existe
  so como auditoria tecnica (nenhuma tela chama esse endpoint) - mostra o que foi aprendido pra cada
  tipo, se veio do padrao ou foi aprendido, quantas amostras, e a latencia media de resposta

## Catch-up de fim do dia — "esqueci de te contar, mas eu fiz isso"

Nem tudo que voce faz passa pelo painel em tempo real. No fim do dia, so contar no chat o que ficou
de fora ("fiz academia, paguei a conta de luz e resolvi aquele negocio do fornecedor") - o painel
registra cada coisa: se ja existir uma tarefa pendente parecida, marca ela como concluida; senao,
cria uma tarefa nova ja nascendo concluida, um registro honesto do que foi feito fora do planejado.

## Datas importantes — pra qualquer area da vida, nao so financeiro

Nem tudo e tarefa (algo pra fazer agora) ou gasto/meta - tem coisa que so importa quando esta
chegando perto: validade da licenca ou do exame medico de piloto, vencimento de seguro, revisao
do carro, aniversario de alguem. Isso vive numa tabela propria (`lembretes`), separada de tarefas,
justamente pra nao poluir a lista do dia a dia com algo que so faz sentido avisar la na frente.

Da pra registrar pelo **chat** (ex: "meu exame medico de piloto vence dia 15 de janeiro, todo
ano"): a IA extrai titulo, data e se repete todo ano (`recorrente`). Pra recorrente, o calculo de
"quando e a proxima vez" (achar o proximo aniversario dessa data a partir de hoje) e feito em
Python (`notificacoes._proxima_ocorrencia`), nunca pela IA. Quando falta 7 dias ou menos pra
proxima ocorrencia, entra na verificacao proativa (ver secao "Notificacoes" acima) e manda push.
Visivel e apagavel na aba Painel, em "Datas importantes".

Tambem da pra registrar direto por um formulario curto (titulo + data + "todo ano"), sem precisar
passar pelo chat - util quando voce so quer anotar algo rapido sem conversar (`POST /api/lembretes`).

## Passada de detalhe (mascara BR, animacao, streak)

**Mascara de moeda e de data (padrao "digito da direita pra esquerda")**: o campo "guardei R$..."
de uma meta agora e texto mascarado em vez de `<input type="number">` (que so aceita ponto como
separador decimal, nunca virgula, e nao tinha como formatar em `1.234,56`). A mascara guarda so os
digitos que voce digitou - os 2 ultimos sempre viram centavos - e reconstroi o texto inteiro a
cada tecla (`aplicarMascaraMoeda` em `app.js`). O mesmo raciocinio vale pro campo de data do
formulario de lembrete (`aplicarMascaraData`): so digitos, as barras entram sozinhas na posicao
certa. Como o texto e sempre refeito do zero a partir dos digitos que sobraram, apagar (backspace)
nunca deixa pontuacao ou barra solta nem quebra o cursor - e o mesmo padrao usado nos apps de
banco brasileiros. A conversao pra numero/ISO antes de mandar pra API (`valorMascaraParaNumero`,
`mascaraDataParaIso`) e Python puro por baixo, sem envolver a IA.

**Sequencia de uso (streak)**: toda acao real no painel (falar no chat, capturar algo, concluir
tarefa/subtarefa, gerar plano do dia, guardar em meta, registrar lembrete) marca o dia de hoje como
ativo numa tabela simples (`atividade_dias`). `GET /api/streak` conta quantos dias seguidos tem
atividade, terminando hoje ou ontem - se voce ainda nao abriu o app hoje mas abriu ontem, a
sequencia continua valendo (so quebra depois de um dia inteiro sem uso, pra nao punir as 00h01). A
conta em si e uma funcao pura e testada a parte (`streak.calcular_streak`, com um stress test de
200 cenarios aleatorios contra uma implementacao de referencia). Aparece como um selo com chama
animada no topo da aba Hoje quando a sequencia e maior que zero.

**Mais uma rodada de animacao e textura**: cartoes (itens de lista, tiles do resumo, bolha do chat
do assistente) ganharam sombra suave em camadas (`--shadow-card`) e um leve gradiente interno em
vez de fundo chapado, cantos mais arredondados (16px→20px nos cartoes, 10-12px→14px em
inputs/botoes), e entram em cascata (cada item da lista com um pequeno atraso a mais que o
anterior) em vez de todos ao mesmo tempo. Uma textura de ruido bem sutil (`feTurbulence` via SVG
inline, opacidade ~3.5%, `mix-blend-mode: overlay`) cobre a tela inteira pra tirar a sensacao de
"plano/chapado". O titulo "Painel Pessoal" tem um gradiente que respira lentamente; icones de
estado vazio pulsam devagar; checkbox de subtarefa da um "pop" ao marcar; botoes levantam
levemente e o icone cresce um pouco ao passar o mouse (`@media (hover: hover)`, pra nao interferir
no toque em celular). Texto "Carregando..." em resumo/construtora agora e um shimmer em vez de
texto estatico.

**Segunda rodada de acabamento (hover, tipografia, fonte tecnica)**: todo `:hover` do app (eram uns
15 que nao tinham essa trava ainda) agora fica atras de `@media (hover: hover)`, pra nenhum efeito
"grudar" depois de um toque em celular. Titulo primario de item de lista (`.item-titulo` - nome da
tarefa, do gasto, do voo, etc.) ganhou peso 600 (antes vinha sem peso proprio nenhum, no padrao do
corpo do texto) pra criar hierarquia mais forte contra o texto secundario; titulo de secao (`h2`)
foi de 600 pra 700. Numero "hero" (tiles de estatistica, valor de gasto, bloco de METAR) ganhou uma
fonte tecnica separada do texto corrido - [JetBrains Mono](https://www.jetbrains.com/lp/mono/) via
Google Fonts, com SF Mono como fallback no iOS - dando o contraste tipo "painel/readout" que so
Inter/SF Pro em tudo nao dava.

## Previsao do tempo do dia — risco de chuva, e a que horas

Alem do clima ligado a voo (ver secao Aviacao abaixo), a aba **Hoje** mostra um aviso de chuva
pro dia a dia em geral - tipo "vou sair pra correr, vai chover?". Configura a cidade uma vez
(`CIDADE_PADRAO` no `.env`, ex: `Brusque`) e o painel busca a previsao **hora a hora** de hoje via
Open-Meteo e resume num selo no topo da aba: se nao tem risco significativo, mostra "sem risco de
chuva" discreto; se tem, mostra exatamente a janela de horas com mais chance ("risco de chuva
entre 14h e 18h, ate 80% de chance") em vez de so um numero solto de "% de chuva hoje" sem
contexto de horario - o pedido explicito foi "nao pode ser so informacao jogada".

A logica que acha essa janela (`clima.resumo_chuva_do_dia`) e pura Python, sem IA envolvida: pega
a previsao hora a hora a partir de agora, acha o pico de chance de chuva, e expande pra tras/frente
enquanto as horas forem consecutivas e continuarem acima de 50% - assim o aviso e sempre um bloco
continuo de verdade, nunca junta duas chuvas separadas do dia como se fossem uma coisa so. Testada
com casos de borda (chuva ate virar o dia, chuva so numa hora, gap que quebra o bloco, empate no
pico) e um stress test de 300 cenarios aleatorios conferindo invariantes da janela
(`tests/test_clima.py`). O mesmo resumo tambem alimenta o resumo do dia (Sonnet so menciona se for
relevante, nunca forcado) e o contexto do chat - assim da pra perguntar "vou poder sair mais
tarde?" e ele considerar a previsao. Sem `CIDADE_PADRAO` configurada, esse aviso simplesmente nao
aparece (o clima ligado a voo continua funcionando normal, ja que cada voo tem seu proprio
destino).

## Noticias sob demanda — "tem noticia de Brusque?"

Pergunta no chat algo como "tem noticia de Brusque?" ou "o que ta rolando na aviacao no Brasil?"
que ele busca manchetes recentes via o feed RSS publico do Google News (`noticias.py`) - gratuito,
sem chave, sem cadastro. **Deliberadamente so sob demanda, nunca notificacao proativa** - foi
pedido explicito do Alex, pra nao virar mais uma fonte de ruido automatico. Sem resultado, a IA diz
que nao achou nada - nunca inventa uma manchete.

## Aviacao — o Alex esta fazendo curso de piloto comercial

Aba propria (`Aviacao`) pra vida de piloto, separada do resto porque tem uma dinamica diferente
de tarefa/gasto: horas voadas, compromissos agendados com antecedencia, e o clima do destino
importa de verdade pra decidir se um voo vai rolar.

**Horas voadas**: cada voo e `data` + `destino` (+ `origem`/`observacao` opcionais) + `horas`
opcional - se `horas` vier vazio, e um voo so *agendado* (compromisso futuro, ainda nao
realizado); quando ele acontecer, basta registrar de novo com as horas ou editar. Os totais de
horas na semana/mes/total (`voos.resumo_horas`) somam so voos ja realizados (com horas) ate hoje -
conta pura em Python, testada com casos de virada de semana/mes/ano e ano bissexto
(`tests/test_voos.py`). Sem meta/numero de horas embutido no app: quantidade de hora pra cada
etapa do curso varia por escola e o app nunca inventa esse numero - so soma o que o Alex registrou.

Da pra registrar por um formulario curto na aba (com mascara de data dd/mm/aaaa, mesmo padrao "so
digito" do resto do app) ou pelo **chat** (ex: "vou voar pra Blumenau semana que vem" registra so
o compromisso; "voei 1,5h hoje, treino de pouso" registra com horas) - ferramenta
`registrar_voo`, e o chat tambem sabe dos proximos voos agendados como contexto de conversa.

**Previsao do tempo no destino**: pra cada voo agendado (data de hoje pra frente), o painel busca
a previsao do dia via [Open-Meteo](https://open-meteo.com) (gratuito, sem chave, sem cadastro) -
geocodifica o nome da cidade digitado (`clima.geocodificar_cidade`, com cache em memoria) e pega a
previsao daquele dia especifico (`clima.previsao_para_data`). Mostra chance de chuva e
minima/maxima, com destaque visual quando o codigo de tempo indica chuva/tempestade. Cada voo com
previsao ganha um link direto pro [Windy](https://www.windy.com) (camada de base de nuvem) no
local exato - sem precisar digitar a cidade de novo la. Erro de rede ou cidade nao encontrada
nunca quebra a lista de voos, so nao mostra o clima daquele item.

**METAR/TAF, com decodificacao e leitura em voz alta**: consulta direto na fonte oficial
([aviationweather.gov](https://aviationweather.gov/data/api/), NOAA - gratuito, sem chave, cobre
aerodromos do mundo todo) por codigo ICAO. O texto **bruto oficial** sempre aparece, exatamente
como a fonte manda. Alem disso, os grupos padronizados (vento, visibilidade, teto/nuvens,
temperatura, altimetro) sao decodificados pra numero/unidade real (`metar.decodificar_grupo`) -
isso e conversao exata e sem ambiguidade (`BKN008` so pode significar "nublado a 800 pes", igual
qualquer curso de meteorologia aeronautica ensina a ler na mao), nunca uma opiniao sobre categoria
de voo. **Teto** e calculado certinho pela definicao padrao (a camada BKN/OVC mais baixa - camada
FEW/SCT nunca conta como teto). O TAF e quebrado em segmentos (previsao inicial + cada BECMG/
TEMPO/FM/PROB), cada um decodificado separado, pra mostrar a tendencia ao longo do periodo (ex:
teto caindo de 1300 pra 400 pes durante a noite) em vez de misturar tudo numa frase so.

Tem um botao de **"ouvir"** (🔊) do lado do METAR e do TAF que le um resumo em portugues em voz
alta via Web Speech API (`speechSynthesis` do navegador - mesmo principio do microfone do chat,
sem custo, sem depender da Anthropic) - pra quando ler o codigo bruto de cabeca cansada nao ta
rendendo. O texto falado (`metar.resumo_falado`) e gerado por template em Python a partir dos
campos ja decodificados, nunca pela IA, e nunca inclui nenhuma palavra de categoria de voo
(testado explicitamente pra nunca aparecer "VFR"/"IFR"/"seguro"/"pode voar" no texto falado).

Decodificador testado com os exemplos reais capturados do SBBI durante o desenvolvimento, alem de
casos de borda (vento calmo/variavel/com rajada, CAVOK, ceu limpo, visibilidade vertical, TAF com
PROB+TEMPO combinados, TAF sem nenhum grupo reconhecido) - `tests/test_metar.py`.

**NOTAM**: pesquisei duas fontes - o AISWEB do DECEA (orgao brasileiro, tem API mas precisa de
cadastro gratuito) ficou inacessivel pra testar durante o desenvolvimento, e o
aviationweather.gov (que ja uso pro METAR/TAF) nao tem endpoint de NOTAM na API publica dele. Por
isso NOTAM ainda nao esta integrado - prefiro nao publicar uma integracao que eu nao consegui
testar de verdade contra a fonte real, ainda mais numa area onde um dado errado importa. Fica pra
uma proxima rodada, com a chave do AISWEB em maos.

Nao ha integracao com apps proprietarios tipo NextAtlas (sem API publica conhecida pra linkar
direto num local especifico) - o Windy foi o unico ponto de "abrir no app externo" que da pra
montar com confianca no formato da URL.

## Roadmap

**Fase 2** — Home Assistant (o Alex ainda nao tem uma instancia - fica pra quando ele reformar o
quarto e comprar os dispositivos, ano que vem); voz na v2 (resposta falada, alem de so
transcrever - hoje so transcreve pro campo de texto)

**Ideia futura** — se o painel pessoal se provar util, replicar pra outros membros da familia (cada um com seu proprio banco de dados/instancia - nunca compartilhando dados entre si sem pedir)
