# Aprendizados - Faixa A13 (calculos em codigo)

- O ambiente automatico desta sessao apontava pro repo errado
  (`/home/user/financeiro-construtora`, financeiro real da construtora,
  nada a ver com este painel pessoal). `docs/agentes/fase7-regras-faixa.md`
  avisa exatamente pra isso: nunca editar esse repo nem o checkout
  principal `painel-pessoal-tdah`, e criar a propria worktree a partir de
  `fase7/integracao`. Confirmar `pwd`/`git remote -v` antes de qualquer
  edicao evitou o erro.

- `ia/funcoes/{chat,captura,planejamento,visao}.py` (infra da Etapa 0)
  ainda nao existia nesta integracao no momento desta faixa - toda a logica
  de IA relevante (CAPTURE_PROMPT, CHAT_TOOLS, classify_capture, chat())
  ainda mora em `claude_client.py`. O inventario documenta os dois lugares
  (o de hoje e onde deve cair quando a migracao pra `ia/funcoes/`
  acontecer), mas a troca em si e de outra faixa.

- Achado nao-obvio: `app.py` e `cards.py` ja tem DUAS implementacoes
  independentes da mesma formula de percentual de meta
  (`_consultar_meta` em app.py vs `card_meta` em cards.py), com
  arredondamento diferente (0 casas vs 1 casa) - risco real de a tela
  mostrar dois numeros diferentes pra mesma meta dependendo de qual
  caminho (card vs consulta) o usuario bateu. Nao e desta faixa consertar
  (arquivos nao sao meus), so documentado com precisao em docs/calculos.md.

- Decisao de design em `calculos.py`: `percentual_meta` clampa o piso em
  0% (um `atual` negativo vira 0%), diferente do `card_meta` legado que
  so clampa o teto (100%). Foi decisao consciente (uma "meta com divida"
  negativa nao faz sentido como % pra exibir), documentada na docstring -
  quem for migrar o caller precisa saber que o numero pode mudar de
  sinal/valor num caso extremo raro (guardado negativo).

- Nao precisou de nenhuma dependencia nova: mes com dia clampado
  (fim de mes/bissexto) da pra fazer com `calendar.monthrange` puro do
  stdlib, sem `python-dateutil` (que nao esta no requirements.txt).
