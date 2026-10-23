"""3a leva dos cards (2026-10-14, docs/briefings/2026-10-14-3a-leva.md).

- linha "pensando": cada tool avisa o passo no stream antes de rodar (cards.passo_ao_vivo);
- vento/teto NA HORA do voo: briefing_voo.previsao_na_hora le o segmento do TAF que vale na
  hora (FM troca, BECMG mescla, TEMPO/PROB vira "pode ter"); fora da validade = None;
- horas do voo com 1 toque: depois do pouso estimado o chat pergunta (card voo_horas) e o chip
  grava em /api/voos/<id>/horas; registrar_voo com horas preenche o voo aberto do dia;
- presente que volta todo ano: renova com as ideias que sobraram e guarda o que ele deu.
Banco temporario, login real, claude_client.chat dublado - nada de rede."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import briefing_voo  # noqa: E402
import cards  # noqa: E402
import claude_client  # noqa: E402
import conversa_proativa  # noqa: E402
import metar  # noqa: E402
import rota_voo  # noqa: E402

PIN = "246810"
HOJE = date.today()


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class _ComBanco(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None)):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            linhas = conn.execute(query, params).fetchall()  # antes do commit: RETURNING
            conn.commit()
            return linhas
        finally:
            conn.close()

    def chat(self, chamadas, rota="/api/chat"):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post(rota, json={"mensagem": "anota ai pra mim"})
            res.get_data()  # stream: o corpo so e gerado quando le - ainda dentro do patch
        self.assertEqual(res.status_code, 200)
        return res, resultados

    def voo(self, data, hora, destino="SSBL", escalas=None, horas=None, tipo=None):
        cur = self.sql("INSERT INTO voos (data, origem, destino, hora, escalas, horas, tipo) "
                       "VALUES (?, 'SSBL', ?, ?, ?, ?, ?) RETURNING id", (data, destino, hora, escalas, horas, tipo))
        return cur[0][0]


# ---------------------------------------------------------------- linha "pensando"
class PassoAoVivoTestCase(unittest.TestCase):
    def test_frase_do_passo_por_tool(self):
        self.assertEqual(cards.passo_ao_vivo("registrar_tarefa", {"titulo": "Jantar com a Júlia"}), 'Anotando "Jantar com a Júlia"')
        self.assertEqual(cards.passo_ao_vivo("registrar_tarefa", {}), "Anotando")
        self.assertEqual(cards.passo_ao_vivo("registrar_voo", {"destino": "SBNF"}), "Montando a rota do voo")
        self.assertEqual(cards.passo_ao_vivo("tool_que_nao_existe", None), "Trabalhando nisso")
        longo = cards.passo_ao_vivo("registrar_tarefa", {"titulo": "x" * 300})
        self.assertLess(len(longo), 60)

    def test_executor_avisa_o_passo_antes_de_rodar_e_sem_stream_nao_faz_nada(self):
        visto = []
        ordem = []
        envolvidos = cards.RegistroExecucao().envolver(
            {"registrar_tarefa": lambda e: ordem.append("rodou") or {"ok": True}})
        with claude_client.ao_texto(lambda ev, dado: visto.append((ev, dado)) or ordem.append("passo")):
            envolvidos["registrar_tarefa"]({"titulo": "Comprar pão"})
        self.assertEqual(visto, [("passo", {"texto": 'Anotando "Comprar pão"'})])
        self.assertEqual(ordem, ["passo", "rodou"])
        # sem stream ligado (Telegram, /api/chat): roda igual, sem aviso
        self.assertEqual(envolvidos["registrar_tarefa"]({"titulo": "x"}), {"ok": True})

    def test_aviso_que_quebra_nao_derruba_a_tool(self):
        def quebra(ev, dado):
            raise RuntimeError("tela fechou")

        envolvidos = cards.RegistroExecucao().envolver({"t": lambda e: {"ok": True}})
        with claude_client.ao_texto(quebra):
            self.assertEqual(envolvidos["t"]({}), {"ok": True})


class PassoNoStreamTestCase(_ComBanco):
    def test_stream_manda_evento_passo_com_o_que_esta_rodando(self):
        from ia.funcoes import chat as chat_mod

        with patch.object(chat_mod, "_decidir_rota", return_value="padrao"):
            res, _ = self.chat([("registrar_tarefa", {"titulo": "Ligar pro dentista"})], rota="/api/chat/stream")
        corpo = res.get_data(as_text=True)
        self.assertIn("event: passo", corpo)
        self.assertIn('Anotando \\"Ligar pro dentista\\"', corpo)
        self.assertLess(corpo.index("event: passo"), corpo.index("event: fim"))


# ---------------------------------------------------------- tempo na hora do voo
TAF = ("TAF SBNF 141100Z 1412/1512 09010KT 9999 SCT030 BECMG 1418/1420 18015G25KT "
       "TEMPO 1420/1424 4000 TSRA BKN012CB FM150300 VRB03KT 9999 FEW020")
AGORA_UTC = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def _buscar(pedidos):
    def buscar(icao):
        pedidos.append(icao)
        return {"taf": TAF, "taf_segmentos": metar.decodificar_taf(metar._tokens_uteis_taf(TAF))}
    return buscar


class PrevisaoNaHoraTestCase(unittest.TestCase):
    def prev(self, dia, hh, mm=0, icao="SSBL"):
        pedidos = []
        p = briefing_voo.previsao_na_hora(icao, datetime(2026, 10, dia, hh, mm), AGORA_UTC, _buscar(pedidos))
        return p, pedidos

    def test_ssbl_usa_o_taf_de_navegantes_e_a_base_vale_de_manha(self):
        p, pedidos = self.prev(14, 11)  # 14Z
        self.assertEqual(pedidos, ["SBNF"])
        self.assertEqual((p["icao"], p["substituto_de"], p["hora"]), ("SBNF", "SSBL", "11:00"))
        self.assertEqual((p["vento"]["direcao"], p["vento"]["velocidade_kt"]), (90, 10))
        self.assertEqual(p["categoria"], "VFR")
        self.assertEqual(p["pode_ter"], [])
        self.assertIn("decisão", p["aviso"])

    def test_becmg_ja_comecado_muda_so_o_vento_e_tempo_vira_pode_ter(self):
        p, _ = self.prev(14, 18)  # 21Z: BECMG 18-20Z ja valeu, TEMPO 20-24Z cobre
        self.assertEqual((p["vento"]["direcao"], p["vento"]["rajada_kt"]), (180, 25))
        self.assertEqual(p["visibilidade_m"], 9999)  # BECMG nao falou de visibilidade: continua
        self.assertEqual(len(p["pode_ter"]), 1)
        self.assertEqual(p["pode_ter"][0]["rotulo"], "pode ter")
        self.assertIn(p["pode_ter"][0]["categoria"], ("IFR", "MVFR"))

    def test_fm_troca_tudo(self):
        p, _ = self.prev(15, 1)  # 04Z, depois do FM150300
        self.assertTrue(p["vento"].get("variavel"))
        self.assertEqual(p["pode_ter"], [])

    def test_fora_da_validade_nao_inventa(self):
        self.assertIsNone(self.prev(15, 10)[0])  # 13Z: TAF vale ate 12Z
        self.assertIsNone(self.prev(14, 8)[0])  # 11Z: antes do inicio

    def test_sem_taf_ou_erro_de_rede_e_none(self):
        quando = datetime(2026, 10, 14, 11)
        self.assertIsNone(briefing_voo.previsao_na_hora("SBNF", quando, AGORA_UTC, lambda i: {"taf": None}))

        def cai(icao):
            raise RuntimeError("sem rede")
        self.assertIsNone(briefing_voo.previsao_na_hora("SBNF", quando, AGORA_UTC, cai))


class RotasDoVooTestCase(_ComBanco):
    def test_tempo_so_dentro_da_janela_do_taf(self):
        daqui = app._agora_brasilia().replace(tzinfo=None) + timedelta(hours=3)
        vid = self.voo(daqui.date().isoformat(), daqui.strftime("%H:%M"))
        prev = {"icao": "SBNF", "categoria": "VFR"}
        with patch("briefing_voo.previsao_na_hora", return_value=prev) as p:
            r = self.client.get(f"/api/voos/{vid}/tempo").get_json()
        self.assertEqual(r, {"ok": True, "previsao": prev, "motivo": None})
        self.assertEqual(p.call_args[0][0], "SSBL")

        longe = daqui + timedelta(days=3)
        vid2 = self.voo(longe.date().isoformat(), longe.strftime("%H:%M"))
        sem_hora = self.voo(daqui.date().isoformat(), None)
        with patch("briefing_voo.previsao_na_hora") as p:
            self.assertEqual(self.client.get(f"/api/voos/{vid2}/tempo").get_json()["motivo"], "fora_da_janela")
            self.assertEqual(self.client.get(f"/api/voos/{sem_hora}/tempo").get_json()["motivo"], "sem_hora")
        p.assert_not_called()
        with patch("briefing_voo.previsao_na_hora", return_value=None):
            self.assertEqual(self.client.get(f"/api/voos/{vid}/tempo").get_json()["motivo"], "sem_taf")
        self.assertEqual(self.client.get("/api/voos/9999/tempo").status_code, 404)

    def test_horas_com_um_toque_grava_e_devolve_o_total(self):
        self.voo((HOJE - timedelta(days=5)).isoformat(), "09:00", horas=10.0)
        self.voo((HOJE - timedelta(days=2)).isoformat(), "09:00", horas=2.0, tipo="simulador")
        vid = self.voo(HOJE.isoformat(), "10:00")
        r = self.client.post(f"/api/voos/{vid}/horas", json={"horas": 1.24}).get_json()
        self.assertEqual(r, {"ok": True, "horas": 1.2, "horas_min": 672})  # 11,2 h sem o simulador
        self.client.post(f"/api/voos/{vid}/horas", json={"horas": 1.5})  # trocou de ideia
        self.assertEqual(self.sql("SELECT horas FROM voos WHERE id = ?", (vid,))[0][0], 1.5)
        for ruim in (0, -1, 12.5, "1,2", True, None):
            self.assertEqual(self.client.post(f"/api/voos/{vid}/horas", json={"horas": ruim}).status_code, 400, ruim)
        self.assertEqual(self.client.post("/api/voos/9999/horas", json={"horas": 1}).status_code, 404)

    def test_visitante_nao_grava_horas(self):
        vid = self.voo(HOJE.isoformat(), "10:00")
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = __import__("time").time()
        self.assertEqual(self.client.post(f"/api/voos/{vid}/horas", json={"horas": 1.2}).status_code, 403)
        self.assertIsNone(self.sql("SELECT horas FROM voos WHERE id = ?", (vid,))[0][0])

    def test_registrar_voo_com_horas_preenche_o_voo_aberto_do_dia(self):
        vid = self.voo(HOJE.isoformat(), "10:00", destino="SSBL")
        self.chat([("registrar_voo", {"data": HOJE.isoformat(), "destino": "Navegantes", "horas": 1.3})])
        self.assertEqual([tuple(r) for r in self.sql("SELECT id, horas FROM voos")], [(vid, 1.3)])

    def test_dois_voos_abertos_no_dia_nao_adivinha(self):
        self.voo(HOJE.isoformat(), "08:00")
        self.voo(HOJE.isoformat(), "14:00")
        self.chat([("registrar_voo", {"data": HOJE.isoformat(), "destino": "Navegantes", "horas": 1.3})])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM voos")[0][0], 3)


class PosVooTestCase(_ComBanco):
    def fim_estimado(self, conn_voo):
        rota = rota_voo.montar("SSBL", conn_voo.get("escalas"), conn_voo.get("destino", "SSBL"), conn_voo["hora"])
        h, m = (rota["pouso"] or "").split(":") if rota["pouso"] else conn_voo["hora"].split(":")
        extra = 0 if rota["pouso"] else conversa_proativa.POS_VOO_SEM_ESTIMATIVA_MIN
        return datetime.combine(HOJE, time(int(h), int(m))) + timedelta(minutes=extra)

    def test_pergunta_20_min_depois_do_pouso_uma_vez_so(self):
        vid = self.voo(HOJE.isoformat(), "10:00", destino="SSBL", escalas="SBNF")
        fim = self.fim_estimado({"hora": "10:00", "escalas": "SBNF", "destino": "SSBL"})
        conn = db.get_db()
        try:
            self.assertEqual(conversa_proativa.voos_pra_perguntar(conn, fim + timedelta(minutes=19)), [])
            agora = fim + timedelta(minutes=20)
            self.assertEqual(conversa_proativa.voos_pra_perguntar(conn, agora), [vid])
            saida = conversa_proativa.verificar(conn, agora)
            self.assertIn(("pos_voo", "Pousou?", "3 perguntas rápidas no chat e eu somo no diário de bordo."), saida)
            self.assertEqual([s for s in conversa_proativa.verificar(conn, agora) if s[0] == "pos_voo"], [])
            msg = conn.execute("SELECT texto, cards_json FROM chat_mensagens WHERE papel = 'assistant'").fetchall()
        finally:
            conn.close()
        self.assertEqual(len(msg), 1)
        self.assertIn(msg[0]["texto"], conversa_proativa.FRASES_POS_VOO)
        card = json.loads(__import__("criptografia").descriptografar(msg[0]["cards_json"]))[0]
        self.assertEqual((card["type"], card["data"]["id"]), ("diario_bordo", vid))  # leva 22/10

    def test_nao_pergunta_de_voo_com_horas_simulador_ou_tarde_da_noite(self):
        self.voo(HOJE.isoformat(), "08:00", horas=1.0)
        self.voo(HOJE.isoformat(), "08:00", tipo="simulador")
        vid = self.voo(HOJE.isoformat(), "08:00")
        conn = db.get_db()
        try:
            self.assertEqual(conversa_proativa.voos_pra_perguntar(conn, datetime.combine(HOJE, time(13, 0))), [vid])
            self.assertEqual(conversa_proativa.voos_pra_perguntar(conn, datetime.combine(HOJE, time(23, 40))), [])
        finally:
            conn.close()

    def test_card_voo_horas_sugere_perto_da_estimativa_da_rota(self):
        self.voo((HOJE - timedelta(days=3)).isoformat(), "09:00", horas=20.0)
        vid = self.voo(HOJE.isoformat(), "10:00", destino="SSBL", escalas="SBNF")
        conn = db.get_db()
        try:
            card = cards.card_voo_horas(conn, vid, HOJE)
            self.assertIsNone(cards.card_voo_horas(conn, 9999, HOJE))
        finally:
            conn.close()
        d = card["data"]
        rota = rota_voo.montar("SSBL", "SBNF", "SSBL", "10:00")
        minutos = rota["em_voo_min"] + rota_voo.MIN_POR_ESCALA * (len(rota["paradas"]) - 2) + cards.HOBBS_EXTRA_MIN
        est = max(0.3, round(minutos / 60, 1))
        self.assertEqual(d["estimativa"], est)
        self.assertEqual(d["sugestoes"], [round(est - 0.2, 1), est, round(est + 0.2, 1)])
        self.assertEqual((d["rota"], d["horas"], d["horas_min"]), ("SSBL → SBNF → SSBL", None, 1200))

    def test_voo_local_sem_estimativa_usa_chips_padrao(self):
        vid = self.voo(HOJE.isoformat(), "10:00", destino="SSBL")
        conn = db.get_db()
        try:
            d = cards.card_voo_horas(conn, vid, HOJE)["data"]
        finally:
            conn.close()
        self.assertIsNone(d["rota"])
        if d["estimativa"] is None:
            self.assertEqual(d["sugestoes"], [1.0, 1.2, 1.5])


# --------------------------------------------------------- presente todo ano
class PresenteAnualTestCase(_ComBanco):
    def presente(self, titulo, **extra):
        res, r = self.chat([("registrar_tarefa", {
            "titulo": titulo, "quando_data": (HOJE + timedelta(days=12)).isoformat(), "estilo": "presente",
            "ideias": [{"titulo": "Livro"}], **extra})])
        return next(c for c in res.get_json()["cards"] if c["type"] == "presente")["data"]

    def test_titulo_de_aniversario_ou_natal_liga_sozinho_e_a_ia_decide_o_resto(self):
        self.assertTrue(self.presente("Aniversário da mãe")["anual"])
        self.assertTrue(self.presente("Niver do Pedro")["anual"])
        self.assertFalse(self.presente("Presente de despedida do Rafa")["anual"])
        self.assertTrue(self.presente("Dia dos pais", anual=True)["anual"])
        self.assertFalse(self.presente("Natal da firma do amigo secreto", anual=False)["anual"])

    def test_passou_a_data_renova_com_as_ideias_que_sobraram(self):
        ontem = HOJE - timedelta(days=1)
        ideias = [{"titulo": "Kit de jardinagem"}, {"titulo": "Livro"}, {"titulo": "Vaso"}]
        ex = {"anual": True, "ideias": ideias, "escolha": 0, "com_quem": "mãe",
              "historico": [{"ano": ontem.year - 1, "presente": "Flores"}], "lembrete_id": 3}
        tid = self.sql("INSERT INTO tasks (title, due_date, estilo, extras) VALUES ('Aniversário da mãe', ?, 'presente', ?) RETURNING id",
                       (ontem.isoformat(), json.dumps(ex)))[0][0]
        self.sql("INSERT INTO tasks (title, due_date, estilo, extras) VALUES ('Despedida', ?, 'presente', ?)",
                 (ontem.isoformat(), json.dumps({"ideias": ideias})))
        conn = db.get_db()
        try:
            novos = conversa_proativa.renovar_presentes_anuais(conn, HOJE)
            self.assertEqual(conversa_proativa.renovar_presentes_anuais(conn, HOJE), [])  # idempotente
            self.assertEqual(len(novos), 1)
            novo = conn.execute("SELECT title, due_date, extras FROM tasks WHERE id = ?", (novos[0],)).fetchone()
            card = cards.card_compromisso(conn, {"id": novos[0]}, hoje=HOJE)
        finally:
            conn.close()
        self.assertEqual((novo["title"], novo["due_date"]), ("Aniversário da mãe", conversa_proativa._mais_um_ano(ontem).isoformat()))
        nx = json.loads(novo["extras"])
        self.assertEqual([i["titulo"] for i in nx["ideias"]], ["Livro", "Vaso"])
        self.assertEqual(nx["historico"][-1], {"ano": ontem.year, "presente": "Kit de jardinagem"})
        self.assertEqual(nx["com_quem"], "mãe")
        self.assertNotIn("escolha", nx)
        self.assertNotIn("lembrete_id", nx)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 3)
        self.assertEqual(json.loads(self.sql("SELECT extras FROM tasks WHERE id = ?", (tid,))[0][0])["renovado_id"], novos[0])
        self.assertEqual((card["data"]["anual"], card["data"]["ano_passado"]), (True, "Kit de jardinagem"))

    def test_29_de_fevereiro_vira_28(self):
        self.assertEqual(conversa_proativa._mais_um_ano(date(2028, 2, 29)), date(2029, 2, 28))
        self.assertEqual(conversa_proativa._mais_um_ano(date(2026, 10, 14)), date(2027, 10, 14))


if __name__ == "__main__":
    unittest.main()
