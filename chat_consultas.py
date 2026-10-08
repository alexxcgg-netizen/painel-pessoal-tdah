"""Consultas de leitura do chat (tarefas, gastos, agenda) - "fonte unica":
o chat so pode falar da vida do Alex com o que o painel tem, entao estas
ferramentas deixam a IA buscar o dado de verdade em vez de responder de
memoria/estimativa.

Cada funcao recebe `conn` (e ganchos opcionais pra nao importar `app`, que
importa este modulo) e NUNCA levanta excecao pra fora: entrada maluca ou falha
interna viram `{"erro": "..."}`. Nao grava nada (a unica escrita e a
materializacao idempotente de recorrentes, que o resto do painel ja faz ao
abrir a lista de tarefas).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import aprendizado

log = logging.getLogger(__name__)

LIMITE_TAREFAS = 30
LIMITE_ATRASADAS = 10
LIMITE_EVENTOS_AGENDA = 40
PERIODO_MAX_DIAS = 400

ERRO_DATA = {"erro": "data invalida, use AAAA-MM-DD"}
ERRO_GENERICO = {"erro": "nao consegui consultar agora"}

_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STATUS_TAREFAS = {"pendentes", "concluidas", "todas"}


class _EntradaInvalida(Exception):
    def __init__(self, erro: dict):
        super().__init__(erro.get("erro"))
        self.erro = erro


def _parse_dia(valor) -> date | None:
    """AAAA-MM-DD estrito (date.fromisoformat aceita formatos alternativos)."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not _RE_DATA.match(texto):
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _opcional(valor) -> bool:
    """None ou string vazia = "nao informado"."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _dia_ou_padrao(valor, padrao: date) -> date:
    if _opcional(valor):
        return padrao
    dia = _parse_dia(valor)
    if dia is None:
        raise _EntradaInvalida(ERRO_DATA)
    return dia


def _validar_periodo(de: date, ate: date) -> None:
    if de > ate:
        raise _EntradaInvalida({"erro": "periodo invalido: 'de' vem depois de 'ate'"})
    if (ate - de).days + 1 > PERIODO_MAX_DIAS:
        raise _EntradaInvalida({"erro": f"periodo grande demais (maximo {PERIODO_MAX_DIAS} dias)"})


def _entrada_dict(entrada) -> dict:
    return entrada if isinstance(entrada, dict) else {}


# --------------------------------------------------------------------------
# consultar_tarefas
# --------------------------------------------------------------------------

_SEM_MODELO = "NOT (recorrencia IS NOT NULL AND due_date IS NULL)"


def _item_tarefa(r) -> dict:
    return {
        "titulo": r["title"],
        "data": r["due_date"],
        "hora": r["hora"],
        "concluida_em": (r["completed_at"] or "")[:16] or None,
    }


def consultar_tarefas(conn, entrada, materializar=None, hoje: date | None = None) -> dict:
    try:
        entrada = _entrada_dict(entrada)
        hoje = hoje or date.today()
        if _opcional(entrada.get("de")) and not _opcional(entrada.get("ate")):
            ate = _dia_ou_padrao(entrada.get("ate"), hoje)
            de = min(hoje, ate)
        else:
            de = _dia_ou_padrao(entrada.get("de"), hoje)
            ate = _dia_ou_padrao(entrada.get("ate"), max(hoje, de))
        _validar_periodo(de, ate)

        status_bruto = entrada.get("status")
        if _opcional(status_bruto):
            status = "pendentes"
        else:
            status = aprendizado.normalizar_consulta(status_bruto) if isinstance(status_bruto, str) else ""
            if status in ("pendente", "abertas"):
                status = "pendentes"
            elif status in ("concluida", "feitas", "feita"):
                status = "concluidas"
            if status not in _STATUS_TAREFAS:
                return {"erro": "status invalido, use pendentes, concluidas ou todas"}

        if callable(materializar) and de <= hoje <= ate:
            try:
                materializar(conn)
            except Exception:  # noqa: BLE001
                log.exception("chat_consultas: falha ao materializar recorrentes")

        de_s, ate_s = de.isoformat(), ate.isoformat()
        cond_pend = "(completed_at IS NULL AND due_date BETWEEN ? AND ?)"
        cond_conc = "(completed_at IS NOT NULL AND (due_date BETWEEN ? AND ? OR substr(completed_at, 1, 10) BETWEEN ? AND ?))"
        if status == "pendentes":
            where, params = cond_pend, [de_s, ate_s]
        elif status == "concluidas":
            where, params = cond_conc, [de_s, ate_s, de_s, ate_s]
        else:
            where, params = f"({cond_pend} OR {cond_conc})", [de_s, ate_s, de_s, ate_s, de_s, ate_s]

        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM tasks WHERE {_SEM_MODELO} AND {where}", params
        ).fetchone()["n"]
        rows = conn.execute(
            "SELECT title, due_date, hora, completed_at FROM tasks "
            f"WHERE {_SEM_MODELO} AND {where} "
            "ORDER BY COALESCE(due_date, substr(completed_at, 1, 10)), hora IS NULL, hora, id LIMIT ?",
            params + [LIMITE_TAREFAS],
        ).fetchall()

        resultado = {
            "periodo": {"de": de_s, "ate": ate_s},
            "status": status,
            "total": total,
            "tarefas": [_item_tarefa(r) for r in rows],
        }
        if total > len(rows):
            resultado["obs"] = f"mostrando as primeiras {len(rows)} de {total}"
        if status in ("pendentes", "todas"):
            # total de pendentes em QUALQUER data (o "total" acima so conta o periodo pedido)
            resultado["pendentes_total_geral"] = conn.execute(
                f"SELECT COUNT(*) AS n FROM tasks WHERE {_SEM_MODELO} AND completed_at IS NULL"
            ).fetchone()["n"]

        if de == ate == hoje and status in ("pendentes", "todas"):
            hoje_s = hoje.isoformat()
            atrasadas_total = conn.execute(
                f"SELECT COUNT(*) AS n FROM tasks WHERE {_SEM_MODELO} AND completed_at IS NULL AND due_date < ?",
                (hoje_s,),
            ).fetchone()["n"]
            atrasadas = conn.execute(
                "SELECT title, due_date, hora, completed_at FROM tasks "
                f"WHERE {_SEM_MODELO} AND completed_at IS NULL AND due_date < ? "
                "ORDER BY due_date, hora IS NULL, hora, id LIMIT ?",
                (hoje_s, LIMITE_ATRASADAS),
            ).fetchall()
            resultado["atrasadas_total"] = atrasadas_total
            resultado["atrasadas"] = [_item_tarefa(r) for r in atrasadas]
        return resultado
    except _EntradaInvalida as e:
        return dict(e.erro)
    except Exception:  # noqa: BLE001
        log.exception("chat_consultas.consultar_tarefas")
        return dict(ERRO_GENERICO)


# --------------------------------------------------------------------------
# consultar_gastos
# --------------------------------------------------------------------------


def consultar_gastos(conn, entrada, hoje: date | None = None) -> dict:
    """Mesma fonte da aba Financas (rotas.f9_financas): manual + banco, so
    saida real, sem transferencia/pagamento de fatura."""
    try:
        entrada = _entrada_dict(entrada)
        hoje = hoje or date.today()
        de = _dia_ou_padrao(entrada.get("de"), hoje.replace(day=1))
        ate = _dia_ou_padrao(entrada.get("ate"), max(hoje, de))
        _validar_periodo(de, ate)

        categoria = entrada.get("categoria")
        termo = aprendizado.normalizar_consulta(categoria)[:80] if isinstance(categoria, str) else ""

        from rotas import f9_financas  # import tardio: evita ciclo com app

        linhas = f9_financas.linhas_saida_real(conn, de, ate)
        categorias_no_periodo = sorted({l["categoria"] for l in linhas})
        if termo:
            # casa pela categoria OU pelo nome do gasto (ex.: "netflix", "mercado")
            linhas = [
                l for l in linhas
                if termo in aprendizado.normalizar_consulta(l["categoria"])
                or termo in aprendizado.normalizar_consulta(l.get("descricao") or "")
            ]

        por_cat: dict[str, float] = {}
        for l in linhas:
            por_cat[l["categoria"]] = por_cat.get(l["categoria"], 0.0) + (-l["valor"])
        top_cat = sorted(
            ({"categoria": c, "valor": round(v, 2)} for c, v in por_cat.items()),
            key=lambda i: i["valor"], reverse=True,
        )[:8]
        maiores = sorted(linhas, key=lambda l: l["valor"])[:5]  # valor negativo: menor = maior gasto

        resultado = {
            "periodo": {"de": de.isoformat(), "ate": ate.isoformat()},
            "total": round(sum(-l["valor"] for l in linhas), 2),
            "quantidade": len(linhas),
            "por_categoria": top_cat,
            "maiores": [
                {"data": l["data"], "descricao": l["descricao"], "categoria": l["categoria"],
                 "valor": round(-l["valor"], 2)}
                for l in maiores
            ],
            "obs": "gasto real (manual + banco), sem pagamento de fatura e transferencia",
        }
        if termo:
            resultado["categoria_filtrada"] = str(categoria).strip()[:80]
            if not linhas:
                resultado["categorias_no_periodo"] = categorias_no_periodo[:20]
        return resultado
    except _EntradaInvalida as e:
        return dict(e.erro)
    except Exception:  # noqa: BLE001
        log.exception("chat_consultas.consultar_gastos")
        return dict(ERRO_GENERICO)


# --------------------------------------------------------------------------
# consultar_agenda
# --------------------------------------------------------------------------


def _hhmm(iso: str | None) -> str | None:
    if not isinstance(iso, str) or "T" not in iso:
        return None
    return iso.split("T", 1)[1][:5]


def consultar_agenda(conn, entrada, eventos_icloud=None, hoje: date | None = None) -> dict:
    """Compromissos de um dia: eventos do iCloud (`eventos_icloud(dia)`, gancho
    que pode levantar excecao ou devolver None) + tarefas com hora marcada."""
    try:
        entrada = _entrada_dict(entrada)
        hoje = hoje or date.today()
        dia = _dia_ou_padrao(entrada.get("dia"), hoje)
        dia_s = dia.isoformat()

        itens: list[dict] = []
        status_icloud = "nao configurado"
        if eventos_icloud is not None:
            try:
                eventos = eventos_icloud(dia)
                status_icloud = "ok"
            except Exception:  # noqa: BLE001
                eventos, status_icloud = [], "indisponivel agora"
            for e in eventos or []:
                if not isinstance(e, dict):
                    continue
                inteiro = bool(e.get("dia_inteiro"))
                itens.append({
                    "hora": None if inteiro else _hhmm(e.get("inicio")),
                    "ate": None if inteiro else _hhmm(e.get("fim")),
                    "titulo": e.get("titulo"),
                    "origem": "calendario",
                    "dia_inteiro": inteiro,
                })

        rows = conn.execute(
            "SELECT title, hora, completed_at FROM tasks "
            "WHERE due_date = ? AND hora IS NOT NULL AND hora != '' "
            f"AND {_SEM_MODELO} ORDER BY hora, id",
            (dia_s,),
        ).fetchall()
        for r in rows:
            itens.append({
                "hora": r["hora"], "ate": None, "titulo": r["title"], "origem": "tarefa",
                "dia_inteiro": False, "concluida": r["completed_at"] is not None,
            })
        sem_hora_rows = conn.execute(
            f"SELECT title FROM tasks WHERE due_date = ? AND completed_at IS NULL "
            f"AND (hora IS NULL OR hora = '') AND {_SEM_MODELO} ORDER BY id",
            (dia_s,),
        ).fetchall()
        sem_hora = len(sem_hora_rows)

        # dia inteiro primeiro, depois por hora
        itens.sort(key=lambda i: (i["hora"] is not None, i["hora"] or ""))
        total = len(itens)
        return {
            "dia": dia_s,
            "total": total,
            "compromissos": itens[:LIMITE_EVENTOS_AGENDA],
            "tarefas_pendentes_sem_hora": sem_hora,
            "tarefas_sem_hora": [r["title"] for r in sem_hora_rows[:LIMITE_EVENTOS_AGENDA]],
            "eventos_icloud": status_icloud,
        }
    except _EntradaInvalida as e:
        return dict(e.erro)
    except Exception:  # noqa: BLE001
        log.exception("chat_consultas.consultar_agenda")
        return dict(ERRO_GENERICO)


# --------------------------------------------------------------------------
# consultar_voos
# --------------------------------------------------------------------------


def consultar_voos(conn, entrada, hoje: date | None = None) -> dict:
    """Diario de voo (tabela voos): total de horas, ultimos voos e voos futuros."""
    try:
        entrada = _entrada_dict(entrada)
        hoje = hoje or date.today()
        rows = conn.execute("SELECT data, origem, destino, horas, observacao FROM voos ORDER BY data DESC, id DESC").fetchall()
        voos = [
            {"data": r["data"], "origem": r["origem"], "destino": r["destino"],
             "horas": r["horas"], "observacao": r["observacao"]}
            for r in rows
        ]
        hoje_s = hoje.isoformat()
        futuros = [v for v in voos if (v["data"] or "") > hoje_s]
        passados = [v for v in voos if (v["data"] or "") <= hoje_s]
        return {
            "total_voos": len(passados),
            "total_horas": round(sum(float(v["horas"] or 0) for v in passados), 2),
            "ultimos_voos": passados[:5],
            "proximos_voos": sorted(futuros, key=lambda v: v["data"])[:5],
            "obs": "diario de voo do painel (voos registrados); sem voo futuro registrado = lista vazia",
        }
    except _EntradaInvalida as e:
        return dict(e.erro)
    except Exception:  # noqa: BLE001
        log.exception("chat_consultas.consultar_voos")
        return dict(ERRO_GENERICO)
