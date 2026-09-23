import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def test_pin_nao_configurado_no_banco_novo(self):
        self.assertFalse(auth.pin_configurado(self.conn))

    def test_definir_pin_valido(self):
        auth.definir_pin(self.conn, "123456", "123456")
        self.assertTrue(auth.pin_configurado(self.conn))
        self.assertTrue(auth.verificar_pin(self.conn, "123456"))

    def test_hash_nunca_guarda_pin_em_texto_puro(self):
        auth.definir_pin(self.conn, "123456", "123456")
        hash_salvo = db.obter_configuracao(self.conn, "pin_hash")
        self.assertNotIn("123456", hash_salvo)

    def test_definir_pin_rejeita_tamanho_errado(self):
        for pin_ruim in ["12345", "1234567", "", "12345a"]:
            with self.subTest(pin=pin_ruim):
                with self.assertRaises(ValueError):
                    auth.definir_pin(self.conn, pin_ruim, pin_ruim)

    def test_definir_pin_rejeita_nao_numerico(self):
        with self.assertRaises(ValueError):
            auth.definir_pin(self.conn, "abcdef", "abcdef")

    def test_definir_pin_rejeita_confirmacao_diferente(self):
        with self.assertRaises(ValueError):
            auth.definir_pin(self.conn, "123456", "654321")

    def test_definir_pin_aceita_espacos_nas_bordas(self):
        auth.definir_pin(self.conn, " 123456 ", " 123456 ")
        self.assertTrue(auth.verificar_pin(self.conn, "123456"))

    def test_verificar_pin_errado_falha(self):
        auth.definir_pin(self.conn, "123456", "123456")
        self.assertFalse(auth.verificar_pin(self.conn, "654321"))

    def test_verificar_pin_sem_pin_configurado_falha_sem_quebrar(self):
        self.assertFalse(auth.verificar_pin(self.conn, "123456"))

    def test_verificar_pin_entrada_vazia_ou_none_nao_quebra(self):
        auth.definir_pin(self.conn, "123456", "123456")
        self.assertFalse(auth.verificar_pin(self.conn, ""))
        self.assertFalse(auth.verificar_pin(self.conn, None))

    def test_secret_key_e_gerada_e_persistida(self):
        chave1 = auth.obter_ou_criar_secret_key(self.conn)
        self.assertEqual(len(chave1), 64)  # secrets.token_hex(32) -> 64 chars hex
        chave2 = auth.obter_ou_criar_secret_key(self.conn)
        self.assertEqual(chave1, chave2)

    def test_secret_key_persiste_em_nova_conexao(self):
        chave1 = auth.obter_ou_criar_secret_key(self.conn)
        outra_conn = db.get_db()
        try:
            chave2 = auth.obter_ou_criar_secret_key(outra_conn)
        finally:
            outra_conn.close()
        self.assertEqual(chave1, chave2)

    def test_sem_tentativas_nao_bloqueia(self):
        pode, msg = auth.verificar_bloqueio(self.conn, "1.2.3.4")
        self.assertTrue(pode)
        self.assertIsNone(msg)

    def test_poucas_tentativas_erradas_nao_bloqueia(self):
        for _ in range(4):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False)
        pode, msg = auth.verificar_bloqueio(self.conn, "1.2.3.4")
        self.assertTrue(pode)

    def test_cinco_tentativas_erradas_bloqueia(self):
        for _ in range(5):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False)
        pode, msg = auth.verificar_bloqueio(self.conn, "1.2.3.4")
        self.assertFalse(pode)
        self.assertIn("minuto", msg)

    def test_bloqueio_e_por_ip_nao_afeta_outros(self):
        for _ in range(5):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False)
        pode, _ = auth.verificar_bloqueio(self.conn, "9.9.9.9")
        self.assertTrue(pode)

    def test_tentativa_com_sucesso_zera_contador(self):
        for _ in range(4):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False)
        auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=True)
        row = self.conn.execute(
            "SELECT tentativas, bloqueado_ate FROM login_tentativas WHERE ip = ?", ("1.2.3.4",)
        ).fetchone()
        self.assertEqual(row["tentativas"], 0)
        self.assertEqual(row["bloqueado_ate"], 0)

    def test_bloqueio_expira_com_o_tempo(self):
        for _ in range(5):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False, agora=1000.0)
        pode, _ = auth.verificar_bloqueio(self.conn, "1.2.3.4", agora=1000.0 + 301)
        self.assertTrue(pode)

    def test_bloqueio_ainda_vale_um_segundo_antes_de_expirar(self):
        for _ in range(5):
            auth.registrar_tentativa(self.conn, "1.2.3.4", sucesso=False, agora=1000.0)
        pode, _ = auth.verificar_bloqueio(self.conn, "1.2.3.4", agora=1000.0 + 299)
        self.assertFalse(pode)


if __name__ == "__main__":
    unittest.main()
