"""Cartoes da manha (leva Lab v4, ideia "cartoes-manha", 30/10/2026).

Coisa que o Alex mencionou uma vez e sumiu (o presente da mae, a revisao do carro, a materia parada). Uma vez por
dia, de madrugada (primeiro tick depois das 4h; o PC pode estar desligado as 4h), a IA relê a semana e deixa no chat
UM card "Pra hoje" com NO MAXIMO 3 cartoes, so com fato concreto:

    "Presente da tua mae -- Tu falou dia 12 que queria dar algo. Aniversario dela em 9 dias e nada anotado."

Cada cartao tem tres botoes: o primeiro (**Resolver**) faz a coisa proposta (cria a tarefa, com hora quando a IA
sugeriu), **Depois** volta amanha, **Esquece** guarda o assunto numa lista e a IA nunca mais puxa aquilo.

Anti-invencao (o card so vale se for fato): o que a IA devolve precisa trazer a `evidencia` - um trecho LITERAL do
que o Alex escreveu (ou de um lembrete/tarefa/diario) - e o servidor confere que esse trecho existe mesmo no contexto
que ele mandou pra IA. Sem evidencia achada = cartao descartado. Mais: assunto ja esquecido, tarefa ja aberta com o
mesmo nome e duplicata no mesmo dia tambem caem fora. Sem nada concreto = nada e publicado (nenhum "bom dia" vazio).

Custo: 1 chamada barata (Haiku, `ia/config.d/cartoes_manha.json`) por dia. Falhou = tenta no tick seguinte, ate 3x.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, time, timedelta

import db

log = logging.getLogger(__name__)

FUNCAO_IA = "cartoes_manha"
MAX_CARTOES = 3
JANELA = (time(4, 0), time(12, 0))
DIAS_DE_CONVERSA = 10
MAX_MENSAGENS = 70
MAX_CONTEXTO = 14000
CONFIG_DIA = "cartoes_manha_dia"  # {"dia": iso, "tentativas": n, "feito": bool}
STATUS = ("novo", "feito", "depois", "esquecido")

SCHEMA = {
    "type": "object",
    "required": ["cartoes"],
    "additionalProperties": False,
    "properties": {
        "cartoes": {
            "type": "array",
            "maxItems": MAX_CARTOES,
            "items": {
                "type": "object",
                "required": ["titulo", "texto", "evidencia", "rotulo"],
                "additionalProperties": False,
                "properties": {
                    "titulo": {"type": "string", "maxLength": 60},
                    "texto": {"type": "string", "maxLength": 240},
                    "evidencia": {"type": "string", "maxLength": 200},
                    "rotulo": {"type": "string", "maxLength": 40},
                    "tarefa": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "titulo": {"type": "string", "maxLength": 100},
                            "quando": {"type": "string", "enum": ["hoje", "amanha", "sem_data"]},
                            "hora": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
}

SISTEMA = """Voce prepara os "cartoes da manha" do Alex (assistente pessoal, TDAH, portugues do Brasil, trata por "tu").
Recebe o que ele escreveu nos ultimos dias, o diario, lembretes e tarefas abertas. Devolva NO MAXIMO 3 cartoes
sobre coisas que ele MENCIONOU uma vez e que ainda nao tem tarefa nem desfecho (presente, revisao do carro, materia
parada, ligar pra alguem, comprar algo). REGRAS:
- So fato concreto, com a data ou o numero que aparece no contexto ("tu falou dia 12 que queria dar algo; faltam 9 dias").
  Use a DATA DE HOJE informada pra contar dias. Nunca palpite, nunca moral, nunca cobranca.
- `evidencia` = trecho LITERAL (copiado, ate 200 caracteres) do contexto que prova o cartao. Sem trecho literal, nao faca o cartao.
- `texto`: 1 ou 2 frases curtas, com "tu". `titulo`: 2 a 5 palavras. `rotulo`: o que o botao principal faz ("Pôr 20 min às 19h",
  "Ver 3 ideias", "Marcar com o Zé"). `tarefa`: a tarefa que o botao cria (titulo curto, quando = hoje/amanha/sem_data, hora HH:MM so se fizer sentido).
