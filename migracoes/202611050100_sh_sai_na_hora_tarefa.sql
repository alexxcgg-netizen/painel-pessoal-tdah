-- Leva "conversa de 04/11" (2026-11-05, docs/briefings/2026-11-05-conversa-04-11.md).
-- sai_na_hora = 1 quando a hora que o Alex disse e a de SAIR de casa, nao a de chegar no lugar
-- ("o date comeca as 19, so saio de casa as 19" - o lugar fica a ~1 h). Ai os avisos
-- e a ilha mandam sair na hora e a chegada vira hora + trajeto. NULL/0 = hora de chegada (o normal).
-- Coluna nova nullable, nenhum dado existente e tocado.
ALTER TABLE tasks ADD COLUMN sai_na_hora INTEGER;
