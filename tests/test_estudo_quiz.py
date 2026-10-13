"""Quiz de aviacao com repeticao espacada (2026-10-13): estudo_quiz.py, ferramentas do
chat, card e POST /api/estudo/responder. Banco temporario, IA nunca chamada."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import cards  # noqa: E402
import db  # noqa: E402
import estudo  # noqa: E402
import estudo_quiz as q  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"
HOJE = date(2026, 10, 13)
PERGUNTA = {
    "tema": "Meteorologia aeronautica",
    "enunciado": "Qual nuvem esta associada a trovoada e forte turbulencia?",
    "alternativas": ["Cirrus", "Cumulonimbus", "Estratos", "Altocumulus"],
    "correta": 1,
    "explicacao": "O CB tem desenvolvimento vertical forte, com trovoada, granizo e turbulencia severa.",
}


def _banco():
    db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
    if db.DB_PATH.exists():
        db.DB_PATH.unlink()
    db.init_db()
    return db.get_db()


class LeitnerTestCase(unittest.TestCase):
    def test_errou_volta_amanha_na_caixa_zero(self):
        self.assertEqual(q.agendar(3, False, HOJE), (0, HOJE + timedelta(days=1)))

    def test_acerto_sobe_caixa_e_espaca(self):
        esperados = [(1, 3), (2, 7), (3, 14), (4, 30), (5, 60), (5, 60)]
        caixa = 0
        for nova, dias in esperados:
            caixa, prox = q.agendar(caixa, True, HOJE)
            self.assertEqual((caixa, prox), (nova, HOJE + timedelta(days=dias)))

    def test_letras(self):
        for v, esperado in (("b", 1), ("B", 1), ("letra c", 2), ("Alternativa D", 3), (0, 0), ("2", 2),
                            ("E", None), ("", None), (None, None), (True, None), (7, None), ("ab", None)):
            with self.subTest(v=v):
                self.assertEqual(q.letra_pra_indice(v), esperado)


class ValidacaoTestCase(unittest.TestCase):
    def test_tema_so_dos_fixos_com_ou_sem_acento(self):
        for t, esperado in (("Meteorologia", "Meteorologia aeronautica"), ("regulamentação", estudo.TEMAS[0]),
                            ("Navegação", "Navegacao"), ("Teoria de voo", None), ("", None)):
            with self.subTest(t=t):
                p, erro = q.validar_pergunta({**PERGUNTA, "tema": t})
                if esperado:
                    self.assertEqual(p["tema"], esperado)
                else:
                    self.assertIsNone(p)
                    self.assertIn("tema", erro)

    def test_pergunta_mal_formada_e_recusada(self):
        ruins = [
            {"alternativas": ["a", "b", "c"]},
            {"alternativas": ["a", "a", "b", "c"]},
            {"alternativas": ["a", "", "b", "c"]},
            {"correta": 4},
            {"correta": "x"},
            {"enunciado": "oi"},
            {"explicacao": ""},
            {"alternativas": "abcd"},
        ]
        for extra in ruins:
            with self.subTest(extra=extra):
                p, erro = q.validar_pergunta({**PERGUNTA, **extra})
                self.assertIsNone(p)
                self.assertTrue(erro)

    def test_tamanho_limitado(self):
        p, _ = q.validar_pergunta({**PERGUNTA, "enunciado": "x" * 5000, "explicacao": "y" * 5000})
        self.assertEqual(len(p["enunciado"]), q.LIMITE_ENUNCIADO)
        self.assertEqual(len(p["explicacao"]), q.LIMITE_EXPLICACAO)

    def test_enum_da_ferramenta_igual_aos_temas_fixos(self):
        from ia.funcoes.chat import CHAT_TOOLS
        tool = next(t for t in CHAT_TOOLS if t["name"] == "fazer_pergunta_aviacao")
        self.assertEqual(tool["input_schema"]["properties"]["tema"]["enum"], list(estudo.TEMAS))
        nomes = {t["name"] for t in CHAT_TOOLS}
        self.assertTrue({"revisar_pergunta_aviacao", "responder_pergunta_aviacao"} <= nomes)


class FluxoTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _banco()

    def tearDown(self):
        self.conn.close()

    def test_card_nao_entrega_a_resposta(self):
        p = q.criar(self.conn, PERGUNTA)
        card = cards.card_quiz_aviacao({"dados": q.dados_card(p)})
        self.assertEqual(card["type"], "quiz_aviacao")
        self.assertNotIn("correta", card["data"])
        self.assertNotIn("explicacao", card["data"])
        self.assertNotIn("resposta", card["data"])

    def test_errar_agenda_pra_amanha_e_revisao_traz_de_volta(self):
        p = q.criar(self.conn, PERGUNTA)
        r = q.responder(self.conn, p["id"], "A", HOJE)
        self.assertFalse(r["acertou"])
        self.assertEqual((r["correta_letra"], r["caixa"]), ("B", 0))
        self.assertEqual(r["proxima_revisao"], (HOJE + timedelta(days=1)).isoformat())
        self.assertIsNone(q.revisar_pendente(self.conn, HOJE))
        volta = q.revisar_pendente(self.conn, HOJE + timedelta(days=1))
        self.assertEqual(volta["id"], p["id"])
        r2 = q.responder(self.conn, p["id"], "b", HOJE + timedelta(days=1))
        self.assertTrue(r2["acertou"])
        self.assertEqual(r2["caixa"], 1)

    def test_responder_de_novo_sem_vencer_nao_mexe_na_agenda(self):
        p = q.criar(self.conn, PERGUNTA)
        q.responder(self.conn, p["id"], "B", HOJE)
        r = q.responder(self.conn, p["id"], "B", HOJE)
        self.assertTrue(r["repetida"])
        linha = q._linha(self.conn, p["id"])
        self.assertEqual((linha["acertos"], linha["caixa"]), (1, 1))

    def test_sem_id_responde_a_ultima_aberta(self):
        q.criar(self.conn, PERGUNTA)
        p2 = q.criar(self.conn, {**PERGUNTA, "enunciado": "Outra pergunta qualquer de meteorologia?"})
        r = q.responder(self.conn, None, "letra b", HOJE)
        self.assertEqual(r["id"], p2["id"])

    def test_linha_de_contexto(self):
        self.assertIsNone(q.linha_contexto(self.conn, HOJE))
        p = q.criar(self.conn, PERGUNTA)
        q.responder(self.conn, p["id"], "C", HOJE)
        txt = q.linha_contexto(self.conn, HOJE + timedelta(days=1))
        self.assertIn("1 pergunta(s) de revisão vencida(s)", txt)
        self.assertIn("Meteorologia", txt)


class RotaTestCase(unittest.TestCase):
    def setUp(self):
        conn = _banco()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        self.pid = q.criar(conn, PERGUNTA)["id"]
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)

    def test_responde_pelo_card(self):
        res = self.client.post("/api/estudo/responder", json={"id": self.pid, "alternativa": "B"})
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertTrue(corpo["acertou"])
        self.assertEqual(corpo["correta"], 1)
        self.assertIn("CB", corpo["explicacao"])

    def test_entrada_ruim(self):
        for corpo, status in (({"id": self.pid, "alternativa": "Z"}, 400), ({"id": "1", "alternativa": "A"}, 400),
                              ({"id": True, "alternativa": "A"}, 400), ({"alternativa": "A"}, 400),
                              ({"id": 99999, "alternativa": "A"}, 404), ({}, 400)):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post("/api/estudo/responder", json=corpo).status_code, status)

    def test_exige_login(self):
        res = app.app.test_client().post("/api/estudo/responder", json={"id": self.pid, "alternativa": "B"})
        self.assertIn(res.status_code, (302, 401))


if __name__ == "__main__":
    unittest.main()
