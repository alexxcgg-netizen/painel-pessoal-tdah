"""rotas/n3a_widget.py — Fase 7, faixa N3a (endpoint e pagina do widget).

`GET /api/widget`: resumo compacto pra widget externo (Widgy, Scriptable,
tela de bloqueio) - autenticado por `PAINEL_WIDGET_TOKEN` (header
`Authorization: Bearer <token>` OU `?token=`), nunca por sessao/PIN. Formato
exato documentado em `docs/widget-widgy.md`.

`GET /widget`: mesma coisa, so que como pagina HTML leve (sem PIN, mesmo
token), pensada pra "adicionar a tela inicial" no celular.

Ja existia um endpoint antigo pra widget Scriptable (`app.atalho_resumo`,
`GET /api/atalho/resumo`, autenticado por `PAINEL_ATALHOS_TOKEN`) - ele
continua existindo do jeito que esta (nao foi editado aqui, tem formato e
proposito diferentes: campos crus tipo `tarefas_pendentes`/`gasto_hoje`, nao
o resumo "foco/proxima_conta/habitos/custo_ia" pedido pra esta faixa). O que
ESTE modulo reaproveita e a coleta de dados ja pronta em outros lugares do
app: `app._visao_do_dia_itens`/`app._proximo_item_em_foco` (o "item em foco
agora", ja usado por `/api/visao-dia/hoje`), `app._contas_pessoais_com_status`
e `app._buscar_contas_a_vencer_construtora` (a mesma API read-only da
construtora que `app._construtora_contexto_contas` ja consulta), e
`db.list_habitos`/`db.marcacoes_habito_no_periodo`/`db.habito_marcado` +
`vida.habito_devido_em` (a mesma logica de habito devido que
`app._contagem_dia` usa) - nada disso e recalculado do zero aqui.

Nunca devolve saldo nem qualquer dado financeiro da construtora: a proxima
conta da construtora entra so com nome+dias (ver `montar_widget`). Sem
valor em R$ por padrao mesmo pra conta pessoal - so com `?mostrar_valores=1`.
"""

import hmac
import os
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request

import db
import ia.teto as ia_teto
import vida

bp = Blueprint("n3a_widget", __name__)

# Agenda do widget (2026-10-13): no maximo 6 itens de hoje; item que terminou ha mais de 30 min some.
AGENDA_MAX_ITENS = 6
AGENDA_TOLERANCIA_MIN = 30

# Rota maquina-a-maquina (token proprio, sem sessao/PIN) - ver
# rotas/__init__.py (infra da Etapa 0): `_verificar_autenticacao` libera
# estes caminhos sem login, e a PROPRIA rota abaixo checa o token.
ROTAS_COM_TOKEN = {"/api/widget", "/api/widget/erro"}
PREFIXOS_COM_TOKEN = ("/widget",)

VERSAO_WIDGET = 1


# --------------------------------------------------------------------------
# Token (header Authorization: Bearer OU ?token=, hmac.compare_digest)
# --------------------------------------------------------------------------


def _token_widget_esperado() -> str | None:
    return os.environ.get("PAINEL_WIDGET_TOKEN") or None


def _token_widget_enviado() -> str:
    cabecalho = request.headers.get("Authorization") or ""
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[len("Bearer ") :].strip()
    return (request.args.get("token") or "").strip()


def _token_widget_valido() -> bool:
    """True so com `PAINEL_WIDGET_TOKEN` configurado E batendo (header
    `Authorization: Bearer` OU `?token=`) em tempo constante
    (`hmac.compare_digest`). Sem token configurado no ambiente OU sem/com
    token errado na requisicao: sempre 401 ("401 sem/errado", conforme
    pedido da faixa) - diferente do padrao mais permissivo de
    `_token_atalho_valido` (app.py, que abre sem token pra uso local): aqui
    nao ha excecao que deixe o widget (dado pessoal) aberto pra quem achar a
    URL so porque ninguem configurou o token ainda.

    Nota: `docs/widget-widgy.md`/`docs/widget-api-widget.md` (faixa N3c/N3d,
    escritos antes deste endpoint existir) mencionam "sem token = funciona
    sem autenticacao" como possibilidade - esta implementacao NAO segue essa
    linha por decisao explicita de seguranca; se a leitura pretendida for a
    outra, e so tirar o `if not esperado: return False` abaixo."""
    esperado = _token_widget_esperado()
    if not esperado:
        return False
    enviado = _token_widget_enviado()
    if not enviado:
        return False
    return hmac.compare_digest(enviado.encode("utf-8"), esperado.encode("utf-8"))


