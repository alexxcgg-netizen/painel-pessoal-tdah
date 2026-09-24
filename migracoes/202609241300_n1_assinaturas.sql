-- Faixa N1 (Fase 7): assinaturas e compras parceladas declaradas a mao pelo
-- Alex - complementa (nao substitui) a deteccao automatica de gasto
-- recorrente que ja existe (gastos.detectar_gastos_recorrentes, ve-se pelo
-- HISTORICO do extrato bancario/gastos) e o limite manual do cartao
-- (bank_accounts.limite, US-E15). Relacao completa em
-- docs/contrato-assinaturas.md ("Relacao com o que ja existe").
--
-- `assinatura`: um compromisso mensal declarado (nome, valor, dia de
-- cobranca) - nasce de "assinei o Spotify por 21,90" no classificador local
-- (classificador_local/regras/n1_financas.py) ou do formulario da aba
-- Financeiro. `cartao_ou_forma` e texto livre (ex: "nubank", "pix", "debito
-- automatico") - quando bate com o nome de uma bank_accounts (tipo='cartao'),
-- financas_recorrentes.py usa isso pra calcular o impacto no limite; quando
-- nao bate, o valor so entra no total comprometido, sem cartao associado.
CREATE TABLE IF NOT EXISTS assinatura (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    valor REAL NOT NULL,
    dia_cobranca INTEGER NOT NULL CHECK (dia_cobranca BETWEEN 1 AND 31),
    cartao_ou_forma TEXT,
    categoria TEXT,
    ativa INTEGER NOT NULL DEFAULT 1,
    inicio TEXT NOT NULL,
    observacao TEXT,
    cancelada_em TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assinatura_ativa ON assinatura (ativa);

-- `compra_parcelada`: uma compra feita em N vezes. `parcela_atual` e so
-- informativo/editavel a mao (ex: importar uma compra que ja estava na
-- parcela 4); o numero CANONICO usado nos calculos e sempre recalculado a
-- partir de `primeira_parcela` + `n_parcelas` + a data de hoje
-- (financas_recorrentes.parcela_info), pra nunca depender de um job
-- mensal incrementando essa coluna (se ele atrasar ou nao existir ainda,
-- o calculo por data continua certo).
CREATE TABLE IF NOT EXISTS compra_parcelada (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor_total REAL NOT NULL,
    n_parcelas INTEGER NOT NULL CHECK (n_parcelas > 0),
    parcela_atual INTEGER NOT NULL DEFAULT 1,
    valor_parcela REAL NOT NULL,
    cartao TEXT,
    primeira_parcela TEXT NOT NULL,
    categoria TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_compra_parcelada_primeira ON compra_parcelada (primeira_parcela);
