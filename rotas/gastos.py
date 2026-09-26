"""Blueprint gastos - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from rotas._base import app_modulo
from db import atualizar_categoria_gasto, gasto_mes_por_categoria, get_db, list_incomes, list_orcamentos, reclassificar_gasto_para_tarefa, registrar_correcao_classificacao
import aprendizado
import csv
import gastos
import io
import vida

bp = Blueprint("gastos", __name__)

@bp.route("/api/capture", methods=["POST"])
def capture():
    app = app_modulo()
    _corpo_json = app._corpo_json
    _executar_captura = app._executar_captura
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    text = _texto_seguro(body.get("text"))
    clarificacao = _texto_seguro(body.get("clarificacao"))
    client_id = _texto_seguro(body.get("client_id"))[:64]  # UUID cabe sobra; so um teto de sanidade
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, clarificacao, client_id)

@bp.route("/api/intent/classificar", methods=["POST"])
def intent_classificar():
    """Classifica um comando de voz/texto numa acao (contrato em
    docs/INTENT.md) - ver _classificar_intent pra logica de verdade."""
    app = app_modulo()
    _classificar_intent = app._classificar_intent
    _corpo_json = app._corpo_json
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    if not texto:
        return jsonify({"error": "texto vazio"}), 400

    conn = get_db()
    resultado, error = _classificar_intent(conn, texto)
    if error:
        conn.close()
        return error
    conn.commit()
    conn.close()
    return jsonify(resultado)

@bp.route("/api/intent/corrigir", methods=["POST"])
def intent_corrigir():
    """US-B3: quando o dialogo de voz de 2 turnos (UI, voz-comando.js) tem uma
    correcao confirmada pelo Alex pro texto original, isso alimenta o mesmo
    banco de padroes aprendidos do resto do intent (US-A3/US-A4) - reusa
    aprendizado.confirmar_padrao_intent com forcar_confianca_alta=True (mesmo
    espirito de uma correcao manual de captura, US-A4): uma correcao vale
    como sinal forte na hora, sem precisar repetir o erro 3x.

    Modo visitante: 403 (revisao da Fase 6) - um padrao aprendido muda como
    o chat responde depois (envenenamento do banco local)."""
    app = app_modulo()
    ACOES_INTENT = app.ACOES_INTENT
    _corpo_json = app._corpo_json
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    _texto_seguro = app._texto_seguro
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    acao_correta = body.get("acao_correta")
    parametros = body.get("parametros")
    if not isinstance(parametros, dict):
        parametros = {}

    if not texto:
        return jsonify({"error": "texto vazio"}), 400
    if acao_correta not in ACOES_INTENT:
        return jsonify({"error": "acao_correta invalida"}), 400

    conn = get_db()
    aprendizado.confirmar_padrao_intent(conn, texto, acao_correta, parametros, forcar_confianca_alta=True)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/expenses/<int:expense_id>/reclassificar", methods=["POST"])
def reclassificar_gasto_rota(expense_id):
    """Correcao rapida: a IA classificou como gasto algo que na verdade era
    tarefa. Campos de prazo sao opcionais (o corpo do gasto raramente tem
    essa informacao - fica null, como uma tarefa sem prazo definido)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _normalizar_hora = app._normalizar_hora
    corpo = _corpo_json()
    due_at = corpo.get("quando") if isinstance(corpo.get("quando"), str) else None
    due_date = corpo.get("quando_data") if isinstance(corpo.get("quando_data"), str) else None
    hora = _normalizar_hora(corpo.get("hora"))

    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        return jsonify({"error": "gasto nao encontrado"}), 404

    novo_id = reclassificar_gasto_para_tarefa(conn, expense_id, due_at, due_date, hora)
    registrar_correcao_classificacao(
        conn, expense["source_text"] or expense["description"], "gasto", expense["category"], "tarefa", None
    )
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"ok": True, "novo_id": novo_id})

@bp.route("/api/expenses/<int:expense_id>/categoria", methods=["POST"])
def corrigir_categoria_gasto_rota(expense_id):
    """Correcao rapida: so a categoria do gasto saiu errada, tipo continua
    certo - nao precisa mover linha nenhuma entre tabelas."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _texto_seguro = app._texto_seguro
    corpo = _corpo_json()
    categoria = _texto_seguro(corpo.get("categoria"))
    if not categoria:
        return jsonify({"error": "categoria vazia"}), 400

    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        return jsonify({"error": "gasto nao encontrado"}), 404

    categoria_antiga = expense["category"]
    atualizar_categoria_gasto(conn, expense_id, categoria)
    if categoria_antiga != categoria:
        registrar_correcao_classificacao(
            conn,
            expense["source_text"] or expense["description"],
            "gasto",
            categoria_antiga,
            "gasto",
            categoria,
        )
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/expenses", methods=["GET"])
def list_expenses():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@bp.route("/api/incomes", methods=["GET"])
def list_incomes_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    rows = list_incomes(conn, limit=50)
    conn.close()
    return jsonify(rows)

@bp.route("/api/orcamentos", methods=["GET"])
def list_orcamentos_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    orcamentos = list_orcamentos(conn)
    ano_mes = date.today().strftime("%Y-%m")
    for o in orcamentos:
        o["gasto_mes"] = gasto_mes_por_categoria(conn, o["categoria"], ano_mes)
    conn.close()
    return jsonify(orcamentos)

@bp.route("/api/gastos-fixos", methods=["GET"])
def gastos_fixos_rota():
    app = app_modulo()
    _gastos_fixos = app._gastos_fixos
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = _gastos_fixos(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/sobra-do-mes", methods=["GET"])
def sobra_do_mes_rota():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    _sobra_do_mes = app._sobra_do_mes
    date = app.date
    if _modo_visitante_ativo():
        hoje = date.today()
        return jsonify(
            {**gastos.sobra_do_mes(0, 0, 0), "projecao": vida.projecao_fim_do_mes(0, 0, 0, hoje)}
        )
    conn = get_db()
    resultado = _sobra_do_mes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/expenses/historico", methods=["GET"])
def expenses_historico():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify([])
    dias = request.args.get("dias", default=14, type=int)
    dias = min(max(dias, 1), 90)
    conn = get_db()
    rows = conn.execute("SELECT amount, created_at FROM expenses WHERE tipo = 'real'").fetchall()
    conn.close()
    historico = gastos.historico_diario([dict(r) for r in rows], dias, date.today())
    return jsonify(historico)

@bp.route("/api/expenses/exportar-csv", methods=["GET"])
def exportar_expenses_csv():
    """CSV de todos os gastos (real e planejado) - sem limite de 50 como o
    /api/expenses normal, essa e feita pra abrir na planilha, nao pra tela."""
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
    conn = get_db()
    rows = conn.execute(
        "SELECT created_at, amount, category, tipo, description FROM expenses ORDER BY created_at"
    ).fetchall()
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["data", "valor", "categoria", "tipo", "descricao"])
    for r in rows:
        writer.writerow([r["created_at"], r["amount"], r["category"], r["tipo"], r["description"] or ""])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=gastos.csv"},
    )

@bp.route("/api/gastos/resumo-semanal", methods=["GET"])
def gastos_resumo_semanal():
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify(gastos.resumo_semanal([], date.today()))
    conn = get_db()
    rows = conn.execute(
        "SELECT amount, category, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    conn.close()
    return jsonify(gastos.resumo_semanal([dict(r) for r in rows], date.today()))
