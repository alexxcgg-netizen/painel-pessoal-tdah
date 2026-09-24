-- Faixa P1a (Fase 7): nucleo da Caixa do assistente proativo. Ver
-- docs/agentes/fase7-assistente.md (contrato comum) e assistente/contrato.py
-- (assinatura publica: enfileirar/resolver/aviso_permitido).
--
-- assistente_itens: cada linha e um item da Caixa (pergunta, aviso, sugestao,
-- briefing ou proposta_memoria) que o assistente colocou na fila pro Alex ver
-- e/ou responder. `chave_unica` (quando nao vazia) evita duplicar o mesmo item
-- se um gatilho rodar duas vezes (tick idempotente) - por isso o indice unico
-- parcial abaixo, em vez de UNIQUE direto na coluna (que bloquearia varias
-- linhas com chave_unica = '').
--
-- `opcoes` e `repetir` guardam JSON como TEXT (mesmo padrao ja usado em
-- outras tabelas do projeto pra campo estruturado, ex.: cards de
-- chat_mensagens) - sqlite3 nao tem tipo JSON nativo.
-- `repetir` no formato do contrato: {"apos_minutos": [120, 240], "max_por_dia": 3}.
--
-- `pushes_hoje`/`ultimo_push_em`: contagem de push reenviado hoje (a P1a
-- reseta a contagem sozinha quando o dia de `ultimo_push_em` for diferente do
-- dia de `agora`, sem precisar de coluna extra so pra guardar "qual dia" -
-- ver assistente/caixa.py, processar_repeticoes).
CREATE TABLE IF NOT EXISTS assistente_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('pergunta', 'aviso', 'sugestao', 'briefing', 'proposta_memoria')),
    titulo TEXT NOT NULL,
    corpo TEXT NOT NULL DEFAULT '',
    opcoes TEXT,
    origem TEXT NOT NULL DEFAULT '',
    chave_unica TEXT NOT NULL DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente', 'resolvido', 'adiado', 'expirado')),
    resposta TEXT,
    resposta_texto TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    vence_em TEXT,
    adiado_ate TEXT,
    repetir TEXT,
    pushes_hoje INTEGER NOT NULL DEFAULT 0,
    ultimo_push_em TEXT,
    resolvido_em TEXT
);

-- Indice unico parcial: so entra em vigor quando chave_unica foi de fato
-- informada (string nao vazia). Item sem chave_unica pode se repetir a
-- vontade (comportamento igual a nao ter dedupe nenhum).
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistente_itens_chave_unica
    ON assistente_itens (chave_unica)
    WHERE chave_unica <> '';

-- listar()/contar_pendentes() filtram por estado o tempo todo (tela
-- Assistente + selo da aba Hoje, no cliente); tipo entra na ordenacao por
-- urgencia; vence_em entra tanto na ordenacao quanto em expirar().
CREATE INDEX IF NOT EXISTS idx_assistente_itens_estado ON assistente_itens (estado);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_tipo ON assistente_itens (tipo);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_vence_em ON assistente_itens (vence_em);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_adiado_ate ON assistente_itens (adiado_ate);

-- Horario do ultimo /api/tick executado com sucesso: reaproveita a tabela
-- `configuracoes` (chave/valor) que ja existe em db.py, em vez de criar uma
-- tabela `assistente_ticks` so pra uma linha - ver
-- assistente/caixa.py (CHAVE_ULTIMO_TICK) e rotas/p1a_caixa.py
-- (GET /api/assistente/saude). Nada a criar aqui: `configuracoes` ja existe
-- desde a Fase 1 (db.py, init_db()).
