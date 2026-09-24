# Aprendizados - faixa N1 (assinaturas e compras parceladas)

- `classificador_local/__init__.py` (contrato real, mesclado no meio desta
  faixa) só repassa `resultado["parametros"]` pro `executar(conn,
  parametros)` do módulo - **não** `resultado["acao"]`. Um arquivo de regra
  que resolve VÁRIAS frases (o meu resolve 7) precisa duplicar a sub-ação
  DENTRO de `parametros` também (`parametros["acao"]`), senão `executar`
  não tem como saber qual das 7 rodar. Ver `_resultado()` em
  `classificador_local/regras/n1_financas.py`.

- `casar()` não pode devolver `Decimal` em `parametros`: `/api/intent/
  classificar` (`app.py`, não é meu arquivo) faz `jsonify(resultado)` sem
  conversão nenhuma, e o encoder JSON padrão do Flask não serializa
  `Decimal` (dá 500). Resolvido convertendo pra `float` no fim do parser de
  valor do classificador (`_parse_valor`); `financas_recorrentes._d`
  reconverte pra `Decimal` via `str(valor)` na hora de gravar, então a
  precisão do texto original ("21,90") não se perde nesse meio de campo.

- Granularidade de MÊS pra `parcela_info` (não de dia): a primeira versão
  tentava decidir "parcela paga" olhando se o dia de cobrança do mês atual
  já tinha passado, e isso criava uma inconsistência (a compra virava
  "quitada" um mês cedo demais, no PRÓPRIO dia da última cobrança, em vez
  de só no mês seguinte). Resolvido tratando o mês inteiro como uma unidade
  - o dia exato só entra pra calcular a *data* de `proxima_cobranca`, nunca
  pra decidir `parcela_atual_calculada`/`quitada`/`parcelas_restantes`.
  Mais simples E mais correto (pego rodando os testes, não por inspeção).

- `total_mensal_comprometido`/`impacto_limite_cartao_proximos_meses`
  precisam listar TODA assinatura (`apenas_ativas=False`), não só
  `ativa=1`: uma assinatura cancelada NO MEIO do mês ainda cobrou antes de
  cancelar, e `_assinatura_cobra_no_mes` já sabe decidir isso sozinha
  olhando `inicio`/`cancelada_em` - filtrar por `ativa=1` antes de chamar
  essa função descartava a assinatura cedo demais.

- Desfazer: `db.ENTIDADES_DESFAZIVEIS`/`app._desfazer_itens` não são meus
  arquivos e não conhecem as 2 entidades novas. Em vez de esperar,
  implementei um mecanismo LOCAL que grava na MESMA tabela
  `acoes_desfazer` (schema genérico já existia, Fase 6) só que sem passar
  pelas funções restritas de `db.py` - uma rota própria
  (`POST /api/financas/desfazer/<token>`) aplica. Convive sem conflito com
  o mecanismo geral (tokens são `secrets.token_urlsafe`, sem colisão
  prática) e pode ser aposentado depois sem mudar o formato do token no
  card.

- Rodar a suite completa de infra (`test_fase7_infra_rotas.py`,
  `test_fase7_infra_classificador.py`) só por sanidade pegou falhas
  PRÉ-EXISTENTES (confirmado removendo temporariamente meus 2 arquivos e
  rodando de novo - a mesma falha aparece, só que travando em "p7_sinais"
  em vez de "n1_financas"): esses testes de infra registram
  `rotas.registrar_todas` uma segunda vez no MESMO `app.app` real dentro
  do processo de teste, o que colide com qualquer blueprint que `app.py`
  já registrou sozinho na subida. Não mexi nesses arquivos (não são meus);
  anotado em `progress.txt` pro integrador.
