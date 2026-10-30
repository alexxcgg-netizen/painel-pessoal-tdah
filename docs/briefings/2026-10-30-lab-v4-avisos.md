# Lab v4, grupo C: avisos e manhã (30/10/2026)

Sete ideias: cartões da manhã, bom dia, aviso com outra cara, se-então, número no ícone, central e carro.
Tudo por trás de chave ou de configuração: sem o passo do Alex, a parte do painel fica quieta, sem erro.

## O que entrou

| Ideia | Painel | Arquivos principais |
| :--- | :--- | :--- |
| Cartões da manhã | Entre 4h e 12h o tick monta até 3 cartões e publica 1 card `cartoes_manha` no chat + push "Pra hoje". Resolver cria a tarefa, Depois volta amanhã, Esquece nunca mais puxa o assunto. | `manha.py`, `ia/config.d/cartoes_manha.json`, `static/js/cards-manha.js` |
| Bom dia | `GET/POST /api/atalho/bom-dia` (token). Guarda o sono em `saude_dados`, registra "acordou", dispara sinal `acordei` e o gatilho `acordar`. Devolve `fala` (~20 s), `linhas`, `audio_url`. Card `bom_dia` 1x por dia. | `bom_dia.py`, `rotas/avisos_manha.py` |
| Aviso com outra cara | Reenvio da insistência troca de cara: direto, humor, porquê, passo. Sorteio ponderado pelo que ele marcou Feito/tocou (piso 15%, nenhuma cara some). Sem IA, custo zero. | `aviso_cara.py`, ganchos em `app.py`, `db.py`, `rotas/push.py` |
| Se-então | Ferramenta do chat `propor_se_entao` gera o card "Quando ___ eu ___". Ativar grava; dispara 1x por dia no gatilho (acordar, sentar pra estudar, chegar em casa, voltar do treino, numa hora). Push com botão Feito: "Boa. +1 no teu dia." | `se_entao.py`, `cards.py`, `ia/funcoes/chat.py` |
| Número no ícone | Badging API: abertas e não recorrentes com data até hoje (máx. 99). Página: ao abrir, ao voltar e 700 ms depois de qualquer escrita. App fechado: cada push leva o número. | `badge.py`, `static/js/nucleo/badge.js`, `static/service-worker.js` |
| Central | Botão "Anotar no painel" (ControlWidget iOS 18) abre o app no chat com o microfone pronto. Mesmo efeito do Atalho `?capturar=1`. | `native/widgetkit/PainelControle*.swift`, `PainelApp.swift`, `init.js` |
| Carro | `GET/POST /api/atalho/carro` (token). Pega o próximo compromisso de hoje com `local` (ou voo), mede o trajeto no Maps e fala a hora de chegar. "No caminho" só se o recado custar até 10 min a mais (medido). Card `carro` com botão Waze; não repete em 3 h. | `carro.py`, `rotas/avisos_manha.py` |

## Decisões

- **Anti-invenção nos cartões**: cada cartão traz uma `evidencia` que tem de existir literalmente no contexto (conversa dele de 10 dias, resumos do diário, lembretes, tarefas) com no mínimo 12 caracteres. Sem isso o cartão é descartado. Também cai o que ele mandou esquecer, o que já é tarefa aberta e repetição. A IA falhando = nada é inventado; tenta de novo no tick (até 3 por dia). Modelo barato (haiku) pela camada `ia/`.
- **Aviso com cara não reduz aviso**: só o corpo muda; título e quantidade de reenvios ficam iguais. Desliga com a configuração `aviso_cara_ligado = 0`.
- **Badge**: conta tarefa aberta com data até hoje. O número só atualiza com o app aberto ou quando chega push (iOS não tem push silencioso para PWA).
- **Carro sem Maps**: não existe "no caminho"; a fala diz só o compromisso e quanto falta.
- **Bom dia**: o sono entra por `sono_horas` ("6,7", "6h40") ou por `dormiu` + `acordou`. Fora de 0,5 a 16 h é ignorado.
- Avisos novos entram no catálogo de avisos (`cartoes_manha`, `se_entao`, `bom_dia`) e podem ser desligados na tela de avisos.

## O que ficou de fora

- Tela de gerenciar combinados se-então: existe `GET /api/se-entao` e o card tem Testar/Desativar, mas sem lista própria. Card antigo no histórico volta ao estado "proposta".
- Web Push declarativo e push silencioso (não existem para PWA).
- O ControlWidget não foi compilado (sem Mac/Xcode aqui). Está atrás de `#if compiler(>=6.0)`, então um Xcode antigo ignora em vez de quebrar.
- Service worker: `ASSETS` ganhou `badge.js`, `cards-manha.js` e `cards-manha.css`, mas o `CACHE_NAME` não foi mexido. Quem integrar precisa subir a versão.

## O que depende do Alex

Token: o mesmo `PAINEL_ATALHOS_TOKEN`, header `X-Webhook-Token`, em todos os Atalhos abaixo.

1. **`.env`**: `GOOGLE_MAPS_API_KEY` e `ENDERECO_CASA` (sem eles o carro fala só o compromisso). Para a voz do bom dia, o ElevenLabs que já existe; sem chave o Atalho usa "Falar texto".
2. **Atalho "Bom dia"** (Automação → Alarme → "É parado", Executar Imediatamente, sem perguntar):
   1. "Buscar amostras de Saúde" (Sono, último dia) e calcular as horas, ou ler início/fim.
   2. "Obter conteúdo da URL": POST `https://SEU-PAINEL/api/atalho/bom-dia`, JSON `{"sono_horas": <horas>}` (ou `dormiu` e `acordou` em HH:MM), header do token.
   3. "Obter valor do dicionário" `fala` → "Falar texto". Se vier `audio_url` (não nulo), pode baixar e tocar o áudio em vez de falar.
3. **Atalho "Partida no carro"** (Automação → Bluetooth ou CarPlay → "Conecta", Executar Imediatamente):
   1. "Obter localização atual".
   2. POST `/api/atalho/carro` com `{"lat": ..., "lon": ...}` e o header do token.
   3. `fala` → "Falar texto". Para abrir o Waze: o card no chat já traz o botão.
4. **Gatilho "sentar pra estudar"**: Atalho (ou Siri "vou estudar") que faz POST `/api/atalho/gatilho` com `{"evento": "sentar_estudar"}`. "Chegar em casa" já dispara pelo Atalho de local que existe (`/api/atalho/local`, lugar "casa"); "acordar" dispara pelo bom dia; "voltar do treino" dispara ao registrar o treino.
5. **Número no ícone**: dar a permissão de notificação ao app na tela de início (sem ela o iOS não mostra o número).
6. **Central**: reconstruir o .ipa (GitHub Actions) e instalar; depois Central de Controle → "+" → Adicionar controle → Painel → "Anotar no painel". Exige iOS 18 e Xcode 16 no runner; se o runner for mais velho, o botão simplesmente não aparece.
   - **Sem build (alternativa)**: Atalho "Anota no painel" (Ditar texto → POST `/api/atalho/capturar` com `{"text": ...}`) adicionado à Central de Controle.

## Testes

`tests/test_lab_v4_avisos.py` (37), `tests/js/cards_manha.test.js`, `tests/js/badge.test.js`. Capturas 390 px dos quatro cards sem rolagem horizontal e alvos de toque de 44 px ou mais.
