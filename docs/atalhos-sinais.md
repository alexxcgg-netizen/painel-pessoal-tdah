# Sinais do iPhone (faixa P7) — guia de montagem

O painel deixou de só *esperar* o Alex abrir o app: agora ele também **recebe sinais** que o
iPhone já sabe sozinho (chegou/saiu de um lugar, o alarme parou, o Modo Sono começou, o
carregador foi conectado) e reage a eles — pergunta, avisa ou só guarda o histórico pro motor de
regras (faixa P4) usar depois. Tudo chega por **automações do app Atalhos** (nativo, grátis),
no endpoint genérico `POST /api/sinal`.

## Isto não é o `/api/atalho/local`

O painel já tinha `POST /api/atalho/local` (ver `docs/ATALHOS.md`, itens 1 e 2) — **continua
existindo, sem nenhuma mudança**. São coisas diferentes, de propósito diferente:

| | `/api/atalho/local` (já existia) | `/api/sinal` (novo, faixa P7) |
|---|---|---|
| Pra que serve | Só geofence casa/mercado | Qualquer sinal pessoal (local, sono, carregador...) |
| Autenticação | `X-Webhook-Token` / `PAINEL_ATALHOS_TOKEN` | `Authorization: Bearer` / `PAINEL_SINAL_TOKEN` |
| Grava histórico? | Não (só uma chave de dedup em `configuracoes`) | Sim, uma linha por sinal (tabela `sinais`) |
| Resposta | `{"mensagem": "..."}` pro Atalho **mostrar na tela** | `{"ok": true, "id": ...}`, sem texto de display |
| Quem consome | O próprio Atalho, na hora | O motor de regras (P4) e as reações da P7, depois |

**Continue usando o `/api/atalho/local` pras automações de casa e mercado que já tem montadas** —
elas já fazem o que fazem bem (checklist de saída, lista de compras ao chegar no mercado). O
`/api/sinal` é pra tudo que é **novo**: os quatro tipos abaixo, e qualquer automação futura que
só precise registrar "isto aconteceu" sem esperar uma frase de volta.

## Antes de começar

Defina `PAINEL_SINAL_TOKEN` no `.env` do servidor — uma senha longa qualquer, por exemplo:

```
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

> Este token é **diferente** do `PAINEL_ATALHOS_TOKEN` (que continua só pros endpoints antigos).
> Sem `PAINEL_SINAL_TOKEN` configurado, `POST /api/sinal` **recusa todo pedido** (fica sempre
> fechado, nunca aberto por falta de configuração — diferente do comportamento antigo).

Troque `https://SEU-DOMINIO` pelo endereço do painel (o mesmo que você abre no Safari) em todos
os exemplos abaixo.

## Molde da ação "Obter Conteúdo de URL"

Toda automação desta faixa usa a mesma ação, só muda o corpo:

