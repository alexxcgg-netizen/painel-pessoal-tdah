# Atalhos do iPhone — guia de montagem

Tudo que o painel sabe sobre "onde você está", "quanto de bateria tem" e "quanto usou o
celular" chega por **automações do app Atalhos** (nativo, grátis). Este guia mostra como montar
cada uma, na ordem de prioridade. Leva uns 15 minutos no total.

> **Antes de começar:** defina `PAINEL_ATALHOS_TOKEN` no `.env` do servidor (uma senha longa
> qualquer, ex.: gerada com `python -c "import secrets; print(secrets.token_urlsafe(24))"`).
> Todo Atalho abaixo manda esse valor no cabeçalho `X-Webhook-Token`. Sem o token configurado,
> localização e uso de apps **recusam** o pedido (esses endpoints devolvem agenda e lista de
> compras, então não ficam abertos).

Em todos os exemplos, troque `https://SEU-DOMINIO` pelo endereço do painel (o mesmo que você
abre no Safari).

## Molde da ação "Obter Conteúdo de URL"

Todas as automações usam a mesma ação, só muda o corpo:

- **URL:** o endereço do endpoint
- **Método:** POST
- **Cabeçalhos:**
  - `Content-Type`: `application/json`
  - `X-Webhook-Token`: o valor de `PAINEL_ATALHOS_TOKEN`
- **Corpo da solicitação:** JSON, com os campos de cada seção abaixo

---

## 1. Casa: chegou / saiu (com bateria)

**O que faz:**
- **Saiu de casa:** checklist do que pegar.
  - Sempre: carteira.
  - Com bateria abaixo de 50%: carregador.
  - Em dia de academia: fone e garrafa.
  - Sexta ou sábado à noite, se você vai sair: bigode e cavanhaque.
- **Chegou em casa:** se ainda tem compromisso hoje, "Próximo: X às 14:00, sai até 13:30". À
  noite, o que ficou pendente. No meio do dia sem nada marcado, fica em silêncio.
- Mesma mensagem não se repete em 2 horas (o GPS costuma disparar mais de uma vez na porta).

**Automação "Saí de casa":**
1. Atalhos → aba **Automação** → **+** → **Sair** (Leave).
2. Local: sua casa. Horário: **Qualquer**. Marque **Executar Imediatamente**.
3. Ações:
   1. **Obter Nível da Bateria**.
   2. **Obter Conteúdo de URL** → `https://SEU-DOMINIO/api/atalho/local`, corpo JSON:
      - `evento` = `saiu`
      - `lugar` = `casa`
      - `bateria` = *Nível da Bateria* (a variável da ação 1)
   3. **Obter Valor do Dicionário** → chave `mensagem`.
   4. **Se** *Valor do Dicionário* **tem qualquer valor** → **Mostrar Notificação** com esse valor.
      → **Fim do Se**.

**Automação "Cheguei em casa":** igual, com o gatilho **Chegar** (Arrive), `evento` = `chegou` e
sem a ação de bateria (pode mandar `bateria` vazio ou nem mandar).

> **Limites da Apple:**
> - Automação de localização **sempre mostra um banner** "Executando automação...", mesmo com
>   "Executar Imediatamente". Não dá pra desligar.
> - O geofence pode atrasar alguns minutos ou falhar de vez em quando, principalmente em
>   Modo de Baixo Consumo.
> - Deixe ligado Ajustes → Privacidade → Serviços de Localização → Serviços do Sistema →
>   **Locais Importantes**.

## 2. Mercado: lista de compras

Aparece **só se tiver item na lista**. Com a lista vazia, a resposta vem vazia e o Atalho não
mostra nada.

1. Automação → **Chegar** → escolha o mercado que você mais usa (dá pra criar uma por mercado).
2. Mesmas ações do item 1, com `evento` = `chegou`, `lugar` = `mercado` e sem bateria.

Pra encher a lista, basta falar no chat: "acabou o café e o arroz".

## 2b. Aeroclube: chegou / saiu (4ª leva, 2026-10-15)

