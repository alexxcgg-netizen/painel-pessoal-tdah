-- Diario de bordo (leva 22/10, docs/briefings/2026-10-22-leva-ideias-v3.md): as 3 perguntas depois do voo.
-- natureza: 'navegacao' | 'tgl' | 'instrumentos' (NULL = nao respondido; voo antigo da CIV fica NULL).
-- noturno: 1 = voo de noite (NULL/0 = dia). toques: toques e arremetidas do TGL.
-- Colunas novas nullable, sem UPDATE em dado existente.
ALTER TABLE voos ADD COLUMN natureza TEXT;
ALTER TABLE voos ADD COLUMN noturno INTEGER;
ALTER TABLE voos ADD COLUMN toques INTEGER;
