"""Grupo B (Tempo), leva do Laboratorio v4 de 30/10/2026: fita, espera, calibrador, disjuntor e porta (tempo.py,
rotas/tempo.py). Banco temporario (tests.test_assistente_vida._Base), relogio sempre injetado, sem rede."""
import json
import unittest
from datetime import datetime, timedelta

from tests.test_assistente_vida import _Base

import cards
import conversa_proativa
import db
import foco
import tempo

DIA = "2026-10-30"
MANHA = datetime(2026, 10, 30, 10, 0, 0)


class TempoBase(_Base):
    def setUp(self):
        super().setUp()
        tempo.limpar_cache()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def voo(self, hora="15:00", data=DIA, horas=None):
        c = self.conn.execute("INSERT INTO voos (data, origem, destino, hora, horas) VALUES (?, 'SSBL', 'SSBL', ?, ?)",
                              (data, hora, horas))
        self.conn.commit()
        return c.lastrowid

    def tarefa(self, titulo, hora=None, data=DIA, local=None, extras=None):
        c = self.conn.execute("INSERT INTO tasks (title, due_date, hora, local, extras) VALUES (?, ?, ?, ?, ?)",
                              (titulo, data, hora, local, json.dumps(extras) if extras else None))
        self.conn.commit()
        return c.lastrowid

    def chat_cards(self, tipo=None):
        out = [c for m in db.list_chat_mensagens(self.conn) for c in db.cards_de_mensagem_chat(m)]
        return [c for c in out if tipo is None or c["type"] == tipo]


class FitaEEsperaTest(TempoBase):
    def test_fita_pega_o_proximo_que_trava_e_ignora_remedio_e_comida(self):
        self.tarefa("Tomar remédio", "10:30")
        self.tarefa("Comer: almoço", "11:00")
        self.tarefa("Academia", "18:30")
        f = tempo.fita(self.conn, MANHA)
        self.assertEqual((f["titulo"], f["hora"], f["tem_saida"]), ("Academia", "18:30", False))
        self.assertEqual(f["sair_em_s"], f["evento_em_s"])  # academia sem local: sai na hora
        self.assertEqual(f["evento_em_s"], 8.5 * 3600)

    def test_fita_voo_sai_antes_pela_antecedencia_mais_folga(self):
        self.voo("15:00")
        f = tempo.fita(self.conn, MANHA)
        self.assertTrue(f["tem_saida"])
        # voo 15:00 - 30 min de briefing - 15 de folga = sai 14:15
        self.assertEqual(f["sair_em_s"], (4 * 60 + 15) * 60)
        self.assertEqual(f["evento_em_s"], 5 * 3600)

    def test_fita_passou_de_5_min_pula_pro_proximo_e_nada_longe(self):
        self.tarefa("Academia", "10:00")
        self.tarefa("Dentista", "16:00")
        self.assertEqual(tempo.fita(self.conn, MANHA + timedelta(minutes=3))["titulo"], "Academia")
        self.assertEqual(tempo.fita(self.conn, MANHA + timedelta(minutes=10))["titulo"], "Dentista")
        self.assertIsNone(tempo.fita(self.conn, datetime(2026, 10, 30, 20, 0)))

    def test_rota_da_fita_e_visitante(self):
        self.voo("23:00")
        r = self.client.get("/api/tempo/fita")
        self.assertEqual(r.status_code, 200)
        self.assertIn("fita", r.get_json())

    def test_espera_card_so_com_janela_de_1h_e_uma_vez_e_nada_de_madrugada(self):
        self.voo("15:00")
        self.assertEqual(tempo.modo_espera(self.conn, datetime(2026, 10, 30, 5, 0)), [])
        self.assertEqual(self.chat_cards("espera"), [])
        tempo.modo_espera(self.conn, MANHA)
        c = self.chat_cards("espera")
        self.assertEqual(len(c), 1)
        d = c[0]["data"]
        # voo 15:00 -> sai 14:15, se arrumar 40 min (padrao) -> livre ate 13:35
        self.assertEqual((d["livre_ate"], d["sair"], d["hora"], d["chamar"]), ("13:35", "14:15", "15:00", "ligado"))
        self.assertEqual((d["livre_min"], d["arrumar_min"], d["ir_min"]), (215, 40, 45))
        tempo.modo_espera(self.conn, MANHA + timedelta(minutes=5))
        self.assertEqual(len(self.chat_cards("espera")), 1)  # uma vez por compromisso

    def test_espera_perto_demais_nao_vira_card(self):
        self.voo("15:00")
        tempo.modo_espera(self.conn, datetime(2026, 10, 30, 13, 0))  # livre so 35 min
        self.assertEqual(self.chat_cards("espera"), [])

    def test_espera_cabe_so_com_palpite_dele_e_multiplica_pelo_fator(self):
        self.voo("15:00")
        self.tarefa("Pagar a fatura", extras={"estimativa_min": 10})
        self.tarefa("Sem palpite")
        self.tarefa("Aula longa", extras={"estimativa_min": 400})
        for est, real in ((20, 40), (10, 20), (30, 60)):
            tempo.registrar_calibragem(self.conn, "x", est, real * 60, MANHA)
        tempo.modo_espera(self.conn, MANHA)
        cabe = self.chat_cards("espera")[0]["data"]["cabe"]
        self.assertEqual([(c["titulo"], c["min"]) for c in cabe], [("Pagar a fatura", 20)])  # 10 x 2,0

    def test_chamada_liga_desliga_e_push_uma_vez_na_hora(self):
        vid = self.voo("15:00")
        # antes da hora de comecar (13:35): nada
        self.assertEqual(tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 12, 0)), [])
        r = self.client.post("/api/tempo/espera/chamar", json={"kind": "voo", "ref": vid, "ligado": False})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 13, 36)), [])  # desligado
        self.client.post("/api/tempo/espera/chamar", json={"kind": "voo", "ref": vid, "ligado": True})
        av = tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 13, 36))
        self.assertEqual([a[0] for a in av], ["espera_chama"])
        self.assertIn("14:15", av[0][2])
        self.assertEqual(tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 13, 40)), [])  # nunca repete

    def test_chamada_cala_na_janela_do_aviso_de_sair(self):
        # voo 15:00 sai 14:15: das 13:50 em diante quem fala e o "hora de ir pro voo", nao um 2o push
        self.voo("15:00")
        self.assertEqual(tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 13, 55)), [])

    def test_compromisso_de_sair_e_garantido_pelo_aviso_que_ja_existe(self):
        self.tarefa("Jantar com a Ana", "20:00")
        i = [x for x in tempo.compromissos(self.conn, MANHA) if x["titulo"].startswith("Jantar")][0]
        self.assertEqual(tempo.chamada(self.conn, i), "garantido")
        self.assertEqual(tempo.chamar_na_hora(self.conn, datetime(2026, 10, 30, 18, 50)), [])

    def test_rota_chamar_valida_corpo(self):
        self.assertEqual(self.client.post("/api/tempo/espera/chamar", json={"kind": "x", "ref": 1, "ligado": True}).status_code, 400)
        self.assertEqual(self.client.post("/api/tempo/espera/chamar", json={"kind": "voo", "ref": 1, "ligado": "sim"}).status_code, 400)


