# Contrato: API externa do `financeiro-construtora`

Fonte de verdade dos dois endpoints somente-leitura que o `financeiro-construtora`
(outro repositório, outro dono de dado - o financeiro real de uma empresa, **não**
este painel pessoal) expõe pro painel pessoal do Alex. Este documento descreve o
contrato do lado de fora; o cliente deste repositório que consome ele é
`construtora_cliente.py` (`ClienteConstrutora`, Fase 7, faixa A10).

**Nunca editar nada em `/home/user/financeiro-construtora`** - é outro projeto,
outro dono de dado, regra do `docs/agentes/fase7-regras-faixa.md` desta faixa. Este
documento é só leitura do que já existe lá (código-fonte de
`painel_web/web_server.py` e `CHANGELOG.md` das versões `v3.99.14`/`v3.99.16`),
nunca uma proposta de mudança nele.

## Atualização 2026-10-10 (decisão do Alex, substitui a A10 abaixo)

> O card agora mostra 4 números prontos da construtora v3.99.90+: `saldo_caixa`
> (Dinheiro hoje), `a_receber` (A receber das vendas), `lucro_obras_fechadas`
> (+ `obras_fechadas`) e `estoque_a_venda` (+ `unidades_a_venda`). "Entradas x
> Gastos" saiu da tela. `lucro_liquido` e `margem` (gerais) continuam fora - a
> lista branca em `app.py` (`CAMPOS_RESUMO_CONSTRUTORA_PERMITIDOS`) descarta.
> Cada conta de `/api/contas_a_vencer` traz `pagador` (`"empresa"` | `"socio"`);
> `"socio"` = o Ademir paga em espécie, selo "Ademir paga", não conta como saída
> do caixa. Campo faltando = só aquele número some. Nada é recalculado aqui.

## Decisão do Alex (Fase 7, faixa A10) - histórico, ver atualização acima

