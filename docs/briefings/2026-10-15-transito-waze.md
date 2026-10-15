# Leva 2026-10-15 - trânsito de verdade + Waze

Pedido do Alex: "o que falta hoje no painel é o trânsito"; o Waze é melhor pra ver o trânsito na
hora; tudo grátis ("pagar pra outra API não sei se valeria"); avisar nos cards quando tiver algo
tipo blitz/acidente; recalcular "a cada hora".

## O que existe e o que dá
- O painel já pede `TRAFFIC_AWARE` ao Google Routes (maps_client.tempo_de_viagem), mas com o
  trânsito do MOMENTO da pergunta, sem dizer quanto é trânsito, e o aviso "hora de sair" consulta
  1x por dia.
- Waze: só deep link (`https://waze.com/ul?ll=lat,lng&navigate=yes`), um destino, nada volta. Dado
  de trânsito/alerta do Waze só pra órgão público (Waze for Cities). Raspar o mapa deles: não.
- Blitz com certeza: não existe fonte. O mais perto e grátis: o Google diz QUAIS trechos estão
  lentos/parados (`TRAFFIC_ON_POLYLINE` → `speedReadingIntervals`), sem o motivo.

## Custo (grátis com trava)
Google, cotas grátis por mês (por SKU, desde 03/2025): Routes Pro (com trânsito) 5.000; trechos
lentos cai na faixa mais cara (tratado como Enterprise: 1.000). Geocoding (nome do trecho) 10.000.
Trava no painel (tabela `uso_maps`, por mês): lentidão 800, trânsito 4.000, básico 8.000,
nome do lugar 8.000. Passou → cai pro nível de baixo (sem lentidão → sem trânsito) e, sem nada,
erro tratado (card/aviso seguem com a folga).

## Mudanças
1. `tempo_de_viagem(partida=, lentidao=)`: `departureTime` (trânsito previsto pra hora de sair),
   `staticDuration` → `transito_min`, trechos lentos/parados (km do início, extensão, nível, ponto
   do meio, nome "BR-470, Gaspar" pelo Geocoding reverso - só pros 2 piores), `destino_ll`.
2. Card `rota` (chat): "+N min de trânsito", linha "Parado na BR-470, Gaspar (2 km) - pode ser
   acidente ou blitz", trecho pintado no mapinho, botão "Waze até X" (1º destino).
3. Aviso "hora de sair" (date/balada/compromisso com lugar) e "hora de ir pro voo": recalcula com
   trânsito no máximo 1x por hora por lugar (era 1x por dia / a cada 5 min no voo); o texto leva
   "+N min de trânsito" e o trecho parado.
4. Cards de compromisso, voo agendado e véspera: botão do Waze.
5. Tarefa com lugar: botão "Waze" nas ações (o toque no aviso "hora de sair" já abre a tarefa com
   as ações abertas → um toque e o Waze navega).

## Decisões (vetáveis)
- "A cada hora" = recálculo de hora em hora do trânsito dos compromissos de hoje (até 4 h antes),
  não um card novo no chat a cada hora.
- Trecho só vira aviso com ≥ 300 m; "lento" só aparece se tiver ≥ 1 km, "parado" sempre.
- Texto do aviso: "pode ser acidente ou blitz" - nunca afirma a causa.
- Waze vai até a 1ª parada (ele não aceita paradas no meio).
