### Fase 7, P4 - regras em portugues (backend)

- `assistente/regras.py`: motor puro das regras que o Alex cria em
  linguagem natural no chat/captura ("me avisa se gastar mais de 300 com
  mercado na semana", "todo dia as 18h me lembra de tomar o remedio").
  Parser local (regex, sem IA) pros formatos diario/semanal com hora fixa e
  limite de gasto por categoria/periodo; `interpretar_regra` cai pra
  `ia.core.chamar_ia("interpretar_regra", ...)` (config em
  `ia/config.d/interpretar_regra.json`, ativo=false) so quando o local nao
  bate. `normalizar_regra` valida os 5 gatilhos suportados (`horario`,
  `gasto_categoria`, `habito_nao_feito_ate`, `tarefa_vencida`,
  `sinal_iphone`) com a MESMA validacao pro resultado local e da IA. Regra
  sobre vida amorosa/relacionamento e sempre recusada, por palavra-chave,
  antes de chamar IA (decisao do Alex).
- `assistente/gatilhos/p4_regras.py`: tarefa periodica do tick - avalia
  cada regra ativa e enfileira um aviso (`origem: "p4_regras:<id>"`) quando
  a condicao bate, idempotente por janela (dia/semana/mes/data conforme o
  gatilho, via a coluna `ultima_vez`).
- `classificador_local/regras/p4_regra.py`: reconhece o pedido sem IA
  (`casar`) e devolve o card de confirmacao `p4_regra_confirmacao`
  (Confirmar/Cancelar) via `executar` - card e action ainda NAO documentados
  em `docs/CARDS.md` nem renderizados no front (fora do escopo desta faixa,
  ver `scripts/ralph-p4-regras/progress.txt`).
- `migracoes/202609241230_p4_regras.sql`: tabela `p4_regras`.
- `rotas/p4_regras.py`: `GET /api/p4_regras`, `POST /api/p4_regras/confirmar`,
  `POST /api/p4_regras/<id>/pausar`, `POST /api/p4_regras/<id>/retomar`,
  `DELETE /api/p4_regras/<id>` (sessao/PIN, Blueprint registrado sozinho).
- Testes: `tests/test_fase7_p4_*.py` (167 testes + 41 subtests, 0 falhas) -
  parser local, schema validado com IA mockada, cada gatilho, idempotencia,
  pausa, apagar, e recusa de regra sobre vida amorosa/relacionamento.
