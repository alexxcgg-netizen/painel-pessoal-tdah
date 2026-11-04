"""Laboratorio v4, Grupo F (Aviacao), 30/10/2026: aviacao_lab.py + rotas/aviacao_lab.py.
Radar de validades, previsao do cheque, banca por caderno, voo de cadeira, vento na pista e passaporte.
Nenhuma rede: o METAR entra por funcao injetada ou mock."""
import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import aviacao_lab
import cards
import conversa_proativa
import db

HOJE = date(2026, 10, 30)


def _metar(direcao=290, vel=12, rajada=None, variavel=False):
    return {
        "metar": f"SSBL 301200Z {direcao:03d}{vel:02d}KT 9999 SCT030 24/17 Q1016",
        "metar_decodificado": {"vento": {"direcao": direcao, "velocidade_kt": vel, "rajada_kt": rajada, "variavel": variavel}},
    }


class AviacaoLabBase(_Base):
    def com_conn(self, fn, *a, **k):
        conn = db.get_db()
        try:
            r = fn(conn, *a, **k)
            conn.commit()
            return r
        finally:
            conn.close()

    def voo(self, data, origem="SSBL", destino="SSBL", horas=None, **extra):
        cols = ["data", "origem", "destino", "horas", *extra]
        conn = db.get_db()
        try:
            i = conn.execute(f"INSERT INTO voos ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             (data, origem, destino, horas, *extra.values())).lastrowid
            conn.commit()
            return i
        finally:
            conn.close()


class RadarTest(AviacaoLabBase):
    def test_prazos_digitados_viram_itens_com_tom_e_dias(self):
        self.com_conn(aviacao_lab.salvar_prazo, "cma", "2027-03-17")
        self.com_conn(aviacao_lab.salvar_prazo, "endosso", "2026-10-24")  # +30 d = 23/11
        self.com_conn(aviacao_lab.salvar_prazo, "fgv", "2026-09-01")  # +60 d = 31/10
        r = self.com_conn(aviacao_lab.radar, HOJE)
        por = {i["chave"]: i for i in r["itens"]}
        self.assertEqual(por["cma"]["dias"], 138)
        self.assertEqual(por["cma"]["tom"], "ok")
        self.assertEqual(por["endosso"]["vence"], "2026-11-23")
        self.assertEqual(por["endosso"]["dias"], 24)
        self.assertEqual(por["endosso"]["tom"], "alerta")
        self.assertEqual(por["fgv"]["dias"], 1)
        self.assertEqual(por["fgv"]["tom"], "perigo")
        self.assertEqual([i["chave"] for i in r["itens"]], ["fgv", "endosso", "cma"])
        self.assertEqual(len(r["campos"]), 6)

    def test_cma_nao_tem_regra_calculada_e_fica_marcado(self):
        # a validade do CMA (RBAC 67) nao foi conferida: o painel so guarda a data que ele digitou
        cma = next(p for p in aviacao_lab.PRAZOS if p[0] == "cma")
        self.assertEqual(cma[2], "vence")
        self.assertIsNone(cma[3])
        self.assertIn("não conferi", cma[5])

    def test_valida_chave_e_data(self):
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_prazo, "inventado", "2026-01-01")
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_prazo, "cma", "31/12/2026")
        self.com_conn(aviacao_lab.salvar_prazo, "cma", "2027-01-01")
        self.com_conn(aviacao_lab.salvar_prazo, "cma", "")
        self.assertEqual(self.com_conn(aviacao_lab.radar, HOJE)["itens"], [])

    def test_voo_sem_confirmacao_na_civ_vem_primeiro_e_some_ao_confirmar(self):
        antigo = self.voo("2026-09-01", horas=1.0)  # fora da janela de 14 dias
        ontem = self.voo("2026-10-29", horas=1.2)
        da_civ = self.voo("2026-10-28", horas=1.0, fonte="civ")
        sim = self.voo("2026-10-27", horas=1.0, tipo="simulador")
        self.com_conn(aviacao_lab.salvar_prazo, "cma", "2027-03-17")
        r = self.com_conn(aviacao_lab.radar, HOJE)
        self.assertEqual([i["chave"] for i in r["itens"]], [f"civ{ontem}", "cma"])
        self.assertTrue(r["itens"][0]["pendente"])
        self.assertEqual(r["itens"][0]["tom"], "perigo")
        self.assertEqual(r["itens"][0]["nome"], "Confirmar o voo de 29/10 na CIV")
        self.assertTrue(self.com_conn(aviacao_lab.confirmar_civ, ontem))
        self.assertEqual([i["chave"] for i in self.com_conn(aviacao_lab.radar, HOJE)["itens"]], ["cma"])
        self.assertFalse(self.com_conn(aviacao_lab.confirmar_civ, 9999))
        _ = (antigo, da_civ, sim)

    def test_avisos_so_nos_marcos_e_uma_vez_cada(self):
        self.com_conn(aviacao_lab.salvar_prazo, "cma", (HOJE + timedelta(days=28)).isoformat())
        manha = datetime(2026, 10, 30, 10, 0)
        saida = self.com_conn(aviacao_lab.avisos_prazos, manha)
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0][0], "prazo_aviacao")
        self.assertIn("CMA", saida[0][2])
        self.assertEqual(self.com_conn(aviacao_lab.avisos_prazos, manha), [])  # idempotente
        self.assertEqual(self.com_conn(aviacao_lab.avisos_prazos, datetime(2026, 10, 30, 22, 0)), [])  # fora da janela
        chat = self.sql("SELECT cards_json FROM chat_mensagens ORDER BY id DESC LIMIT 1")
        self.assertTrue(chat)


