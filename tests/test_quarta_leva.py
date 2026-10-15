"""4a leva: automacoes (2026-10-15, docs/briefings/2026-10-15-4a-leva.md).

- vespera do voo (so quando tem voo com hora) e manha do voo com METAR;
- despertador pro Atalho (/api/atalho/despertador);
- aeroclube pela localizacao (/api/atalho/local lugar=aeroclube);
- compras que se repetem (compras_previstas / adiar);
- assinatura que subiu no chat; documentos 60/30/7; projecao das horas; mochila do voo.
Banco temporario, login real, Maps desligado, METAR dublado - nada de rede."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import conversa_proativa  # noqa: E402
import criptografia  # noqa: E402
import vida  # noqa: E402

PIN = "246810"
HOJE = date.today()
BASE = date(2030, 3, 11)  # data fixa pras contas que nao dependem do relogio


class _ComBanco(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        # o que ele usa de verdade (docs/CARDS.md): chegar 45 min antes, se arrumar 45 min
        db.definir_configuracao(conn, "voo_briefing_min", "45")
        db.definir_configuracao(conn, "tempo_se_arrumar_min", "45")
        conn.commit()
        conn.close()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": "", "PAINEL_ATALHOS_TOKEN": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None)):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            linhas = conn.execute(query, params).fetchall()
            conn.commit()
            return linhas
        finally:
            conn.close()

    def voo(self, data, hora, destino="SSBL", horas=None, tipo=None):
        return self.sql("INSERT INTO voos (data, origem, destino, hora, horas, tipo) VALUES (?, 'SSBL', ?, ?, ?, ?) "
                        "RETURNING id", (str(data), destino, hora, horas, tipo))[0][0]

    def com_conn(self, fn, *args, **kw):
        conn = db.get_db()
        try:
            return fn(conn, *args, **kw)
        finally:
            conn.close()

    def mensagens(self):
        saida = []
        for r in self.sql("SELECT texto, cards_json FROM chat_mensagens WHERE papel = 'assistant' ORDER BY id"):
            cartas = json.loads(criptografia.descriptografar(r["cards_json"])) if r["cards_json"] else []
            saida.append((r["texto"], cartas))
        return saida

    def visitante(self):
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = __import__("time").time()


# ------------------------------------------------------------------ 1. vespera / manha
class VesperaDoVooTestCase(_ComBanco):
    def test_vespera_so_com_voo_com_hora_na_janela_e_uma_vez(self):
        amanha = BASE + timedelta(days=1)
        vid = self.voo(amanha, "08:00")
        self.voo(amanha, None)  # sem hora: fica com o push antigo
        self.voo(amanha, "10:00", tipo="simulador")
        noite = datetime.combine(BASE, time(20, 0))
        self.assertEqual(self.com_conn(conversa_proativa.vespera_do_voo, noite - timedelta(minutes=1)), [])
        saida = self.com_conn(conversa_proativa.vespera_do_voo, noite)
        self.assertEqual(saida, [("vespera_voo", "Amanhã tem voo", "Acorda 06:15, sai 07:00. Previsão e mochila no chat.")])
        self.assertEqual(self.com_conn(conversa_proativa.vespera_do_voo, noite + timedelta(hours=1)), [])
        (texto, [card]), = self.mensagens()
        self.assertTrue(texto.startswith("Amanhã tem voo às 08:00. Acorda 06:15 e sai 07:00"))
        d = card["data"]
        self.assertEqual(card["type"], "vespera_voo")
        self.assertEqual((d["id"], d["acordar"], d["sair"], d["chegar"], d["icao"], d["rota"]), (vid, "06:15", "07:00", "07:15", "SSBL", None))
        self.assertEqual([m["texto"] for m in d["mochila"]], list(cards.MOCHILA_VOO))
        self.assertEqual(d["mochila"][0]["texto"], "CIV e CMA")

    def test_dia_sem_voo_nao_fala_nada(self):
        self.assertEqual(self.com_conn(conversa_proativa.vespera_do_voo, datetime.combine(BASE, time(21, 0))), [])
        self.assertEqual(self.mensagens(), [])

    def test_maps_quando_configurado_entra_na_saida(self):
        vid = self.voo(BASE + timedelta(days=1), "08:00")
        with patch("app._saida_pro_voo", return_value={"sair": "06:40", "trajeto_min": 25}):
            self.com_conn(conversa_proativa.vespera_do_voo, datetime.combine(BASE, time(20, 30)))
        d = self.mensagens()[0][1][0]["data"]
        self.assertEqual((d["id"], d["sair"], d["acordar"], d["trajeto_min"]), (vid, "06:40", "05:55", 25))

    def test_manha_do_voo_metar_e_hora_de_sair(self):
        self.voo(BASE, "08:00")
        cedo = datetime.combine(BASE, time(6, 29))
        pedidos = []

        def briefing(conn, icao):
            pedidos.append(icao)
            return {"icao": icao}

        card = {"type": "briefing_voo", "data": {"icao": "SBNF", "observado": "06:00", "categoria": "VFR"}}
        with patch("cards.card_briefing_voo", return_value=card):
            self.assertEqual(self.com_conn(conversa_proativa.manha_do_voo, cedo, briefing), [])
            saida = self.com_conn(conversa_proativa.manha_do_voo, cedo + timedelta(minutes=1), briefing)
            self.assertEqual(self.com_conn(conversa_proativa.manha_do_voo, cedo + timedelta(minutes=30), briefing), [])
        self.assertEqual(pedidos, ["SSBL"])
        self.assertEqual(saida, [("manha_voo", "Voo hoje", "Sai às 07:00. METAR de SBNF das 06:00: VFR.")])
        texto, cartas = self.mensagens()[0]
        self.assertEqual(texto, "Bom dia! Voo hoje às 08:00. Sai às 07:00 pra chegar 07:15. METAR de SBNF das 06:00: VFR.")
        self.assertEqual(cartas[0]["type"], "briefing_voo")

    def test_manha_sem_metar_avisa_e_nao_fala_depois_de_decolar(self):
        self.voo(BASE, "11:00")
        self.voo(BASE, "07:00")
        # 07:30: o das 11:00 ainda nao (comeca 1h30 antes de sair = 08:30); o das 07:00 ja decolou
        self.assertEqual(self.com_conn(conversa_proativa.manha_do_voo, datetime.combine(BASE, time(7, 30)), lambda c, i: {}), [])
        saida = self.com_conn(conversa_proativa.manha_do_voo, datetime.combine(BASE, time(8, 30)), lambda c, i: {"erro": "sem rede"})
        self.assertEqual(len(saida), 1)
        self.assertIn("Não consegui puxar o METAR", self.mensagens()[0][0])

    def test_push_antigo_fica_so_pro_voo_sem_hora(self):
        conn = db.get_db()
        try:
            amanha = HOJE + timedelta(days=1)
            conn.execute("INSERT INTO voos (data, destino, hora) VALUES (?, 'SBFL', '10:00')", (amanha.isoformat(),))
            conn.commit()
            noite = datetime.combine(HOJE, time(20, 0))
            self.assertNotIn("pre_voo", {t for t, *_ in app._avisos_fase2(conn, noite)})
        finally:
            conn.close()


# ------------------------------------------------------------------ 2. despertador
class DespertadorTestCase(_ComBanco):
    def get(self, quando, query=""):
        with patch("app._agora_brasilia", return_value=quando):
            return self.client.get(f"/api/atalho/despertador{query}")

    def test_primeiro_compromisso_de_amanha(self):
        self.voo(BASE + timedelta(days=1), "08:00")
        r = self.get(datetime.combine(BASE, time(22, 0))).get_json()
        self.assertEqual(r["tem"], True)
        self.assertEqual((r["acordar"], r["sair"], r["hora"], r["titulo"]), ("06:15", "07:00", "08:00", "voo"))
        self.assertEqual(r["acordar_iso"], f"{(BASE + timedelta(days=1)).isoformat()}T06:15:00")
        self.assertEqual(r["mensagem"], "Despertador às 06:15: o voo às 08:00, sai 07:00.")

    def test_ate_e_madrugada(self):
        self.voo(BASE + timedelta(days=1), "08:00")
        r = self.get(datetime.combine(BASE, time(22, 0)), "?ate=06:00").get_json()
        self.assertEqual((r["tem"], r["acordar"]), (False, "06:15"))
        self.assertTrue(self.get(datetime.combine(BASE, time(22, 0)), "?ate=07:00").get_json()["tem"])
        # 1h da manha do proprio dia do voo: olha o dia de hoje, nao o de amanha
        r = self.get(datetime.combine(BASE + timedelta(days=1), time(1, 0))).get_json()
        self.assertEqual((r["tem"], r["data"]), (True, (BASE + timedelta(days=1)).isoformat()))

    def test_nada_com_hora_e_token(self):
        r = self.get(datetime.combine(BASE, time(22, 0))).get_json()
        self.assertEqual((r["tem"], r["mensagem"]), (False, ""))
        self.client.post("/logout")
        self.assertEqual(self.get(datetime.combine(BASE, time(22, 0))).status_code, 401)
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "x" * 24}):
            self.assertEqual(self.get(datetime.combine(BASE, time(22, 0))).status_code, 401)
            with patch("app._agora_brasilia", return_value=datetime.combine(BASE, time(22, 0))):
                ok = self.client.get("/api/atalho/despertador", headers={"X-Webhook-Token": "x" * 24})
            self.assertEqual(ok.status_code, 200)


# ------------------------------------------------------------------ 3. aeroclube
class AeroclubeTestCase(_ComBanco):
    def test_chegou_com_checklist_uma_vez_e_saiu_pergunta_horas(self):
        vid = self.voo(BASE, "08:00")
        chegou = self.com_conn(app._mensagem_aeroclube, "chegou", datetime.combine(BASE, time(7, 10)))
        self.assertTrue(chegou.startswith("Chegou no aeroclube. Decola 08:00. Confere: CIV e CMA, fone (headset)"))
        self.assertIsNone(self.com_conn(app._mensagem_aeroclube, "chegou", datetime.combine(BASE, time(7, 20))))
        # saiu antes de decolar (foi buscar algo): nao pergunta
        self.assertIsNone(self.com_conn(app._mensagem_aeroclube, "saiu", datetime.combine(BASE, time(7, 40))))
        saiu = self.com_conn(app._mensagem_aeroclube, "saiu", datetime.combine(BASE, time(9, 30)))
        self.assertEqual(saiu, "Quanto deu o voo? Um toque no chat e eu somo nas tuas horas.")
        self.assertIsNone(self.com_conn(app._mensagem_aeroclube, "saiu", datetime.combine(BASE, time(9, 40))))
        tipos = [c[0]["type"] if c else None for _, c in self.mensagens()]
        self.assertEqual(tipos, [None, "voo_horas"])
        self.assertEqual(self.mensagens()[1][1][0]["data"]["id"], vid)

    def test_sem_voo_no_dia_nao_fala(self):
        self.voo(BASE, "08:00", horas=1.2)
        self.assertIsNone(self.com_conn(app._mensagem_aeroclube, "chegou", datetime.combine(BASE, time(7, 10))))

    def test_rota_do_atalho_com_lugar_aeroclube(self):
        self.voo(HOJE, None)
        r = self.client.post("/api/atalho/local", json={"evento": "chegou", "lugar": "Aeroclube"}).get_json()
        self.assertTrue(r["mensagem"].startswith("Chegou no aeroclube. Confere:"))
        r = self.client.post("/api/atalho/local", json={"evento": "chegou", "lugar": "SSBL"}).get_json()
        self.assertEqual(r["mensagem"], "")  # ja marcou a chegada desse voo


# ------------------------------------------------------------------ 4. compras
class ComprasTestCase(_ComBanco):
    def comprou(self, item, *dias_atras, pendente=False):
        for d in dias_atras:
            self.sql("INSERT INTO compras (item, item_normalizado, comprado_em) VALUES (?, ?, ?)",
                     (item, vida.normalizar_item_compra(item), (HOJE - timedelta(days=d)).isoformat()))
        if pendente:
            self.sql("INSERT INTO compras (item, item_normalizado) VALUES (?, ?)", (item, vida.normalizar_item_compra(item)))

    def test_so_com_historico_regular_e_fora_da_lista(self):
        self.comprou("café", 30, 20, 10)
        self.comprou("pilha", 20, 10)  # 2 vezes: nao chuta
        self.comprou("sal", 600, 400, 200)  # intervalo longo demais
        self.comprou("leite", 21, 14, 7, pendente=True)  # ja ta na lista
        self.comprou("arroz", 60, 40, 20)  # 20 em 20 dias -> acaba hoje
        self.comprou("detergente", 45, 30, 15)  # 15 em 15 -> hoje
        self.comprou("azeite", 90, 60, 40)  # mediana 25 -> devia ter acabado ha 15 dias: comprou fora
        self.comprou("feijão", 26, 16, 6)  # 10 em 10 -> daqui 4 dias: longe ainda
        itens = self.com_conn(conversa_proativa.compras_previstas, HOJE)
        self.assertEqual(sorted(i["chave"] for i in itens), sorted(vida.normalizar_item_compra(x) for x in ("café", "arroz", "detergente")))
        cafe = next(i for i in itens if i["item"].lower().startswith("caf"))
        self.assertEqual((cafe["intervalo_dias"], cafe["dias"], cafe["prevista"]), (10, 0, HOJE.isoformat()))

    def test_aviso_uma_vez_por_dia_e_por_compra(self):
        self.comprou("café", 30, 20, 10)
        dez = datetime.combine(HOJE, time(10, 0))
        self.assertEqual(self.com_conn(conversa_proativa.avisar_compras, datetime.combine(HOJE, time(8, 0))), [])
        saida = self.com_conn(conversa_proativa.avisar_compras, dez)
        self.assertEqual(len(saida), 1)
        self.assertIn("deve acabar nos próximos dias", saida[0][2])
        self.assertEqual(self.com_conn(conversa_proativa.avisar_compras, dez + timedelta(hours=2)), [])
        self.assertEqual(self.com_conn(conversa_proativa.avisar_compras, dez + timedelta(days=1)), [])
        texto, [card] = self.mensagens()[0]
        self.assertEqual(card["type"], "compras_previsao")
        self.assertEqual(len(card["data"]["itens"]), 1)

    def test_ainda_tem_adia_e_por_na_lista_tira(self):
        self.comprou("café", 30, 20, 10)
        r = self.client.post("/api/compras/adiar", json={"item": "café"})
        self.assertEqual(r.get_json(), {"ok": True, "ate": (HOJE + timedelta(days=5)).isoformat()})
        self.assertEqual(self.com_conn(conversa_proativa.compras_previstas, HOJE), [])
        self.assertEqual(len(self.com_conn(conversa_proativa.compras_previstas, HOJE + timedelta(days=5))), 1)
        for ruim in ({}, {"item": ""}, {"item": 3}, {"item": "x" * 61}):
            self.assertEqual(self.client.post("/api/compras/adiar", json=ruim).status_code, 400, ruim)
        self.client.post("/api/compras", json={"item": "café"})
        self.assertEqual(self.com_conn(conversa_proativa.compras_previstas, HOJE + timedelta(days=5)), [])

    def test_visitante_nao_adia(self):
        self.visitante()
        self.assertEqual(self.client.post("/api/compras/adiar", json={"item": "café"}).status_code, 403)


# ------------------------------------------------------------------ 5. assinatura
class AssinaturaTestCase(_ComBanco):
    AUMENTO = {"descricao": "Netflix", "categoria": "assinaturas", "valor_anterior_medio": 39.9, "valor_novo": 44.9, "aumento_pct": 12.53}

    def test_card_no_chat_uma_vez_sem_push_duplicado(self):
        with patch("gastos.detectar_aumento_assinatura", return_value=[self.AUMENTO]), \
                patch("notificacoes._gastos_reais_unificados_para_deteccao", return_value=[]):
            agora = datetime.combine(BASE, time(10, 0))
            self.assertEqual(self.com_conn(conversa_proativa.assinaturas_que_subiram, agora), [])
            self.com_conn(conversa_proativa.assinaturas_que_subiram, agora + timedelta(days=1))
        (texto, [card]), = self.mensagens()
        self.assertEqual(texto, '"Netflix" ficou 13% mais cara. Mantém ou quer que eu te lembre de cancelar?')
        self.assertEqual(card["data"], {"descricao": "Netflix", "categoria": "assinaturas", "de": 39.9, "para": 44.9, "pct": 13})

    def test_visitante_nao_ve_valor(self):
        card = cards.card_assinatura_subiu(self.AUMENTO)
        [m] = cards.mascarar_cards([card])
        self.assertTrue(m["data"]["oculto"])
        self.assertFalse({"de", "para", "pct"} & set(m["data"]))


# ------------------------------------------------------------------ 6. documentos
class DocumentosTestCase(_ComBanco):
    def test_marcos_60_30_7_cada_um_uma_vez(self):
        conn = db.get_db()
        db.create_lembrete(conn, "Renovar CMA", (BASE + timedelta(days=45)).isoformat())
        db.create_lembrete(conn, "Aniversário da mãe", (BASE + timedelta(days=45)).isoformat())
        conn.commit()
        conn.close()
        dez = datetime.combine(BASE, time(10, 0))
        self.assertEqual(self.com_conn(conversa_proativa.documentos_vencendo, datetime.combine(BASE, time(7, 0))), [])
        [(tipo, titulo, texto)] = self.com_conn(conversa_proativa.documentos_vencendo, dez)
        self.assertEqual((tipo, titulo), ("documento_validade", "Documento vencendo"))
        self.assertIn('"Renovar CMA" vence em 45 dias', texto)
        self.assertEqual(self.com_conn(conversa_proativa.documentos_vencendo, dez + timedelta(days=1)), [])
        self.assertEqual(len(self.com_conn(conversa_proativa.documentos_vencendo, dez + timedelta(days=16))), 1)  # 29 dias
        self.assertEqual(len(self.com_conn(conversa_proativa.documentos_vencendo, dez + timedelta(days=40))), 1)  # 5 dias
        self.assertEqual(self.com_conn(conversa_proativa.documentos_vencendo, dez + timedelta(days=41)), [])
        marcos = [c[0]["data"]["marco"] for _, c in self.mensagens()]
        self.assertEqual(marcos, [60, 30, 7])

    def test_marco(self):
        self.assertEqual([cards.marco_documento(d) for d in (61, 60, 31, 30, 8, 7, 0, -1)], [None, 60, 60, 30, 30, 7, 7, None])


# ------------------------------------------------------------------ 7. projecao
class ProjecaoTestCase(_ComBanco):
    def test_ritmo_dos_ultimos_60_dias(self):
        conn = db.get_db()
        db.definir_configuracao(conn, "aviacao_meta_horas", "50")
        conn.commit()
        conn.close()
        self.voo(BASE - timedelta(days=200), "09:00", horas=30.0)  # conta pro total, nao pro ritmo
        for k in range(8):  # 8 voos de 1,5 h em 60 dias = 12 h / 8,57 semanas = 1,4 h/semana
            self.voo(BASE - timedelta(days=5 + k * 7), "09:00", horas=1.5)
        self.voo(BASE - timedelta(days=3), "09:00", horas=2.0, tipo="simulador")
        p = self.com_conn(cards.projecao_horas, BASE)
        self.assertEqual((p["falta_h"], p["ritmo_h_semana"], p["horas_por_voo"], p["meta_horas"]), (8.0, 1.4, 1.5, 50))
        self.assertEqual(p["data_meta"], (BASE + timedelta(days=40)).isoformat())  # ceil(8/1.4*7)
        self.assertEqual(p["data_meta_mais_um"], (BASE + timedelta(days=20)).isoformat())  # ceil(8/2.9*7)
        resumo = self.com_conn(cards.card_voo_resumo, BASE)
        self.assertEqual(resumo["data"]["projecao"], p)

    def test_sem_voo_recente_ou_meta_batida_e_none(self):
        self.voo(BASE - timedelta(days=90), "09:00", horas=10.0)
        self.assertIsNone(self.com_conn(cards.projecao_horas, BASE))
        self.voo(BASE - timedelta(days=2), "09:00", horas=200.0)
        self.assertIsNone(self.com_conn(cards.projecao_horas, BASE))

    def test_ritmo_lento_demais_nao_inventa_data(self):
        self.voo(BASE - timedelta(days=10), "09:00", horas=0.2)
        p = self.com_conn(cards.projecao_horas, BASE)
        self.assertIsNone(p["data_meta"])


# ------------------------------------------------------------------ mochila
class MochilaTestCase(_ComBanco):
    def test_marca_e_devolve(self):
        vid = self.voo(BASE, "08:00")
        n = len(cards.MOCHILA_VOO)
        self.assertEqual(self.client.get(f"/api/voos/{vid}/mochila").get_json(), {"ok": True, "feitos": [False] * n})
        r = self.client.post(f"/api/voos/{vid}/mochila", json={"i": 0, "feito": True}).get_json()
        self.assertEqual((r["feitos"][0], r["total"]), (True, n))
        self.assertTrue(self.com_conn(cards.card_vespera_voo, vid)["data"]["mochila"][0]["feito"])
        for ruim in ({"i": n, "feito": True}, {"i": -1, "feito": True}, {"i": True, "feito": True}, {"i": 0, "feito": 1}, {}):
            self.assertEqual(self.client.post(f"/api/voos/{vid}/mochila", json=ruim).status_code, 400, ruim)
        self.assertEqual(self.client.get("/api/voos/9999/mochila").status_code, 404)

    def test_visitante_ve_mas_nao_marca(self):
        vid = self.voo(BASE, "08:00")
        self.visitante()
        self.assertEqual(self.client.get(f"/api/voos/{vid}/mochila").status_code, 200)
        self.assertEqual(self.client.post(f"/api/voos/{vid}/mochila", json={"i": 0, "feito": True}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
