# Lab v4 - Grupo G: Fechamento e recompensa (2026-10-30)

Ideias: medalha, placar do feito, pouso do dia, retrospectiva do mes. Sem commit, sem bump do SW, sem CHANGELOG (fica pro integrador).

## O que entrou
- **Medalha na hora**: `medalha.py` + `static/js/cards-medalha.js`. Recorde = 1RM estimado (Epley, `kg x (1 + reps/30)`) maior que toda marca anterior do exercicio (tabela `treino_marcas`). Cai no card do treino ao vivo, brilho segue o dedo, vira moedinha na linha. A resposta de `POST /api/treino/sessoes/<id>/exercicio` ganha `medalha`; `treino_agora` ganha `medalhas`.
- **Placar do feito**: card `placar_feito`, tabela `feito_extra`, rotas `/api/feito-hoje`, tool de chat `feito_hoje` (aceita `anotar`).
- **Pouso do dia**: card `pouso_dia`; as 21h saem placar + pouso no lugar do antigo `fechar_dia()` (que continua no codigo). Rotas `/api/pouso-dia/amanha` e `/pousar`; tool `pouso_do_dia`.
- **Retrospectiva**: card `retrospectiva` (capa no chat, historia em tela cheia), rotas `/api/retrospectiva/<AAAA-MM>` e `/meta`; aviso do dia 1 ao 3, uma vez por mes; tool `retrospectiva_mes`. O gasto que mais cresceu e dinheiro: some no visitante.

## Decisoes
- O treino ao vivo marca o exercicio, nao a serie: a "serie" e a carga e as reps da ficha na hora da marca. Faixa de reps vale o piso. A primeira marca so grava a base (sem sessao anterior, usa `treino_cargas`). Sem medalha com mais de 15 reps, sem kg ou sem reps.
- Texto por template, zero IA, tudo fato calculado.
- Retrospectiva: so tem tela quem tem dado. Meta do mes novo em config `meta_mes_AAAA-MM`. Sem pedido, o mes e o corrente a partir do dia 25, senao o anterior.
- "Hoje" = Brasilia (`completed_at` e UTC).

## Ficou de fora
- Narracao ElevenLabs da retrospectiva (gasta credito).
- "Frase mais engracada do chat" (nao e fato calculado).

## Pegadinhas
- `lower()` do SQLite so entende ASCII: comparacao de texto com acento usa `casefold` em Python.
- Migracao nova: `migracoes/202610301000_fch_fechamento.sql` (`feito_extra`, `treino_marcas`).
- `tests/test_conversa_proativa.py`: 2 assercoes mudaram (o fechamento das 21h virou placar + pouso).

## Pro integrador
Bump do `CACHE_NAME` do SW (os 3 arquivos novos ja estao no `ASSETS`), entrada no CHANGELOG + `scripts/indice_changelog.py`, rodar a suite completa.

## Passos do Alex
Nenhum obrigatorio. Pode pedir "o que eu fiz hoje" ou "me mostra a retrospectiva do mes". A medalha so aparece quando carga ou reps da ficha passam do historico.
