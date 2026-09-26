"""Blueprint seguranca - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rotas._base import app_modulo
import criptografia

bp = Blueprint("seguranca", __name__)


@bp.route("/api/seguranca/status", methods=["GET"])
def seguranca_status():
    """Rota de diagnostico: diz se a criptografia em repouso (Open Finance +
    saude) esta ligada agora. Ver docs/SEGURANCA.md. Sem ENCRYPTION_KEY
    configurada, o app segue funcionando normalmente (decisao de design
    documentada) mas os campos sensiveis ficam em texto plano no banco -
    esta rota existe pra isso nunca ficar escondido, so silencioso no log."""
    ativa = criptografia.configurada()
    return jsonify(
        {
            "criptografia_ativa": ativa,
            "aviso": (
                None
                if ativa
                else (
                    "ENCRYPTION_KEY nao configurada - dado do Open Finance e de saude esta "
                    "em texto plano no banco. Rode python scripts/gerar_chave_criptografia.py."
                )
            ),
        }
    )
