# Pendências que ainda podem valer

Tirado dos arquivos antigos de setembro (`docs/historico/TODO-2026-09.md` e `STATUS-2026-09.md`) em
2026-10-16. **Nenhum item foi conferido de novo** - confirmar com o Alex antes de agir, e apagar a
linha quando resolver. Este é o único lugar de pendência: não recriar TODO/STATUS na raiz.

- [ ] **Segurança:** revogar a chave da API do Render que foi colada num chat e gerar outra se precisar
      (Render > Account Settings > API Keys). Só o Alex pode fazer.
- [ ] Testes que leem o `.env` real (deveriam usar `.env` de teste).
- [ ] Teste dependente de data: `test_formato_da_resposta` (falhava por data, não por bug).
- [ ] A página carregava `summarize_day` (IA) a cada abertura: conferir se o teto de R$ 40/mês de
      custo de IA segura (hoje o resumo é cacheado 1x/dia - provavelmente já resolvido).
- [ ] Compra parcelada sem interruptor de aviso.
- [ ] Widget do Scriptable segue sem acento de propósito.
