-- Extrato da CIV Digital (ANAC) no diario de voo (2026-10-09): cada voo guarda a
-- aeronave (matricula), a funcao a bordo como esta na CIV ("Piloto em Instrucao",
-- "Piloto em Instrucao Solo"...), o tipo ('simulador' nao entra no total de horas
-- de voo, igual a CIV; NULL = voo) e a fonte ('civ' = importado do extrato oficial).
-- Colunas novas nullable, sem UPDATE em dado existente.
ALTER TABLE voos ADD COLUMN aeronave TEXT;
ALTER TABLE voos ADD COLUMN funcao TEXT;
ALTER TABLE voos ADD COLUMN tipo TEXT;
ALTER TABLE voos ADD COLUMN fonte TEXT;
