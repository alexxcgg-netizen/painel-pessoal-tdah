# O tick do assistente (`POST /api/tick`)

A Caixa do assistente (`docs/agentes/fase7-assistente.md`) só avisa, pergunta
e insiste porque alguma coisa chama `POST /api/tick` de tempos em tempos.
Sem isso, os itens ficam parados na Caixa (você só vê quando abrir o painel
na mão) e o push de reforço (depois de 2h e de 4h, política de insistência
do contrato) nunca sai.

## Por que precisa de algo batendo de fora

O Render no plano grátis **dorme o processo** depois de um tempo sem
requisição HTTP chegando. Um `while True: sleep(...)` rodando dentro do
próprio app não ajuda: o processo pode estar dormindo bem nesse momento.
Só uma requisição HTTP de fora acorda o servidor - por isso o tick é uma
rota (`POST /api/tick`), não uma thread de fundo, e por isso precisa de um
cron **externo** (fora do Render) chamando essa rota, não um agendador
interno.

Se você hospedar em algo que fica sempre acordado (VPS própria, por
exemplo), o cron pode rodar na própria máquina (`systemd timer`/`cron`) -
mas a rota continua sendo `POST /api/tick` de qualquer jeito, só muda quem
chama.

## O que a rota faz

1. Roda todo gatilho do assistente (`assistente.gatilhos.executar_todos`) -
   cada faixa P que tiver um `assistente/gatilhos/<faixa>_*.py` com
   `executar(conn, agora)` entra aqui.
2. Processa repetição (reenvio de push depois de 2h/4h, no máximo 3x por
   dia, respeitando o horário de silêncio) e expiração (`vence_em` vencido
   vira `expirado`) dos itens da Caixa.
3. Registra o horário desse tick (usado por `GET /api/assistente/saude` -
   se fizer mais de 15 minutos desde o último tick bem-sucedido, a UI
   mostra um aviso de "assistente pode estar atrasado").
4. Responde um JSON curto com as contagens (gatilhos executados,
   reativados, pushes enviados, expirados) - dá pra conferir no log do cron
   se rodou de verdade.

É seguro chamar em cima da hora, de novo, ou duas vezes seguidas sem
esperar a anterior responder: cada gatilho usa `chave_unica` pra não
duplicar item, e `processar_repeticoes` só manda o próximo push quando já
passou o tempo certo - rodar o tick 2x no mesmo minuto não manda push a
mais nem cria item repetido.

## Frequência recomendada

A cada **5 minutos**. Menos que isso não ganha muita coisa (os prazos da
Caixa são em horas, não minutos); mais espaçado que isso atrasa demais a
primeira notificação de um item novo (o primeiro push só sai no tick
seguinte à criação do item).

## Autenticação

A rota não usa sessão de login (quem chama - um cron externo - não guarda
cookie entre execuções). Ela é protegida por token, igual ao
`SAUDE_WEBHOOK_TOKEN`/`PAINEL_ATALHOS_TOKEN` que já existem no projeto: você
configura `PAINEL_TICK_TOKEN` no `.env` (variável nova - anotada em
`scripts/ralph-p1a-caixa/progress.txt`, ainda falta entrar no
`.env.example`, que não é arquivo meu pra editar) e manda em todo request:

```
Authorization: Bearer <PAINEL_TICK_TOKEN>
```

Sem token configurado no servidor, a rota fica **sempre fechada** (nunca
cai para "aberta pra quem estiver logado" - diferente do
`PAINEL_ATALHOS_TOKEN`, que nesse caso permite sessão, porque o tick nunca
tem sessão de verdade por trás).

Resposta sem token, com token errado ou com header faltando: `401`.

## Opção 1 (grátis, zero manutenção): cron-job.org

1. Crie uma conta em https://cron-job.org (ou qualquer serviço parecido de
   cron via HTTP gratuito).
2. Novo cron job:
   - URL: `https://<seu-app>.onrender.com/api/tick`
   - Método: `POST`
   - Intervalo: a cada 5 minutos
   - Cabeçalho customizado: `Authorization: Bearer <PAINEL_TICK_TOKEN>`
3. Salve e confira o histórico de execuções do serviço depois de alguns
   minutos - toda chamada deveria vir com `200` e `{"ok": true, ...}`.

Qualquer serviço parecido (cron-job.org, EasyCron, UptimeRobot em modo
"monitor HTTP" apontando pra rota, etc.) funciona do mesmo jeito: só
precisa conseguir mandar um `POST` com um cabeçalho customizado numa
frequência de minutos.

## Opção 2 (VPS própria, sempre ligada): systemd timer ou cron

Se o painel estiver rodando numa VPS que fica sempre acordada, não precisa
de serviço externo - um cron local já resolve, porque o processo nunca
dorme (o problema que o tick externo resolve no Render grátis não existe
aqui).

### Com `cron` (mais simples)

```
*/5 * * * * curl -fsS -X POST https://seu-dominio/api/tick \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" >/dev/null 2>&1
```

(`crontab -e`, cole a linha acima trocando URL e token.)

### Com `systemd timer` (mais robusto - reinicia sozinho se cair)

`/etc/systemd/system/painel-tick.service`:

```ini
[Unit]
Description=Tick do assistente do Painel Pessoal

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -fsS -X POST https://seu-dominio/api/tick \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

`/etc/systemd/system/painel-tick.timer`:

```ini
[Unit]
Description=Roda o tick do assistente a cada 5 minutos

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

Depois:

```
sudo systemctl daemon-reload
sudo systemctl enable --now painel-tick.timer
systemctl list-timers | grep painel-tick   # confirma o proximo disparo
journalctl -u painel-tick.service -n 20    # confirma que voltou 200
```

## Conferindo se está funcionando

- `GET /api/assistente/saude` (autenticado por sessão, igual ao resto do
  painel) devolve `{"ultimo_tick_em": ..., "minutos_desde_ultimo_tick": ...,
  "atrasado": true|false}`. `atrasado: true` quando já fez mais de 15
  minutos desde o último tick com sucesso - é esse campo que a UI usa pra
  mostrar o aviso.
- Se `atrasado` ficar sempre `true`, confira nesta ordem: (1) o cron externo
  está de fato configurado e rodando (histórico do cron-job.org, ou
  `journalctl`/`systemctl list-timers` na VPS); (2) `PAINEL_TICK_TOKEN` no
  `.env` do servidor é exatamente o mesmo que está no cabeçalho do cron;
  (3) o app não está caindo no meio do tick (log do servidor).
