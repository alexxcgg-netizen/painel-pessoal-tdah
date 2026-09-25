-- Fase 9, faixa F9-sync: idempotencia real da sincronizacao Pluggy (Nubank) +
-- campos ricos da transacao (reconexao do item Pluggy reimportou o historico
-- inteiro com um novo conjunto de ids, dobrando linhas na mesma conta - ver
-- CHANGELOG 2026-09-25, "pendencias pra proxima sessao", item Pluggy
-- `ce7aa441` 404 -> reconectado).
--
-- Roda uma unica vez por banco (o runner em db.py registra o nome do arquivo
-- em `migracoes_aplicadas` e nunca reaplica).
--
-- Esta faixa NAO faz limpeza de duplicata aqui via SQL/DELETE em lote: uma
-- primeira versao tentava agrupar por (bank_account_id, data, valor,
-- descricao), mas `valor`/`descricao` sao criptografados em repouso quando
-- ENCRYPTION_KEY esta configurada (Fernet usa IV aleatorio, entao dois
-- ciphertexts do mesmo valor/descricao nunca batem por igualdade de string
-- - o DELETE simplesmente nao acha nada em producao) e, sem criptografia,
-- o mesmo agrupamento apagaria duas compras legitimas iguais no mesmo dia
-- (ex.: dois cafes de R$ 8,00 com ids diferentes). A limpeza das duplicatas
-- do incidente de reconexao passa a ser feita pela reconciliacao por
-- external_id dentro da propria sincronizacao (rotas/f8_banco.py,
-- `_reconciliar_transacoes_removidas`): a cada sync, o que a Pluggy devolve
-- agora e tratado como fonte da verdade pra aquele intervalo de datas, e so
-- roda quando a busca de transacoes terminou completa (nunca com paginacao
-- truncada nem lista vazia) - nunca toca em `expenses` (gasto manual).
ALTER TABLE bank_transactions ADD COLUMN estabelecimento TEXT;
ALTER TABLE bank_transactions ADD COLUMN categoria_pluggy TEXT;
ALTER TABLE bank_transactions ADD COLUMN descricao_original TEXT;
ALTER TABLE bank_transactions ADD COLUMN tipo_operacao TEXT;
ALTER TABLE bank_transactions ADD COLUMN estorno_de_external_id TEXT;
