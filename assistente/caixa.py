"""assistente/caixa.py — Faixa P1a (Fase 7): implementacao real do contrato
de assistente/contrato.py (enfileirar/resolver, sem o `conn` - a assinatura
la e fechada) mais o resto do nucleo da Caixa do assistente: listar,
contar_pendentes, processar_repeticoes, expirar e o envio de push. Ver
docs/agentes/fase7-assistente.md pro contrato comum entre as faixas P.

Cada funcao publica garante o proprio schema (CREATE TABLE IF NOT EXISTS,
barato e idempotente) - assim o modulo funciona sozinho em teste (so
`db.init_db()` + estas funcoes, sem aplicar a migracao a parte) e tambem
antes do autoloader de `migracoes/` (Etapa 0/X1) estar de pe.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sqlite3
from datetime import datetime, timedelta

import db
import notificacoes
import push_client

# Mesmo SQL de migracoes/202609241200_p1a_assistente_itens.sql - ver aquele
# arquivo pros comentarios completos sobre cada coluna/indice.
_SCHEMA_SQL = """
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_assistente_itens_chave_unica
    ON assistente_itens (chave_unica) WHERE chave_unica <> '';
CREATE INDEX IF NOT EXISTS idx_assistente_itens_estado ON assistente_itens (estado);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_tipo ON assistente_itens (tipo);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_vence_em ON assistente_itens (vence_em);
CREATE INDEX IF NOT EXISTS idx_assistente_itens_adiado_ate ON assistente_itens (adiado_ate);
"""

TIPOS_VALIDOS = {"pergunta", "aviso", "sugestao", "briefing", "proposta_memoria"}
ESTADOS_VALIDOS = {"pendente", "resolvido", "adiado", "expirado"}
RESPOSTAS_PADRAO = {"sim", "nao", "adiar", "aceitar", "recusar"}

# Ordem de urgencia pedida no contrato: pergunta vencida > pergunta > aviso >
# sugestao. briefing/proposta_memoria (que a frase do contrato nao cita)
# ficam depois de sugestao, na ordem em que aparecem na lista de tipos.
_RANK_TIPO = {"pergunta": 1, "aviso": 2, "sugestao": 3, "briefing": 4, "proposta_memoria": 5}

DEFAULT_REPETIR = {"apos_minutos": [120, 240], "max_por_dia": 3}
# 3h: nao especificado no contrato (so diz que "adiar" e uma resposta
# valida). Meio-termo razoavel entre os proprios 2h/4h da insistencia -
# reabre a pergunta antes do proximo reforco de push chegar no mesmo dia.
ADIAR_PADRAO_MINUTOS = 180

CHAVE_ULTIMO_TICK = "assistente.ultimo_tick_em"

# Fora do escopo por decisao do Alex (fase7-assistente.md): vida amorosa e
# relacionamento nunca viram aviso, pergunta nem proposta de memoria.
# Checado uma unica vez aqui (enfileirar e o unico ponto de entrada de toda
# faixa produtora), pra nenhuma faixa precisar lembrar de filtrar sozinha.
# Lista curta de proposito - termos que quase so aparecem nesse contexto,
# pra nao engolir sugestao financeira/tarefa legitima por engano (ex.:
# "orcamento do casamento" fica de fora de proposito).
PALAVRAS_FORA_DE_ESCOPO = (
    "namorada", "namorado", "ex-namorada", "ex-namorado",
    "esposa", "esposo", "crush", "paquera", "affair",
    "vida amorosa", "relacionamento amoroso",
)


def _agora() -> datetime:
    """Hora local (igual ao resto do projeto - notificacoes.py usa
    datetime.now() sem tz). Ponto unico pra testes trocarem via monkeypatch
    de `caixa._agora`: enfileirar/resolver nao podem ganhar um parametro
    `agora` porque a assinatura vem fechada de assistente/contrato.py."""
    return datetime.now()


def _fmt(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def _fora_de_escopo(titulo: str, corpo: str) -> bool:
    texto = f"{titulo} {corpo}".lower()
    return any(palavra in texto for palavra in PALAVRAS_FORA_DE_ESCOPO)


def _garantir_tabela(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)


def _row_para_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    for campo in ("opcoes", "repetir"):
        bruto = item.get(campo)
        if bruto:
            try:
                item[campo] = json.loads(bruto)
            except (TypeError, ValueError):
                item[campo] = None
        else:
            item[campo] = None
    return item


# ---------------------------------------------------------------------------
# Contrato (assistente/contrato.py) - assinatura exata, sem `conn`.

def enfileirar(tipo: str, titulo: str, corpo: str = "", *, opcoes: list | None = None,
               origem: str = "", chave_unica: str = "", repetir: dict | None = None,
               vence_em: str | None = None) -> str:
    """Cria um item na Caixa e devolve o id (string). Devolve "" sem criar
    nada quando `tipo` esta fora do vocabulario ou o texto bate com o filtro
    de fora-de-escopo. `chave_unica` (quando nao vazia) e idempotente: se ja
    existir um item com essa chave (de qualquer estado), devolve o id dele
    em vez de duplicar - e o que deixa um gatilho rodar 2x no mesmo tick sem
    problema."""
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo invalido: {tipo!r} (esperado um de {sorted(TIPOS_VALIDOS)})")
    if not titulo or not titulo.strip():
        raise ValueError("titulo obrigatorio")
    if _fora_de_escopo(titulo, corpo):
        return ""

    chave_unica = chave_unica or ""
    conn = db.get_db()
    try:
        _garantir_tabela(conn)
        agora = _agora()
        try:
            cur = conn.execute(
                """
                INSERT INTO assistente_itens
                    (tipo, titulo, corpo, opcoes, origem, chave_unica, criado_em, vence_em, repetir)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tipo,
                    titulo.strip(),
                    corpo or "",
                    json.dumps(opcoes, ensure_ascii=False) if opcoes else None,
                    origem or "",
                    chave_unica,
                    _fmt(agora),
                    vence_em,
                    json.dumps(repetir, ensure_ascii=False) if repetir else None,
                ),
            )
            conn.commit()
            return str(cur.lastrowid)
        except sqlite3.IntegrityError:
            # chave_unica ja existia - devolve o id de quem ja estava la.
            conn.rollback()
            existente = conn.execute(
                "SELECT id FROM assistente_itens WHERE chave_unica = ?", (chave_unica,)
            ).fetchone()
            if existente is None:
                raise
            return str(existente["id"])
    finally:
        conn.close()


