# Leva 2026-10-15 - microfone, barra de abas e o que o chat mostrou

Origem: o Alex pediu que o Claude acompanhe o chat (`/ler-chat`); a leitura da semana 09-15/10
mostrou 6 problemas, e ele acrescentou dois que sente no uso: "às vezes clico pra falar e não sai,
ou não escuta nada" e "o menu da barra ainda aparece pela metade".

## 1. Barra de abas pela metade (4ª tentativa)
- Causa provável: `_medirDesvioTela` usava o MENOR desvio já visto como "normal". Se a 1ª medida
  sai 0 (iOS ainda se arrumando) e depois vira os ~34 px normais do app da tela de início, a barra
  desce 34 px = metade dela.
- Fix: "normal" = último desvio PEQUENO (≤ 60 px) medido; só desvio GRANDE (teclado preso,
  centenas de px) mexe. Nunca desce a barra por folga pequena.
- Diagnóstico: o app manda as medidas reais da tela (iPhone) pra `POST /api/diagnostico`
  (tabela `diagnostico_cliente`, últimas 500); `scripts/ler_chat.py` mostra junto. Se voltar, já
  tem o número em vez de chute.

## 2. Microfone
- "Não escuta nada": o detector de voz usa um AudioContext que o iPhone deixa "interrupted" ao
  voltar do fundo; só "suspended" era tratado. Detector surdo = "ninguém falou" = áudio jogado
  fora. Fix: retoma/recria o contexto; se o detector não recebeu som nenhum (zeros), o áudio vai
  mesmo assim (o servidor já corta eco/alucinação do Whisper).
- "Clico e não sai": `getUserMedia` que não responde deixava a barra em 0:00 pra sempre; áudio
  curto/vazio sumia calado. Fix: prazo de 5 s com aviso, 1 nova tentativa automática quando o
  microfone está ocupado, para a voz da IA antes de gravar, aviso quando gravou pouco.
- Cada falha vai pro mesmo diagnóstico (nome do erro, estado do contexto, tamanho).

## 3. O que o chat mostrou (comportamento da IA)
1. Ele pede pra IA escolher o horário ("tu me diz", "encaixa", "você escolhe") e ela pergunta.
   Regra no prompt: sem horário dito → a IA escolhe e diz que dá pra mudar.
2. Vários copos de água numa fala → 4 cards iguais. Um card só (o último estado), Desfazer de todos.
3. Card de sugestão (15:00) contradizendo o horário que a IA marcou de fato: sugestão some quando
   a mesma resposta já gravou o horário.
4. Pergunta repetida (o valor de um pagamento) - regra no prompt: não repetir pergunta pendente quando ele
   fala de outro assunto; uma vez só.
5. Perto da meia-noite: "não foi salva" pra tarefa de ontem; date de ontem lembrado hoje - regra
   no prompt (o histórico já marca a mensagem de dia que passou).
6. Número por extenso no texto ("sala doze") - só na fala (voz), nunca no texto.

## Decisões (vetáveis)
- Desvio pequeno da barra (≤ 60 px) nunca mexe nela.
- Detector de voz surdo → manda o áudio mesmo assim.
- Prazo do microfone: 5 s.
- IA escolhe o horário quando ele não diz.
