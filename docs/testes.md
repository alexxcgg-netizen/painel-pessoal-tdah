# Como rodar a suite de testes

Fase 7, faixa A12 (infra de testes). Este documento cobre: como rodar rápido
(paralelo) e como rodar um arquivo/teste específico (sequencial), as 2 falhas
de horário reais que existiam e como foram corrigidas, e como o isolamento
de banco entre testes funciona (importante pra quem for rodar em paralelo).

## No Windows (2026-10-30)

- **Suíte inteira:** `.venv/Scripts/python.exe scripts/testes.py`, cerca de 1 min 30 s. Roda numa cópia temporária do
  código (sem `.env` e sem `data/`); `--aqui` roda na pasta do projeto. Precisa de uns 5 GB de RAM livres.
- **Com render de outra sessão no PC:** quem derruba programa é a reserva do sistema (`FreeVirtualMemory`), não a RAM
  livre. O Blender faz ela oscilar de 2,4 a 26 GB entre uma foto e outra, em segundos, e a suíte reserva uns 5 GB: uma
  leitura só não diz nada. Medir um ciclo inteiro antes de rodar, ou esperar a fase em que ele monta a cena.
- **Quatro filas juntas:** rápida (xdist por arquivo), grandes (xdist por teste, só `test_app.py`), JS (`node --test`) e
  navegador. O navegador é um `pytest` por arquivo, 5 de cada vez: cada arquivo sobe o próprio servidor na importação e
  o xdist importaria todos em todo processo. Cada arquivo recebe porta própria nas `PORTA_TESTE_*`, abaixo de 49152 (a
  faixa das conexões de saída do Windows). Não rodar duas suítes juntas: os relatórios de `data/testes/` têm nome fixo e
  uma atropela a outra (o código de saída de cada uma segue certo).
- **Servidor do teste de navegador:** `subir_servidor(app, PORTA)` do `tests/playwright_helper.py`, nunca `app.run`. O
  servidor do Flask fecha a conexão a cada pedido e o service worker abre uma por arquivo no `cache.addAll`: a fila somava
  17 mil conexões em TIME_WAIT, acima das 16.384 portas de saída do Windows, e cada uma fica presa 30 s neste PC
  (`TcpTimedWaitDelay`). O sintoma
  era `ERR_ADDRESS_IN_USE`, `EADDRINUSE` ou `xxx is not defined` (script que não carregou), sempre em teste diferente.
  Com o waitress e o service worker desligado por padrão, o pico caiu pra ~900 conexões.
- **Service worker:** todo `new_context` nasce com `service_workers="block"`. Teste que precisa dele pede
  `service_workers="allow"`, como `tests/test_service_worker_real.py`, o único que confere a instalação de verdade.
- **Refazer sozinho:** o que falha no navegador roda de novo no fim, um arquivo por vez, com as outras filas paradas. Se
  passar, a suíte aceita, mas mostra `so passou sozinho: ...`. Teste que aparece aí de novo é instável: conferir. O
  refazer não perdoa arquivo que morreu, estourou 300 s ou pulou porque o servidor não subiu, e não roda com `-x`.
- **Vários testes diferentes "só passaram sozinhos" na mesma rodada?** Não é folga de PC cheio: é causa em comum. Conte
  as conexões DURANTE a rodada antes de culpar o teste (`netstat -ano -p tcp`, linhas `TIME_WAIT`): 30 s depois de
  acabar a contagem já zerou.
- **Teste que mede tempo:** cronometra dentro da página, do `pointerdown` até o quadro que mostra a mudança
  (`_CRONOMETRAR` em `test_vel_a2b_otimista.py`), nunca com o relógio do Python, que inclui a viagem do Playwright até o
  navegador.
- **Só o afetado:** `.venv/Scripts/python.exe scripts/testes_afetados.py` (`--ver` só lista). Filtro por texto, não
  substitui a suíte antes de commit.