- Nao repita nada que ja virou tarefa aberta, nem os assuntos da lista "NAO PUXAR". Nada de vida amorosa, dinheiro da empresa ou valores.
- Se nao houver nada concreto, devolva {"cartoes": []}. Melhor zero cartoes que um cartao inventado."""


def criar_tabelas(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cartoes_manha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia TEXT NOT NULL,
            chave TEXT NOT NULL,
            titulo TEXT NOT NULL,
            texto TEXT NOT NULL,
            rotulo TEXT NOT NULL,
            evidencia TEXT NOT NULL DEFAULT '',
            tarefa_titulo TEXT,
            tarefa_quando TEXT,
            tarefa_hora TEXT,
            status TEXT NOT NULL DEFAULT 'novo',
            adiado_ate TEXT,
            tarefa_id INTEGER,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            resolvido_em TEXT
        )
        """
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS manha_esquecidos (chave TEXT PRIMARY KEY, titulo TEXT NOT NULL, "
        "em TEXT NOT NULL DEFAULT (datetime('now')))"
    )


# ------------------------------------------------------------------ texto


def sem_acento(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _normal(texto) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sem_acento(texto))).strip()


_PALAVRAS_FRACAS = {"para", "pra", "com", "uma", "uns", "umas", "dos", "das", "que", "mae", "meu", "sua", "seu"}


def chave_do_assunto(titulo: str) -> str:
    """Impressao do assunto: ate 3 palavras com mais de 3 letras, em ordem alfabetica ('Presente da tua mãe' ->
    'presente'; 'Óleo do carro' -> 'carro oleo'). Serve pra 'Esquece' valer mesmo quando a IA reescreve o titulo."""
    palavras = sorted({p for p in _normal(titulo).split() if len(p) > 3 and p not in _PALAVRAS_FRACAS})
    return " ".join(palavras[:3]) or _normal(titulo)[:30]


def _mesmo_assunto(chave_a: str, chave_b: str) -> bool:
    a, b = set(chave_a.split()), set(chave_b.split())
    if not a or not b:
        return False
    if a == b:
        return True
    comum = a & b
    # assunto de uma palavra so ("presente") casa se ela aparece no outro; senao precisa de 2 palavras em comum
    return bool(comum) if min(len(a), len(b)) == 1 else len(comum) >= 2


# ------------------------------------------------------------------ contexto


def contexto(conn, hoje: date) -> str:
    """O que a IA enxerga: conversa recente DELE (so as falas dele, a do assistente pode estar errada),
    diario, lembretes proximos e tarefas abertas. Tudo com data."""
    import diario

    partes = [f"DATA DE HOJE: {hoje.isoformat()} ({diario.DIAS_SEMANA[hoje.weekday()]})"]
    limite = (datetime.now() - timedelta(days=DIAS_DE_CONVERSA + 1)).strftime("%Y-%m-%d %H:%M:%S")
    falas = conn.execute(
        "SELECT texto, criado_em FROM chat_mensagens WHERE papel = 'user' AND criado_em >= ? ORDER BY id DESC LIMIT ?",
        (limite, MAX_MENSAGENS),
    ).fetchall()
    linhas = []
    for f in reversed(falas):
        dt = diario.utc_para_local(f["criado_em"])
        texto = " ".join((f["texto"] or "").split())[:300]
        if dt and texto:
            linhas.append(f"[{dt:%Y-%m-%d}] {texto}")
    partes.append("O QUE O ALEX ESCREVEU:\n" + ("\n".join(linhas) or "(nada)"))
    dias = []
    for atras in range(1, DIAS_DE_CONVERSA + 1):
        dia = hoje - timedelta(days=atras)
        e = diario.ler_dia(conn, dia)
        if e and e.get("resumo"):
            dias.append(f"[{dia.isoformat()}] " + " ".join(l.strip().lstrip("-").strip() for l in e["resumo"].splitlines() if l.strip()))
    if dias:
        partes.append("DIARIO:\n" + "\n".join(dias))
    lemb = conn.execute(
        "SELECT titulo, data FROM lembretes WHERE data >= ? AND data <= ? ORDER BY data LIMIT 20",
        (hoje.isoformat(), (hoje + timedelta(days=30)).isoformat()),
    ).fetchall()
    if lemb:
        partes.append("LEMBRETES PROXIMOS:\n" + "\n".join(f"[{l['data']}] {l['titulo']}" for l in lemb))
    tarefas = conn.execute(
        "SELECT title, due_date, hora FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL ORDER BY id DESC LIMIT 40"
    ).fetchall()
    if tarefas:
        partes.append("TAREFAS ABERTAS (ja tem dono, nao repetir):\n" + "\n".join(
            f"- {t['title']}" + (f" ({t['due_date']}{' ' + t['hora'] if t['hora'] else ''})" if t["due_date"] else "") for t in tarefas))
    return "\n\n".join(partes)[:MAX_CONTEXTO]