class PrevisaoChequeTest(AviacaoLabBase):
    def test_ritmo_das_ultimas_4_semanas_e_gargalo_sem_ritmo(self):
        # 28 h antigas + 4 voos recentes de 2 h (8 h em 4 semanas = ~8,7 h/mes); nenhuma hora noturna
        self.voo("2026-08-01", "SSBL", "SBFL", 28.0, natureza="navegacao")
        for d in ("2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"):
            self.voo(d, "SSBL", "SBNF", 2.0, natureza="navegacao")
        p = self.com_conn(aviacao_lab.previsao_cheque, HOJE)
        por = {r["chave"]: r for r in p["requisitos"]}
        self.assertEqual(por["total"]["h"], 36.0)
        self.assertEqual(por["total"]["falta"], 114.0)
        self.assertAlmostEqual(por["total"]["ritmo_mes"], 8.7, places=1)
        self.assertEqual(por["navegacao"]["h"], 36.0)
        self.assertEqual(por["noturno"]["ritmo_mes"], 0)
        self.assertIsNone(por["noturno"]["data"])
        self.assertIn(p["gargalo"], ("instrumentos", "noturno"))  # os dois sem nenhuma hora recente
        self.assertTrue(p["gargalo_sem_ritmo"])
        self.assertIsNone(p["data_cheque"])  # sem ritmo noturno nao existe data honesta
        self.assertIsNotNone(p["simulacao_noturno"])
        self.assertEqual(p["simulacao_noturno"]["falta"], 5.0)
        self.assertIn("300 NM", p["lembrete_navegacao"])

    def test_requisito_sem_nenhuma_hora_recente_e_o_gargalo_mesmo_que_outro_atrase_mais(self):
        for d in ("2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"):
            self.voo(d, "SSBL", "SSBL", 10.0, natureza="tgl", noturno=1)
        p = self.com_conn(aviacao_lab.previsao_cheque, HOJE)
        por = {r["chave"]: r for r in p["requisitos"]}
        self.assertTrue(por["noturno"]["fechou"])
        self.assertEqual(p["gargalo"], "navegacao")  # TGL nao e navegacao: sem ritmo, sem data
        self.assertTrue(p["gargalo_sem_ritmo"])
        self.assertIsNone(p["data_cheque"])

    def test_com_ritmo_em_tudo_o_gargalo_e_o_que_fecha_por_ultimo(self):
        for d in ("2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"):
            self.voo(d, "SSBL", "SBNF", 5.0, natureza="navegacao", noturno=1)
            self.voo(d, "SSBL", "SSBL", 5.0, natureza="instrumentos")
        p = self.com_conn(aviacao_lab.previsao_cheque, HOJE)
        por = {r["chave"]: r for r in p["requisitos"]}
        for k in ("navegacao", "instrumentos", "noturno"):
            self.assertTrue(por[k]["fechou"], k)
        self.assertEqual(p["gargalo"], "total")
        self.assertFalse(p["gargalo_sem_ritmo"])
        self.assertEqual(p["rotulo_cheque"], por["total"]["rotulo"])
        self.assertEqual(por["total"]["falta"], 110.0)

    def test_sem_voo_nenhum_nao_inventa_data(self):
        p = self.com_conn(aviacao_lab.previsao_cheque, HOJE)
        self.assertTrue(p["sem_ritmo_total"])
        self.assertIsNone(p["data_cheque"])
        self.assertIsNone(p["custo"])

    def test_custo_so_com_valor_da_hora_digitado(self):
        self.voo("2026-10-05", "SSBL", "SSBL", 4.0, natureza="tgl")
        self.assertIsNone(self.com_conn(aviacao_lab.previsao_cheque, HOJE)["custo"])
        self.assertEqual(self.com_conn(aviacao_lab.salvar_valor_hora, 1050), 1050.0)
        p = self.com_conn(aviacao_lab.previsao_cheque, HOJE)
        self.assertEqual(p["horas_a_voar"], 146.0)
        self.assertEqual(p["custo"], 146.0 * 1050)
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_valor_hora, -5)
        self.assertIsNone(self.com_conn(aviacao_lab.salvar_valor_hora, ""))

    def test_visitante_nao_ve_o_custo(self):
        self.com_conn(aviacao_lab.salvar_valor_hora, 900)
        card = self.com_conn(aviacao_lab.card_previsao_cheque, HOJE)
        mascarado = cards.mascarar_cards([card])[0]["data"]
        self.assertNotIn("custo", mascarado)
        self.assertNotIn("valor_hora", mascarado)
        self.assertTrue(mascarado["oculto"])


