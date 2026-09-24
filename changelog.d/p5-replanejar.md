### Fase 7, faixa P5 - replanejar o dia
- **Reconhece sem IA** "replaneja meu dia", "atrasei", "perdi a manhã" e
  variações pt-BR (`classificador_local/regras/p5_replanejar.py`) e monta
  o card `replanejamento` (contrato `{cards, resumo_texto, passos}`) com o
  novo plano e as ações `aplicar_replanejamento`/`desfazer_replanejamento`.
- **`assistente/replanejar.py`**: junta tarefas de hoje ainda não feitas +
  agenda restante a partir da hora atual, chama
  `claude_client.plano_do_dia` (checando o teto mensal de IA antes -
  `/api/plano-do-dia` não checava) e grava/desfaz o plano aplicado
  (`configuracoes`, chave `p5_ordem_dia:<dia>` - ainda não existe tabela de
  ordem/horário por tarefa, ver `scripts/ralph-p5-replanejar/
  APRENDIZADOS.md`).
- **Sugestão automática às 14h** (`assistente/gatilhos/p5_replanejar.py`,
  "Quer replanejar a tarde?" quando há tarefa atrasada) - flag
  `replanejar_auto` **desligada por padrão**.
- Testes: `tests/test_fase7_p5_replanejar.py` (32, 100% verde, IA sempre
  mockada).