def esquecidos(conn) -> list[dict]:
    criar_tabelas(conn)
    return [dict(r) for r in conn.execute("SELECT chave, titulo FROM manha_esquecidos ORDER BY em DESC LIMIT 60").fetchall()]


# ------------------------------------------------------------------ validar


def _hora_ok(h) -> str | None:
    if not isinstance(h, str):
        return None
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", h)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def validar(bruto, ctx: str, ja_esquecidos: list[dict], tarefas_abertas: list[str]) -> list[dict]:
    """Aplica as travas anti-invencao em cima do que a IA devolveu. Devolve ate MAX_CARTOES cartoes limpos."""
    itens = bruto.get("cartoes") if isinstance(bruto, dict) else None
    if not isinstance(itens, list):
        return []
    ctx_n = _normal(ctx)
    chaves_esq = [e["chave"] for e in ja_esquecidos]
    chaves_tar = [chave_do_assunto(t) for t in tarefas_abertas]
    saida, vistas = [], []
    for it in itens:
        if not isinstance(it, dict):
            continue
        titulo = " ".join(str(it.get("titulo") or "").split())[:60]
        texto = " ".join(str(it.get("texto") or "").split())[:240]
        rotulo = " ".join(str(it.get("rotulo") or "").split())[:40]
        evidencia = _normal(it.get("evidencia"))
        if not titulo or not texto or not rotulo or len(evidencia) < 12 or evidencia not in ctx_n:
            continue  # sem trecho literal que prove = nao e fato
        chave = chave_do_assunto(titulo)
        if any(_mesmo_assunto(chave, c) for c in chaves_esq + vistas) or any(_mesmo_assunto(chave, c) for c in chaves_tar):
            continue
        tar = it.get("tarefa") if isinstance(it.get("tarefa"), dict) else {}
        t_tit = " ".join(str(tar.get("titulo") or titulo).split())[:100]
        quando = tar.get("quando") if tar.get("quando") in ("hoje", "amanha", "sem_data") else "hoje"
        saida.append({
            "chave": chave, "titulo": titulo, "texto": texto, "rotulo": rotulo,
            "evidencia": " ".join(str(it.get("evidencia")).split())[:200],
            "tarefa_titulo": t_tit, "tarefa_quando": quando, "tarefa_hora": _hora_ok(tar.get("hora")),
        })
        vistas.append(chave)
        if len(saida) >= MAX_CARTOES:
            break
    return saida


def _pedir_ia(ctx: str, ja_esquecidos: list[dict]) -> dict | None:
    from ia import core
    from ia.funcoes.chat import _garantir_adapter_anthropic_legado

    nao_puxar = "\n".join(f"- {e['titulo']}" for e in ja_esquecidos) or "(nada)"
    try:
        _garantir_adapter_anthropic_legado()
        resp = core.chamar_ia(
            FUNCAO_IA, [{"role": "user", "content": f"{ctx}\n\nNAO PUXAR (ele pediu pra esquecer):\n{nao_puxar}"}],
            sistema=SISTEMA, schema=SCHEMA,
        )
    except Exception:  # noqa: BLE001 - cartao da manha e extra; nunca derruba o tick
        log.exception("cartoes_manha: IA falhou")
        return None
    if not getattr(resp, "ok", False) or not isinstance(getattr(resp, "dados", None), dict):
        return None
    return resp.dados


