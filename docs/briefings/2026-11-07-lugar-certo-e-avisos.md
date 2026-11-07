# Leva 07/11/2026 — lugar certo, atraso sem susto, avisos variados e "tá aberto?"

Pedido do Alex (07/11), depois da leitura do chat de 06-07/11: consertar o que a leitura achou, guardar os
aprendizados, melhorar MUITO os avisos (mais estilos, mais de acordo com a situação, a IA podendo mandar aviso,
parar o aviso do navegador quando o app do iPhone dá conta) e o painel conferir na internet se o lugar está
aberto ("vou no shopping" → "agora ele tá fechado").

Regras de sempre: dado do chat/banco nunca vai pra commit/docs/teste (só o aprendizado geral); `data/painel.db`
só leitura; teste com banco temporário; texto de UI com "tu"; avisos no estilo C "Amigo" + 1 emoji
(voto 06/11, `notificacoes.py`); **não reduzir a quantidade de avisos** (TDAH, eles ajudam) — mudar o jeito.

## Achados (conferidos no banco e no código)
1. **Nenhum lugar tem coordenada.** `onde_estou._coordenada` usa `maps_client.geocodificar` (Geocoding API), que
   responde `REQUEST_DENIED` (billing do projeto). Routes e Places (New) funcionam. Resultado: `visitas.lugar` é
   NULL em todas as visitas desde que o GPS existe; casa nunca reconhecida. Às 7h43, dormindo em casa, o
   `checar_atraso` achou que ele estava fora e empurrou o remédio + 4 tarefas (tarefa sem lugar = "em casa").
2. **`sai_na_hora` ignorado no atraso.** "Às 21 tenho que buscar" virou `sai_na_hora=1` com hora 21:00 (a IA
   entendeu "sair às 21"). O `checar_atraso` leu 21:00 como hora de CHEGAR e, às 20h23 em casa, empurrou pra 21h15.