# --------------------------------------------------------------------------
# Funcao pura (sem banco, sem Flask) - monta o JSON exato a partir de dados
# ja coletados. Testavel isolada, ver
# tests/test_fase7_n3a_widget_montagem.py.
# --------------------------------------------------------------------------


def _formatar_atualizado_em(agora_utc: datetime) -> str:
    return agora_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _linha_foco(foco: dict | None) -> str | None:
    if not foco:
        return None
    return f"Foco: {foco['titulo']} em {foco['em_minutos']} min"


def _linha_conta(conta: dict | None) -> str | None:
    if not conta:
        return None
    dias = conta["em_dias"]
    if dias is None:
        return f"Conta: {conta['nome']}"
    if dias < 0:
        return f"Conta: {conta['nome']} vencida ha {abs(dias)} dia(s)"
    if dias == 0:
        return f"Conta: {conta['nome']} vence hoje"
    return f"Conta: {conta['nome']} em {dias} dias"


def _linha_habitos(habitos: dict | None) -> str | None:
    if not habitos:
        return None
    return f"Habitos: {habitos['feitos']}/{habitos['total']}"


def _linha_custo_ia(custo_ia: dict | None) -> str | None:
    if not custo_ia:
        return None
    return f"IA: {custo_ia['percentual_teto']}% do teto"


def montar_widget(
    *,
    agora_utc: datetime,
    foco: dict | None = None,
    proxima_conta: dict | None = None,
    habitos: dict | None = None,
    custo_ia_percentual: float | None = None,
    mostrar_valores: bool = False,
    comida: dict | None = None,
    agenda: list | None = None,
) -> dict:
    """Monta o JSON EXATO do widget (ver docs/widget-widgy.md) a partir de
    dados ja coletados. Campo ausente vira `null` e a linha correspondente
    some de `linhas` - nunca uma chave faltando (o Widgy mapeia caminho fixo
    tipo `foco.titulo`, uma chave sumida quebraria o mapeamento).

    - `foco`: None ou {"titulo": str, "em_minutos": int}.
    - `proxima_conta`: None ou {"nome": str, "em_dias": int|None,
      "valor": float|None, "origem": "pessoal"|"construtora"}. "origem" e
      "valor" NUNCA vao pro JSON de saida quando a conta e da construtora
      (nunca dado financeiro real da empresa, mesmo com
      `mostrar_valores=True`) nem quando `mostrar_valores` e False (regra:
      sem valor em R$ por padrao, so com `?mostrar_valores=1`).
    - `habitos`: None ou {"feitos": int, "total": int} - so quando
      `total > 0` (dia sem nenhum habito devido nao tem o que mostrar).
    - `custo_ia_percentual`: None ou numero (pode passar de 100 com o teto
      ja estourado) - normalmente vem de `ia.teto`/`ia.medicao`.
    - `comida` (2026-10-13, widget do Scriptable): None ou {"kcal", "proteina_g", "carbo_g",
      "gordura_g", "refeicoes", "meta_kcal", "meta_proteina_g"} - o que ele comeu hoje pelas fotos
      do prato (refeicoes.py) contra a meta do perfil. Metas podem ser None (perfil sem peso).
      `carbo_g`/`gordura_g` saem inteiros (arredondados) e default 0.
    - `agenda` (2026-10-13): lista (sempre lista, `[]` quando nao ha nada) de compromissos/tarefas/
      habitos de hoje - ver `_coletar_agenda`. Cada item: {"hora", "titulo", "em_minutos", "tipo",
      "concluido"}. NAO entra em `linhas` (o widget desenha a agenda a parte). Lista nao vazia conta
      como dado pra `estado` "normal".

    `estado`: "normal" com pelo menos um campo preenchido, "vazio" sem
    nenhum dado pra mostrar (nunca "erro" aqui - erro e responsabilidade de
    quem coleta os dados, ver `estado_erro`)."""
    foco_out = {"titulo": foco["titulo"], "em_minutos": foco["em_minutos"]} if foco else None
    if foco_out and foco.get("hora"):
        foco_out["hora"] = foco["hora"]

    conta_out = None
    if proxima_conta:
        conta_out = {"nome": proxima_conta["nome"], "em_dias": proxima_conta["em_dias"]}
        if (
            mostrar_valores
            and proxima_conta.get("origem") != "construtora"
            and proxima_conta.get("valor") is not None
        ):
            conta_out["valor"] = proxima_conta["valor"]

    habitos_out = None
    if habitos and habitos.get("total"):
        habitos_out = {"feitos": habitos["feitos"], "total": habitos["total"]}

    custo_ia_out = None
    if custo_ia_percentual is not None:
        custo_ia_out = {"percentual_teto": round(custo_ia_percentual)}

    comida_out = None
    if comida and (comida.get("refeicoes") or comida.get("meta_kcal")):
        comida_out = {
            "kcal": round(comida.get("kcal") or 0),
            "proteina_g": round(comida.get("proteina_g") or 0),
            "carbo_g": round(comida.get("carbo_g") or 0),
            "gordura_g": round(comida.get("gordura_g") or 0),
            "refeicoes": int(comida.get("refeicoes") or 0),
            "meta_kcal": comida.get("meta_kcal"),
            "meta_proteina_g": comida.get("meta_proteina_g"),
        }

    agenda_out = list(agenda or [])

    tem_algo = any([foco_out, conta_out, habitos_out, custo_ia_out, comida_out, agenda_out])
    estado = "normal" if tem_algo else "vazio"

    linhas = [
        linha
        for linha in (
            _linha_foco(foco_out),
            _linha_conta(conta_out),
            _linha_habitos(habitos_out),
            _linha_custo_ia(custo_ia_out),
        )
        if linha
    ]

    return {
        "versao": VERSAO_WIDGET,
        "atualizado_em": _formatar_atualizado_em(agora_utc),
        "estado": estado,
        "foco": foco_out,
        "proxima_conta": conta_out,
        "habitos": habitos_out,
        "custo_ia": custo_ia_out,
        "comida": comida_out,
        "agenda": agenda_out,
        "linhas": linhas,
    }