# ------------------------------------------------------------------ preparar


def _estado_dia(conn, hoje: date) -> dict:
    try:
        e = json.loads(db.obter_configuracao(conn, CONFIG_DIA) or "{}")
    except ValueError:
        e = {}
    if not isinstance(e, dict) or e.get("dia") != hoje.isoformat():
        e = {"dia": hoje.isoformat(), "tentativas": 0, "feito": False}
    return e


def _guardar_estado(conn, e: dict) -> None:
    db.definir_configuracao(conn, CONFIG_DIA, json.dumps(e))


def devolvidos_de_ontem(conn, hoje: date) -> list[dict]:
    """Cartoes que ele empurrou com 'Depois' e que voltam hoje (sem gastar IA)."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM cartoes_manha WHERE status = 'depois' AND adiado_ate <= ? ORDER BY id", (hoje.isoformat(),)).fetchall()]


def preparar(conn, hoje: date, agora: datetime, pedir_ia=None) -> list[dict] | None:
    """Monta os cartoes do dia (devolvidos do 'Depois' primeiro, depois os novos da IA, ate 3 no total) e grava.
    None = nao era hora / ja fez hoje / IA falhou (tenta de novo no proximo tick). [] = nada concreto hoje."""
    criar_tabelas(conn)
    estado = _estado_dia(conn, hoje)
    if estado["feito"] or estado["tentativas"] >= 3:
        return None
    for v in devolvidos_de_ontem(conn, hoje):
        conn.execute("UPDATE cartoes_manha SET status = 'novo', dia = ?, adiado_ate = NULL WHERE id = ?", (hoje.isoformat(), v["id"]))
    volta = _linhas_do_dia(conn, hoje)  # os que voltaram do 'Depois' (e qualquer um de hoje que ja exista)
    vagas = MAX_CARTOES - len(volta)
    if vagas > 0:
        estado["tentativas"] += 1
        ctx = contexto(conn, hoje)
        esq = esquecidos(conn)
        bruto = (pedir_ia or _pedir_ia)(ctx, esq)
        if bruto is None and not volta:
            _guardar_estado(conn, estado)
            conn.commit()
            return None  # IA falhou: tenta de novo no proximo tick (ate 3x)
        if bruto is not None:
            abertas = [r["title"] for r in conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()]
            # os que voltaram do 'Depois' tambem contam como 'ja visto' pra IA nao repetir o mesmo assunto
            ja = [{"chave": v["chave"], "titulo": v["titulo"]} for v in volta]
            for n in validar(bruto, ctx, esq + ja, abertas)[:vagas]:
                conn.execute(
                    "INSERT INTO cartoes_manha (dia, chave, titulo, texto, rotulo, evidencia, tarefa_titulo, tarefa_quando, tarefa_hora) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (hoje.isoformat(), n["chave"], n["titulo"], n["texto"], n["rotulo"], n["evidencia"], n["tarefa_titulo"],
                     n["tarefa_quando"], n["tarefa_hora"]),
                )
    estado["feito"] = True
    _guardar_estado(conn, estado)
    conn.commit()
    return _linhas_do_dia(conn, hoje)


def _linhas_do_dia(conn, hoje: date) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM cartoes_manha WHERE dia = ? AND status = 'novo' ORDER BY id", (hoje.isoformat(),)).fetchall()]


# ------------------------------------------------------------------ card


def card(linhas: list[dict], agora: datetime) -> dict:
    import cards

    return cards.novo_card("cartoes_manha", {
        "preparado_as": f"{agora:%H:%M}",
        "cartoes": [{"id": l["id"], "titulo": l["titulo"], "texto": l["texto"], "rotulo": l["rotulo"], "status": l["status"]} for l in linhas],
    })


def verificar(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Passo do tick (conversa_proativa.verificar): publica o card no chat 1x por dia e devolve o push
    [(tipo, titulo, corpo)]. Nunca levanta."""
    if not (JANELA[0] <= agora.time() <= JANELA[1]) or db.ja_notificou_hoje(conn, "cartoes_manha_chat"):
        return []
    linhas = preparar(conn, agora.date(), agora)
    if linhas is None:
        return []
    if not linhas:
        db.marcar_notificado(conn, "cartoes_manha_chat")
        conn.commit()
        return []
    import conversa_proativa

    n = len(linhas)
    texto = "Preparei " + ("1 coisa que ficou solta" if n == 1 else f"{n} coisas que ficaram soltas") + ". Resolve, adia ou me manda esquecer."
    conversa_proativa.publicar(conn, "cartoes_manha_chat", texto, [card(linhas, agora)])
    corpo = linhas[0]["titulo"] + (f" e mais {n - 1}" if n > 1 else "") + ". Abre pra resolver."
    return [("cartoes_manha", "Pra hoje", corpo)]


