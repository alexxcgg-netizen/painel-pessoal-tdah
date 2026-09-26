"""assistente/gatilhos/p9_memoria.py — faixa P9 (memoria viva), Fase 7.

Tarefa periodica (`executar(conn, agora)`, carregada sozinha pelo tick -
ver fase7-assistente.md) que roda 1x por semana, domingo a noite, e
enfileira na Caixa uma proposta por fato relevante que `assistente.
memoria_viva` detectou. `ao_resolver` aplica a memoria quando o Alex aceita,
e guarda a recusa (pra nao repropor a mesma coisa por 8 semanas) quando ele
recusa.

Infra da P1a (`assistente/caixa.py` com `enfileirar`/`resolver`) ainda nao
esta integrada nesta branch - por isso o import e tardio (`_caixa()`, so
dentro da funcao) e os testes mockam `_caixa()` em vez de `assistente.
caixa` (ver fase7-regras-faixa.md: "faixas que so consomem importam de
forma tardia... nos testes usam unittest.mock.patch" - aqui o mock troca a
propria funcao de obtencao, ja que o modulo real ainda nao existe pra
patch.object apontar).

Nota de integracao pra quem mexer no dispatch de `ao_resolver` na P1a: o
contrato diz "o prefixo e o texto de origem antes do `_`", com o exemplo
"p2_conta:123" -> prefixo "p2". Esta faixa te, porem, o nome de arquivo
fixado no prompt como `p9_memoria.py` (com "_" no meio) - a origem aqui usa
"p9_memoria:<chave>" (prefixo = tudo antes do primeiro ":", nao do "_").
Se o dispatch real da P1a cortar estritamente no primeiro "_", vai bater em
"p9.py" em vez deste arquivo; ajustar o dispatch (ou trocar a origem aqui
pra "p9:memoria:<chave>") quando a P1a integrar - anotado em
`scripts/ralph-p9-memoria/APRENDIZADOS.md`.

Toda a informacao pra aplicar uma proposta aceita (acao, memoria_id, texto,
categoria) fica guardada AQUI (tabela `p9_memoria_propostas`), nao no item
da Caixa - assim este modulo so depende do que o contrato garante (`item
["origem"]` e o parametro `resposta`), nunca do formato interno do item da
P1a. As tabelas (`p9_memoria_propostas`, `p9_memoria_recusas`) sao criadas
sob demanda (`CREATE TABLE IF NOT EXISTS`) porque a infra de migracao
automatica (`migracoes/*.sql` aplicado sozinho) tambem ainda nao esta
integrada - o `.sql` equivalente existe em `migracoes/` pra quando ela
chegar (aplica-lo de novo depois e inofensivo, e so `IF NOT EXISTS`)."""

import logging
from datetime import datetime, timedelta

import db
from assistente import memoria_viva

log = logging.getLogger(__name__)

FLAG_ATIVO = "assistente.p9_memoria.ativo"
CHAVE_ULTIMA_SEMANA = "assistente.p9_memoria.ultima_semana"
DIAS_SEM_REPROPOR = 56  # 8 semanas