- **URL:** `https://SEU-DOMINIO/api/sinal`
- **Método:** POST
- **Cabeçalhos:**
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer SEU_PAINEL_SINAL_TOKEN` (troque pelo valor real)
- **Corpo da solicitação:** JSON, com os campos:
  - `tipo` (obrigatório): um de `cheguei`, `sai`, `acordei`, `dormir`, `carregando`
  - `lugar` (opcional): nome do lugar — só faz sentido pra `cheguei`/`sai`
  - `quando` (opcional): data/hora ISO 8601 de quando aconteceu de verdade (ex.:
    `Data Atual` formatada como ISO 8601, ação **Formatar Data**); sem isso, o painel usa o
    horário em que recebeu o POST

A resposta é sempre um JSON curto (`{"ok": true, "id": 42}` ou `{"error": "..."}`) — **não** é
pra mostrar em tela, então não precisa de "Obter Valor do Dicionário" nem "Mostrar Notificação"
depois (diferente do `/api/atalho/local`).

---

## 1. Cheguei / Saí de um lugar

Além (ou em vez) do `/api/atalho/local` de casa/mercado, dá pra registrar qualquer outro lugar
que valha a pena guardar histórico (academia, trabalho, casa de alguém).

1. Atalhos → aba **Automação** → **+** → **Chegar** (Arrive) ou **Sair** (Leave).
2. Local: o que você quiser. Horário: **Qualquer**. Marque **Executar Imediatamente**.
3. Ação única: **Obter Conteúdo de URL** (molde acima), corpo JSON:
   - `tipo` = `cheguei` (gatilho Chegar) ou `sai` (gatilho Sair)
   - `lugar` = nome do lugar, ex. `academia`

**Reação embutida:** chegar no lugar `mercado` põe a lista de compras pendente como item na
Caixa do assistente (igual o `/api/atalho/local` já mostra na hora — aqui é o mesmo aviso, só
que como item da Caixa, não repetindo no mesmo dia).

## 2. Acordei (alarme parado)

1. Atalhos → aba **Automação** → **+** → **Alarme** → **Alarme Parado**.
2. Marque **Executar Imediatamente**.
3. Ação única: corpo JSON com `tipo` = `acordei` (sem `lugar`).

**Reação embutida:** garante que o briefing da manhã apareça (se a faixa P3 já estiver pronta
nesta integração; senão o sinal só fica registrado no histórico mesmo).

## 3. Dormir (Modo Sono)

1. Atalhos → aba **Automação** → **+** → **Modo Sono** → **Modo Sono Ativado**.
2. Marque **Executar Imediatamente**.
3. Ação única: corpo JSON com `tipo` = `dormir`.

## 4. Carregador conectado

1. Atalhos → aba **Automação** → **+** → **Carregador** → **Conectado**.
2. Marque **Executar Imediatamente**.
3. Ação única: corpo JSON com `tipo` = `carregando`.

> Combina bem com deixar o iPhone perto da cama à noite: registra o horário real de "foi
> carregar" sem precisar abrir o painel.

---

## Sugestões de automações úteis pra TDAH

Ideias de combinações que valem a pena montar (cada uma usa o que já existe acima):

- **"Cheguei no trabalho" / "Saí do trabalho"** (`tipo` = `cheguei`/`sai`, `lugar` = `trabalho`):
  dá pro motor de regras (P4) calcular quanto tempo você ficou lá, sem anotar manualmente.
- **Acordei tarde demais**: combine o sinal `acordei` com o horário — se o alarme parou muito
  depois do previsto, a P4 pode sugerir replanejar o dia (faixa P5) em vez de fingir que nada
  mudou.
- **Dormiu tarde 3 dias seguidos**: `dormir` alimentando um alerta de padrão, parecido com o
  "sono ruim 3 noites seguidas" que já existe pros dados de Saúde (`docs/ATALHOS.md`, item 4) —
  aqui é o horário real de deitar, não os dados agregados do app Saúde.
- **Carregando de dia (não de noite)**: pode ser sinal de bateria fraca no meio do dia — juntando
  com o sinal de `cheguei`/`sai` dá pra perceber um padrão de "saiu de casa sem carregar".
- **Chegou em qualquer lugar sem ter dormido direito**: cruzar `dormir`/`acordei` com `cheguei`
  é o tipo de regra que cabe na P4, não nesta faixa — aqui só garantimos que o dado existe.

## Testando sem sair de casa

Em cada automação, toque nela → **Executar** (ou monte o mesmo Atalho como atalho comum e rode).

- `{"error": "token invalido"}`: o cabeçalho `Authorization` está errado, ausente, ou
  `PAINEL_SINAL_TOKEN` não está configurado no servidor.
- `{"error": "tipo invalido - use um de: ..."}`: confira o valor de `tipo` (tem que ser
  exatamente um dos cinco, em minúsculo).
- `{"ok": true, "id": 42}`: gravou certo — o `id` é o número da linha na tabela `sinais`.
