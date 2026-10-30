# Leva: Treino 3D no app (29-30/10/2026)

Pedido do Alex: depois de aprovar os 215 exercícios no artefato ("todos estão legais") e o teste no iPhone ("acho que
tá bom"), levar o 3D pro treino ao vivo do chat. Aprovou trazer a biblioteca three.js e o corpo MakeHuman (CC0) pra
dentro do app ("sim duas").

## Decisões
- **Um motor só, carregado sob demanda.** `static/treino3d/treino3d.js` (módulo gerado pelo
  `docs/prototipos/academia-3d/academia/build_app.py` a partir do `motor.js` + `moldes/*.js` do protótipo) + o corpo
  (`static/treino3d/corpo.json`) + three.js r170 vendorizado (`static/vendor/three/`, ~1,8 MB no total). Só é baixado
  quando um card `treino_agora` mostra o painel; o fetch do service worker guarda no cache e da 2ª vez abre na hora.
  Não entram no precache do SW (deixaria toda atualização do app 1,8 MB mais pesada).
- **Um palco que muda de card.** Um renderizador WebGL só (iPhone limita contextos e memória): o palco 3D (canvas +
  etiqueta "pega mais em" + fase) vai pro card que está na tela. O motor só desenha quando o palco está visível.
- **Layout igual ao protótipo aprovado ("No chat"):** palco largo em cima (proporção 1 : 0,95, cantos 16 px), nome
  + séries/rep embaixo. A etiqueta usa a cor do card de treino.
- **Nome da ficha → exercício:** `static/js/treino3d-catalogo.js` (catálogo de 215 + mapeador). Normaliza (acento,
  "4x10", "20 kg"), sinônimos dos dois lados (pulley/cabo = polia, RDL = terra romeno, hip thrust, militar, afundo...),
  raiz de 6 letras. Ganha quem cobre mais do que ele escreveu; empate: nome exato, depois o que começa pelo mesmo
  movimento, depois a ordem do catálogo (variação mais comum primeiro: "Supino reto" = com barra). A 1ª palavra dele
  tem que estar no nome e 60% das palavras têm que bater; senão null e o painel some (nunca a animação de outro).
- **Motor SVG antigo (`exercicio-3d.js`, 43 exercícios) removido.** Sem WebGL 2 ou se o motor falhar: painel some,
  card limpo (regra da skill).
- **Rep e série:** o motor dispara `rep` no palco a cada repetição; o card conta "rep x/y" e acende as séries como antes.
  Reduced-motion: pose parada no meio do movimento e "N reps".

## Ressalvas
- O protótipo continua fora do git (`docs/prototipos/academia-3d/`); os arquivos gerados no app dizem de onde vêm.
  Mudou molde no protótipo → rodar `build_app.py` de novo.
- Defeitos conhecidos do protótipo vêm junto (lista em `2026-10-29-treino3d-todos-os-moldes.md`), inclusive o contador
  de rep que não acompanha os ritmos próprios (21, alternadas, cardio).
- Primeira abertura no iPhone baixa ~1,8 MB e monta o corpo esculpido; não medi o tempo no aparelho.

## Conferido
- `node --test tests/js/*.test.js` (novo `tests/js/treino3d.test.js`), suíte completa, smoke-test com banco temporário.
- Headless 390 px: card com supino → marca → crucifixo entra; reduced-motion; sem WebGL (painel some). Sem erro de
  página, sem rolagem lateral.