class CalibradorTest(TempoBase):
    def test_fator_precisa_de_3_e_usa_soma_das_ultimas_10(self):
        self.assertIsNone(tempo.fator(self.conn))
        tempo.registrar_calibragem(self.conn, "Lavar o carro", 30, 55 * 60, MANHA)
        tempo.registrar_calibragem(self.conn, "Mercado", 40, 65 * 60, MANHA)
        self.assertIsNone(tempo.fator(self.conn))
        tempo.registrar_calibragem(self.conn, "E-mails", 15, 30 * 60, MANHA)
        f = tempo.fator(self.conn)
        self.assertEqual((f["fator"], f["n"], f["est_media"], f["real_media"]), (1.8, 3, 28, 50))

    def test_registrar_recusa_lixo(self):
        for est, real in ((0, 60), (700, 60), ("abc", 60), (10, "x"), (10, 999 * 60 * 60)):
            self.assertFalse(tempo.registrar_calibragem(self.conn, "x", est, real, MANHA))
        self.assertEqual(tempo.historico(self.conn), [])

    def test_reservar_arredonda_pra_5_e_nunca_menos_de_5(self):
        self.assertEqual(tempo.reservar(20, 1.7), 35)
        self.assertEqual(tempo.reservar(5, 0.5), 5)
        self.assertEqual(tempo.reservar(60, 1.7), 100)

    def test_foco_terminei_com_palpite_alimenta_o_historico(self):
        tid = self.tarefa("Lavar a moto")
        self.assertTrue(tempo.guardar_palpite(self.conn, tid, 20))
        e = foco.abrir(self.conn, MANHA, "Lavar a moto", "Molha a moto.", None, 25, tid)
        foco.comecar(self.conn, MANHA, e["id"])
        foco.responder(self.conn, MANHA + timedelta(minutes=12), "ainda", e["id"])
        foco.responder(self.conn, MANHA + timedelta(minutes=34), "fim", e["id"])
        h = tempo.historico(self.conn)
        self.assertEqual(len(h), 1)
        self.assertEqual((h[0]["titulo"], h[0]["est"]), ("Lavar a moto", 20))
        self.assertGreaterEqual(h[0]["real"], 12)

    def test_foco_sem_palpite_nao_registra(self):
        tid = self.tarefa("Sem palpite")
        e = foco.abrir(self.conn, MANHA, "Sem palpite", "x", None, 10, tid)
        foco.responder(self.conn, MANHA + timedelta(minutes=2), "fim", e["id"])
        self.assertEqual(tempo.historico(self.conn), [])

    def test_contexto_da_ia_leva_o_fator_so_quando_ele_importa(self):
        self.assertIsNone(tempo.linha_contexto(self.conn))
        for est, real in ((20, 34), (10, 17), (30, 51)):
            tempo.registrar_calibragem(self.conn, "x", est, real * 60, MANHA)
        self.assertIn("x1,7", tempo.linha_contexto(self.conn))
        import vida_assistente

        self.assertTrue(any("Fator de tempo" in l for l in vida_assistente.linhas_contexto(self.conn, MANHA)))

    def test_card_publicado_uma_vez_e_de_novo_so_com_5_medidas_e_uma_semana(self):
        for est, real in ((20, 34), (10, 17), (30, 51)):
            tempo.registrar_calibragem(self.conn, "x", est, real * 60, MANHA)
        tempo.calibrador_novo(self.conn, MANHA)
        tempo.calibrador_novo(self.conn, MANHA + timedelta(minutes=5))
        self.assertEqual(len(self.chat_cards("calibrador")), 1)
        d = self.chat_cards("calibrador")[0]["data"]
        self.assertEqual((d["fator"], d["n"], len(d["historico"])), (1.7, 3, 3))
        for _ in range(5):
            tempo.registrar_calibragem(self.conn, "y", 10, 17 * 60, MANHA)
        tempo.calibrador_novo(self.conn, MANHA + timedelta(days=2))
        self.assertEqual(len(self.chat_cards("calibrador")), 1)  # passou 5 medidas, mas faz so 2 dias
        tempo.calibrador_novo(self.conn, MANHA + timedelta(days=8))
        self.assertEqual(len(self.chat_cards("calibrador")), 2)

    def test_rota_do_palpite(self):
        tid = self.tarefa("Lavar a moto")
        r = self.client.post("/api/tempo/calibrador/palpite", json={"task_id": tid, "minutos": 20})
        self.assertEqual(r.get_json()["reserva"], 20)  # sem fator ainda: palpite puro
        self.assertEqual(tempo.palpite_da_tarefa(self.conn, tid), 20)
        self.assertEqual(self.client.post("/api/tempo/calibrador/palpite", json={"task_id": tid, "minutos": 0}).status_code, 400)
        self.assertEqual(self.client.post("/api/tempo/calibrador/palpite", json={"task_id": 9999, "minutos": 10}).status_code, 404)


