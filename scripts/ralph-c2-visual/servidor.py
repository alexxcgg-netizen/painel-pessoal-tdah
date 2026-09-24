"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra revisao visual da C2.
Junta os moldes da P1b (itens sinteticos na Caixa + 1 regra P4) e da V3 (duble do iCloud).
Tarefas/habitos/projetos sinteticos sao criados pelo proprio verificar.py via HTTP.

Uso: PORTA=5120 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c2-visual/servidor.py <repo>
"""
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

repo = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL"):
    os.environ.pop(k, None)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-teste-falso")  # duble: nenhuma chamada real
os.environ.setdefault("PAINEL_TICK_TOKEN", "token-teste-playwright")

import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="c2-visual-db-")) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import caldav_client  # noqa: E402
from assistente import caixa  # noqa: E402


def _criar_evento_duble(titulo, inicio, fim, lembrar_min_antes=None):
    return {"uid": str(uuid.uuid4()), "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}


caldav_client.criar_evento = _criar_evento_duble

conn = db.get_db()
try:
    agora = datetime.now()
    caixa.enfileirar("pergunta", "Pagou o cartao de credito?", "Vencia hoje as 10h.",
                     opcoes=["Sim", "Ainda nao", "Adiar"], origem="c2:1", chave_unica="c2-cartao",
                     vence_em=(agora - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
    caixa.enfileirar("aviso", "Voce tem 3 tarefas vencidas", "Revisar quando puder.",
                     origem="c2:2", chave_unica="c2-aviso")
    caixa.enfileirar("sugestao", "Bloquear 1h pra revisao trimestral amanha?", "Faz 3 meses.",
                     origem="c2:3", chave_unica="c2-sugestao")
    caixa.enfileirar("briefing", "Bom dia! 2 reunioes e 1 conta vencendo hoje.",
                     origem="c2:4", chave_unica="c2-briefing")
    hid = caixa.enfileirar("pergunta", "Foi ao dentista ontem?", opcoes=["Sim", "Nao"],
                           origem="c2:5", chave_unica="c2-dentista")
    caixa.resolver(hid, "sim", "marquei a proxima")
    conn.execute(
        "INSERT INTO p4_regras (texto_original, json, ativa) VALUES (?, ?, 1)",
        ("me avisa se gastar mais de 300 com mercado na semana",
         json.dumps({"gatilho": "gasto_categoria",
                     "condicao": {"categoria": "mercado", "limite": 300, "periodo": "semana"},
                     "acao": {"tipo": "aviso"}}, ensure_ascii=False)),
    )
    conn.commit()
finally:
    conn.close()

from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5120")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
