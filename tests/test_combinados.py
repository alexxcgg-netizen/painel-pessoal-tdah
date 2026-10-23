"""Leva 22/10 (combinados.py): Quadro dos combinados - pessoas (esperas + responder) e empresa so leitura."""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import app
import cards
import combinados
import db


class CombinadosTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_pessoas_junta_esperas_e_responder_com_rascunho(self):
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES ('Instrutor', 'o documento da prova', '2026-10-10 12:00:00')")
        self.conn.execute("INSERT INTO esperas (quem, sobre, resolvido_em) VALUES ('Fulano', 'x', '2026-10-01')")
        self.conn.execute("INSERT INTO responder (quem, sobre, criado_em) VALUES ('Ana', 'o churrasco', '2026-10-20 01:00:00')")
        self.conn.commit()
        p = combinados.pessoas(self.conn, date(2026, 10, 22))
        self.assertEqual([(i["tipo"], i["quem"], i["dias"]) for i in p], [("espera", "Instrutor", 12), ("responder", "Ana", 3)])
        self.assertIn("Conseguiu ver o documento da prova?", p[0]["rascunho"])
        self.assertTrue(p[1]["rascunho"].startswith("Oi, Ana! Desculpa a demora. Sobre o churrasco"))

    def test_empresa_so_atrasadas_como_chegaram_e_sem_total(self):
        contas = {"status": "ok", "contas": [
            {"fornecedor": "Concreto", "descricao": "lote 3", "valor": 7850.0, "dias_ate_vencer": -2},
            {"fornecedor": "Andaime", "descricao": "", "valor": 4200.0, "dias_ate_vencer": -5},
            {"fornecedor": "Frete", "descricao": "", "valor": 1960.0, "dias_ate_vencer": 3},
        ]}
        e = combinados.empresa(contas)
        self.assertEqual([(c["nome"], c["valor"], c["dias"]) for c in e["atrasadas"]], [("Andaime", 4200.0, 5), ("Concreto", 7850.0, 2)])
        self.assertNotIn("total", e)
        self.assertEqual(combinados.empresa(None), {"disponivel": False, "atrasadas": []})

    def test_chat_mostra_o_card_e_visitante_nao_ve(self):
        self.conn.execute("INSERT INTO esperas (quem, sobre) VALUES ('Instrutor', 'o documento')")
        self.conn.commit()
        with patch.object(app, "_buscar_contas_a_vencer_construtora", return_value=None):
            corpo, res = self.chat([("quadro_combinados", {})])
        self.assertEqual((res[0]["pessoas"], res[0]["empresa_disponivel"]), (1, False))
        card = [c for c in corpo["cards"] if c["type"] == "combinados"][0]
        self.assertEqual(card["data"]["pessoas"][0]["quem"], "Instrutor")
        oculto = cards.mascarar_cards([card])[0]["data"]
        self.assertTrue(oculto["oculto"])
        self.assertNotIn("pessoas", oculto)
        self.assertNotIn("empresa", oculto)


if __name__ == "__main__":
    unittest.main()
