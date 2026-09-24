### Fase 7 - Faixa A14 (roteador de mensagem simples do chat)

- **`ia/roteador_chat.py`**: implementa `decidir(mensagem, contexto)` e
  `decidir_com_motivo(mensagem, contexto)` (destino + motivo, pra A/B e
  logs) de verdade, substituindo o placeholder da Etapa 0 (que sempre
  devolvia `"padrao"`). Devolve `"local"` quando o classificador local
  (`classificador_local.casar`, import tardio/defensivo - infra da Etapa 0
  ainda em extração) ou uma consulta já conhecida
  (`aprendizado.consulta_conhecida`/`aprendizado.padrao_intent_confiavel`,
  mesma lógica de `app._classificar_intent(somente_local=True)`) resolvem
  sem IA nenhuma; `"luna"` pra mensagem curta e simples que ainda precisa
  de IA mas não do modelo grande; `"padrao"` pro resto (pedido de
  conselho/decisão, pergunta sobre sentimento/emoção, mensagem longa,
  histórico longo, ou qualquer erro interno). **Nunca levanta exceção** -
  qualquer falha interna cai em `("padrao", "erro:<tipo>")`.
- **Atrás de flag, desligada por padrão**: `ia/roteador_chat.json`
  (`{"ativo": false}`) é a fonte principal; com ela desligada,
  `decidir`/`decidir_com_motivo` sempre devolvem `"padrao"` - zero mudança
  de comportamento do chat até o Alex ligar de propósito. Existe também um
  caminho alternativo pela chave `roteador_chat_ativo` em `configuracoes`
  (`db.obter_configuracao`), pra uma futura tela ligar sem editar arquivo.
- **`tests/test_fase7_a14_roteador.py`**: flag desligada sempre `"padrao"`
  (inclusive pra mensagem que bateria com local/luna, JSON corrompido,
  diretório no lugar do arquivo); com a flag ligada, 40+ mensagens
  sintéticas pt-BR cobrindo os três destinos (consulta conhecida ->
  `local`; conselho/decisão/emoção -> `padrao`; cumprimento/mensagem curta
  -> `luna`), limite de tamanho de mensagem e de histórico; robustez
  (vazio, só espaço, `None`, gigante, emoji, só números, tipos inválidos em
  mensagem/contexto, `classificador_local` ausente ou que lança exceção).
  `scripts/testes.sh tests/test_fase7_a14_roteador.py` -> 38 testes / 47
  subtests, 0 falhas.