def estado_erro(agora_utc: datetime) -> dict:
    """Mesmo formato de sempre (nenhuma chave falta), com `estado: "erro"`
    e tudo mais null/vazio - pro Widgy nunca receber uma chave sumida nem um
    500 cru. `GET /api/widget` sempre devolve 200 com este JSON quando a
    coleta de dados quebra por dentro (ver `coletar_resumo`)."""
    return {
        "versao": VERSAO_WIDGET,
        "atualizado_em": _formatar_atualizado_em(agora_utc),
        "estado": "erro",
        "foco": None,
        "proxima_conta": None,
        "habitos": None,
        "custo_ia": None,
        "comida": None,
        "agenda": None,
        "linhas": [],
    }


# --------------------------------------------------------------------------
# Coleta de dados - recebe o modulo app.py ja carregado (`app_mod`, o que
# `rotas._base.app_modulo()` devolve dentro da rota) por parametro, nunca
# importa `app` no topo do arquivo (import circular - ver rotas/_base.py).
# Injetar `app_mod` por parametro tambem deixa estas funcoes testaveis
# direto com `import app` (mesmo padrao de tests/test_app.py), sem precisar
# subir o Flask nem a infra de rotas/.
# --------------------------------------------------------------------------


def _coletar_foco(app_mod, conn, agora: datetime) -> dict | None:
    """Reaproveita `app._visao_do_dia_itens`/`app._proximo_item_em_foco` (o
    "item em foco agora" que ja alimenta `/api/visao-dia/hoje`) - so deriva
    os minutos (que a funcao original nao expoe, so o texto ja formatado
    'em 19 min') a partir do MESMO item escolhido, sem reimplementar a
    escolha em si."""
    hoje = agora.date()
    itens = app_mod._visao_do_dia_itens(conn, hoje)
    escolhido = app_mod._proximo_item_em_foco(itens, agora)
    if not escolhido:
        return None
    item = next(
        (i for i in itens if i.get("origem") == escolhido["origem"] and i.get("id") == escolhido["id"]),
        None,
    )
    if not item:
        return None
    try:
        inicio = datetime.fromisoformat(item["inicio"])
    except (KeyError, ValueError, TypeError):
        return None
    em_minutos = max(0, round((inicio - agora).total_seconds() / 60))
    return {"titulo": escolhido["titulo"], "em_minutos": em_minutos, "hora": inicio.strftime("%H:%M")}