3. Título do `indo_pra` = texto cru da tarefa cortado em 48 letras; card `espera` junta o título inteiro ("…, depois
   Sta às…") e corta no meio da palavra.
4. A mesma tarefa cobrada por `travou` e `tarefa_adiada` (e de novo no dia seguinte).
5. Card/resposta com "sair de casa HH:MM" quando ele já está na rua.
6. Aviso do navegador ainda chega (há 1 inscrição de push web do Safari): o app iPhone só agenda os de hora
   conhecida; o resto (atraso, indo pra, insistência) ainda vai pelo navegador.

## Frentes (agentes em paralelo, mesma árvore, Edit só no trecho seu de arquivo compartilhado)

### A — Lugar certo + atraso sem susto (achados 1, 2)
- Coordenada de lugar sem depender da Geocoding: Places Text Search (New) com `places.location` (cota
  `lugar_busca`), cache igual ao de hoje; Geocoding vira última tentativa. Trocar também os outros usos de
  `geocodificar` que dependem dela (ex.: `posto_no_meio_do_caminho`) pra mesma função nova.
- Casa aprendida pelo GPS como reserva: visita longa de madrugada (ex.: cobre 03:00-05:00, 3+ noites no mesmo
  ponto ~150 m) = casa, se a casa não tem coordenada. Guardar em `lugares_coordenadas` com `origem: "gps"`.
- Visita gravada com `lugar` NULL e depois reconhecida: reprocessar as visitas abertas/recentes quando a
  coordenada aparece (pra hoje já funcionar).
- `checar_atraso`: (a) só tarefa com destino real (`local` ou apelido no título) — tarefa sem lugar nunca;
  (b) remédio nunca (mesma regra de remédio que já existe no app); (c) `sai_na_hora`: a hora é de SAIR —
  atrasado só se agora + 5 min > hora de sair e ele ainda não saiu; (d) visita sem lugar reconhecido e casa sem
  coordenada → não empurra nada (sem base, não chuta).
- Chat (`claude_client` prompt/ferramenta de tarefa): "às 21 tenho que buscar X em Y" = hora de ESTAR lá
  (sai_na_hora falso, a saída é calculada pra trás). `sai_na_hora` só com "saio às…", "sair às…".
- Diagnóstico: `/api/diagnostico` (ou relatório do painel) mostra quantos lugares têm coordenada e quantas
  visitas foram reconhecidas nos últimos 7 dias — pra isso nunca mais ficar invisível.
- Testes: `tests/test_onde_estou*.py` + novos.

### B — Cards e cobrança (achados 3, 4, 5)
- `indo_pra` e `espera`: nome curto do lugar/compromisso (apelido do lugar, ou "o date", "o banco" pelo
  `onde_estou._titulo_frase`/`nome_e_genero`), pra/pro certo, corte só em palavra inteira com "…".
- Cobrança: uma tarefa recebe no máximo UM cutucão de "parada/travou/adiada" a cada 48 h, e só de um tipo
  (o mais útil: `tarefa_adiada` ganha de `travou` se ela foi adiada 3+ vezes). Contar `tarefa_parada` (push) junto.
- "Sair de casa": se a última visita diz que ele não está em casa (ou há posição recente fora do raio de casa), o
  card/plano mostra a saída a partir de onde ele está ("daqui até lá: X min") ou esconde a linha "sair de casa";
  o texto da IA recebe no contexto "ele já está na rua" (não repetir o horário velho).
- `onde_estou` atraso + recado: uma mensagem só no chat (o recado pronto vai como card da mesma mensagem).
- Testes Python + JS dos cards mexidos.

### C — Avisos: mais estilos, mais certos, pelo app (achado 6 + pedido)
- **Catálogo novo** em `notificacoes.py` (ou módulo `avisos_texto.py`): para cada assunto, 4-8 variações de texto no
  estilo C escolhidas por contexto (hora do dia, clima, lugar, se é a 1ª vez/repetição, sequência de feitos,
  quanto falta) e sem repetir a última que ele viu (guardar a última variação por tipo). Assuntos novos onde faz
  sentido (chuva antes de sair, trânsito piorou, lugar fecha antes de tu chegar, chegou em casa → marca o que fez,
  bateu meta, sequência). Nunca reduzir quantidade. Título ≤ 1 linha, corpo ≤ 2 linhas da tela bloqueada.
- **Botões no aviso** (iOS `UNNotificationCategory`): Feito / +15 min / Amanhã / Abrir rota conforme o assunto,
  ligados nas rotas que já existem (`rotas/avisos_app.py` acao).
- **A IA pode mandar aviso**: ferramenta do chat `agendar_aviso` (texto curto, quando, assunto/emoji) → entra na
  lista do app (`/api/app/avisos`) e, sem app, no push web. Limite de sanidade (ex.: 20 por dia) e não no
  silencioso, salvo pedido explícito dele.
- **Navegador só de reserva**: avisos que não são de hora conhecida (atraso, indo pra, insistência, os da IA) ficam
  numa fila `GET /api/app/avisos/pendentes`; o app busca em toda chance de acordar (abrir, voltar, visita do
  GPS, background refresh `BGAppRefreshTask`, posição de viagem) e mostra como aviso LOCAL, contando de volta o que
  entregou. O push do navegador só sai se o app não pegou em X min (crítico 3 min, resto 15 min) ou se o app não
  falou com o painel nas últimas 36 h. Diagnóstico conta entregues pelo app × navegador.
- Testes Python (catálogo: toda variação ≤ limites, sem "você", com acento) + JS se houver; `checar_projeto.py` pro
  Swift.
- **Pra frente D:** texto = `avisos_texto.lugar_fechado(conn, lugar, chegada, fecha=None, abre=None, temporario=False,
  chave="lugar_fechado-<tarefa>-<dia>")` -> (titulo, corpo) sem emoji (🚪 via `com_emoji`); entrega =
  `avisos_pendentes.entregar(conn, tipo="lugar_fechado", ref=<tarefa>, titulo=com_emoji(...), corpo=..., agora=...,
  enviar_push=<fn que manda o push>)` ou, dentro do tick, `avisos.append(("lugar_fechado", ref, titulo, corpo))`.
- **Feito (frente C, 07/11):** catálogo `avisos_texto.py` (25 assuntos, 118 variações; escolha por contexto, sem repetir,
  estável por aviso, 1ª vez = texto antigo); fila `avisos_pendentes.py` + `GET /api/app/avisos/pendentes` e
  `POST .../pendentes/entregues`; tick, insistência e `onde_estou._avisar` passam pela fila quando o app está vivo;
  botões novos no app (`hora` Feito/+15 min/Amanhã, `saida` Abrir rota/+15 min, `soneca` +15 min; "+15 min" = o app
  avisa de novo sozinho, a tarefa não muda); ferramenta `agendar_aviso` (limite 20/dia, silencioso só com
  `mesmo_no_silencio`); relatório do painel conta app × navegador. Não ligados ainda (só texto pronto, esperando
  veto): `transito_piorou`, `chegou_casa`, `meta_batida`, `sequencia`.

### D — "Tá aberto?" (pedido novo)
- `maps_client.horario_funcionamento` passa a pedir também `places.currentOpeningHours` (feriado/horário
  especial) e `places.businessStatus` (CLOSED_TEMPORARILY/PERMANENTLY); cache curto (horas, não pra sempre).
- Ferramenta do chat `ver_horario_lugar(lugar, quando?)` → "aberto até 22h", "fechado agora, abre 10h",
  "fechado temporariamente". Prompt: quando ele diz que vai a um lugar (shopping, banco, loja, cartório), a IA
  confere antes de responder e avisa se estiver fechado na hora que ele vai chegar.
- Automático: tarefa com lugar criada/movida pra hoje → confere se o lugar está aberto na hora de chegada; fechado
  ou fechando em < 30 min da chegada → linha no card da tarefa + aviso (assunto novo `lugar_fechado`, da frente C).
- Cota `horario_lugar` (300/mês) continua valendo; sem cota/rede, não afirma nada.
- Testes com resposta do Google mockada.
- **Feito (D):** `horario_lugar.py` (leitura dos períodos + `situacao`/`frase_chegada` + automático) e
  `maps_client.dados_horario` (5 campos, cache 6 h, falha não cacheia; `horario_funcionamento` mantém o formato e passa a
  usar o horário especial). Chat: `ver_horario_lugar` + parágrafo "TA ABERTO?" no prompt; `registrar_tarefa`/
  `replanejar_saida` devolvem `lugar_na_chegada` quando fechado/fechando. Automático no tick de 5 min
  (`conferir_tarefas_de_hoje`, roda mesmo sem push) → `extras.horario_lugar` → linha na pílula D da tarefa
  (`data.lugar_fechado`: curta no lugar do "quando", frase inteira dentro, cor `#ffcf7a`) + aviso `lugar_fechado`
  (dedup `ja_notificou_hoje` por tarefa). Fora: card_compromisso (date/balada/documentos) e a aba Tarefas não mostram a
  linha ainda; o texto do aviso é fixo (catálogo de variações da frente C pode assumir `lugar_fechado`).

## Aprendizados (pedido dele: "pega esses aprendizados pra não errar mais")
- Memória: `hipotese-do-alex-primeiro` (conferir a base no banco antes de culpar a regra).
- `AGENTS.md`, seção de pegadinhas (cada frente escreve a sua, 1-3 linhas): Geocoding bloqueada → usar Places;
  `sai_na_hora` = hora de sair, todo cálculo de atraso/saída tem que respeitar; tarefa sem lugar não tem destino.

## Pronto quando
Suíte inteira verde (`scripts/testes.py`), `checar_projeto.py` ok, SW bump se mexer em CSS/JS do PWA,
CHANGELOG + índice, briefing com as decisões. Não commita/push sem ok dele. App iOS novo só depois do ok.