def resolver(item_id: str, resposta: str, texto: str = "") -> None:
    """Registra a resposta e fecha (`resolvido`) ou adia (`adiado`) o item.
    Idempotente: responder de novo um item ja `resolvido`/`expirado` nao faz
    nada. `resposta` precisa ser uma das padrao (sim/nao/adiar/aceitar/
    recusar) ou um valor presente nas `opcoes` proprias do item."""
    conn = db.get_db()
    try:
        _garantir_tabela(conn)
        row = conn.execute(
            "SELECT * FROM assistente_itens WHERE id = ?", (int(item_id),)
        ).fetchone()
        if row is None:
            raise ValueError(f"item {item_id!r} nao encontrado")
        item = _row_para_dict(row)

        if item["estado"] in ("resolvido", "expirado"):
            return

        opcoes_validas = set(RESPOSTAS_PADRAO)
        for opcao in item.get("opcoes") or []:
            if isinstance(opcao, str):
                opcoes_validas.add(opcao)
            elif isinstance(opcao, dict) and isinstance(opcao.get("valor"), str):
                opcoes_validas.add(opcao["valor"])
        if resposta not in opcoes_validas:
            raise ValueError(f"resposta invalida: {resposta!r} (esperado um de {sorted(opcoes_validas)})")

        agora = _agora()
        if resposta == "adiar":
            adiado_ate = agora + timedelta(minutes=ADIAR_PADRAO_MINUTOS)
            conn.execute(
                "UPDATE assistente_itens SET estado = 'adiado', resposta = ?, resposta_texto = ?, "
                "adiado_ate = ? WHERE id = ?",
                (resposta, texto or "", _fmt(adiado_ate), item["id"]),
            )
            conn.commit()
            return

        conn.execute(
            "UPDATE assistente_itens SET estado = 'resolvido', resposta = ?, resposta_texto = ?, "
            "resolvido_em = ? WHERE id = ?",
            (resposta, texto or "", _fmt(agora), item["id"]),
        )
        conn.commit()

        item["estado"] = "resolvido"
        item["resposta"] = resposta
        item["resposta_texto"] = texto or ""
        item["resolvido_em"] = _fmt(agora)
        _chamar_ao_resolver(conn, item, resposta, texto)
    finally:
        conn.close()