def _coletar_comida(conn, hoje: date) -> dict | None:
    """O que ele comeu hoje pelas fotos do prato contra a meta do perfil (refeicoes.py faz a
    soma e a meta - nada recalculado aqui)."""
    import refeicoes

    tot = refeicoes.do_dia(conn, hoje)
    meta = refeicoes.meta_do_dia(conn, hoje)
    return {
        "kcal": tot["kcal"],
        "proteina_g": tot["proteina_g"],
        "carbo_g": tot["carbo_g"],
        "gordura_g": tot["gordura_g"],
        "refeicoes": tot["refeicoes"],
        "meta_kcal": meta["kcal"] if meta else None,
        "meta_proteina_g": meta["proteina_g"] if meta else None,
    }


def _ler_horario_local(valor) -> datetime | None:
    """ISO string -> datetime NAIVE na hora local (pra comparar com `agora`, que tambem e naive
    local). Item de calendario (iCloud) pode vir com fuso: convertido com `astimezone()` antes de
    tirar o tzinfo. Devolve None se nao der pra ler."""
    try:
        dt = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


_TIPO_AGENDA = {"tarefa": "tarefa", "habito": "habito"}


def _coletar_agenda(app_mod, conn, agora: datetime) -> list[dict]:
    """Agenda de hoje pro widget - reaproveita `app._visao_do_dia_itens` (mesma lista que
    `/api/visao-dia/hoje` usa), so filtra e formata. Pula item de dia inteiro e item cujo
    inicio/fim nao da pra ler. Mantem o que ainda nao terminou ou terminou ha no maximo
    `AGENDA_TOLERANCIA_MIN` minutos (concluido tambem entra, so com `concluido` True). Ordena por
    inicio e corta em `AGENDA_MAX_ITENS`. `em_minutos` nunca e negativo (item em andamento = 0)."""
    itens = app_mod._visao_do_dia_itens(conn, agora.date())
    limite_fim = agora - timedelta(minutes=AGENDA_TOLERANCIA_MIN)
    candidatos = []
    for item in itens:
        if item.get("dia_inteiro"):
            continue
        inicio = _ler_horario_local(item.get("inicio"))
        fim = _ler_horario_local(item.get("fim"))
        if inicio is None or fim is None:
            continue
        if fim < limite_fim:
            continue
        origem = item.get("origem")
        candidatos.append(
            (
                inicio,
                {
                    "hora": inicio.strftime("%H:%M"),
                    "titulo": str(item.get("titulo") or "").strip()[:60],
                    "em_minutos": max(0, round((inicio - agora).total_seconds() / 60)),
                    "tipo": _TIPO_AGENDA.get(origem, "compromisso"),
                    "concluido": bool(item.get("concluido")),
                },
            )
        )
    candidatos.sort(key=lambda par: par[0])
    return [saida for _, saida in candidatos[:AGENDA_MAX_ITENS]]


