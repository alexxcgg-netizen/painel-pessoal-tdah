# Contrato de uma direção do Laboratório HUD

Arquivo: `lab/dNN.js` (NN = 01..10). JS puro, sem biblioteca, sem import, sem fetch.
Registra exatamente:

```js
(window.DIRECOES = window.DIRECOES || {})[N] = {
  nome: "Reator",                       // 1 palavra
  ideia: "Anel central grande com o gasto do mês; anéis girando.",  // 1 linha
  acento: "#00E5FF",                     // a ÚNICA cor de destaque
  fontes: ["Chakra+Petch:wght@400;600", "JetBrains+Mono:wght@400"], // famílias do Google Fonts (formato css2 family=); a página carrega
  render(root, D, ctx) {                 // root = ShadowRoot vazio; D = dados (formato de dados_lab.json)
    // ctx = { tela: "hoje"|"financas"|"vida", irPara(tela), reduzido: bool }
    // Escreva <style> + HTML dentro de root. Todo CSS fica dentro do root (isolado).
    // Retorne uma função de limpeza (para intervals/requestAnimationFrame).
    return () => {};
  }
};
```

A página (casca) já tem: fundo #000, seletor de direção no topo e as abas Hoje/Finanças/Vida acima do palco. O palco tem a largura de um iPhone (até 430px). Cada troca de tela ou de direção chama a limpeza e `render` de novo. A direção PODE ter sua própria barra de navegação inferior (chamando `ctx.irPara`), recomendada para parecer app de verdade.

## Três telas, mesmo conteúdo em todas as direções
- **hoje**: hora (ao vivo) e data, clima (`D.hoje.clima`), botão de comando de voz (ícone microfone, 44px+) e ao lado o aviso crítico (`D.aviso_critico`) no topo; gasto do mês (`D.financas.gasto_mes`, com gráfico usando `por_dia_mes`); linha hoje / fatura / conta (`gasto_hoje`, `fatura_atual`, `saldo_conta`); "em foco agora" (`D.tarefas.em_foco`); atalhos das abas (Finanças, Vida, Tarefas, Aviação); campo do chat no rodapé (input visual, sem enviar).
- **financas**: resumo do mês (gasto, comparação com `gasto_mes_anterior`, orçamento se houver); gasto por categoria (`por_categoria`); fatura x conta; lista dos últimos 15 dias (`ultimos_15_dias`, mostra ~6 e botão "carregar mais" que revela o resto). Extrato completo e assinaturas (`assinaturas`) SÓ aparecem ao tocar (recolhidos).
- **vida**: as 18 seções (`D.vida_secoes`) como ícones pequenos no topo (grade/faixa rolável horizontal); só abre o conteúdo da seção tocada (mostre o `resumo` e 2–3 linhas plausíveis). Viagens: use `D.viagem` se existir.

## Regras visuais (todas obrigatórias)
- Fundo `#000` puro. Uma cor de destaque (`acento`) + neutros (brancos/cinzas com leve viés do acento). Semântico mínimo (um vermelho de alerta só no aviso crítico é permitido).
- Sem glow, sem box-shadow luminoso, sem text-shadow brilhante, sem LED verde. Borda fina (1px) ou nenhuma.
- Estilo HUD de ficção científica (linhas finas, anéis, grades, tipografia técnica). Sem nomes/logos/personagens de franquias.
- Animações leves e contínuas coerentes com a direção (anel girando, gráfico se desenhando, varredura, número contando, cursor piscando). Se `ctx.reduzido` for true: nada de animação contínua, estados finais direto.
- Pouca coisa na tela; detalhe só ao tocar.
- Alvos de toque >= 44px. Contraste de texto >= 4.5:1 sobre #000 (cinzas de texto no mínimo #8a8a8a para texto pequeno).
- Números com `font-variant-numeric: tabular-nums`. Moeda em pt-BR (`R$ 1.234,56`), use `Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL"})`.
- Largura: funciona de 360px a 430px, sem rolagem horizontal da página (faixas roláveis horizontais internas são ok).
- Gráficos em SVG ou canvas desenhados à mão, escala correta, rótulos só de valores reais.
- As 10 direções precisam ser diferentes de verdade em LAYOUT e LINGUAGEM VISUAL, não só na cor.
