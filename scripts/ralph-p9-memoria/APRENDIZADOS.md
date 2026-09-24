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
