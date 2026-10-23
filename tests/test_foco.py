"""Leva 22/10 (foco.py): Parceiro de foco - relogio que espera no meio, travei encolhe o passo, terminei conclui."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import app
import db
import foco


class FocoTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()
        self.t0 = datetime(2026, 10, 22, 14, 0, 0)

    def tearDown(self):
        self.conn.close()

    def _abrir(self, minutos=10):
        tid = self.conn.execute("INSERT INTO tasks (title) VALUES ('Organizar as fotos')").lastrowid
        self.conn.commit()
        e = foco.abrir(self.conn, self.t0, "Organizar as fotos", "Abre a galeria e apaga só os prints.",
                       "Só apaga 5 fotos.", minutos, tid)
        return tid, e

    def test_relogio_espera_no_meio_e_avisa_uma_vez(self):
        _, e = self._abrir()
        self.assertEqual((e["fase"], e["total_s"]), ("pronto", 600))
        self.assertFalse(foco.segurando_avisos(self.conn, self.t0))
        foco.comecar(self.conn, self.t0, e["id"])
        self.assertTrue(foco.segurando_avisos(self.conn, self.t0 + timedelta(minutes=1)))
        e = foco.estado(self.conn, self.t0 + timedelta(minutes=8))
        self.assertEqual((e["fase"], e["decorrido_s"]), ("meio", 300))  # parou na metade, esperando
        self.assertFalse(foco.segurando_avisos(self.conn, self.t0 + timedelta(minutes=8)))
        self.assertEqual([a[0] for a in foco.aviso_do_meio(self.conn, self.t0 + timedelta(minutes=8))], ["foco_meio"])
        self.assertEqual(foco.aviso_do_meio(self.conn, self.t0 + timedelta(minutes=9)), [])  # nunca insiste
        agora = self.t0 + timedelta(minutes=9)
        e = foco.responder(self.conn, agora, "ainda", e["id"])
        self.assertEqual((e["fase"], e["decorrido_s"]), ("rodando", 300))
        e = foco.estado(self.conn, agora + timedelta(minutes=6))
        self.assertEqual(e["fase"], "acabou")  # tempo cumprido nao marca a tarefa sozinho
        e = foco.responder(self.conn, agora + timedelta(minutes=6), "mais", e["id"])
        self.assertEqual((e["fase"], e["total_s"]), ("rodando", 900))

    def test_travei_encolhe_o_passo_e_terminei_conclui_com_o_tempo(self):
        tid, e = self._abrir()
        foco.comecar(self.conn, self.t0, e["id"])
        e = foco.responder(self.conn, self.t0 + timedelta(minutes=5), "travei", e["id"])
        self.assertEqual((e["fase"], e["passo"], e["travei"]), ("pausado", "Só apaga 5 fotos.", True))
        foco.comecar(self.conn, self.t0 + timedelta(minutes=7), e["id"])
        e = foco.responder(self.conn, self.t0 + timedelta(minutes=9), "fim", e["id"])
        self.assertEqual((e["fase"], e["levou_s"]), ("feito", 420))
        t = self.conn.execute("SELECT completed_at, extras FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertIsNotNone(t["completed_at"])
        self.assertIn('"foco_s": 420', t["extras"])
        self.assertIsNone(foco.comecar(self.conn, self.t0, e["id"]))  # fechou

    def test_chat_abre_a_sessao_e_rotas(self):
        corpo, res = self.chat([("parceiro_foco", {"titulo": "organizar as fotos do celular",
                                                   "primeiro_passo": "Abre a galeria.", "minutos": 7})])
        self.assertTrue(res[0]["tarefa_nova"])
        self.assertEqual(res[0]["minutos"], 10)  # 7 nao vale: volta pro padrao
        card = [c for c in corpo["cards"] if c["type"] == "foco"][0]
        sid = card["data"]["id"]
        self.assertEqual(card["data"]["passo"], "Abre a galeria.")
        self.assertEqual(self.client.post("/api/foco/comecar", json={"id": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/foco/comecar", json={"id": sid + 1}).status_code, 409)
        self.assertEqual(self.client.post("/api/foco/comecar", json={"id": sid}).get_json()["sessao"]["fase"], "rodando")
        self.assertEqual(self.client.post("/api/foco/responder", json={"id": sid, "r": "talvez"}).status_code, 400)
        self.assertEqual(self.client.post("/api/foco/responder", json={"id": sid, "r": "fim"}).get_json()["sessao"]["fase"], "feito")
        self.assertEqual(self.client.get("/api/foco").get_json()["sessao"]["fase"], "feito")
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertIsNone(self.client.get("/api/foco").get_json()["sessao"])
            self.assertEqual(self.client.post("/api/foco/pausar", json={"id": sid}).status_code, 403)

    def test_empurrada_3_vezes_vira_dica_no_contexto(self):
        import dia_ruim

        tid, _ = self._abrir()
        for _ in range(3):
            dia_ruim.registrar_adiamento(self.conn, [tid], "2026-10-20", "2026-10-21")
        self.conn.commit()
        visto = []
        self.chat([], contexto_visto=visto)
        self.assertIn("Empurradas 3+ vezes: Organizar as fotos", visto[0])

    def test_relogio_correndo_segura_aviso_comum(self):
        _, e = self._abrir()
        foco.comecar(self.conn, datetime.now(), e["id"])
        self.assertTrue(foco.segurando_avisos(self.conn, datetime.now()))


if __name__ == "__main__":
    unittest.main()
