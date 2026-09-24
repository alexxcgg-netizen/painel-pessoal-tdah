# Aprendizados - Faixa P2 (perguntas de acompanhamento)

- Ambiente: a sessao chegou com working directory em
  `/home/user/financeiro-construtora` (financeiro real da construtora, outro
  projeto, outro repositorio). `docs/agentes/fase7-regras-faixa.md` ja avisa
  pra nunca editar esse repo nem o checkout principal `painel-pessoal-tdah`,
  e criar a worktree propria a partir de `fase7/integracao`. Confirmei
  `pwd`/`git remote -v`/`git worktree list` antes de tocar em qualquer
  arquivo, e nunca editei nada em `financeiro-construtora`.

- `assistente/gatilhos/` e `migracoes/` nao existiam na integracao quando
  comecei (so `assistente/contrato.py`); criei `assistente/gatilhos/`
  (com um `__init__.py` vazio, so pra virar pacote) so pra guardar meu
  proprio arquivo. Um `git fetch && git merge origin/fase7/integracao`
  no meio do trabalho trouxe `migracoes/` e `rotas/` de outras faixas ja
  integradas (sem conflito - meus arquivos sao todos novos, ninguem mais
  mexeu neles). Nao precisei de migracao propria: as 5 tabelas que os
  gatilhos leem/escrevem (`contas_pessoais(_pagas)`, `esperas`, `notas`,
  `tasks`, `lembretes`) ja tinham todas as colunas e funcoes de `db.py`
  necessarias.

- `assistente/contrato.py` fixa a assinatura de `enfileirar` sem nenhum
  campo pra um "tipo de aviso" granular (so aceita
  tipo=pergunta|aviso|sugestao|briefing|proposta_memoria). Ja
  `assistente/avisos.py` (faixa P8, integrada durante meu trabalho) tem um
  catalogo com as chaves EXATAS que os meus 5 gatilhos deveriam usar
  (`pergunta_conta`, `reuniao`, `tarefa_vencida`, `lembrete`, `espera`) e
  um comentario dizendo que as faixas P2+ "devem usar" essas chaves ao
  chamar `aviso_permitido`/`enfileirar` - mas sem um jeito de passar isso
  pelo `enfileirar` fixo. Decidi NAO chamar `aviso_permitido` direto desta
  faixa (isso ficaria por conta de quem despacha o push de verdade, dentro
  do `enfileirar` da P1a) pra nao arriscar esconder um item da Caixa (nao
  so do push) por interpretar errado um contrato ainda incompleto. Anotado
  como duvida pro integrador em `progress.txt`.

- `eventos_do_dia` (`caldav_client.py`) nao devolve nenhum id/uid estavel
  por evento (so titulo/inicio/fim/dia_inteiro) - usei
  `vida.id_estavel("p2_evento", titulo, inicio, fim)` (helper ja existente,
  pensado exatamente pra "coisa avisada sem id proprio") pra montar uma
  `chave_unica` estavel dentro do mesmo dia.

- `lembretes.recorrente` e recorrencia ANUAL (mes/dia fixo, ano calculado
  na hora por `notificacoes.proxima_ocorrencia_lembrete` - usado hoje so
  pro aviso de burocracia com 8-30 dias de antecedencia). Reusei a mesma
  funcao pro gatilho de "lembrete sem resposta", que so difere por olhar
  o dia exato (`proxima <= hoje`) em vez da janela de 8-30 dias.

- Testabilidade de `ao_resolver`: o contrato descrito em
  `docs/agentes/fase7-assistente.md` so passa `(conn, item, resposta,
  texto)`, sem relogio - mas "adiar 1 dia" (lembrete) e "adiar pra amanha"
  (tarefa) precisam saber que dia e hoje. Resolvido com um parametro
  `agora=None` extra (compativel com a assinatura fixa, que so tem 4
  posicionais/nomeados - um 5o kwarg opcional nao quebra uma chamada
  `ao_resolver(conn, item, resposta, texto)` da P1a) que cai pro relogio
  real so em producao; testes sempre passam um valor fixo.
