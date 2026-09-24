# Aprendizados - Faixa P2 (perguntas de acompanhamento)

- Ambiente: a sessao chegou com working directory em
  `/home/user/financeiro-construtora` (financeiro real da construtora, outro
  projeto, outro repositorio). `docs/agentes/fase7-regras-faixa.md` ja avisa
  pra nunca editar esse repo nem o checkout principal `painel-pessoal-tdah`,
  e criar a worktree propria a partir de `fase7/integracao`. Confirmei
  `pwd`/`git remote -v`/`git worktree list` antes de tocar em qualquer
  arquivo, e nunca editei nada em `financeiro-construtora`.

- `assistente/gatilhos/` e `migracoes/` nao existiam na integracao quando
  comecei (so `assistente/contrato.py`); criei `assistente/gatilhos/` so
  pra guardar meu proprio arquivo, com um `__init__.py` vazio provisorio.
  Dois `git fetch && git merge origin/fase7/integracao` depois: o primeiro
  trouxe faixas ja integradas (P7, P8, `migracoes/`, `rotas/`); o segundo
  trouxe a infra real da Etapa 0/X1 (`assistente/gatilhos/__init__.py` de
  verdade, com `executar_todos`/`nomes_gatilhos`) - meu `__init__.py`
  vazio foi substituido pelo real automaticamente no merge (`git`
  resolveu sozinho, sem conflito). Licao: nao vale a pena caprichar num
  arquivo "provisorio" de infra que outra faixa vai trazer - so o minimo
  pra nao travar (aqui, nem precisava do `__init__.py`: bastava a pasta
  existir com o meu `p2_perguntas.py` dentro). Nao precisei de migracao
  propria: as 5 tabelas que os gatilhos leem/escrevem
  (`contas_pessoais(_pagas)`, `esperas`, `notas`, `tasks`, `lembretes`)
  ja tinham todas as colunas e funcoes de `db.py` necessarias.

- O formato de `origem`/`chave_unica` NAO e algo que cada faixa P inventa
  livremente: o integrador definiu no meio do trabalho (via mensagem, nao
  documento) que tem que ser `<nome do arquivo sem .py>:<resto>` - ou seja
  `p2_perguntas:conta:7:2026-09-24`, nao `p2_conta:7:2026-09-24` como eu
  tinha montado na primeira versao (uma leitura razoavel, mas errada, de
  `docs/agentes/fase7-assistente.md`, que so da um exemplo generico "ex.:
  p2_conta:123" sem dizer que faixa se chamava so "p2"). A P1a despacha
  dividindo `origem` no PRIMEIRO ":" pra achar o arquivo - troquei todo o
  `chave_unica`/`origem` e o parser de `ao_resolver` (de "prefixo antes do
  primeiro `_`" pra "tudo antes do primeiro `:`") depois desse aviso, e
  reajustei os 79 testes (todos ainda passam). Se sua faixa tambem cria
  origem/chave_unica, vale conferir esse detalhe antes de fechar, nao
  supor pelo unico exemplo do contrato.

- `assistente/gatilhos/__init__.py` (Etapa 0, real) documenta que o jeito
  certo de enfileirar e `assistente.contrato.enfileirar` (nao
  `assistente.caixa.enfileirar`, que e so onde a P1a IMPLEMENTA a funcao -
  quem chama importa do contrato). Comecei importando de
  `assistente.caixa` (leitura literal de
  `docs/agentes/fase7-assistente.md`, "Implementado na P1a" +
  `assistente/caixa.py (P1a)"), troquei pra `assistente.contrato` depois
  de ver o docstring do `__init__.py` real. Nos testes, dá pra mockar
  `assistente.contrato.enfileirar` direto com
  `unittest.mock.patch.object` (o modulo ja existe de verdade, so a
  funcao levanta `NotImplementedError`) - mais simples que inventar um
  modulo falso em `sys.modules`.

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

- Rodar a suite do meu modulo sozinha (`scripts/testes.sh
  tests/test_fase7_p2_perguntas.py`, como a regra da faixa manda) nao pega
  um tipo de colisao real: como meu `p2_perguntas.py` agora existe DE
  VERDADE em `assistente/gatilhos/`, a suite de teste da propria infra
  (`tests/test_fase7_infra_gatilhos.py`, arquivo de outra faixa) que
  assumia a pasta vazia/so com modulos de mentira passa a falhar quando
  rodada JUNTO (isolada, continua passando). Nao mexi nesse arquivo (nao e
  meu) - so documentei em `progress.txt`, porque isso vai se repetir com
  cada faixa P nova que chegar.

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
