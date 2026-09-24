# Aprendizados - Faixa P9 (memoria viva)

- O ambiente desta sessao apontava pro repo errado
  (`/home/user/financeiro-construtora`, financeiro real da construtora,
  outro projeto/outro dono de dado, ver o AGENTS.md de la). Confirmado
  `pwd`/`git remote -v` antes de qualquer edicao: todo o trabalho desta
  faixa ficou em `/home/user/painel-pessoal-tdah-fase7-p9-memoria`
  (worktree criada com `git worktree add -b fase7/p9-memoria ... fase7/
  integracao`, seguindo fase7-regras-faixa.md), nunca no financeiro nem no
  checkout principal `painel-pessoal-tdah`.

- Assunto proibido: comecei filtrando por substring solta e quebrei nos
  dois sentidos - "date" como substring batia dentro de "update" (falso
  positivo) e "namor" como radical sozinho nao pegava "esta namorando"
  (sufixo -ando depois do radical "namor" nao tem problema, mas a lista
  original tinha "namorad"/"namoro" que nao cobrem "namorando"). Resolvido
  trocando pra regex com borda de palavra (`\bradical\w*`): pega qualquer
  conjugacao do radical (namor -> namorando/namorada/namoro/namorar) sem
  confundir com substring no meio de outra palavra. Testado com
  test_pega_variacoes_namoro e test_nao_confunde_construtora_com_construir
  (radical "construtora" inteiro, nao "constru", entao nao bate em
  "construir"/"construcao").

- `saude_dados.sono_horas` e campo CRIPTOGRAFADO em repouso (Fernet, ver
  criptografia.py) mesmo sem ENCRYPTION_KEY configurada (nesse caso vira
  texto plano por decisao de design, documentada la - nunca trava o app).
  Os testes usam sempre `db.upsert_saude_dia(conn, data, {"sono_horas":
  ...})` em vez de INSERT direto na tabela, senao `list_saude_dados`
  tentaria descriptografar um valor que nunca foi cifrado.

- Design que evitei: schema com um campo extra tipo `fato_id` pra ligar
  proposta -> fato de volta. O prompt pediu o schema exatamente como
  `{"propostas":[{"acao","memoria_id","texto","motivo"}]}`, entao mantive
  literal. Pra ainda assim ter uma `chave` ESTAVEL por 8 semanas (pro
  "nunca repropor uma recusa"), sem depender do texto que a IA escreve
  (que pode mudar de fraseado de uma semana pra outra e quebraria um hash
  baseado em texto), a chamada de `chamar_ia` virou 1x POR FATO (nao 1
  chamada com a lista toda) - cada fato ja carrega sua propria `chave`
  code-side (ex: "treino_horario:3", "sono_medio",
  "gasto_recorrente:netflix"), e essa chave e o que vira chave_unica
  (`p9:<semana>:<chave>`) e a chave de p9_memoria_recusas. Trade-off
  aceito: ate 5 chamadas de IA por semana (LIMITE_FATOS_POR_SEMANA) em vez
  de 1 - ainda bem dentro do teto (max_tokens_saida 500 cada, so roda 1x
  por semana).

- NOTA DE INTEGRACAO PRA QUEM MEXER NO DISPATCH DE `ao_resolver` NA P1A:
  fase7-assistente.md diz "o prefixo e o texto de origem antes do `_`",
  com o exemplo "p2_conta:123" -> prefixo "p2" -> modulo
  `assistente/gatilhos/p2.py`. Mas o prompt desta faixa fixou o nome do
  arquivo como `assistente/gatilhos/p9_memoria.py` (COM "_" no meio do
  proprio prefixo) - se o dispatch real cortar estritamente no primeiro
  "_", ele vai procurar `assistente/gatilhos/p9.py` (que nao existe) em
  vez deste arquivo. Usei `origem = "p9_memoria:<chave>"` (prefixo = tudo
  antes do primeiro ":", nao do "_") - funciona com um dispatch que separe
  por ":", mas nao com um que separe estritamente pelo primeiro "_". Quem
  integrar a P1a precisa: (a) confirmar qual dos dois o dispatch real faz,
  e (b) se for o segundo, trocar aqui `origem` pra algo como
  "p9:memoria:<chave>" (chave interna ja usa ":", entao a leitura em
  `ao_resolver` - `origem.split(":", 1)[1]` - continua funcionando do
  mesmo jeito, so muda o prefixo fixo antes do primeiro ":").

- Pra nao depender do formato interno do `item` da Caixa (que a P1a ainda
  nao definiu nesta integracao, so o contrato garante `item["origem"]`),
  toda a informacao pra aplicar uma proposta aceita (acao/memoria_id/
  texto/categoria) fica guardada numa tabela propria
  (`p9_memoria_propostas`), nao no item da Caixa. `ao_resolver` so usa
  `item["origem"]` + `resposta` - nada mais do contrato ainda incerto.

- `migracoes/` (Etapa 0, aplicado sozinho) ainda nao integrado nesta
  branch mesmo depois de `git merge origin/fase7/integracao` (trouxe A5/
  A13/A15/N3b, ainda sem P1a/Etapa 0 X1). Como as tabelas desta faixa sao
  pequenas e proprias (nao mudam schema de tabela existente), resolvido
  sem bloquear: `p9_memoria.py` cria as 2 tabelas com `CREATE TABLE IF NOT
  EXISTS` na primeira chamada de `executar`/`ao_resolver`, e o `.sql`
  equivalente ja esta em `migracoes/202609241250_p9_memoria_recusas.sql`
  pronto pra quando o runner automatico chegar (reaplicar e inofensivo,
  e so `IF NOT EXISTS`).

