# Aprendizados - faixa P4 (regras em portugues)

- **Idempotencia sem tabela extra**: em vez de guardar uma "chave de janela
  ja disparada", basta comparar `ultima_vez` (coluna que ja existia no
  desenho pedido pelo prompt) contra os limites da janela atual (dia pro
  horario diario, semana/mes/dia pro gasto_categoria). Se `ultima_vez` cai
  dentro da janela atual, ja disparou - nao dispara de novo. Isso sobrevive
  a reinicio do processo e a 2 ticks no mesmo minuto sem precisar de lock
  nem de tabela auxiliar. A `chave_unica` do `enfileirar` (Caixa, P1a) e so
  a segunda camada de seguranca.

- **origem: o prefixo tem que ser o nome do ARQUIVO do gatilho, nao um nome
  "bonito" livre.** Eu tinha usado `p4_regra:<id>` (sem "s", pensando no
  singular "uma regra") mas o arquivo se chama `assistente/gatilhos/p4_regras.py`
  - o integrador corrigiu isso no meio do trabalho. Regra geral pra quem
  fizer faixa nova: o prefixo de `origem` (antes do PRIMEIRO ":") e sempre
  `Path(__file__).stem` do proprio gatilho, nunca escolhido "a mao".

- **classificador_local/regras/<nome>.py mudou de contrato quando a infra
  chegou**: antes eu tinha `casar()` devolvendo so `{"texto": ...}` (formato
  que eu mesmo inventei, sem infra nenhuma pra validar). Quando a Etapa
  0/X1 chegou, o contrato de verdade (classificador_local/__init__.py) exige
  `{"acao": str, "confianca"?, "parametros"?, "precisa_confirmacao"?}` -
  regra que nao bate nesse formato e simplesmente PULADA (loga um warning,
  nunca quebra) pelo dispatcher `classificador_local.casar()`, o que teria
  deixado minha regra inteira muda sem erro nenhum aparente. Licao: quando
  uma faixa comeca ANTES da infra compartilhada estar pronta, vale a pena
  escrever um teste que passa pelo DISPATCHER real (nao so pelo modulo
  isolado) assim que a infra chegar - foi assim que percebi o problema
  (tests/test_fase7_p4_classificador.py::TestCasarViaDispatcher).

- **Nome real da tabela de sinais do iPhone e `sinais` (nao `sinais_iphone`
  como eu tinha chutado no design inicial), coluna de horario e `quando`
  (nao `criado_em`)** - e ja existe `assistente.sinais.ultimos_sinais`/
  `sinal_recente` prontos (faixa P7), entao `avaliar_sinal_iphone` usa isso
  em vez de reescrever o SQL, com fallback defensivo (import tardio +
  `except sqlite3.OperationalError`) pro caso de rodar numa integracao onde
  a P7 ainda nao chegou.

- **Parser local: cuidado com ordem periodo/categoria.** "me avisa se
  gastar mais de 300 com mercado na semana" (categoria primeiro) e "me
  avisa se eu gastar mais de 150 no mes com farmacia" (periodo primeiro)
  sao as duas frases naturais em portugues, mas so a primeira e um formato
  "simples" o bastante pra regex sem virar um parser ambiguo. A regra que
  segui: se a regex NAO tem certeza (categoria capturada contem uma palavra
  de periodo tipo "mes"/"semana"/"hoje"), devolve None e deixa a IA
  resolver - errar pra "cai na IA" e sempre mais seguro que errar pra "criei
  a regra errada sem o Alex perceber".
