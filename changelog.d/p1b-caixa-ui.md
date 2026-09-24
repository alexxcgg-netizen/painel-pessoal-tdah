### Fase 7, P1b - Caixa do assistente e tela Assistente (UI)

- Faixa compacta "Pendencias do assistente (N)" no topo da aba Hoje
  (`#caixa-assistente`, montada via `static/js/secoes/assistente/caixa.js`):
  recolhivel, 3 itens mais urgentes com botoes de um toque (as `opcoes` do
  item, com fallback por tipo quando o item nao traz opcoes proprias);
  responder chama `POST /api/assistente/caixa/<id>/responder` e o item some
  com animacao discreta. Aviso quando `GET /api/assistente/saude` diz que o
  tick esta atrasado.
- Selo `.nav-selo` com o numero de pendencias no icone de Hoje e no novo
  botao "Assistente" da barra (`templates/navegacao.html`).
- Tela Assistente (`templates/abas/assistente.html`, `#tab-assistente`) com
  3 secoes: Caixa (todos os itens pendentes + historico), Regras (listar,
  pausar/retomar/apagar - `rotas/p4_regras.py`) e Avisos (liga/desliga por
  tipo, canal push/caixa/ambos, horario de silencio global -
  `rotas/p8_avisos.py`).
- `tests/js/caixa_assistente.test.js`: 23 testes (node --test) da logica
  pura de renderizacao/normalizacao de opcoes/contagem/aviso de atraso.
- Verificacao Playwright 390x844 (`scripts/ralph-p1b-caixa-ui/`): banco de
  teste com itens sinteticos em `assistente_itens`/`p4_regras`, faixa
  compacta, selo, recolher/expandir, responder, "Ver tudo", e as 3 secoes
  da tela Assistente. Zero erro de console.
