"""Leva 22/10 (de_onde_parei.py): ao voltar pro app depois de 2 h, card com a tarefa pela metade."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import app
import db
import de_onde_parei as dp

HOJE = date.today().isoformat()


class DeOndePareiTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()
        self.agora = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    def tearDown(self):
        self.conn.close()

    def _tarefa(self, titulo, passos, feitos):
        tid = self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", (titulo, HOJE)).lastrowid
        quando = (self.agora - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        ids = []
        for i, p in enumerate(passos):
            ids.append(self.conn.execute(
                "INSERT INTO subtasks (task_id, title, position, completed_at) VALUES (?, ?, ?, ?)",
                (tid, p, i, quando if i < feitos else None)).lastrowid)
        self.conn.commit()
        return tid, ids

    def _cards(self):
        return [c for m in db.list_chat_mensagens(self.conn) for c in db.cards_de_mensagem_chat(m)]

    def test_so_aparece_depois_de_2h_parado_e_uma_vez_por_tarefa(self):
        tid, _ = self._tarefa("Revisar meteorologia", ["Ler", "Questões 1-7", "Questões 8-13"], 2)
        self._tarefa("Sem começar", ["A", "B"], 0)
        self._tarefa("Já fechada nos passos", ["A"], 1)
        self.assertFalse(dp.ao_ver(self.conn, self.agora, HOJE))  # primeira vez: so guarda
        self.assertFalse(dp.ao_ver(self.conn, self.agora + timedelta(minutes=30), HOJE))
        volta = self.agora + timedelta(hours=3)
        self.assertTrue(dp.ao_ver(self.conn, volta, HOJE))
        card = self._cards()[-1]
        self.assertEqual(card["type"], "de_onde_parei")
        self.assertEqual(card["data"]["task_id"], tid)
        self.assertEqual([p["feito"] for p in card["data"]["passos"]], [True, True, False])
        self.assertEqual(card["data"]["parado_h"], 6)
        # mesmo dia, outra volta: nao repete a mesma tarefa
        self.assertFalse(dp.ao_ver(self.conn, volta + timedelta(hours=3), HOJE))

    def test_passo_velho_nao_conta_e_deixar_pra_la_segura_o_dia(self):
        tid, _ = self._tarefa("Arrumar a mala", ["A", "B"], 1)
        self.conn.execute("UPDATE subtasks SET completed_at = '2000-01-01 10:00:00' WHERE completed_at IS NOT NULL")
        self.conn.commit()
        self.assertIsNone(dp.tarefa_pela_metade(self.conn, self.agora))
        self.conn.execute("UPDATE subtasks SET completed_at = ? WHERE completed_at IS NOT NULL",
                          (self.agora.strftime("%Y-%m-%d %H:%M:%S"),))
        self.conn.commit()
        dp.deixar(self.conn, tid, HOJE)
        dp.ao_ver(self.conn, self.agora, HOJE)
        self.assertFalse(dp.ao_ver(self.conn, self.agora + timedelta(hours=3), HOJE))
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.assertTrue(dp.ao_ver(self.conn, self.agora + timedelta(hours=6), amanha))

    def test_rotas(self):
        tid, ids = self._tarefa("Revisar", ["A", "B"], 1)
        r = self.client.post(f"/api/subtasks/{ids[1]}/marcar", json={"feito": True}).get_json()
        self.assertEqual((r["feitos"], r["total"]), (2, 2))
        r = self.client.post(f"/api/subtasks/{ids[1]}/marcar", json={"feito": False}).get_json()
        self.assertEqual(r["feitos"], 1)
        self.assertEqual(self.client.post(f"/api/subtasks/{ids[1]}/marcar", json={"feito": "sim"}).status_code, 400)
        self.assertEqual(self.client.post("/api/subtasks/99999/marcar", json={"feito": True}).status_code, 404)
        self.assertEqual(self.client.post("/api/de-onde-parei/deixar", json={"task_id": "x"}).status_code, 400)
        self.assertTrue(self.client.post("/api/de-onde-parei/deixar", json={"task_id": tid}).get_json()["ok"])
        # o batimento do app devolve a flag (aqui a tarefa foi deixada: nada a mostrar)
        self.assertFalse(self.client.post("/api/push/visto").get_json()["de_onde_parei"])
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self.client.post(f"/api/subtasks/{ids[0]}/marcar", json={"feito": True}).status_code, 403)
            self.assertEqual(self.client.post("/api/de-onde-parei/deixar", json={"task_id": tid}).status_code, 403)
            self.assertFalse(self.client.post("/api/push/visto").get_json()["de_onde_parei"])

    def test_visto_publica_quando_volta(self):
        self._tarefa("Revisar", ["A", "B"], 1)
        db.definir_configuracao(self.conn, dp.CONFIG_VISTO, (self.agora - timedelta(hours=4)).isoformat())
        self.assertTrue(self.client.post("/api/push/visto").get_json()["de_onde_parei"])
        self.assertEqual(self._cards()[-1]["type"], "de_onde_parei")


if __name__ == "__main__":
    unittest.main()
