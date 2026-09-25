"""Faixa N1 (Fase 7): rotas de assinaturas/compras parceladas. Sessao (PIN
normal, sem token proprio) - a autenticacao e GLOBAL
(`@app.before_request`/`_verificar_autenticacao` em `app.py`) e cobre
qualquer rota de Blueprint que `rotas.registrar_todas` registrar, entao este
arquivo nao declara `ROTAS_COM_TOKEN`. Contrato completo (formato de
entrada/saida de cada rota) em `docs/contrato-assinaturas.md`.

Registrado automaticamente por `rotas.registrar_todas(app)` (infra da Etapa
0/X1, `rotas/__init__.py`) assim que `app.py` sobe - nenhum registro manual
aqui. Import de `db` no topo (nao `rotas._base.app_modulo()`): `db.get_db`
nao tem import circular com este arquivo (`db.py` nao importa `rotas`), so
os helpers que vivem DENTRO de `app.py` precisariam disso."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

import db
import financas_recorrentes as fr

bp = Blueprint("n1_financas", __name__)


def _corpo_json() -> dict:
    """Mesma defesa de `app._corpo_json`: corpo ausente/tipo errado vira
    dict vazio em vez de derrubar a rota com 500."""
    corpo = request.get_json(silent=True)
    return corpo if isinstance(corpo, dict) else {}


def _erro(mensagem: str, status: int = 400):
    return jsonify({"error": mensagem}), status


# =============================================================================
# Assinaturas
# =============================================================================


@bp.route("/api/financas/assinaturas", methods=["GET"])
def listar_assinaturas():
    apenas_ativas = request.args.get("ativas") in ("1", "true", "True")
    conn = db.get_db()
    try:
        resultado = fr.listar_assinaturas(conn, apenas_ativas=apenas_ativas)
        hoje = date.today()
        for a in resultado:
            proxima = fr.proxima_cobranca_assinatura(a, hoje)
            a["proxima_cobranca"] = proxima.isoformat() if proxima else None
    finally:
        conn.close()
    return jsonify({"assinaturas": resultado})


@bp.route("/api/financas/assinaturas/<int:id_>", methods=["GET"])
def obter_assinatura(id_: int):
    conn = db.get_db()
    try:
        a = fr.obter_assinatura(conn, id_)
    finally:
        conn.close()
    if not a:
        return _erro("assinatura nao encontrada", 404)
    return jsonify(a)


@bp.route("/api/financas/assinaturas", methods=["POST"])
def criar_assinatura():
    corpo = _corpo_json()
    nome = corpo.get("nome")
    valor = corpo.get("valor")
    dia_cobranca = corpo.get("dia_cobranca")
    if not isinstance(nome, str) or not nome.strip():
        return _erro("nome obrigatorio")
    if valor is None:
        return _erro("valor obrigatorio")
    if not isinstance(dia_cobranca, int):
        return _erro("dia_cobranca obrigatorio (inteiro entre 1 e 31)")

    conn = db.get_db()
    try:
        aid = fr.criar_assinatura(
            conn,
            nome,
            valor,
            dia_cobranca,
            cartao_ou_forma=corpo.get("cartao_ou_forma"),
            categoria=corpo.get("categoria"),
            inicio=corpo.get("inicio"),
            observacao=corpo.get("observacao"),
        )
        a = fr.obter_assinatura(conn, aid)
    except ValueError as e:
        conn.close()
        return _erro(str(e))
    conn.close()
    return jsonify(a), 201


@bp.route("/api/financas/assinaturas/<int:id_>", methods=["PATCH"])
def atualizar_assinatura(id_: int):
    corpo = _corpo_json()
    conn = db.get_db()
    try:
        alterou = fr.atualizar_assinatura(conn, id_, **corpo)
    except ValueError as e:
        conn.close()
        return _erro(str(e))
    if not alterou:
        conn.close()
        return _erro("assinatura nao encontrada ou nada pra alterar", 404)
    a = fr.obter_assinatura(conn, id_)
    conn.close()
    return jsonify(a)


@bp.route("/api/financas/assinaturas/<int:id_>/avisar_antes_cobrar", methods=["POST"])
def alternar_aviso_cobranca(id_: int):
    """Fase 8/F3: liga/desliga o aviso proativo (3/2/1 dia antes) desta
    assinatura. Desligado por padrao - so quem ligar aqui recebe aviso
    (assistente/gatilhos/f8_aviso_cobranca.py)."""
    corpo = _corpo_json()
    ligado = bool(corpo.get("ligado"))
    conn = db.get_db()
    fr.atualizar_assinatura(conn, id_, avisar_antes_cobrar=ligado)
    a = fr.obter_assinatura(conn, id_)
    conn.close()
    if not a:
        return _erro("assinatura nao encontrada", 404)
    return jsonify(a)


@bp.route("/api/financas/assinaturas/<int:id_>/cancelar", methods=["POST"])
def cancelar_assinatura(id_: int):
    conn = db.get_db()
    ok = fr.cancelar_assinatura(conn, id_)
    if not ok:
        conn.close()
        return _erro("assinatura nao encontrada ou ja cancelada", 404)
    a = fr.obter_assinatura(conn, id_)
    conn.close()
    return jsonify(a)


@bp.route("/api/financas/assinaturas/<int:id_>", methods=["DELETE"])
def excluir_assinatura(id_: int):
    conn = db.get_db()
    ok = fr.excluir_assinatura(conn, id_)
    conn.close()
    if not ok:
        return _erro("assinatura nao encontrada", 404)
    return jsonify({"ok": True})


# =============================================================================
# Compras parceladas
# =============================================================================


@bp.route("/api/financas/parcelas", methods=["GET"])
def listar_parcelas():
    em_andamento = request.args.get("em_andamento") in ("1", "true", "True")
    conn = db.get_db()
    try:
        hoje = date.today()
        resultado = fr.listar_compras_parceladas(conn, apenas_em_andamento=em_andamento, hoje=hoje)
        for c in resultado:
            c.update(fr.parcela_info(c, hoje))
    finally:
        conn.close()
    return jsonify({"parcelas": resultado})


@bp.route("/api/financas/parcelas/<int:id_>", methods=["GET"])
def obter_parcela(id_: int):
    conn = db.get_db()
    try:
        c = fr.obter_compra_parcelada(conn, id_)
        if c:
            c.update(fr.parcela_info(c, date.today()))
    finally:
        conn.close()
    if not c:
        return _erro("compra parcelada nao encontrada", 404)
    return jsonify(c)


@bp.route("/api/financas/parcelas", methods=["POST"])
def criar_parcela():
    corpo = _corpo_json()
    descricao = corpo.get("descricao")
    n_parcelas = corpo.get("n_parcelas")
    if not isinstance(descricao, str) or not descricao.strip():
        return _erro("descricao obrigatoria")
    if not isinstance(n_parcelas, int):
        return _erro("n_parcelas obrigatorio (inteiro positivo)")
    if corpo.get("valor_total") is None and corpo.get("valor_parcela") is None:
        return _erro("informe valor_total ou valor_parcela")

    conn = db.get_db()
    try:
        cid = fr.criar_compra_parcelada(
            conn,
            descricao,
            n_parcelas,
            valor_total=corpo.get("valor_total"),
            valor_parcela=corpo.get("valor_parcela"),
            cartao=corpo.get("cartao"),
            primeira_parcela=corpo.get("primeira_parcela"),
            categoria=corpo.get("categoria"),
        )
        c = fr.obter_compra_parcelada(conn, cid)
        c.update(fr.parcela_info(c, date.today()))
    except ValueError as e:
        conn.close()
        return _erro(str(e))
    conn.close()
    return jsonify(c), 201


@bp.route("/api/financas/parcelas/<int:id_>", methods=["DELETE"])
def excluir_parcela(id_: int):
    conn = db.get_db()
    ok = fr.excluir_compra_parcelada(conn, id_)
    conn.close()
    if not ok:
        return _erro("compra parcelada nao encontrada", 404)
    return jsonify({"ok": True})


# =============================================================================
# Resumo (tela do cartao) + Desfazer local
# =============================================================================


@bp.route("/api/financas/comprometido", methods=["GET"])
def comprometido():
    """Resumo pra tela do cartao (US N1): total mensal comprometido,
    proximas cobrancas e o impacto no limite de cada cartao citado nos
    proximos 6 meses. Ver `docs/contrato-assinaturas.md`."""
    hoje = date.today()
    conn = db.get_db()
    try:
        resultado = {
            "total_mensal": fr.total_mensal_comprometido(conn, hoje),
            "proximas_cobrancas": fr.proximas_cobrancas(conn, hoje),
            "impacto_limite_cartao": fr.impacto_limite_cartao_proximos_meses(conn, hoje),
        }
    finally:
        conn.close()
    return jsonify(resultado)


@bp.route("/api/financas/desfazer/<token>", methods=["POST"])
def desfazer(token: str):
    """Desfazer PROPRIO desta faixa (ver a nota em
    `financas_recorrentes.aplicar_desfazer` - `db.ENTIDADES_DESFAZIVEIS`
    ainda nao conhece assinatura/compra_parcelada, entao nao da pra usar a
    rota generica `/api/desfazer/<token>` ainda)."""
    conn = db.get_db()
    try:
        resultado = fr.aplicar_desfazer(conn, token)
    finally:
        conn.close()
    status = resultado.pop("status")
    return jsonify(resultado), status