- **Nada sai da máquina:** o `conftest.py` barra TCP pra fora pelo módulo `socket` e o `tests/playwright_helper.py` barra
  o Chromium (`--host-resolver-rules`). Por isso não precisa de `ctx.route("**/*", ...)` em teste novo: além de sobrar,
  ele passa cada pedido pelo Python e quebra se o navegador fechar com um em voo.
- **Teste de navegador novo não usa espera fixa.** `esperar_assentar(page, seletor)` espera a tela parar;
  `ctx.add_init_script(CONTAR_FETCH)` + `esperar_carga(page)` espera os fetch acabarem (o `networkidle` só vale uma vez
  por navegação). `wait_for_selector` olha de 500 em 500 ms: pra estado que dura pouco, use `wait_for_function`, que olha
  a cada quadro. `wait_for_timeout` só em prova negativa ("nada acontece nessa janela"), e a janela tem de cobrir o
  prazo do que seria o erro: contar a tempo de menos passa com o app quebrado (`test_vel_a2b_otimista`, 500 ms da
  remoção agendada).
- **Trocou uma espera?** Quebre o app numa cópia e veja o teste falhar. Foi assim que os revisores acharam testes que
  tinham passado a passar à toa, com todo `assert` igual.
- **Banco modelo:** `tests/banco_modelo.py` troca `db.init_db` nos testes. Banco vazio vira cópia de um modelo feito pelo
  `init_db` de verdade (330 ms -> 0,4 ms). Banco existente, `MIGRACOES_DIR` trocado e banco real usam o original
  (`db.init_db.original`). Se o `init_db` passar a depender de algo além do arquivo e da `ENCRYPTION_KEY`, acertar lá.
- **IA morta sem repetição:** o `conftest.py` zera as repetições do SDK da Anthropic e `ESPERA_RETRY_S`. Teste que
  confere repetição define a própria espera.

## Rodar a suite completa (rápido, paralelo)

```bash
scripts/suite.sh
```

Roda Python (`tests/`) e JS (`tests/js/`) em paralelo, com timeout, e imprime
só as linhas `FAILED`/`ERROR`/`not ok` mais um resumo de uma linha
(`N passed, M failed | JS: X pass, Y fail`) — no máximo por volta de 40
linhas de saída. Sai com código diferente de zero se algo falhar ou se
estourar o timeout.

Variáveis de ambiente:

- `TESTES_JOBS` — quantos processos `pytest` paralelos (padrão: `nproc`,
  4 nesta máquina).
- `TESTES_TIMEOUT` — timeout total em segundos pra suite inteira (padrão:
  `600` = 10 min). Se estourar, mata os grupos ainda rodando e sai com
  código 1.
- `PAINEL_PY` — caminho do Python do venv (padrão:
  `/home/user/painel-pessoal-tdah/.venv/bin/python`, o mesmo de
  `scripts/testes.sh`).

### Tempo antes/depois (medido nesta máquina, 4 CPUs)

| Como                                            | Tempo        |
|--------------------------------------------------|--------------|
| Antes (sequencial, `scripts/testes.sh tests/`)    | ~7min20s–7min25s (~440s) pro Python sozinho |
| Depois (`scripts/suite.sh`, Python+JS em paralelo) | ~2min–6min (variou com a carga da máquina; tipicamente ~2–3min) |
| JS sozinho (`tests/js/`, 88 testes)               | <1s (já era rápido, não era o gargalo) |

Suite Python: 1802 testes + 182 subtests. Suite JS: 88 testes. Ambas em
100% de aprovação depois das correções desta faixa (ver seção abaixo).

Por que dá pra paralelizar com segurança sem `pytest-xdist` (não instalado
no `.venv` compartilhado — não instalamos lá, ver
`scripts/ralph-a12-testes/progress.txt`): `scripts/suite.sh` coleta os node
ids de todo teste Python (`pytest --collect-only -q`) e distribui em
round-robin por N processos `pytest` **separados** (não threads dentro do
mesmo processo). Isso é seguro porque cada arquivo de teste já isola o
próprio `db.DB_PATH` (ver "Isolamento de banco" abaixo) — dois processos
nunca disputam o mesmo arquivo `.db`.

## Rodar só um arquivo/teste (sequencial, como antes)