def _coletar_proxima_conta(app_mod, conn, hoje: date) -> dict | None:
    """Junta conta pessoal (`app._contas_pessoais_com_status`) e conta da
    construtora (`app._buscar_contas_a_vencer_construtora`, a mesma API
    read-only que `app._construtora_contexto_contas` ja consulta - ver
    AGENTS.md sobre os dois projetos) e devolve a mais proxima de vencer
    entre as duas fontes. Nunca devolve valor da construtora (dado
    financeiro real da empresa, so nome+dias)."""
    candidatas = []
    for c in app_mod._contas_pessoais_com_status(conn, hoje):
        if c.get("paga"):
            continue
        candidatas.append(
            {"nome": c["nome"], "em_dias": c["dias_ate_vencer"], "valor": c.get("valor"), "origem": "pessoal"}
        )

    dados = app_mod._buscar_contas_a_vencer_construtora(dias=30)
    if dados and dados.get("status") == "ok":
        contas = dados.get("contas") or []
        if contas:
            primeira = contas[0]
            nome = primeira.get("fornecedor") or primeira.get("descricao") or "fornecedor nao informado"
            candidatas.append(
                {
                    "nome": nome,
                    "em_dias": primeira.get("dias_ate_vencer"),
                    "valor": None,
                    "origem": "construtora",
                }
            )

    if not candidatas:
        return None
    candidatas.sort(key=lambda c: c["em_dias"] if c["em_dias"] is not None else float("inf"))
    return candidatas[0]


def _coletar_habitos(conn, dia: date, semana_de) -> dict | None:
    """Mesma logica de habito devido/feito que `app._contagem_dia` usa, so
    isolada (sem somar com tarefa/evento) - `db.list_habitos`/
    `db.marcacoes_habito_no_periodo`/`db.habito_marcado` e
    `vida.habito_devido_em` sao as MESMAS funcoes que `app.py` chama, nada
    recalculado aqui. `semana_de` e `app._semana_de` (injetado por
    parametro pelo mesmo motivo de `_coletar_foco`/`_coletar_proxima_conta`
    acima)."""
    ini_semana, fim_semana = semana_de(dia)
    dia_iso = dia.isoformat()
    total = 0
    feitos = 0
    for h in db.list_habitos(conn):
        vezes_feitas_semana = len(db.marcacoes_habito_no_periodo(conn, h["id"], ini_semana, fim_semana))
        if not vida.habito_devido_em(h, dia, vezes_feitas_semana):
            continue
        total += 1
        if db.habito_marcado(conn, dia_iso, h["id"]):
            feitos += 1
    if total == 0:
        return None
    return {"feitos": feitos, "total": total}


def _coletar_custo_ia_percentual() -> float | None:
    """`custo_ia.percentual_teto` vem de `ia.teto`/`ia.medicao` (fracao
    gasto-do-mes/teto-do-mes, ja calculada por `ia.teto._fracao_teto` -
    reaproveitada, nao recalculada aqui). Pode passar de 100 com o teto ja
    estourado (o Widgy/HTML decide como mostrar isso, o numero cru vai
    inteiro)."""
    return ia_teto._fracao_teto() * 100


def coletar_resumo(app_mod, mostrar_valores: bool = False) -> dict:
    """Coleta tudo (abre/fecha a propria conexao) e monta o JSON final via
    `montar_widget`. QUALQUER excecao na coleta vira `estado: "erro"` (nunca
    deixa subir - `GET /api/widget` e `GET /widget` sempre respondem, nunca
    um 500 cru pro widget/pagina)."""
    agora_utc = datetime.now(timezone.utc)
    try:
        agora_local = datetime.now()
        hoje = agora_local.date()
        conn = db.get_db()
        try:
            foco = _coletar_foco(app_mod, conn, agora_local)
            proxima_conta = _coletar_proxima_conta(app_mod, conn, hoje)
            habitos = _coletar_habitos(conn, hoje, app_mod._semana_de)
            try:
                comida = _coletar_comida(conn, hoje)
            except Exception:
                comida = None  # comida e extra - nunca derruba o resto do widget
            try:
                agenda = _coletar_agenda(app_mod, conn, agora_local)
            except Exception:
                agenda = []  # agenda e extra - nunca derruba o resto do widget
        finally:
            conn.close()
        custo_ia_percentual = _coletar_custo_ia_percentual()
        return montar_widget(
            agora_utc=agora_utc,
            foco=foco,
            proxima_conta=proxima_conta,
            habitos=habitos,
            custo_ia_percentual=custo_ia_percentual,
            mostrar_valores=mostrar_valores,
            comida=comida,
            agenda=agenda,
        )
    except Exception:
        return estado_erro(agora_utc)


