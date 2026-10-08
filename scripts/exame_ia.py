#!/usr/bin/env python3
"""Exame de alucinacao do chat: ~30 perguntas com resposta conhecida contra um banco
TEMPORARIO (nunca o real). Faz chamadas REAIS a IA (centavos) - por isso nao roda em pytest.

Uso:  ANTHROPIC_API_KEY=... python scripts/exame_ia.py [--modelo claude-haiku-5-5] [--json saida.json]
Mede: respostas certas (valor/fato do painel) e "nao sei" honesto quando o dado nao existe."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("FLASK_SKIP_DOTENV", "1")
if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("Falta ANTHROPIC_API_KEY no ambiente (passe so pra este comando; nunca grave em arquivo).")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "exame.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

HOJE = date.today()
MES_PASSADO = (HOJE.replace(day=1) - timedelta(days=1)).replace(day=15)
NAO_TENHO = (r"^\s*n[ãa]o[.,!]|n[ãa]o (tenho|encontr|consta|h[áa] |ha |achei|vejo|existe|est[áa]|dá|da )|n[ãa]o tem|n[ãa]o [ée] algo|nenhum|nada |sem registro|"
             r"n[ãa]o t[áa] no painel|n[ãa]o consigo|n[ãa]o (foi|fui) registrad|zero|R\$ ?0[,.]?0*\b")


def iso(dias: int) -> str:
    return (HOJE + timedelta(days=dias)).isoformat()


def semear(conn):
    t = "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)"
    for titulo, dias, hora, feita in [
        ("Pagar boleto da internet", 0, "09:00", None), ("Ligar para o dentista", 0, "15:30", None),
        ("Revisar relatório do voo", 0, None, None), ("Renovar CNH", -4, None, None),
        ("Comprar presente da Ana", 1, None, None), ("Levar carro na revisão", 5, None, None),
        ("Enviar currículo", 0, None, f"{iso(0)} 08:00:00"),
    ]:
        conn.execute(t, (titulo, iso(dias), hora, feita))
    e = "INSERT INTO expenses (amount, category, description, created_at) VALUES (?, ?, ?, ?)"
    for valor, cat, desc in [(187.45, "alimentação", "Mercado"), (32.90, "transporte", "Uber"),
                             (210.00, "transporte", "Combustível"), (64.30, "saúde", "Farmácia"),
                             (55.90, "lazer", "Netflix")]:
        conn.execute(e, (valor, cat, desc, f"{HOJE.replace(day=1).isoformat()} 12:00:00"))
    conn.execute(e, (999.00, "moradia", "Aluguel", f"{MES_PASSADO.isoformat()} 12:00:00"))
    for dias, origem, destino, horas in [(-10, "SBGR", "SBRJ", 1.2), (-30, "SBRJ", "SBGR", 2.0)]:
        conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES (?, ?, ?, ?)", (iso(dias), origem, destino, horas))
    conn.commit()


# (pergunta, tipo, padrao): "fato" = resposta TEM que casar com padrao; "nao_sei" = tem que admitir que nao tem o dado
PERGUNTAS = [
    ("O que tenho para hoje?", "fato", r"(?s)(?=.*dentista)(?=.*boleto)(?=.*relat)"),
    ("Quanto gastei este mês?", "fato", r"550[,.]55"),
    ("Quanto gastei com transporte este mês?", "fato", r"242[,.]9"),
    ("Qual foi meu maior gasto este mês?", "fato", r"(?s)(?=.*combust)(?=.*210)"),
    ("O que está atrasado?", "fato", r"CNH"),
    ("O que tenho amanhã?", "fato", r"presente"),
    ("Quanto gastei com lazer?", "fato", r"55[,.]9"),
    ("Quanto paguei de aluguel este mês?", "nao_sei", NAO_TENHO),
    ("Quando é meu próximo voo?", "nao_sei", NAO_TENHO),
    ("Quantas horas de voo eu tenho no total?", "fato", r"3[,.]2|3h ?12|3 horas e 12"),
    ("Qual o saldo da minha conta no banco?", "nao_sei", NAO_TENHO),
    ("Quanto está o dólar hoje?", "nao_sei", NAO_TENHO),
    ("Que reuniões tenho amanhã?", "nao_sei", NAO_TENHO),
    ("Qual é o telefone da Ana?", "nao_sei", NAO_TENHO),
    ("Quantas tarefas pendentes tenho no total?", "fato", r"\b6\b|seis"),
    ("Quantas tarefas eu concluí hoje?", "fato", r"\b1\b|\buma?\b"),
    ("Quanto gastei na farmácia?", "fato", r"64[,.]3"),
    ("Quanto gastei no mercado?", "fato", r"187[,.]4"),
    ("O que vence nos próximos 7 dias?", "fato", r"carro|revis"),
    ("Que horas é o dentista?", "fato", r"15[:h]30"),
    ("Tenho alguma tarefa sobre viagem?", "nao_sei", NAO_TENHO),
    ("Quanto gastei no Netflix?", "fato", r"55[,.]9"),
    ("Quanto gastei em restaurantes este mês?", "nao_sei", NAO_TENHO),
    ("Quanto vou gastar no mês que vem?", "nao_sei", NAO_TENHO + r"|estimat|proje|previs"),
    ("Qual foi meu último voo?", "fato", r"SBRJ|Rio"),
    ("Tenho remédio para tomar hoje?", "nao_sei", NAO_TENHO),
    ("Quanto eu pesava na última medição?", "nao_sei", NAO_TENHO),
    ("Quanto gastei somando este mês e o mês passado?", "fato", r"1[.\s]?549"),
    ("Qual o nome do meu médico?", "nao_sei", NAO_TENHO),
    ("Quanto tenho investido?", "nao_sei", NAO_TENHO + r"|n[ãa]o tem no painel|n[ãa]o [ée] coisa"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=None, help="id do modelo (padrao: o do chat em ia/config.d/chat.json)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    if args.modelo:
        chat_mod._modelo_chat = lambda _c, m=args.modelo: m
    db.init_db()
    conn = db.get_db()
    auth.definir_pin(conn, "123456", "123456")
    semear(conn)
    modelo = chat_mod._modelo_chat(chat_mod._config_ia("chat"))
    ok = 0
    linhas = []
    for i, (pergunta, tipo, padrao) in enumerate(PERGUNTAS, 1):
        conn.execute("DELETE FROM chat_mensagens")
        conn.commit()
        antes = (conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])
        detalhes: dict = {}
        resposta, _acoes, erro = app._processar_mensagem_chat(conn, pergunta, detalhes)
        resposta = resposta or ""
        depois = (conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])
        passou = bool(re.search(padrao, resposta, re.I)) and not erro and antes == depois
        ok += passou
        linhas.append({"n": i, "pergunta": pergunta, "tipo": tipo, "passou": passou, "erro": erro,
                       "gravou_algo": antes != depois, "resposta": resposta})
        print(f"{'OK  ' if passou else 'ERRO'} {i:02d} [{tipo}] {pergunta}\n      -> {resposta[:220]!r}")
    row = conn.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(cost_usd),0) FROM api_usage").fetchone()
    print(f"\nModelo: {modelo}  |  acertos: {ok}/{len(PERGUNTAS)}  |  tokens in/out: {row[0]}/{row[1]}  |  custo (tabela do painel): US$ {row[2]:.4f}")
    if args.json:
        Path(args.json).write_text(json.dumps({"modelo": modelo, "acertos": ok, "total": len(PERGUNTAS), "linhas": linhas}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if ok == len(PERGUNTAS) else 1


if __name__ == "__main__":
    sys.exit(main())
