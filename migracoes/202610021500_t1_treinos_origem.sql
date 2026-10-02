-- "Desfazer" do Feito hoje (treino) so apaga o que o botao marcou: a coluna `origem`
-- guarda 'botao' nesses registros (NULL = registrado pelo chat/tela, nunca apagado
-- pelo Desfazer). Coluna nova nullable, sem UPDATE em dado existente.
ALTER TABLE treinos ADD COLUMN origem TEXT;