class BancaTest(AviacaoLabBase):
    def test_pronto_so_com_tres_seguidos_acima_de_80_e_risco_abaixo_de_70(self):
        for a in (17, 18, 19):
            self.com_conn(aviacao_lab.registrar_simulado, "TV", a, HOJE)
        for a in (13, 14, 12):
            self.com_conn(aviacao_lab.registrar_simulado, "MET", a, HOJE)
        for a in (20, 16):
            self.com_conn(aviacao_lab.registrar_simulado, "REG", a, HOJE)
        b = self.com_conn(aviacao_lab.banca, HOJE)
        por = {c["sigla"]: c for c in b["cadernos"]}
        self.assertEqual(por["TV"]["ultimos"], [85, 90, 95])
        self.assertTrue(por["TV"]["pronto"])
        self.assertTrue(por["MET"]["risco"])
        self.assertEqual(por["MET"]["ultimo"], 60)
        self.assertFalse(por["REG"]["pronto"])  # so 2 simulados
        self.assertIsNone(por["NAV"]["ultimo"])
        self.assertEqual(b["foco"], "MET")  # o mais fraco que ja tem simulado
        self.assertEqual(b["questoes"], 20)

    def test_so_o_tempo_da_navegacao_esta_conferido(self):
        t = self.com_conn(aviacao_lab.banca)["cadernos"]
        por = {c["sigla"]: c for c in t}
        self.assertEqual(por["NAV"]["tempo_min"], 100)
        self.assertTrue(por["NAV"]["tempo_conferido"])
        self.assertIsNone(por["MET"]["tempo_min"])
        self.com_conn(aviacao_lab.salvar_tempo_banca, "MET", 90)
        met = next(c for c in self.com_conn(aviacao_lab.banca)["cadernos"] if c["sigla"] == "MET")
        self.assertEqual((met["tempo_min"], met["tempo_conferido"]), (90, False))
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_tempo_banca, "NAV", 50)

    def test_valida_caderno_e_acertos(self):
        for sigla, a in (("XXX", 10), ("REG", 21), ("REG", -1), ("REG", True), ("REG", "10")):
            with self.assertRaises(ValueError):
                self.com_conn(aviacao_lab.registrar_simulado, sigla, a, HOJE)
        i = self.com_conn(aviacao_lab.registrar_simulado, "REG", 14, HOJE)
        self.assertTrue(self.com_conn(aviacao_lab.apagar_simulado, i))
        self.assertFalse(self.com_conn(aviacao_lab.apagar_simulado, i))

    def test_revisao_vem_do_quiz_sem_marcar_nada_e_reagenda_pelo_leitner(self):
        import estudo_quiz

        conn = db.get_db()
        try:
            p = estudo_quiz.criar(conn, {"tema": "Meteorologia", "enunciado": "Nevoeiro de advecção se forma quando...",
                                         "alternativas": ["A1 x", "B2 x", "C3 x", "D4 x"], "correta": 1,
                                         "explicacao": "Ar úmido e quente sobre superfície fria."})
            estudo_quiz.responder(conn, p["id"], "A", HOJE - timedelta(days=1))  # errou -> volta HOJE
        finally:
            conn.close()
        b = self.com_conn(aviacao_lab.banca, HOJE)
        self.assertEqual(b["vencidas"], 1)
        self.assertEqual(b["revisao"][0]["sigla"], "MET")
        self.assertEqual(b["revisao"][0]["resposta"], "B2 x")
        self.assertEqual(self.com_conn(aviacao_lab.banca, HOJE)["vencidas"], 1)  # ler nao gasta a revisao
        r = self.com_conn(aviacao_lab.revisar, p["id"], False, HOJE)
        self.assertEqual((r["dias"], r["texto"]), (1, "Volta amanhã."))
        self.assertEqual(self.com_conn(aviacao_lab.banca, HOJE)["vencidas"], 0)
        r = self.com_conn(aviacao_lab.revisar, p["id"], True, HOJE + timedelta(days=1))
        self.assertEqual(r["dias"], 3)
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.revisar, 9999, True, HOJE)


