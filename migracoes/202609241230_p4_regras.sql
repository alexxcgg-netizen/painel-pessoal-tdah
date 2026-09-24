-- Faixa P4 (Fase 7): regras em portugues criadas pelo Alex no chat/captura
-- ("me avisa se gastar mais de 300 com mercado na semana", "todo dia as 18h
-- me lembra de tomar o remedio"). Uma regra vira um item da Caixa do
-- assistente (aviso) quando a condicao bate - ver assistente/regras.py
-- (motor puro) e assistente/gatilhos/p4_regras.py (tick).
--
-- `json` guarda o contrato normalizado {gatilho, condicao, acao, texto}
-- (ver assistente.regras.normalizar_regra) como texto JSON - schema livre
-- de proposito, porque cada gatilho tem um formato de condicao/acao
-- diferente e SQLite nao tem JSON tipado nativo.
-- `pausada_ate`: NULL = nunca pausada; texto ISO (data ou data+hora) =
-- gatilho ignora a regra enquanto "agora" for menor que este valor.
-- `ultima_vez`: ISO (data+hora) do ultimo disparo - usado pelo motor pra
-- decidir se a janela atual (dia/semana/mes, conforme o gatilho) ja foi
-- atendida, pra nao duplicar aviso (ver assistente/regras.py).
CREATE TABLE IF NOT EXISTS p4_regras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto_original TEXT NOT NULL,
    json TEXT NOT NULL,
    ativa INTEGER NOT NULL DEFAULT 1,
    pausada_ate TEXT,
    criada_em TEXT NOT NULL DEFAULT (datetime('now')),
    ultima_vez TEXT
);

CREATE INDEX IF NOT EXISTS idx_p4_regras_ativa ON p4_regras (ativa);
