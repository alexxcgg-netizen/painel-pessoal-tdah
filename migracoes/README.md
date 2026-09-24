# migracoes/

Mudanca de schema da Fase 7 em diante mora aqui, um arquivo `.sql` por mudanca, em vez de
cada faixa editar o `init_db()` de `db.py` (que vira conflito de merge com 20 faixas em
paralelo).

## Como funciona

- `db.init_db()`, no fim (depois de todos os `CREATE TABLE`/`_garantir_coluna` que ja
  existiam), aplica cada `migracoes/*.sql` em **ordem alfabetica**, **uma vez so** por banco.
- O controle fica na tabela `migracoes_aplicadas (nome TEXT PRIMARY KEY, aplicada_em TEXT)`
  (`nome` = nome do arquivo, `aplicada_em` = UTC).
- Cada arquivo roda numa transacao so (`BEGIN IMMEDIATE` ... `COMMIT`), junto com o registro
  em `migracoes_aplicadas`. Se qualquer comando falhar, tudo daquele arquivo e desfeito
  (`ROLLBACK`) e o `init_db()` levanta `db.ErroMigracao` com o nome do arquivo - o app nao
  sobe com banco pela metade. Arquivos anteriores ja aplicados continuam aplicados.

## Convencao de nome

```
AAAAMMDDHHMM_<faixa>_<descricao>.sql
```

Exemplo: `202609241530_p1a_caixa_assistente.sql` (data/hora em que voce criou o arquivo, a
sigla da sua faixa, descricao curta com `_`). A data na frente garante a ordem; a faixa no
nome evita duas faixas criarem o mesmo arquivo.

## Regras

- **Nunca editar uma migracao existente** (ja pode ter rodado no banco real) - sempre um
  arquivo NOVO, mesmo pra corrigir a anterior.
- Sem `BEGIN`/`COMMIT`/`ROLLBACK` dentro do arquivo - a transacao e de quem aplica.
  `PRAGMA` que nao funciona dentro de transacao (ex: `foreign_keys`, `journal_mode`) tambem
  nao entra aqui.
- Prefira `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`. `ALTER TABLE ... ADD
  COLUMN` pode (roda uma vez so, pelo controle acima), mas lembre que coluna nova precisa de
  `DEFAULT` se for `NOT NULL`.
- Dado de producao: migracao que mexe em linha existente (UPDATE/DELETE) precisa de
  justificativa no comentario do proprio arquivo e backup antes (regra do AGENTS.md).
- Teste com banco temporario (`db.DB_PATH` + `db.garantir_banco_nao_producao()`), nunca
  contra `data/painel.db`.
