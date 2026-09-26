"""Blueprint braindump - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
from db import apagar_brain_dump, create_brain_dump, create_nota, criar_gasto_de_brain_dump, criar_tarefa_de_brain_dump, get_db, list_brain_dump_pendentes, marcar_brain_dump_processado, obter_brain_dump
import cards
import math
import time

bp = Blueprint("braindump", __name__)

@bp.route("/api/brain-dump", methods=["GET"])
def brain_dump_pendentes():
    conn = get_db()
    resultado = list_brain_dump_pendentes(conn)
    conn.close()
    return jsonify(resultado)

@bp.route("/api/brain-dump", methods=["POST"])
def capturar_brain_dump():
    app = app_modulo()
    MSG_TEXTO_LONGO = app.MSG_TEXTO_LONGO
    TAMANHO_MAX_TEXTO_CHAT = app.TAMANHO_MAX_TEXTO_CHAT
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    _texto_seguro = app._texto_seguro
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    if not texto:
        return jsonify({"error": "manda algum texto"}), 400
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": MSG_TEXTO_LONGO}), 400

    conn = get_db()
    item_id = create_brain_dump(conn, texto)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": item_id, "ok": True}), 201

@bp.route("/api/brain-dump/<int:item_id>/converter", methods=["POST"])
def converter_brain_dump(item_id):
    """Converte um item pendente em tarefa/nota/gasto de verdade -
    reaproveita create_nota (ja existente) e dois inserts minimos pra tarefa/
    gasto (criar_tarefa_de_brain_dump/criar_gasto_de_brain_dump, mesmo
    formato das rotas que ja existem pra cada tipo, so sem passar pela
    classificacao por IA - o Alex ja escolheu o tipo na hora de converter).

    Fase 6 (US-E6): tipo "assistente" manda o texto inteiro pro MESMO
    pipeline do chat (_processar_mensagem_chat - tool-use + cards), entao um
    despejo com viagem, gastos, salario, habito, lembrete e reuniao
    misturados vira um card por item + resumo_final, com Desfazer
    independente em cada card. Toda saida (qualquer tipo) segue o contrato
    de docs/CARDS.md, alem dos campos antigos (ok/tipo/id).

    Modo visitante: 403 (revisao da Fase 6) - cria gasto/tarefa/evento de
    uma vez."""
    app = app_modulo()
    TETO_IA_MSG = app.TETO_IA_MSG
    _corpo_json = app._corpo_json
    _criar_token_desfazer = app._criar_token_desfazer
    _marcar_atividade = app._marcar_atividade
    _normalizar_hora = app._normalizar_hora
    _processar_mensagem_chat = app._processar_mensagem_chat
    _recusar_no_modo_visitante = app._recusar_no_modo_visitante
    _resposta_contrato = app._resposta_contrato
    _texto_seguro = app._texto_seguro
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    tipo = body.get("tipo")
    if tipo not in ("tarefa", "nota", "gasto", "assistente"):
        return jsonify({"error": "tipo precisa ser tarefa, nota, gasto ou assistente"}), 400

    conn = get_db()
    item = obter_brain_dump(conn, item_id)
    if not item:
        conn.close()
        return jsonify({"error": "item não encontrado"}), 404
    if item["processado"]:
        conn.close()
        return jsonify({"error": "item já foi processado"}), 400

    if tipo == "assistente":
        # reserva o item ANTES da IA (dois toques ao mesmo tempo nao
        # processam o mesmo despejo duas vezes); devolve se a IA falhar.
        if not marcar_brain_dump_processado(conn, item_id):
            conn.close()
            return jsonify({"error": "item já foi processado"}), 400
        detalhes: dict = {}
        resposta, acoes, erro = _processar_mensagem_chat(conn, item["texto"], detalhes)
        if erro:
            conn.execute("UPDATE brain_dump SET processado = 0 WHERE id = ?", (item_id,))
            conn.commit()
            conn.close()
            return jsonify({"error": erro}), 402 if erro == TETO_IA_MSG else 502
        _marcar_atividade(conn)
        conn.commit()
        conn.close()
        corpo = {"ok": True, "tipo": tipo, "resposta": resposta, "acoes": acoes}
        corpo.update(detalhes or cards.envelope([], resposta, []))
        return jsonify(_resposta_contrato(corpo))

    inicio = time.perf_counter()
    efeitos = []
    if tipo == "tarefa":
        titulo = _texto_seguro(body.get("titulo")) or item["texto"]
        novo_id = criar_tarefa_de_brain_dump(
            conn, titulo, body.get("due_date"), _normalizar_hora(body.get("hora")), item["texto"]
        )
        efeitos.append({"entidade": "tarefa", "id": novo_id})
        passo = {"modulo": "Tarefas", "descricao": f'Criou a tarefa "{cards._titulo_curto(titulo)}"'}
        resumo = "Virou tarefa."
    elif tipo == "nota":
        titulo = _texto_seguro(body.get("titulo")) or item["texto"][:60]
        novo_id = create_nota(conn, titulo, body.get("corpo") or item["texto"], source_text=item["texto"])
        passo = {"modulo": "Notas", "descricao": f'Salvou a nota "{cards._titulo_curto(titulo)}"'}
        resumo = "Virou nota."
    else:
        valor = body.get("valor")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool) or not math.isfinite(valor) or valor <= 0:
            conn.close()
            return jsonify({"error": "informe um valor valido pro gasto"}), 400
        descricao = _texto_seguro(body.get("titulo")) or item["texto"]
        novo_id = criar_gasto_de_brain_dump(conn, valor, body.get("categoria"), descricao, item["texto"])
        efeitos.append({"entidade": "gasto", "id": novo_id})
        passo = {"modulo": "Finanças", "descricao": f'Registrou o gasto "{cards._titulo_curto(descricao)}"'}
        resumo = "Virou gasto."
    passo["ms"] = int(round((time.perf_counter() - inicio) * 1000))

    marcar_brain_dump_processado(conn, item_id)
    _marcar_atividade(conn)
    corpo = {"ok": True, "tipo": tipo, "id": novo_id}
    corpo.update(cards.montar_resposta(conn, efeitos, resumo, [passo], _criar_token_desfazer(conn)))
    conn.commit()
    conn.close()
    return jsonify(_resposta_contrato(corpo))

@bp.route("/api/brain-dump/<int:item_id>", methods=["DELETE"])
def apagar_brain_dump_rota(item_id):
    conn = get_db()
    apagar_brain_dump(conn, item_id)
    conn.close()
    return jsonify({"ok": True})