class ChairFlyingTest(AviacaoLabBase):
    def test_roteiro_padrao_so_manda_falar_e_o_proprio_substitui(self):
        passos, proprio = self.com_conn(aviacao_lab.roteiro)
        self.assertFalse(proprio)
        self.assertEqual(len(passos), 4)
        for p in passos:  # nada de procedimento de aviao afirmado: sao so perguntas/ganchos
            self.assertTrue(p["texto"].startswith(("Fala", "Faz")))
        n = self.com_conn(aviacao_lab.salvar_roteiro, [{"titulo": "Partida", "texto": "Meu flow de partida do manual."}])
        self.assertEqual(n, 1)
        passos, proprio = self.com_conn(aviacao_lab.roteiro)
        self.assertTrue(proprio)
        self.assertEqual(passos[0]["titulo"], "Partida")
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_roteiro, [{"titulo": "", "texto": "x"}])
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.salvar_roteiro, "nao e lista")

    def test_onde_travou_vem_primeiro_na_proxima_vez(self):
        v = self.voo("2026-10-31", horas=None, hora="08:00")
        c = self.com_conn(aviacao_lab.chair_flying, HOJE)
        self.assertEqual(c["voo"]["id"], v)
        self.assertEqual(c["comeca_por"], [])
        self.assertEqual(c["chips"][-1], aviacao_lab.NADA_TRAVOU)
        self.com_conn(aviacao_lab.registrar_chair, v, ["Fonia" if False else "Saída do circuito", "Rolagem"], HOJE)
        c = self.com_conn(aviacao_lab.chair_flying, HOJE)
        self.assertEqual([p["titulo"] for p in c["passos"]][:2], ["Rolagem", "Saída do circuito"])
        self.assertEqual(c["comeca_por"], ["Rolagem", "Saída do circuito"])

    def test_registrar_valida_e_liso_nao_guarda_nada(self):
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.registrar_chair, None, ["Passo que não existe"], HOJE)
        with self.assertRaises(ValueError):
            self.com_conn(aviacao_lab.registrar_chair, None, "Rolagem", HOJE)
        self.com_conn(aviacao_lab.registrar_chair, None, [aviacao_lab.NADA_TRAVOU], HOJE)
        self.assertEqual(self.com_conn(aviacao_lab.chair_flying, HOJE)["comeca_por"], [])

    def test_chat_convida_na_vespera_depois_das_21h_uma_vez_so(self):
        self.voo("2026-10-31", horas=None, hora="08:00")
        self.assertEqual(self.com_conn(aviacao_lab.chair_da_vespera, datetime(2026, 10, 30, 20, 30)), [])
        saida = self.com_conn(aviacao_lab.chair_da_vespera, datetime(2026, 10, 30, 21, 15))
        self.assertEqual(len(saida), 1)
        self.assertEqual(saida[0][0], "chair_flying")
        self.assertEqual(self.com_conn(aviacao_lab.chair_da_vespera, datetime(2026, 10, 30, 21, 20)), [])


