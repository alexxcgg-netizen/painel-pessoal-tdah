# calculos.py — inventário e guia de migração (Faixa A13, Fase 7)

Objetivo da faixa: o modelo de IA nunca deve fazer conta (amortização, juros,
saldo, projeção, percentual de meta, totais, parcelas restantes, "em N
dias"). O modelo só interpreta o texto e explica o resultado; a conta é
código determinístico, em `calculos.py` (raiz do repo).

Este documento tem duas partes:

1. **Inventário** — todo lugar em `claude_client.py`, `CHAT_TOOLS` e nos
   executores de `app.py` onde hoje se pede pro modelo calcular algo, ou
   onde o modelo devolve um número calculado que é usado depois sem
   recálculo em código. Também lista, a título de referência, os lugares
   onde a conta **já é código** (útil pra quem for consolidar tudo em cima
   de `calculos.py` depois).
2. **Instruções de troca** — pra cada violação, a chamada exata de
   `calculos.py` que deve substituir o cálculo do modelo. Essa troca em si
   **não é desta faixa** (os arquivos são das faixas A6-A9/N1, que mexem em
   `claude_client.py`/`ia/funcoes/*.py`/executores de `app.py`) — aqui só
   fica documentado o "receita pronta" pra quem for fazer.

`ia/funcoes/{chat,captura,planejamento,visao}.py` ainda não existe nesta
integração (`fase7/integracao` na data desta faixa) — quando existir, a
mesma lógica de `classify_capture`/`chat` de `claude_client.py` deve ter
migrado pra lá; a violação e a troca sugerida são as mesmas, só muda o
arquivo de destino.

---

## 1. Onde o MODELO calcula hoje (violação — precisa de troca)

### 1.1 `CAPTURE_PROMPT` (`claude_client.py`, usado por `classify_capture`)

| Arquivo | Linhas | O que é calculado hoje | Como o número calculado é usado |
|---|---|---|---|
| `claude_client.py` | 32-35 | Para `tipo="tarefa"`: o modelo converte uma data relativa em texto livre ("amanhã", "sexta que vem", "daqui uma semana") pra uma data absoluta `AAAA-MM-DD` em `quando_data`, a partir de `{hoje}` — instrução literal: *"quando der pra calcular uma data concreta a partir de hoje"*. | `app.py:725` grava `parsed.get("quando_data")` direto na coluna `due_date` de `tasks`, sem recalcular nada em código. |
| `claude_client.py` | 44-46 | Para `tipo="meta"`: o modelo calcula `prazo` (`AAAA-MM-DD`) a partir de `{hoje}` quando o texto diz algo relativo tipo "até dezembro" ou "em 6 meses" — instrução literal: *"calcule a partir de hoje ({hoje})"*. | `app.py:716` chama `create_goal(conn, parsed["titulo"], parsed["valor"], parsed.get("prazo"))` — o prazo calculado pelo modelo vira a data-limite real da meta no banco. |

**Chamador em `app.py`:** `result, error = _call_claude(claude_client.classify_capture, full_text, contexto_correcao)` em `app.py:683`; `parsed = result[0]` é usado sem validação/recálculo em `app.py:703-726`.

### 1.2 `CHAT_TOOLS` (`claude_client.py`, usado por `chat()`)

| Arquivo | Linhas | O que é calculado hoje | Como o número calculado é usado |
|---|---|---|---|
| `claude_client.py` | 305-317 (tool `registrar_tarefa`, campo `quando_data`) | Mesma conta do item 1.1: descrição do campo pede pro modelo converter `quando` (texto livre) numa data absoluta *"só quando der pra calcular uma data concreta a partir de hoje"*, e também preencher `quando_data` com a data de hoje quando houver `hora` sem referência de dia. | `app.py:2777-2784` (`exec_registrar_tarefa`, executor da tool no loop de chat) grava `entrada.get("quando_data")` direto na coluna `due_date` de `tasks`, sem recalcular. |

Nenhuma outra tool de `CHAT_TOOLS` pede conta financeira/temporal ao
modelo diretamente — as que *parecem* pedir ("calcular_gasto_viagem",
"distribuir_tarefas_na_semana") na verdade descrevem um cálculo que
**já acontece em código** no executor (ver seção 2) — o nome da tool é só
o rótulo que a IA usa pra decidir chamá-la, a conta em si não é feita
pelo modelo.

### 1.3 Resumo da troca (para as faixas A6-A9/N1)

O problema de fundo dos dois itens acima é o mesmo: **conversão de data
relativa → data absoluta** feita pelo modelo. A troca correta **não** é só
substituir por uma chamada a `calculos.dias_ate` (essa função calcula a
distância entre duas datas já absolutas, não resolve "sexta que vem"), e
sim isolar essa responsabilidade fora do modelo:

1. Pare de pedir pro modelo preencher `quando_data`/`prazo` (remova essas
   instruções de `CAPTURE_PROMPT` linhas 32-35/44-46 e da tool
   `registrar_tarefa` linhas 305-317 do `CHAT_TOOLS`). O modelo continua
   preenchendo `quando`/texto livre (isso é interpretação de linguagem
   natural, legítimo) e, se quiser, um `recorrencia`/pista estruturada
   simples (ex.: `"amanha"`, `"hoje"`, `"em_N_dias:N"`, `"proxima:SEGUNDA"`)
   — nunca a data final calculada.
2. Um parser determinístico em código (fora desta faixa — cabe a quem
   possui `app.py`/`agenda.py`, seguindo o padrão de
   `classificador_local/regras/<faixa>_<nome>.py` descrito em
   `docs/agentes/fase7-regras-faixa.md`) resolve essa pista estruturada pra
   uma data absoluta.
3. Uma vez com a data absoluta em mãos, **aí sim** `calculos.dias_ate(data,
   hoje)` é a função certa pra qualquer "faltam quantos dias" derivado
   dela (ex.: pra decidir se ainda cabe aviso antecipado, pra ordenar a
   agenda por proximidade etc.) — reaproveitando o padrão que já existe em
   vários lugares do app como `(data - hoje).days` (ex.:
   `notificacoes.py:461`, `app.py:5814`, `app.py:6796`), só que agora
   validado (data inválida vira `ValueError` claro, não uma exceção crua
   de `date.fromisoformat`).
4. Para `tipo="meta"` com prazo relativo ("em 6 meses"): mesma ideia —
   o modelo extrai a pista (`"em_N_meses:6"`) e o código resolve a data
   absoluta com `calculos.data_ultima_parcela(hoje, 7)` (a "última
   parcela" contada a partir de hoje com `n=7` cai 6 meses depois de
   hoje — reaproveitando a mesma aritmética de mês que uma parcela de
   financiamento usa, já que "daqui a N meses" e "data da parcela N" são
   o mesmo problema de calendário) **ou**, se preferir uma função com nome
   mais claro pro caso de uso, uma pequena função wrapper local
   (`vida.py`/`agenda.py`, fora desta faixa) que chama
   `calculos._somar_meses`-equivalente — como esse helper é privado em
   `calculos.py`, o jeito público de obter o mesmo resultado é via
   `calculos.data_ultima_parcela(hoje, meses + 1)`.

---

## 2. Onde a conta JÁ é código (referência — sem ação necessária desta faixa)

Estes pontos não são uma violação (o modelo não participa da conta), mas
duplicam fórmulas que `calculos.py` agora centraliza. Ficam aqui como
inventário completo (pedido pela faixa) e como sugestão de limpeza futura
pra quem for mexer nesses arquivos por outro motivo — **nenhum arquivo
desta lista pertence à faixa A13**, então nenhum deles foi editado aqui.

| Arquivo | Linhas | O que calcula | Função de `calculos.py` equivalente | Observação |
|---|---|---|---|---|
| `app.py` | 419-433 (`_calculo_meta`) | `falta`, `meses_restantes`, `dias_restantes`, `por_mes` de uma meta — já comentado no código como *"em Python puro, não pela IA"* | `calculos.projecao_meta(atual, alvo, aporte_mensal, hoje)` p/ a parte de "quanto falta guardar por mês pra bater o prazo" (a direção é invertida: hoje o código parte do prazo fixo e calcula `por_mes`; `projecao_meta` parte de um `aporte_mensal` fixo e calcula a data — são as duas metades do mesmo problema) | Bom exemplo do padrão certo: conta 100% em código, chamada por uma rota Flask (`app.py:7742`, `7767`), nunca pelo modelo. |
| `cards.py` | 354-374 (`card_meta`) | `percentual = round(min(100.0, guardado / alvo * 100), 1) if alvo > 0 else 0.0` | `calculos.percentual_meta(guardado, alvo)` | Usa `float`/1 casa, sem `Decimal`; `calculos.percentual_meta` usa `Decimal`/2 casas (`ROUND_HALF_EVEN`) e também trata `guardado` negativo (vira 0%, `card_meta` hoje não clampa o piso). |
| `app.py` | 2555-2562 (`_consultar_meta`) | A MESMA fórmula de `card_meta`, duplicada de forma independente (`pct = round(min(100.0, ... / alvo * 100)) if alvo > 0 else 0`, 0 casas aqui) | `calculos.percentual_meta(valor_guardado, valor_alvo)` | Duas implementações divergentes da mesma conta (1 casa vs 0 casas) — candidato óbvio a bug de UI (`card_meta` e `_consultar_meta` podem mostrar percentuais diferentes pra mesma meta). |
| `gastos.py` | 214-215 (`total_gasto_fixo_mensal`) | `round(sum(r["valor_medio"] for r in recorrentes), 2)` | `calculos.comprometido_mensal(assinaturas=recorrentes_como_valor, parcelas=[])` | `comprometido_mensal` foi desenhada pra também somar parcelamentos ativos (`parcelas_restantes`), útil se/quando o painel ganhar uma feature de compra parcelada (ver seção 3). |
| `gastos.py` | 218-231 (`sobra_do_mes`) | `sobra = round(renda_mes - gasto_real_mes, 2)` e variações | `calculos.saldo_apos(renda_mes, [{"valor": gasto_real_mes, "tipo": "saida"}])` cobre o caso simples; os demais campos (`sobra_considerando_planejado`) não têm equivalente 1:1 ainda (função de mais alto nível, específica do domínio "sobra do mês" — ok ficar em `gastos.py`, só a subtração base é o que `calculos.py` padroniza) | Usa `round()`/`float`, não `Decimal`. |
| `vida.py` | 482-495 (`projecao_fim_do_mes`) | Ritmo diário de gasto e projeção de saldo até o fim do mês | Sem equivalente direto na lista pedida pra esta faixa (é uma extrapolação de ritmo diário, não uma meta com aporte fixo) — poderia futuramente virar uma função nova em `calculos.py` se outra faixa precisar dela testada separadamente; por ora só documentado aqui. | — |
| `vida.py` | 500-521 (`previsao_meta`) | Ritmo de depósito dos últimos 90 dias e projeção de quando uma meta bate | Parecido com `calculos.projecao_meta`, mas deriva o "aporte mensal" do histórico de depósitos em vez de receber um valor fixo — **não** é um duplicado 1:1, é complementar. Quando o Alex pergunta "guardando X por mês, quando bate a meta?" (valor hipotético), a função certa é `calculos.projecao_meta`; quando é "no ritmo que venho guardando, quando bate?" (baseado no histórico real), continua sendo `vida.previsao_meta`. | Usa `float`, `round()`. |
| `viagem.py` | 9-11 (`custo_combustivel`) | `litros = distancia_km / km_por_litro; custo = litros * preco_por_litro` | Não há função 1:1 na lista desta faixa; se quiser padronizar em `calculos.py` no futuro seria algo como `custo_por_consumo(distancia_km, km_por_litro, preco_por_litro)` | **Risco**: divide por `km_por_litro` sem checar zero — `km_por_litro=0` (usuário digitando errado) estoura `ZeroDivisionError` cru, sem tratamento. `calculos.py` sempre trata esse tipo de entrada com `ValueError` claro; vale replicar o padrão aqui quando alguém mexer no arquivo. |

Chamado por: `app.py:3129-3146` (`exec_calcular_gasto_viagem`, executor da
tool `calcular_gasto_viagem`) — a distância/duração vêm de verdade do
Google Maps (`maps_client.tempo_de_viagem`, nunca inventadas), só a conta
de litros/custo é local e pura, já em código.

---

## 3. Funções de `calculos.py` sem chamador ainda (uso futuro)

`parcela_price`, `tabela_amortizacao`, `juros_compostos`,
`parcelas_restantes` e `data_ultima_parcela` não têm hoje nenhum ponto do
app que calcule empréstimo/financiamento/parcelamento — não existe ainda
uma feature de "compra parcelada"/"empréstimo" no painel (`grep -rn
"parcela\|juros\|amortiza"` no código de produção não retorna nada além
deste inventário). Foram implementadas mesmo assim porque a faixa pede
essas funções especificamente (provavelmente pra uma feature futura de
cartão/financiamento). Quando essa feature existir, a tool nova em
`CHAT_TOOLS`/`ia/funcoes/*.py` deve:

- pedir ao modelo **só** os dados de entrada em texto livre (valor, taxa
  se o usuário souber, número de parcelas, data da primeira parcela);
- nunca pedir "quanto fica a parcela" ou "quantos meses faltam" como algo
  que o modelo preenche — isso sempre vem de `calculos.parcela_price`/
  `calculos.tabela_amortizacao`/`calculos.parcelas_restantes`/
  `calculos.data_ultima_parcela` chamadas pelo executor em `app.py`, e o
  resultado (já calculado) é que vira contexto pro modelo **explicar** em
  português, nunca pro modelo recalcular ou conferir.

---

## 4. Referência rápida — assinatura de cada função

Todas em `calculos.py`, puras, sem banco/rede, `Decimal` pra dinheiro
(2 casas, `ROUND_HALF_EVEN`), entrada inválida sempre vira `ValueError`
claro (nunca uma exceção crua nem um número errado calado). Ver
docstring de cada função pra regra completa (divisão por zero, valor
negativo, arredondamento) e `tests/test_calculos.py` pra exemplos.

- `percentual_meta(atual, alvo) -> Decimal` — 0.00 a 100.00.
- `projecao_meta(atual, alvo, aporte_mensal, hoje) -> dict` —
  `{falta, atingivel, meses_necessarios, data_prevista}`.
- `parcela_price(valor, taxa_mensal, n) -> Decimal`.
- `tabela_amortizacao(valor, taxa_mensal, n, sistema="price"|"sac") -> list[dict]`.
- `juros_compostos(principal, taxa_periodo, n_periodos, aporte_periodico=0) -> dict`.
- `total_por_categoria(itens: list[dict]) -> dict[str, Decimal]`.
- `saldo_apos(saldo, lancamentos: list[dict]) -> Decimal`.
- `parcelas_restantes(n_total, parcela_atual) -> int`.
- `data_ultima_parcela(primeira, n) -> date`.
- `dias_ate(data, hoje) -> int`.
- `comprometido_mensal(assinaturas: list, parcelas: list) -> Decimal`.
