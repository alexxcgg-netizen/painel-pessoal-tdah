"""Diario do Alex: o que aconteceu em CADA dia (2026-10-12, pedido dele: "ele tem que saber que
o date foi ontem... saber o que aconteceu cada dia, ser muito organizado").

Problema que resolve: o chat mandava as ultimas 20 mensagens pra IA SEM data. O "date as 20h"
de sabado aparecia igual a uma mensagem de hoje, e na segunda a IA ainda lembrava ele do date.

Como fica:
- Cada dia que ja passou vira uma linha em `diario_dias`: fatos tirados do banco (tarefas feitas,
  tarefas que ficaram sem fazer, gastos, voos, treinos, notas) + um resumo curto da conversa daquele
  dia, escrito UMA vez pela IA (barato: so quando o dia fecha). Falhou a IA = fica so com os fatos e
  tenta de novo depois.
- O chat recebe "Diario dos ultimos dias", sempre com o nome do dia ("ontem, domingo 11/10"), e
  as mensagens antigas que ainda vao na integra chegam marcadas com a data (ver app._historico_chat_para_ia).
- A ferramenta `consultar_diario` deixa a IA abrir qualquer dia ("o que eu fiz sabado?").

Horarios: o banco grava `datetime('now')` (UTC); o dia aqui e SEMPRE o de Brasilia.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")
FUNCAO_IA = "diario_dia"
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
# quantos dias pra tras o contexto do chat mostra (o resto a IA abre com consultar_diario)
DIAS_NO_CONTEXTO = 3
# quantos dias pra tras o fechamento automatico olha (dia sem nada nao vira linha)
DIAS_PRA_FECHAR = 7

SISTEMA_DIARIO = """Voce escreve o DIARIO de um dia que JA PASSOU do Alex (assistente pessoal dele).
Recebe os fatos do banco daquele dia e o que o Alex escreveu/falou pro assistente naquele dia (com horario).

