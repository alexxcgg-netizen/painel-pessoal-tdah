"""POST /api/diagnostico (2026-10-15): medidas reais do aparelho (tela/microfone) pra parar de
chutar bug de iPhone. So numero/nome de erro, nunca falha alto, guarda as ultimas 500."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from rotas import diagnostico  # noqa: E402

PIN = "123456"


class DiagnosticoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def _linhas(self):
        conn = db.get_db()
        try:
            return [(r["tipo"], json.loads(r["dados_json"])) for r in conn.execute("SELECT * FROM diagnostico_cliente ORDER BY id")]
        finally:
            conn.close()

    def test_grava_so_numero_e_texto_curto(self):
        r = self.client.post("/api/diagnostico", json={"tipo": "tela", "dados": {
            "motivo": "voltou", "innerH": 844, "vvH": 878.5, "app": True, "lista": [1, 2], "obj": {"a": 1},
            "longo": "x" * 500, "x" * 40: 1,
        }})
        self.assertEqual(r.status_code, 204)
        [(tipo, dados)] = self._linhas()
        self.assertEqual(tipo, "tela")
        self.assertEqual(dados["innerH"], 844)
        self.assertEqual(dados["vvH"], 878.5)
        self.assertIs(dados["app"], True)
        self.assertNotIn("lista", dados)
        self.assertNotIn("obj", dados)
        self.assertEqual(len(dados["longo"]), 80)
        self.assertEqual(len(dados), 5)

    def test_lixo_nao_quebra_nem_grava(self):
        for corpo in (None, [], {"tipo": "outro", "dados": {}}, {"tipo": "mic", "dados": "x"}):
            r = self.client.post("/api/diagnostico", data=json.dumps(corpo), content_type="application/json")
            self.assertEqual(r.status_code, 204)
        self.assertEqual(self._linhas(), [])

    def test_guarda_so_as_ultimas(self):
        antes = diagnostico.MAX_LINHAS
        diagnostico.MAX_LINHAS = 3
        try:
            for i in range(5):
                self.client.post("/api/diagnostico", json={"tipo": "mic", "dados": {"i": i}})
        finally:
            diagnostico.MAX_LINHAS = antes
        self.assertEqual([d["i"] for _, d in self._linhas()], [2, 3, 4])

    def test_precisa_de_login(self):
        self.client.post("/logout")
        r = app.app.test_client().post("/api/diagnostico", json={"tipo": "mic", "dados": {"i": 1}})
        self.assertIn(r.status_code, (401, 302, 403))
        self.assertEqual(self._linhas(), [])


if __name__ == "__main__":
    unittest.main()
