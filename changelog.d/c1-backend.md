### Fase 7 - Faixa C1 (polimento do backend)

- **Chat com o histórico da A5 e medição nova**: o app manda o resumo das conversas antigas
  (`contexto_fixo`) e na íntegra só o que ainda não foi resumido (máx. 20 mensagens, sem buraco
  e sem repetir). Cada rodada do chat é medida em `uso_ia` (`medir_uso=True`, via
  `claude_client.opcoes_chat`).
- **Gasto do mês com fonte única** (`ia.medicao.gasto_mes_atual`): cada chamada de IA conta
  uma vez só, mesmo gravada na tabela nova e na antiga. **Teto único de R$40** (ou o
  configurado no card) vale pro chat, intent, nota fiscal, Telegram, decisão e mensagem difícil.
- **Mensagens de erro certas**: teto estourado → "teto mensal de gasto com IA estourado" (402);
  rede/provedor → "Erro ao falar com a IA" (502); só JSON ruim continua "formato inesperado".
  Exceções novas em `ia.core` (`TetoEstourado`, `ErroProvedor`, `RespostaInvalida`). Foto de
  nota fiscal com falha de IA não dá mais erro 500.
- **Um push só à noite**: com o briefing da P3 ligado (e o tick configurado), o fechamento
  antigo das 21h fica calado.
- **Construtora pelo cliente novo** (`construtora_cliente.py`): o painel recebe só gastos,
  entradas e o tempo até a próxima conta - nunca lucro, margem nem VGV. Push e contexto do chat
  sem valor de conta. `CONSTRUTORA_API_MOCK=1` funciona na aba.
- **Percentual de meta igual em todo lugar** (`calculos.percentual_meta_exibicao`, 1 casa).
- **Caixa respeita a central de avisos (P8)**: tipo desligado não cria item nem manda push;
  silêncio e canal "só Caixa" valem pro push. Corrigido o fechamento da noite da P3, cuja
  resposta ("Como foi o dia?") nunca chegava a gravar o humor.
- **Cards de assinatura e parcela** cadastrados no servidor (modo visitante esconde valores) e
  **Desfazer** de assinatura/parcela funcionando também pelo botão geral.
- **Visão no GPT-6 Luna pronta**: o adapter OpenAI converte foto e PDF; ligar `ativo: true` basta.
- **Telegram**: webhook novo e polling antigo nunca rodam juntos no mesmo bot (`TELEGRAM_MODO`,
  `TELEGRAM_BOT_TOKEN_CAPTURA` pra bot separado).
- **Robustez**: fuzz de 184 cenários (`scripts/ralph-c1-backend/fuzz.py`) achou e corrigiu 15
  erros 500 (assinatura/parcela com valor ou data inválidos, dado ruim já gravado derrubando a
  listagem, corpos malformados em regras e Caixa). Testes não saem mais da máquina (SDKs de IA
  apontam pra porta local) e não vazam estado entre arquivos.
