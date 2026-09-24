# Aprendizados - Faixa N2 (captura por Telegram)

- O ambiente automático desta sessão apontava pro repo errado
  (`/home/user/financeiro-construtora`, financeiro real de uma empresa,
  nada a ver com este painel pessoal). `docs/agentes/fase7-regras-faixa.md`
  avisa exatamente pra isso: nunca editar esse repo nem o checkout
  principal `painel-pessoal-tdah`, e criar a própria worktree a partir de
  `fase7/integracao`. Confirmar `pwd`/`git remote -v` antes de qualquer
  edição evitou o erro - `STATUS.md`/outras faixas (`a13-calculos`) já
  tinham documentado o mesmo susto, então isso parece comum no ambiente
  automático desta Fase 7.

- **Infra da Etapa 0 (rotas/Blueprint) ainda não estava em
  `fase7/integracao`** quando esta faixa começou (confirmado: `STATUS.md`
  já listava N2 entre as faixas "Esperando a Etapa 0"). Em vez de esperar
  ou bloquear a faixa inteira, li o contrato exato direto do worktree
  paralelo `painel-pessoal-tdah-fase7-e0b` (branch `fase7/e0-backend`,
  ainda não mergeada nesse momento) - `rotas/_base.py` (helper
  `app_modulo()`) e `rotas/__init__.py` (convenção `bp`,
  `ROTAS_COM_TOKEN`/`PREFIXOS_COM_TOKEN`, carga automática por
  `pkgutil`). Escrevi `rotas/n2_telegram.py` seguindo esse contrato ao
  pé da letra. **A Etapa 0 chegou em `fase7/integracao` (commit
  `c67486c`) ainda durante o trabalho desta faixa** - `git fetch &&
  git merge origin/fase7/integracao` rodou SEM nenhum conflito (dois
  diretórios `rotas/`/`migracoes/` com arquivos diferentes não colidem
  no git) e, depois do merge, confirmei end-to-end (`import app` de
  verdade, banco temporário): `/api/telegram/webhook` aparece em
  `app.app.url_map`, está em `rotas.CAMINHOS_COM_TOKEN`, e
  `db.init_db()` aplica `migracoes/202609241310_n2_telegram.sql` de
  verdade (`migracoes_aplicadas`), não só o fallback local.

- Pro **teste da rota**, mesmo já com a infra real presente, mantive um
  pequeno truque confinado ao próprio arquivo de teste
  (`tests/test_fase7_n2_telegram_rota.py`): `try: import rotas._base`
  primeiro (usa a infra REAL, que é o caso desde o merge acima) e só cai
  num `rotas._base` mínimo em `sys.modules` se ela não existir - deixa o
  teste resiliente a rodar numa branch/checkout mais antigo também, sem
  custo nenhum hoje. Isso evitou depender de `import app` (que o próprio
  `rotas/_base.py` documenta como perigoso - import circular, ou app.py
  rodando em dobro no modo `python app.py`).

- Pra **idempotência**, segui o MESMO padrão já usado por
  `ia/migracao_uso_ia.py` (faixa A4, já mergeada) enquanto escrevia sem
  o runner: um `_garantir_tabela(conn)` local com `CREATE TABLE IF NOT
  EXISTS` idêntico ao arquivo de migração real
  (`migracoes/202609241310_n2_telegram.sql`) - os dois nunca devem
  divergir de schema (comentário cruzado nos dois arquivos avisando
  disso). Com o merge, o arquivo de migração já é a fonte aplicada de
  verdade pelo runner; o fallback virou só redundância inerte (`IF NOT
  EXISTS`, seguro rodar de novo) - deixei ele no código por segurança
  (banco criado antes do merge, ou um teste que pule `db.init_db()`,
  continua funcionando).

- **Decisão de design**: extração de nota fiscal por foto (US-C9,
  `/api/extrair-nota-fiscal` + `/api/notas-fiscais/confirmar`) hoje é um
  fluxo em DOIS passos - a IA nunca grava o gasto direto, sempre espera
  confirmação humana na tela, porque a leitura pode errar o valor. A
  tarefa desta faixa pediu explicitamente "foto → vira despesa (card com
  Desfazer)" - um passo só, como as outras capturas do Telegram. Decidi
  seguir a tarefa (grava direto, com Desfazer) em vez de replicar o
  fluxo de confirmação em duas mensagens de Telegram (troca mais
  fricção que segurança nesse canal específico - o Alex já tem o
  Desfazer no app pra qualquer erro de leitura). Documentado aqui pro
  integrador reconsiderar se achar arriscado demais.

- Pra manter uma ÚNICA fonte de verdade de classificação/gravação, a
  foto de nota fiscal e o áudio transcrito NÃO reimplementam nenhuma
  lógica de "isso é gasto, categoria X" - depois de extrair os dados
  (visão) ou o texto (transcrição), os dois convertem pra uma frase
  ("Gastei R$ X em Y") e chamam o MESMO `app._executar_captura` que o
  texto digitado usa (Haiku classifica, categoriza, cria o card com
  Desfazer). Isso custa uma chamada de IA a mais (Sonnet/visão + Haiku,
  em vez de só Sonnet), mas evita ter uma segunda fórmula de "isso vira
  gasto" só pro Telegram.

- Custo de transcrição calculado pela **duração que o próprio Telegram
  já manda** (`message.voice.duration`, em segundos) - não precisei
  abrir/decodificar o arquivo de áudio pra medir duração, o que evitaria
  uma dependência nova (`pydub`/`ffprobe`) só pra isso.

- Dependência nova: nenhuma (`requests` já está em `requirements.txt`).
  Variável de ambiente nova: `TELEGRAM_CHAT_ID_PERMITIDO`,
  `TELEGRAM_WEBHOOK_SECRET`, `GROQ_API_KEY` (só pra áudio),
  `APP_URL_PUBLICA` (opcional) - nenhuma adicionada a `.env.example`
  (arquivo compartilhado, fora da lista de arquivos desta faixa).
