# Animações dos exercícios no treino ao vivo (2026-10-21)

Pedido do Alex (depois de aprovar o artefato https://claude.ai/artifact/3RzJBSr3eYyo1duLwzRvCT):
levar as animações pro painel dele e pro do João, "de vários e vários exercícios", com os cards
de cada painel.

## Decisões (respostas dele)
- **Onde:** só no treino ao vivo (card `treino_agora`): painel pequeno em cima da lista com o
  exercício da vez animado contando reps; marcou, passa pro próximo.
- **Quantos:** ~40 (academia toda, com variações).
- **João:** leva o treino ao vivo inteiro (caixinhas, troca de carga com gráfico, Desfazer) +
  animações, no visual do painel dele, sem nada do Alex.

## Como
- `static/js/exercicio-3d.js`: um corpo 3D só (tronco por anéis + casco convexo, membros em
  cápsula, IK de 2 segmentos com polo), câmera 3/4 de cima, pintado de trás pra frente.
  Cada exercício = pose(t) + cena (equipamento) + músculo que acende no empurrão.
  t=0 é a posição contraída (segura em cima), t=1 o fim da descida. Ritmo de série: desce 2 s,
  pausa, sobe 1 s, segura.
- Exercício que não está na lista: card sem o painel (não inventa animação errada).
- `prefers-reduced-motion`: pose parada no meio do movimento.
- Mudou na implementação: treino AINDA EM ANDAMENTO anima mesmo vindo do histórico (ele fecha e reabre
  o app no meio do treino - parado ia perder a graça); treino concluído abre parado. O laço só roda
  com o painel na tela (IntersectionObserver).
- Padrão de qualidade: skill `treino-ao-vivo` (nada de boneco de palito).