def _chamar_ao_resolver(conn: sqlite3.Connection, item: dict, resposta: str, texto: str) -> None:
    """origem = '<modulo_do_gatilho>:<resto>' (ex.: 'p9_memoria:semana-39:abc',
    'p2_perguntas:conta:12:2026-09-24'). Definicao do integrador (substitui
    o texto ambiguo do contrato): <modulo_do_gatilho> e o nome EXATO do
    arquivo em assistente/gatilhos/ sem '.py' - divide no PRIMEIRO ':',
    nunca no '_' (o nome do modulo pode ter '_' dentro, ex. p2_perguntas).
    Se o modulo (ou o ao_resolver dentro dele) nao existir, e um no-op
    silencioso: so registra a resposta, sem erro - as faixas P2..P9 ainda
    podem nao ter sido escritas, e um bug numa delas nunca pode derrubar o
    resolver de outra."""
    origem = item.get("origem") or ""
    prefixo = origem.split(":", 1)[0].strip()
    if not prefixo:
        return
    try:
        modulo = importlib.import_module(f"assistente.gatilhos.{prefixo}")
        ao_resolver = getattr(modulo, "ao_resolver", None)
        if ao_resolver is None:
            return
        ao_resolver(conn, item, resposta, texto)
    except Exception as exc:  # noqa: BLE001 - ver docstring acima
        print(f"[assistente.caixa] ao_resolver falhou (origem={origem!r}): {exc!r}")


# ---------------------------------------------------------------------------
# Leitura da Caixa (recebem `conn` de fora, como o resto do projeto).

def listar(conn: sqlite3.Connection, estado: str | None = None, limite: int = 200) -> list[dict]:
    """estado=None lista so os itens `pendente` (o que a tela Assistente e o
    selo da aba Hoje mostram por padrao). Ordenado por urgencia: pergunta
    vencida > pergunta > aviso > sugestao > briefing > proposta_memoria;
    dentro do mesmo tipo, quem tem vence_em mais proximo vem primeiro (quem
    nao tem vence_em fica por ultimo dentro do grupo)."""
    _garantir_tabela(conn)
    estado_filtro = estado if estado is not None else "pendente"
    if estado_filtro not in ESTADOS_VALIDOS:
        raise ValueError(f"estado invalido: {estado_filtro!r} (esperado um de {sorted(ESTADOS_VALIDOS)})")

    agora_str = _fmt(_agora())
    linhas = conn.execute(
        "SELECT * FROM assistente_itens WHERE estado = ? ORDER BY criado_em DESC",
        (estado_filtro,),
    ).fetchall()
    itens = [_row_para_dict(r) for r in linhas]

    def _chave_ordenacao(item: dict) -> tuple:
        vencida = item["tipo"] == "pergunta" and item["vence_em"] is not None and item["vence_em"] <= agora_str
        rank_tipo = 0 if vencida else _RANK_TIPO.get(item["tipo"], 9)
        sem_vencimento = item["vence_em"] is None
        return (rank_tipo, sem_vencimento, item["vence_em"] or "", item["id"])

    itens.sort(key=_chave_ordenacao)
    return itens[: max(0, limite)]


def contar_pendentes(conn: sqlite3.Connection) -> int:
    _garantir_tabela(conn)
    row = conn.execute("SELECT COUNT(*) AS n FROM assistente_itens WHERE estado = 'pendente'").fetchone()
    return int(row["n"])


# ---------------------------------------------------------------------------
# Periodicidade (chamadas do tick - `agora` sempre injetado, nunca
# datetime.now() direto aqui).

def expirar(conn: sqlite3.Connection, agora: datetime) -> int:
    """Vence quem passou de vence_em e ainda nao foi resolvido (pendente ou
    adiado - um item adiado que estoura o prazo enquanto cochilava tambem
    expira, o adiamento nao segura o prazo). Devolve quantos expiraram."""
    _garantir_tabela(conn)
    cur = conn.execute(
        "UPDATE assistente_itens SET estado = 'expirado' "
        "WHERE estado IN ('pendente', 'adiado') AND vence_em IS NOT NULL AND vence_em <= ?",
        (_fmt(agora),),
    )
    conn.commit()
    return cur.rowcount


def _fallback_silencio_padrao(agora: datetime) -> bool:
    return not notificacoes.dentro_do_horario_silencioso(agora, "22:00", "07:00")


def _aviso_permitido(tipo: str, agora: datetime) -> bool:
    """Import tardio de assistente.avisos.aviso_permitido (faixa P8) - se
    ainda nao existir (ou for so o stub NotImplementedError de
    assistente/contrato.py), cai no fallback fixo (permitido fora de
    22h-7h, sem olhar configuracoes). A implementacao real de P8 aceita um
    `agora` opcional (pra ser testavel sem depender do relogio real) -
    passamos o nosso quando ela aceita esse parametro (checado via
    inspect, em vez de tentar/capturar TypeError, pra nao confundir um bug
    de verdade dentro dela com "essa versao nao tem agora")."""
    try:
        from assistente.avisos import aviso_permitido
    except (ImportError, ModuleNotFoundError):
        return _fallback_silencio_padrao(agora)
    try:
        aceita_agora = "agora" in inspect.signature(aviso_permitido).parameters
    except (TypeError, ValueError):
        aceita_agora = False
    try:
        if aceita_agora:
            return bool(aviso_permitido(tipo, agora=agora))
        return bool(aviso_permitido(tipo))
    except NotImplementedError:
        return _fallback_silencio_padrao(agora)


