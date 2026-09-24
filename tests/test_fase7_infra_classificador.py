"""Fase 7, Etapa 0: regras locais do classificador (classificador_local/).

A regra falsa e escrita numa pasta temporaria acrescentada ao
`classificador_local.regras.__path__` so durante o teste - nenhuma regra de
exemplo fica ativa no app. IA sempre mockada: o teste garante que ela NAO
foi chamada quando a regra casa."""

import os
import sys
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import classificador_local  # noqa: E402
from classificador_local import regras as pacote_regras  # noqa: E402

PIN_TESTE = "123456"
USO = {"model": "claude-sonnet", "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.001}

# Regra falsa: "assinei <servico> <valor> por mes" vira um gasto (efeito com
# card transacao + Desfazer, igual o chat faria).
REGRA_ASSINATURA = '''
import re

_RE = re.compile(r"assinei (?P<servico>[a-z]+) (?P<valor>\\d+) por mes", re.IGNORECASE)
CHAMADAS = []


def casar(texto):
    m = _RE.fullmatch(texto.strip())
    if not m:
        return None
    return {"acao": "registrar_assinatura", "confianca": 0.95,
            "parametros": {"servico": m["servico"], "valor": float(m["valor"])}}


def executar(conn, parametros):
    CHAMADAS.append(parametros)
    cur = conn.execute(
        "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
        (parametros["valor"], "contas", parametros["servico"], "regra local", "real"),
    )
    return {"efeitos": [{"entidade": "gasto", "id": cur.lastrowid}],
            "resumo_texto": "Assinatura registrada."}
'''


class _PastaRegras:
    def __init__(self, modulos: dict[str, str]):
        self.modulos = modulos

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        for nome, codigo in self.modulos.items():
            (Path(self.tmp.name) / f"{nome}.py").write_text(textwrap.dedent(codigo))
        # So a pasta temporaria: modulos reais das faixas nao interferem no teste.
        self._path_antes = list(pacote_regras.__path__)
        pacote_regras.__path__[:] = [self.tmp.name]
        return self

    def modulo(self, nome):
        return sys.modules[f"classificador_local.regras.{nome}"]

    def __exit__(self, *exc):
        pacote_regras.__path__[:] = self._path_antes
        for nome in self.modulos:
            sys.modules.pop(f"classificador_local.regras.{nome}", None)
        self.tmp.cleanup()


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)
        self.nome = f"regra_{uuid.uuid4().hex[:8]}"

    def contar(self, tabela):
        conn = db.get_db()
        try:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()["n"]
        finally:
            conn.close()


