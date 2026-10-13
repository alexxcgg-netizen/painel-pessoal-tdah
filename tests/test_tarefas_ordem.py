"""Aba Tarefas em ordem de agenda (2026-10-13): GET /api/tasks devolve por dia
(atrasada/hoje primeiro), dentro do dia por horario, sem horario no fim do dia dela e
sem data no fim da lista. Banco temporario."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class OrdemDeAgendaTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        hoje = date.today()
        ontem, amanha = (hoje - timedelta(days=1)).isoformat(), (hoje + timedelta(days=1)).isoformat()
        # criadas fora de ordem de proposito (a ordem antiga era a de criacao)
        for titulo, dia, hora in (
            ("sem data", None, None),
            ("hoje 10:30", hoje.isoformat(), "10:30"),
            ("amanha 09:00", amanha, "09:00"),
            ("hoje sem hora", hoje.isoformat(), None),
            ("hoje 08:00", hoje.isoformat(), "08:00"),
            ("ontem 18:00", ontem, "18:00"),
            ("hoje 10:00", hoje.isoformat(), "10:00"),
        ):
            conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", (titulo, dia, hora))
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)

    def test_ordem_de_agenda(self):
        titulos = [t["title"] for t in self.client.get("/api/tasks").get_json()]
        self.assertEqual(titulos, ["ontem 18:00", "hoje 08:00", "hoje 10:00", "hoje 10:30", "hoje sem hora",
                                   "amanha 09:00", "sem data"])


if __name__ == "__main__":
    unittest.main()