class DisjuntorTest(TempoBase):
    def _hiperfoco(self, agora, minutos=90):
        db.definir_configuracao(self.conn, "hiperfoco_ate", (agora + timedelta(minutes=minutos)).isoformat(timespec="seconds"))
        db.definir_configuracao(self.conn, "hiperfoco_minutos", str(minutos))

    def test_nao_dispara_antes_de_90_min_e_dispara_uma_vez_por_bloco(self):
        t0 = datetime(2026, 10, 30, 9, 0)
        self._hiperfoco(t0, 90)  # comecou 9:00
        self.assertEqual(tempo.disjuntor(self.conn, t0 + timedelta(minutes=30)), [])
        self._hiperfoco(t0 + timedelta(minutes=30), 90)  # estende: foco seguido, sem buraco
        for m in range(35, 90, 5):  # o tick real roda a cada 5 min
            self.assertEqual(tempo.disjuntor(self.conn, t0 + timedelta(minutes=m)), [])
        av = tempo.disjuntor(self.conn, t0 + timedelta(minutes=95))
        self.assertEqual([a[0] for a in av], ["disjuntor"])
        self.assertEqual(len(self.chat_cards("disjuntor")), 1)
        self.assertEqual(tempo.disjuntor(self.conn, t0 + timedelta(minutes=100)), [])  # 1 por bloco de 90
        self.assertEqual(self.chat_cards("disjuntor")[0]["data"]["motivo"], "tempo")

    def test_buraco_de_mais_de_12_min_quebra_o_foco_seguido(self):
        t0 = datetime(2026, 10, 30, 9, 0)
        self._hiperfoco(t0, 60)
        tempo.disjuntor(self.conn, t0 + timedelta(minutes=50))
        # volta 40 min depois (sem foco nesse meio tempo) e comeca outro
        t1 = t0 + timedelta(minutes=120)
        self._hiperfoco(t1, 25)
        self.assertEqual(tempo.disjuntor(self.conn, t1 + timedelta(minutes=10)), [])
        self.assertEqual(self.chat_cards("disjuntor"), [])

    def test_passou_da_hora_de_comer_sem_refeicao_dispara_com_45_min(self):
        t0 = datetime(2026, 10, 30, 14, 0)
        self._hiperfoco(t0, 60)
        av = tempo.disjuntor(self.conn, t0 + timedelta(minutes=50))
        self.assertEqual(len(av), 1)
        self.assertEqual(self.chat_cards("disjuntor")[0]["data"]["motivo"], "refeicao")

    def test_refeicao_registrada_cala_o_motivo_de_comida(self):
        import refeicoes

        t0 = datetime(2026, 10, 30, 14, 0)
        refeicoes.registrar(self.conn, refeicoes.itens_limpos([{"nome": "Prato", "gramas": 300, "kcal": 600, "proteina_g": 30}]), None, t0)
        self._hiperfoco(t0, 60)
        self.assertEqual(tempo.disjuntor(self.conn, t0 + timedelta(minutes=50)), [])

    def test_parceiro_de_foco_rodando_tambem_conta(self):
        t0 = datetime(2026, 10, 30, 9, 0)
        e = foco.abrir(self.conn, t0, "Estudar", "Abre o livro.", None, 25, None)
        foco.comecar(self.conn, t0, e["id"])
        self.assertEqual(tempo.disjuntor(self.conn, t0 + timedelta(minutes=5)), [])
        self.assertEqual(tempo._foco_desde(self.conn, t0 + timedelta(minutes=5)), t0)

    def test_toques_registram_de_verdade_e_os_tres_zeram(self):
        t0 = datetime.now().replace(microsecond=0)
        self._hiperfoco(t0 - timedelta(minutes=100), 200)
        tempo.disjuntor(self.conn, t0)
        r = self.client.post("/api/tempo/disjuntor", json={"acao": "agua"}).get_json()
        self.assertEqual(r["copos"], 1)
        self.assertEqual(self.client.post("/api/tempo/disjuntor", json={"acao": "comer"}).status_code, 200)
        import refeicoes

        self.assertEqual(refeicoes.do_dia(self.conn, t0.date())["refeicoes"], 1)
        r = self.client.post("/api/tempo/disjuntor", json={"acao": "alongar"}).get_json()
        self.assertTrue(r["zerou"])
        e = json.loads(db.obter_configuracao(self.conn, "disjuntor_estado"))
        self.assertEqual(e["avisos"], 0)
        self.assertEqual(self.client.post("/api/tempo/disjuntor", json={"acao": "veneno"}).status_code, 400)

    def test_push_do_disjuntor_passa_pelo_hiperfoco(self):
        import vida

        self.assertIn("disjuntor", vida.CRITICOS_HIPERFOCO)
        self.assertIn("espera_chama", vida.CRITICOS_HIPERFOCO)


