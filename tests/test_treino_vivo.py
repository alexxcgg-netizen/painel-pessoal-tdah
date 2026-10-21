"""Treino ao vivo (2026-10-21): "vou treinar peito" abre a ficha com caixinha por exercicio, o
ultimo marcado registra o treino, e "o supino foi pra 25" troca so aquela carga na ficha (com
Desfazer). claude_client.chat e dublado; nenhuma rede."""
import unittest
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import app
import treino_vivo

PEITO = "Supino reto|4|10|20 kg\nCrucifixo|3|12|\nTriceps corda|4|12|15 kg"


class LerExercicioTestCase(unittest.TestCase):
    def test_texto_livre_e_formato_do_menu(self):
        self.assertEqual(treino_vivo.ler_exercicio("supino reto 4x10 com 20kg"),
                         {"nome": "Supino reto", "series": "4", "reps": "10", "carga": "20 kg"})
        self.assertEqual(treino_vivo.ler_exercicio("Crucifixo 3 x 8-12"),
                         {"nome": "Crucifixo", "series": "3", "reps": "8-12", "carga": ""})
        self.assertEqual(treino_vivo.ler_exercicio("Remada|4|10|30 kg")["carga"], "30 kg")
        self.assertEqual(treino_vivo.ler_exercicio("Prancha")["nome"], "Prancha")
        self.assertIsNone(treino_vivo.ler_exercicio("   "))
        self.assertEqual(treino_vivo.normalizar_ficha(["supino 4x10 20kg", "", "prancha"]),
                         "Supino|4|10|20 kg\nPrancha|||")

    def test_carga_texto(self):
        self.assertEqual(treino_vivo.carga_texto("25"), "25 kg")
        self.assertEqual(treino_vivo.carga_texto(22.5), "22.5 kg")
        self.assertEqual(treino_vivo.carga_texto("25KG"), "25 kg")
        self.assertEqual(treino_vivo.carga_texto("3 placas"), "3 placas")
        self.assertEqual(treino_vivo.carga_texto(None), "")
        self.assertEqual(treino_vivo.carga_texto(True), "")

    def test_achar_ficha_e_exercicio(self):
        fichas = [{"id": 1, "grupo": "Peito e tríceps"}, {"id": 2, "grupo": "Treino B"}, {"id": 3, "grupo": "Costas"}]
        self.assertEqual(treino_vivo.achar_ficha(fichas, "peito")["id"], 1)
        self.assertEqual(treino_vivo.achar_ficha(fichas, "treino b")["id"], 2)
        self.assertEqual(treino_vivo.achar_ficha(fichas, "B")["id"], 2)
        self.assertEqual(treino_vivo.achar_ficha(fichas, "triceps e peito")["id"], 1)
        self.assertIsNone(treino_vivo.achar_ficha(fichas, "perna"))
        exs = treino_vivo.exercicios_da_ficha(PEITO + "\nSupino inclinado halter|3|12|")
        self.assertEqual(treino_vivo.achar_exercicio(exs, "crucifixo"), 1)
        self.assertEqual(treino_vivo.achar_exercicio(exs, "supino reto"), 0)
        self.assertIsNone(treino_vivo.achar_exercicio(exs, "supino"))  # dois supinos: nao chuta
        self.assertEqual(treino_vivo.achar_exercicio(exs, "inclinado"), 3)

    def test_rotacao_pega_a_feita_ha_mais_tempo(self):
        fichas = [{"id": 1, "grupo": "A"}, {"id": 2, "grupo": "B"}, {"id": 3, "grupo": "C"}]
        self.assertEqual(treino_vivo.proxima_da_rotacao(fichas, {"a": "2026-10-20", "b": "2026-10-18", "c": "2026-10-19"})["id"], 2)
        self.assertEqual(treino_vivo.proxima_da_rotacao(fichas, {"a": "2026-10-20"})["id"], 2)  # nunca feita primeiro
        self.assertIsNone(treino_vivo.proxima_da_rotacao([], {}))


class TreinoAoVivoTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios": PEITO})
        self.client.post("/api/treino/fichas", json={"grupo": "Costas", "exercicios": "Remada|4|10|30 kg"})

    def _card(self, corpo, tipo):
        return next(c for c in corpo["cards"] if c["type"] == tipo)

    def _marcar(self, sessao, i, feito=True):
        return self.client.post(f"/api/treino/sessoes/{sessao}/exercicio", json={"i": i, "feito": feito})

    def test_comecar_treino_abre_a_ficha_com_caixinhas(self):
        corpo, res = self.chat([("comecar_treino", {"grupo": "peito"})])
        card = self._card(corpo, "treino_agora")
        self.assertEqual(card["data"]["grupo"], "Peito")
        self.assertEqual([e["nome"] for e in card["data"]["exercicios"]], ["Supino reto", "Crucifixo", "Triceps corda"])
        self.assertEqual(card["data"]["feitos"], [])
        self.assertEqual(res[0]["exercicios"][0], "Supino reto 4x10 20 kg")
        # abrir de novo no mesmo dia e a mesma sessao
        _, res2 = self.chat([("comecar_treino", {"grupo": "Peito"})])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM treino_sessoes")[0][0], 1)
        self.assertNotIn("erro", res2[0])

    def test_sem_grupo_vem_a_da_vez_e_grupo_errado_lista_as_fichas(self):
        self.client.post("/api/treino", json={"grupo": "peito"})
        _, res = self.chat([("comecar_treino", {})])
        self.assertEqual(res[0]["ficha"], "Costas")
        self.assertEqual(res[0]["escolhida_por"], "rotacao")
        _, res = self.chat([("comecar_treino", {"grupo": "perna"})])
        self.assertIn("erro", res[0])
        self.assertEqual(sorted(res[0]["fichas"]), ["Costas", "Peito"])

    def test_ultimo_marcado_registra_e_desmarcar_desfaz(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        sid = self._card(corpo, "treino_agora")["data"]["sessao_id"]
        self.assertFalse(self._marcar(sid, 0).get_json()["concluido"])
        self.assertFalse(self._marcar(sid, 1).get_json()["concluido"])
        r = self._marcar(sid, 2).get_json()
        self.assertTrue(r["concluido"])
        self.assertEqual(r["feitos"], [0, 1, 2])
        treinos = self.sql("SELECT grupo, origem FROM treinos")
        self.assertEqual([(t["grupo"], t["origem"]) for t in treinos], [("Peito", "sessao")])
        # marcar de novo nao duplica
        self._marcar(sid, 2)
        self.assertEqual(len(self.sql("SELECT id FROM treinos")), 1)
        # "Feito hoje" da ficha enxerga o treino
        fichas = {f["grupo"]: f for f in self.client.get("/api/treino/fichas").get_json()}
        self.assertTrue(fichas["Peito"]["feito_hoje"])
        r = self._marcar(sid, 1, False).get_json()
        self.assertFalse(r["concluido"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM treinos")[0][0], 0)

    def test_marcar_com_entrada_ruim(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        sid = self._card(corpo, "treino_agora")["data"]["sessao_id"]
        for corpo_ruim in ({"i": 0}, {"i": "0", "feito": True}, {"i": True, "feito": True}, {"i": -1, "feito": True}, [1]):
            self.assertEqual(self.client.post(f"/api/treino/sessoes/{sid}/exercicio", json=corpo_ruim).status_code, 400)
        self.assertEqual(self._marcar(sid, 3).status_code, 400)
        self.assertEqual(self._marcar(999, 0).status_code, 404)

    def test_historico_mostra_as_caixinhas_de_agora(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        sid = self._card(corpo, "treino_agora")["data"]["sessao_id"]
        self._marcar(sid, 0)
        hist = self.client.get("/api/chat/historico").get_json()
        card = next(c for m in hist for c in m["cards"] if c["type"] == "treino_agora")
        self.assertEqual(card["data"]["feitos"], [0])

    def test_registrar_treino_depois_da_ficha_completa_nao_duplica(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        sid = self._card(corpo, "treino_agora")["data"]["sessao_id"]
        for i in range(3):
            self._marcar(sid, i)
        _, res = self.chat([("registrar_treino", {"grupo": "Peito", "duracao_min": 55, "nota": "pesado"})])
        self.assertTrue(res[0]["ja_registrado_pela_ficha"])
        linhas = self.sql("SELECT duracao_min, nota FROM treinos")
        self.assertEqual([(l["duracao_min"], l["nota"]) for l in linhas], [(55, "pesado")])

    def test_atualizar_carga_troca_so_aquele_exercicio_e_desfaz(self):
        corpo, res = self.chat([("atualizar_carga_treino", {"exercicio": "supino", "carga": "25"})])
        self.assertEqual((res[0]["antes"], res[0]["depois"]), ("20 kg", "25 kg"))
        ficha = self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Peito'")[0]["exercicios"]
        self.assertEqual(ficha, "Supino reto|4|10|25 kg\nCrucifixo|3|12|\nTriceps corda|4|12|15 kg")
        card = self._card(corpo, "treino_carga")
        self.assertEqual(card["data"]["mudancas"][0]["sentido"], "subiu")
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        ficha = self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Peito'")[0]["exercicios"]
        self.assertEqual(ficha, PEITO)

    def test_duas_trocas_numa_resposta_um_card_e_desfazer_volta_tudo(self):
        corpo, _ = self.chat([
            ("atualizar_carga_treino", {"exercicio": "supino reto", "carga": "25 kg"}),
            ("atualizar_carga_treino", {"exercicio": "crucifixo", "carga": "12", "reps": "10"}),
        ])
        cards = [c for c in corpo["cards"] if c["type"] == "treino_carga"]
        self.assertEqual(len(cards), 1)
        self.assertEqual([m["exercicio"] for m in cards[0]["data"]["mudancas"]], ["Supino reto", "Crucifixo"])
        self.assertIsNone(cards[0]["data"]["mudancas"][1]["sentido"])  # nao tinha carga antes
        ficha = self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Peito'")[0]["exercicios"]
        self.assertIn("Crucifixo|3|10|12 kg", ficha)
        token = next(a["token"] for a in cards[0]["actions"] if a["tipo"] == "desfazer")
        self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Peito'")[0]["exercicios"], PEITO)

    def test_historico_da_carga_vira_grafico_e_desfazer_tira_o_ponto(self):
        # ficha salva ha uma semana com 20 kg (ponto de partida)
        self.sql("UPDATE treino_fichas SET atualizado_em = date('now', '-7 day')")
        self.sql("DELETE FROM treino_cargas")
        corpo, _ = self.chat([("atualizar_carga_treino", {"exercicio": "supino reto", "carga": "25"})])
        hist = self._card(corpo, "treino_carga")["data"]["mudancas"][0]["historico"]
        self.assertEqual([h["kg"] for h in hist], [20.0, 25.0])
        self.assertLess(hist[0]["data"], hist[1]["data"])
        corpo, _ = self.chat([("atualizar_carga_treino", {"exercicio": "supino reto", "carga": "22,5"})])
        card = self._card(corpo, "treino_carga")
        self.assertEqual([h["kg"] for h in card["data"]["mudancas"][0]["historico"]], [20.0, 22.5])  # 1 ponto por dia
        self.assertEqual(card["data"]["mudancas"][0]["sentido"], "desceu")
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.client.post(f"/api/desfazer/{token}")
        kgs = [r["carga_num"] for r in self.sql("SELECT carga_num FROM treino_cargas WHERE nome = 'Supino reto' ORDER BY id")]
        self.assertEqual(kgs, [20.0, 25.0])

    def test_ficha_salva_grava_o_ponto_de_partida_so_em_kg(self):
        self.client.post("/api/treino/fichas", json={"grupo": "Ombro", "exercicios": "Elevacao lateral|3|12|8 kg\nPrancha|3|1 min|"})
        linhas = self.sql("SELECT nome, carga_num FROM treino_cargas WHERE nome IN ('Elevacao lateral', 'Prancha')")
        self.assertEqual([(l["nome"], l["carga_num"]) for l in linhas], [("Elevacao lateral", 8.0)])
        # salvar de novo igual nao repete o ponto
        self.client.post("/api/treino/fichas", json={"grupo": "Ombro", "exercicios": "Elevacao lateral|3|12|8 kg"})
        self.assertEqual(len(self.sql("SELECT id FROM treino_cargas WHERE nome = 'Elevacao lateral'")), 1)

    def test_carga_exercicio_inexistente_ou_ambiguo(self):
        self.client.post("/api/treino/fichas", json={"grupo": "Ombro", "exercicios": "Remada alta|3|12|10 kg"})
        _, res = self.chat([("atualizar_carga_treino", {"exercicio": "leg press", "carga": "100"})])
        self.assertIn("erro", res[0])
        self.assertIn("Peito", res[0]["exercicios_das_fichas"])
        _, res = self.chat([("atualizar_carga_treino", {"exercicio": "remada", "carga": "35"})])
        self.assertIn("mais de uma", res[0]["erro"])
        # com a ficha de costas aberta hoje, desempata
        self.chat([("comecar_treino", {"grupo": "costas"})])
        _, res = self.chat([("atualizar_carga_treino", {"exercicio": "remada", "carga": "35"})])
        self.assertEqual((res[0]["ficha"], res[0]["depois"]), ("Costas", "35 kg"))
        _, res = self.chat([("atualizar_carga_treino", {"exercicio": "supino", "carga": ""})])
        self.assertIn("erro", res[0])

    def test_ficha_colada_no_chat_vira_formato_do_menu(self):
        self.chat([("salvar_ficha_treino", {"grupo": "Perna", "exercicios": ["agachamento 4x10 60kg", "leg press 3x12"]})])
        ficha = self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Perna'")[0]["exercicios"]
        self.assertEqual(ficha, "Agachamento|4|10|60 kg\nLeg press|3|12|")

    def test_sono_do_treino_grava_e_cruza_com_a_carga(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        card = self._card(corpo, "treino_agora")
        self.assertIsNone(card["data"]["sono_horas"])  # ainda nao respondeu: o card pergunta
        sid = card["data"]["sessao_id"]
        for ruim in ({}, {"horas": "7"}, {"horas": True}, {"horas": 1}, {"horas": 20}):
            self.assertEqual(self.client.post(f"/api/treino/sessoes/{sid}/sono", json=ruim).status_code, 400)
        self.assertEqual(self.client.post("/api/treino/sessoes/9999/sono", json={"horas": 7}).status_code, 404)
        r = self.client.post(f"/api/treino/sessoes/{sid}/sono", json={"horas": 7.6}).get_json()
        self.assertEqual(r["sono_horas"], 7.5)
        hist = self.client.get("/api/chat/historico").get_json()
        cards_hist = [c for m in hist for c in (m.get("cards") or []) if c["type"] == "treino_agora"]
        self.assertEqual(cards_hist[-1]["data"]["sono_horas"], 7.5)
        # a troca de carga leva o sono de cada dia junto do ponto
        corpo, _ = self.chat([("atualizar_carga_treino", {"exercicio": "supino reto", "carga": "25"})])
        pontos = self._card(corpo, "treino_carga")["data"]["mudancas"][0]["historico"]
        self.assertEqual(pontos[-1]["sono"], 7.5)
        # modo visitante: nao grava e o sono sai dos cards
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self.client.post(f"/api/treino/sessoes/{sid}/sono", json={"horas": 5}).status_code, 403)
        import cards
        mascarados = cards.mascarar_cards([self._card(corpo, "treino_carga"), card | {"data": {**card["data"], "sono_horas": 7.5}}])
        self.assertNotIn("sono", mascarados[0]["data"]["mudancas"][0]["historico"][-1])
        self.assertNotIn("sono_horas", mascarados[1]["data"])

    def test_modo_visitante_nao_mexe(self):
        corpo, _ = self.chat([("comecar_treino", {"grupo": "peito"})])
        sid = self._card(corpo, "treino_agora")["data"]["sessao_id"]
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self._marcar(sid, 0).status_code, 403)
            _, res = self.chat([("atualizar_carga_treino", {"exercicio": "supino", "carga": "25"})])
        self.assertIn("erro", res[0])
        self.assertEqual(self.sql("SELECT exercicios FROM treino_fichas WHERE grupo = 'Peito'")[0]["exercicios"], PEITO)


if __name__ == "__main__":
    unittest.main()
