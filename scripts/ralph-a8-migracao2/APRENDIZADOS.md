# Aprendizados - Faixa A8 (Migracao 2: planejamento)

- Mesmo aviso de sempre (ja documentado por outras faixas): o ambiente
  automatico desta sessao apontava pro repo errado
  (`/home/user/financeiro-construtora`, financeiro real de outra empresa,
  sem nenhuma relacao com este painel). `docs/agentes/fase7-regras-faixa.md`
  manda ignorar esse checkout e criar a propria worktree a partir de
  `fase7/integracao`. `pwd`/`git remote -v` conferidos antes de qualquer
  edicao.

- `ia.core.chamar_ia` exige que o JSON de saida (quando ha `schema`) seja um
  OBJETO no nivel raiz (`ia/core.py:_chamar_uma_vez`: "JSON precisa ser
  objeto, veio ..."). As 3 funcoes que antes pediam pro modelo devolver uma
  LISTA crua (`break_down_task`, `requebrar_tarefa`, `gerar_mala` - prompt
  antigo dizia literalmente "Responda so com um JSON de lista de strings")
  tiveram que embrulhar a lista num objeto de 1 campo (`{"passos": [...]}`
  ou `{"itens": [...]}`) pro schema bater, e o codigo desembrulha de volta
  (`resp.dados["passos"]`) antes de devolver - o retorno Python continua
  `list[str]`, identico a antes. Quem for migrar outra funcao que hoje pede
  lista crua pro modelo (`ia/funcoes/captura.py`, `ia/funcoes/visao.py`, se
  alguma pedir) vai precisar do mesmo truque.

- `contexto_fixo` (nao `sistema`) e o campo certo pro prompt fixo de cada
  uma destas 5 funcoes: e a UNICA parte que o adapter Anthropic pode marcar
  com `cache_control` (`ia/adapters/anthropic.py:_estimar_tokens` +
  `cache_min_tokens`), entao mesmo com `cache.ativo: false` hoje, deixar o
  texto fixo la (em vez de misturado com o dado variavel na mensagem)
  deixa a config pronta pra ligar cache sem mexer no codigo de novo. Dado
  que muda a cada chamada (titulo da tarefa, destino, texto da pagina...)
  fica so na mensagem.

- Achado que nao e desta faixa consertar (app.py fora da lista de arquivos):
  nenhuma das 5 rotas que usam estas funcoes (`/api/tasks/<id>/breakdown`,
  requebrar, `/api/viagens/<id>/mala`, resumir link ao salvar, e
  `/api/plano-do-dia`) checava o teto mensal de IA antes desta migracao -
  so a rota de captura (`app.py:869`) e um segundo ponto (`app.py:3433`)
  faziam isso. Com `chamar_ia` o teto passa a valer de graca pras 5 (ele
  mesmo checa `ia.teto.teto_permite` antes de chamar qualquer adapter) -
  ver `_teto_permite` em `ia/core.py` e o teste
  `TestIntegracaoComNucleoReal.test_teto_estourado_bloqueia_sem_chamar_nenhum_adapter`
  em `tests/test_fase7_a8_planejamento.py`. Isso resolve, de graca, a
  pendencia "mala e PDF de cotacao fora do teto" apontada na Fase 6 (o PDF
  de cotacao em si e `ia/funcoes/visao.py`, faixa A9, fora do escopo A8;
  aqui so a mala e as outras 4 funcoes de planejamento ficaram cobertas).

- Efeito colateral do ponto acima que vale registrar: `app.py:_call_claude`
  (linha 411) so traduz `anthropic.APIError` e `(ValueError, KeyError)` em
  respostas de erro prontas. `chamar_ia` nunca levanta `anthropic.APIError`
  (o erro do provedor vira `Resposta(ok=False, erro=...)` dentro do
  nucleo), entao a distincao de mensagem que existia antes (erro de
  rede/provedor vs JSON invalido) se perde: qualquer falha das 5 funcoes
  desta faixa agora levanta `ValueError` e todas caem na mesma mensagem
  (`CLAUDE_FORMAT_ERROR_MSG`, 502) - inclusive teto estourado, que fica
  com uma mensagem generica em vez do formato dedicado que a rota de
  captura usa (`{"teto_ia_estourado": True}`, `app.py:875`). Funcionalmente
  seguro (nunca crasha, sempre 502 com mensagem util), so nao e uma
  experiencia tao boa quanto poderia ser. Anotado em `progress.txt` pro
  integrador decidir se vale a pena app.py reconhecer esse caso.