class VentoPistaTest(AviacaoLabBase):
    PISTA = {"cabeceiras": [18, 36], "decl_w": 20.6, "limite_kt": 10}

    def test_conta_com_e_sem_declinacao(self):
        c = aviacao_lab.calcular_vento(290, 12, self.PISTA)
        self.assertEqual((c["cabeceira"], c["proa"], c["traves"], c["tom"]), (36, 8, 9, "alerta"))
        errada = aviacao_lab.calcular_vento(290, 12, self.PISTA, corrigir=False)
        self.assertEqual((errada["proa"], errada["traves"]), (4, 11))
        self.assertEqual(errada["tom"], "perigo")

    def test_escolhe_a_cabeceira_com_mais_vento_de_proa(self):
        c = aviacao_lab.calcular_vento(160, 10, self.PISTA, corrigir=False)
        self.assertEqual(c["cabeceira"], 18)
        self.assertEqual(c["proa"], 9)

    def test_rajada_pesa_no_traves_e_vento_variavel_nao_tem_conta(self):
        c = aviacao_lab.calcular_vento(290, 8, self.PISTA, rajada=20)
        self.assertGreater(c["traves_rajada"], c["traves"])
        self.assertEqual(c["tom"], "perigo")
        self.assertTrue(aviacao_lab.calcular_vento(None, 5, self.PISTA)["variavel"])
        self.assertEqual(aviacao_lab.calcular_vento(0, 0, self.PISTA)["traves"], 0)

    def test_pista_padrao_de_ssbl_e_01_19(self):
        # o Alex confirmou as cabeceiras em 04/11/2026; o padrao antigo 18/36 estava errado
        self.assertEqual(aviacao_lab.PISTA_PADRAO["cabeceiras"], [1, 19])
        self.assertEqual(self.com_conn(aviacao_lab.pista_config)["cabeceiras"], [1, 19])

    def test_pista_comeca_nao_conferida_e_mexer_nos_numeros_tira_a_conferencia(self):
        pc = self.com_conn(aviacao_lab.pista_config)
        self.assertFalse(pc["conferido"])
        self.assertTrue(pc["padrao_de_terceiros"])
        pc = self.com_conn(aviacao_lab.salvar_pista, {"conferido": True})
        self.assertFalse(pc["conferido"] and pc["padrao_de_terceiros"])  # confirmou os padroes
        self.com_conn(aviacao_lab.salvar_pista, {"conferido": True, "cabeceiras": [17, 35], "decl_w": 20.0})
        self.assertTrue(self.com_conn(aviacao_lab.pista_config)["conferido"])
        pc = self.com_conn(aviacao_lab.salvar_pista, {"decl_w": 21.3})
        self.assertFalse(pc["conferido"])
        self.assertEqual(pc["cabeceiras"], [17, 35])
        for ruim in ({"cabeceiras": [18, 20]}, {"cabeceiras": [0, 18]}, {"decl_w": 99}, {"limite_kt": 0}, {"decl_w": True}):
            with self.assertRaises(ValueError):
                self.com_conn(aviacao_lab.salvar_pista, ruim)

    def test_card_usa_o_metar_injetado_e_aguenta_falta_de_rede(self):
        v = self.com_conn(aviacao_lab.vento_pista, "SSBL", lambda icao: _metar(290, 12))
        self.assertEqual(v["hora_z"], "1200Z")
        self.assertTrue(v["medido"])
        self.assertEqual((v["conta"]["cabeceira"], v["conta"]["traves"]), (1, 10))  # pista 01/19
        self.assertFalse(v["pista"]["conferido"])
        sem = self.com_conn(aviacao_lab.vento_pista, "SSBL", lambda icao: {})
        self.assertFalse(sem["medido"])
        self.assertIsNone(sem["conta"])

        def cai(_):
            raise RuntimeError("sem rede")

        self.assertFalse(self.com_conn(aviacao_lab.vento_pista, "SSBL", cai)["medido"])
        var = self.com_conn(aviacao_lab.vento_pista, "SSBL", lambda i: _metar(0, 4, variavel=True))
        self.assertIsNone(var["direcao"])
        self.assertTrue(var["variavel"])

    def test_linha_do_bom_dia_so_para_ssbl_com_vento_medido(self):
        linha = self.com_conn(aviacao_lab.linha_vento, "SSBL", {"direcao": 290, "velocidade_kt": 12, "rajada_kt": None, "variavel": False})
        # padrao 01/19 (o Alex confirmou 04/11/2026): 290 V a 12 kt = 310,6 M, melhor na 01
        self.assertEqual(linha, "Vento: través 10 kt na 01, teu limite é 10 (pista e declinação ainda não conferidas).")
        self.assertIsNone(self.com_conn(aviacao_lab.linha_vento, "SBNF", {"direcao": 290, "velocidade_kt": 12}))
        self.assertIsNone(self.com_conn(aviacao_lab.linha_vento, "SSBL", {"variavel": True, "velocidade_kt": 3}))
        self.assertIsNone(self.com_conn(aviacao_lab.linha_vento, "SSBL", None))
        self.com_conn(aviacao_lab.salvar_pista, {"conferido": True})
        self.assertNotIn("não conferidas", self.com_conn(aviacao_lab.linha_vento, "SSBL", {"direcao": 290, "velocidade_kt": 12}))


