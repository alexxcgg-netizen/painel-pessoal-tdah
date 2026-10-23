"""Leva 22/10 (diario_bordo.py): Diario de bordo - 3 perguntas depois do voo e quanto falta pra comercial
pelos minimos do RBAC 61.101 (150 total, 20 navegacao, 10 instrumentos com ate 5 de simulador, 5 noturno)."""
import unittest
from datetime import date

from tests.test_assistente_vida import _Base

import db
import diario_bordo

HOJE = date(2026, 10, 22)


class DiarioBordoTestCase(_Base):
    def voo(self, data, origem="SSBL", destino="SSBL", horas=None, **extra):
        cols = ["data", "origem", "destino", "horas", *extra]
        cur = self.sql_id(f"INSERT INTO voos ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          (data, origem, destino, horas, *extra.values()))
        return cur

    def sql_id(self, query, params=()):
        conn = db.get_db()
        try:
            id_ = conn.execute(query, params).lastrowid
            conn.commit()
            return id_
        finally:
            conn.close()

    def test_progresso_soma_por_categoria_e_aponta_a_mais_atrasada(self):
        self.voo("2026-10-01", "SSBL", "SBFL", 2.0)  # antigo da CIV, sem resposta: navegacao pela rota
        self.voo("2026-10-05", horas=1.0, natureza="tgl", toques=6)
        self.voo("2026-10-08", horas=1.5, natureza="instrumentos", noturno=1)
        self.voo("2026-10-09", horas=7.0, tipo="simulador")  # so 5 h entram, e so em instrumentos
        self.voo("2026-11-01", "SSBL", "SBFL", 3.0)  # futuro nao conta
        conn = db.get_db()
        try:
            p = diario_bordo.progresso(conn, HOJE)
        finally:
            conn.close()
        cats = {c["chave"]: (c["h"], c["meta"]) for c in p["cats"]}
        self.assertEqual(cats, {"total": (4.5, 150), "navegacao": (2.0, 20), "noturno": (1.5, 5), "instrumentos": (6.5, 10)})
        self.assertEqual(p["pior"], "navegacao")
        self.assertEqual(p["toques_curso"], 6)

    def test_rota_registra_desfaz_e_valida(self):
        vid = self.voo(HOJE.isoformat())
        r = self.client.post(f"/api/voos/{vid}/diario", json={"horas": 1.3, "natureza": "tgl", "noturno": True, "toques": 5})
        d = r.get_json()["card"]
        self.assertTrue(d["registrado"])
        self.assertEqual((d["horas"], d["natureza"], d["noturno"], d["toques"]), (1.3, "tgl", True, 5))
        self.assertEqual({c["chave"]: c["h"] for c in d["cats"]}["noturno"], 1.3)
        self.assertEqual(d["toques_curso"], 5)
        # desfazer: volta como estava (sem horas, sem resposta)
        d2 = self.client.post(f"/api/voos/{vid}/diario", json={"horas": None, "natureza": None}).get_json()["card"]
        self.assertFalse(d2["registrado"])
        self.assertEqual(tuple(self.sql("SELECT horas, natureza, toques FROM voos WHERE id = ?", (vid,))[0]), (None, None, None))
        ruins = [{"horas": 1, "natureza": "pista"}, {"horas": 30, "natureza": "navegacao"},
                 {"horas": 1, "natureza": "tgl", "toques": 0}, {"horas": True, "natureza": "navegacao"}]
        for corpo in ruins:
            self.assertEqual(self.client.post(f"/api/voos/{vid}/diario", json=corpo).status_code, 400, corpo)
        self.assertEqual(self.client.post("/api/voos/9999/diario", json={"horas": 1, "natureza": "navegacao"}).status_code, 404)

    def test_chat_acabei_de_voar_abre_o_card_e_registra_o_que_ele_disse(self):
        corpo, res = self.chat([("diario_de_bordo", {})])
        self.assertTrue(res[0]["voo_novo"])  # nao tinha voo marcado: entra o local de hoje
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("diario_bordo", tipos)
        corpo, res = self.chat([("diario_de_bordo", {"natureza": "navegacao", "horas": 1.3})])
        self.assertFalse(res[0]["voo_novo"])
        card = next(c for c in corpo["cards"] if c["type"] == "diario_bordo")
        self.assertTrue(card["data"]["registrado"])

    def test_pergunta_depois_do_voo_usa_o_diario(self):
        import cards
        import conversa_proativa

        vid = self.voo(HOJE.isoformat(), hora="08:00")
        conn = db.get_db()
        try:
            from datetime import datetime
            self.assertTrue(conversa_proativa.perguntar_horas_agora(conn, vid, datetime(2026, 10, 22, 11, 0)))
        finally:
            conn.close()
        hist = str(self.client.get("/api/chat/historico").get_json())
        self.assertIn("'diario_bordo'", hist)
        self.assertIn("diario_bordo", cards.TIPOS_CARD)


if __name__ == "__main__":
    unittest.main()
