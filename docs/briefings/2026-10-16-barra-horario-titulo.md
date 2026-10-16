# Leva 2026-10-16 - barra que sumia, horario solto, titulo de depois

Origem: "de uma olhada na conversa" - leitura do chat e do diagnostico do aparelho de 15/10
(so aprendizados gerais aqui; a copia do chat e pessoal e fica fora do git).

## O que vi
1. Diagnostico `tela` com `motivo=desvio` absurdo na tela IA: `vvTopo` = 956 (a tela inteira),
   `ancora` 0 ou negativa, barra descida 1.912 / 2.126 / 33.984 px -> fora da tela. Medida de
   transicao do iOS (o resto do dia: `ancora=956`, `bruto=0`, certo).
2. Ele mandou so um horario logo depois da IA criar uma tarefa sem hora; a IA nao gravou e ele
   repetiu mais tarde.
3. A IA disse que "a resposta veio com o titulo antigo" depois de renomear um bloco: o
   `ajustar_tarefa` devolve `titulo` = o de antes mesmo renomeando.

## Decisoes (vetaveis)
- Medida impossivel = barra no lugar normal (0px) + remedir em 400 ms, ate 5x seguidas. Limites:
  sonda entre 30% da tela e o fundo; topo visivel < 60% da tela; desvio <= 60% da tela (teclado
  preso de verdade e ~300-400 px numa tela de 956). Em segundo plano nao mede.
- Horario solto logo depois = da tarefa recem-criada/citada; so pergunta se houver 2+ sem hora.
- `ajustar_tarefa` devolve `titulo` novo + `titulo_antes`.