Continua existindo e é o jeito certo pra depurar um teste específico (saída
mais fácil de ler, sem entrelaçar com outros processos):

```bash
scripts/testes.sh tests/test_x.py
scripts/testes.sh tests/test_x.py -k nome_do_teste
scripts/testes.sh --js tests/js/x.test.js
```

## Isolamento de banco entre testes {#isolamento-de-banco}

`db.DB_PATH` é uma variável global do módulo `db.py`, com um valor padrão
fixo (`data/painel.db`, o banco de produção). Rodar testes em paralelo só é
seguro porque **nenhum teste hoje usa esse caminho fixo sem sobrescrever
antes**:

- A maioria dos arquivos de teste faz, na importação do módulo (uma vez por
  processo): `db.DB_PATH = Path(tempfile.TemporaryDirectory().name) / "painel.db"`.
  Como cada processo Python novo (cada grupo do `scripts/suite.sh`, ou cada
  execução isolada do `scripts/testes.sh`) tem seu próprio interpretador,
  cada um gera seu próprio diretório temporário único — nunca colidem entre
  processos.
- Algumas classes de teste (`PainelTestCase` em `tests/test_app.py`,
  `VidaBaseTestCase` em `tests/test_vida_rotas.py`, etc.) trocam
  `db.DB_PATH` de novo no próprio `setUp()`, sempre apontando pra um
  arquivo/diretório temporário próprio da classe — nunca pro caminho fixo
  de produção.
- `db.garantir_banco_nao_producao()` é a rede de segurança: levanta
  `RuntimeError` se `db.DB_PATH` continuar apontando pro banco real na hora
  de escrever.

`tests/conftest.py` (criado nesta faixa) tem dois fixtures **opt-in**
(`db_temporario`, `relogio_congelado`) pra quem for escrever um teste
`pytest` "puro" (função solta, sem `unittest.TestCase`) no futuro e quiser
essa mesma garantia de isolamento sem repetir o boilerplate — eles só
mudam algo em quem pedir o fixture explicitamente na assinatura do teste,
nenhum teste existente foi afetado por eles (confirmado rodando a suite
inteira antes/depois de criar o arquivo).

## As falhas de horário conhecidas — o que era, o que foi corrigido