# --------------------------------------------------------------------------
# Diagnostico (2026-10-13, 1o teste no iPhone: "nao apareceu nada"): cada chamada das rotas do
# widget vira uma linha em data/widget.log (data/ ja fica fora do git) - hora, rota, status e app
# que chamou. NUNCA o token: so o caminho, sem query string. O script do Scriptable tambem manda
# o proprio erro pra /api/widget/erro, que cai no mesmo arquivo.
# --------------------------------------------------------------------------

_LOG_WIDGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "widget.log")


def _registrar_log_widget(linha: str) -> None:
    try:
        os.makedirs(os.path.dirname(_LOG_WIDGET), exist_ok=True)
        if os.path.exists(_LOG_WIDGET) and os.path.getsize(_LOG_WIDGET) > 512 * 1024:
            os.replace(_LOG_WIDGET, _LOG_WIDGET + ".1")
        with open(_LOG_WIDGET, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {linha}\n")
    except OSError:
        pass  # log e so diagnostico - nunca derruba o widget


@bp.after_request
def _log_widget(resposta):
    agente = (request.headers.get("User-Agent") or "-").replace("\n", " ")[:120]
    _registrar_log_widget(f"{request.method} {request.path} -> {resposta.status_code} | {agente}")
    return resposta


@bp.route("/api/widget/erro", methods=["POST"])
def widget_erro():
    """O script do Scriptable manda aqui o erro que aconteceu no iPhone (mesmo token do widget)."""
    if not _token_widget_valido():
        return jsonify({"error": "token invalido"}), 401
    dados = request.get_json(silent=True) or {}
    msg = " ".join(str(dados.get(k) or "") for k in ("etapa", "erro", "familia")).replace("\n", " ")[:500]
    _registrar_log_widget(f"ERRO DO SCRIPT: {msg}")
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Rotas. `app_modulo()` e importado DENTRO de cada rota (nunca no topo do
# arquivo) - ver rotas/_base.py (infra da Etapa 0, evita import circular
# com app.py, que ainda esta sendo importado quando registra os blueprints).
# --------------------------------------------------------------------------


def _sessao_do_painel_valida(app) -> bool:
    """2026-10-22 (app iOS nativo): o app WKWebView ja esta logado no painel pelo PIN - a sessao
    assinada vale tambem aqui. Modo visitante nunca (o widget e dado pessoal)."""
    from flask import session

    return bool(session.get("autenticado")) and not app._modo_visitante_ativo()


@bp.route("/api/widget", methods=["GET"])
def widget_api():
    from rotas._base import app_modulo

    if not _token_widget_valido() and not _sessao_do_painel_valida(app_modulo()):
        return jsonify({"error": "token invalido"}), 401

    mostrar_valores = request.args.get("mostrar_valores") == "1"
    resumo = coletar_resumo(app_modulo(), mostrar_valores=mostrar_valores)
    return jsonify(resumo)


@bp.route("/api/widget/instalacao", methods=["GET"])
def widget_instalacao():
    """2026-10-13: Configurações > "Widget do iPhone" - entrega o script do Scriptable e o token
    pro Alex COPIAR no proprio iPhone (sem passar arquivo/senha do PC pro celular na mao).
    Rota NORMAL (sessao/PIN - nao esta em ROTAS_COM_TOKEN) e recusada no modo visitante, porque
    devolve o token. O endereco (URL) quem monta e o navegador (location.origin), que e
    exatamente o que o iPhone ja usa pra chegar no painel."""
    from rotas._base import app_modulo

    recusa = app_modulo()._recusar_no_modo_visitante()
    if recusa:
        return recusa
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scriptable", "scriptable-widget.js")
    try:
        with open(caminho, encoding="utf-8") as f:
            script = f.read()
    except OSError:
        return jsonify({"error": "script do widget não encontrado"}), 500
    token = _token_widget_esperado()
    return jsonify({"configurado": bool(token), "token": token, "script": script})


@bp.route("/widget", methods=["GET"])
def widget_pagina():
    if not _token_widget_valido():
        return "token invalido", 401

    from rotas._base import app_modulo

    mostrar_valores = request.args.get("mostrar_valores") == "1"
    resumo = coletar_resumo(app_modulo(), mostrar_valores=mostrar_valores)
    return render_template("widget.html", r=resumo)