class PassaporteTest(AviacaoLabBase):
    def test_um_carimbo_por_aerodromo_com_a_data_do_primeiro_pouso(self):
        self.voo("2026-03-12", "SSBL", "SSBL", 1.0)
        self.voo("2026-04-02", "SSBL", "SBNF", 1.5, escalas="SBJV")
        self.voo("2026-05-19", "SSBL", "SBNF", 1.5)  # repete: nao vira carimbo novo
        self.voo("2026-06-01", "SSBL", "Floripa", 1.0)  # apelido -> SBFL
        self.voo("2026-06-05", "SSBL", "SSBL", 1.0, tipo="simulador")  # simulador nao conta
        self.voo("2026-12-01", "SSBL", "SBCT", None)  # agendado nao conta
        self.voo("2026-10-25", "SSBL", "Praia", 0.5)  # nao e ICAO: sem carimbo, mas as horas contam
        p = self.com_conn(aviacao_lab.passaporte, HOJE)
        icaos = [c["icao"] for c in p["carimbos"]]
        self.assertEqual(icaos, ["SSBL", "SBJV", "SBNF", "SBFL"])
        nf = next(c for c in p["carimbos"] if c["icao"] == "SBNF")
        self.assertEqual((nf["primeiro"], nf["voos"]), ("2026-04-02", 2))
        self.assertEqual(p["horas"], 5.5)
        self.assertEqual(p["voos"], 5)
        self.assertTrue(all(not c["novo"] for c in p["carimbos"]))

    def test_carimbo_recente_vem_marcado_como_novo_e_aeronaves_contam(self):
        self.voo("2026-10-25", "SSBL", "SBNF", 1.0, aeronave="PT-ABC")
        self.voo("2026-10-26", "SSBL", "SBNF", 1.0, aeronave="pt-abc")
        self.voo("2026-10-27", "SSBL", "SBNF", 1.0, aeronave="PR-XYZ")
        p = self.com_conn(aviacao_lab.passaporte, HOJE)
        self.assertTrue(next(c for c in p["carimbos"] if c["icao"] == "SBNF")["novo"])
        self.assertEqual(p["aeronaves"], 2)

    def test_diario_vazio_nao_quebra(self):
        p = self.com_conn(aviacao_lab.passaporte, HOJE)
        self.assertEqual((p["carimbos"], p["horas"], p["aeronaves"]), ([], 0.0, 0))


