"""Sobe o app da worktree num banco TEMPORARIO (nunca o real) pra verificacao
visual da P1b (faixa compacta em Hoje, selo, tela Assistente). Mesmo padrao
da V3 (scripts/ralph-v3-organizacao/servidor.py). Alem de subir o app, insere
itens de teste sinteticos, em pt-BR, na tabela `assistente_itens` (faixa
P1a) e uma regra de teste em `p4_regras` (faixa P4), pra tela Assistente ter
o que mostrar sem depender do tick de verdade rodar.

Uso: PORTA=5142 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-p1b-caixa-ui/servidor.py <repo>
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

repo = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
sys.path.insert(0, repo)
os.chdir(repo)
for k in ("TELEGRAM_BOT_TOKEN", "RENDER", "PAINEL_PIN_INICIAL"):
    os.environ.pop(k, None)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-teste-falso")  # dublê: nenhuma chamada real
os.environ.setdefault("PAINEL_TICK_TOKEN", "token-teste-playwright")

import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp(prefix="p1b-caixa-ui-db-")) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from assistente import caixa  # noqa: E402

conn = db.get_db()
try:
    agora = datetime.now()

    # Pergunta com opcoes proprias (testa os botoes de um toque vindos do
    # item, nao o fallback por tipo) - a mais urgente por ter vence_em no
    # passado (assistente/caixa.py: pergunta vencida vem primeiro).
    caixa.enfileirar(
        "pergunta",
        "Pagou o cartao de credito?",
        "Vencia hoje as 10h - ainda nao vi a baixa.",
        opcoes=["Sim", "Ainda nao", "Adiar"],
        origem="teste_playwright:1",
        chave_unica="teste-pergunta-cartao",
        vence_em=(agora - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    # Aviso sem opcoes proprias (testa o fallback padrao por tipo: aceitar/adiar).
    caixa.enfileirar(
        "aviso",
        "Voce tem 3 tarefas vencidas",
        "Revisar a lista de Tarefas quando puder.",
        origem="teste_playwright:2",
        chave_unica="teste-aviso-tarefas",
    )
    # Sugestao (fallback aceitar/recusar).
    caixa.enfileirar(
        "sugestao",
        "Bloquear 1h pra revisao trimestral amanha?",
        "Voce nao abre essa secao ha 3 meses.",
        origem="teste_playwright:3",
        chave_unica="teste-sugestao-revisao",
    )
    # Um quarto item pendente, pra confirmar que a faixa compacta corta em 3
    # mas o selo/titulo mostram a contagem certa (4) e a secao completa da
    # aba Assistente lista os 4.
    caixa.enfileirar(
        "briefing",
        "Bom dia! 2 reunioes e 1 conta vencendo hoje.",
        origem="teste_playwright:4",
        chave_unica="teste-briefing-manha",
    )
    # Um item ja resolvido, pra popular o Historico.
    id_historico = caixa.enfileirar(
        "pergunta",
        "Foi ao dentista ontem?",
        opcoes=["Sim", "Nao"],
        origem="teste_playwright:5",
        chave_unica="teste-pergunta-dentista",
    )
    caixa.resolver(id_historico, "sim", "marquei a proxima pra mes que vem")

    # Regra de teste (faixa P4) - direto na tabela (mais simples que passar
    # pelo parser/IA aqui, o motor em si e testado na propria faixa P4).
    conn.execute(
        "INSERT INTO p4_regras (texto_original, json, ativa) VALUES (?, ?, 1)",
        (
            "me avisa se gastar mais de 300 com mercado na semana",
            json.dumps(
                {
                    "gatilho": "gasto_categoria",
                    "condicao": {"categoria": "mercado", "limite": 300, "periodo": "semana"},
                    "acao": {"tipo": "aviso"},
                    "texto": "me avisa se gastar mais de 300 com mercado na semana",
                },
                ensure_ascii=False,
            ),
        ),
    )
    conn.commit()
finally:
    conn.close()

from werkzeug.serving import make_server  # noqa: E402

srv = make_server("127.0.0.1", int(os.environ.get("PORTA", "5142")), app.app, threaded=True)
print("rodando", db.DB_PATH, flush=True)
srv.serve_forever()
