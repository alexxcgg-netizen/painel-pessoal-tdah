"""Grupo G do lab v4 (2026-10-30): Medalha na hora, Placar do feito, Pouso do dia e Retrospectiva do
mes. Banco temporario (a base `_Base` do teste de assistente), IA dublada, nenhuma rede."""
import unittest
from datetime import date, datetime, timedelta

from tests.test_assistente_vida import _Base

import cards
import db
import fechamento_dia
import medalha
import retrospectiva
import treino_vivo

HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)
AMANHA = HOJE + timedelta(days=1)
PEITO = "Supino reto|4|10|20 kg\nCrucifixo|3|12|\nTriceps corda|4|8-12|15 kg"


def _tarefa(conn, titulo, due=None, hora=None, feita_em=None):
    cur = conn.execute("INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)",
                       (titulo, due.isoformat() if due else None, hora, feita_em))
    conn.commit()
    return cur.lastrowid


def _feita_em(dia: date) -> str:
    return f"{dia.isoformat()} 15:00:00"  # UTC: meio-dia de Brasilia


class EpleyTestCase(unittest.TestCase):
    def test_formula_e_reps(self):
        self.assertEqual(treino_vivo.rm_epley(72.5, 8), 91.8)  # a conta da demo
        self.assertEqual(treino_vivo.rm_epley(20, 10), 26.7)
        self.assertEqual(treino_vivo.rm_epley(100, 1), 103.3)
        self.assertEqual(treino_vivo.reps_da_serie("8-12"), 8)
        self.assertEqual(treino_vivo.reps_da_serie("10"), 10)
        self.assertIsNone(treino_vivo.reps_da_serie(""))
        self.assertIsNone(treino_vivo.reps_da_serie("falha"))
        self.assertEqual(treino_vivo.series_da_ficha("4"), 4)
        self.assertIsNone(treino_vivo.series_da_ficha("0"))

    def test_legenda_mostra_a_conta(self):
        m = {"carga": 72.5, "reps": 8, "rm": 91.8, "ganho": 3.0}
        self.assertEqual(medalha.legenda(m), "+3 kg no 1RM estimado. 72,5 × (1 + 8/30) = 91,8.")
        self.assertEqual(medalha.legenda({**m, "ganho": None}), "72,5 × (1 + 8/30) = 91,8.")


class MedalhaTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios": PEITO})
        conn = db.get_db()
        self.ficha = db.list_fichas_treino(conn)[0]["id"]
        conn.close()

    def _sessao(self, dia):
        conn = db.get_db()
        try:
            return db.abrir_sessao_treino(conn, self.ficha, dia.isoformat())
        finally:
            conn.close()

    def _marcar(self, sid, i, feito=True):
        r = self.client.post(f"/api/treino/sessoes/{sid}/exercicio", json={"i": i, "feito": feito})
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def _carga(self, supino_kg):
        self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios":
                         PEITO.replace("Supino reto|4|10|20 kg", f"Supino reto|4|10|{supino_kg} kg")})

    def test_primeira_marca_e_base_sem_medalha(self):
        sid = self._sessao(ONTEM)
        r = self._marcar(sid, 0)
        self.assertIsNone(r["medalha"])
        marca = self.sql("SELECT rm_est, recorde, volume_kg FROM treino_marcas")[0]
        self.assertEqual((marca["rm_est"], marca["recorde"], marca["volume_kg"]), (26.7, 0, 800.0))

    def test_carga_maior_depois_ganha_medalha_e_fica_gravada(self):
        self._marcar(self._sessao(ONTEM), 0)
        self._carga(25)
        sid = self._sessao(HOJE)
        r = self._marcar(sid, 0)
        m = r["medalha"]
        self.assertEqual((m["i"], m["nome"], m["rm"], m["anterior"], m["ganho"]), (0, "Supino reto", 33.3, 26.7, 6.6))
        self.assertEqual(m["legenda"], "+6,6 kg no 1RM estimado. 25 × (1 + 10/30) = 33,3.")
        # fica gravada: o card do historico volta com a medalha
        conn = db.get_db()
        try:
            card = cards.card_treino_agora(conn, sid)
        finally:
            conn.close()
        self.assertEqual([x["i"] for x in card["data"]["medalhas"]], [0])

    def test_empate_e_carga_menor_nao_ganham(self):
        self._marcar(self._sessao(ONTEM), 0)
        self.assertIsNone(self._marcar(self._sessao(HOJE), 0)["medalha"])  # mesma carga, mesmas reps
        self._carga(15)
        self.assertIsNone(self._marcar(self._sessao(HOJE + timedelta(days=1)), 0)["medalha"])

    def test_desmarcar_apaga_e_marcar_de_novo_reavalia(self):
        self._marcar(self._sessao(ONTEM), 0)
        self._carga(25)
        sid = self._sessao(HOJE)
        self.assertIsNotNone(self._marcar(sid, 0)["medalha"])
        self.assertIsNone(self._marcar(sid, 0, False)["medalha"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM treino_marcas WHERE sessao_id = ?", (sid,))[0][0], 0)
        self.assertIsNotNone(self._marcar(sid, 0)["medalha"])  # a medalha volta

    def test_historico_de_carga_da_ficha_vira_base_na_primeira_marca(self):
        # a ficha ja teve 20 kg antes de hoje (treino_cargas) e agora esta em 25: bater 20 x 10 = 26,7
        self.sql("INSERT INTO treino_cargas (ficha_id, exercicio, nome, carga, carga_num, data) VALUES (?, ?, ?, ?, ?, ?)",
                 (self.ficha, "supino reto", "Supino reto", "20 kg", 20.0, ONTEM.isoformat()))
        self._carga(25)
        m = self._marcar(self._sessao(HOJE), 0)["medalha"]
        self.assertEqual((m["anterior"], m["rm"]), (26.7, 33.3))

    def test_sem_kg_sem_reps_ou_reps_demais_nao_entram(self):
        sid = self._sessao(HOJE)
        self.assertIsNone(self._marcar(sid, 1)["medalha"])  # crucifixo sem carga
        self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios": "Supino|4|20|40 kg\nPuxada|3||30 kg\nLeg|3|10|3 placas"})
        for i in range(3):
            self.assertIsNone(self._marcar(sid, i)["medalha"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM treino_marcas")[0][0], 0)

    def test_faixa_de_reps_vale_o_piso(self):
        sid = self._sessao(HOJE)
        self._marcar(sid, 2)  # triceps 15 kg x "8-12"
        self.assertEqual(self.sql("SELECT reps, rm_est FROM treino_marcas")[0]["reps"], 8)


class PlacarTestCase(_Base):
    def test_junta_tarefa_treino_voo_e_extra(self):
        conn = db.get_db()
        _tarefa(conn, "Pagou a Enel", feita_em=_feita_em(HOJE))
        _tarefa(conn, "Feita ontem", feita_em=_feita_em(ONTEM))
        _tarefa(conn, "Aberta", due=HOJE)
        db.registrar_treino(conn, HOJE.isoformat(), "Peito", None, None)
        conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES (?, 'SSBL', 'SBNF', 1.2)", (HOJE.isoformat(),))
        conn.commit()
        fechamento_dia.adicionar_extra(conn, "  lavei a louça. ", HOJE)
        itens = fechamento_dia.feitos_do_dia(conn, HOJE)
        conn.close()
        self.assertEqual([(i["texto"], i["rotulo"]) for i in itens], [
            ("Pagou a Enel", "planejado"), ("Treino de Peito", "planejado"),
            ("Voo SSBL → SBNF", "planejado"), ("Lavei a louça", "fora do plano")])

    def test_extra_idempotente_vazio_e_limite(self):
        conn = db.get_db()
        a = fechamento_dia.adicionar_extra(conn, "Lavei a louça", HOJE)
        b = fechamento_dia.adicionar_extra(conn, "LAVEI A LOUÇA", HOJE)
        self.assertEqual((a["novo"], b["novo"], a["id"] == b["id"]), (True, False, True))
        self.assertIsNone(fechamento_dia.adicionar_extra(conn, "   ", HOJE))
        longo = fechamento_dia.adicionar_extra(conn, "x" * 500, HOJE)
        self.assertEqual(len(longo["texto"]), fechamento_dia.MAX_TEXTO_EXTRA)
        self.assertTrue(fechamento_dia.remover_extra(conn, a["id"]))
        self.assertFalse(fechamento_dia.remover_extra(conn, a["id"]))
        conn.close()

    def test_sugestoes_usam_o_que_ele_mais_anota(self):
        conn = db.get_db()
        for d in (3, 4, 5):
            fechamento_dia.adicionar_extra(conn, "Liguei pro banco", HOJE - timedelta(days=d))
        sug = fechamento_dia.sugestoes_extra(conn, HOJE)
        self.assertEqual(sug[0], "Liguei pro banco")
        self.assertEqual(len(sug), 4)
        fechamento_dia.adicionar_extra(conn, "liguei pro banco", HOJE)
        self.assertNotIn("Liguei pro banco", fechamento_dia.sugestoes_extra(conn, HOJE))
        conn.close()

    def test_rotas(self):
        r = self.client.post("/api/feito-hoje", json={"texto": "Arrumei a mochila"})
        self.assertEqual(r.status_code, 201)
        corpo = r.get_json()
        self.assertEqual((corpo["total"], corpo["item"]["rotulo"]), (1, "fora do plano"))
        self.assertEqual(self.client.post("/api/feito-hoje", json={"texto": "arrumei a mochila"}).status_code, 200)
        self.assertEqual(self.client.post("/api/feito-hoje", json={"texto": " "}).status_code, 400)
        self.assertEqual(self.client.post("/api/feito-hoje", json={"texto": "x", "dia": "lixo"}).status_code, 400)
        self.assertEqual(self.client.post("/api/feito-hoje", json={"texto": "x", "dia": "2020-01-01"}).status_code, 400)
        self.assertEqual(self.client.get("/api/feito-hoje").get_json()["total"], 1)
        self.assertEqual(self.client.delete(f"/api/feito-hoje/{corpo['item']['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/feito-hoje/{corpo['item']['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/feito-hoje").get_json()["total"], 0)

    def test_exige_login(self):
        anonimo = __import__("app").app.test_client()
        self.assertEqual(anonimo.get("/api/feito-hoje").status_code, 401)
        self.assertEqual(anonimo.post("/api/feito-hoje", json={"texto": "x"}).status_code, 401)
        self.assertEqual(anonimo.get("/api/retrospectiva/2026-10").status_code, 401)

    def test_chat_tool_anota_e_devolve_o_card(self):
        corpo, res = self.chat([("feito_hoje", {"anotar": ["lavei a louça", "Liguei pro banco"]})])
        self.assertEqual(res[0]["anotados"], ["Lavei a louça", "Liguei pro banco"])
        card = next(c for c in corpo["cards"] if c["type"] == "placar_feito")
        self.assertEqual(card["data"]["total"], 2)

    def test_historico_do_chat_traz_o_placar_de_agora(self):
        self.chat([("feito_hoje", {})])
        self.client.post("/api/feito-hoje", json={"texto": "Anotei depois"})
        hist = self.client.get("/api/chat/historico").get_json()
        card = next(c for m in hist for c in m["cards"] if c["type"] == "placar_feito")
        self.assertEqual(card["data"]["total"], 1)


class PousoTestCase(_Base):
    def test_dia_vazio_nao_gera_nada(self):
        conn = db.get_db()
        self.assertIsNone(fechamento_dia.pouso_do_dia(conn, HOJE))
        conn.close()

    def test_placar_vem_antes_e_o_pouso_traz_so_os_passos_que_existem(self):
        conn = db.get_db()
        _tarefa(conn, "Feita", feita_em=_feita_em(HOJE))
        _tarefa(conn, "Ligar pro dentista", due=HOJE)
        _tarefa(conn, "Separar a CIV", due=AMANHA, hora="07:10")
        texto, lista = fechamento_dia.pouso_do_dia(conn, HOJE, "21:00")
        conn.close()
        self.assertEqual([c["type"] for c in lista], ["placar_feito", "pouso_dia"])
        self.assertIn("1 coisa hoje", texto)
        self.assertIn("1 em aberto", texto)
        d = lista[1]["data"]
        self.assertEqual([p["titulo"] for p in d["pendentes"]], ["Ligar pro dentista"])
        self.assertEqual(d["primeira"], {"texto": "Separar a CIV", "hora": "07:10", "tipo": "tarefa"})
        self.assertIsNone(d["mochila"])  # sem voo amanha, sem passo da mochila
        self.assertFalse(d["pousado"])

    def test_dia_limpo_fala_que_pode_desligar(self):
        conn = db.get_db()
        _tarefa(conn, "Feita", feita_em=_feita_em(HOJE))
        texto, lista = fechamento_dia.pouso_do_dia(conn, HOJE)
        conn.close()
        self.assertIn("Nada pendurado", texto)
        self.assertEqual(lista[1]["data"]["ids_adiar"], [])

    def test_primeira_de_amanha_pega_o_horario_mais_cedo_entre_voo_e_tarefa(self):
        conn = db.get_db()
        _tarefa(conn, "Reunião", due=AMANHA, hora="09:00")
        conn.execute("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SBNF', '08:00')", (AMANHA.isoformat(),))
        conn.commit()
        p = fechamento_dia.primeira_de_amanha(conn, HOJE)
        self.assertEqual((p["texto"], p["hora"], p["tipo"]), ("Voo SSBL → SBNF", "08:00", "voo"))
        m = fechamento_dia.mochila_de_amanha(conn, HOJE)
        self.assertEqual(len(m["itens"]), len(cards.MOCHILA_VOO))
        self.assertFalse(any(i["feito"] for i in m["itens"]))
        conn.close()

    def test_sem_horario_vale_a_primeira_tarefa_e_amanha_vazio_e_none(self):
        conn = db.get_db()
        self.assertIsNone(fechamento_dia.primeira_de_amanha(conn, HOJE))
        _tarefa(conn, "Sem hora", due=AMANHA)
        self.assertEqual(fechamento_dia.primeira_de_amanha(conn, HOJE), {"texto": "Sem hora", "hora": None, "tipo": "tarefa"})
        conn.close()

    def test_empurrar_muda_a_primeira_de_amanha_e_pousar_grava(self):
        conn = db.get_db()
        id_ = _tarefa(conn, "Atrasada de hoje", due=HOJE, hora="06:30")
        conn.close()
        self.assertIsNone(self.client.get("/api/pouso-dia/amanha").get_json()["primeira"])
        self.assertEqual(self.client.post("/api/tarefas/adiar", json={"ids": [id_]}).status_code, 200)
        self.assertEqual(self.client.get("/api/pouso-dia/amanha").get_json()["primeira"]["texto"], "Atrasada de hoje")
        self.assertEqual(self.client.post("/api/pouso-dia/pousar", json={"dia": "lixo"}).status_code, 400)
        self.assertEqual(self.client.post("/api/pouso-dia/pousar", json={}).status_code, 200)
        conn = db.get_db()
        self.assertTrue(fechamento_dia.ja_pousou(conn, app_hoje()))
        conn.close()

    def test_historico_volta_com_o_que_ainda_esta_aberto(self):
        conn = db.get_db()
        id_ = _tarefa(conn, "Ficou", due=app_hoje())
        conn.close()
        self.chat([("pouso_do_dia", {})])
        self.client.post("/api/tarefas/adiar", json={"ids": [id_]})
        hist = self.client.get("/api/chat/historico").get_json()
        card = next(c for m in hist for c in m["cards"] if c["type"] == "pouso_dia")
        self.assertEqual(card["data"]["ids_adiar"], [])


def app_hoje():
    import app
    return app._agora_brasilia().date()


class VerificarTestCase(_Base):
    def test_21h_publica_placar_e_pouso_uma_vez_so(self):
        import conversa_proativa as cp
        conn = db.get_db()
        _tarefa(conn, "Pendente", due=HOJE)
        agora = datetime.combine(HOJE, datetime.min.time()).replace(hour=21, minute=3)
        saida = cp.verificar(conn, agora)
        self.assertEqual(saida[0][0], "fechamento_noturno")
        self.assertIn("1 em aberto", saida[0][2])
        tipos = [c["type"] for m in db.list_chat_mensagens(conn) for c in db.cards_de_mensagem_chat(m)]
        self.assertIn("placar_feito", tipos[:2])
        self.assertIn("pouso_dia", tipos[:2])
        self.assertEqual(cp.verificar(conn, agora.replace(minute=8)), [])
        conn.close()


class RetrospectivaTestCase(_Base):
    def _mes_passado(self):
        return retrospectiva.mes_anterior(HOJE.year, HOJE.month)

    def _dado(self, conn, dia, tarefas=0, kg=0, voo_h=0.0, destino=None, categoria=None, valor=0.0, recorde=None):
        for i in range(tarefas):
            _tarefa(conn, f"t{dia}{i}", feita_em=_feita_em(dia))
        if kg:
            conn.execute(
                "INSERT INTO treino_marcas (sessao_id, idx, ficha_id, exercicio, nome, data, carga_kg, series, reps, volume_kg, rm_est, recorde) "
                "VALUES (?, ?, 1, 'supino', 'Supino', ?, 20, 4, 10, ?, ?, ?)",
                (abs(hash((dia, kg))) % 100000, 0, dia.isoformat(), kg, recorde or 26.7, 1 if recorde else 0))
        if voo_h:
            conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES (?, 'SSBL', ?, ?)", (dia.isoformat(), destino or "SBNF", voo_h))
        if categoria:
            conn.execute("INSERT INTO expenses (amount, category, created_at, tipo) VALUES (?, ?, ?, 'real')", (valor, categoria, f"{dia.isoformat()} 12:00:00"))
        conn.commit()

    def test_mes_sem_nada_nao_tem_retrospectiva(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self.assertIsNone(retrospectiva.dados(conn, a, m))
        conn.close()

    def test_numeros_do_mes_so_com_dado_de_verdade(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        a2, m2 = retrospectiva.mes_anterior(a, m)
        d1, d0 = date(a, m, 10), date(a2, m2, 10)
        self._dado(conn, d1, tarefas=3, kg=800, voo_h=1.5, destino="SBNF", categoria="delivery", valor=200, recorde=33.3)
        self._dado(conn, d0, tarefas=1, voo_h=1.0, destino="SSBL", categoria="delivery", valor=50)
        d = retrospectiva.dados(conn, a, m, HOJE)
        conn.close()
        self.assertEqual((d["tarefas"], d["tarefas_ant"]), (3, 1))
        self.assertEqual((d["kg"], d["treinos"]), (800, 1))
        self.assertEqual((d["voo_horas"], d["voos"], d["aerodromos_novos"]), (1.5, 1, 1))  # SBNF e novo, SSBL ja existia
        self.assertEqual(d["recorde"]["rm"], 33.3)
        self.assertEqual(d["gasto_cresceu"], {"categoria": "delivery", "mais": 150, "total": 200})
        self.assertEqual(d["proximo_mes"], retrospectiva.chave_mes(*retrospectiva.mes_seguinte(a, m)))
        self.assertLessEqual(len(d["metas"]), 3)
        self.assertIn("Dormir 7 h+", d["metas"] + ["Dormir 7 h+"])

    def test_gasto_pequeno_nao_vira_destaque_e_visitante_nao_ve_dinheiro(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self._dado(conn, date(a, m, 5), tarefas=1, categoria="mercado", valor=20)
        d = retrospectiva.dados(conn, a, m, HOJE)
        conn.close()
        self.assertIsNone(d["gasto_cresceu"])
        c = cards.novo_card("retrospectiva", {**d, "gasto_cresceu": {"categoria": "x", "mais": 99, "total": 99}})
        mascarado = cards.mascarar_cards([c])[0]["data"]
        self.assertNotIn("gasto_cresceu", mascarado)
        self.assertTrue(mascarado["oculto"])

    def test_escolher_meta_grava_pro_mes_seguinte(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self.assertEqual(retrospectiva.escolher_meta(conn, a, m, "  Voar 8 h "), "Voar 8 h")
        self.assertEqual(retrospectiva.meta_do_mes(conn, *retrospectiva.mes_seguinte(a, m)), "Voar 8 h")
        self.assertIsNone(retrospectiva.escolher_meta(conn, a, m, "   "))
        conn.close()

    def test_rotas(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self._dado(conn, date(a, m, 10), tarefas=2)
        conn.close()
        chave = retrospectiva.chave_mes(a, m)
        self.assertEqual(self.client.get(f"/api/retrospectiva/{chave}").get_json()["tarefas"], 2)
        self.assertEqual(self.client.get("/api/retrospectiva/lixo").status_code, 400)
        self.assertEqual(self.client.get("/api/retrospectiva/2001-01").status_code, 404)
        r = self.client.post(f"/api/retrospectiva/{chave}/meta", json={"meta": "Zerar atrasados"})
        self.assertEqual(r.get_json()["meta"], "Zerar atrasados")
        self.assertEqual(self.client.post(f"/api/retrospectiva/{chave}/meta", json={}).status_code, 400)
        self.assertEqual(self.client.get(f"/api/retrospectiva/{chave}").get_json()["meta_escolhida"], "Zerar atrasados")

    def test_aviso_no_dia_1_uma_vez_so_e_so_com_dado(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        dia1 = datetime(HOJE.year, HOJE.month, 1, 10, 0)
        self.assertEqual(retrospectiva.avisar_mes(conn, dia1), [])  # nada pra contar: nao publica
        self._dado(conn, date(a, m, 10), tarefas=4)
        conn2 = db.get_db()
        self.assertEqual(retrospectiva.avisar_mes(conn2, dia1), [])  # ja avaliou este mes (marcado)
        conn2.close()
        conn.execute("DELETE FROM notificacoes_enviadas WHERE tipo = 'retrospectiva_chat'")
        conn.commit()
        saida = retrospectiva.avisar_mes(conn, dia1)
        self.assertEqual(saida[0][0], "padroes_semana")
        self.assertIn("4 tarefas fechadas", saida[0][2])
        tipos = [c["type"] for msg in db.list_chat_mensagens(conn) for c in db.cards_de_mensagem_chat(msg)]
        self.assertEqual(tipos, ["retrospectiva"])
        self.assertEqual(retrospectiva.avisar_mes(conn, dia1), [])
        conn.close()

    def test_janela_do_dia_1(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self._dado(conn, date(a, m, 10), tarefas=1)
        self.assertEqual(retrospectiva.avisar_mes(conn, datetime(HOJE.year, HOJE.month, 1, 7, 0)), [])
        self.assertEqual(retrospectiva.avisar_mes(conn, datetime(HOJE.year, HOJE.month, 15, 10, 0)), [])
        conn.close()
        self.assertTrue(retrospectiva._na_janela(datetime(2026, 11, 3, 8, 0)))  # PC desligado no dia 1
        self.assertFalse(retrospectiva._na_janela(datetime(2026, 11, 4, 8, 0)))

    def test_chat_tool_devolve_o_card_ou_explica(self):
        conn = db.get_db()
        a, m = self._mes_passado()
        self._dado(conn, date(a, m, 10), tarefas=2)
        conn.close()
        corpo, res = self.chat([("retrospectiva_mes", {"mes": retrospectiva.chave_mes(a, m)})])
        self.assertEqual(next(c for c in corpo["cards"] if c["type"] == "retrospectiva")["data"]["tarefas"], 2)
        _, res = self.chat([("retrospectiva_mes", {"mes": "2001-01"})])
        self.assertIn("erro", res[0])
        _, res = self.chat([("retrospectiva_mes", {"mes": "lixo"})])
        self.assertIn("erro", res[0])

    def test_mes_padrao(self):
        self.assertEqual(retrospectiva.mes_padrao(date(2026, 10, 30)), (2026, 10))
        self.assertEqual(retrospectiva.mes_padrao(date(2026, 11, 3)), (2026, 10))
        self.assertEqual(retrospectiva.mes_padrao(date(2027, 1, 5)), (2026, 12))


if __name__ == "__main__":
    unittest.main()
