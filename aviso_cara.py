"""Aviso que muda de cara (leva Lab v4, ideia "aviso-cara", 30/10/2026).

O aviso continua INSISTINDO igual (os minutos e as repeticoes de `notificacoes.INSISTENCIA` nao mudam -
os avisos ajudam no TDAH, nada de reduzir). O que muda e o TEXTO a cada vez, pra nao virar paisagem:

  - direto:  o texto de sempre;
  - humor:   uma frase leve, sem cobranca;
  - porque:  um fato real (passou X min do horario, esta ha N dias na lista) ou o ganho de fazer agora;
  - passo:   o proximo passo concreto (proxima subtarefa; senao "so o primeiro passo, 2 minutos").

Aprende com o uso: cada envio guarda a cara usada (`aviso_cara_envios`); tocar em Feito (no proprio aviso, na
tarefa ou no app) marca aquela cara como "funcionou". Na hora de escolher, as caras que mais levaram a Feito
pesam mais (com piso, pra nao travar numa so). Sem chamada de IA: template + fato do banco (custo zero, e nenhum
fato inventado). O primeiro envio do dia so troca de cara quando o MESMO aviso ja saiu em outro dia (tarefa
recorrente, tipo a creatina) - senao fica o texto normal.

Desligar tudo: configuracao `aviso_cara_ligado` = "0" (padrao ligado).
"""

from __future__ import annotations

import random
from datetime import date, datetime

import db

ROSTOS = ("direto", "humor", "porque", "passo")
# tipos cujo referencia_id e o id da tarefa (mesmo conjunto de notificacoes.INSISTENCIA_DE_TAREFA, mais o aviso
# de horario passado): os fatos do banco so valem pra eles
TIPOS_DE_TAREFA = ("tarefa_horario", "se_arrumar", "hora_de_sair", "tarefa_horario_passou")
PISO_PESO = 0.15  # nenhuma cara some de vez: o gosto dele muda
CONFIG_LIGADO = "aviso_cara_ligado"

HUMOR_TAREFA = (
    "{nome} continua te esperando. Educada, mas insistente.",
    "Eu de novo. {nome}, lembra dela?",
    "Se {nome} tivesse pernas, já tinha vindo até ti.",
)
HUMOR_GERAL = (
    "Sei que é chato, mas é rapidinho.",
    "Eu insisto porque gosto de ti.",
    "Prometo parar assim que tu tocar em Feito.",
)
PORQUE_GERAL = (
    "Fazer agora tira isso da cabeça.",
    "Quanto antes, menos pesa.",
)