Escreva de 2 a 5 linhas curtas, em portugues, no passado, comecando cada uma com "- ":
- o que ele fez / o que aconteceu (compromissos, saidas, voo, trabalho, com quem);
- combinados e decisoes que continuam valendo depois desse dia;
- o que ficou em aberto pra frente (so se ainda faz sentido depois desse dia).
Compromisso daquele dia (date, buscar alguem, reuniao) e coisa do PASSADO: escreva como "teve date as 20h",
nunca como algo a fazer. So vale o que ele disse e os fatos do banco; nao deduza nada alem disso e use as
palavras dele (se ele disse "a menina", nao vire "namorada"). "anotacoes do alex" sao correcoes dele e
valem mais que o resto. Em aberto so entra pendencia da vida dele (ligar, comprar, resolver), nunca problema do painel ou do
assistente (modo visitante, ajuste de tela, erro). Nao invente nada. Sem saudacao, sem comentario, sem
valores da construtora. Dia sem nada relevante: uma linha so."""


def criar_tabela(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diario_dias (
            dia TEXT PRIMARY KEY,
            resumo TEXT,
            fatos_json TEXT NOT NULL,
            tentativas_ia INTEGER NOT NULL DEFAULT 0,
            gerado_em TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    # correcao/acrescimo que o Alex fez sobre um dia ("o date foi ontem") - vale mais que o resumo
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS diario_anotacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia TEXT NOT NULL,
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


# ---- datas ------------------------------------------------------------------

def hoje_local() -> date:
    return datetime.now(TZ).date()


def utc_para_local(texto: str | None) -> datetime | None:
    """'2026-10-12 19:29:27' (UTC do sqlite) -> datetime de Brasilia (sem tzinfo)."""
    if not texto:
        return None
    try:
        dt = datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return None
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ).replace(tzinfo=None)


def _faixa_utc(dia: date) -> tuple[str, str]:
    """[inicio, fim) do dia de Brasilia em texto UTC, pra comparar com colunas datetime('now')."""
    ini = datetime.combine(dia, time(0, 0), TZ).astimezone(ZoneInfo("UTC"))
    fim = ini + timedelta(days=1)
    return ini.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S")


def rotulo_dia(dia: date, hoje: date | None = None) -> str:
    """'hoje (segunda 12/10)', 'ontem (domingo 11/10)', 'sábado 10/10'."""
    hoje = hoje or hoje_local()
    base = f"{DIAS_SEMANA[dia.weekday()]} {dia:%d/%m}"
    if dia == hoje:
        return f"hoje ({base})"
    if dia == hoje - timedelta(days=1):
        return f"ontem ({base})"
    if dia == hoje - timedelta(days=2):
        return f"anteontem ({base})"
    return base


# ---- fatos do banco ---------------------------------------------------------

def _tabela_existe(conn, nome: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone())


def _hhmm(texto) -> str:
    dt = utc_para_local(texto)
    return f"{dt:%H:%M}" if dt else ""


def fatos_do_dia(conn, dia: date) -> dict:
    """So o que o banco sabe, sem IA. Chaves vazias somem."""
    ini, fim = _faixa_utc(dia)
    d = dia.isoformat()
    fatos: dict = {}

    # tarefa do dia marcada como feita de madrugada (voltou do date as 3h e marcou) conta no dia dela
    ini_6h = (datetime.fromisoformat(ini) + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    fim_6h = (datetime.fromisoformat(fim) + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    ontem = (dia - timedelta(days=1)).isoformat()
    feitas = conn.execute(
        "SELECT title, completed_at FROM tasks WHERE recorrencia IS NULL AND ("
        " (completed_at >= ? AND completed_at < ? AND NOT (due_date IS ? AND completed_at < ?))"
        " OR (completed_at >= ? AND completed_at < ? AND due_date = ?)"
        ") ORDER BY completed_at",
        (ini, fim, ontem, ini_6h, fim, fim_6h, d),
    ).fetchall()
    if feitas:
        fatos["tarefas_feitas"] = [
            r["title"] + (f" ({_hhmm(r['completed_at'])})" if r["completed_at"] < fim else "") for r in feitas
        ]

    nao_feitas = conn.execute(
        "SELECT title, hora FROM tasks WHERE due_date = ? AND recorrencia IS NULL "
        "AND (completed_at IS NULL OR completed_at >= ?) ORDER BY hora",
        # marcou como feita ate as 6h do dia seguinte (voltou do date e marcou) = foi feita no dia
        (d, (datetime.fromisoformat(fim) + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()
    if nao_feitas:
        fatos["tarefas_do_dia_nao_feitas"] = [r["title"] + (f" ({r['hora']})" if r["hora"] else "") for r in nao_feitas]

    gastos = conn.execute(
        "SELECT description, amount FROM expenses WHERE created_at >= ? AND created_at < ? AND tipo = 'real'",
        (ini, fim),
    ).fetchall()
    if gastos:
        total = sum(float(g["amount"] or 0) for g in gastos)
        fatos["gastos"] = f"{len(gastos)} gasto(s), R$ {total:.2f}: " + ", ".join(
            (g["description"] or "?") for g in gastos[:8]
        )

    if _tabela_existe(conn, "voos"):
        voos = conn.execute("SELECT origem, destino, hora, horas FROM voos WHERE data = ?", (d,)).fetchall()
        if voos:
            fatos["voos"] = [
                f"{v['origem'] or '?'} -> {v['destino'] or '?'}" + (f" às {v['hora']}" if v["hora"] else "")
                + (f" ({v['horas']}h)" if v["horas"] else "")
                for v in voos
            ]

    if _tabela_existe(conn, "treinos"):
        treinos = conn.execute("SELECT grupo, duracao_min FROM treinos WHERE data = ?", (d,)).fetchall()
        if treinos:
            fatos["treinos"] = [f"{t['grupo'] or 'treino'}" + (f" {t['duracao_min']} min" if t["duracao_min"] else "") for t in treinos]

    if _tabela_existe(conn, "notas"):
        notas = conn.execute(
            "SELECT titulo FROM notas WHERE criado_em >= ? AND criado_em < ?", (ini, fim)
        ).fetchall()
        if notas:
            fatos["notas_criadas"] = [n["titulo"] for n in notas]

    if _tabela_existe(conn, "checkins"):
        c = conn.execute("SELECT energia, sono, humor FROM checkins WHERE data = ?", (d,)).fetchone()
        if c and any(c[k] is not None for k in ("energia", "sono", "humor")):
            fatos["checkin"] = ", ".join(f"{k} {c[k]}" for k in ("energia", "sono", "humor") if c[k] is not None)

    if _tabela_existe(conn, "refeicoes"):
        import refeicoes

        comida = refeicoes.fatos_do_dia(conn, dia)
        if comida:
            fatos["comida"] = comida

    if _tabela_existe(conn, "diario_anotacoes"):
        anot = [r["texto"] for r in conn.execute("SELECT texto FROM diario_anotacoes WHERE dia = ? ORDER BY id", (d,))]
        if anot:
            fatos["anotacoes_do_alex"] = anot

    n_msgs = conn.execute(
        "SELECT COUNT(*) FROM chat_mensagens WHERE papel = 'user' AND criado_em >= ? AND criado_em < ?", (ini, fim)
    ).fetchone()[0]
    if n_msgs:
        fatos["mensagens_no_chat"] = n_msgs
    return fatos


def conversa_do_dia(conn, dia: date) -> list[dict]:
    ini, fim = _faixa_utc(dia)
    linhas = conn.execute(
        "SELECT papel, texto, criado_em FROM chat_mensagens WHERE criado_em >= ? AND criado_em < ? ORDER BY id",
        (ini, fim),
    ).fetchall()
    return [{"papel": r["papel"], "texto": r["texto"] or "", "hora": _hhmm(r["criado_em"])} for r in linhas]


def _fatos_em_texto(fatos: dict) -> str:
    partes = []
    for chave, valor in fatos.items():
        if chave == "mensagens_no_chat":
            continue
        rotulo = chave.replace("_", " ")
        partes.append(f"{rotulo}: {', '.join(valor) if isinstance(valor, list) else valor}")
    return "; ".join(partes)


# ---- fechar o dia -----------------------------------------------------------

def _resumo_ia(dia: date, fatos: dict, conversa: list[dict]) -> str | None:
    from ia import core
    from ia.funcoes.chat import _garantir_adapter_anthropic_legado

    # so as falas do Alex: a do assistente pode estar errada (no dia 11/10 ele lembrou do date de
    # sabado como se fosse domingo) e o resumo copiava o erro como fato
    transcript = "\n".join(f"[{m['hora']}] {m['texto'][:1500]}" for m in conversa if m["papel"] == "user")
    conteudo = (
        f"DIA: {DIAS_SEMANA[dia.weekday()]} {dia:%d/%m/%Y}\n"
        f"FATOS DO BANCO: {_fatos_em_texto(fatos) or 'nenhum'}\n\n"
        f"O QUE O ALEX DISSE NO DIA:\n{transcript or '(nada)'}"
    )
    try:
        _garantir_adapter_anthropic_legado()
        resp = core.chamar_ia(FUNCAO_IA, [{"role": "user", "content": conteudo[:24000]}], sistema=SISTEMA_DIARIO)
    except Exception:  # noqa: BLE001 - diario e extra; nunca derruba nada
        log.exception("diario: IA falhou")
        return None
    texto = (getattr(resp, "texto", "") or "").strip()
    if not getattr(resp, "ok", False) or not texto:
        return None
    return texto[:1500]


def fechar_dia(conn, dia: date, usar_ia: bool = True) -> dict | None:
    """Grava (ou regrava) a linha do dia. Dia sem nenhum fato nem conversa: nao grava nada."""
    criar_tabela(conn)
    fatos = fatos_do_dia(conn, dia)
    if not fatos:
        return None
    anterior = conn.execute("SELECT tentativas_ia FROM diario_dias WHERE dia = ?", (dia.isoformat(),)).fetchone()
    tentativas = (anterior["tentativas_ia"] if anterior else 0)
    resumo = None
    if usar_ia and fatos.get("mensagens_no_chat"):
        resumo = _resumo_ia(dia, fatos, conversa_do_dia(conn, dia))
        tentativas += 1
    conn.execute(
        "INSERT INTO diario_dias (dia, resumo, fatos_json, tentativas_ia, gerado_em) VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(dia) DO UPDATE SET resumo = COALESCE(excluded.resumo, diario_dias.resumo), "
        "fatos_json = excluded.fatos_json, tentativas_ia = excluded.tentativas_ia, gerado_em = excluded.gerado_em",
        (dia.isoformat(), resumo, json.dumps(fatos, ensure_ascii=False), tentativas),
    )
    conn.commit()
    return {"dia": dia.isoformat(), "resumo": resumo, "fatos": fatos}


def garantir_dias_fechados(conn, hoje: date | None = None, max_ia: int = 1) -> int:
    """Fecha os dias que ja passaram (ultimos DIAS_PRA_FECHAR) que ainda nao tem linha, ou que tem
    conversa mas o resumo da IA falhou (ate 3 tentativas). Faz no maximo `max_ia` chamadas de IA por
    vez - o resto fica pro proximo tick. Devolve quantos dias gravou. Nunca levanta."""
    hoje = hoje or hoje_local()
    gravados = 0
    try:
        criar_tabela(conn)
        ia_usadas = 0
        for atras in range(1, DIAS_PRA_FECHAR + 1):
            dia = hoje - timedelta(days=atras)
            linha = conn.execute(
                "SELECT resumo, fatos_json, tentativas_ia FROM diario_dias WHERE dia = ?", (dia.isoformat(),)
            ).fetchone()
            if linha:
                tem_conversa = bool(json.loads(linha["fatos_json"] or "{}").get("mensagens_no_chat"))
                if linha["resumo"] or not tem_conversa or linha["tentativas_ia"] >= 3:
                    continue
            usar_ia = ia_usadas < max_ia
            if linha and not usar_ia:
                continue  # ja tem os fatos; so falta a IA, que fica pra depois
            if fechar_dia(conn, dia, usar_ia=usar_ia) is not None:
                gravados += 1
                if usar_ia:
                    ia_usadas += 1
    except Exception:  # noqa: BLE001
        log.exception("diario: garantir_dias_fechados falhou")
    return gravados


# ---- leitura ----------------------------------------------------------------

_DIAS_SEMANA_SEM_ACENTO = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def resolver_dia_passado(texto: str | None, hoje: date | None = None) -> date | None:
    """'ontem', 'anteontem', 'hoje', 'sabado' (o ultimo que passou), '10/10', 'dia 10', 'AAAA-MM-DD'.
    Sempre olha pra TRAS (o resolvedor de tarefa, ia.funcoes.chat, olha pra frente)."""
    import re
    import unicodedata

    hoje = hoje or hoje_local()
    t = unicodedata.normalize("NFKD", (texto or "").lower()).encode("ascii", "ignore").decode().strip()
    if not t:
        return None
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        pass
    if "anteontem" in t:
        return hoje - timedelta(days=2)
    if "ontem" in t:
        return hoje - timedelta(days=1)
    if t.startswith("hoje"):
        return hoje
    for i, nome in enumerate(_DIAS_SEMANA_SEM_ACENTO):
        if nome in t:
            atras = (hoje.weekday() - i) % 7 or 7
            return hoje - timedelta(days=atras)
    m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        dia_n, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else hoje.year
        ano = ano + 2000 if ano < 100 else ano
        try:
            d = date(ano, mes, dia_n)
        except ValueError:
            return None
        return d if d <= hoje or m.group(3) else d.replace(year=d.year - 1)
    m = re.search(r"dia (\d{1,2})", t)
    if m:
        try:
            d = hoje.replace(day=int(m.group(1)))
        except ValueError:
            return None
        if d > hoje:
            mes_ant = hoje.replace(day=1) - timedelta(days=1)
            try:
                d = mes_ant.replace(day=int(m.group(1)))
            except ValueError:
                return None
        return d
    return None


def anotar(conn, dia: date, texto: str) -> None:
    """O Alex corrigiu/acrescentou algo sobre um dia. Fica separado do resumo (que pode ser
    regerado) e entra em tudo que le o dia."""
    criar_tabela(conn)
    conn.execute("INSERT INTO diario_anotacoes (dia, texto) VALUES (?, ?)", (dia.isoformat(), texto.strip()[:500]))
    conn.commit()


def _anotacoes(conn, dia: date) -> list[str]:
    return [r[0] for r in conn.execute("SELECT texto FROM diario_anotacoes WHERE dia = ? ORDER BY id", (dia.isoformat(),))]


def ler_dia(conn, dia: date) -> dict | None:
    criar_tabela(conn)
    linha = conn.execute("SELECT resumo, fatos_json FROM diario_dias WHERE dia = ?", (dia.isoformat(),)).fetchone()
    anot = _anotacoes(conn, dia)
    if not linha and not anot:
        return None
    entrada = {
        "dia": dia.isoformat(),
        "resumo": linha["resumo"] if linha else None,
        "fatos": json.loads(linha["fatos_json"] or "{}") if linha else {},
    }
    if anot:
        entrada["anotacoes_do_alex"] = anot
    return entrada


def dias_com_resumo(conn, dias: list[date]) -> set[str]:
    criar_tabela(conn)
    if not dias:
        return set()
    marcas = ",".join("?" * len(dias))
    return {
        r[0] for r in conn.execute(
            f"SELECT dia FROM diario_dias WHERE resumo IS NOT NULL AND dia IN ({marcas})", [d.isoformat() for d in dias]
        )
    }


def _texto_do_dia(entrada: dict) -> str:
    if entrada.get("resumo"):
        texto = " ".join(l.strip().lstrip("-").strip() for l in entrada["resumo"].splitlines() if l.strip())
    else:
        fatos = {k: v for k, v in entrada["fatos"].items() if k != "anotacoes_do_alex"}
        texto = _fatos_em_texto(fatos) or "nada registrado"
    if entrada.get("anotacoes_do_alex"):
        texto += " | O Alex corrigiu (vale mais que o resto): " + "; ".join(entrada["anotacoes_do_alex"])
    return texto


def linhas_contexto(conn, hoje: date | None = None) -> list[str]:
    """Linhas pro system prompt do chat: os ultimos dias, cada um com o nome certo."""
    hoje = hoje or hoje_local()
    linhas = []
    for atras in range(1, DIAS_NO_CONTEXTO + 1):
        dia = hoje - timedelta(days=atras)
        entrada = ler_dia(conn, dia)
        if entrada:
            linhas.append(f"- {rotulo_dia(dia, hoje)}: {_texto_do_dia(entrada)}")
    if not linhas:
        return []
    return [
        "Diário dos últimos dias (dias que JÁ PASSARAM - compromisso citado aqui já aconteceu ou não vale "
        "mais; nada daqui é de hoje). Pra outro dia use consultar_diario:",
        *linhas,
    ]


def consultar(conn, dia: date, hoje: date | None = None) -> dict:
    """Executor da tool consultar_diario: o dia pedido, com rotulo; dia passado sem linha ainda
    e fechado na hora (sem IA, so fatos) pra nunca responder 'nao sei' tendo dado no banco."""
    hoje = hoje or hoje_local()
    if dia > hoje:
        return {"erro": "esse dia ainda não chegou"}
    if dia == hoje:
        fatos = fatos_do_dia(conn, dia)
        return {"dia": rotulo_dia(dia, hoje), "fatos": fatos or "nada registrado ainda hoje",
                "obs": "é hoje - a conversa de hoje você já tem nas mensagens"}
    entrada = ler_dia(conn, dia) or fechar_dia(conn, dia, usar_ia=False)
    if not entrada:
        return {"dia": rotulo_dia(dia, hoje), "nada": "nenhum registro nesse dia"}
    resultado = {"dia": rotulo_dia(dia, hoje), "fatos": entrada["fatos"]}
    if entrada.get("resumo"):
        resultado["resumo"] = entrada["resumo"]
    if entrada.get("anotacoes_do_alex"):
        resultado["anotacoes_do_alex"] = entrada["anotacoes_do_alex"]
    return resultado
