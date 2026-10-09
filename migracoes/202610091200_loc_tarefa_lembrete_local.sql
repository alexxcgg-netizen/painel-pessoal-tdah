-- Localizacao do celular (2026-10-09): tarefa/lembrete criado com "aqui"/"onde eu
-- estou" guarda o endereco aproximado (texto, vindo do GPS + OpenStreetMap). Colunas
-- novas nullable, sem UPDATE em dado existente.
ALTER TABLE tasks ADD COLUMN local TEXT;
ALTER TABLE lembretes ADD COLUMN local TEXT;
