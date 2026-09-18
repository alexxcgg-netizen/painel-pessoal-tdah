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
python -m unittest discover tests -v
```

Os testes usam mock nas chamadas a Claude (nao gastam nada nem precisam de `ANTHROPIC_API_KEY`
real) e cobrem o fluxo completo: captura, pergunta de esclarecimento quando a IA fica em duvida,
completar tarefa, quebra em subtarefas, resumo do dia, acumulo de custo, o loop de tool-use do
chat (`tests/test_claude_client.py`) e as regras de notificacao proativa (`tests/test_notificacoes.py`).

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

**Notificacoes proativas - ja implementado, roda enquanto o `python app.py` estiver de pe**: um
job (`APScheduler`, ver `iniciar_scheduler()` em `app.py`) roda a cada 3h e verifica, em Python
puro (`notificacoes.py`), quatro coisas: tarefas atrasadas (com data), metas financeiras fora do
ritmo pra bater o prazo (compara o quanto ja devia ter guardado, proporcional ao tempo passado,
com o que guardou de verdade), gasto da semana bem acima da media das ultimas semanas, e datas
importantes se aproximando (ver secao "Datas importantes" abaixo). Cada tipo de aviso so dispara
uma vez por dia (deduplicado na tabela `notificacoes_enviadas`), pra nao virar spam. Da pra forcar
uma verificacao na hora com `POST /api/notificacoes/verificar-agora`.

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

## Chat — a tela principal agora e conversa

A aba Hoje virou um chat de verdade em vez do painel de numeros: voce escreve o que quiser
("adiciona pagar aluguel dia 5", "gastei 80 no mercado", "monta meu plano do dia") e a Sonnet
decide sozinha, usando [tool use](https://docs.claude.com/en/docs/agents-and-tools/tool-use) da
API da Anthropic, se registra uma tarefa, um gasto, uma meta, gera o plano do dia, ou so responde
em texto - sem voce precisar navegar ate um formulario especifico. As ferramentas
(`registrar_tarefa`, `registrar_gasto`, `registrar_meta`, `gerar_plano_do_dia`,
`registrar_lembrete`) sao as mesmas operacoes que ja existiam (mais a de datas importantes, ver
abaixo), so que agora tambem acionaveis por conversa. O historico fica salvo (`chat_mensagens`) e
entra como contexto nas proximas mensagens, junto com a memoria duravel e um resumo factual do que
esta acontecendo agora (tarefas pendentes, gasto de hoje, agenda, saude).

O painel de numeros (resumo, agenda, saude, plano do dia, deslocamento, memoria, datas
importantes) nao sumiu - virou a aba **Painel**, acessivel quando voce quiser ver os dados direto
em vez de perguntar.

A captura rapida no topo (`Digite algo: tarefa, lembrete, gasto ou meta...`) continua existindo
em paralelo - e mais rapida pra um lancamento pontual sem abrir conversa.

## Datas importantes — pra qualquer area da vida, nao so financeiro

Nem tudo e tarefa (algo pra fazer agora) ou gasto/meta - tem coisa que so importa quando esta
chegando perto: validade da licenca ou do exame medico de piloto, vencimento de seguro, revisao
do carro, aniversario de alguem. Isso vive numa tabela propria (`lembretes`), separada de tarefas,
justamente pra nao poluir a lista do dia a dia com algo que so faz sentido avisar la na frente.

So da pra registrar pelo **chat** (ex: "meu exame medico de piloto vence dia 15 de janeiro, todo
ano"): a IA extrai titulo, data e se repete todo ano (`recorrente`). Pra recorrente, o calculo de
"quando e a proxima vez" (achar o proximo aniversario dessa data a partir de hoje) e feito em
Python (`notificacoes._proxima_ocorrencia`), nunca pela IA. Quando falta 7 dias ou menos pra
proxima ocorrencia, entra na verificacao proativa (ver secao "Notificacoes" acima) e manda push.
Visivel e apagavel na aba Painel, em "Datas importantes".

## Roadmap

**Fase 2** — comando de voz livre (falar em vez de digitar no chat); integracao com Home
Assistant (luz/temperatura/cortina do quarto ligada a rotina ou tarefa); memoria alimentada
organicamente pelas conversas do chat, nao so pela captura rapida

**Ideia futura** — se o painel pessoal se provar util, replicar pra outros membros da familia (cada um com seu proprio banco de dados/instancia - nunca compartilhando dados entre si sem pedir)