class RotasTest(AviacaoLabBase):
    def test_get_de_cada_card_devolve_o_card_pronto(self):
        with patch.object(aviacao_lab, "_metar_cache", lambda icao: _metar(290, 12)):
            for qual, tipo in (("radar", "radar_validades"), ("cheque", "previsao_cheque"), ("banca", "banca"),
                               ("chair", "chair_flying"), ("vento", "vento_pista"), ("passaporte", "passaporte")):
                r = self.client.get(f"/api/aviacao/card/{qual}")
                self.assertEqual(r.status_code, 200, qual)
                card = r.get_json()["card"]
                self.assertEqual(card["type"], tipo)
                self.assertIn(tipo, cards.TIPOS_CARD)
        self.assertEqual(self.client.get("/api/aviacao/card/outro").status_code, 404)

    def test_card_vento_pela_rota_busca_o_icao_e_nao_a_data(self):
        pedidos = []
        with patch.object(aviacao_lab, "_metar_cache", lambda icao: pedidos.append(icao) or _metar(290, 12)):
            self.assertEqual(self.client.get("/api/aviacao/card/vento").status_code, 200)
        self.assertTrue(pedidos)
        self.assertTrue(all(isinstance(i, str) and len(i) == 4 for i in pedidos), pedidos)

    def test_prazos_civ_valor_da_hora_banca_chair_e_pista(self):
        r = self.client.post("/api/aviacao/prazos", json={"chave": "cma", "data": "2027-03-17"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["card"]["campos"][0]["valor"], "2027-03-17")
        self.assertEqual(self.client.post("/api/aviacao/prazos", json={"chave": "x", "data": "2027-03-17"}).status_code, 400)

        hoje = date.today()
        v = self.voo((hoje - timedelta(days=1)).isoformat(), horas=1.0)
        r = self.client.post(f"/api/voos/{v}/civ", json={"confirmada": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.sql("SELECT civ_confirmada FROM voos WHERE id = ?", (v,))[0][0], 1)
        self.assertEqual(self.client.post("/api/voos/9999/civ", json={}).status_code, 400)

        self.assertEqual(self.client.post("/api/aviacao/valor-hora", json={"valor": 1050}).get_json()["card"]["valor_hora"], 1050.0)
        self.assertEqual(self.client.post("/api/aviacao/valor-hora", json={"valor": "abc"}).status_code, 400)

        r = self.client.post("/api/aviacao/banca/simulado", json={"caderno": "MET", "acertos": 12})
        self.assertEqual(r.status_code, 200)
        sid = r.get_json()["simulado_id"]
        self.assertEqual(self.client.post("/api/aviacao/banca/simulado", json={"caderno": "MET", "acertos": 99}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/aviacao/banca/simulado/{sid}/apagar", json={}).status_code, 200)
        self.assertEqual(self.client.post("/api/aviacao/banca/tempo", json={"caderno": "TV", "minutos": 45}).status_code, 200)
        self.assertEqual(self.client.post("/api/aviacao/banca/tempo", json={"caderno": "NAV", "minutos": 45}).status_code, 400)
        self.assertEqual(self.client.post("/api/aviacao/banca/revisao", json={"id": "x"}).status_code, 400)

        r = self.client.post("/api/aviacao/chair", json={"voo_id": None, "travou": ["Rolagem"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/api/aviacao/chair", json={"travou": ["Inexistente"]}).status_code, 400)
        r = self.client.post("/api/aviacao/chair/roteiro", json={"passos": [{"titulo": "A", "texto": "falar a"}]})
        self.assertEqual(r.get_json()["passos"], 1)

        with patch.object(aviacao_lab, "_metar_cache", lambda icao: _metar()):
            r = self.client.post("/api/aviacao/pista", json={"conferido": True})
        self.assertTrue(r.get_json()["card"]["pista"]["conferido"] or r.get_json()["card"]["pista"]["padrao_de_terceiros"])
        self.assertEqual(self.client.post("/api/aviacao/pista", json={"decl_w": 500}).status_code, 400)

    def test_login_global_vale_pras_rotas_novas(self):
        puro = app_novo_client()
        self.assertEqual(puro.get("/api/aviacao/card/radar").status_code, 401)
        self.assertEqual(puro.post("/api/aviacao/prazos", json={"chave": "cma", "data": "2027-01-01"}).status_code, 401)


def app_novo_client():
    import app

    return app.app.test_client()


class IntegracaoProativaTest(AviacaoLabBase):
    def test_manha_do_voo_ganha_a_linha_do_vento_sem_rede_nova(self):
        self.voo("2026-10-30", "SSBL", "SSBL", horas=None, hora="09:00")
        briefing = {"icao": "SSBL", "nome": "Blumenau", "categoria": "VFR", "observado": "08h", "idade_min": 5,
                    "vento": {"direcao": 290, "velocidade_kt": 12, "rajada_kt": None, "variavel": False},
                    "taf": [], "nuvens": [], "fenomenos": []}
        conn = db.get_db()
        try:
            conversa_proativa.manha_do_voo(conn, datetime(2026, 10, 30, 7, 0), lambda c, i: briefing)
            conn.commit()
            texto = conn.execute("SELECT texto FROM chat_mensagens ORDER BY id DESC LIMIT 1").fetchone()["texto"]
        finally:
            conn.close()
        self.assertIn("Vento: través 10 kt na 01, teu limite é 10", texto)

    def test_verificar_roda_as_automacoes_novas_sem_derrubar_nada(self):
        conn = db.get_db()
        try:
            self.assertIsInstance(conversa_proativa.verificar(conn, datetime(2026, 10, 30, 10, 0)), list)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
