"""Fase 7 / C1 - historia 5: percentual de meta com UMA funcao so
(calculos.percentual_meta_exibicao) no card de meta (cards.py), no
consultar_meta do chat e no /api/progresso (app.py) - antes eram 3 contas
com arredondamentos diferentes (1 casa, 0 casas)."""
import math
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import calculos  # noqa: E402
import cards  # noqa: E402

PIN_TESTE = "123456"


class FuncaoUnicaTestCase(unittest.TestCase):
    def test_casos(self):
        casos = [
            ((0, 100), 0.0), ((50, 100), 50.0), ((1, 3), 33.3), ((2, 3), 66.7),
            ((150, 100), 100.0), ((-10, 100), 0.0), ((10, 0), 0.0), ((10, -5), 0.0),
            ((None, 100), 0.0), ((10, None), 0.0), (("abc", 100), 0.0), ((float("nan"), 100), 0.0),
            ((float("inf"), 100), 0.0), ((Decimal("0.05"), 100), 0.0), ((0.25, 100), 0.2),
            ((0.35, 100), 0.4), ((99.96, 100), 100.0), ((1e308, 1e-308), 100.0),
        ]
        for (atual, alvo), esperado in casos:
            with self.subTest(atual=atual, alvo=alvo):
                valor = calculos.percentual_meta_exibicao(atual, alvo)
                self.assertIsInstance(valor, float)
                self.assertEqual(valor, esperado)
                self.assertTrue(0.0 <= valor <= 100.0 and math.isfinite(valor))

    def test_bate_com_a_funcao_estrita_arredondada(self):
        for atual in range(0, 1001, 7):
            estrito = calculos.percentual_meta(atual, 997)
            self.assertAlmostEqual(calculos.percentual_meta_exibicao(atual, 997), float(estrito), delta=0.0501)


class MesmoNumeroEmTodaTelaTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        self.meta_id = db.create_goal(conn, "Reserva de emergencia sintetica", 3000.0, None)
        conn.execute("UPDATE goals SET valor_guardado = 1000 WHERE id = ?", (self.meta_id,))
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200

    def test_card_chat_e_progresso_mostram_o_mesmo_percentual(self):
        conn = db.get_db()
        try:
            card = cards.card_meta(conn, self.meta_id)
            consulta = app._consultar_meta(conn, "reserva")
        finally:
            conn.close()
        progresso = self.client.get("/api/progresso").get_json()
        pct_card = card["data"]["percentual"]
        pct_chat = consulta["metas"][0]["percentual"]
        pct_progresso = [m["pct"] for m in progresso["metas"] if m["titulo"].startswith("Reserva")][0]
        self.assertEqual(pct_card, 33.3)
        self.assertEqual(pct_card, pct_chat)
        self.assertEqual(pct_card, pct_progresso)


if __name__ == "__main__":
    unittest.main()
