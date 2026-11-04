-- Leva "cards ao vivo" / assistente passo a passo (2026-11-04, docs/briefings/2026-11-04-cards-ao-vivo.md).
-- parada = onde o Alex passa ANTES de ir pro compromisso ("casa do guri"), do jeito que ele disse no chat.
-- A hora de sair conta casa -> parada -> destino com 5 min parado (notificacoes.caminho_com_parada).
-- Coluna nova nullable, nenhum dado existente e tocado.
ALTER TABLE tasks ADD COLUMN parada TEXT;