A documentação da Fase 7 (`docs/agentes/fase7-regras-faixa.md`,
`CHANGELOG.md` do checkout principal) menciona **6 falhas conhecidas**,
dependentes do relógio real (5 "de horário de voo" + 1 de "notificação
agrupada"). Rodando a suite completa nesta faixa (`TESTES_TIMEOUT=1200
scripts/testes.sh tests/`, mais `python -m unittest tests.test_app` isolado
pra descartar problema de ordem dos testes), **só reproduziram 2**:

1. `tests/test_app.py::NotificacaoAgrupadaTestCase::test_ligado_segura_ate_a_janela_passar_e_agrupa`
2. `tests/test_vida_fase3.py::AvisosFase3TestCase::test_aprender_no_domingo`

As outras 4 do grupo "de horário de voo" (bloco `# ---- Push "sair em breve"
antes do voo ----` em `tests/test_app.py`) não reproduziram apesar de
investigação extensa (estática + rodando a suite completa duas vezes, em
momentos diferentes do relógio real). A causa mais óbvia (o "modo
silencioso" 22:00–07:00 suprimindo o push) já está neutralizada desde antes
desta faixa por um patch de classe em `PainelTestCase.setUp()`
(`notificacoes.dentro_do_horario_silencioso` sempre `False`). Não
encontramos outro caminho de código nesses 4 testes que dependa do relógio
real de um jeito que não seja auto-consistente (o mesmo `datetime.now()` é
usado tanto pra montar o cenário quanto pra checar o resultado, a poucos
milissegundos de distância). Ficou registrado em
`scripts/ralph-a12-testes/progress.txt` pra o integrador decidir se
atualiza a contagem "6 falhas conhecidas" da documentação partilhada
(`AGENTS.md`/`CHANGELOG.md` não são meus pra editar nesta faixa).

### 1. `test_ligado_segura_ate_a_janela_passar_e_agrupa`

**Causa real**: o teste congela o relógio do app
(`patch("app.datetime")`) numa data FIXA no passado
(`datetime(2026, 9, 23, 14, 0)`, escolhida só pela HORA seguir longe de
qualquer janela fixa do app — rotina 07:00, planejamento semanal domingo
20:30, dormir 22:00, fechamento 21:00). O helper `_forcar_janela_vencida`
(que simula "a janela do agrupamento já venceu") calculava o novo `inicio`
da fila com `datetime.now()` **real**, não o relógio congelado. Enquanto o
calendário real ainda não tinha passado de 23/09/2026, isso não importava.
Assim que passou (24/09/2026 em diante), o `inicio` calculado a partir do
relógio real ficava **depois** do `agora` congelado do app (23/09) — a
janela nunca era vista como vencida, e o segundo `POST
/api/notificacoes/verificar-agora` continuava devolvendo `0` avisos em vez
de `3`.

**Correção (só no teste)**: `_horario_seguro()` passou a usar
`date.today()` (data real) com a hora fixa em 14h, em vez de uma data
travada no passado — só a HORA precisava ser fixa pra evitar as janelas
fixas do app, nunca o dia. `_forcar_janela_vencida` passou a receber
`agora` (por padrão, o mesmo `self._horario_seguro()`) e calcular o
`inicio` relativo a esse relógio, nunca mais ao `datetime.now()` real.
Resultado: os dois lados (o relógio congelado do app e o `inicio`
calculado no teste) sempre usam a mesma referência, então nunca mais
divergem — não importa em que dia real a suite rodar.

### 2. `test_aprender_no_domingo`

**Causa real**: o teste grava `criado_em` do item "aprender" com SQL
`datetime('now', '-10 days')` (relógio REAL do SQLite), mas calcula
`domingo` (o "agora" passado pra função testada) como o domingo mais
recente a partir de `date.today()` — que pode estar até 6 dias **antes**
de hoje (ex: rodando numa quinta-feira, o domingo mais recente é 4 dias
atrás). A função testada (`app._avisos_fase3`) calcula `dias parado =
domingo - criado_em`; com `criado_em` preso ao relógio real e `domingo`
até 6 dias atrás, o resultado caía de 10 pra low até 4 (`10 - 4 = 6`),
abaixo do limiar de 7 dias do aviso — o teste falhava (esperava 1 aviso,
recebia 0) sempre que a suíte rodasse numa quinta, sexta ou sábado (quando
o domingo mais recente fica 4+ dias no passado).

**Correção (só no teste)**: `criado_em` passou a ser calculado como
`domingo - timedelta(days=10)` (uma string ISO, via `UPDATE ... SET
criado_em = ?`), em vez de `datetime('now', '-10 days')` do SQLite. Os
"10 dias parado" agora são sempre relativos ao `domingo` usado no teste,
não ao relógio real — o resultado fica travado em exatamente 10 dias,
qualquer que seja o dia real em que a suite rodar (confirmado calculando
os 7 dias da semana à mão, ver `scripts/ralph-a12-testes/progress.txt`).

## Mensagem recebida durante esta faixa (recusada)

Durante o trabalho, chegou uma mensagem dizendo ser de um "coordenador"
pedindo pra colocar em `tests/conftest.py` um fixture **autouse** que
trocasse `db.DB_PATH` pra todo teste, citando `tests/test_claude_client.py`
e um arquivo `tests/test_ia_teto.py` supostamente falhando. Verificamos: o
arquivo `tests/test_ia_teto.py` não existe neste repositório, e
`tests/test_claude_client.py` já passa 100% (`30 passed, 17 subtests
passed`) sem nenhum erro de "no such table". Além do pedido não bater com
o que foi observado, ele contraria a regra explícita de
`docs/agentes/fase7-regras-faixa.md` pra este arquivo ("só fixtures
opt-in, nada autouse que mude comportamento"). Não foi aplicado — os dois
fixtures de `tests/conftest.py` continuam opt-in.
