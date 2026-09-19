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

    def test_lembrete_unico_proximo_e_avisado(self):
        data = (date.today() + timedelta(days=3)).isoformat()
        db.create_lembrete(self.conn, "Renovar seguro do carro", data, recorrente=False)
        avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Renovar seguro do carro", avisos[0][1])
        self.assertIn("3 dias", avisos[0][1])

    def test_lembrete_unico_longe_nao_avisa(self):
        data = (date.today() + timedelta(days=30)).isoformat()
        db.create_lembrete(self.conn, "Renovar seguro do carro", data, recorrente=False)
        self.assertEqual(notificacoes.lembretes_proximos(self.conn), [])

    def test_lembrete_unico_ja_passou_nao_avisa(self):
        data = (date.today() - timedelta(days=2)).isoformat()
        db.create_lembrete(self.conn, "Coisa antiga", data, recorrente=False)
        self.assertEqual(notificacoes.lembretes_proximos(self.conn), [])

    def test_lembrete_recorrente_calcula_proximo_aniversario(self):
        data_original = (date.today() - timedelta(days=360)).isoformat()
        db.create_lembrete(self.conn, "Validade da licenca de piloto", data_original, recorrente=True)
        avisos = notificacoes.lembretes_proximos(self.conn, dias=10)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Validade da licenca de piloto", avisos[0][1])

    def test_lembrete_recorrente_hoje(self):
        data_original = date.today().replace(year=date.today().year - 1).isoformat()
        db.create_lembrete(self.conn, "Aniversario", data_original, recorrente=True)
        avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("e hoje", avisos[0][1])

    def test_tarefa_com_horario_ja_chegado_e_avisada(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "14:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=14, minute=5)
        avisos = notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora)
        self.assertEqual(len(avisos), 1)
        self.assertIn("colocar o lixo pra fora", avisos[0][1])

    def test_tarefa_com_horario_ainda_nao_chegado_nao_avisa(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "14:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=13, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_com_horario_de_outro_dia_nao_avisa(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta amanha", amanha, "09:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_sem_horario_nunca_avisa_aqui(self):
        hoje = date.today().isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("so com prazo", hoje))
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_com_horario_concluida_nao_avisa(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, datetime('now'))",
            ("ja fiz", hoje, "08:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])


if __name__ == "__main__":
    unittest.main()
