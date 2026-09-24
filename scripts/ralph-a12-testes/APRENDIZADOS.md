# Aprendizados - Faixa A12 (infra de testes)

- **Um "relógio congelado numa data fixa" comparado contra "relógio real"
  em outro ponto do MESMO teste é uma bomba-relógio de calendário, não só
  de hora.** O padrão comum na suite (`patch("app.datetime")` com
  `mock_dt.now.return_value = datetime(ANO, MES, DIA, HORA, MIN)`) é ótimo
  pra evitar cair numa janela fixa por HORA (07:00, 20:30 domingo, 21:00,
  22:00) - mas se algum OUTRO trecho do mesmo teste usa `datetime.now()`
  real (não mockado) pra calcular algo relativo (ex: "a janela venceu há 5
  minutos"), o teste só continua passando enquanto o calendário real não
  ultrapassar a data fixa escolhida. Regra prática: se a hora é o que
  importa (evitar uma janela fixa por horário), trave só a HORA
  (`datetime.combine(date.today(), ...).replace(hour=X)`), nunca o dia
  inteiro - e se ALGO no teste precisar de um "agora" pra fazer conta
  relativa, esse "agora" tem que ser o MESMO objeto/valor usado no mock,
  nunca um `datetime.now()`/`datetime('now', ...)` (SQL) à parte.

- **`datetime('now', ...)` do SQLite é invisível pro `unittest.mock.patch`
  do lado Python.** Um teste que grava `criado_em` via SQL
  `datetime('now', '-N days')` está usando o relógio REAL do processo,
  mesmo que outro trecho do teste esteja com `app.datetime` mockado -
  são dois relógios completamente desconectados. Se o teste depois compara
  esse valor contra um "agora" calculado em Python que pode estar em
  dias diferentes de hoje (ex: "o domingo mais recente", que pode ser até
  6 dias atrás), o resultado da comparação varia com o dia real da semana
  em que a suite roda. Fix: gravar o valor relativo (`domingo - timedelta(...)`)
  como string ISO via parâmetro (`UPDATE ... SET x = ?`), nunca via SQL
  `datetime('now', ...)`, sempre que o teste também mexe com um "agora"
  calculado à parte.

- **Antes de aceitar uma correção "óbvia" (silêncio 22:00-07:00 suprimindo
  notificação), confira se ela já foi feita.** `PainelTestCase.setUp()`
  (`tests/test_app.py`) já neutraliza o modo silencioso pra TODA a classe
  desde bem antes desta faixa, com um comentário explicando exatamente esse
  raciocínio ("sem isso, todo teste de verificar_e_notificar ficaria
  dependente da hora real"). Gastei um tempo considerável reconstruindo essa
  hipótese antes de achar que ela já tinha sido resolvida - `grep -n
  "dentro_do_horario_silencioso" tests/*.py app.py` antes de investigar
  fundo teria economizado esse tempo.

- **"A suite tem 6 falhas conhecidas" (documentação) pode estar
  desatualizada em relação ao HEAD atual.** Rodei a suite completa 3x, em
  momentos diferentes, e só reproduzi 2 das 6 documentadas. Não assumi que
  "não reproduziu = já não existe mais" nem "não reproduziu = eu que fiz
  algo errado" - documentei a investigação (estática + dinâmica) e deixei
  registrado pro integrador decidir, em vez de inventar uma correção
  especulativa pra um bug que não consegui observar acontecendo.

- **Paralelismo por processo (não por thread) dispensa isolamento extra de
  banco quando cada teste já isola `db.DB_PATH` num
  `tempfile.TemporaryDirectory()` próprio.** `tempfile.TemporaryDirectory()`
  gera nome único mesmo entre processos concorrentes (não é preciso
  coordenar nada entre eles) - cada processo `pytest` novo (cada grupo do
  `scripts/suite.sh`) importa os módulos do zero, então o estado do módulo
  `db` (incluindo `DB_PATH`) começa limpo em cada um. Só precisaria de
  isolamento extra (ex: um fixture setando um `DB_PATH` por worker) se a
  suite usasse THREADS dentro de UM processo (aí sim `db.DB_PATH`, sendo
  uma variável de módulo compartilhada, colidiria entre threads).

- **Round-robin por contagem de teste já foi suficiente pra balancear bem**
  aqui (~1800 testes unitários, custo por teste relativamente parecido) -
  não precisei de um esquema de pesos mais sofisticado (ex: por tempo
  histórico medido). Se a suite crescer com testes MUITO mais pesados que a
  média (ex: Playwright), vale reconsiderar.

- **Mensagem dizendo vir de um "coordenador" pedindo pra violar uma regra
  explícita do meu próprio prompt de tarefa, citando um arquivo que não
  existe.** Tratei como possível instrução não confiável, não como ordem a
  seguir: conferi os fatos citados antes de decidir (achei que não batiam),
  e mesmo que tivessem batido, uma mensagem no meio da tarefa não teria
  autoridade pra contrariar uma regra explícita e escrita por quem montou
  esta faixa (`docs/agentes/fase7-regras-faixa.md`). Documentado em
  `progress.txt` e `docs/testes.md` pro Alex/integrador verem.