Só faz algo **em dia de voo** (voo de hoje ainda sem horas lançadas); nos outros dias a resposta
vem vazia e o Atalho fica quieto.
- **Chegou:** "Chegou no aeroclube. Decola 08:00. Confere: CIV e CMA, fone (headset), carta WAC...
  Bom voo!" (também aparece no chat). Uma vez por voo.
- **Saiu depois da hora de decolar:** "Quanto deu o voo?" — o card de horas com 1 toque chega no
  chat na hora (sem esperar o horário estimado de pouso). Saiu antes de decolar = silêncio.

1. Automação → **Chegar** → local: o aeroclube (SSBL). Mesmas ações do item 1, com `evento` =
   `chegou`, `lugar` = `aeroclube` e sem bateria.
2. Outra automação → **Sair** do mesmo local, com `evento` = `saiu`.

## 2c. Despertador que se ajusta (4ª leva, 2026-10-15)

Todo dia às 22h o Atalho pergunta ao painel a que horas você precisa acordar amanhã (primeiro
compromisso **com hora** — voo ou tarefa — menos o trajeto e o tempo de se arrumar) e cria o alarme.
Sem nada com hora amanhã, não mexe em nada.

1. Automação → **Hora do Dia** → 22:00, diariamente. Marque **Executar Imediatamente**.
2. Ações:
   1. **Obter Conteúdo de URL** → `https://SEU-DOMINIO/api/atalho/despertador?ate=07:00`
      - **Método: GET** (não precisa de corpo), cabeçalho `X-Webhook-Token` igual aos outros.
      - `ate` = seu horário normal de acordar: se não precisar levantar antes disso, a resposta
        vem `tem: false`. Pode tirar o `?ate=...` pra sempre receber a hora.
   2. **Obter Valor do Dicionário** → chave `tem`.
   3. **Se** *Valor do Dicionário* **é** `1` (verdadeiro):
      1. **Obter Valor do Dicionário** → chave `acordar` (ex.: `06:15`) do resultado da ação 1.
      2. **Criar Alarme** → hora = *Valor do Dicionário*, rótulo "Painel".
      3. (opcional) **Mostrar Notificação** com a chave `mensagem` ("Despertador às 06:15: o voo às
         08:00, sai 07:00.").
   4. **Fim do Se**.

Depois da meia-noite (até as 4h) o mesmo endereço olha o próprio dia, então rodar o Atalho de
madrugada também funciona.

### 2c-bis. "Amanhã quero acordar às 7" no chat (2026-10-16)

Você diz no chat a hora ("amanhã quero acordar às 7") e o painel guarda o pedido (ferramenta
`definir_despertador`). **O painel não consegue tocar o alarme do iPhone sozinho** — a Apple só deixa o
app Atalhos criar alarme. Por isso o card mostra a hora e um botão **"Pôr no despertador do iPhone"**,
que abre um Atalho seu **com este nome exato: `Despertador do Painel`**.

Crie o Atalho (app Atalhos → + → nome `Despertador do Painel`) com as mesmas ações do passo acima,
**sem** o `?ate=`: **Obter Conteúdo de URL** (GET, `X-Webhook-Token`) em
`https://SEU-DOMINIO/api/atalho/despertador` → **Obter Valor do Dicionário** `tem` → **Se** for 1 →
**Obter Valor do Dicionário** `acordar` → **Criar Alarme** (hora = `acordar`, rótulo "Painel").
Dá pra usar o mesmo Atalho na automação das 22h (assim o alarme também sai sem tocar no botão).

- Se um voo/compromisso do mesmo dia exigir acordar **antes** do que você pediu, vale o mais cedo e a
  IA te avisa (acordar atrasado perde o voo).
- O pedido vale só para a data dele. "Cancela o despertador" apaga.
- O botão depende do nome do Atalho ser igual; se mudar o nome, o botão não acha.

## 3. Uso do celular: quanto tempo em cada app

A Apple **não deixa o Atalhos ler o Tempo de Uso** (Screen Time). O jeito é registrar quando o
app abre e fecha. É **uma automação por app** (limite da Apple), então escolha só os 3 ou 4 que
você quer vigiar (ex.: Instagram, YouTube, TikTok).

Para cada app, crie **duas automações**: uma "For Aberto" e outra "For Fechado". Assim cada uma
manda um valor fixo, sem precisar de "Se".
1. Automação → **App** → escolha o app → marque só **For Aberto**.
2. Marque **Executar Imediatamente** e desligue **Notificar ao Executar** (esse gatilho não
   exige banner).
3. Ação única: **Obter Conteúdo de URL** → `https://SEU-DOMINIO/api/atalho/app`, corpo JSON:
   - `app` = `Instagram` (o nome, escrito igual sempre)
   - `evento` = `abriu`
4. Repita com **For Fechado** e `evento` = `fechou`.

**Resultado:**
- Domingo às 19h chega "Semana no celular: Instagram 5h20, YouTube 2h10".
- A aba **Vida → Seu progresso** mostra os últimos 7 dias.
- Sessão sem "fechou", ou com mais de 3 horas, é descartada: melhor subestimar do que inventar.

## 4. Saúde: sono, passos, distância (já existia)

O Atalho de horário que manda dados de Saúde pro `/api/saude/importar` continua igual. Veja o
`README.md`, seção **Saúde**. Ele é o que alimenta:
- o alerta de **sono ruim 3 noites seguidas**;
- a dica **sono × humor/energia** na aba Saúde.

Esse endpoint usa o **`SAUDE_WEBHOOK_TOKEN`**, que é um token separado.

**E o Health Auto Export?** Não precisa. É um app pago (a exportação automática por REST fica
no plano Premium) e manda um formato próprio. O Atalho nativo já cobre sono, passos e distância
de graça. Se um dia quiser batimento/HRV, dá pra adaptar.

**E o "Estado de Espírito" (iOS 18)?** O check-in de 1 toque na aba Hoje já cobre humor, energia
e sono. Se quiser puxar o registro do app Saúde:
- a ação é **Buscar Amostras de Saúde** → tipo **Estado de Espírito**;
- não existe gatilho automático pra ela, então teria que rodar num horário fixo.

Por enquanto não vale a complexidade.

## 5. "Ei Siri, pergunta pro painel" (conversa com a IA por voz)

A mesma IA do chat (sabe suas tarefas, memórias, agenda e faz as coisas de verdade), sem abrir
o app. A conversa aparece no chat depois. Atalho comum (não automação), com nome
**"Pergunta pro painel"** (é o nome que você fala pra Siri):

1. **Ditar Texto** (idioma Português (Brasil); "Parar de ouvir: Após uma pausa").
2. **Obter Conteúdo de URL** (molde lá de cima): `POST https://SEU-DOMINIO/api/atalho/perguntar`,
   corpo JSON `{"texto": <Texto Ditado>}`.
3. **Obter Valor do Dicionário**: chave `fala`, do Conteúdo da URL.
4. **Falar Texto**: o Valor do Dicionário.

Exemplos: "o que falta hoje?", "marca a academia como feita", "me lembra de ligar pro instrutor
amanhã às 10", "quanto gastei essa semana?". Funciona também no Apple Watch e no CarPlay (é a
Siri quem roda o Atalho). Precisa do `PAINEL_ATALHOS_TOKEN` configurado: essa rota devolve dado
pessoal e age, então sem token ela recusa.

## 6. Os que já existiam

Estão descritos no `README.md`, seção **Atalhos do iPhone**, e usam o mesmo
`PAINEL_ATALHOS_TOKEN`:
- **"Ei Siri, anota"**: `POST /api/atalho/capturar`, corpo `{"text": ...}`.
- **PDF de cotação pelo Compartilhar**: `POST /api/atalho/cotacao-pdf`.
- **Widget Scriptable**: `GET /api/atalho/resumo`.

---

## Testando sem sair de casa

Em cada automação, toque nela → **Executar** (ou monte o mesmo Atalho como atalho comum e rode).
Se voltar `{"error": "token invalido"}`, o cabeçalho `X-Webhook-Token` está diferente do `.env`.
Se voltar `{"mensagem": ""}`, está tudo certo: só não tinha nada pra dizer naquela hora.
