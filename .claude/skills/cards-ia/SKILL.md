---
name: cards-ia
description: Cria ou ajusta um card da IA no chat do Painel Pessoal do Alex (voo, gasto, date, balada, tabelionato, presente, horas do voo...) seguindo a linguagem visual que ele aprovou. Usar sempre que for criar um type de card novo, mudar o visual/interação de um card existente, ou desenhar um protótipo de card.
---

# Cards da IA - linguagem aprovada pelo Alex

Fonte completa e viva: `docs/CARDS.md` (seções "Linguagem visual dos cards" e "O que já está no
app"). Protótipo navegável das cenas aprovadas: `docs/prototipos/cards-ia-v2.html`
(artefato https://claude.ai/artifact/JzmyFm39GypNtUKXLuS1ph). Ler os dois antes de mexer.

## Régua atual: linguagem D "ao vivo" (aprovada 04/11/2026 - vale por cima do resto)
`docs/CARDS.md` "Linguagem D" + `docs/briefings/2026-11-04-cards-ao-vivo.md`.
- Card novo de compromisso/registro usa a casca `CardsD.pilula({v, cor, icone, titulo, sub, rotulo,
  valor, corpo})` (`static/js/cards-d.js` + `secoes/hoje/cards-d.css`): pílula fechada com ícone na
  cor, título, uma linha e o próximo passo à direita; toque abre (grid-rows + mola). Sem rodapé.
- **Contagem só dos segundos do servidor**: builder manda `*_s` + `gerado_ts`; front usa
  `CardsD.contagem(s, gerado_ts, fmt)` (dígitos rolam, `CardsD.tique` 1 relógio por página).
  Nunca calcular "falta X" com hora de parede no front.
- Pedaços prontos: `cadeia`, `tempoHoras`, `levar`, `anelIcone`, `anelPedacos`, `deslizaHTML`,
  `botoes`; ganchos `registrarAbrir/Chegar/Preparar/Desfazer/Desliza`.
- **Proibido (cara de IA)**: fio de luz na borda, luz que segue o dedo, inclinação 3D, selo
  brilhante, chip com emoji, título em degradê, eyebrow em MAIÚSCULAS espaçadas, herói gigante.
- Entrada só em `.card-novo`; `prefers-reduced-motion` zera tudo; alvo ≥ 44 px; dado faltando = o
  campo some (nunca "~" ou exemplo); texto com "tu", sem emoji.

## Princípios (o que fez ele gostar - não negociar)
1. **Cada assunto tem a sua cara, a família é a mesma.** Casca igual (desde 04/11 a pílula D), miolo
   desenhado pro assunto com dado real (voo = METAR e vento por aeródromo, saída = cadeia + tempo
   hora a hora + o que levar, gasto = anel do teto, conta = deslize). Ainda valem: tabelionato =
   pasta + carimbo, compras = cupom, presente = caixa. Nunca "título + lista" genérico.
2. **Uma cor por assunto** em `--card-cor` (voo `--cor-cat-1`/#8fd0ff, date #f5a3b8, balada
   #c4a1ff + neon #ff8fd1, documentos `--cor-cat-8`, presente #ffd36e, gasto #b5e48c, tarefa
   #f0a58f, alteração #aab4f6, feito #9fdcb0). O resto nos neutros do app (`--text`,
   `--text-muted`, `--text-faint`, `--border`, `--surface`). App é só escuro.
3. **A IA pensa no antes**: todo compromisso responde "a que horas eu saio / começo a me arrumar"
   (linha se arrumar → sair → chegar). Liga as pontas da semana (balada antes de voo = sono).
4. **Interação de verdade dentro do card**: caixinhas, controle segmentado com pílula que desliza,
   chips de 1 toque, ideias escolhíveis, botão de conflito - sempre otimista (muda na hora, reverte
   se a rota falhar) e com alvo de toque ≥ 44 px.
5. **Movimento que assenta**: `--ease-bounce` / `--ease-suave`, cascata ~80 ms, números contam,
   só o pedaço que mudou se mexe. Entrada animada SÓ em `.card-novo` com `--chegada`; histórico
   abre parado. Sempre um bloco `@media (prefers-reduced-motion: reduce)` zerando tudo.
6. **Resposta antes do card**: linha "pensando" com os passos reais (órbita + shimmer) que vira o
   recibo recolhível "N passos · X s"; texto palavra por palavra; card por último.
7. **Dado real do mundo dele, nunca inventado**: ICAO, NM, VFR/MVFR, meta de 150 h, SSBL padrão,
   chegar 45 min antes, se arrumar 45 min. Se não há dado (ex.: TAF não cobre a hora), não mostra.
8. Texto de UI em português do jeito dele ("tu", direto, sem robô), travessão "—".

## Contrato técnico
- **Servidor**: builder `card_<tipo>` em `cards.py` → `novo_card(type, data, actions)`; type novo
  em `TIPOS_CARD`. Valor em dinheiro → `CAMPOS_SENSIVEIS` (visitante não vê).
- **Front**: `Cards.registrar("<type>", (data, card, ctx) => html)` - renderizador PURO, devolve o
  estado final; todo texto de `data` passa por `esc`; hora "agora" vem de `ctx.agora`. Cliques via
  `data-acao="x"` + `Cards.registrarAcao("x", async (btn, cardEl, deps) => ...)` usando
  `deps.apiFetch` e `deps.aoMudar`. Coisa que precisa de rede depois de renderizar (ex.: tempo do
  voo) vai num slot `hidden` preenchido no `preparar(el)`.
- Arquivos por família: `static/js/cards-saidas.js` + `static/css/secoes/hoje/cards-saidas.css`
  (compromissos), `static/js/cards-aviacao.js` + `cards-aviacao.css` (voo/briefing/quiz/véspera),
  `static/js/cards-automacao.js` + `cards-automacao.css` (cards que o assistente puxa sozinho:
  documento, compras, assinatura - botão `.ca-botao` com o próximo passo; o que ele já respondeu
  fica no `localStorage` pro histórico não oferecer de novo), `cards-vivos.js`, `cards-tipos.js`. Selo "registrado" = `CardsPremium.TIPOS_REGISTRO` (só pra
  card que registrou algo; pergunta não ganha selo).
- Arquivo CSS/JS novo: entra em `ASSETS` do `static/service-worker.js`, em `fase7.css` /
  `templates/scripts.html`; bump do `CACHE_NAME` (e da string em `tests/test_tarefas_ver_mais.py`) -
  numa leva com várias frentes, só quem fecha a leva mexe no `CACHE_NAME`.

## Antes de dar como pronto
1. Testes: Python do builder/rota (`tests/test_cards*.py`) + JS do renderizador
   (`node --test tests/js/*.test.js`: renderiza, escapa HTML, dado faltando não quebra, e nenhuma
   classe de "cara de IA" volta). Casca D: `tests/js/cards_d.test.js` e `tests/test_cards_d.py`.
2. Captura em **390 px** (`scratchpad/ver_cards.py` ou headless equivalente com banco temporário):
   sem rolagem lateral, nada encavalado (rótulos de linha do tempo/rota quebram primeiro), "R$" e
   valor sem quebrar (`&nbsp;`), sem `pageerror`.
3. Atualizar `docs/CARDS.md` (cena nova na tabela "O que já está no app") e o `CHANGELOG.md`.
4. Mostrar as capturas pro Alex e listar as decisões tomadas pra ele vetar (regra das levas: fazer
   tudo de uma vez com briefing próprio em `docs/briefings/`, perguntar só o irreversível).
5. O que ele aprovar ou recusar vira linha nova em `docs/CARDS.md` "Linguagem visual" - esta
   habilidade resume aquele documento; se divergirem, vale o `docs/CARDS.md`.
