"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao visual da V3
(habitos, projetos, agenda-painel, tarefas). Mesmo padrao da V0b (scripts/ralph-v0b-botoes/servidor.py).
Uso: PORTA=5150 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v3-organizacao/servidor.py <repo>
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

db.DB_PATH = Path(tempfile.mkdtemp(prefix="v3-organizacao-db-")) / "painel.db"
db.garantir_banco_nao_producao()
import app  # noqa: E402
import caldav_client  # noqa: E402
import uuid  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

# Duble do iCloud (agenda "Painel"): nunca chama rede real nem pede credencial - so pra
# verificar a UI nova (bottom-sheet) da secao vida/agenda-painel de ponta a ponta.
def _criar_evento_duble(titulo, inicio, fim, lembrar_min_antes=None):
    return {"uid": str(uuid.uuid4()), "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}


caldav_client.criar_evento = _criar_evento_duble

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5150")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
