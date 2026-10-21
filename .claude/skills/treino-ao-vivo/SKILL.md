---
name: treino-ao-vivo
description: Padrão "outro nível" do treino ao vivo do Painel Pessoal (ficha no chat com caixinha por exercício, troca de carga, animação do exercício). Usar sempre que for mexer no treino ao vivo, no card treino_agora/treino_carga, na ficha de treino ou em qualquer animação de exercício/academia no app ou em artefato de protótipo.
---

# Treino ao vivo - padrão do Alex

Pedido dele (2026-10-21): "o treino ao vivo tem que ser bem, bem, bem montado... não pode ser um
bonequinho qualquer coisa, tem que ser uma coisa de outro nível mesmo". Vale pra sempre.

## O que já existe (conferir no código antes de afirmar)
- `treino_vivo.py`: lê/escreve a linha da ficha (`nome|series|reps|carga`, o formato do menu;
  texto livre "supino reto 4x10 com 20kg" também é lido), acha ficha e exercício pelo que ele
  falou, rotação ("hoje é qual treino?" = ficha feita há mais tempo), carga ("25" → "25 kg").
- Tabela `treino_sessoes` (`migracoes/202610211800_tv_treino_sessoes.sql`): uma sessão por ficha
  por dia, `feitos` em JSON. O último exercício marcado registra o treino (`treinos.origem =
  'sessao'`); desmarcar desfaz.
- Chat: `comecar_treino` (card `treino_agora`), `atualizar_carga_treino` (card `treino_carga`,
  antes → depois, Desfazer pela entidade `treino_carga`). Rota da caixinha:
  `POST /api/treino/sessoes/<id>/exercicio`. Histórico atualiza pelo
  `cards.acertar_treino_agora`.
- Testes: `tests/test_treino_vivo.py` e `tests/js/cards.test.js` (treino ao vivo / troca de carga).
- Animação: `static/js/exercicio-3d.js` (43 exercícios; novo = entrada em `EX` com `pose(t)`/`cena`/`m` +
  linha no `MAPA` do `tipo()`), painel `.tv-agora` ligado em `cards-vivos.js` (`palcoPreparar`/`trocarExercicio`).
  Conferir exercício novo renderizando t=0 e t=1 lado a lado antes de dar como pronto;
  `tests/js/exercicio.test.js` pega NaN e nome mapeado errado.

## Régua de qualidade (não negociar)
1. **Nada de boneco de palito / ícone genérico.** Animação de exercício só entra se parecer
   produto premium (referência de nível: Apple Fitness+, Nike Training Club, Fitbod): figura com
   proporção humana real, volume (preenchimento, luz e sombra), equipamento desenhado de verdade
   (barra com anilhas e pegada certa, halter, banco com estofado e pés, polia com cabo e corda).
2. **Biomecânica certa.** Amplitude real do exercício (supino: barra desce até a linha do peito,
   cotovelo ~45° do tronco; crucifixo: cotovelo levemente flexionado e fixo, arco amplo; tríceps
   corda: cotovelo colado no corpo, só o antebraço se move, abre a corda embaixo). Ritmo de série:
   excêntrica ~2 s, pausa curta, concêntrica ~1 s. Nada de membro esticando/encolhendo.
3. **O músculo que trabalha aparece** (realce suave no peitoral/tríceps no pico da contração),
   sutil, nunca neon chamativo.
4. **Movimento que assenta** (`--ease-suave`/`--ease-bounce` nas transições de UI; curva
   própria no movimento do corpo), 60 fps, só `transform`/`opacity` ou desenho em canvas/SVG
   por quadro sem layout. Troca de exercício com transição, não corte seco.
   `prefers-reduced-motion`: pose parada no meio do movimento.
5. **Cada exercício tem a sua animação**; exercício sem animação pronta mostra o card limpo,
   sem figura nenhuma (melhor nada do que algo fraco).
6. **Protótipo primeiro no artefato** (fluxo da casa: ele vê ao vivo e dá veredito antes de ir
   pro app). Antes de começar uma leva de animação, perguntar o que estiver ambíguo (estilo,
   ângulo de câmera, quanto detalhe), mostrar 1 exercício bem acabado antes de fazer os outros.
7. Conferir em 390 px e no iPhone (performance no Safari), sem rolagem lateral.

## Fluxo
- Ideia nova do treino → protótipo no artefato de treino (scratchpad `painel-treino.html`,
  https://claude.ai/artifact/3RzJBSr3eYyo1duLwzRvCT) com dado inventado → veredito → app com
  teste Python + JS, SW bump, CHANGELOG, `docs/CARDS.md`.
- Dado do Alex (fichas reais, cargas) nunca vai pro artefato.
