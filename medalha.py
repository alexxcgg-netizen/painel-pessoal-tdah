"""Medalha na hora (lab v4, 2026-10-30, ideia aprovada pelo Alex): no treino ao vivo, quando o
exercicio marcado bate o recorde de carga, cai uma medalha ali mesmo.

Recorde = 1RM estimado (Epley: kg x (1 + reps/30)) maior que o de TODAS as marcas anteriores do
mesmo exercicio. A "serie" aqui e o que a ficha diz (carga e reps do exercicio na hora da marca) -
o treino ao vivo marca o exercicio, nao serie a serie. Faixa de reps ("8-12") vale o piso (8).

  - Sem historico do exercicio (primeira marca): grava a base e NAO dá medalha (nao ha o que bater),
    a nao ser que a carga ja tenha mudado na ficha (treino_cargas): ai o maior kg anterior vira base.
  - Carga que nao e kg ("3 placas"), exercicio sem reps ou com mais de 15 reps: nao entra.
  - Desmarcar apaga a marca; marcar de novo reavalia (a medalha pode voltar).
  - A medalha fica gravada na linha (`recorde = 1`) e volta no card do historico.

Tabela `treino_marcas` (migracoes/202610301000_fch_fechamento.sql). Funcoes puras de formula em
`treino_vivo.py`.
"""

from __future__ import annotations

import treino_vivo
import vida

EPSILON = 0.05  # 1RM e arredondado em 0,1: empate nao e recorde


def _kg(carga: str) -> float | None:
    if "kg" not in (carga or "").lower():
        return None
    kg = treino_vivo.numero_da_carga(carga)
    return kg if kg and kg > 0 else None


def _base_anterior(conn, sessao_id: int, chave: str, reps: int, data: str) -> float | None:
    """Maior 1RM ja marcado desse exercicio (fora a sessao de agora); sem marca nenhuma, usa a maior
    carga que a ficha ja teve antes de hoje (treino_cargas) com as reps de agora."""
    r = conn.execute(
        "SELECT MAX(rm_est) AS m FROM treino_marcas WHERE exercicio = ? AND sessao_id != ?", (chave, sessao_id)
    ).fetchone()
    if r and r["m"] is not None:
        return float(r["m"])
    r = conn.execute(
        "SELECT MAX(carga_num) AS m FROM treino_cargas WHERE exercicio = ? AND data < ?", (chave, data)
    ).fetchone()
    if r and r["m"] is not None:
        return treino_vivo.rm_epley(float(r["m"]), reps)
    return None


def marcar(conn, sessao: dict, ficha: dict | None, idx: int, feito: bool) -> dict | None:
    """Chamado a cada caixinha. Devolve a medalha {i, nome, rm, anterior, ganho, carga, reps}
    quando ESTA marca bateu o recorde; None caso contrario. Faz commit."""
    conn.execute("DELETE FROM treino_marcas WHERE sessao_id = ? AND idx = ?", (sessao["id"], idx))
    medalha = None
    exs = treino_vivo.exercicios_da_ficha(ficha["exercicios"]) if ficha else []
    if feito and 0 <= idx < len(exs):
        ex = exs[idx]
        kg = _kg(ex["carga"])
        reps = treino_vivo.reps_da_serie(ex["reps"])
        if kg and reps and reps <= treino_vivo.REPS_MAX_PRA_1RM:
            chave = vida.normalizar_nome(ex["nome"])
            rm = treino_vivo.rm_epley(kg, reps)
            anterior = _base_anterior(conn, sessao["id"], chave, reps, sessao["data"])
            recorde = anterior is not None and rm > anterior + EPSILON
            series = treino_vivo.series_da_ficha(ex["series"])
            conn.execute(
                "INSERT INTO treino_marcas (sessao_id, idx, ficha_id, exercicio, nome, data, carga_kg, series, reps, "
                "volume_kg, rm_est, rm_anterior, recorde) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sessao["id"], idx, sessao["ficha_id"], chave, ex["nome"], sessao["data"], kg, series, reps,
                 round(kg * reps * (series or 1), 1), rm, anterior, 1 if recorde else 0),
            )
            if recorde:
                medalha = _dict(ex["nome"], idx, rm, anterior, kg, reps)
    conn.commit()
    return medalha


def _dict(nome: str, idx: int, rm: float, anterior: float | None, kg: float, reps: int) -> dict:
    return {
        "i": idx, "nome": nome, "rm": rm,
        "anterior": anterior, "ganho": round(rm - anterior, 1) if anterior is not None else None,
        "carga": kg, "reps": reps,
    }


def medalhas_da_sessao(conn, sessao_id: int) -> list[dict]:
    return [
        _dict(r["nome"], r["idx"], r["rm_est"], r["rm_anterior"], r["carga_kg"], r["reps"])
        for r in conn.execute(
            "SELECT * FROM treino_marcas WHERE sessao_id = ? AND recorde = 1 ORDER BY idx", (sessao_id,)
        )
    ]


def legenda(m: dict) -> str:
    """'+3 kg no 1RM estimado. 72,5 x (1 + 8/30) = 91,8.' - a conta aparece pra ele conferir."""
    def n(v):
        return f"{v:g}".replace(".", ",")

    ganho = f"+{n(m['ganho'])} kg no 1RM estimado. " if m.get("ganho") is not None else ""
    return f"{ganho}{n(m['carga'])} × (1 + {m['reps']}/30) = {n(m['rm'])}."