class CasarTestCase(_Base):
    def test_sem_regra_nenhuma_nao_casa_nada(self):
        with _PastaRegras({}):
            self.assertEqual(classificador_local.nomes_regras(), [])
            self.assertIsNone(classificador_local.casar("assinei netflix 55 por mes"))

    def test_casa_e_normaliza_o_formato(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            r = classificador_local.casar("assinei netflix 55 por mes")
            self.assertEqual(r, {
                "acao": "registrar_assinatura", "confianca": 0.95,
                "parametros": {"servico": "netflix", "valor": 55.0},
                "precisa_confirmacao": False, "regra": self.nome,
            })
            self.assertIsNone(classificador_local.casar("gastei 55 no mercado"))

    def test_entrada_invalida_nao_quebra(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            for texto in (None, "", "   ", 123, ["x"], {"a": 1}, "x" * 100_000, "\x00\ud800"):
                self.assertIsNone(classificador_local.casar(texto))

    def test_primeira_regra_em_ordem_alfabetica_vence(self):
        a = "def casar(t):\n    return {'acao': 'da_a'} if 'x' in t else None\n"
        b = "def casar(t):\n    return {'acao': 'da_b'}\n"
        with _PastaRegras({f"b_{self.nome}": b, f"a_{self.nome}": a}):
            self.assertEqual(classificador_local.casar("tem x")["regra"], f"a_{self.nome}")
            self.assertEqual(classificador_local.casar("sem")["acao"], "da_b")

    def test_regra_quebrada_ou_formato_invalido_e_pulada(self):
        quebrada = "def casar(t):\n    raise RuntimeError('bug na regra')\n"
        invalida = "def casar(t):\n    return {'confianca': 1}\n"
        lista = "def casar(t):\n    return ['nao', 'dict']\n"
        sem_casar = "VALOR = 1\n"
        ok = "def casar(t):\n    return {'acao': 'ok', 'confianca': 7, 'parametros': 'x', 'precisa_confirmacao': 1}\n"
        with _PastaRegras({f"a_{self.nome}": quebrada, f"b_{self.nome}": invalida, f"c_{self.nome}": lista,
                           f"d_{self.nome}": sem_casar, f"e_{self.nome}": ok}):
            with self.assertLogs("classificador_local", level="WARNING"):
                r = classificador_local.casar("qualquer")
            self.assertEqual(r["regra"], f"e_{self.nome}")
            self.assertEqual(r["confianca"], 1.0)  # limitado a 0..1
            self.assertEqual(r["parametros"], {})
            self.assertIs(r["precisa_confirmacao"], True)

    def test_regra_com_erro_de_sintaxe_e_pulada(self):
        with _PastaRegras({f"a_{self.nome}": "def casar(:\n", f"b_{self.nome}": REGRA_ASSINATURA}):
            with self.assertLogs("classificador_local", level="ERROR"):
                r = classificador_local.casar("assinei spotify 20 por mes")
            self.assertEqual(r["regra"], f"b_{self.nome}")


class ExecutarTestCase(_Base):
    def test_efeitos_viram_cards_do_contrato(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            conn = db.get_db()
            r = classificador_local.casar("assinei netflix 55 por mes")
            env = classificador_local.executar(conn, r, app._criar_token_desfazer(conn))
            conn.commit()
            conn.close()
        self.assertEqual(set(env), {"cards", "resumo_texto", "passos"})
        self.assertEqual(env["resumo_texto"], "Assinatura registrada.")
        self.assertEqual(env["cards"][0]["type"], "transacao")
        self.assertEqual(env["cards"][0]["id"], "c1")
        self.assertTrue(any(a.get("tipo") == "desfazer" for a in env["cards"][0]["actions"]))
        self.assertEqual(env["passos"][0]["modulo"], "Classificador local")
        self.assertEqual(self.contar("expenses"), 1)

    def test_cards_prontos_e_desistencia(self):
        pronto = """
            import cards
            def casar(t):
                return {"acao": "x"}
            def executar(conn, p):
                return {"cards": [cards.novo_card("sugestao", {"titulo": "oi"})], "resumo_texto": "ok",
                        "passos": [{"modulo": "M", "descricao": "d", "ms": 1}]}
            """
        desiste = "def casar(t):\n    return {'acao': 'x'}\ndef executar(conn, p):\n    return None\n"
        sem_exec = "def casar(t):\n    return {'acao': 'x'}\n"
        conn = db.get_db()
        try:
            with _PastaRegras({self.nome: pronto}):
                env = classificador_local.executar(conn, classificador_local.casar("a"))
                self.assertEqual(env["cards"][0]["id"], "c1")
                self.assertEqual(env["passos"], [{"modulo": "M", "descricao": "d", "ms": 1}])
            with _PastaRegras({self.nome: desiste}):
                self.assertIsNone(classificador_local.executar(conn, classificador_local.casar("a")))
            with _PastaRegras({self.nome: sem_exec}):
                self.assertIsNone(classificador_local.executar(conn, classificador_local.casar("a")))
            for invalido in (None, {}, {"regra": 1}, "x"):
                self.assertIsNone(classificador_local.executar(conn, invalido))
        finally:
            conn.close()

    def test_executar_que_explode_faz_rollback(self):
        explode = """
            def casar(t):
                return {"acao": "x"}
            def executar(conn, p):
                conn.execute("INSERT INTO expenses (amount, category, description) VALUES (1, 'x', 'meio')")
                raise ValueError("quebrou no meio")
            """
        conn = db.get_db()
        with _PastaRegras({self.nome: explode}):
            with self.assertLogs("classificador_local", level="ERROR"):
                self.assertIsNone(classificador_local.executar(conn, classificador_local.casar("a")))
        conn.commit()
        conn.close()
        self.assertEqual(self.contar("expenses"), 0)


class IntegracaoAppTestCase(_Base):
    """Plugado em /api/chat, /api/capture e _classificar_intent."""

    def test_chat_resolve_local_sem_chamar_ia(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.chat") as ia:
                res = self.client.post("/api/chat", json={"mensagem": "assinei netflix 55 por mes"})
            ia.assert_not_called()
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertEqual(corpo["resposta"], "Assinatura registrada.")
        self.assertEqual(corpo["acoes"], ["registrar_assinatura"])
        self.assertEqual(corpo["cards"][0]["type"], "transacao")
        self.assertEqual(self.contar("expenses"), 1)
        # vira historico do chat com os cards, igual a resposta da IA
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertEqual([m["papel"] for m in hist], ["user", "assistant"])
        self.assertEqual(hist[1]["cards"][0]["type"], "transacao")

    def test_chat_sem_regra_que_case_segue_pra_ia(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.chat", return_value=("Oi!", [], USO)) as ia:
                res = self.client.post("/api/chat", json={"mensagem": "bom dia"})
            ia.assert_called_once()
        self.assertEqual(res.get_json()["resposta"], "Oi!")

    def test_chat_regra_que_desiste_segue_pra_ia(self):
        desiste = "def casar(t):\n    return {'acao': 'x'}\ndef executar(conn, p):\n    return None\n"
        with _PastaRegras({self.nome: desiste}):
            with patch("claude_client.chat", return_value=("Da IA.", [], USO)) as ia:
                res = self.client.post("/api/chat", json={"mensagem": "qualquer coisa"})
            ia.assert_called_once()
        self.assertEqual(res.get_json()["resposta"], "Da IA.")

    def test_telegram_usa_o_mesmo_caminho_local(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.chat") as ia:
                self.assertEqual(app._telegram_chat_fn("assinei netflix 55 por mes"), "Assinatura registrada.")
            ia.assert_not_called()

    def test_captura_resolve_local_sem_chamar_ia_e_idempotente(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}) as pasta:
            with patch("claude_client.classify_capture") as ia:
                corpo_req = {"text": "assinei netflix 55 por mes", "client_id": "abc-123"}
                res = self.client.post("/api/capture", json=corpo_req)
                res2 = self.client.post("/api/capture", json=corpo_req)
            ia.assert_not_called()
            self.assertEqual(len(pasta.modulo(self.nome).CHAMADAS), 1)
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self.assertEqual(corpo["regra_local"], self.nome)
        self.assertEqual(corpo["acao"], "registrar_assinatura")
        self.assertEqual(corpo["cards"][0]["type"], "transacao")
        self.assertEqual(res2.get_json(), corpo)
        self.assertEqual(self.contar("expenses"), 1)

    def test_captura_sem_regra_que_case_segue_pra_ia(self):
        parsed = {"tipo": "tarefa", "titulo": "ligar pro dentista", "quando": None, "quando_data": None,
                  "hora": None, "duvida": None, "memoria": None}
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.classify_capture", return_value=(parsed, USO)) as ia:
                res = self.client.post("/api/capture", json={"text": "ligar pro dentista"})
            ia.assert_called_once()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["tipo"], "tarefa")

    def test_intent_primeira_camada_so_classifica(self):
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.classify_intent") as ia:
                res = self.client.post("/api/intent/classificar", json={"texto": "assinei netflix 55 por mes"})
            ia.assert_not_called()
        self.assertEqual(res.get_json(), {
            "acao": "registrar_assinatura", "confianca": 0.95,
            "parametros": {"servico": "netflix", "valor": 55.0},
            "precisa_confirmacao": False, "regra_local": self.nome,
        })
        self.assertEqual(self.contar("expenses"), 0)  # intent nunca executa

    def test_intent_sem_regra_que_case_segue_pra_ia(self):
        resultado = {"acao": "consultar", "confianca": 0.9, "parametros": {}, "precisa_confirmacao": False}
        with _PastaRegras({self.nome: REGRA_ASSINATURA}):
            with patch("claude_client.classify_intent", return_value=(resultado, USO)) as ia:
                res = self.client.post("/api/intent/classificar", json={"texto": "quanto gastei com ifood"})
            ia.assert_called_once()
        self.assertNotIn("regra_local", res.get_json())


if __name__ == "__main__":
    unittest.main()
