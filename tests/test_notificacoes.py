import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
import notificacoes


class NotificacoesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def test_sem_tarefa_atrasada_retorna_none(self):
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_tarefa_atrasada_e_contada(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        self.conn.commit()
        self.assertEqual(notificacoes.tarefas_atrasadas(self.conn), "Voce tem 1 tarefa atrasada.")

    def test_tarefa_concluida_nao_conta_como_atrasada(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("pagar conta", ontem),
        )
        self.conn.commit()
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_tarefa_sem_data_nao_conta_como_atrasada(self):
        self.conn.execute("INSERT INTO tasks (title) VALUES (?)", ("algo vago",))
        self.conn.commit()
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_meta_fora_do_ritmo_e_detectada(self):
        criado = (datetime.now() - timedelta(days=50)).isoformat()
        prazo = (date.today() + timedelta(days=50)).isoformat()
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("Moto", 10000, prazo, 100, criado),
        )
        self.conn.commit()
        avisos = notificacoes.metas_fora_do_ritmo(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Moto", avisos[0][1])

    def test_meta_no_ritmo_nao_e_avisada(self):
        criado = (datetime.now() - timedelta(days=50)).isoformat()
        prazo = (date.today() + timedelta(days=50)).isoformat()
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("Moto", 10000, prazo, 5000, criado),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.metas_fora_do_ritmo(self.conn), [])

    def test_meta_sem_prazo_e_ignorada(self):
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, valor_guardado) VALUES (?, ?, ?)",
            ("Sem prazo", 10000, 0),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.metas_fora_do_ritmo(self.conn), [])

    def test_gasto_semana_elevado_detectado(self):
        hoje = date.today()
        for i in range(1, 4):
            dia = hoje - timedelta(days=7 * i + 2)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (500, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        msg = notificacoes.gasto_semana_elevado(self.conn)
        self.assertIsNotNone(msg)
        self.assertIn("500.00", msg)

    def test_gasto_semana_normal_nao_avisa(self):
        hoje = date.today()
        for i in range(0, 4):
            dia = hoje - timedelta(days=7 * i + 1)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.commit()
        self.assertIsNone(notificacoes.gasto_semana_elevado(self.conn))


if __name__ == "__main__":
    unittest.main()
