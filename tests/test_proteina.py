"""Leva 22/10 (refeicoes.sugestoes): Refeicao pela proteina - a proxima refeicao sai do que ele costuma comer."""
import json
import unittest
from datetime import date

from tests.test_assistente_vida import _Base

import db
import refeicoes


class SugestoesTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()
        refeicoes.criar_tabela(self.conn)

    def tearDown(self):
        self.conn.close()

    def _foto(self, dia, itens):
        self.conn.execute("INSERT INTO refeicoes (dia, itens_json) VALUES (?, ?)", (dia, json.dumps(itens)))
        self.conn.commit()

    def test_mais_frequente_com_mediana_e_completa_com_o_padrao(self):
        self._foto("2026-10-20", [{"nome": "Frango grelhado", "proteina_g": 40}, {"nome": "Arroz", "proteina_g": 4}])
        self._foto("2026-10-21", [{"nome": "frango grelhado", "proteina_g": 30}, {"nome": "Ovos mexidos", "proteina_g": 18}])
        self._foto("2026-10-22", [{"nome": "Frango grelhado", "proteina_g": 50}])
        self._foto("2026-08-01", [{"nome": "Picanha", "proteina_g": 60}])  # velho demais
        s = refeicoes.sugestoes(self.conn, date(2026, 10, 22))
        self.assertEqual(s[0], {"nome": "Frango grelhado", "g": 40})
        self.assertEqual(s[1], {"nome": "Ovos mexidos", "g": 18})
        self.assertEqual(len(s), 3)  # arroz (pouca proteina) nao entra; o 3o vem do padrao
        self.assertNotIn("Picanha", [x["nome"] for x in s])

    def test_sem_historico_usa_o_padrao(self):
        self.assertEqual([x["nome"] for x in refeicoes.sugestoes(self.conn, date(2026, 10, 22))],
                         [n for n, _ in refeicoes.SUGESTOES_PADRAO])


if __name__ == "__main__":
    unittest.main()