> O painel pessoal mostra **só** gastos, entradas e tempo até a próxima conta a
> pagar da construtora - vindos desta API, que nunca é tocada diretamente
> (`construtora.db` não é lido nem escrito daqui, nenhum cálculo financeiro é
> duplicado). Isso substitui a regra antiga ("nunca número da construtora") - ver
> [Onde a regra antiga aparece hoje](#onde-a-regra-antiga-nunca-número-da-construtora-aparece-hoje)
> no fim deste documento pra quem for atualizar a regra.

Ou seja: `finance_core.py` (no outro repositório) continua a única fonte de
verdade matemática de lá (regra de ouro #2 do `AGENTS.md` do
`financeiro-construtora`); aqui do lado do painel pessoal, `construtora_cliente.py`
só *consome* os dois endpoints abaixo e nunca recalcula nada.

## Autenticação

Header `X-API-Key`, comparado no servidor contra a variável de ambiente
`PAINEL_EXTERNO_API_KEY` (do lado do `financeiro-construtora`; neste repositório
a mesma chave vai em `CONSTRUTORA_API_KEY`, ver `.env.example`). "Máquina falando
com máquina" - não usa a sessão por PIN do painel web da construtora.

- Sem `PAINEL_EXTERNO_API_KEY` configurada do lado de lá: rota inteira desativada,
  **fail closed** (503) - nunca fica "aberta sem querer".
- Chave ausente ou errada: 401.
- As duas rotas têm rate limit **próprio e isolado** (não compartilham contador):
  20 requisições/min por IP, em memória, do lado do `financeiro-construtora`.
  Estourar devolve 429.

## `GET /api/resumo`

Resumo financeiro alto nível - sem detalhamento por obra nem por categoria (decisão
do Alex em `v3.99.14`, "sai só o essencial").

**Requisição:** `GET {base_url}/api/resumo`, header `X-API-Key: <chave>`. Sem
parâmetros.

**Resposta `200 OK`:**

```json
{
  "status": "ok",
  "tot_entradas": 185000.0,
  "tot_saidas": 132500.0,
  "lucro_liquido": 52500.0,
  "margem": 28.4
}
```

Todos os quatro campos numéricos vêm sempre de `calcular_resumo_financeiro()`
(regra de ouro #2 do outro lado - nunca recalculado fora de `finance_core.py`).
`margem` é percentual (já multiplicado por 100, ex: `28.4` = 28,4%).

**Erros** (todos no formato `{"status": "error", "message": "..."}`):

| Código | Quando | `message` |
| :--- | :--- | :--- |
| 503 | `PAINEL_EXTERNO_API_KEY` não configurada do lado de lá | "Integração externa não configurada." |
| 401 | header ausente ou chave errada | "Chave de API inválida." |
| 429 | rate limit estourado (20 req/min/IP) | "Muitas requisições. Aguarde um instante e tente de novo." |
| 500 | exceção interna ao calcular o resumo (nunca vaza detalhe da exceção) | "Falha ao calcular o resumo financeiro." |

## `GET /api/contas_a_vencer`

Contas a pagar em aberto (`contas_pagar.status != 'Pago'`, incluindo `NULL`) que
vencem dentro da janela pedida, mais **qualquer conta já vencida** (sem limite pra
trás - conta atrasada nunca some da lista só por estar velha).

**Requisição:** `GET {base_url}/api/contas_a_vencer?dias=N`, header
`X-API-Key: <chave>`. `dias` é opcional (padrão 30), clampado do lado de lá pra um
intervalo são (a função `listar_contas_a_vencer` blinda contra `NaN`/`inf`/valores
absurdos desde `v3.99.16` - clampa pra 0-10.000 dias na função, e a rota clampa de
novo pra 1-365 no parâmetro da querystring).

**Resposta `200 OK`:**

```json
{
  "status": "ok",
  "contas": [
    {
      "vencimento": "2026-10-01",
      "valor": 8450.0,
      "fornecedor": "Cimento Forte Materiais",
      "descricao": "Compra de cimento e areia",
      "dias_ate_vencer": 5
    }
  ]
}
```

- `contas` pode ser uma lista vazia (nenhuma conta em aberto na janela pedida) -
  isso ainda é `status: "ok"`, não é erro.
- `dias_ate_vencer`: inteiro, **negativo quando já venceu** (`-3` = venceu há 3
  dias), `0` = vence hoje, positivo = dias até vencer.
- `fornecedor` e/ou `descricao` podem vir `null` (coluna opcional sem preenchimento
  do lado de lá) - nunca assumir que pelo menos um dos dois sempre existe com
  valor não-nulo (ver `_construtora_contexto_contas`/`_id_estavel_conta` em
  `app.py`, que já tratam isso com `or`).
- Data de vencimento ilegível **exclui** a conta da lista (o outro lado prefere não
  mostrar a arriscar um número errado) - nunca aparece com `vencimento: null`.
- Ordem: quem decide a ordem é o `financeiro-construtora`; hoje (`v3.99.16`) ordena
  por proximidade (vencida/mais próxima primeiro), mas este cliente não recalcula
  nem reordena - só confia na ordem recebida.

**Erros:** mesmo formato/códigos de `/api/resumo` acima (503 não configurada, 401
chave inválida, 429 rate limit - **isolado do de `/api/resumo`** -, 500 exceção
interna com mensagem genérica "Falha ao listar contas a pagar.").

## Timeout, cache e modo mock (`construtora_cliente.py`)

- Timeout de rede: **5s** por requisição (mesmo valor já usado em `app.py`).
- Cache em memória de **60s** por endpoint (`resumo` e `contas:<dias>` são chaves
  separadas) - funciona como throttle: dentro do TTL, uma chamada repetida nunca
  bate na rede de novo. Mesmo espírito do cache que já existe em `app.py`
  (`_CACHE_CONSTRUTORA`), mas numa instância própria (`ClienteConstrutora`), não
  compartilhada com o cache antigo.
- Qualquer falha (timeout, erro de conexão, HTTP de erro, JSON inválido, resposta
  que não é um objeto JSON, variável de ambiente não configurada) devolve `None` -
  **nunca levanta exceção pro chamador**. Uma falha nunca fica em cache (a próxima
  chamada tenta de novo).
- Modo mock: `CONSTRUTORA_API_MOCK=1` no ambiente, ou `ClienteConstrutora(mock=True)`
  por injeção (o segundo sempre vence se os dois estiverem presentes). Nunca faz
  chamada de rede; devolve dados sintéticos pt-BR no mesmo formato dos endpoints
  reais (inclusive uma conta já vencida, pra exercitar `dias_ate_vencer` negativo).
  Pensado pra rodar/testar o painel pessoal sem a construtora disponível.

## API pública deste cliente (o que o resto do painel pessoal pode usar)

`construtora_cliente.py` expõe só isto (decisão do Alex - nada de faturamento,
margem, lucro ou detalhamento por obra do lado do painel pessoal):

| Função | Retorno | `None` quando |
| :--- | :--- | :--- |
| `gastos_do_mes()` | `float` (`tot_saidas` do resumo) | API indisponível/não configurada, campo ausente ou não numérico |
| `entradas_do_mes()` | `float` (`tot_entradas` do resumo) | idem |
| `proxima_conta(com_valor=False)` | `{"nome": str, "dias": int}` (+ `"valor": float` se `com_valor=True`) | sem nenhuma conta em aberto, ou API indisponível |

`ClienteConstrutora` (a classe por trás dessas três funções) também está disponível
pra quem precisar injetar `base_url`/`api_key`/`mock`/`timeout`/`cache_ttl` (testes,
outro ambiente, etc) - ver docstring em `construtora_cliente.py`.

## Ligado no `app.py` (Fase 7, faixa C1)

Desde a C1, `app.py` lê a construtora **só** por este cliente (instância padrão,
`construtora_cliente.cliente_padrao()`): `_buscar_resumo_construtora`/
`_buscar_contas_a_vencer_construtora` continuam existindo (outras faixas usam), mas
agora delegam pro cliente e **filtram na entrada** - o resumo sai só com `status`,
`tot_entradas` e `tot_saidas` (nunca `lucro_liquido`, `margem` nem VGV) e cada conta só
com `vencimento`, `valor`, `fornecedor`, `descricao`, `dias_ate_vencer`. O contexto do
chat/resumo do dia e o push de conta a vencer mostram só nome + tempo até vencer (sem
valor); a lista da aba Construtora continua com o valor de cada conta.
`GET /api/construtora/resumo` funciona com `CONSTRUTORA_API_MOCK=1` (sem URL/chave). A
tabela abaixo fica como histórico do que foi trocado.

## O que este documento **não** é

`construtora_cliente.py` é um cliente **novo**, ainda não ligado a nada em
`app.py`. As chamadas antigas que já existem lá (`_buscar_resumo_construtora`,
`_buscar_contas_a_vencer_construtora`, `_cache_construtora_get`/`_cache_construtora_set`,
`_construtora_contexto_contas`, `_construtora_contexto_resumo`) continuam
funcionando exatamente como estão - **não foram trocadas nesta faixa** (`app.py` é
arquivo compartilhado, fora da lista de arquivos da faixa A10). A troca fica pro
integrador, com o mapa abaixo.

### Pontos em `app.py` que o integrador troca pelo cliente novo

Todos referenciados por número de linha do estado do `app.py` em
`fase7/integracao` no momento em que este documento foi escrito (`git log
origin/fase7/integracao` no topo era `ed0dcce`) - conferir de novo antes de
mexer, já que outras faixas também tocam `app.py`:

| Linha(s) aprox. | O que tem hoje | Troca sugerida |
| :--- | :--- | :--- |
| 1466-1483 (`_CACHE_CONSTRUTORA`, `_cache_construtora_get`/`_set`) | cache manual em dict de módulo | some - vira o cache interno de `ClienteConstrutora` |
| 1486-1507 (`_buscar_resumo_construtora`) | `requests.get` direto + cache manual | `ClienteConstrutora.resumo()` (ou `gastos_do_mes()`/`entradas_do_mes()` se só o valor for usado) |
| 1509-1534 (`_buscar_contas_a_vencer_construtora`) | idem, endpoint de contas | `ClienteConstrutora.contas_a_vencer(dias=...)` (ou `proxima_conta()` se só a mais próxima interessar) |
| 1661-1681 (`_construtora_contexto_contas`) | frase sobre a próxima conta pro resumo do dia/chat | `proxima_conta()` + montar a frase (mais simples: já vem `{"nome", "dias"}` prontos) |
| 1684-1697 (`_construtora_contexto_resumo`) | frase com entradas/saídas/lucro/margem + contas | **atenção**: hoje inclui lucro/margem, que a decisão do Alex (Fase 7 A10) não autoriza mais pro painel pessoal mostrar - revisar o texto pra só "gastos, entradas e tempo até a próxima conta", não só trocar a chamada por baixo |
| 4451 (dentro do laço de avisos/notificações) | `_buscar_contas_a_vencer_construtora(dias=30)` direto | `ClienteConstrutora.contas_a_vencer(dias=30)` (o laço em si, que decide o que notificar, não muda) |
| 7788-7802 (`GET /api/construtora/resumo`, rota Flask) | monta `{"configurado", "dados", "contas"}` a partir das duas funções antigas | decidir se essa rota deve mudar de formato também (fora do escopo desta faixa - documentado aqui, não decidido) |

### Onde a regra antiga ("nunca número da construtora") aparece hoje

Grep feito em `app.py` (system prompt do chat) e `cards.py` (cards) no estado
citado acima:

- `claude_client.py:83-85` - `CHAT_SYSTEM_PROMPT`: injeta `{construtora}` (a frase
  de `_construtora_contexto_resumo`) com a instrução "mencione só se fizer sentido,
  não force".
- `claude_client.py:172-181` - `CHAT_SYSTEM_PROMPT`: **é aqui que mora a regra**
  ("Nunca cite um valor em R$ específico da construtora na resposta [...] esses
  números moram só no financeiro-construtora, sistema separado do painel pessoal
  [...] Fale do negócio em termos qualitativos [...] nunca com o valor exato.").
- `claude_client.py:1691-1699` - `DECISAO_PROMPT` (card "vale a pena?"): mesma regra
  repetida ("nunca invente nem repita valor em R$ específico [...]").
- `cards.py`: **sem ocorrência** da regra (grep não achou nada sobre construtora
  além do card de resumo do dia consumir `agua_copos`/etc. de saúde, sem relação) -
  ou seja, hoje a regra só existe em texto de prompt de IA (`claude_client.py`),
  nunca em código que filtra campo de card.
- Já existe uma decisão registrada sobre o alcance dessa regra (Fase 6, US-E11,
  `CHANGELOG.md`): a leitura foi que ela é sobre o **assistente nunca
  inventar/repetir** um número numa resposta livre, não sobre remover a injeção
  factual pré-existente (`_construtora_contexto_resumo`) que já mostrava dado
  pronto vindo da API externa - "pergunta que ficou em aberto pro Alex confirmar".
  A decisão desta faixa (Fase 7 A10, ver topo deste documento) parece resolver essa
  pergunta a favor de manter/expandir a exposição factual (gastos, entradas, tempo
  até a próxima conta) - **mas ela não muda a regra de `claude_client.py` acima**,
  que continua valendo pro texto *livre* do assistente (nunca citar valor exato de
  cabeça/de memória, mesmo que o contexto factual abaixo do prompt tenha um número).
  Quem integrar isso decide se quer reescrever esse trecho do prompt pra deixar essa
  distinção mais explícita (fora do escopo desta faixa - arquivo compartilhado).