# ------------------------------------------------------------------ acoes


def _por_id(conn, cartao_id: int) -> dict | None:
    criar_tabelas(conn)
    r = conn.execute("SELECT * FROM cartoes_manha WHERE id = ?", (cartao_id,)).fetchone()
    return dict(r) if r else None


def estado_de(conn, ids: list[int]) -> dict[int, str]:
    criar_tabelas(conn)
    ids = [int(i) for i in ids][:20]
    if not ids:
        return {}
    marcas = ",".join("?" * len(ids))
    return {r["id"]: r["status"] for r in conn.execute(f"SELECT id, status FROM cartoes_manha WHERE id IN ({marcas})", ids).fetchall()}


def resolver(conn, cartao_id: int, hoje: date) -> dict | None:
    """'Resolver': cria a tarefa que o cartao propos (hoje / amanha / sem data -> hoje, com hora se tiver)."""
    c = _por_id(conn, cartao_id)
    if not c:
        return None
    if c["status"] == "feito":
        return {"ok": True, "tarefa_id": c["tarefa_id"], "ja": True}
    quando = c["tarefa_quando"] or "hoje"
    dia = hoje + timedelta(days=1) if quando == "amanha" else hoje
    tid = None
    if c["tarefa_titulo"]:
        tid = conn.execute(
            "INSERT INTO tasks (title, due_date, hora, source_text) VALUES (?, ?, ?, ?)",
            (c["tarefa_titulo"], dia.isoformat(), c["tarefa_hora"], f"cartao da manha: {c['titulo']}"),
        ).lastrowid
    conn.execute("UPDATE cartoes_manha SET status = 'feito', tarefa_id = ?, resolvido_em = datetime('now') WHERE id = ?", (tid, cartao_id))
    conn.commit()
    return {"ok": True, "tarefa_id": tid, "titulo": c["tarefa_titulo"], "dia": dia.isoformat(), "hora": c["tarefa_hora"]}


def depois(conn, cartao_id: int, hoje: date) -> dict | None:
    """'Depois': volta amanha (uma vez; se ja voltou e ele empurra de novo, volta de novo)."""
    c = _por_id(conn, cartao_id)
    if not c:
        return None
    amanha = (hoje + timedelta(days=1)).isoformat()
    conn.execute("UPDATE cartoes_manha SET status = 'depois', adiado_ate = ? WHERE id = ?", (amanha, cartao_id))
    conn.commit()
    return {"ok": True, "volta_em": amanha}


def esquecer(conn, cartao_id: int) -> dict | None:
    """'Esquece': o assunto entra na lista que vai pra IA como 'NAO PUXAR'."""
    c = _por_id(conn, cartao_id)
    if not c:
        return None
    conn.execute("UPDATE cartoes_manha SET status = 'esquecido', resolvido_em = datetime('now') WHERE id = ?", (cartao_id,))
    conn.execute("INSERT OR REPLACE INTO manha_esquecidos (chave, titulo) VALUES (?, ?)", (c["chave"], c["titulo"]))
    conn.commit()
    return {"ok": True}
