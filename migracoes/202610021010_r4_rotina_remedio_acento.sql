-- Faixa R4 (uso diario): corrige o texto da rotina padrao ja semeada em instalacoes
-- antigas ("Remedio" sem acento -> "Remédio"). UPDATE de dado, justificado: so toca
-- linhas com EXATAMENTE o texto antigo (item que o dono editou fica como esta) e e
-- idempotente (rodar de novo nao encontra mais nenhuma linha com o texto antigo).
UPDATE rotina_itens
   SET texto = 'Remédio (se tiver hoje)'
 WHERE texto = 'Remedio (se tiver hoje)';
