### Fase 7 N3a: endpoint e pagina do widget (`GET /api/widget`, `GET /widget`)

- Novo `rotas/n3a_widget.py` (Blueprint `n3a_widget`): `GET /api/widget`
  devolve o resumo compacto pro widget externo (Widgy, "API Widget" e
  similares) no formato fixo `{versao, atualizado_em, estado, foco,
  proxima_conta, habitos, custo_ia, linhas}` - documentado antes em
  `docs/widget-widgy.md`/`docs/widget-api-widget.md`. `GET /widget` e a
  mesma coisa como pagina HTML leve (`templates/widget.html`), escura, sem
  PIN, com `<meta http-equiv="refresh" content="900">`.
- Autenticacao por `PAINEL_WIDGET_TOKEN` (variavel de ambiente nova, nao
  esta em `.env.example` ainda) - header `Authorization: Bearer` ou
  `?token=`, comparado com `hmac.compare_digest`. Sem token configurado ou
  sem/com token errado na requisicao: sempre 401 (nunca abre por padrao).
- Reaproveita coleta ja existente em vez de recalcular: item em foco
  (`app._proximo_item_em_foco`), contas pessoais e da construtora
  (`app._contas_pessoais_com_status` + a API read-only ja existente
  `app._buscar_contas_a_vencer_construtora`), habitos devidos/feitos
  (`db.list_habitos`/`vida.habito_devido_em`) e percentual do teto de IA
  (`ia.teto._fracao_teto`). Nunca devolve valor em R$ por padrao (so com
  `?mostrar_valores=1`, e nunca pra conta da construtora, mesmo assim).
  Qualquer falha na coleta vira `estado: "erro"` (200, nunca 500 cru).
- Testes: `tests/test_fase7_n3a_widget_montagem.py` (28, funcao pura de
  montagem do JSON) e `tests/test_fase7_n3a_widget_api.py` (33, coleta real
  + token + rota/pagina). 61/61 passam.
