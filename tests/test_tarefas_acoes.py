"""Aba Tarefas nova (leva 06/11, frente 6): rotas da folha de acoes e da regua do dia
(rotas/tarefas_acoes.py) - mover dia/hora e renomear, sempre com o token do Desfazer de sempre."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN = "246810"


class TarefasAcoesTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        self.hoje = app._agora_brasilia().date()

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall() if query.lstrip().upper().startswith("SELECT") else cur.lastrowid
        finally:
            conn.close()

    def criar(self, titulo="Ligar pro contador", due_date=None, hora=None, **extra):
        cols = {"title": titulo, "due_date": due_date, "hora": hora, **extra}
        return self.sql(
            f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values())
        )

    def linha(self, task_id):
        return self.sql("SELECT * FROM tasks WHERE id = ?", (task_id,))[0]

    def mover(self, task_id, corpo):
        return self.client.post(f"/api/tasks/{task_id}/mover", json=corpo)

    # ---------------------------------------------------------------- mover
    def test_muda_so_a_hora_e_o_desfazer_volta(self):
        tid = self.criar(due_date=self.hoje.isoformat(), hora="16:30")
        r = self.mover(tid, {"hora": "9:15"})
        self.assertEqual(r.status_code, 200)
        dados = r.get_json()
        self.assertTrue(dados["ok"])
        self.assertTrue(dados["mudou"])
        self.assertEqual(dados["tarefa"]["hora"], "09:15")
        self.assertEqual(dados["tarefa"]["due_date"], self.hoje.isoformat())
        self.assertTrue(dados["token"])
        self.assertEqual(self.linha(tid)["hora"], "09:15")
        d = self.client.post(f"/api/desfazer/{dados['token']}")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(self.linha(tid)["hora"], "16:30")

    def test_muda_o_dia_mantem_a_hora(self):
        amanha = (self.hoje + timedelta(days=1)).isoformat()
        tid = self.criar(due_date=self.hoje.isoformat(), hora="10:00")
        dados = self.mover(tid, {"data": amanha}).get_json()
        self.assertEqual(dados["tarefa"]["due_date"], amanha)
        self.assertEqual(dados["tarefa"]["hora"], "10:00")
        # empurrou uma de hoje pra frente: conta como adiamento
        adiadas = self.sql("SELECT de, para FROM tarefas_adiadas WHERE task_id = ?", (tid,))
        self.assertEqual([(a["de"], a["para"]) for a in adiadas], [(self.hoje.isoformat(), amanha)])
        self.client.post(f"/api/desfazer/{dados['token']}")
        self.assertEqual(self.linha(tid)["due_date"], self.hoje.isoformat())

    def test_dia_e_hora_juntos_e_tirar_a_hora(self):
        dia = (self.hoje + timedelta(days=3)).isoformat()
        tid = self.criar(due_date=self.hoje.isoformat(), hora="08:00")
        dados = self.mover(tid, {"data": dia, "hora": "21:00"}).get_json()
        self.assertEqual((dados["tarefa"]["due_date"], dados["tarefa"]["hora"]), (dia, "21:00"))
        dados = self.mover(tid, {"hora": None}).get_json()
        self.assertIsNone(dados["tarefa"]["hora"])
        self.assertTrue(dados["token"])
        self.client.post(f"/api/desfazer/{dados['token']}")
        self.assertEqual(self.linha(tid)["hora"], "21:00")

    def test_trazer_atrasada_pra_hoje_nao_conta_adiamento(self):
        ontem = (self.hoje - timedelta(days=1)).isoformat()
        tid = self.criar(due_date=ontem)
        dados = self.mover(tid, {"data": self.hoje.isoformat()}).get_json()
        self.assertEqual(dados["tarefa"]["due_date"], self.hoje.isoformat())
        self.assertEqual(self.sql("SELECT * FROM tarefas_adiadas"), [])

    def test_hora_em_tarefa_sem_dia_poe_hoje(self):
        tid = self.criar(due_date=None)
        dados = self.mover(tid, {"hora": "15:00"}).get_json()
        self.assertEqual(dados["tarefa"]["due_date"], self.hoje.isoformat())
        self.assertEqual(dados["tarefa"]["hora"], "15:00")
        # o Desfazer volta as duas colunas
        self.client.post(f"/api/desfazer/{dados['token']}")
        self.assertIsNone(self.linha(tid)["due_date"])
        self.assertIsNone(self.linha(tid)["hora"])

    def test_nada_mudou_devolve_sem_token(self):
        tid = self.criar(due_date=self.hoje.isoformat(), hora="10:00")
        dados = self.mover(tid, {"hora": "10:00"}).get_json()
        self.assertTrue(dados["ok"])
        self.assertFalse(dados["mudou"])
        self.assertIsNone(dados["token"])

    def test_tarefa_feita_nao_muda(self):
        tid = self.criar(due_date=self.hoje.isoformat(), hora="10:00", completed_at="2026-11-06 09:00:00")
        r = self.mover(tid, {"hora": "11:00"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.linha(tid)["hora"], "10:00")

    def test_entrada_invalida(self):
        tid = self.criar(due_date=self.hoje.isoformat(), hora="10:00")
        casos = [
            {},
            {"data": "amanha"},
            {"data": "2026-02-30"},
            {"data": None},
            {"data": 20261107},
            {"hora": "25:00"},
            {"hora": "10h"},
            {"hora": 10},
            {"hora": ["10:00"]},
            {"data": "2026-11-07'; DROP TABLE tasks; --"},
        ]
        for corpo in casos:
            with self.subTest(corpo=corpo):
                self.assertEqual(self.mover(tid, corpo).status_code, 400)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/mover", json=["hora"]).status_code, 400)
        self.assertEqual(self.linha(tid)["hora"], "10:00")

    def test_tarefa_que_nao_existe_e_modelo_de_rotina(self):
        self.assertEqual(self.mover(999, {"hora": "10:00"}).status_code, 404)
        modelo = self.criar("Academia", due_date=None, hora="07:00", recorrencia="diaria")
        self.assertEqual(self.mover(modelo, {"hora": "08:00"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/tasks/{modelo}/titulo", json={"titulo": "x"}).status_code, 404)

    def test_dia_de_rotina_que_sai_do_dia_nao_volta_sozinho(self):
        modelo = self.criar("Academia", due_date=None, hora="07:00", recorrencia="diaria")
        # GET /api/tasks materializa a de hoje; usa a data do servidor (date.today) igual a rota
        hoje_srv = date.today().isoformat()
        self.client.get("/api/tasks")
        inst = self.sql("SELECT id FROM tasks WHERE recorrente_origem_id = ? AND due_date = ?", (modelo, hoje_srv))
        self.assertEqual(len(inst), 1)
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.mover(inst[0]["id"], {"data": amanha}).status_code, 200)
        self.client.get("/api/tasks")
        de_hoje = self.sql("SELECT id FROM tasks WHERE recorrente_origem_id = ? AND due_date = ?", (modelo, hoje_srv))
        self.assertEqual(de_hoje, [], "a rotina de hoje foi recriada depois de mover pra amanha")

    # ------------------------------------------------- plano de saida refeito
    # mudar hora/dia de date, balada ou tarefa com lugar pela aba (regua, folha, /mover e o /hora
    # antigo) refaz a saida pela MESMA funcao do chat (app.replanejar_saida)
    def _arrumar_min(self):
        conn = db.get_db()
        try:
            return app.vida_assistente.se_arrumar_min(conn)
        finally:
            conn.close()

    def test_mover_date_refaz_a_saida_sem_trajeto(self):
        tid = self.criar("Date com a Ana", due_date=self.hoje.isoformat(), hora="20:00", estilo="date")
        with mock.patch.object(app, "_saida_pro_compromisso", return_value=None) as rota:
            dados = self.mover(tid, {"hora": "21:00"}).get_json()
        rota.assert_called_once_with(self.hoje.isoformat(), "21:00", None)
        plano = dados["plano"]
        self.assertEqual(plano["sair_de_casa"], "20:45")  # 15 min de folga sem trajeto
        self.assertEqual(plano["comecar_a_se_arrumar"], app.rota_voo.menos_minutos("20:45", self._arrumar_min()))

    def test_mover_dia_de_tarefa_com_lugar_usa_o_trajeto(self):
        amanha = (self.hoje + timedelta(days=1)).isoformat()
        tid = self.criar("Dentista", due_date=self.hoje.isoformat(), hora="14:00", local="Rua Exemplo, 100")
        saida = {"sair": "13:20", "trajeto_min": 30}
        with mock.patch.object(app, "_saida_pro_compromisso", return_value=saida) as rota:
            dados = self.mover(tid, {"data": amanha}).get_json()
        rota.assert_called_once_with(amanha, "14:00", "Rua Exemplo, 100")
        self.assertEqual(dados["plano"]["sair_de_casa"], "13:20")
        self.assertEqual(dados["plano"]["ida_min"], 30)

    def test_mover_balada_com_parada_regrava_a_parada(self):
        tid = self.criar("Balada", due_date=self.hoje.isoformat(), hora="23:00", estilo="balada",
                         parada="Posto Exemplo", local="Clube Exemplo")
        info = {"nome": "Posto Exemplo", "chegar": "22:10"}
        with mock.patch.object(app, "_saida_com_parada", return_value=({"sair": "21:55"}, info)) as rota:
            dados = self.mover(tid, {"hora": "23:30"}).get_json()
        rota.assert_called_once()
        self.assertEqual(rota.call_args.args[1:], (self.hoje.isoformat(), "23:30", "Posto Exemplo", "Clube Exemplo"))
        self.assertEqual(dados["plano"]["sair_de_casa"], "21:55")
        self.assertEqual(dados["parada"], info)
        conn = db.get_db()
        try:
            self.assertEqual(db.extras_tarefa(conn, tid)["parada"], info)  # o card le daqui
        finally:
            conn.close()

    def test_tarefa_comum_nao_ganha_plano(self):
        tid = self.criar("Ligar pro contador", due_date=self.hoje.isoformat(), hora="10:00")
        with mock.patch.object(app, "_saida_pro_compromisso") as rota:
            dados = self.mover(tid, {"hora": "11:00"}).get_json()
        rota.assert_not_called()
        self.assertNotIn("plano", dados)

    def test_tirar_a_hora_do_date_nao_planeja(self):
        tid = self.criar("Date", due_date=self.hoje.isoformat(), hora="20:00", estilo="date")
        with mock.patch.object(app, "_saida_pro_compromisso") as rota:
            dados = self.mover(tid, {"hora": None}).get_json()
        rota.assert_not_called()
        self.assertNotIn("plano", dados)

    def test_maps_quebrado_nao_derruba_o_mover(self):
        tid = self.criar("Date", due_date=self.hoje.isoformat(), hora="20:00", estilo="date")
        with mock.patch.object(app, "_saida_pro_compromisso", side_effect=RuntimeError("sem rede")):
            r = self.mover(tid, {"hora": "21:00"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("plano", r.get_json())
        self.assertEqual(self.linha(tid)["hora"], "21:00")
        self.assertTrue(r.get_json()["token"])

    def test_hora_antiga_do_card_tambem_refaz_a_saida(self):
        tid = self.criar("Balada", due_date=self.hoje.isoformat(), hora="23:00", estilo="balada")
        with mock.patch.object(app, "_saida_pro_compromisso", return_value=None):
            dados = self.client.post(f"/api/tasks/{tid}/hora", json={"hora": "22:30"}).get_json()
        self.assertEqual(dados["hora"], "22:30")
        self.assertEqual(dados["plano"]["sair_de_casa"], "22:15")
        comum = self.criar("Comum", due_date=self.hoje.isoformat(), hora="10:00")
        dados = self.client.post(f"/api/tasks/{comum}/hora", json={"hora": "10:30"}).get_json()
        self.assertEqual(dados, {"ok": True, "hora": "10:30"})

    # --------------------------------------------------------------- titulo
    def test_renomear_e_desfazer(self):
        tid = self.criar("Ligar pro contador", due_date=self.hoje.isoformat())
        r = self.client.post(f"/api/tasks/{tid}/titulo", json={"titulo": "  Ligar pro contador\n sobre o IR  "})
        self.assertEqual(r.status_code, 200)
        dados = r.get_json()
        self.assertEqual(dados["tarefa"]["title"], "Ligar pro contador sobre o IR")
        self.assertTrue(dados["token"])
        self.client.post(f"/api/desfazer/{dados['token']}")
        self.assertEqual(self.linha(tid)["title"], "Ligar pro contador")

    def test_renomear_tarefa_feita_pode(self):
        tid = self.criar("Velho", completed_at="2026-11-06 09:00:00")
        dados = self.client.post(f"/api/tasks/{tid}/titulo", json={"titulo": "Novo"}).get_json()
        self.assertEqual(dados["tarefa"]["title"], "Novo")

    def test_titulo_invalido(self):
        tid = self.criar("Velho")
        for corpo in ({}, {"titulo": ""}, {"titulo": "   \n "}, {"titulo": None}, {"titulo": 5},
                      {"titulo": "x" * 201}):
            with self.subTest(corpo=str(corpo)[:40]):
                self.assertEqual(self.client.post(f"/api/tasks/{tid}/titulo", json=corpo).status_code, 400)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/titulo", json={"titulo": "x" * 200}).status_code, 200)
        self.assertEqual(self.client.post("/api/tasks/999/titulo", json={"titulo": "x"}).status_code, 404)

    def test_titulo_com_html_volta_igual_texto(self):
        tid = self.criar("Velho")
        dados = self.client.post(f"/api/tasks/{tid}/titulo", json={"titulo": "<img src=x onerror=alert(1)>"}).get_json()
        # guardado como texto; quem desenha usa textContent
        self.assertEqual(dados["tarefa"]["title"], "<img src=x onerror=alert(1)>")

    # ---------------------------------------------------------------- acesso
    def test_sem_login_nao_entra(self):
        tid = self.criar("Velho", due_date=self.hoje.isoformat())
        anonimo = app.app.test_client()
        r1 = anonimo.post(f"/api/tasks/{tid}/mover", json={"hora": "10:00"})
        r2 = anonimo.post(f"/api/tasks/{tid}/titulo", json={"titulo": "x"})
        self.assertIn(r1.status_code, (302, 401))
        self.assertIn(r2.status_code, (302, 401))
        self.assertEqual(self.linha(tid)["title"], "Velho")
        self.assertIsNone(self.linha(tid)["hora"])


if __name__ == "__main__":
    unittest.main()