class PortaTest(TempoBase):
    def test_voo_ganha_a_lista_na_hora_de_se_arrumar_e_so_uma_vez(self):
        vid = self.voo("15:00")
        tempo.porta(self.conn, datetime(2026, 10, 30, 13, 0))  # cedo demais
        self.assertEqual(self.chat_cards("porta"), [])
        tempo.porta(self.conn, datetime(2026, 10, 30, 13, 33))
        c = self.chat_cards("porta")
        self.assertEqual(len(c), 1)
        d = c[0]["data"]
        self.assertEqual((d["lugar"], d["sai"], d["voo_id"]), ("Voo", "14:15", vid))
        self.assertEqual([l["nome"] for l in d["lugares"]], ["Voo", "Academia", "Faculdade"])
        self.assertEqual(d["lugares"][0]["itens"][0]["texto"], "CIV e CMA")
        tempo.porta(self.conn, datetime(2026, 10, 30, 13, 40))
        self.assertEqual(len(self.chat_cards("porta")), 1)

    def test_mochila_da_vespera_vale_na_porta(self):
        vid = self.voo("15:00")
        db.definir_configuracao(self.conn, f"mochila_voo_{vid}", json.dumps([True, True, False, False, False, False, False]))
        d = tempo.card_porta(self.conn, "Voo", DIA, voo_id=vid)["data"]
        self.assertEqual([i["feito"] for i in d["lugares"][0]["itens"]][:3], [True, True, False])

    def test_marcar_voo_escreve_na_mesma_mochila_da_vespera(self):
        vid = self.voo("15:00")
        r = self.client.post("/api/tempo/porta/marcar", json={"lugar": "Voo", "i": 1, "feito": True, "dia": DIA, "voo_id": vid})
        self.assertTrue(r.get_json()["feitos"][1])
        self.assertTrue(cards.mochila_feita(self.conn, vid)[1])

    def test_academia_marca_por_dia_e_amanha_comeca_limpo(self):
        self.client.post("/api/tempo/porta/marcar", json={"lugar": "Academia", "i": 0, "feito": True, "dia": DIA})
        hoje = tempo.card_porta(self.conn, "Academia", DIA)["data"]
        amanha = tempo.card_porta(self.conn, "Academia", "2026-10-31")["data"]
        self.assertTrue(hoje["lugares"][1]["itens"][0]["feito"])
        self.assertFalse(amanha["lugares"][1]["itens"][0]["feito"])

    def test_esqueci_uma_vez_entra_pra_sempre_sem_duplicar_e_remove(self):
        r = self.client.post("/api/tempo/porta/item", json={"lugar": "Academia", "item": "  Cinto de   treino ", "dia": DIA})
        itens = [i["texto"] for i in r.get_json()["card"]["lugares"][1]["itens"]]
        self.assertEqual(itens[-1], "Cinto de treino")
        self.assertTrue(r.get_json()["card"]["lugares"][1]["itens"][-1]["meu"])
        self.client.post("/api/tempo/porta/item", json={"lugar": "Academia", "item": "toalha"})  # ja existe
        self.client.post("/api/tempo/porta/item", json={"lugar": "Academia", "item": "cinto de treino"})
        self.assertEqual([x for x in tempo.listas(self.conn)["Academia"]["extras"]], ["Cinto de treino"])
        r = self.client.post("/api/tempo/porta/item", json={"lugar": "Academia", "item": "Cinto de treino", "acao": "remover"})
        self.assertEqual(tempo.listas(self.conn)["Academia"]["extras"], [])
        self.assertEqual(self.client.post("/api/tempo/porta/item", json={"lugar": "Padaria", "item": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/tempo/porta/item", json={"lugar": "Academia", "item": "  "}).status_code, 400)

    def test_marcar_valida_indice_e_corpo(self):
        for corpo in ({"lugar": "Academia", "i": 99, "feito": True, "dia": DIA}, {"lugar": "Academia", "i": 0, "feito": "s", "dia": DIA},
                      {"lugar": "Academia", "i": 0, "feito": True, "dia": "ontem"}, {"lugar": "Outro", "i": 0, "feito": True, "dia": DIA}):
            self.assertEqual(self.client.post("/api/tempo/porta/marcar", json=corpo).status_code, 400, corpo)

    def test_vespera_da_academia_pergunta_se_deixa_a_mochila_pronta(self):
        self.tarefa("Academia", "07:00", data="2026-10-31")
        tempo.porta(self.conn, datetime(2026, 10, 30, 19, 0))  # antes da janela
        self.assertEqual(self.chat_cards("porta"), [])
        tempo.porta(self.conn, datetime(2026, 10, 30, 21, 0))
        c = self.chat_cards("porta")
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0]["data"]["vespera"])
        self.assertEqual(c[0]["data"]["dia"], "2026-10-31")
        tempo.porta(self.conn, datetime(2026, 10, 30, 21, 5))
        self.assertEqual(len(self.chat_cards("porta")), 1)

    def test_tick_inteiro_nao_quebra_e_tipos_estao_no_contrato(self):
        self.voo("15:00")
        conversa_proativa.verificar(self.conn, MANHA)
        for t in ("espera", "calibrador", "disjuntor", "porta"):
            self.assertIn(t, cards.TIPOS_CARD)


if __name__ == "__main__":
    unittest.main()
