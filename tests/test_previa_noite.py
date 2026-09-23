import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class PreviaNoiteAnteriorTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_sem_dado_nenhum(self):
        hoje = date(2026, 6, 15)
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["data"], "2026-06-14")
        self.assertIsNone(resultado["sono_horas"])
        self.assertIsNone(resultado["sono_checkin"])
        self.assertEqual(resultado["copos_agua"], 0)
        self.assertEqual(resultado["medicamentos_total"], 0)

    def test_sono_do_saude_dados(self):
        hoje = date(2026, 6, 15)
        db.upsert_saude_dia(self.conn, "2026-06-14", {"sono_horas": 7.5})
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["sono_horas"], 7.5)

    def test_sono_do_checkin(self):
        hoje = date(2026, 6, 15)
        db.salvar_checkin(self.conn, "2026-06-14", {"sono": 4})
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["sono_checkin"], 4)

    def test_hidratacao_de_ontem_conta_hoje_nao(self):
        hoje = date(2026, 6, 15)
        db.registrar_hidratacao(self.conn, "2026-06-14")
        db.registrar_hidratacao(self.conn, "2026-06-14")
        db.registrar_hidratacao(self.conn, "2026-06-15")
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["copos_agua"], 2)

    def test_medicamento_tomado_ontem(self):
        hoje = date(2026, 6, 15)
        task_id = self.conn.execute(
            "INSERT INTO tasks (title, recorrencia) VALUES ('Remedio X', 'diaria')"
        ).lastrowid
        self.conn.commit()
        med_id = db.create_medicamento(self.conn, "Remedio X", "10mg", "08:00", "diaria", task_id)
        instancia_id = self.conn.execute(
            "INSERT INTO tasks (title, due_date, recorrente_origem_id, completed_at) "
            "VALUES ('Remedio X', '2026-06-14', ?, datetime('now'))",
            (task_id,),
        ).lastrowid
        self.conn.commit()
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["medicamentos_total"], 1)
        self.assertEqual(resultado["medicamentos_tomados"], 1)
        self.assertTrue(med_id and instancia_id)

    def test_medicamento_nao_tomado_ontem(self):
        hoje = date(2026, 6, 15)
        task_id = self.conn.execute(
            "INSERT INTO tasks (title, recorrencia) VALUES ('Remedio Y', 'diaria')"
        ).lastrowid
        self.conn.commit()
        db.create_medicamento(self.conn, "Remedio Y", "5mg", "20:00", "diaria", task_id)
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, recorrente_origem_id) VALUES ('Remedio Y', '2026-06-14', ?)",
            (task_id,),
        )
        self.conn.commit()
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["medicamentos_total"], 1)
        self.assertEqual(resultado["medicamentos_tomados"], 0)

    def test_medicamento_sem_instancia_ontem_nao_conta(self):
        hoje = date(2026, 6, 15)
        task_id = self.conn.execute(
            "INSERT INTO tasks (title, recorrencia) VALUES ('Remedio Z', 'semanal')"
        ).lastrowid
        self.conn.commit()
        db.create_medicamento(self.conn, "Remedio Z", "1x", "09:00", "semanal", task_id)
        resultado = app._previa_noite_anterior(self.conn, hoje)
        self.assertEqual(resultado["medicamentos_total"], 0)


class PreviaNoiteApiTestCase(unittest.TestCase):
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

    def test_rota_retorna_estrutura_esperada(self):
        res = self.client.get("/api/previa-noite")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        for chave in ("data", "sono_horas", "sono_checkin", "copos_agua", "medicamentos_tomados", "medicamentos_total"):
            self.assertIn(chave, dados)

    def test_rota_oculta_com_modo_visitante(self):
        conn = db.get_db()
        db.upsert_saude_dia(conn, (date.today() - timedelta(days=1)).isoformat(), {"sono_horas": 3.0})
        conn.close()
        self.client.post("/api/modo-visitante", json={"ativar": True})
        res = self.client.get("/api/previa-noite")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("oculto"))
        self.assertNotIn(b"3.0", res.data)

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/previa-noite")
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
