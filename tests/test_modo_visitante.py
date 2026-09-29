import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class ModoVisitanteTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def test_estado_inicial_desligado(self):
        res = self.client.get("/api/modo-visitante")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["ativo"])

    def test_ativar_nao_precisa_de_pin(self):
        res = self.client.post("/api/modo-visitante", json={"ativar": True})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["ativo"])
        self.assertTrue(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_desativar_sem_pin_e_recusado_e_continua_ativo(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        res = self.client.post("/api/modo-visitante", json={"ativar": False})
        self.assertEqual(res.status_code, 403)
        self.assertTrue(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_desativar_com_pin_errado_e_recusado(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        res = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": "000000"})
        self.assertEqual(res.status_code, 403)
        self.assertTrue(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_desativar_com_pin_certo_funciona(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        res = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": PIN_TESTE})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["ativo"])
        self.assertFalse(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_estado_nao_persiste_no_banco(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        conn = db.get_db()
        tabelas = [
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        conn.close()
        self.assertNotIn("modo_visitante", tabelas)
        conn_temp = db.get_db()
        valor_config = conn_temp.execute(
            "SELECT valor FROM configuracoes WHERE chave = 'modo_visitante'"
        ).fetchone()
        conn_temp.close()
        self.assertIsNone(valor_config)

    def test_estado_some_no_logout(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        self.client.post("/logout")
        self.client.post("/login", json={"pin": PIN_TESTE})
        self.assertFalse(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/modo-visitante")
        self.assertEqual(res.status_code, 401)

    def test_pin_errado_repetido_bloqueia_temporariamente(self):
        """Achado da revisao de seguranca da Fase 5: antes, o PIN do modo
        visitante nao tinha limite de tentativas (diferente do /login) -
        agora reusa o mesmo mecanismo (auth.verificar_bloqueio/registrar_tentativa)."""
        self.client.post("/api/modo-visitante", json={"ativar": True})
        for _ in range(auth.TENTATIVAS_PARA_BLOQUEAR):
            res = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": "000000"})
            self.assertEqual(res.status_code, 403)

        res_bloqueado = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": "000000"})
        self.assertEqual(res_bloqueado.status_code, 429)

        res_pin_certo_tambem_bloqueado = self.client.post(
            "/api/modo-visitante", json={"ativar": False, "pin": PIN_TESTE}
        )
        self.assertEqual(res_pin_certo_tambem_bloqueado.status_code, 429)
        self.assertTrue(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_estado_e_por_sessao_nao_vaza_pra_outro_cliente(self):
        outro_client = app.app.test_client()
        res_login = outro_client.post("/login", json={"pin": PIN_TESTE})
        assert res_login.status_code == 200
        self.client.post("/api/modo-visitante", json={"ativar": True})
        self.assertFalse(outro_client.get("/api/modo-visitante").get_json()["ativo"])


if __name__ == "__main__":
    unittest.main()
