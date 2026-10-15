"""Cards de compromisso com cara propria (2026-10-14, 2a leva - docs/CARDS.md "Linguagem visual").

Date, balada, documentos e presente: a IA marca `estilo` no registrar_tarefa; o executor guarda
os extras (lista, ideias, com quem, volta) e calcula o que precisa de rede (trajeto, clima, horario
do Google, compromisso do dia seguinte) - o card sai montado sem rede. Pedidos do Alex: balada so
fala de sono se o dia seguinte tiver compromisso com hora (volta padrao 03:00); tocar numa ideia de
presente cria lembrete de comprar 4 dias antes; documentos mostra o horario do Google.
Mesmo esquema do test_voo_agendado: banco temporario, login real, claude_client.chat dublado."""
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
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

PIN = "246810"
HOJE = date.today()
EM_3 = (HOJE + timedelta(days=3)).isoformat()
EM_12 = (HOJE + timedelta(days=12)).isoformat()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class CardsSaidasTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        # nada de rede de verdade: sem casa/cidade e sem Maps, a menos que o teste ligue
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None)):  # clima do prompt, nao do card
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def chat(self, chamadas):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "sabado tenho date"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def card(self, corpo, tipo):
        return next(c for c in corpo["cards"] if c["type"] == tipo)

    def extras(self, task_id):
        return json.loads(self.sql("SELECT extras FROM tasks WHERE id = ?", (task_id,))[0][0])

    # ------------------------------------------------------------------ date
    def test_date_sem_maps_usa_folga_de_15_min_e_guarda_a_lista(self):
        corpo, res = self.chat([("registrar_tarefa", {
            "titulo": "Jantar com a Júlia", "quando_data": EM_3, "hora": "20:00", "estilo": "date",
            "lugar": "Lume Bistrô", "com_quem": "Júlia",
            "lista": [{"texto": "Reservar mesa", "quando": "hoje"}, "Comprar flores", {"sem": "texto"}, 7],
        })])
        self.assertEqual(res[0]["plano"]["sair_de_casa"], "19:45")
        self.assertEqual(res[0]["plano"]["comecar_a_se_arrumar"], "19:05")  # 40 min padrao
        d = self.card(corpo, "date")["data"]
        self.assertEqual((d["sair"], d["comecar"], d["arrumar_min"]), ("19:45", "19:05", 40))
        self.assertEqual((d["lugar"], d["com_quem"]), ("Lume Bistrô", "Júlia"))
        self.assertIsNone(d["trajeto_min"])
        self.assertEqual([i["texto"] for i in d["lista"]], ["Reservar mesa", "Comprar flores"])
        self.assertFalse(any(i["feito"] for i in d["lista"]))
        self.assertNotIn("tarefas_criadas", [c["type"] for c in corpo["cards"]])

    def test_date_com_maps_e_clima_traz_trajeto_e_temperatura(self):
        prev = {"temp": 15.6, "chuva_pct": 60, "codigo": 61}
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste", "CIDADE_PADRAO": "Blumenau"}), \
             patch("maps_client.configurado", return_value=True), \
             patch("maps_client.horario_de_saida",
                   return_value={"sair_ate": f"{EM_3}T19:30:00", "duracao_minutos": 25}) as maps, \
             patch("clima.geocodificar_cidade", return_value={"lat": -26.9, "lon": -49.1}), \
             patch("clima.previsao_na_hora", return_value=prev):
            corpo, res = self.chat([("registrar_tarefa", {
                "titulo": "Date", "quando_data": EM_3, "hora": "20:00", "estilo": "date", "lugar": "Lume"})])
        self.assertEqual(maps.call_args[0][:2], ("casa de teste", "Lume"))
        self.assertEqual(res[0]["plano"]["temperatura_na_hora"], 16)
        d = self.card(corpo, "date")["data"]
        self.assertEqual((d["sair"], d["trajeto_min"]), ("19:30", 25))
        self.assertEqual(d["clima"], {"temp": 16, "chuva_pct": 60})

    def test_rede_fora_do_ar_nao_derruba_o_registro(self):
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa", "CIDADE_PADRAO": "Blumenau"}), \
             patch("maps_client.configurado", return_value=True), \
             patch("maps_client.horario_de_saida", side_effect=RuntimeError("sem rede")), \
             patch("clima.geocodificar_cidade", side_effect=RuntimeError("sem rede")):
            corpo, res = self.chat([("registrar_tarefa", {
                "titulo": "Date", "quando_data": EM_3, "hora": "20:00", "estilo": "date", "lugar": "Lume"})])
        self.assertTrue(res[0]["ok"])
        self.assertEqual(self.card(corpo, "date")["data"]["sair"], "19:45")

    def test_estilo_sem_dia_vira_tarefa_comum(self):
        corpo, _ = self.chat([("registrar_tarefa", {"titulo": "Ir num date um dia", "estilo": "date"})])
        self.assertEqual(self.sql("SELECT estilo, extras FROM tasks")[0][:], (None, None))
        self.assertIn("tarefas_criadas", [c["type"] for c in corpo["cards"]])

    def test_estilo_desconhecido_e_ignorado(self):
        self.chat([("registrar_tarefa", {"titulo": "X", "quando_data": EM_3, "estilo": "<script>"})])
        self.assertIsNone(self.sql("SELECT estilo FROM tasks")[0][0])

    # ---------------------------------------------------------------- balada
    def test_balada_sem_compromisso_no_dia_seguinte_nao_fala_de_sono(self):
        corpo, res = self.chat([("registrar_tarefa", {
            "titulo": "Balada no Warung", "quando_data": EM_3, "hora": "23:00", "estilo": "balada"})])
        self.assertNotIn("dia_seguinte", res[0]["plano"])
        d = self.card(corpo, "balada")["data"]
        self.assertIsNone(d["volta"])
        self.assertNotIn("sono", d)

    def test_balada_com_voo_no_dia_seguinte_conta_o_sono_a_partir_das_3h(self):
        amanha = (HOJE + timedelta(days=4)).isoformat()
        self.sql("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '14:00')", (amanha,))
        corpo, res = self.chat([("registrar_tarefa", {
            "titulo": "Balada", "quando_data": EM_3, "hora": "23:00", "estilo": "balada"})])
        # voo 14:00, chegar 30 min antes + 15 de folga -> sair 13:15 -> acordar 12:35 (40 min)
        self.assertIn("acordar ate 12:35", res[0]["plano"]["dia_seguinte"])
        d = self.card(corpo, "balada")["data"]
        self.assertEqual((d["volta"], d["volta_dita"]), ("03:00", False))
        self.assertEqual(d["sono"], {"min": 575, "volta": "03:00", "acordar": "12:35", "compromisso": "voo", "hora": "14:00"})

    def test_balada_com_volta_dita_e_tarefa_cedo_usa_a_hora_dele(self):
        amanha = (HOJE + timedelta(days=4)).isoformat()
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES ('Prova de navegação', ?, '09:00')", (amanha,))
        corpo, _ = self.chat([("registrar_tarefa", {
            "titulo": "Balada", "quando_data": EM_3, "hora": "23:00", "estilo": "balada", "volta": "4:30"})])
        d = self.card(corpo, "balada")["data"]
        self.assertEqual((d["volta"], d["volta_dita"]), ("04:30", True))
        # 09:00 - 15 = 08:45 sair -> 08:05 acordar -> 3h35 de sono
        self.assertEqual((d["sono"]["acordar"], d["sono"]["min"]), ("08:05", 215))

    def test_volta_dirigindo_por_padrao_e_uber_cria_a_tarefa_de_chamar(self):
        amanha = (HOJE + timedelta(days=4)).isoformat()
        self.sql("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '14:00')", (amanha,))
        corpo, _ = self.chat([("registrar_tarefa", {
            "titulo": "Balada", "quando_data": EM_3, "hora": "23:00", "estilo": "balada"})])
        d = self.card(corpo, "balada")["data"]
        self.assertEqual(d["volta_modo"], "dirigindo")
        self.assertNotIn("uber", d)
        tid = d["id"]
        r = self.client.post(f"/api/tasks/{tid}/volta", json={"modo": "uber"}).get_json()
        self.assertEqual(r, {"ok": True, "modo": "uber", "hora": "02:30"})
        uber = self.sql("SELECT title, due_date, hora FROM tasks WHERE title = 'Chamar Uber pra voltar'")
        self.assertEqual(tuple(uber[0]), ("Chamar Uber pra voltar", amanha, "02:30"))  # madrugada = dia seguinte
        # escolher Uber de novo nao duplica
        self.client.post(f"/api/tasks/{tid}/volta", json={"modo": "uber"})
        self.assertEqual(len(self.sql("SELECT id FROM tasks WHERE title = 'Chamar Uber pra voltar'")), 1)
        self.assertEqual(self.client.get(f"/api/tasks/estado?ids={tid}").get_json()["extras"][str(tid)]["volta_modo"], "uber")
        r = self.client.post(f"/api/tasks/{tid}/volta", json={"modo": "carona"}).get_json()
        self.assertEqual(r, {"ok": True, "modo": "carona", "hora": None})
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE title = 'Chamar Uber pra voltar'")[0][0], 0)
        self.assertEqual(self.extras(tid)["volta_modo"], "carona")
        for ruim in ("taxi", None, 1, ["uber"]):
            self.assertEqual(self.client.post(f"/api/tasks/{tid}/volta", json={"modo": ruim}).status_code, 400, ruim)

    def test_volta_sem_hora_dita_usa_3h_e_a_ia_pode_mandar_o_modo(self):
        corpo, _ = self.chat([("registrar_tarefa", {
            "titulo": "Balada", "quando_data": EM_3, "hora": "23:00", "estilo": "balada", "volta_modo": "carona"})])
        d = self.card(corpo, "balada")["data"]
        self.assertEqual(d["volta_modo"], "carona")
        r = self.client.post(f"/api/tasks/{d['id']}/volta", json={"modo": "uber"}).get_json()
        self.assertEqual(r["hora"], "02:30")
        corpo, _ = self.chat([("registrar_tarefa", {
            "titulo": "Outra", "quando_data": EM_3, "hora": "23:00", "estilo": "balada", "volta_modo": "<x>"})])
        self.assertEqual(self.card(corpo, "balada")["data"]["volta_modo"], "dirigindo")

    def test_balada_da_2a_leva_com_chave_do_uber_ligada_aparece_como_uber(self):
        self.assertEqual(cards.modo_volta({"uber": True, "uber_tarefa_id": 4}), "uber")
        self.assertEqual(cards.modo_volta({"uber": False}), "dirigindo")
        self.assertEqual(cards.modo_volta({"uber": True, "volta_modo": "carona"}), "carona")
        self.assertEqual(cards.modo_volta({"volta_modo": "<x>"}), "dirigindo")

    # ------------------------------------------------------------ documentos
    def test_documentos_traz_horario_do_google_e_a_caixinha_marca(self):
        horario = {"nome": "1º Tabelionato", "faixas": [["09:00", "12:00"], ["13:00", "17:00"]]}
        with patch("maps_client.configurado", return_value=True), \
             patch("maps_client.horario_funcionamento", return_value=horario) as hf:
            corpo, res = self.chat([("registrar_tarefa", {
                "titulo": "Reconhecer firma", "quando_data": EM_3, "hora": "09:00", "estilo": "documentos",
                "lugar": "1º Tabelionato de Itajaí", "lista": [{"texto": "RG", "detalhe": "original"}, "Contrato"]})])
        self.assertEqual(hf.call_args[0][0], "1º Tabelionato de Itajaí")
        self.assertEqual(res[0]["plano"]["horario_do_lugar"], "09:00-12:00, 13:00-17:00")
        card = self.card(corpo, "documentos")
        self.assertEqual(card["data"]["horario"], horario)
        tid = card["data"]["id"]
        r = self.client.post(f"/api/tasks/{tid}/lista", json={"i": 1, "feito": True}).get_json()
        self.assertEqual(r, {"ok": True, "feitos": 1, "total": 2})
        self.assertEqual(self.client.get(f"/api/tasks/estado?ids={tid}").get_json()["extras"][str(tid)]["lista"], [False, True])
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/lista", json={"i": 5, "feito": True}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/lista", json={"i": True}).status_code, 400)

    def test_lista_so_vale_pra_tarefa_com_estilo_de_lista(self):
        self.sql("INSERT INTO tasks (title, due_date) VALUES ('comum', ?)", (EM_3,))
        tid = self.sql("SELECT id FROM tasks")[0][0]
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/lista", json={"i": 0, "feito": True}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/presente", json={"i": 0}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/volta", json={"modo": "uber"}).status_code, 404)

    # -------------------------------------------------------------- presente
    def presente(self, dia=EM_12):
        corpo, res = self.chat([("registrar_tarefa", {
            "titulo": "Aniversário da mãe", "quando_data": dia, "estilo": "presente",
            "ideias": [{"titulo": "Kit de jardinagem", "porque": "voltou às orquídeas", "preco": 180},
                       {"titulo": "Livro", "preco": True}, {"porque": "sem titulo"}]})])
        return self.card(corpo, "presente"), res[0]

    def test_presente_compra_ate_4_dias_antes_e_a_ideia_vira_lembrete(self):
        card, res = self.presente()
        limite = (HOJE + timedelta(days=8)).isoformat()
        self.assertEqual(res["plano"]["comprar_ate"], limite)
        d = card["data"]
        self.assertEqual((d["dias"], d["compra_ate"], d["escolha"]), (12, limite, None))
        self.assertEqual([(i["titulo"], i["preco"]) for i in d["ideias"]], [("Kit de jardinagem", 180), ("Livro", None)])
        tid = d["id"]
        r = self.client.post(f"/api/tasks/{tid}/presente", json={"i": 0}).get_json()
        self.assertEqual(r, {"ok": True, "escolha": 0, "compra_ate": limite})
        self.client.post(f"/api/tasks/{tid}/presente", json={"i": 1})  # trocou de ideia: mesmo lembrete
        lembretes = self.sql("SELECT titulo, data FROM lembretes")
        self.assertEqual([tuple(x) for x in lembretes], [("Comprar presente: Livro (Aniversário da mãe)", limite)])
        self.assertEqual(self.client.get(f"/api/tasks/estado?ids={tid}").get_json()["extras"][str(tid)]["escolha"], 1)
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/presente", json={"i": 9}).status_code, 400)

    def test_presente_em_cima_da_hora_compra_hoje(self):
        card, res = self.presente((HOJE + timedelta(days=2)).isoformat())
        self.assertEqual(card["data"]["compra_ate"], HOJE.isoformat())
        self.assertEqual(res["plano"]["comprar_ate"], HOJE.isoformat())

    def test_desfazer_leva_junto_o_lembrete_do_presente(self):
        card, _ = self.presente()
        self.client.post(f"/api/tasks/{card['data']['id']}/presente", json={"i": 0})
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lembretes")[0][0], 0)

    def test_visitante_nao_ve_preco_nem_mexe_no_card(self):
        card, _ = self.presente()
        mascarado = cards.mascarar_cards([json.loads(json.dumps(card))])[0]
        self.assertNotIn("preco", json.dumps(mascarado["data"]["ideias"]))
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = __import__("time").time()
        tid = card["data"]["id"]
        for rota, corpo in (("presente", {"i": 0}), ("lista", {"i": 0, "feito": True}), ("volta", {"modo": "uber"})):
            self.assertEqual(self.client.post(f"/api/tasks/{tid}/{rota}", json=corpo).status_code, 403, rota)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lembretes")[0][0], 0)


class AvisoSeArrumarTestCase(unittest.TestCase):
    def test_date_conta_como_saida_mesmo_sem_palavra_no_titulo(self):
        import notificacoes

        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        try:
            conn.execute("INSERT INTO tasks (title, due_date, hora, estilo) VALUES ('Júlia', ?, '20:00', 'date')",
                         (HOJE.isoformat(),))
            conn.commit()
            from datetime import datetime
            agora = datetime.combine(HOJE, datetime.strptime("19:00", "%H:%M").time())
            with patch.dict(os.environ, {"ENDERECO_CASA": ""}):
                plano = notificacoes.plano_se_arrumar(conn, agora)
        finally:
            conn.close()
        self.assertTrue(plano, "date de hoje com hora tem que entrar no aviso de se arrumar")


if __name__ == "__main__":
    unittest.main()
