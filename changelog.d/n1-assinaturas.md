### Fase 7 - faixa N1 (assinaturas e compras parceladas, junto com o cartão)

- Novos modelos (migração `migracoes/202609241300_n1_assinaturas.sql`):
  `assinatura` (nome, valor, dia de cobrança, cartão/forma, categoria,
  ativa, início, observação, cancelada_em) e `compra_parcelada` (descrição,
  valor total, n_parcelas, valor_parcela, cartão, primeira_parcela,
  categoria) - declaradas pelo Alex ou pelo classificador local, sem
  sobrepor a detecção automática de recorrência que já existia
  (`gastos.detectar_gastos_recorrentes`, que observa o histórico de gasto).
- `financas_recorrentes.py`: total mensal comprometido, próximas cobranças
  ("em N dias"), parcelas restantes/mês de término (granularidade de mês -
  uma compra fica "em andamento" o mês inteiro da última parcela), impacto
  no limite de cada cartão nos próximos 6 meses (reusa
  `vida.fracao_limite_cartao`, cruzando com `bank_accounts.limite`, US-E15)
  e `valor_para_aviso_custos_fixos`, o número que alimenta o aviso já
  existente "custos fixos já comprometem X%"
  (`notificacoes.mes_seguinte_apertado`) sem duplicar aquele cálculo.
- Classificador local sem IA (`classificador_local/regras/n1_financas.py`):
  "assinei Netflix 55 por mês", "comprei geladeira 3000 em 12 vezes no
  nubank", "cancelei a Netflix", "quanto tenho de parcelas?", "quais
  assinaturas eu tenho" - cria/cancela/consulta e devolve os cards
  `assinatura`, `compra_parcelada` e `resumo_financeiro_recorrente`
  (contrato completo em `docs/contrato-assinaturas.md`), com Desfazer.
- Rotas `rotas/n1_financas.py`: CRUD de assinaturas/parcelas +
  `GET /api/financas/comprometido` (resumo pra tela do cartão, V6).
- `docs/contrato-assinaturas.md`: publicado logo no início da faixa, pras
  faixas de UI (V1, V6) poderem desenhar contra o formato de rota/card sem
  esperar a lógica terminar.
- 138 testes (`tests/test_fase7_n1_calculos.py`,
  `tests/test_fase7_n1_classificador.py`, `tests/test_fase7_n1_rotas.py`),
  incluindo fuzz de 60+ entradas estranhas no classificador e a integração
  completa via `POST /api/chat`.