## Atualizacao apos aviso do integrador (commit c67486c: Etapa 0 X1 completa)

- `git fetch origin && git merge origin/fase7/integracao` trouxe o resto
  da Etapa 0 X1 (`rotas/` com Blueprint+`ROTAS_COM_TOKEN` e carga
  automatica, `migracoes/*.sql` agora REALMENTE aplicado sozinho por
  `db.init_db()` -> `aplicar_migracoes()`, `classificador_local/`,
  `assistente/gatilhos/__init__.py` real com `executar_todos`) + faixas P7
  (sinais) e P8 (avisos). Sem conflito de merge: a minha
  `assistente/gatilhos/__init__.py` (vazia, criada so pra virar pacote)
  foi automaticamente substituida pela real da integracao - nao precisei
  apagar nada a mao (o Git resolveu sozinho porque a minha nao tinha
  conteudo pra divergir). Meu `migracoes/202609241250_p9_memoria_recusas
  .sql` ja seguia o formato `AAAAMMDDHHMM_<faixa>_<descricao>.sql` do
  `migracoes/README.md` novo, entao nao precisou renomear - e agora e
  aplicado de verdade (meu `_garantir_tabelas()` em `p9_memoria.py`
  virou so um cinto-de-seguranca redundante, mantive porque e inofensivo
  e nao custa nada). `assistente/caixa.py` da P1a **ainda nao chegou**
  na integracao (so a infra X1 chegou) - o design com `_caixa()` +
  tabela propria `p9_memoria_propostas` continua sendo a decisao certa.

- Depois do merge, reconferido: 58/58 testes desta faixa continuam
  passando, `gitleaks detect --no-git --source .` continua sem achados.

- Rodei a suite inteira (`tests/`, sem `tests/js`) pra caçar colisao de
  verdade (nao so os meus arquivos). Resultado: 10 falhas, NENHUMA em
  `assistente/memoria_viva.py`, `assistente/gatilhos/p9_memoria.py`,
  `ia/config.d/propor_memoria.json` ou nos meus 2 `tests/test_fase7_p9_*`
  - todas em arquivos que eu nunca editei:
  - `test_app.py::NotificacaoAgrupadaTestCase::test_ligado_segura_ate_a_
    janela_passar_e_agrupa` e `test_vida_fase3.py::AvisosFase3TestCase::
    test_aprender_no_domingo`: dependem de horario/`datetime.now()`
    mockado de um jeito sensivel a quando o teste roda - exatamente a
    familia das "6 falhas conhecidas, que dependem de horario (voo/
    agrupamento)" que `fase7-regras-faixa.md` ja avisa que existem.
  - `test_fase7_infra_rotas.py` (8 falhas, `ValueError: The name
    'p7_sinais' is already registered...`): registro duplicado de
    Blueprint Flask - percebi (via `ps aux`) varias sessoes de outras
    faixas rodando pytest ao mesmo tempo no mesmo container (vi processos
    de `p1a-caixa` e `a12-testes` ativos) - pode ser efeito colateral de
    rodar a suite inteira em paralelo com workers de outra faixa tambem
    testando `rotas/`. De qualquer forma, `rotas/` nao e arquivo meu.
  - `test_fase7_a14_roteador.py::RobustezTestCase::
    test_classificador_local_ausente_nao_quebra` e
    `test_fase7_p7_rota_sinal.py::RotaSinalTestCase::
    test_corpo_nao_json_nao_derruba_a_rota` (415 vs 400 esperado): fora
    do meu escopo, arquivos de outras faixas.

- Efeito colateral ESPERADO (nao bug meu - e inerente a QUALQUER faixa P
  que adicione seu primeiro gatilho real em `assistente/gatilhos/`): 3
  testes em `tests/test_fase7_infra_gatilhos.py` passaram a falhar so
  porque assumiam, literalmente, que a pasta real estava vazia
  (`test_pasta_real_sem_gatilho_nenhum_ainda`:
  `self.assertEqual(gatilhos.nomes_gatilhos(), [])`) ou comparavam o
  dict de resultado de `executar_todos` por IGUALDADE EXATA
  (`test_roda_todos_em_ordem_alfabetica...`,
  `test_com_conexao_real_do_painel`), sem deixar espaco pra um gatilho
  de verdade que ja exista no pacote. Meu `p9_memoria.executar` continua
  se comportando corretamente nesses testes (nunca levanta excecao -
  devolve `{"ok": False, "erro": "...no such table: configuracoes"}` no
  teste com conexao sqlite "crua" sem `db.init_db()`, e `{"ok": True,
  "resultado": None}` no teste com conexao real, porque o horario do
  teste nao e domingo >=19h) - so a asserção de igualdade estrita do
  teste que nao previa nenhum gatilho concorrente. NAO editei
  `tests/test_fase7_infra_gatilhos.py` (nao esta na minha lista de
  arquivos). A mesma quebra vai acontecer de novo assim que a proxima
  faixa P integrar o proprio gatilho - quem for atualizar essas 3 asserts
  (pra "contem p9_memoria" em vez de "esta vazio", e pra so checar as
  chaves do modulo/pasta de teste em vez do dict inteiro) e o
  integrador/dono da Etapa 0, nao uma faixa P individual.
