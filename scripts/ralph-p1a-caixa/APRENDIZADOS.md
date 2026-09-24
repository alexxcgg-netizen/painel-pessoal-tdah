# Aprendizados - Faixa P1a (Caixa do assistente)

- **`assistente/contrato.py` fecha a assinatura sem `conn`** pra
  `enfileirar`/`resolver` - cada chamada abre e fecha a própria conexão
  (`db.get_db()`). Isso também significa que nenhuma das duas pode receber
  um `agora` injetado como parâmetro; usei um hook de módulo
  (`caixa._agora`, default `datetime.now`) pra dar aos testes um jeito de
  travar o relógio sem mudar a assinatura pública. `listar` tem o mesmo
  problema (ordenar "pergunta vencida" depende da hora) e usa o mesmo hook.

- **Despacho de `ao_resolver`**: `origem` é `<módulo_do_gatilho>:<resto>` -
  divide no **primeiro `:`**, nunca no `_` (o texto antigo do contrato
  dizia "antes do `_`", mas o nome do módulo pode ter `_` dentro, ex.
  `p2_perguntas`). Definição confirmada pelo integrador durante esta
  faixa - se um prompt futuro repetir o texto antigo, ignore, siga o `:`.

- **`assistente/avisos.aviso_permitido(tipo, agora=None, conn=None)`** (P8,
  já mesclada) aceita um `agora` opcional pra ser testável - descobri isso
  só depois de mesclar `origin/fase7/integracao` (antes disso o módulo nem
  existia, só o fallback fixo 22h-7h desta faixa rodava). Chamei com
  `inspect.signature` pra decidir se passo `agora=` ou não, em vez de
  `try/except TypeError` (que esconderia um bug de verdade dentro da
  função por engano).

- **`item["tipo"]` da Caixa (pergunta/aviso/sugestão/briefing/
  proposta_memoria) não é a mesma coisa que as chaves do catálogo `TIPOS`
  de `assistente/avisos.py`** (que são ~49 tipos específicos tipo
  "pergunta_conta", "tarefa_vencida"). Como nunca bate, `aviso_permitido`
  cai no comportamento documentado pra tipo desconhecido (permitido,
  respeitando só o silêncio global) - funciona e é seguro, mas o
  liga/desliga fino por tipo do P8 não alcança item da Caixa. Ver
  `progress.txt` pra mais detalhe/sugestão de como ligar isso no futuro.

- **`tests/test_fase7_infra_rotas.py` (do X1) já está quebrado com
  qualquer blueprint real registrado** (`p7_sinais.py`/`p8_avisos.py` já
  bastam, confirmei sem meu `rotas/p1a_caixa.py`): `import app` já chama
  `rotas.registrar_todas(app.app)` uma vez, e o helper de teste
  `_registrar_no_app` chama de novo - Flask recusa registrar o mesmo
  objeto `Blueprint` duas vezes no mesmo app. Não é algo que uma faixa de
  rota consiga evitar sozinha (é o teste que precisa mudar de estratégia,
  ex. um app Flask novo por teste em vez de reusar `app.app`) - avisei no
  `progress.txt`, não mexi no arquivo (não é meu).

- **Migração real**: `db.init_db()` aplica `migracoes/*.sql` sozinho no
  fim (controle em `migracoes_aplicadas`), então a partir do merge com
  `origin/fase7/integracao` minha `_garantir_tabela` interna em
  `caixa.py` (CREATE TABLE IF NOT EXISTS) ficou redundante em produção -
  mantive mesmo assim, porque deixa `assistente/caixa.py` funcionar
  sozinho em qualquer teste que não passe pelo `db.init_db()` completo
  (custo é só um `executescript` idempotente a mais por chamada).
