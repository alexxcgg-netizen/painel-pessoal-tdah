"""Fase 6, Grupo F, faixa Painel/Tarefas (F2) - US-F6 a US-F10.

A maioria das historias deste grupo foi so polimento visual (HTML/CSS/JS do
Painel, verificado com Playwright headless, nao com teste unitario aqui) -
este arquivo cobre so a parte com logica de servidor nova: US-F10 (POST
/api/tasks direto, com prazo opcional).

Segue o padrao de tests/test_pin_inicial.py: db.DB_PATH pra um arquivo
temporario + db.garantir_banco_nao_producao() ANTES de importar app."""

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
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class Fase6F2TarefasTestCase(unittest.TestCase):
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

    # ---- US-F10: POST /api/tasks direto (formulario, sem IA) -------------

    def test_criar_tarefa_direta_sem_prazo(self):
        res = self.client.post("/api/tasks", json={"titulo": "limpar o quarto"})
        self.assertEqual(res.status_code, 201)
        task_id = res.get_json()["id"]

        conn = db.get_db()
        row = conn.execute("SELECT title, due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        self.assertEqual(row["title"], "limpar o quarto")
        self.assertIsNone(row["due_date"])

    def test_criar_tarefa_direta_com_prazo(self):
        hoje = date.today().isoformat()
        res = self.client.post("/api/tasks", json={"titulo": "pagar boleto", "due_date": hoje})
        self.assertEqual(res.status_code, 201)
        task_id = res.get_json()["id"]

        conn = db.get_db()
        row = conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        self.assertEqual(row["due_date"], hoje)

    def test_criar_tarefa_direta_aparece_no_get_tasks(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.client.post("/api/tasks", json={"titulo": "comprar tijolo", "due_date": amanha})

        tarefas = self.client.get("/api/tasks").get_json()
        alvo = next(t for t in tarefas if t["title"] == "comprar tijolo")
        self.assertEqual(alvo["due_date"], amanha)
        self.assertIsNone(alvo["completed_at"])

    def test_criar_tarefa_direta_sem_titulo_400(self):
        res = self.client.post("/api/tasks", json={"titulo": "   "})
        self.assertEqual(res.status_code, 400)

    def test_criar_tarefa_direta_titulo_ausente_400(self):
        res = self.client.post("/api/tasks", json={"due_date": date.today().isoformat()})
        self.assertEqual(res.status_code, 400)

    def test_criar_tarefa_direta_prazo_mal_formatado_400(self):
        res = self.client.post("/api/tasks", json={"titulo": "algo", "due_date": "31/12/2026"})
        self.assertEqual(res.status_code, 400)

    def test_criar_tarefa_direta_titulo_muito_longo_400(self):
        res = self.client.post("/api/tasks", json={"titulo": "a" * 201})
        self.assertEqual(res.status_code, 400)

    def test_criar_tarefa_direta_prazo_vazio_vira_none(self):
        """Prazo e opcional de verdade - string vazia (campo deixado em
        branco no formulario) nao deve virar erro de formato, so None."""
        res = self.client.post("/api/tasks", json={"titulo": "sem prazo mesmo", "due_date": ""})
        self.assertEqual(res.status_code, 201)
        task_id = res.get_json()["id"]
        conn = db.get_db()
        row = conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        self.assertIsNone(row["due_date"])

    def test_tarefa_antiga_sem_prazo_continua_valida(self):
        """Acceptance criteria da US-F10: tarefa sem due_date (jeito antigo,
        de antes desta historia existir) continua aparecendo normalmente em
        /api/tasks - devolvida como um dict comum, sem due_date quebrando
        nada (nem 500, nem sumir da lista)."""
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES (?)", ("tarefa bem antiga",))
        conn.commit()
        conn.close()

        tarefas = self.client.get("/api/tasks").get_json()
        alvo = next(t for t in tarefas if t["title"] == "tarefa bem antiga")
        self.assertIsNone(alvo["due_date"])
        self.assertIsNone(alvo["due_at"])


if __name__ == "__main__":
    unittest.main()
