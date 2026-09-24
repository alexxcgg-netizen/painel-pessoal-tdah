# Aprendizados - faixa N3a (widget)

- **Infra de Blueprint ainda nao mergeada e nao trava a faixa**: escrever o
  `from rotas._base import app_modulo` DENTRO de cada funcao de rota (nunca
  no topo do arquivo) deixa o modulo inteiro importavel mesmo sem
  `rotas/__init__.py`/`rotas/_base.py` existirem ainda - o namespace package
  implicito do Python (PEP 420) ja deixa `from rotas import n3a_widget`
  funcionar sem `__init__.py`. Isso permitiu testar a rota HTTP completa
  (nao so a funcao pura) registrando o Blueprint num Flask app isolado no
  proprio arquivo de teste, com um stub minimo de `sys.modules["rotas._base"]`
  devolvendo o `app` real (importado com banco de teste, igual todo outro
  teste do projeto). Ver tests/test_fase7_n3a_widget_api.py
  (_instalar_stub_rotas_base). Outras faixas de rota ja mergeadas
  (p7_sinais) importam `app_modulo` no topo do arquivo e por isso o modulo
  delas nem importa hoje - se outra faixa tiver o mesmo bloqueio, esse
  padrao lazy-import resolve sem esperar a infra.

- **Achar a funcao certa pra reaproveitar vale a pena procurar pelo nome**:
  `app._proximo_item_em_foco` (usada por `/api/visao-dia/hoje`) e um match
  quase perfeito pro campo `foco` do widget (literalmente "item em foco
  agora") - so nao expõe minutos, so o texto formatado ('em 19 min'), entao
  a coleta busca o MESMO item escolhido de novo (por origem+id) pra derivar
  o numero, sem reimplementar a escolha em si.

- **Cuidado ao "seguir os docs" de outra faixa quando ele contradiz o
  contrato do proprio prompt**: docs/widget-widgy.md e
  docs/widget-api-widget.md (N3c/N3d) foram escritos falando de um
  comportamento ("sem token = sem autenticacao, aberto") mais permissivo do
  que o pedido explicito desta faixa ("401 sem/errado"). Ao tentar seguir o
  doc por consistencia, o classificador de seguranca do harness bloqueou o
  comando (a mudanca "enfraquecia" a checagem de token) - bom sinal de que a
  leitura mais estrita era a certa aqui. Registrado em progress.txt pro
  integrador decidir se os docs precisam mudar.
