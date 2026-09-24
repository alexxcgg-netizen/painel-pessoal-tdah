"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao
visual da v6-financas (Gastos, Bancos, Construtora).
Uso: PORTA=5194 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v6-financas/servidor.py <repo>
"""
import os
import sys
import tempfile
from pathlib import Path

repo = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL"):
    os.environ.pop(k, None)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-teste-falso")  # dublê: nenhuma chamada real
# API da construtora em modo mock (pedido do prompt da faixa) - dados sinteticos,
# sem chamada de rede real. So construtora_cliente.py (faixa A10) sabe ler esta
# flag; a rota GET /api/construtora/resumo ainda usada por construtora.js
# (app.py, compartilhado, nao editado por esta faixa) so olha
# CONSTRUTORA_API_URL/CONSTRUTORA_API_KEY - sem essas duas, cai no estado
# "nao configurado" (tela vazia graciosa, sem crash) - ver
# scripts/ralph-v6-financas/APRENDIZADOS.md #5.
os.environ["CONSTRUTORA_API_MOCK"] = "1"
import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="v6-financas-db-")) / "painel.db"
db.garantir_banco_nao_producao()
import app  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5194")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