def criar_tabela(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS aviso_cara_envios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL,
            tipo TEXT NOT NULL,
            referencia_id INTEGER NOT NULL DEFAULT 0,
            rosto TEXT NOT NULL,
            repeticao INTEGER NOT NULL DEFAULT 0,
            enviado_em TEXT NOT NULL,
            resolvido_em TEXT,
            resolvido_por TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_aviso_cara_tag ON aviso_cara_envios (tag, id)")


def ligado(conn) -> bool:
    return (db.obter_configuracao(conn, CONFIG_LIGADO) or "1") != "0"


# ---------------------------------------------------------------- aprendizado


def desempenho(conn, tipo: str | None = None) -> dict[str, dict]:
    """{rosto: {envios, feitos, toques}} - o que o painel aprendeu. `tipo` restringe a um tipo de aviso."""
    criar_tabela(conn)
    sql = "SELECT rosto, COUNT(*) n, SUM(resolvido_por = 'feito') f, SUM(resolvido_por = 'toque') t FROM aviso_cara_envios"
    args: tuple = ()
    if tipo:
        sql += " WHERE tipo = ?"
        args = (tipo,)
    out = {r: {"envios": 0, "feitos": 0, "toques": 0} for r in ROSTOS}
    for linha in conn.execute(sql + " GROUP BY rosto", args).fetchall():
        if linha["rosto"] in out:
            out[linha["rosto"]] = {"envios": linha["n"], "feitos": linha["f"] or 0, "toques": linha["t"] or 0}
    return out


def pesos(conn, tipo: str | None = None) -> dict[str, float]:
    """Peso de cada cara: taxa suavizada de Feito (toque conta meio), com piso."""
    d = desempenho(conn, tipo)
    saida = {}
    for rosto in ROSTOS:
        e = d[rosto]
        taxa = (e["feitos"] + 0.5 * e["toques"] + 1) / (e["envios"] + 2)
        saida[rosto] = max(PISO_PESO, taxa)
    return saida


def escolher_rosto(conn, tipo: str, tag: str, repeticao: int, hoje: date) -> str:
    """Sorteio ponderado, deterministico por (tag, dia, repeticao). Nao repete a cara que ja saiu hoje nesse
    mesmo aviso (enquanto sobrar alguma)."""
    criar_tabela(conn)
    usadas = {
        r["rosto"]
        for r in conn.execute(
            "SELECT rosto FROM aviso_cara_envios WHERE tag = ? AND substr(enviado_em, 1, 10) = ?",
            (tag, hoje.isoformat()),
        ).fetchall()
    }
    candidatas = [r for r in ROSTOS if r not in usadas] or list(ROSTOS)
    p = pesos(conn, tipo)
    rng = random.Random(f"{tag}|{hoje.isoformat()}|{repeticao}")
    return rng.choices(candidatas, weights=[p[r] for r in candidatas], k=1)[0]


def registrar_envio(conn, tag: str, tipo: str, referencia_id: int, rosto: str, repeticao: int, agora: datetime) -> None:
    criar_tabela(conn)
    conn.execute(
        "INSERT INTO aviso_cara_envios (tag, tipo, referencia_id, rosto, repeticao, enviado_em) VALUES (?, ?, ?, ?, ?, ?)",
        (tag, tipo, referencia_id, rosto, repeticao, agora.isoformat(timespec="seconds")),
    )
    conn.commit()


def resolver(conn, tag: str, por: str, agora: datetime | None = None) -> int:
    """O aviso da `tag` foi respondido ('feito' ou 'toque'): a ULTIMA cara enviada leva o credito.
    Um 'feito' depois de um 'toque' promove (o toque so abriu; o Feito e o que importa)."""
    criar_tabela(conn)
    agora = agora or datetime.now()
    ultimo = conn.execute(
        "SELECT id, resolvido_por FROM aviso_cara_envios WHERE tag = ? ORDER BY id DESC LIMIT 1", (tag,)
    ).fetchone()
    if not ultimo or (ultimo["resolvido_por"] == "feito") or (ultimo["resolvido_por"] and por == "toque"):
        return 0
    conn.execute(
        "UPDATE aviso_cara_envios SET resolvido_em = ?, resolvido_por = ? WHERE id = ?",
        (agora.isoformat(timespec="seconds"), por, ultimo["id"]),
    )
    conn.commit()
    return 1


def tarefa_concluida(conn, task_id: int, agora: datetime | None = None) -> int:
    """Concluiu a tarefa (no app, no chat ou no botao do aviso): a ultima cara de cada aviso dela leva o Feito."""
    criar_tabela(conn)
    tags = [
        r["tag"]
        for r in conn.execute(
            "SELECT DISTINCT tag FROM aviso_cara_envios WHERE referencia_id = ? AND tipo IN (%s)"
            % ",".join("?" * len(TIPOS_DE_TAREFA)),
            (task_id, *TIPOS_DE_TAREFA),
        ).fetchall()
    ]
    return sum(resolver(conn, t, "feito", agora) for t in tags)


# ---------------------------------------------------------------- texto


def _min_ate(hora: str | None, agora: datetime) -> int | None:
    try:
        h, m = (hora or "").split(":")
        return int(agora.hour * 60 + agora.minute - (int(h) * 60 + int(m)))
    except (ValueError, TypeError):
        return None


def _fatos_tarefa(conn, task_id: int, agora: datetime) -> dict | None:
    t = conn.execute(
        "SELECT id, title, hora, due_date, created_at, completed_at FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not t or t["completed_at"]:
        return None
    sub = conn.execute(
        "SELECT title FROM subtasks WHERE task_id = ? AND completed_at IS NULL ORDER BY position, id LIMIT 1", (task_id,)
    ).fetchone()
    dias = None
    try:
        dias = (agora.date() - date.fromisoformat((t["created_at"] or "")[:10])).days
    except ValueError:
        pass
    atraso = _min_ate(t["hora"], agora) if t["due_date"] == agora.date().isoformat() else None
    return {"nome": t["title"], "hora": t["hora"], "atraso_min": atraso, "dias_na_lista": dias,
            "passo": sub["title"] if sub else None}


def _curto(texto: str, maximo: int = 60) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + "…"


def corpo_da_cara(rosto: str, corpo: str, fatos: dict | None, semente: int) -> str:
    """Texto do corpo do aviso na cara `rosto`. `fatos` so existe pra aviso de tarefa."""
    if rosto == "direto":
        return corpo
    if fatos:
        nome = _curto(fatos["nome"])
        if rosto == "humor":
            return HUMOR_TAREFA[semente % len(HUMOR_TAREFA)].format(nome=nome)
        if rosto == "porque":
            if fatos["atraso_min"] is not None and fatos["atraso_min"] >= 5:
                return f"{nome} era pras {fatos['hora']} e já passou {fatos['atraso_min']} min. Quanto antes, menos pesa."
            if fatos["dias_na_lista"] is not None and fatos["dias_na_lista"] >= 2:
                return f"{nome} está na tua lista há {fatos['dias_na_lista']} dias. Hoje dá pra tirar."
            return f"Fazer {nome} agora tira isso da cabeça."
        if rosto == "passo":
            if fatos["passo"]:
                return f"Próximo passo de {nome}: {_curto(fatos['passo'])}."
            return f"Só o primeiro passo de {nome}: abre e começa, 2 minutos já valem."
    if rosto == "humor":
        return f"{corpo} {HUMOR_GERAL[semente % len(HUMOR_GERAL)]}"
    if rosto == "porque":
        return f"{corpo} {PORQUE_GERAL[semente % len(PORQUE_GERAL)]}"
    return f"{corpo} Começa pelo primeiro passo, só 2 minutos."


def variar(conn, tipo: str, referencia_id: int, tag: str, titulo: str, corpo: str, repeticao: int,
           agora: datetime | None = None, so_se_repetiu_em_outro_dia: bool = False) -> tuple[str, str]:
    """(titulo, corpo) com a cara do envio, e registra qual cara saiu. Desligado ou erro = devolve igual.
    `repeticao` 0 = primeiro envio do dia (so troca de cara se `so_se_repetiu_em_outro_dia` e o mesmo aviso ja saiu
    antes); 1, 2... = reenvio da insistencia (sempre troca)."""
    try:
        if not ligado(conn):
            return titulo, corpo
        agora = agora or datetime.now()
        criar_tabela(conn)
        if repeticao == 0 and so_se_repetiu_em_outro_dia:
            ja = conn.execute(
                "SELECT 1 FROM avisos_insistentes WHERE tipo = ? AND corpo = ? AND data < ? LIMIT 1",
                (tipo, corpo, agora.date().isoformat()),
            ).fetchone()
            if not ja:
                registrar_envio(conn, tag, tipo, referencia_id, "direto", 0, agora)
                return titulo, corpo
        rosto = escolher_rosto(conn, tipo, tag, repeticao, agora.date())
        fatos = _fatos_tarefa(conn, referencia_id, agora) if tipo in TIPOS_DE_TAREFA and referencia_id else None
        semente = hash_estavel(f"{tag}|{agora.date().isoformat()}|{repeticao}")
        novo = corpo_da_cara(rosto, corpo, fatos, semente)
        registrar_envio(conn, tag, tipo, referencia_id, rosto, repeticao, agora)
        return titulo, novo
    except Exception:  # noqa: BLE001 - texto do aviso nunca pode derrubar o aviso
        import logging

        logging.getLogger(__name__).exception("aviso_cara falhou")
        return titulo, corpo


def hash_estavel(texto: str) -> int:
    """Hash que nao muda entre execucoes (hash() de str muda a cada processo)."""
    n = 0
    for ch in texto:
        n = (n * 131 + ord(ch)) % 1_000_003
    return n
