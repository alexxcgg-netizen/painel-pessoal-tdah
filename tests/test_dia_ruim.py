"""Leva 22/10 (dia_ruim.py): cadeado (inegociavel), botao dia ruim e o alerta "dia que vai dar errado"."""
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.test_assistente_vida import _Base

import app
import cards
import conversa_proativa as cp
import db
import dia_ruim

HOJE = date.today()
AMANHA = (HOJE + timedelta(days=1)).isoformat()


class DiaRuimTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def _tarefa(self, titulo, hora=None, due=None, ineg=0):
        cur = self.conn.execute("INSERT INTO tasks (title, due_date, hora, inegociavel) VALUES (?, ?, ?, ?)",
                                (titulo, due or HOJE.isoformat(), hora, ineg))
        self.conn.commit()
        return cur.lastrowid

    def _due(self, tid):
        return self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (tid,)).fetchone()["due_date"]

    def test_aliviar_deixa_o_inegociavel_encurta_treino_e_empurra_o_resto(self):
        consulta = self._tarefa("Consulta", "15:00", ineg=1)
        treino = self._tarefa("Treino de perna", "18:00")
        estudo = self._tarefa("Estudar meteorologia", "20:00")
        garagem = self._tarefa("Arrumar a garagem", "10:00")
        atrasada = self._tarefa("Responder o grupo", due=(HOJE - timedelta(days=2)).isoformat())
        e = dia_ruim.aliviar(self.conn, HOJE)
        self.assertEqual([t["id"] for t in e["inegociavel"]], [consulta])
        self.assertEqual({t["id"] for t in e["reduzido"]}, {treino, estudo})
        self.assertEqual({t["curta"] for t in e["reduzido"]}, {"versão leve · 25 min", "versão curta · 20 min"})
        self.assertEqual({t["id"] for t in e["amanha"]}, {garagem, atrasada})
        self.assertEqual((self._due(consulta), self._due(garagem)), (HOJE.isoformat(), AMANHA))
        self.assertTrue(dia_ruim.ativo(self.conn, HOJE))
        self.assertEqual(dia_ruim.empurradas_na_semana(self.conn, HOJE), 2)
        # trazer de volta e empurrar de novo
        e = dia_ruim.trazer_de_volta(self.conn, garagem, HOJE)
        self.assertEqual([t["id"] for t in e["fica"]], [garagem])
        self.assertIsNone(dia_ruim.trazer_de_volta(self.conn, consulta, HOJE))
        e = dia_ruim.empurrar(self.conn, garagem, HOJE)
        self.assertIn(garagem, [t["id"] for t in e["amanha"]])
        self.assertIsNone(dia_ruim.empurrar(self.conn, consulta, HOJE))  # inegociavel nunca
        # desfazer volta tudo
        e = dia_ruim.desfazer(self.conn, HOJE)
        self.assertFalse(e["ativo"])
        self.assertEqual(self._due(garagem), HOJE.isoformat())
        self.assertEqual(e["reduzido"], [])

    def test_inegociavel_nao_vai_no_passar_pra_amanha_do_fechar_o_dia(self):
        ineg = self._tarefa("Pagar o boleto", ineg=1)
        normal = self._tarefa("Lavar o carro")
        r = cp.adiar_para_amanha(self.conn, [ineg, normal], HOJE)
        self.assertEqual(r["movidas"], 1)
        self.assertEqual((self._due(ineg), self._due(normal)), (HOJE.isoformat(), AMANHA))

    def test_aviso_de_5_min_so_pra_inegociavel(self):
        agora = datetime.combine(HOJE, datetime.min.time()).replace(hour=14, minute=56)
        ineg = self._tarefa("Consulta", "15:00", ineg=1)
        self._tarefa("Normal", "15:00")
        self.assertEqual([i for i, _ in dia_ruim.inegociaveis_chegando(self.conn, agora)], [ineg])
        self.assertEqual(dia_ruim.inegociaveis_chegando(self.conn, agora.replace(hour=14, minute=40)), [])

    def test_alerta_da_manha_com_dois_sinais(self):
        self._tarefa("Consulta", "15:00")
        manha = datetime.combine(HOJE, datetime.min.time()).replace(hour=7, minute=20)
        db.salvar_checkin(self.conn, HOJE.isoformat(), {"sono": 1})
        self.assertEqual(cp.alerta_do_dia(self.conn, manha), [])  # 1 sinal so
        dia_ruim.registrar_adiamento(self.conn, [1, 2, 3], HOJE.isoformat(), AMANHA)
        self.conn.commit()
        saida = cp.alerta_do_dia(self.conn, manha)
        self.assertEqual([s[0] for s in saida], ["alerta_dia"])
        card = [c for m in db.list_chat_mensagens(self.conn) for c in db.cards_de_mensagem_chat(m)][-1]
        self.assertEqual(card["type"], "alerta_dia")
        self.assertEqual({s["tipo"] for s in card["data"]["sinais"]}, {"sono", "empurradas"})
        self.assertEqual(cp.alerta_do_dia(self.conn, manha.replace(hour=8)), [])  # 1x por dia
        self.assertNotIn("sinais", cards.mascarar_cards([card])[0]["data"])
        self.assertEqual(cp.alerta_do_dia(self.conn, manha.replace(hour=21)), [])

    def test_rotas_dos_botoes(self):
        tid = self._tarefa("Arrumar a garagem")
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/inegociavel", json={"valor": "sim"}).status_code, 400)
        self.assertEqual(self.client.post("/api/tasks/99999/inegociavel", json={"valor": True}).status_code, 404)
        self.assertTrue(self.client.post(f"/api/tasks/{tid}/inegociavel", json={"valor": True}).get_json()["inegociavel"])
        self.client.post(f"/api/tasks/{tid}/inegociavel", json={"valor": False})
        r = self.client.post("/api/dia-ruim", json={}).get_json()
        self.assertEqual([t["id"] for t in r["amanha"]], [tid])
        tipos = [c["type"] for m in db.list_chat_mensagens(self.conn) for c in db.cards_de_mensagem_chat(m)]
        self.assertIn("dia_ruim", tipos)
        self.assertEqual(self.client.post("/api/dia-ruim/trazer", json={"id": tid}).get_json()["fica"][0]["id"], tid)
        self.assertEqual(self.client.post("/api/dia-ruim/trazer", json={"id": "x"}).status_code, 400)
        self.assertFalse(self.client.post("/api/dia-ruim/desfazer", json={}).get_json()["ativo"])
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            for url, corpo in (("/api/dia-ruim", {}), ("/api/dia-ruim/desfazer", {}), (f"/api/tasks/{tid}/inegociavel", {"valor": True})):
                self.assertEqual(self.client.post(url, json=corpo).status_code, 403, url)

    def test_chat_alivia_e_trava_pelas_ferramentas(self):
        self._tarefa("Pagar o boleto")
        self._tarefa("Arrumar a garagem")
        corpo, res = self.chat([("travar_tarefa", {"titulo": "boleto"}), ("dia_ruim", {})])
        self.assertTrue(res[0]["inegociavel"])
        self.assertEqual(res[1]["inegociavel"], ["Pagar o boleto"])
        self.assertEqual(res[1]["amanha"], ["Arrumar a garagem"])
        self.assertIn("dia_ruim", [c["type"] for c in corpo["cards"]])
        # nesse dia o contexto pede resposta curta e calma
        visto = []
        self.chat([], contexto_visto=visto)
        self.assertIn("DIA RUIM", visto[0])

    def test_mover_tarefas_nao_leva_a_travada(self):
        self._tarefa("Pagar o boleto", ineg=1)
        livre = self._tarefa("Arrumar a garagem")
        _, res = self.chat([("mover_tarefas", {"para_data": AMANHA})])
        self.assertEqual(res[0]["ficaram_travadas"], ["Pagar o boleto"])
        self.assertEqual(self._due(livre), AMANHA)


if __name__ == "__main__":
    unittest.main()
