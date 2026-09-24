"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao visual da V2
(aba Painel). Mesmo molde de scripts/ralph-v0c-secoes/servidor.py.
Uso: PORTA=5140 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v2-painel/servidor.py <repo>
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
from ia.medicao import registrar_uso  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="v2-painel-db-")) / "painel.db"
db.garantir_banco_nao_producao()
db.init_db()

# Alguns dados sinteticos de uso de IA pro card "Custo de IA" nao aparecer vazio na
# verificacao visual (nomes/numeros ficticios, em pt-BR, nada real).
registrar_uso("chat", "anthropic", "claude-sonnet-5", tokens_in=12000, tokens_out=3000, custo_usd=0.15)
registrar_uso("captura", "openai", "gpt-6-luna", tokens_in=800, tokens_out=200, custo_usd=0.01)
registrar_uso("planejamento", "anthropic", "claude-opus-5-5", tokens_in=5000, tokens_out=1200, custo_usd=0.35)
registrar_uso("chat", "anthropic", "claude-sonnet-5", tokens_in=9000, tokens_out=2200, custo_usd=0.12)

import app  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5140")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
