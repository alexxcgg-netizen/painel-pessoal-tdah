-- Fase 9, faixa F9-sync: idempotencia real da sincronizacao Pluggy (Nubank) +
-- campos ricos da transacao + limpeza das duplicatas ja gravadas antes desta
-- faixa (reconexao do item Pluggy reimportou o historico inteiro com um novo
-- conjunto de ids, dobrando linhas na mesma conta - ver CHANGELOG 2026-09-25,
-- "pendencias pra proxima sessao", item Pluggy `ce7aa441` 404 -> reconectado).
--
-- Roda uma unica vez por banco (o runner em db.py registra o nome do arquivo
-- em `migracoes_aplicadas` e nunca reaplica) - tanto num banco novo (colunas
-- ainda nao existem, tabela ja vem vazia, o DELETE abaixo e um no-op) quanto
-- num banco existente com as duplicadas do incidente acima.

-- Campos ricos do Pluggy (extras, lidos apenas na sincronizacao - a faixa
-- financas_descricao.py decide o que exibir, nao esta faixa).
ALTER TABLE bank_transactions ADD COLUMN estabelecimento TEXT;
ALTER TABLE bank_transactions ADD COLUMN categoria_pluggy TEXT;
ALTER TABLE bank_transactions ADD COLUMN descricao_original TEXT;
ALTER TABLE bank_transactions ADD COLUMN tipo_operacao TEXT;
ALTER TABLE bank_transactions ADD COLUMN estorno_de_external_id TEXT;

-- Limpeza das duplicatas ja gravadas: mesma conta + mesma data + mesmo valor
-- + mesma descricao (nota: `valor`/`descricao` sao criptografados em
-- repouso quando ENCRYPTION_KEY esta configurada - Fernet usa IV aleatorio,
-- entao ciphertexts de duas gravacoes do mesmo valor/descricao nao batem por
-- igualdade de string; nesse caso esta limpeza nao encontra o cluster e nao
-- apaga nada, o que e o lado seguro do erro - nunca apaga transacao unica
-- nem gasto manual, que fica em outra tabela `expenses`, nunca tocada
-- aqui). Mantem sempre a linha de menor id (a mais antiga) de cada grupo;
-- um grupo sem duplicata (linha unica) tem MIN(id) = seu proprio id, entao
-- nunca e apagado.
DELETE FROM bank_transactions
WHERE id NOT IN (
    SELECT MIN(id) FROM bank_transactions
    GROUP BY bank_account_id, data, valor, descricao
);
