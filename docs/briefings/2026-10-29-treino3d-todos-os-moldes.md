# Leva: Treino 3D, todos os exercícios animados (29/10/2026)

Pedido do Alex: "tá bugado o halter no crucifixo, mas é pra fazer todos os movimentos de todos os exercícios sem ficar
parando". Protótipo em `docs/prototipos/academia-3d/` (fora do git), artefato
https://claude.ai/artifact/PVuFTFc3HQ46uw1LGxukpd. Nada vai pro app nesta leva.

## Decisões
- **Halter do crucifixo:** o halter era orientado só pelo eixo do cabo (`setFromUnitVectors`). Quando o cabo apontava
  quase pro -X o giro ficava indefinido e o halter (sextavado) saltava ~51°. Agora segue a rotação inteira da mão
  (`seguraHalter`), em todos os exercícios com halter. Medido: maior salto 0,6°/passo.
- **Estrutura pra paralelizar:** cada grupo do catálogo vira `moldes/<grupo>.js` (um bloco `{}` próprio, ids com
  prefixo) + `moldes/<grupo>.cat.json` (troca o "~" do catálogo no build). `build.py --so <grupo>` monta só aquele
  grupo pra testar; `ver.py` faz folha de contato + checa erro e NaN. Guia: `moldes/LEIA.md`.
- **Kit compartilhado** `moldes/00-kit.js` (polia com pilha de placas e cabo que estica, corda, barras, triângulo,
  estribo, Smith, barra fixa, paralelas, banco inclinado/declinado, kettlebell, bolas, colchonete...) pra todos os
  grupos terem o mesmo acabamento.
- **Motor:** `molde.fase(relogio)` opcional (isometria e cardio), músculo novo `tibial`, marcador `/*EXTRAS*/`.
- **9 agentes em paralelo (Sonnet, regra de economia do CLAUDE.md)**, um por grupo: peito, costas, ombros+antebraço,
  bíceps, tríceps, quadríceps, posterior+glúteos, core, panturrilha+cardio+funcional. Eu reviso cada folha, integro,
  rodo a varredura completa e publico.
- Intensidade dos músculos por EMG publicado quando houver; "estimativa" quando não.

## Pendente / ressalvas
- iPhone não conferido (o shader do músculo e o corpo esculpido já são pesados).
- Equipamento de máquina é desenhado por cada grupo com as peças do kit.

## Resultado (29/10)
- 215 exercícios animados (era 31): peito 19, costas 28, ombros+antebraço 24, bíceps 13, tríceps 17, quadríceps 21,
  posterior+glúteos 24, core 22, panturrilha+cardio+funcional 20. Nenhum "~" sobrou no catálogo.
- Varredura com tudo junto: 215 sem erro, sem NaN, sem rolagem lateral em 390 px. Folhas em academia/fotos/geral-*.png.
- EMG: cada grupo citou as fontes num comentário acima do FOCOS; a maior parte foi conferida só pelo resumo, e muitos
  valores são estimativa (marcados).
- Defeitos conhecidos relatados pelos agentes (a revisar com o Alex): elíptico sem barra de ligação, corda de pular
  atravessa o corpo no topo, remada invertida com o dorsal virado pro chão, sissy com o poste cruzando o tronco,
  leg press horizontal com moldura parecendo mesa, francês com halter possivelmente encostando no encosto, contador de
  reps não acompanha os ritmos próprios (21, alternadas, cardio).
- **Veredito do Alex (29/10): "todos estão legais"** — os 215 aprovados como estão.
