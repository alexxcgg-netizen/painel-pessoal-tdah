"""Blueprint backup - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, send_file

from rotas._base import app_modulo
from db import get_db
import csv
import db
import io
import json
import os
import sqlite3
import tempfile
import zipfile

bp = Blueprint("backup", __name__)

@bp.route("/api/backup/exportar", methods=["GET"])
def exportar_backup():
    """Baixa uma copia consistente do banco inteiro - usa a API de backup do
    proprio sqlite3 (nao uma copia de arquivo crua), que tira um snapshot
    seguro mesmo com o banco em uso, sem lock nem risco de arquivo pela
    metade. Mesmo habito de backup do financeiro-construtora (AGENTS.md de
    la), aqui como export manual sob demanda em vez de automatico antes de
    escrita."""
    app = app_modulo()
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    origem = sqlite3.connect(db.DB_PATH)
    destino = sqlite3.connect(tmp.name)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

    nome_arquivo = f"painel-backup-{date.today().isoformat()}.db"
    resposta = send_file(tmp.name, as_attachment=True, download_name=nome_arquivo, mimetype="application/octet-stream")
    resposta.call_on_close(lambda: os.unlink(tmp.name))
    return resposta

@bp.route("/api/backup/exportar-json", methods=["GET"])
def exportar_backup_json():
    """Export completo em JSON de TODAS as tabelas do banco (nao so gastos) -
    pensado pra restaurar o painel inteiro depois, diferente do
    /api/expenses/exportar-csv (so gastos, pra planilha) e do
    /api/backup/exportar (.db bruto, so restaura via SQLite direto)."""
    app = app_modulo()
    VERSAO_EXPORT_JSON = app.VERSAO_EXPORT_JSON
    _exportar_tabelas_dict = app._exportar_tabelas_dict
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    datetime = app.datetime
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
    conn = get_db()
    try:
        tabelas = _exportar_tabelas_dict(conn)
    finally:
        conn.close()

    corpo = {
        "versao": VERSAO_EXPORT_JSON,
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
        "tabelas": tabelas,
    }
    nome_arquivo = f"painel-backup-{date.today().isoformat()}.json"
    return Response(
        json.dumps(corpo, ensure_ascii=False, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )

@bp.route("/api/backup/exportar-csv-completo", methods=["GET"])
def exportar_backup_csv_completo():
    """Export completo em CSV de TODAS as tabelas, um .csv por tabela dentro
    de um .zip - diferente do JSON (uma estrutura relacional so faz sentido
    achatada em varios arquivos, nao um CSV unico) e do
    /api/expenses/exportar-csv (so gastos)."""
    app = app_modulo()
    _exportar_tabelas_dict = app._exportar_tabelas_dict
    _modo_visitante_ativo = app._modo_visitante_ativo
    date = app.date
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
    conn = get_db()
    try:
        tabelas = _exportar_tabelas_dict(conn)
    finally:
        conn.close()

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, linhas in tabelas.items():
            buffer_csv = io.StringIO()
            writer = csv.writer(buffer_csv)
            if linhas:
                colunas = list(linhas[0].keys())
                writer.writerow(colunas)
                for linha in linhas:
                    writer.writerow([linha[c] for c in colunas])
            # tabela vazia ainda gera um .csv (sem cabecalho, ja que sem
            # linhas nao da pra saber as colunas so pelo select) - melhor um
            # arquivo vazio presente do que a tabela sumir silenciosamente
            # do zip
            zf.writestr(f"{nome}.csv", buffer_csv.getvalue())
    buffer_zip.seek(0)

    nome_arquivo = f"painel-backup-csv-{date.today().isoformat()}.zip"
    resposta = send_file(
        buffer_zip,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/zip",
    )
    return resposta
