"""BRIEFING.md Fase 3: projecao do mes, previsao de meta, aprender, links
salvos, progresso, revisao mensal, burocracia, pos-voo e uso do celular."""

import os
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from test_vida_rotas import VidaBaseTestCase, fake_usage

import app
import db
import leitura
import vida


class LogicaFase3TestCase(unittest.TestCase):
    def test_eh_burocracia(self):
        for sim in ["Renovar CNH", "Imposto de renda 2027", "Declaracao do IR", "Exame médico CMA", "IPVA do carro"]:
            self.assertTrue(vida.eh_burocracia(sim), sim)
        for nao in ["Ir no mercado", "Aniversario do Jorge", "Pagar luz", None, ""]:
            self.assertFalse(vida.eh_burocracia(nao), nao)

    def test_projecao_fim_do_mes(self):
        p = vida.projecao_fim_do_mes(5000, 1000, 200, date(2026, 9, 10))
        self.assertEqual(p["ritmo_diario"], 100.0)
        self.assertEqual(p["dias_restantes"], 20)
        self.assertEqual(p["gasto_projetado"], 3200.0)
        self.assertEqual(p["sobra_projetada"], 1800.0)
        ultimo_dia = vida.projecao_fim_do_mes(0, 0, 0, date(2026, 2, 28))
        self.assertEqual(ultimo_dia["dias_restantes"], 0)

    def test_previsao_meta(self):
        hoje = date(2026, 9, 23)
        depositos = [
            {"valor": 300, "criado_em": "2026-07-25 10:00:00"},
            {"valor": 300, "criado_em": "2026-08-25 10:00:00"},
            {"valor": 999, "criado_em": "2025-01-01 10:00:00"},  # fora da janela de 90 dias
        ]
        p = vida.previsao_meta(3000, 1200, depositos, hoje)
        self.assertEqual(p["ritmo_mensal"], 300.0)
        self.assertEqual(p["data_prevista"], (hoje + timedelta(days=181)).isoformat())
        self.assertIsNone(vida.previsao_meta(3000, 3000, depositos, hoje))
        self.assertIsNone(vida.previsao_meta(3000, 0, [], hoje))
        self.assertIsNone(vida.previsao_meta(3000, 0, [{"valor": 10, "criado_em": "lixo"}], hoje))

    def test_uso_de_apps(self):
        eventos = [
            {"app": "Instagram", "evento": "abriu", "em": "2026-09-23T10:00:00"},
            {"app": "Instagram", "evento": "fechou", "em": "2026-09-23T10:30:00"},
            {"app": "TikTok", "evento": "abriu", "em": "2026-09-23T11:00:00"},
            {"app": "TikTok", "evento": "fechou", "em": "2026-09-23T15:30:00"},  # 4h30: fechou perdido
            {"app": "Instagram", "evento": "abriu", "em": "2026-09-23T20:00:00"},
            {"app": "Instagram", "evento": "fechou", "em": "2026-09-23T20:45:00"},
            {"app": "YouTube", "evento": "fechou", "em": "2026-09-23T21:00:00"},
            {"app": "YouTube", "evento": "abriu", "em": "2026-09-23T22:00:00"},
            {"app": "", "evento": "abriu", "em": "2026-09-23T22:00:00"},
            {"app": "X", "evento": "abriu", "em": "lixo"},
        ]
        self.assertEqual(vida.uso_de_apps(eventos), {"Instagram": 75})

    def test_formatar_minutos_e_mes_anterior(self):
        self.assertEqual(vida.formatar_minutos(75), "1h15")
        self.assertEqual(vida.formatar_minutos(120), "2h")
        self.assertEqual(vida.formatar_minutos(9), "9min")
        self.assertEqual(vida.mes_anterior(date(2026, 3, 15)), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(vida.mes_anterior(date(2026, 1, 1)), (date(2025, 12, 1), date(2025, 12, 31)))


class LeituraTestCase(unittest.TestCase):
    def test_validar_url_bloqueia_rede_interna(self):
        for ruim in ["ftp://x.com/a", "javascript:alert(1)", "http://localhost/admin", "http://127.0.0.1:5000/",
                     "http://10.0.0.5/", "http://169.254.169.254/latest/meta-data", "http://[::1]/", "", 5, None,
                     "http://" + "a" * 2000 + ".com"]:
            with self.assertRaises(leitura.LinkInvalido, msg=repr(ruim)):
                leitura.validar_url(ruim)
        with patch("leitura._host_publico", return_value=True):
            self.assertEqual(leitura.validar_url(" https://exemplo.com/artigo "), "https://exemplo.com/artigo")

    def test_redirecionamento_pra_rede_interna_bloqueado(self):
        redirect = SimpleNamespace(is_redirect=True, headers={"Location": "http://127.0.0.1/segredo"}, close=lambda: None)
        with patch("leitura._host_publico", side_effect=lambda h: h != "127.0.0.1"), \
                patch("leitura.requests.get", return_value=redirect):
            with self.assertRaises(leitura.LinkInvalido):
                leitura.baixar_pagina("https://exemplo.com/a")

    def test_extrair(self):
        pagina = """<html><head><title>Titulo &amp; tal</title>
        <meta property="og:description" content="Resumo da pagina">
        <script>var segredo = 1;</script><style>.x{}</style></head>
        <body><h1>Oi</h1><p>Texto   importante</p></body></html>"""
        r = leitura.extrair(pagina)
        self.assertEqual(r["titulo"], "Titulo & tal")
        self.assertIn("Resumo da pagina", r["texto"])
        self.assertIn("Texto importante", r["texto"])
        self.assertNotIn("segredo", r["texto"])
        og = leitura.extrair('<meta content="Video legal" property="og:title"><title>outro</title>')
        self.assertEqual(og["titulo"], "Video legal")


class AprenderSalvosTestCase(VidaBaseTestCase):
    def test_aprender_crud(self):
        r = self.client.post("/api/aprender", json={"tema": "Investimento em FII", "nota": "comecar pelo basico"})
        self.assertEqual(r.status_code, 201)
        aid = r.get_json()["id"]
        self.assertEqual(self.client.get("/api/aprender").get_json()[0]["dias_parado"], 0)
        self.assertEqual(self.client.post(f"/api/aprender/{aid}/retomei").status_code, 200)
        self.assertEqual(self.client.post(f"/api/aprender/{aid}/outra").status_code, 404)
        self.assertEqual(self.client.post("/api/aprender/999/retomei").status_code, 404)
        self.client.post(f"/api/aprender/{aid}/concluido")
        self.assertEqual(self.client.get("/api/aprender").get_json(), [])
        for corpo in [{}, {"tema": " "}, {"tema": "x" * 81}, {"tema": 5}]:
            self.assertEqual(self.client.post("/api/aprender", json=corpo).status_code, 400)

    def test_salvar_link_com_resumo(self):
        pagina = "<title>Artigo</title><p>" + "conteudo relevante " * 20 + "</p>"
        with patch("leitura._host_publico", return_value=True), \
                patch("leitura.baixar_pagina", return_value=pagina), \
                patch("claude_client.resumir_link", return_value=("- ponto 1\n- ponto 2", fake_usage())):
            r = self.client.post("/api/salvos", json={"url": "https://exemplo.com/artigo"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["resumo"], "- ponto 1\n- ponto 2")
        salvo = self.client.get("/api/salvos").get_json()[0]
        self.assertEqual(salvo["titulo"], "Artigo")
        self.client.post(f"/api/salvos/{salvo['id']}/lido")
        self.assertIsNotNone(self.client.get("/api/salvos").get_json()[0]["lido_em"])
        self.assertEqual(self.client.post("/api/salvos/999/lido").status_code, 404)

    def test_link_que_nao_abre_fica_salvo(self):
        import requests
        with patch("leitura._host_publico", return_value=True), \
                patch("leitura.baixar_pagina", side_effect=requests.ConnectionError("fora do ar")):
            r = self.client.post("/api/salvos", json={"url": "https://exemplo.com/x"}).get_json()
        self.assertIsNone(r["resumo"])
        self.assertIn("link ficou salvo", r["aviso"])
        self.assertEqual(len(self.client.get("/api/salvos").get_json()), 1)

    def test_link_interno_recusado(self):
        for url in ["http://127.0.0.1:5000/api/backup", "file:///etc/passwd", "nao e link"]:
            self.assertEqual(self.client.post("/api/salvos", json={"url": url}).status_code, 400)
        self.assertEqual(self.client.get("/api/salvos").get_json(), [])

    def test_chat_registra_aprender_e_salva_link(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertTrue(executores["registrar_aprender"]({"tema": "Meteorologia avancada"})["ok"])
            self.assertIn("erro", executores["salvar_link"]({"url": "http://localhost/x"}))
            return "Anotado.", ["registrar_aprender"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "quero aprender meteorologia avancada"})
        self.assertEqual(self.client.get("/api/aprender").get_json()[0]["tema"], "Meteorologia avancada")


class ProgressoRevisaoTestCase(VidaBaseTestCase):
    def test_progresso_conta_fatos(self):
        conn = self._conn()
        hoje = date.today().isoformat()
        tid = self._tarefa("x")
        self.client.post(f"/api/tasks/{tid}/complete")
        db.registrar_treino(conn, hoje, "Peito", 60, None)
        self.client.post("/api/hidratacao")
        for item in self.client.get("/api/rotina?momento=manha").get_json()["itens"][:2]:
            with patch("app.datetime") as dt:
                dt.now.return_value = datetime.combine(date.today(), datetime.min.time()).replace(hour=8)
                dt.fromisoformat = datetime.fromisoformat
                self.client.post(f"/api/rotina/{item['id']}/alternar")
        self.client.post("/api/checkin", json={"humor": "bom", "energia": "ok"})
        p = self.client.get("/api/progresso?dias=30").get_json()
        self.assertEqual(p["tarefas_feitas"], 1)
        self.assertEqual(p["treinos"], 1)
        self.assertEqual(p["rotina_manha_dias"], 1)
        self.assertEqual(p["humor_medio"], "bom")
        self.assertEqual(p["dias"], 30)
        self.assertEqual(self.client.get("/api/progresso?dias=1").get_json()["dias"], 7)

    def test_revisao_mensal(self):
        r = self.client.get("/api/revisao-mensal?mes=2026-02").get_json()
        self.assertEqual(r["dias"], 28)
        self.assertTrue(r["texto"].startswith("Fevereiro fechou: 0 tarefa(s) feita(s)"))
        self.assertEqual(self.client.get("/api/revisao-mensal?mes=2026-12").get_json()["dias"], 31)
        for ruim in ["2026-13", "ontem", "2026"]:
            self.assertEqual(self.client.get(f"/api/revisao-mensal?mes={ruim}").status_code, 400)
        self.assertEqual(self.client.get("/api/revisao-mensal").status_code, 200)

    def test_sobra_com_projecao_e_meta_com_previsao(self):
        conn = self._conn()
        dia = (date.today() + timedelta(days=1)).day
        if (date.today() + timedelta(days=1)).month == date.today().month:
            db.create_conta_pessoal(conn, "Internet", dia, 100.0)
        s = self.client.get("/api/sobra-do-mes").get_json()
        self.assertIn("projecao", s)
        self.assertIn("sobra_projetada", s["projecao"])
        goal = conn.execute("INSERT INTO goals (titulo, valor_alvo, valor_guardado) VALUES ('Viagem', 3000, 600)").lastrowid
        conn.execute("INSERT INTO goal_deposits (goal_id, valor, criado_em) VALUES (?, 600, datetime('now', '-40 days'))", (goal,))
        conn.commit()
        meta = self.client.get("/api/metas").get_json()[0]
        self.assertIsNotNone(meta["previsao"])
        self.assertGreater(meta["previsao"]["data_prevista"], date.today().isoformat())


class UsoAppsTestCase(VidaBaseTestCase):
    def test_eventos_e_resumo(self):
        with patch("app.datetime") as dt:
            dt.fromisoformat = datetime.fromisoformat
            base = datetime.now().replace(microsecond=0) - timedelta(hours=2)
            for minutos, evento in [(0, "abriu"), (40, "fechou")]:
                dt.now.return_value = base + timedelta(minutes=minutos)
                self.assertEqual(self.client.post("/api/atalho/app", json={"app": "Instagram", "evento": evento}).status_code, 200)
        uso = self.client.get("/api/uso-apps?dias=7").get_json()
        self.assertEqual(uso["apps"], [{"app": "Instagram", "minutos": 40, "texto": "40min"}])
        for corpo in [{}, {"app": "X"}, {"app": "X", "evento": "minimizou"}, {"app": "x" * 41, "evento": "abriu"}]:
            self.assertEqual(self.client.post("/api/atalho/app", json=corpo).status_code, 400)
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "segredo"}):
            anonimo = app.app.test_client()
            self.assertEqual(anonimo.post("/api/atalho/app", json={"app": "X", "evento": "abriu"}).status_code, 401)


