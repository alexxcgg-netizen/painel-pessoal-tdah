"""Faixa M3 (uso diario, ver scratchpad/uso/BRIEF.md): aba Tarefas ganha um
"Ver concluidas" (GET /api/tasks?estado=concluidas) - concluida some da lista
padrao mas NUNCA e apagada do banco. Cobre:
  - comportamento padrao de GET /api/tasks continua identico (nao traz concluida);
  - ?estado=concluidas traz as concluidas (mais recentes primeiro, limite 50);
  - completar/reabrir so mexe em completed_at - a linha nunca some da tabela;
  - fuzzing leve do parametro `estado` (nunca 500).

Banco sempre temporario, sem IA/Pluggy real - mesmo padrao de tests/test_fase9_api.py.
"""

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


class TarefasConcluidasTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        self.conn.commit()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def tearDown(self):
        self.conn.close()

    def _criar_tarefa(self, titulo="tarefa de teste"):
        cur = self.conn.execute("INSERT INTO tasks (title) VALUES (?)", (titulo,))
        self.conn.commit()
        return cur.lastrowid

    def _linha_no_banco(self, task_id):
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    # ---- comportamento padrao (sem parametro) --------------------------------

    def test_padrao_nao_traz_concluidas(self):
        tid = self._criar_tarefa()
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/complete").status_code, 200)

        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(tasks, [])

    def test_padrao_continua_trazendo_pendentes(self):
        tid = self._criar_tarefa("pendente")
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual([t["id"] for t in tasks], [tid])

    def test_valor_desconhecido_de_estado_cai_no_padrao(self):
        tid = self._criar_tarefa()
        self.client.post(f"/api/tasks/{tid}/complete")
        # qualquer coisa != "concluidas" (incl. lixo) tem que se comportar
        # exatamente como sem o parametro nenhum - nunca inventa um 3o modo.
        for query in ["?estado=lixo", "?estado=", "?estado=CONCLUIDAS", "?estado=pendentes"]:
            with self.subTest(query=query):
                tasks = self.client.get(f"/api/tasks{query}").get_json()
                self.assertEqual(tasks, [])

    # ---- ?estado=concluidas ---------------------------------------------------

    def test_estado_concluidas_traz_a_concluida(self):
        tid = self._criar_tarefa("comprar cimento")
        self.client.post(f"/api/tasks/{tid}/complete")

        tasks = self.client.get("/api/tasks?estado=concluidas").get_json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], tid)
        self.assertEqual(tasks[0]["title"], "comprar cimento")
        self.assertIsNotNone(tasks[0]["completed_at"])

    def test_estado_concluidas_nao_traz_pendente(self):
        self._criar_tarefa("essa fica pendente")
        tasks = self.client.get("/api/tasks?estado=concluidas").get_json()
        self.assertEqual(tasks, [])

    def test_estado_concluidas_mesmo_formato_de_campos_da_lista_padrao(self):
        tid = self._criar_tarefa()
        tasks_pendente = self.client.get("/api/tasks").get_json()
        self.client.post(f"/api/tasks/{tid}/complete")
        tasks_concluida = self.client.get("/api/tasks?estado=concluidas").get_json()
        # mesmo conjunto de chaves (subtasks/empacada_dias/fichas_treino inclusos)
        # pra UI poder reusar o mesmo shape de resposta.
        self.assertEqual(set(tasks_pendente[0].keys()), set(tasks_concluida[0].keys()))

    def test_estado_concluidas_ordena_mais_recente_primeiro_e_limita_a_50(self):
        ids = [self._criar_tarefa(f"tarefa {i}") for i in range(55)]
        # completa todas com completed_at explicito e distinto (evita empate de
        # timestamp - datetime('now') e so precisao de segundo) pra ordem ficar
        # deterministica: id maior = completada por ultimo = mais recente.
        for i, tid in enumerate(ids):
            self.conn.execute(
                "UPDATE tasks SET completed_at = datetime('now', ?) WHERE id = ?",
                (f"+{i} seconds", tid),
            )
        self.conn.commit()

        tasks = self.client.get("/api/tasks?estado=concluidas").get_json()
        self.assertEqual(len(tasks), 50)
        # as 50 mais recentes = as ultimas 50 criadas (i=5..54), na ordem inversa
        esperado = [ids[i] for i in range(54, 4, -1)]
        self.assertEqual([t["id"] for t in tasks], esperado)

    # ---- nunca apaga -----------------------------------------------------------

    def test_completar_nunca_apaga_a_linha_do_banco(self):
        tid = self._criar_tarefa()
        self.client.post(f"/api/tasks/{tid}/complete")
        self.assertIsNotNone(self._linha_no_banco(tid))

    def test_reabrir_volta_pra_lista_padrao_sem_recriar_linha(self):
        tid = self._criar_tarefa("desmarcar essa")
        self.client.post(f"/api/tasks/{tid}/complete")
        self.assertEqual(self.client.get("/api/tasks?estado=concluidas").get_json()[0]["id"], tid)

        res = self.client.post(f"/api/tasks/{tid}/reabrir")
        self.assertEqual(res.status_code, 200)

        # mesmo id, mesma linha - so completed_at voltou a NULL.
        self.assertEqual(self.client.get("/api/tasks").get_json()[0]["id"], tid)
        self.assertEqual(self.client.get("/api/tasks?estado=concluidas").get_json(), [])
        linha = self._linha_no_banco(tid)
        self.assertIsNotNone(linha)
        self.assertIsNone(linha["completed_at"])

    def test_reabrir_tarefa_inexistente_continua_404(self):
        # regra do dono: nao inventa rota nova - a API ja permitia desmarcar
        # (par de /complete), so reusa; aqui so confirma que continua intacta.
        self.assertEqual(self.client.post("/api/tasks/999999/reabrir").status_code, 404)

    # ---- fuzzing leve do parametro novo -----------------------------------------

    def test_fuzzing_estado_nunca_da_500(self):
        casos = [
            "?estado=concluidas",
            "?estado=" + "x" * 5000,
            "?estado=' OR '1'='1",
            "?estado=concluidas&estado=lixo",
            "?estado=<script>alert(1)</script>",
            "?estado=None",
            "?estado=null",
        ]
        for query in casos:
            with self.subTest(query=query):
                res = self.client.get(f"/api/tasks{query}")
                self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