def enviar_push(conn: sqlite3.Connection, titulo: str, corpo: str, url: str = "") -> bool:
    """Funcao fina que reaproveita o mecanismo de push ja existente
    (push_client.py + db.list_push_subscriptions/delete_push_subscription) -
    o envio "de verdade" hoje mora dentro de rotas de app.py (`_despachar`
    perto da linha 4502, `/api/push/testar` perto da 8340), acoplado a
    variaveis locais da requisicao (sessao, `subs` etc.), entao nao dava pra
    chamar direto. `url` fica na assinatura pro contrato de notificacao
    clicavel; static/service-worker.js (fora dos meus arquivos) ainda so
    abre "/" no clique, entao url nao e usado no payload por enquanto.
    Devolve True se conseguiu entregar pra pelo menos uma inscricao."""
    if not push_client.configurado():
        return False
    subs = db.list_push_subscriptions(conn)
    entregue = False
    for s in subs:
        try:
            sub_dict = json.loads(s["subscription_json"])
        except (TypeError, ValueError):
            continue
        if push_client.enviar(sub_dict, titulo, corpo):
            entregue = True
        else:
            db.delete_push_subscription(conn, s["endpoint"])
    return entregue


def processar_repeticoes(conn: sqlite3.Connection, agora: datetime) -> dict:
    """Politica de insistencia do contrato (fase7-assistente.md): reenvia
    push apos 2h e 4h contados da criacao do item (`repetir.apos_minutos`,
    padrao [120, 240]), no maximo `repetir.max_por_dia` vezes por dia
    corrido (padrao 3), respeitando aviso_permitido. No maximo 1 push por
    item por chamada (o tick roda a cada poucos minutos - varios limiares
    vencidos de uma vez viram varias chamadas de tick, nunca uma rajada no
    mesmo instante). Tambem tira da soneca quem passou de adiado_ate,
    devolvendo pro estado pendente (essa mesma chamada ja pode mandar o
    proximo push pra ele, se o horario permitir). Devolve
    {"reativados": N, "pushes_enviados": M} - o /api/tick usa isso na
    resposta curta."""
    _garantir_tabela(conn)
    agora_str = _fmt(agora)

    cur = conn.execute(
        "UPDATE assistente_itens SET estado = 'pendente', adiado_ate = NULL "
        "WHERE estado = 'adiado' AND adiado_ate IS NOT NULL AND adiado_ate <= ?",
        (agora_str,),
    )
    reativados = cur.rowcount
    conn.commit()

    pushes_enviados = 0
    pendentes = conn.execute("SELECT * FROM assistente_itens WHERE estado = 'pendente'").fetchall()
    for row in pendentes:
        item = _row_para_dict(row)
        repetir_cfg = item.get("repetir") or DEFAULT_REPETIR
        apos_minutos = sorted(repetir_cfg.get("apos_minutos") or DEFAULT_REPETIR["apos_minutos"])
        max_por_dia = repetir_cfg.get("max_por_dia", DEFAULT_REPETIR["max_por_dia"])

        ultimo_push_em = item.get("ultimo_push_em")
        mesmo_dia = bool(ultimo_push_em) and str(ultimo_push_em)[:10] == agora_str[:10]
        pushes_hoje = item["pushes_hoje"] if mesmo_dia else 0
        if pushes_hoje >= max_por_dia:
            continue

        criado_em = datetime.strptime(item["criado_em"], "%Y-%m-%d %H:%M:%S")
        elapsed_min = (agora - criado_em).total_seconds() / 60
        limiares_vencidos = sum(1 for t in apos_minutos if elapsed_min >= t)
        pushes_devidos_agora = min(1 + limiares_vencidos, max_por_dia)
        if pushes_hoje >= pushes_devidos_agora:
            continue

        if not _aviso_permitido(item["tipo"], agora):
            continue

        enviar_push(conn, item["titulo"], item["corpo"], url="")
        conn.execute(
            "UPDATE assistente_itens SET pushes_hoje = ?, ultimo_push_em = ? WHERE id = ?",
            (pushes_hoje + 1, agora_str, item["id"]),
        )
        conn.commit()
        pushes_enviados += 1

    return {"reativados": reativados, "pushes_enviados": pushes_enviados}
