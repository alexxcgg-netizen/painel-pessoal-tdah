### Fase 7 - Faixa A13 (cálculos em código)

- **`calculos.py` (novo)**: módulo central de conta determinística - a IA
  nunca deve calcular juros, parcela, saldo, projeção, percentual de meta,
  total ou "faltam N dias"; agora existe um lugar único e testado pra isso.
  11 funções puras, sem banco/rede, dinheiro sempre em `Decimal` (2 casas,
  `ROUND_HALF_EVEN` - arredondamento bancário, documentado em cada função):
  `percentual_meta`, `projecao_meta`, `parcela_price`, `tabela_amortizacao`
  (Price e SAC), `juros_compostos`, `total_por_categoria`, `saldo_apos`,
  `parcelas_restantes`, `data_ultima_parcela`, `dias_ate`,
  `comprometido_mensal`. Entrada inválida (data que não parseia, número de
  parcelas <= 0, taxa que quebra a fórmula) sempre vira `ValueError` claro,
  nunca uma exceção crua ou um número errado calado.
- **`tests/test_calculos.py`**: 87 testes (`unittest`), incluindo fuzz
  (percentual sempre entre 0-100, tabela de amortização sempre fecha em
  saldo 0 pra várias combinações de valor/taxa/prazo, datas bissextas
  2024/2000/1900, listas com centenas/milhares de itens, tipos inválidos em
  todo ponto de entrada). `scripts/testes.sh tests/test_calculos.py` -> 87
  passed, 0 failed.
- **`docs/calculos.md` (novo)**: inventário arquivo:linha de todo lugar em
  `claude_client.py` (`CAPTURE_PROMPT`, `CHAT_TOOLS`) e nos executores de
  `app.py` onde o modelo hoje calcula uma data relativa (`quando_data` de
  tarefa, `prazo` de meta) e o número volta pro banco sem recálculo em
  código - com a instrução exata de troca pra quem mexer nesses arquivos
  (faixas A6-A9/N1). Documenta também, como referência, onde a conta já é
  código hoje (`app.py:_calculo_meta`, `gastos.py`, `vida.py`,
  `viagem.py`) e um achado de bug (`cards.py:card_meta` e
  `app.py:_consultar_meta` calculam percentual de meta com fórmulas
  arredondando diferente, podem divergir na tela).
