# Leva 2026-10-18 - memória sob demanda + o que o chat mostrou

Pedido do Alex: "dá uma olhada no chat... seria legal se tivesse memória, mas ele só visse ela quando eu
perguntasse. Ex.: quando foi o dia que eu arrumei o quartinho?".

## 1. Memória sob demanda
- `memoria.py` + ferramenta do chat `buscar_na_memoria(assunto, de?, ate?)`. Procura o assunto em tarefas
  (feitas = dia em que foram riscadas; sem fazer = dia marcado), no que o Alex falou no chat, resumo e anotações do
  diário, notas, esperas, decisões e gastos. Devolve acertos com data e dia da semana, mais recente primeiro.
- **Nada vai sozinho pro contexto** (custo zero até ele perguntar). A regra do prompt manda a IA chamar só quando
  ele pergunta do passado e dizer "não há registro" quando não achar, sem chutar data.
- Sem tabela nova e sem IA na busca: casamento por início de palavra e sem acento ("arrumei" acha "arrumar").
- A última mensagem dele (a própria pergunta) é ignorada, senão ela sempre "achava" ela mesma.
- Limite: só acha o que foi anotado, falado ou riscado. "Arrumei o quartinho" sem nunca ter dito ao painel não existe.

## 2. Achados do chat (16 a 18/10) e correções
- Ele listou 4 tarefas e a IA respondeu "nada foi criado ainda, só confirma": regra nova `LISTA DE TAREFAS SEM
  DIA` (cria tudo, escolhe dia e hora, avisa que dá pra mudar). Reenvio da mesma mensagem: conferir antes de dizer
  "é a mesma".
- 16/10 14:34: ele respondeu "março do ano que vem" e a IA mudou de assunto pra cobrar compromisso de antes: regra
  `RESPOSTA CURTA DELE CONTINUA O ASSUNTO`.
- Relatório: "barra fora da tela" era falso positivo (comparava com `innerH`, mas a janela visual desce junto);
  agora usa `vvTopo + vvH`. "Nunca abertos" virou "nunca vistos" (visto = tocou OU abriu o app).
- Log do servidor: o aviso de HTTP/3 do `urllib3-future` (a cada ~5 min, refaz sozinho e funciona) é filtrado.

## Decisões (vetáveis)
- Não aumentei as threads do Waitress (rajadas de fila em 16/10 12:13 e 18/10 19:46 ao abrir o app); fica como
  pendência: o app abre ~dezenas de requisições de uma vez com 4 threads.
- Não desinstalei o `urllib3-future` (veio de `niquests`, fora do `requirements.txt`), só filtrei o ruído.
- Sem mudança de JS/CSS, então o Service Worker continua v86.
