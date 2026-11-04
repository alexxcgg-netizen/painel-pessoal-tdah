"""Card tarefa_feita (2026-10-14, docs/CARDS.md "Linguagem visual dos cards").

Concluir pelo chat - registrar_feito ("ja fui no tricologista") ou ajustar_tarefa com
status=concluir - vira o card com o anel do dia e a proxima de hoje; o Desfazer reabre a
tarefa que ja existia ou apaga a que nasceu concluida. Mesmo esquema do test_voo_agendado."""
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402

PIN = "246810"
HOJE = date.today().isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        app._CACHE_CONSTRUTORA.clear()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def chat(self, chamadas):
        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                executores[tool](entrada)
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "ja fiz"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    def desfazer(self, card):
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)


class TarefaFeitaTestCase(_Base):
    def test_registrar_feito_marca_a_pendente_e_desfazer_reabre(self):
        self.sql("INSERT INTO tasks (title, due_date, completed_at) VALUES ('Academia', ?, datetime('now'))", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Consulta com tricologista', ?, '10:00')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Concreteira', ?, '23:59')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Racao', ?)", (HOJE,))
        corpo = self.chat([("registrar_feito", {"titulo": "consulta com tricologista"})])
        self.assertEqual([c["type"] for c in corpo["cards"]], ["tarefa_feita"])
        d = corpo["cards"][0]["data"]
        self.assertEqual((d["titulo"], d["feitas"], d["total"], d["faltam"], d["data"]),
                         ("Consulta com tricologista", 2, 4, 2, HOJE))
        self.assertEqual(d["proxima"]["titulo"], "Concreteira")  # 23:59 ainda nao passou

        self.desfazer(corpo["cards"][0])
        self.assertIsNone(self.sql("SELECT completed_at FROM tasks WHERE title LIKE 'Consulta%'")[0][0])

    def test_registrar_feito_sem_parecida_cria_concluida_e_desfazer_apaga(self):
        corpo = self.chat([("registrar_feito", {"titulo": "fui na academia"})])
        card = corpo["cards"][0]
        self.assertEqual(card["type"], "tarefa_feita")
        self.assertEqual((card["data"]["feitas"], card["data"]["total"], card["data"]["proxima"]), (1, 1, None))
        self.desfazer(card)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 0)

    def test_ajustar_tarefa_concluir_vira_tarefa_feita_mas_editar_hora_continua_edicao(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Visitar obra', ?)", (HOJE,))
        corpo = self.chat([("ajustar_tarefa", {"titulo": "visitar obra", "status": "concluir"})])
        self.assertEqual([c["type"] for c in corpo["cards"]], ["tarefa_feita"])
        self.desfazer(corpo["cards"][0])
        self.assertIsNone(self.sql("SELECT completed_at FROM tasks")[0][0])

        corpo = self.chat([("ajustar_tarefa", {"titulo": "visitar obra", "hora": "15:00"})])
        self.assertEqual([c["type"] for c in corpo["cards"]], ["edicao"])

    def test_hora_em_tarefa_sem_dia_poe_ela_em_hoje(self):
        # 03/11: "imprimir as contas" ganhou 11h e ficou sem data - nao aparecia no dia nem chamava na hora
        import app as app_mod

        self.sql("INSERT INTO tasks (title) VALUES ('Imprimir as contas')")
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Ligar pro banco', '2026-12-01')")
        self.chat([("ajustar_tarefa", {"titulo": "imprimir as contas", "hora": "11:00"})])
        self.chat([("ajustar_tarefa", {"titulo": "ligar pro banco", "hora": "09:00"})])
        linhas = {r[0]: (r[1], r[2]) for r in self.sql("SELECT title, due_date, hora FROM tasks")}
        self.assertEqual(linhas["Imprimir as contas"], (app_mod._agora_brasilia().date().isoformat(), "11:00"))
        self.assertEqual(linhas["Ligar pro banco"], ("2026-12-01", "09:00"))  # dia que ja tinha fica

    def test_tarefa_atrasada_conta_no_anel_de_hoje(self):
        conn = db.get_db()
        try:
            tid = conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Atrasada', '2026-01-02')").lastrowid
            conn.execute("INSERT INTO tasks (title, due_date) VALUES ('De hoje', ?)", (HOJE,))
            db.complete_task(conn, tid)
            d = cards.card_tarefa_feita(conn, tid, agora=datetime.now())["data"]
        finally:
            conn.close()
        self.assertEqual((d["feitas"], d["total"]), (1, 2))
        self.assertEqual(d["proxima"]["titulo"], "De hoje")

    def test_proxima_que_ja_passou_da_lugar_a_sem_hora(self):
        conn = db.get_db()
        try:
            tid = conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Feita', ?)", (HOJE,)).lastrowid
            conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Cedo', ?, '07:00')", (HOJE,))
            conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Sem hora', ?)", (HOJE,))
            db.complete_task(conn, tid)
            agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
            d = cards.card_tarefa_feita(conn, tid, agora=agora)["data"]
        finally:
            conn.close()
        self.assertEqual(d["proxima"], {"titulo": "Sem hora", "hora": None})


class TarefaComApertoTestCase(_Base):
    """Tarefa nova a menos de 45 min de outra pendente do dia (card tarefas_criadas + aperto)."""

    def criar(self, hora, titulo="Tricologista"):
        def fake(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": titulo, "quando_data": HOJE, "hora": hora})
            return "Feito.", ["registrar_tarefa"], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "tricologista"})
        card = next(c for c in res.get_json()["cards"] if c["type"] == "tarefas_criadas")
        return card["data"].get("aperto")

    def test_outra_antes_sugere_uma_hora_antes_da_nova(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Mikael', ?, '09:00')", (HOJE,))
        ap = self.criar("09:30")
        self.assertEqual((ap["titulo"], ap["hora"], ap["sugestao"]), ("Mikael", "09:00", "08:30"))

    def test_outra_depois_sugere_uma_hora_depois(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Mikael', ?, '10:00')", (HOJE,))
        self.assertEqual(self.criar("09:30")["sugestao"], "10:30")

    def test_longe_concluida_ou_sem_hora_nao_aperta(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Longe', ?, '11:00')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('Feita', ?, '09:15', datetime('now'))", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('Sem hora', ?)", (HOJE,))
        self.assertIsNone(self.criar("09:30"))

    def test_sugestao_que_apertaria_uma_terceira_nao_sai(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Mikael', ?, '09:00')", (HOJE,))
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Cafe', ?, '08:20')", (HOJE,))
        ap = self.criar("09:30")
        self.assertEqual(ap["titulo"], "Mikael")
        self.assertIsNone(ap["sugestao"])

    def test_rota_de_hora_move_a_outra(self):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Mikael', ?, '09:00')", (HOJE,))
        ap = self.criar("09:30")
        res = self.client.post(f"/api/tasks/{ap['id']}/hora", json={"hora": "8:30"})
        self.assertEqual(res.get_json(), {"ok": True, "hora": "08:30"})
        self.assertEqual(self.sql("SELECT hora FROM tasks WHERE title = 'Mikael'")[0][0], "08:30")
        self.assertEqual(self.client.post(f"/api/tasks/{ap['id']}/hora", json={"hora": "25:00"}).status_code, 400)
        self.assertEqual(self.client.post("/api/tasks/9999/hora", json={"hora": "08:00"}).status_code, 404)
        self.assertEqual(self.client.post("/api/modo-visitante", json={"ativar": True}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/tasks/{ap['id']}/hora", json={"hora": "07:00"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
