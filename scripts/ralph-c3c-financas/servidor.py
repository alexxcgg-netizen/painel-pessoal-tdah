"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao
visual/fuzz da faixa c3c-financas (Gastos, Assinaturas e parcelas, Bancos,
Construtora, Contas pessoais).

Uso: PORTA=5133 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3c-financas/servidor.py <repo>

- CONSTRUTORA_API_MOCK=1: dados sinteticos da construtora (construtora_cliente.py,
  faixa A10). A rota antiga GET /api/construtora/resumo (app.py, fora da lista
  desta faixa) so le CONSTRUTORA_API_URL/KEY e usa as funcoes antigas
  _buscar_*_construtora - aqui, SO neste harness de teste, elas sao apontadas
  pro ClienteConstrutora(mock=True). Nenhuma chamada de rede real, nenhum
  arquivo do app alterado.
- Semente sintetica pt-BR: gastos, meta, 2 contas de banco (cartao com limite).
"""
import os
import sys
import tempfile
from pathlib import Path

repo = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL", "PLUGGY_CLIENT_ID", "PLUGGY_CLIENT_SECRET"):
    os.environ.pop(k, None)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-teste-falso")  # duble: nenhuma chamada real
os.environ["CONSTRUTORA_API_MOCK"] = "1"
os.environ["CONSTRUTORA_API_URL"] = "http://mock.invalido"
os.environ["CONSTRUTORA_API_KEY"] = "chave-falsa-de-teste"
import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="c3c-financas-db-")) / "painel.db"
db.garantir_banco_nao_producao()
import app  # noqa: E402
import construtora_cliente  # noqa: E402

_cli = construtora_cliente.ClienteConstrutora(mock=True)
app._buscar_resumo_construtora = _cli.resumo
app._buscar_contas_a_vencer_construtora = lambda dias=30: _cli.contas_a_vencer(dias=dias)

if os.environ.get("SEMENTE", "1") == "1":
    conn = db.get_db()
    db.criar_gasto_de_brain_dump(conn, 45.9, "mercado", "Padaria do bairro")
    db.criar_gasto_de_brain_dump(conn, 1234567.89, "outros", "Valor gigante de teste de layout")
    db.criar_gasto_de_brain_dump(conn, 18.5, "transporte", "Onibus")
    m1 = db.create_goal(conn, "Viagem para a serra", 5000, "2026-12-31")
    db.add_to_goal(conn, m1, 1200)
    m2 = db.create_goal(conn, "Reserva de emergencia", 1000, None)
    db.add_to_goal(conn, m2, 1000)
    c1 = db.get_or_create_bank_account(conn, "nubank", "cartao")
    db.definir_limite_conta(conn, c1, 8000)
    db.atualizar_saldo_conta(conn, c1, -2345.67)
    c2 = db.get_or_create_bank_account(conn, "caixa", "conta")
    db.atualizar_saldo_conta(conn, c2, 987654.32)
    conn.close()

from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5133")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