class AvisosFase3TestCase(VidaBaseTestCase):
    def _tipos(self, agora):
        conn = self._conn()
        return [(t, c) for t, _, _, c in app._avisos_fase3(conn, agora)]

    def test_revisao_no_dia_1(self):
        primeiro = datetime(2026, 10, 1, 9, 30)
        self.assertTrue([c for t, c in self._tipos(primeiro) if t == "revisao_mensal" and c.startswith("Setembro fechou")])
        self.assertFalse([t for t, _ in self._tipos(primeiro.replace(day=2)) if t == "revisao_mensal"])
        self.assertFalse([t for t, _ in self._tipos(primeiro.replace(hour=8)) if t == "revisao_mensal"])

    def test_burocracia_com_30_dias(self):
        conn = self._conn()
        db.create_lembrete(conn, "Renovar CNH", (date.today() + timedelta(days=20)).isoformat())
        db.create_lembrete(conn, "Aniversario da Mae", (date.today() + timedelta(days=20)).isoformat())
        db.create_lembrete(conn, "Passaporte", (date.today() + timedelta(days=45)).isoformat())
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=10)
        textos = [c for t, c in self._tipos(agora) if t == "burocracia"]
        self.assertEqual(len(textos), 1)
        self.assertIn("Renovar CNH", textos[0])

    def test_aprender_no_domingo(self):
        conn = self._conn()
        aid = db.create_aprender(conn, "FII", None)
        conn.execute("UPDATE aprender SET criado_em = datetime('now', '-10 days') WHERE id = ?", (aid,))
        conn.commit()
        domingo = datetime.combine(date.today(), datetime.min.time()).replace(hour=11)
        domingo -= timedelta(days=(domingo.weekday() - 6) % 7)
        textos = [c for t, c in self._tipos(domingo) if t == "aprender"]
        self.assertEqual(len(textos), 1)
        self.assertIn('"FII"', textos[0])
        self.assertFalse([t for t, _ in self._tipos(domingo - timedelta(days=1)) if t == "aprender"])

    def test_pos_voo_duas_horas_depois(self):
        conn = self._conn()
        hoje = date.today()
        conn.execute("INSERT INTO voos (data, destino, hora) VALUES (?, 'SBJV', '10:00')", (hoje.isoformat(),))
        conn.execute("INSERT INTO voos (data, destino, hora, observacao) VALUES (?, 'SBFL', '08:00', 'ja anotei')", (hoje.isoformat(),))
        conn.commit()
        base = datetime.combine(hoje, datetime.min.time())
        self.assertFalse([t for t, _ in self._tipos(base.replace(hour=11)) if t == "pos_voo"])
        textos = [c for t, c in self._tipos(base.replace(hour=12, minute=5)) if t == "pos_voo"]
        self.assertEqual(textos, ["Como foi o voo pra SBJV? Conta no chat que eu guardo no diario de bordo."])

    def test_uso_apps_domingo_a_noite(self):
        conn = self._conn()
        agora = datetime.now().replace(microsecond=0)
        db.registrar_evento_app(conn, "Instagram", "abriu", (agora - timedelta(hours=3)).isoformat())
        db.registrar_evento_app(conn, "Instagram", "fechou", (agora - timedelta(hours=2)).isoformat())
        domingo = agora + timedelta(days=(6 - agora.weekday()) % 7)
        domingo = domingo.replace(hour=20)
        with patch("app.datetime") as dt:
            dt.now.return_value = agora
            dt.fromisoformat = datetime.fromisoformat
            textos = [c for t, c in self._tipos(domingo) if t == "uso_apps"]
        self.assertEqual(textos, ["Semana no celular: Instagram 1h."])


if __name__ == "__main__":
    unittest.main()
