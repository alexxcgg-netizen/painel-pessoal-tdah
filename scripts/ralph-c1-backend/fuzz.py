#!/usr/bin/env python
"""Fase 7 / C1 - fuzzing e stress do backend contra o app de TESTE.

Uso (da raiz do repo):
    /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c1-backend/fuzz.py

Garantias:
- banco SQLite TEMPORARIO (db.DB_PATH trocado + db.garantir_banco_nao_producao()
  ANTES de importar app) - nunca o data/painel.db;
- nenhuma chamada real: cliente Anthropic, adapters do ia.core, push, Telegram e
  requests.get/post sao dubles;
- meta: 0 respostas 500 e 0 corrupcao (PRAGMA integrity_check, contagens
  exatas depois da concorrencia).

Sai com codigo 0 so se todos os cenarios passarem."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

TOKEN_TICK = "tick-fuzz-sintetico"
TOKEN_SINAL = "sinal-fuzz-sintetico"
# Aviso do integrador: base URL local em TODO SDK (qualquer chamada que escape
# dos dubles morre em 127.0.0.1:9) e chaves falsas - antes de importar o app.
os.environ.update({
    "ANTHROPIC_API_KEY": "teste-fake",
    "OPENAI_API_KEY": "teste-fake",
    "GEMINI_API_KEY": "teste-fake",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:9",
    "OPENAI_BASE_URL": "http://127.0.0.1:9",
    "PAINEL_TICK_TOKEN": TOKEN_TICK,
    "PAINEL_SINAL_TOKEN": TOKEN_SINAL,
})
for var in ("CONSTRUTORA_API_URL", "CONSTRUTORA_API_KEY", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY"):
    os.environ.pop(var, None)

import socket  # noqa: E402

# Guarda de rede: qualquer conexao de socket que nao seja pra 127.0.0.1/::1 e
# recusada e registrada (o fuzz falha se a lista nao terminar vazia).
CONEXOES_EXTERNAS: list[str] = []
_connect_original = socket.socket.connect


def _connect_so_local(self, endereco):
    host = endereco[0] if isinstance(endereco, tuple) else str(endereco)
    if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
        CONEXOES_EXTERNAS.append(str(endereco))
        raise ConnectionRefusedError(f"fuzz: conexao externa bloqueada ({endereco})")
    return _connect_original(self, endereco)


socket.socket.connect = _connect_so_local
_getaddrinfo_original = socket.getaddrinfo


def _getaddrinfo_so_local(host, *a, **k):
    if host not in ("127.0.0.1", "::1", "localhost", None):
        CONEXOES_EXTERNAS.append(f"dns:{host}")
        raise socket.gaierror(f"fuzz: DNS externo bloqueado ({host})")
    return _getaddrinfo_original(host, *a, **k)


socket.getaddrinfo = _getaddrinfo_so_local

import db  # noqa: E402

_TMP = tempfile.TemporaryDirectory(prefix="c1-fuzz-")
db.DB_PATH = Path(_TMP.name) / "painel_fuzz.db"
db.garantir_banco_nao_producao()
db.init_db()

import app  # noqa: E402
import auth  # noqa: E402
import claude_client  # noqa: E402
from assistente import caixa  # noqa: E402
from ia import core, medicao  # noqa: E402
from ia.contrato import Adapter, Resposta  # noqa: E402

PIN = "135790"
GIGANTE = "x" * 200_000
RESULTADOS: list[tuple[str, bool, str]] = []


# ---------------------------------------------------------------------------
# Dubles (nenhuma rede)
# ---------------------------------------------------------------------------

def _resp_anthropic(**_kwargs):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Anotado (duble).")],
        stop_reason="end_turn", model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=50, output_tokens=10, cache_read_input_tokens=0,
                              cache_creation_input_tokens=0),
    )


class AdapterDuble(Adapter):
    def chamar(self, **kwargs):
        return Resposta(ok=True, texto="resumo sintetico", provedor="duble", modelo=kwargs["modelo"],
                        custo_usd=0.0001)


def _sem_rede(*_a, **_k):
    raise AssertionError("rede real proibida no fuzz")


def _instalar_dubles():
    for provedor in ("anthropic", "openai", "gemini"):
        core.registrar_adapter(provedor, AdapterDuble)
    patches = [
        patch.object(claude_client.client.messages, "create", side_effect=_resp_anthropic),
        patch("push_client.configurado", return_value=False),
        patch("push_client.enviar", return_value=False),
        patch("requests.get", side_effect=_sem_rede),
        patch("requests.post", side_effect=_sem_rede),
        patch("ia.funcoes.chat._decidir_rota", return_value="padrao"),
    ]
    for p in patches:
        p.start()
    return patches


# ---------------------------------------------------------------------------
# Execucao de cenario
# ---------------------------------------------------------------------------

def _cliente_logado():
    c = app.app.test_client()
    r = c.post("/login", json={"pin": PIN})
    assert r.status_code == 200, r.get_data(as_text=True)
    return c


def cenario(nome, metodo, url, *, esperado=None, cliente=None, **kwargs):
    """Roda uma requisicao; falha se 5xx ou se `esperado` (status ou tupla)
    nao bater."""
    c = cliente or CLIENTE
    try:
        res = c.open(url, method=metodo, **kwargs)
        ok = res.status_code < 500
        detalhe = f"{res.status_code}"
        if esperado is not None:
            # esperado explicito (ex.: 502 de IA fora do ar, que e erro
            # controlado) vale no lugar da regra "< 500"
            aceitos = esperado if isinstance(esperado, tuple) else (esperado,)
            ok = res.status_code in aceitos
            detalhe += f" (esperado {aceitos})"
        if not ok:
            detalhe += " " + res.get_data(as_text=True)[:200]
    except Exception as exc:  # noqa: BLE001
        ok, detalhe = False, f"EXCECAO {exc!r}\n{traceback.format_exc()[-800:]}"
    RESULTADOS.append((nome, ok, detalhe))
    return ok


def checar(nome, condicao, detalhe=""):
    RESULTADOS.append((nome, bool(condicao), detalhe))


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


JSON_RUIM = dict(data="{nao e json", content_type="application/json")


# ---------------------------------------------------------------------------
# Cenarios
# ---------------------------------------------------------------------------

def cenarios_chat():
    for i, corpo in enumerate([
        {"mensagem": "me lembra de comprar pao amanha"},
        {"mensagem": ""}, {"mensagem": None}, {"mensagem": 123}, {"mensagem": ["a", "b"]},
        {"mensagem": {"x": 1}}, {"mensagem": "y" * 4000}, {"mensagem": "y" * 4001}, {"mensagem": GIGANTE},
        {"mensagem": "🤖🔥 ação émoji ✅ ​"}, {"mensagem": "'; DROP TABLE tasks; --"},
        {"mensagem": "texto\x00com\x00nulo"}, {"mensagem": "gastei -50 no mercado"},
        {"mensagem": "gastei 0 reais"}, {"mensagem": "tarefa pro dia 31/02/2026"},
        {"outra_chave": "sem mensagem"}, [], "string solta", 42, None,
    ]):
        cenario(f"chat#{i} {str(corpo)[:40]!r}", "POST", "/api/chat", json=corpo)
    cenario("chat JSON malformado", "POST", "/api/chat", **JSON_RUIM)
    cenario("chat sem content-type", "POST", "/api/chat", data="mensagem=oi")
    with patch("claude_client.chat", side_effect=core.ErroProvedor("chat: caiu")):
        cenario("chat IA fora do ar -> 502", "POST", "/api/chat", json={"mensagem": "piada"}, esperado=502)
    with patch("claude_client.chat", side_effect=core.TetoEstourado("chat: teto")):
        cenario("chat teto levantado -> 402", "POST", "/api/chat", json={"mensagem": "piada"}, esperado=402)
    with patch("ia.teto.teto_permite", return_value=False):
        cenario("chat teto estourado -> 402", "POST", "/api/chat", json={"mensagem": "piada"}, esperado=402)


def cenarios_tick():
    cenario("tick sem token", "POST", "/api/tick", esperado=401)
    cenario("tick token errado", "POST", "/api/tick", headers=bearer("errado"), esperado=401)
    cenario("tick Bearer vazio", "POST", "/api/tick", headers={"Authorization": "Bearer "}, esperado=401)
    cenario("tick sem Bearer", "POST", "/api/tick", headers={"Authorization": TOKEN_TICK}, esperado=401)
    cenario("tick header gigante", "POST", "/api/tick", headers=bearer(GIGANTE[:8000]), esperado=401)
    cenario("tick token com prefixo certo", "POST", "/api/tick", headers=bearer(TOKEN_TICK + "x"), esperado=401)
    cenario("tick token certo", "POST", "/api/tick", headers=bearer(TOKEN_TICK), esperado=200)
    cenario("tick token certo 2x (idempotente)", "POST", "/api/tick", headers=bearer(TOKEN_TICK), esperado=200)
    anon = app.app.test_client()
    cenario("tick token certo sem sessao", "POST", "/api/tick", cliente=anon, headers=bearer(TOKEN_TICK),
            esperado=200)
    cenario("tick GET nao permitido", "GET", "/api/tick", headers=bearer(TOKEN_TICK), esperado=405)


def cenarios_sinal():
    h = bearer(TOKEN_SINAL)
    cenario("sinal sem token", "POST", "/api/sinal", json={"tipo": "acordei"}, esperado=401)
    cenario("sinal token errado", "POST", "/api/sinal", json={"tipo": "acordei"}, headers=bearer("x"), esperado=401)
    for tipo in ("cheguei", "sai", "acordei", "dormir", "carregando"):
        cenario(f"sinal {tipo}", "POST", "/api/sinal", json={"tipo": tipo, "lugar": "mercado"}, headers=h,
                esperado=201)
    for i, corpo in enumerate([
        {"tipo": "voei"}, {"tipo": None}, {"tipo": 1}, {"tipo": "acordei", "lugar": 5},
        {"tipo": "acordei", "lugar": GIGANTE}, {"tipo": "acordei", "quando": "2026-13-45T25:61"},
        {"tipo": "acordei", "quando": "ontem"}, {"tipo": "acordei", "quando": 0},
        {"tipo": "acordei", "quando": "9999-99-99"}, {"tipo": "acordei", "quando": "2026-09-24T07:00:00"},
        {"tipo": "acordei", "quando": "2026-02-30T07:00:00"}, [], "texto",
    ]):
        cenario(f"sinal corpo#{i} {str(corpo)[:40]!r}", "POST", "/api/sinal", json=corpo, headers=h)
    cenario("sinal JSON malformado", "POST", "/api/sinal", headers=h, **JSON_RUIM)


def cenarios_financas():
    base = "/api/financas"
    for i, corpo in enumerate([
        {"nome": "Streaming Sintetico", "valor": 29.9, "dia_cobranca": 10},
        {"nome": "Negativa", "valor": -10, "dia_cobranca": 10}, {"nome": "Zero", "valor": 0, "dia_cobranca": 10},
        {"nome": "Dia0", "valor": 5, "dia_cobranca": 0}, {"nome": "Dia32", "valor": 5, "dia_cobranca": 32},
        {"nome": "DiaTexto", "valor": 5, "dia_cobranca": "abc"}, {"nome": GIGANTE[:5000], "valor": 5, "dia_cobranca": 1},
        {"valor": 5, "dia_cobranca": 1}, {"nome": "NaN", "valor": "NaN", "dia_cobranca": 1},
        {"nome": "Inf", "valor": 1e309, "dia_cobranca": 1}, {"nome": "Enorme", "valor": 1e308, "dia_cobranca": 1},
        {"nome": "DataRuim", "valor": 5, "dia_cobranca": 1, "inicio": "2026-02-30"},
        {"nome": "Bool", "valor": True, "dia_cobranca": True}, [], "x", None,
    ]):
        cenario(f"assinatura POST#{i} {str(corpo)[:40]!r}", "POST", f"{base}/assinaturas", json=corpo)
    cenario("assinatura POST JSON malformado", "POST", f"{base}/assinaturas", **JSON_RUIM)
    cenario("assinaturas GET", "GET", f"{base}/assinaturas", esperado=200)
    cenario("assinatura GET 1", "GET", f"{base}/assinaturas/1")
    cenario("assinatura GET inexistente", "GET", f"{base}/assinaturas/999999", esperado=404)
    cenario("assinatura PATCH lixo", "PATCH", f"{base}/assinaturas/1", json={"valor": "muito", "dia_cobranca": -3})
    cenario("assinatura PATCH lista", "PATCH", f"{base}/assinaturas/1", json=[1, 2])
    cenario("assinatura cancelar inexistente", "POST", f"{base}/assinaturas/999999/cancelar")
    cenario("assinatura DELETE inexistente", "DELETE", f"{base}/assinaturas/999999")
    for i, corpo in enumerate([
        {"descricao": "geladeira sintetica", "valor_total": 3000, "n_parcelas": 12},
        {"descricao": "zero", "valor_total": 100, "n_parcelas": 0},
        {"descricao": "neg", "valor_total": 100, "n_parcelas": -1},
        {"descricao": "muitas", "valor_parcela": 1, "n_parcelas": 100000},
        {"descricao": "total neg", "valor_total": -500, "n_parcelas": 2},
        {"descricao": "data ruim", "valor_total": 100, "n_parcelas": 2, "primeira_parcela": "2026-99-01"},
        {"descricao": "sem valor", "n_parcelas": 3}, {"n_parcelas": 3, "valor_total": 30}, [],
    ]):
        cenario(f"parcela POST#{i} {str(corpo)[:40]!r}", "POST", f"{base}/parcelas", json=corpo)
    cenario("parcelas GET", "GET", f"{base}/parcelas", esperado=200)
    cenario("parcela GET inexistente", "GET", f"{base}/parcelas/999999", esperado=404)
    cenario("parcela DELETE inexistente", "DELETE", f"{base}/parcelas/999999")
    cenario("comprometido GET", "GET", f"{base}/comprometido", esperado=200)
    cenario("desfazer financas token lixo", "POST", f"{base}/desfazer/naoexiste", esperado=404)
    cenario("desfazer financas token gigante", "POST", f"{base}/desfazer/{'a' * 3000}")
    cenario("desfazer geral token lixo", "POST", "/api/desfazer/naoexiste", esperado=404)

    # Achado da C3c (integrador): data invalida nao pode gravar a linha, e
    # linha ruim ja gravada (banco antigo) nao pode derrubar as leituras.
    conn = db.get_db()
    antes = conn.execute("SELECT COUNT(*) AS n FROM compra_parcelada").fetchone()["n"]
    conn.close()
    cenario("parcela data invalida -> 400", "POST", f"{base}/parcelas", esperado=400,
            json={"descricao": "c3c", "valor_total": 100, "n_parcelas": 2, "primeira_parcela": "2026-99-01"})
    conn = db.get_db()
    depois = conn.execute("SELECT COUNT(*) AS n FROM compra_parcelada").fetchone()["n"]
    conn.execute("INSERT INTO compra_parcelada (descricao, valor_total, n_parcelas, parcela_atual, valor_parcela, "
                 "primeira_parcela) VALUES ('legado ruim', 100, 2, 1, 50, 'lixo')")
    conn.execute("INSERT INTO assinatura (nome, valor, dia_cobranca, ativa, inicio) VALUES ('legado', 'NaN', 5, 1, 'x')")
    conn.commit()
    conn.close()
    checar("parcela data invalida nao grava linha", depois == antes, f"{antes} -> {depois}")
    for rota in ("assinaturas", "parcelas", "comprometido"):
        cenario(f"{rota} GET com linha ruim no banco", "GET", f"{base}/{rota}", esperado=200)
    for valor in (1e308, "inf", "NaN", 1e10):
        cenario(f"assinatura valor {valor} -> 400", "POST", f"{base}/assinaturas", esperado=400,
                json={"nome": "grande", "valor": valor, "dia_cobranca": 1})


def cenarios_construtora():
    """Achado da C3c: /api/construtora/resumo nunca manda lucro/margem/VGV."""
    with patch.dict(os.environ, {"CONSTRUTORA_API_MOCK": "1"}):
        app._CACHE_CONSTRUTORA.clear()
        res = CLIENTE.get("/api/construtora/resumo")
    corpo = res.get_data(as_text=True).lower()
    checar("construtora mock -> 200", res.status_code == 200, str(res.status_code))
    checar("construtora sem lucro/margem/vgv", not any(p in corpo for p in ("lucro", "margem", "vgv")), corpo[:200])
    cenario("construtora sem config", "GET", "/api/construtora/resumo", esperado=200)


def cenarios_p4():
    regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
             "acao": {"mensagem": "tomar o remedio sintetico"}, "texto": "todo dia 18h"}
    cenario("p4 GET", "GET", "/api/p4_regras", esperado=200)
    cenario("p4 confirmar valida", "POST", "/api/p4_regras/confirmar",
            json={"texto_original": "todo dia 18h", "json": regra}, esperado=201)
    for i, corpo in enumerate([
        {}, {"texto_original": "x"}, {"json": regra}, {"texto_original": 123, "json": regra},
        {"texto_original": "x", "json": "nao e dict"}, {"texto_original": "x", "json": {"gatilho": "???"}},
        {"texto_original": "x", "json": {**regra, "condicao": {"tipo": "diario", "hora": "25:99"}}},
        {"texto_original": GIGANTE, "json": regra}, [], [1, 2, 3], "texto",
    ]):
        cenario(f"p4 confirmar#{i} {str(corpo)[:40]!r}", "POST", "/api/p4_regras/confirmar", json=corpo)
    cenario("p4 confirmar JSON malformado", "POST", "/api/p4_regras/confirmar", **JSON_RUIM)
    for acao in ("pausar", "retomar"):
        cenario(f"p4 {acao} inexistente", "POST", f"/api/p4_regras/999999/{acao}", esperado=404)
        cenario(f"p4 {acao} existente", "POST", f"/api/p4_regras/1/{acao}", json={"dias": 2})
        cenario(f"p4 {acao} corpo lixo", "POST", f"/api/p4_regras/1/{acao}", json=[1])
        cenario(f"p4 {acao} dias negativos", "POST", f"/api/p4_regras/1/{acao}", json={"dias": -5})
    cenario("p4 DELETE inexistente", "DELETE", "/api/p4_regras/999999", esperado=404)


def cenarios_assistente():
    cenario("caixa GET", "GET", "/api/assistente/caixa", esperado=200)
    for estado in ("pendente", "resolvido", "adiado", "expirado", "lixo", "", GIGANTE[:3000]):
        cenario(f"caixa GET estado={estado[:10]!r}", "GET", f"/api/assistente/caixa?estado={estado}")
    item_id = caixa.enfileirar("pergunta", "Pagou a conta sintetica?", origem="fuzz:1")
    for i, corpo in enumerate([
        {"resposta": "sim"}, {"resposta": "sim"}, {"resposta": ""}, {"resposta": None}, {"resposta": 5},
        {"resposta": "talvez"}, {"resposta": "sim", "texto": GIGANTE}, [], "x",
    ]):
        cenario(f"caixa responder#{i} {str(corpo)[:30]!r}", "POST", f"/api/assistente/caixa/{item_id}/responder",
                json=corpo)
    cenario("caixa responder id texto", "POST", "/api/assistente/caixa/abc/responder", json={"resposta": "sim"})
    cenario("caixa responder id inexistente", "POST", "/api/assistente/caixa/999999/responder",
            json={"resposta": "sim"}, esperado=404)
    cenario("avisos GET", "GET", "/api/assistente/avisos", esperado=200)
    for i, (tipo, corpo) in enumerate([
        ("pergunta_conta", {"ligado": False}), ("pergunta_conta", {"ligado": "nao"}),
        ("pergunta_conta", {"canal": "pombo"}), ("pergunta_conta", {"silencio_inicio": "25:00"}),
        ("tipo_que_nao_existe", {"ligado": True}), ("pergunta_conta", []), ("pergunta_conta", "x"),
        ("pergunta_conta", {"ligado": True, "canal": "caixa"}),
    ]):
        cenario(f"avisos PUT#{i} {tipo} {str(corpo)[:30]!r}", "PUT", f"/api/assistente/avisos/{tipo}", json=corpo)
    for i, corpo in enumerate([{"inicio": "22:00", "fim": "07:00"}, {"inicio": "7h", "fim": "x"}, {}, [], None]):
        cenario(f"silencio PUT#{i}", "PUT", "/api/assistente/avisos/silencio", json=corpo)
    for i, corpo in enumerate([{"manha": "07:30"}, {"noite": "25:00"}, {"manha": 7}, {}, [], "x"]):
        cenario(f"briefing horarios PUT#{i}", "PUT", "/api/assistente/briefing/horarios", json=corpo)
    cenario("briefing horarios GET", "GET", "/api/assistente/briefing/horarios", esperado=200)
    cenario("briefing previa GET", "GET", "/api/assistente/briefing/previa")
    cenario("assistente saude GET", "GET", "/api/assistente/saude", esperado=200)


# ---------------------------------------------------------------------------
# Concorrencia: 20 threads na Caixa e no teto de IA
# ---------------------------------------------------------------------------

def concorrencia():
    n_threads, por_thread = 20, 10
    erros: list[str] = []
    barreira = threading.Barrier(n_threads)
    custo = 0.001

    def trabalhador(i):
        try:
            barreira.wait()
            for j in range(por_thread):
                # Caixa: itens unicos + a MESMA chave_unica disputada por todos
                caixa.enfileirar("aviso", f"Item sintetico {i}-{j}", origem=f"fuzz:{i}", chave_unica=f"fuzz-{i}-{j}")
                caixa.enfileirar("aviso", "Disputado", origem="fuzz:x", chave_unica=f"disputado-{j}")
                # teto: grava uso e consulta o teto ao mesmo tempo
                medicao.registrar_uso("chat", "duble", "duble", custo_usd=custo)
                app._teto_ia_estourado("chat")
        except Exception as exc:  # noqa: BLE001
            erros.append(f"thread {i}: {exc!r}")

    conn = db.get_db()
    antes_uso = conn.execute("SELECT COUNT(*) AS n FROM uso_ia").fetchone()["n"]
    antes_gasto = medicao.gasto_mes_atual()
    conn.close()

    threads = [threading.Thread(target=trabalhador, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    checar("concorrencia: nenhuma thread travou", all(not t.is_alive() for t in threads))
    checar("concorrencia: nenhuma excecao (lock/integridade)", not erros, "; ".join(erros[:5]))

    conn = db.get_db()
    try:
        unicos = conn.execute("SELECT COUNT(*) AS n FROM assistente_itens WHERE chave_unica LIKE 'fuzz-%'").fetchone()["n"]
        disputados = conn.execute(
            "SELECT chave_unica, COUNT(*) AS n FROM assistente_itens WHERE chave_unica LIKE 'disputado-%' "
            "GROUP BY chave_unica").fetchall()
        depois_uso = conn.execute("SELECT COUNT(*) AS n FROM uso_ia").fetchone()["n"]
    finally:
        conn.close()
    total = n_threads * por_thread
    checar("concorrencia: caixa com 1 item por chave unica", unicos == total, f"{unicos} != {total}")
    checar("concorrencia: chave disputada nunca duplica",
           len(disputados) == por_thread and all(r["n"] == 1 for r in disputados), str([dict(r) for r in disputados]))
    checar("concorrencia: uso_ia com todas as linhas", depois_uso - antes_uso == total, f"{depois_uso - antes_uso}")
    delta = medicao.gasto_mes_atual() - antes_gasto
    checar("concorrencia: gasto do mes soma cada chamada uma vez", abs(delta - total * custo) < 1e-9, f"{delta}")

    # 20 ticks em paralelo (clientes separados) - so 200/401, nunca 500
    status: list[int] = []

    def tick():
        c = app.app.test_client()
        status.append(c.post("/api/tick", headers=bearer(TOKEN_TICK)).status_code)

    ts = [threading.Thread(target=tick) for _ in range(20)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=120)
    checar("concorrencia: 20 ticks paralelos sem 500", len(status) == 20 and all(s == 200 for s in status),
           str(status))


def integridade():
    conn = db.get_db()
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()
    checar("integridade: PRAGMA integrity_check", ok == "ok", ok)
    checar("integridade: foreign_key_check vazio", not fk, str(fk[:3]))
    checar("integridade: banco e o temporario", str(db.DB_PATH).startswith(_TMP.name), str(db.DB_PATH))
    checar("rede: nenhuma conexao externa (anthropic/openai/google/telegram)", not CONEXOES_EXTERNAS,
           str(CONEXOES_EXTERNAS[:5]))


def main() -> int:
    global CLIENTE
    conn = db.get_db()
    auth.definir_pin(conn, PIN, PIN)
    conn.commit()
    conn.close()
    patches = _instalar_dubles()
    try:
        CLIENTE = _cliente_logado()
        for bloco in (cenarios_chat, cenarios_tick, cenarios_sinal, cenarios_financas, cenarios_construtora,
                      cenarios_p4, cenarios_assistente, concorrencia, integridade):
            try:
                bloco()
            except Exception as exc:  # noqa: BLE001
                RESULTADOS.append((f"bloco {bloco.__name__}", False, f"EXCECAO {exc!r}\n{traceback.format_exc()[-800:]}"))
    finally:
        for p in patches:
            p.stop()
        for provedor in ("anthropic", "openai", "gemini"):
            core.registrar_adapter(provedor, None)

    falhas = [r for r in RESULTADOS if not r[1]]
    for nome, _, detalhe in falhas:
        print(f"FALHA: {nome}: {detalhe}")
    print(json.dumps({"cenarios": len(RESULTADOS), "falhas": len(falhas)}))
    return 1 if falhas else 0


CLIENTE = None

if __name__ == "__main__":
    sys.exit(main())
