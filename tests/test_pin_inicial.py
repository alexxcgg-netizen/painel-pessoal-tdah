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


class PinInicialTestCase(unittest.TestCase):
    """PAINEL_PIN_INICIAL: fecha a janela em que o primeiro visitante de uma
    URL publica nova (ex: Render) escolheria o PIN."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_sem_variavel_nao_faz_nada(self):
        self.assertFalse(app._aplicar_pin_inicial(self.conn, None))
        self.assertFalse(app._aplicar_pin_inicial(self.conn, ""))
        self.assertFalse(auth.pin_configurado(self.conn))

    def test_define_pin_quando_ainda_nao_existe(self):
        self.assertTrue(app._aplicar_pin_inicial(self.conn, "482913"))
        self.assertTrue(auth.verificar_pin(self.conn, "482913"))

    def test_nunca_sobrescreve_pin_existente(self):
        auth.definir_pin(self.conn, "111111", "111111")
        self.conn.commit()
        self.assertFalse(app._aplicar_pin_inicial(self.conn, "222222"))
        self.assertTrue(auth.verificar_pin(self.conn, "111111"))
        self.assertFalse(auth.verificar_pin(self.conn, "222222"))

    def test_pin_invalido_derruba_em_vez_de_deixar_configuracao_aberta(self):
        for invalido in ("123", "abcdef", "1234567", " 12 34 "):
            with self.assertRaises(RuntimeError):
                app._aplicar_pin_inicial(self.conn, invalido)
        self.assertFalse(auth.pin_configurado(self.conn))

    def test_com_pin_inicial_configurar_pin_fica_fechado(self):
        app._aplicar_pin_inicial(self.conn, "482913")
        client = app.app.test_client()
        res = client.post("/configurar-pin", data={"pin": "000000", "confirmacao": "000000"})
        self.assertNotEqual(res.status_code, 200)
        self.assertTrue(auth.verificar_pin(self.conn, "482913"))
        self.assertFalse(auth.verificar_pin(self.conn, "000000"))


if __name__ == "__main__":
    unittest.main()
