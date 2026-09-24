# Aprendizados - Faixa A7 (Migração 1)

- **Migrar uma função de IA pra `chamar_ia` troca o objeto que faz a
  chamada de rede.** `AdapterAnthropic` (`ia/adapters/anthropic.py`, faixa
  A2) cria seu próprio `anthropic.Anthropic(...)` dentro de `__init__` - não
  reaproveita `ia.legado.client`. Qualquer teste antigo que mocka
  `claude_client.client.messages.create` (ou `ia.legado.client...`)
  especificamente pra função migrada para de funcionar, mesmo com
  `ativo: false` na config (o `modelo_atual` também passa pelo adapter).
  Quem herdar a próxima faixa de migração (A8/A9/...) provavelmente vai
  bater nisso de novo - o jeito certo de mockar depois da migração é
  `patch("ia.funcoes.<grupo>.chamar_ia", ...)` (unidade) ou
  `ia.core.registrar_adapter(...)` com um Adapter dublê (integração com o
  núcleo de verdade) - não mais `claude_client.client.messages.create`.

- **`ia.core.chamar_ia` sempre exige um objeto JSON no topo do schema**
  (`ia/core.py:_chamar_uma_vez`: `isinstance(dados, dict)` obrigatório).
  `escolher_essencial` devolvia uma lista `[{"id":..,"motivo":..}]` direto -
  teve que virar `{"escolhas": [...]}` no schema/prompt novo, com o código
  desembrulhando `dados["escolhas"]` antes de devolver pro chamador (que
  continua recebendo a lista, sem mudar o contrato externo).

- **`resolver_data` fica mais simples separando "pista bruta" de "hora
  implica hoje".** A regra "tem hora mas nenhuma referência de dia -> assume
  hoje" não é sobre calendário, é sobre o par (quando, hora) de uma
  tarefa - por isso ficou em `classify_capture` (depois de chamar
  `resolver_data`), não dentro da própria função de resolução de data.

- **`calculos.data_ultima_parcela(hoje, n+1)` soma `n` meses a uma data**
  (com o dia comprimido em mês mais curto) sem precisar reimplementar
  `_somar_meses` (que é privada em `calculos.py`) nem adicionar
  `python-dateutil`.