_SQL_TABELAS = """
CREATE TABLE IF NOT EXISTS p9_memoria_propostas (
    chave TEXT PRIMARY KEY,
    acao TEXT NOT NULL,
    memoria_id INTEGER,
    texto TEXT NOT NULL,
    categoria TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS p9_memoria_recusas (
    chave TEXT PRIMARY KEY,
    texto TEXT,
    recusado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _garantir_tabelas(conn) -> None:
    conn.executescript(_SQL_TABELAS)
    conn.commit()


def _caixa():
    """Import tardio (infra da P1a) - isolado numa funcao pra os testes
    poderem trocar so isto por um dublê, sem precisar que `assistente.
    caixa` exista de verdade nesta branch."""
    from assistente import caixa
    return caixa


def _flag_ativa(conn) -> bool:
    # Padrao ligado (fase7-assistente.md): so desliga se alguem gravou "0".
    return db.obter_configuracao(conn, FLAG_ATIVO) != "0"


def _semana_iso(agora: datetime) -> str:
    ano, semana, _ = agora.isocalendar()
    return f"{ano}-W{semana:02d}"


def _ja_rodou_essa_semana(conn, semana: str) -> bool:
    return db.obter_configuracao(conn, CHAVE_ULTIMA_SEMANA) == semana


def _marcar_rodou(conn, semana: str) -> None:
    db.definir_configuracao(conn, CHAVE_ULTIMA_SEMANA, semana)


def _recusas_recentes(conn, agora: datetime, dias: int = DIAS_SEM_REPROPOR) -> set[str]:
    _garantir_tabelas(conn)
    limite = (agora - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT chave FROM p9_memoria_recusas WHERE recusado_em >= ?", (limite,)
    ).fetchall()
    return {r["chave"] for r in rows}


def _titulo_e_corpo(proposta: dict) -> tuple[str, str]:
    if proposta["acao"] == "adicionar":
        return "Adicionar a 'O que eu lembro sobre você'?", proposta["texto"]
    if proposta["acao"] == "alterar":
        return "Atualizar uma memória existente?", proposta["texto"]
    return "Remover uma memória desatualizada?", proposta["texto"]


def executar(conn, agora: datetime) -> None:
    """Roda 1x por semana, domingo a partir das 19h (mesma janela que o
    resto do app ja usa pra tarefa semanal - ver app.py `agora.weekday() ==
    6 and agora.hour >= 19`). Idempotente por semana ISO: mesmo que o tick
    rode de novo dentro da mesma janela, so gera as propostas (e chama IA)
    uma vez por semana - `chave_unica` no `enfileirar` cobre o caso raro de
    reinicio no meio da rodada."""
    if not _flag_ativa(conn):
        return
    if not (agora.weekday() == 6 and agora.hour >= 19):
        return
    semana = _semana_iso(agora)
    if _ja_rodou_essa_semana(conn, semana):
        return

    _garantir_tabelas(conn)
    recusas = _recusas_recentes(conn, agora)
    propostas = memoria_viva.gerar_propostas_da_semana(conn, agora, recusas_recentes=recusas)

    if propostas:
        caixa = _caixa()
        for proposta in propostas:
            conn.execute(
                "INSERT INTO p9_memoria_propostas (chave, acao, memoria_id, texto, categoria) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET acao=excluded.acao, memoria_id=excluded.memoria_id, "
                "texto=excluded.texto, categoria=excluded.categoria, criado_em=datetime('now')",
                (proposta["chave"], proposta["acao"], proposta["memoria_id"], proposta["texto"],
                 proposta["categoria"]),
            )
            conn.commit()
            titulo, corpo = _titulo_e_corpo(proposta)
            caixa.enfileirar(
                tipo="proposta_memoria",
                titulo=titulo,
                corpo=corpo,
                opcoes=["aceitar", "recusar"],
                origem=f"p9_memoria:{proposta['chave']}",
                chave_unica=f"p9:{semana}:{proposta['chave']}",
            )

    _marcar_rodou(conn, semana)


def ao_resolver(conn, item: dict, resposta: str, texto: str = "") -> None:
    """Chamado pela P1a quando o Alex responde ao item (`item["origem"]`
    comeca com "p9_memoria:"). 'aceitar' aplica a memoria com as funcoes
    existentes de `db.py` (create_memoria/update_memoria/delete_memoria);
    'recusar' so registra (pra nao repropor por 8 semanas) - o texto nunca
    muda sozinho fora do aceite explicito."""
    origem = (item or {}).get("origem") if isinstance(item, dict) else None
    if not isinstance(origem, str) or not origem.startswith("p9_memoria:"):
        return
    chave = origem.split(":", 1)[1]
    if not chave:
        return

    _garantir_tabelas(conn)
    row = conn.execute("SELECT * FROM p9_memoria_propostas WHERE chave = ?", (chave,)).fetchone()

    if resposta == "recusar":
        texto_guardado = row["texto"] if row else ""
        conn.execute(
            "INSERT INTO p9_memoria_recusas (chave, texto) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET texto=excluded.texto, recusado_em=datetime('now')",
            (chave, texto_guardado),
        )
        if row:
            conn.execute("DELETE FROM p9_memoria_propostas WHERE chave = ?", (chave,))
        conn.commit()
        return

    if resposta != "aceitar" or row is None:
        return

    proposta = dict(row)
    if proposta["acao"] == "adicionar":
        db.create_memoria(conn, proposta["texto"], source_text="p9_memoria_viva",
                           categoria=proposta["categoria"])
    elif proposta["acao"] == "alterar" and proposta["memoria_id"] is not None:
        db.update_memoria(conn, proposta["memoria_id"], proposta["texto"])
    elif proposta["acao"] == "remover" and proposta["memoria_id"] is not None:
        db.delete_memoria(conn, proposta["memoria_id"])
    else:
        log.warning("p9_memoria: proposta aceita mas sem acao valida (chave %s)", chave)

    conn.execute("DELETE FROM p9_memoria_propostas WHERE chave = ?", (chave,))
    conn.commit()
