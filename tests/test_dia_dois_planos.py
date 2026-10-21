"""Conversa mais humana (2026-10-21, prototipo aprovado "balao que vira card + pilula"): o
planejar_dia grava o plano A e leva um plano B pro card; o historico mostra o plano que esta
valendo; "\\u00e1" literal da IA vira o caractere. claude_client.chat e dublado; nenhuma rede."""
import unittest
from datetime import date

from tests.test_assistente_vida import _Base

import app
import cards

AMANHA = date.fromordinal(date.today().toordinal() + 1).isoformat()
BLOCOS_A = [
    {"titulo": "Revisao do carro", "hora": "09:00"},
    {"titulo": "Ligar pro banco", "hora": "11:00"},
    {"titulo": "Estudar teoria", "hora": "15:00"},
]


class DoisPlanosTestCase(_Base):
    def _planejar(self, plano_b):
        entrada = {"data": AMANHA, "blocos": BLOCOS_A, "plano_a_nome": "Carro de manha",
                   "plano_a_nota": "antes da chuva", "plano_b": plano_b}
        corpo, res = self.chat([("planejar_dia", entrada)])
        card = next(c for c in corpo["cards"] if c["type"] == "tarefas_criadas")
        return card, res[0]

    def test_plano_b_vai_pro_card_com_os_ids_das_tarefas(self):
        card, res = self._planejar({"nome": "Tudo a tarde", "nota": "carro pega chuva", "blocos": [
            {"titulo": "revisão do carro", "hora": "14:00"},
            {"titulo": "Estudar teoria", "hora": "17:00"},
            {"titulo": "Bloco que nao existe no A", "hora": "18:00"},
        ]})
        planos = card["data"]["planos"]
        self.assertEqual(planos["escolhido"], "a")
        self.assertEqual(planos["a"]["nome"], "Carro de manha")
        self.assertEqual([i["hora"] for i in planos["a"]["itens"]], ["09:00", "11:00", "15:00"])
        self.assertEqual([i["hora"] for i in planos["b"]["itens"]], ["14:00", "17:00"])  # o bloco solto caiu
        ids = {t["id"] for t in card["data"]["agenda_do_dia"]}
        self.assertTrue(all(i["id"] in ids for i in planos["b"]["itens"]))
        self.assertEqual(res["plano_b_no_card"], "Tudo a tarde")
        # o A e o que ficou gravado
        horas = [r["hora"] for r in self.sql("SELECT hora FROM tasks ORDER BY id")]
        self.assertEqual(horas, ["09:00", "11:00", "15:00"])

    def test_plano_b_igual_ou_vazio_nao_vira_pilula(self):
        for b in ({"nome": "Igual", "blocos": [{"titulo": "Ligar pro banco", "hora": "11:00"}]},
                  {"nome": "Nada casa", "blocos": [{"titulo": "Outra coisa", "hora": "08:00"}]},
                  {"nome": "Sem blocos"}, "texto", None):
            self.sql("DELETE FROM tasks")
            card, res = self._planejar(b)
            self.assertNotIn("planos", card["data"], b)
            self.assertNotIn("plano_b_no_card", res)

    def test_historico_mostra_o_plano_que_esta_valendo(self):
        card, _ = self._planejar({"nome": "Tudo a tarde", "blocos": [
            {"titulo": "Revisao do carro", "hora": "14:00"}, {"titulo": "Estudar teoria", "hora": "17:00"}]})
        hist = self.client.get("/api/chat/historico").get_json()
        guardado = next(c for m in hist for c in m["cards"] if c["type"] == "tarefas_criadas")
        self.assertEqual(guardado["data"]["planos"]["escolhido"], "a")
        # trocou na pilula (o front chama a rota de hora pra cada item do B)
        for i in card["data"]["planos"]["b"]["itens"]:
            r = self.client.post(f"/api/tasks/{i['id']}/hora", json={"hora": i["hora"]})
            self.assertEqual(r.status_code, 200)
        hist = self.client.get("/api/chat/historico").get_json()
        guardado = next(c for m in hist for c in m["cards"] if c["type"] == "tarefas_criadas")
        self.assertEqual(guardado["data"]["planos"]["escolhido"], "b")


class PlanosValidosTestCase(unittest.TestCase):
    def test_filtra_id_de_fora_hora_ruim_e_plano_sem_nome(self):
        p = {"a": {"nome": "A", "itens": [{"id": 1, "hora": "09:00"}, {"id": 99, "hora": "10:00"}]},
             "b": {"nome": "B", "nota": "x" * 300, "itens": [{"id": 1, "hora": "9h"}, {"id": 2, "hora": "14:00"}]}}
        v = cards.planos_validos(p, {1, 2})
        self.assertEqual(v["a"]["itens"], [{"id": 1, "hora": "09:00"}])
        self.assertEqual(v["b"]["itens"], [{"id": 2, "hora": "14:00"}])
        self.assertEqual(len(v["b"]["nota"]), 140)
        self.assertIsNone(cards.planos_validos({**p, "b": {"nome": "", "itens": p["b"]["itens"]}}, {1, 2}))
        self.assertIsNone(cards.planos_validos({"a": p["a"]}, {1, 2}))
        self.assertIsNone(cards.planos_validos("x", {1}))


class DesescaparTestCase(unittest.TestCase):
    def test_escape_literal_vira_caractere(self):
        self.assertEqual(app._desescapar_unicode("j\\u00e1 marquei, est\\u00E1 \\u00f3timo"), "já marquei, está ótimo")
        self.assertEqual(app._desescapar_unicode("sem escape \\n aqui"), "sem escape \\n aqui")
        self.assertIsNone(app._desescapar_unicode(None))


if __name__ == "__main__":
    unittest.main()
