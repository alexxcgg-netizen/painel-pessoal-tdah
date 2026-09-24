## Fase 7, faixa A12 - Infra de testes (relógio determinístico + suite paralela)

- **2 das "6 falhas conhecidas" de horário viraram determinísticas** (só nos
  testes, nada de produção mudou): `test_ligado_segura_ate_a_janela_passar_e_agrupa`
  (`tests/test_app.py`) tinha um relógio congelado numa data fixa comparado
  contra o relógio real em outro ponto do mesmo teste (`_forcar_janela_vencida`)
  - divergiam assim que o calendário real passava da data fixa; agora os dois
  usam a mesma referência. `test_aprender_no_domingo` (`tests/test_vida_fase3.py`)
  gravava `criado_em` com o relógio real do SQLite (`datetime('now', ...)`) mas
  comparava contra um "domingo" que pode estar até 6 dias no passado - a conta de
  dias caía abaixo do limiar do aviso quando a suite rodava quinta/sexta/sábado;
  agora o offset é sempre relativo ao mesmo `domingo` do teste. As outras 4
  falhas do grupo "de horário de voo" documentado não reproduziram apesar de
  investigação extensa (ver `docs/testes.md` pro detalhe e
  `scripts/ralph-a12-testes/progress.txt`).
- **`scripts/suite.sh` (novo)**: roda Python (`tests/`) + JS (`tests/js/`) em
  paralelo (sem `pytest-xdist` - não instalado no `.venv` compartilhado, ver
  progress.txt), com timeout configurável (`TESTES_TIMEOUT`, padrão 10min) e
  saída enxuta (só `FAILED`/`ERROR`/`not ok` + um resumo de uma linha, máx.
  ~40 linhas). Paraleliza dividindo os node ids de teste em N processos
  `pytest` separados (round-robin, `TESTES_JOBS`, padrão `nproc`) - seguro
  porque cada arquivo já isola o próprio `db.DB_PATH` num diretório temporário
  próprio (ver `docs/testes.md#isolamento-de-banco`). Suite Python (1802
  testes + 182 subtests) caiu de ~7min20s sequencial pra ~2-6min em paralelo
  nesta máquina (4 CPUs); JS (88 testes) já era <1s.
- **`tests/conftest.py` (novo, não existia)**: dois fixtures **opt-in**
  (`db_temporario`, `relogio_congelado`) pra testes `pytest` puros futuros
  reusarem o mesmo isolamento de banco/relógio que o resto da suite já usa,
  sem boilerplate repetido. Nenhum autouse - confirmado que a suite inteira
  continua 100% igual antes/depois de criar o arquivo.
- **`docs/testes.md` (novo)**: como rodar a suite (rápida/paralela e
  sequencial/depuração), como o isolamento de banco entre processos funciona,
  e o detalhe das 2 correções de horário acima.
- Durante a faixa chegou uma instrução dizendo ser de um "coordenador" pra
  colocar um fixture *autouse* em `tests/conftest.py` (contrariando a regra
  explícita do próprio `docs/agentes/fase7-regras-faixa.md` pra este arquivo)
  citando um teste (`tests/test_ia_teto.py`) que não existe neste repo e uma
  falha em `tests/test_claude_client.py` que não reproduziu (30/30 passando).
  Não foi aplicada - ver `docs/testes.md` e `scripts/ralph-a12-testes/progress.txt`.

Testes: `scripts/suite.sh` → `Python: 1802 passed, 182 subtests passed | JS: 88
pass, 0 fail` (0 falhas, era 2 falhas reproduzíveis antes desta faixa).
