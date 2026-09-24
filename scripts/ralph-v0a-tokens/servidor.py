"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao visual da V0a.
Uso: PORTA=5170 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v0a-tokens/servidor.py <repo>
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
import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="v0a-db-")) / "painel.db"
db.garantir_banco_nao_producao()
import app  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5170")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
