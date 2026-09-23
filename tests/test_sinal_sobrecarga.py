import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import notificacoes

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class SinalSobrecargaPuroTestCase(unittest.TestCase):
    def test_nenhum_sinal(self):
        r = notificacoes.sinal_sobrecarga(0, False, False)
        self.assertEqual(r["pontuacao"], 0)
        self.assertFalse(r["sobrecarregado"])
        self.assertEqual(r["sinais"], [])

    def test_um_sinal_isolado_nao_e_sobrecarga(self):
        r = notificacoes.sinal_sobrecarga(5, False, False)
        self.assertEqual(r["pontuacao"], 1)
        self.assertFalse(r["sobrecarregado"])
        self.assertEqual(r["sinais"], ["tarefas atrasadas"])

    def test_tarefas_atrasadas_abaixo_do_minimo_nao_conta(self):
        r = notificacoes.sinal_sobrecarga(2, False, False)
        self.assertEqual(r["pontuacao"], 0)

    def test_tarefas_atrasadas_no_minimo_conta(self):
        r = notificacoes.sinal_sobrecarga(3, False, False)
        self.assertEqual(r["pontuacao"], 1)

    def test_dois_sinais_e_sobrecarga(self):
        r = notificacoes.sinal_sobrecarga(4, True, False)
        self.assertEqual(r["pontuacao"], 2)
        self.assertTrue(r["sobrecarregado"])
        self.assertEqual(set(r["sinais"]), {"tarefas atrasadas", "sono ruim"})

    def test_tres_sinais(self):
        r = notificacoes.sinal_sobrecarga(4, True, True)
        self.assertEqual(r["pontuacao"], 3)
        self.assertTrue(r["sobrecarregado"])
        self.assertEqual(set(r["sinais"]), {"tarefas atrasadas", "sono ruim", "semana pesada"})

    def test_so_semana_pesada_nao_e_sobrecarga(self):
        r = notificacoes.sinal_sobrecarga(0, False, True)
        self.assertEqual(r["pontuacao"], 1)
        self.assertFalse(r["sobrecarregado"])

    def test_sono_ruim_mais_semana_pesada_e_sobrecarga(self):
        r = notificacoes.sinal_sobrecarga(0, True, True)
        self.assertEqual(r["pontuacao"], 2)
        self.assertTrue(r["sobrecarregado"])


class SobrecargaApiTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def tearDown(self):
        self.conn.close()

    def test_sem_sinal_nenhum(self):
        res = self.client.get("/api/sobrecarga")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados["pontuacao"], 0)
        self.assertFalse(dados["sobrecarregado"])

    def test_tarefas_atrasadas_reais_contam(self):
        hoje = date.today()
        atrasada = (hoje - timedelta(days=5)).isoformat()
        for i in range(3):
            self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", (f"T{i}", atrasada))
        self.conn.commit()
        res = self.client.get("/api/sobrecarga")
        dados = res.get_json()
        self.assertIn("tarefas atrasadas", dados["sinais"])

    def test_tarefa_concluida_nao_conta_como_atrasada(self):
        hoje = date.today()
        atrasada = (hoje - timedelta(days=5)).isoformat()
        for i in range(5):
            self.conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
                (f"T{i}", atrasada),
            )
        self.conn.commit()
        res = self.client.get("/api/sobrecarga")
        self.assertEqual(res.get_json()["pontuacao"], 0)

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/sobrecarga")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
