"""O que a conversa de 04/11 mostrou (2026-11-05, docs/briefings/2026-11-05-conversa-04-11.md): o lugar do date
contado depois ficava so no titulo (saida com a folga de casa), a hora dita era tratada como chegada quando era a
de sair, tarefa com dia ficava sem hora, a previsao de outro dia nao tinha a temperatura da noite e quem e quem
nao ficava guardado. Banco temporario; Claude, Maps e clima dublados - nenhuma rede."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import clima  # noqa: E402
import notificacoes  # noqa: E402
import tempo  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN = "975310"
HOJE = date.today()
EM_3 = (HOJE + timedelta(days=3)).isoformat()
DIA = date(2026, 11, 6)


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


def _as(hhmm: str, dia: date = DIA) -> datetime:
    return datetime.combine(dia, time(*map(int, hhmm.split(":"))))


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()
        tempo.limpar_cache()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None),
                  patch("app._eventos_de_hoje_com_seguranca", return_value=[])):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora, dia=DIA, local=None, estilo=None, sai_na_hora=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, estilo, sai_na_hora) VALUES (?, ?, ?, ?, ?, ?)",
            (titulo, dia.isoformat() if isinstance(dia, date) else dia, hora, local, estilo, sai_na_hora),
        )
        self.conn.commit()
        return cur.lastrowid

    def chat(self, chamadas, mensagem="oi"):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Fechado.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def linha(self, tid=None):
        if tid is None:
            return self.conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchone()
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()


class PromptEFerramentasTestCase(unittest.TestCase):
    def test_ajustar_tarefa_aceita_lugar_com_quem_e_sai_na_hora(self):
        tools = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        props = tools["ajustar_tarefa"]["input_schema"]["properties"]
        for campo in ("lugar", "com_quem", "sai_na_hora"):
            self.assertIn(campo, props)
        self.assertEqual(props["sai_na_hora"]["type"], "boolean")
        self.assertIn("sai_na_hora", tools["registrar_tarefa"]["input_schema"]["properties"])

    def test_regras_novas_no_prompt(self):
        p = chat_mod.CHAT_SYSTEM_PROMPT
        self.assertIn("TAREFA COM DIA GANHA HORA", p)
        self.assertIn("LUGAR CONTADO DEPOIS", p)
        self.assertIn("HORA DE SAIR OU DE CHEGAR", p)
        self.assertIn("QUEM E QUEM", p)
        # a regra velha mandava deixar sem hora a tarefa "solta" com dia (quinta 05/11 ficou toda sem hora)
        self.assertNotIn("segue sem hora mesmo", p)

    def test_clima_fala_do_hora_a_hora(self):
        tools = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        self.assertIn("hora_a_hora", tools["consultar_clima"]["description"])


class LugarDepoisTestCase(_Base):
    def test_lugar_contado_depois_vai_pra_coluna_e_volta_o_plano(self):
        tid = self.tarefa("Date", "19:00", dia=EM_3, estilo="date")
        corpo, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "lugar": "Shopping Vizinho",
                                                    "com_quem": "Vitoria"})])
        self.assertTrue(r["ok"])
        self.assertEqual(self.linha(tid)["local"], "Shopping Vizinho")
        self.assertEqual(db.extras_tarefa(self.conn, tid)["com_quem"], "Vitoria")
        self.assertEqual(r["plano"]["sair_de_casa"], "18:45")  # sem Maps: a folga de 15 min
        # Desfazer tira o lugar
        card = next(c for c in corpo["cards"] if c["type"] == "edicao")
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertIsNone(self.linha(tid)["local"])

    def test_lugar_com_maps_saida_de_verdade(self):
        self.tarefa("Date", "19:00", dia=EM_3, estilo="date")
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste"}), \
                patch("maps_client.configurado", return_value=True), \
                patch("maps_client.horario_de_saida",
                      return_value={"sair": "17:56", "duracao_minutos": 59, "trajeto_min": 59}), \
                patch("app._saida_do_maps", return_value={"sair": "17:56", "trajeto_min": 59}):
            _, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "lugar": "Shopping Vizinho"})])
        self.assertEqual(r["plano"]["sair_de_casa"], "17:56")
        self.assertEqual(r["plano"]["ida_min"], 59)

    def test_so_com_quem_nao_da_erro(self):
        tid = self.tarefa("Date", "19:00", dia=EM_3, estilo="date")
        _, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "com_quem": "Vitoria"})])
        self.assertTrue(r["ok"])
        self.assertEqual(db.extras_tarefa(self.conn, tid)["com_quem"], "Vitoria")


class SaiNaHoraTestCase(_Base):
    def _maps_59(self):
        return (patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste"}),
                patch("maps_client.configurado", return_value=True),
                patch("app._saida_pro_compromisso", return_value=None),
                patch("maps_client.tempo_de_viagem", return_value={"duracao_minutos": 59}))

    def test_registrar_com_sai_na_hora_sai_19_e_chega_19_59(self):
        a, b, c, d = self._maps_59()
        with a, b, c, d:
            corpo, [r] = self.chat([("registrar_tarefa", {
                "titulo": "Date com a Vitoria", "quando_data": EM_3, "hora": "19:00", "estilo": "date",
                "lugar": "Shopping Vizinho", "sai_na_hora": True})])
        self.assertEqual(self.linha()["sai_na_hora"], 1)
        self.assertEqual(r["plano"]["sair_de_casa"], "19:00")
        self.assertEqual(r["plano"]["chega_no_lugar"], "19:59")
        self.assertEqual(r["plano"]["comecar_a_se_arrumar"], "18:20")  # 40 min, o padrao
        d = next(c for c in corpo["cards"] if c["type"] == "date")["data"]
        self.assertEqual((d["sair"], d["chegada"], d["sai_na_hora"]), ("19:00", "19:59", True))
        self.assertEqual([p["rotulo"] for p in d["cadeia"]], ["Se arrumar", "Sair", "Chegar"])
        self.assertEqual([p["hora"] for p in d["cadeia"]], ["18:20", "19:00", "19:59"])

    def test_registrar_sem_flag_continua_chegada(self):
        _, [r] = self.chat([("registrar_tarefa", {"titulo": "Date", "quando_data": EM_3, "hora": "19:00",
                                                  "estilo": "date", "sai_na_hora": "sim"})])
        self.assertIsNone(self.linha()["sai_na_hora"])  # so True de verdade liga
        self.assertEqual(r["plano"]["sair_de_casa"], "18:45")

    def test_ajustar_marca_e_desmarca_sai_na_hora(self):
        tid = self.tarefa("Date", "19:00", dia=EM_3, local="Shopping Vizinho", estilo="date")
        a, b, c, d = self._maps_59()
        with a, b, c, d:
            corpo, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "sai_na_hora": True})])
        self.assertEqual(self.linha(tid)["sai_na_hora"], 1)
        self.assertEqual((r["plano"]["sair_de_casa"], r["plano"]["chega_no_lugar"]), ("19:00", "19:59"))
        _, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "sai_na_hora": False})])
        self.assertIsNone(self.linha(tid)["sai_na_hora"])
        self.assertEqual(r["plano"]["sair_de_casa"], "18:45")

    def test_sem_maps_chega_com_a_folga(self):
        self.tarefa("Date", "19:00", dia=EM_3, local="Shopping Vizinho", estilo="date")
        _, [r] = self.chat([("ajustar_tarefa", {"titulo": "Date", "sai_na_hora": True})])
        self.assertEqual((r["plano"]["sair_de_casa"], r["plano"]["chega_no_lugar"]), ("19:00", "19:15"))

    def test_avisos_mandam_sair_na_hora(self):
        self.tarefa("Date", "19:00", local="Shopping Vizinho", estilo="date", sai_na_hora=1)
        [p] = notificacoes.plano_se_arrumar(self.conn, _as("17:00"), 45, trajeto_min=lambda l: 59)
        self.assertEqual((p["saida"], p["comecar"]), (_as("19:00"), _as("18:15")))
        # sem a marca, a mesma tarefa sairia 18:01
        self.conn.execute("UPDATE tasks SET sai_na_hora = NULL")
        [p] = notificacoes.plano_se_arrumar(self.conn, _as("17:00"), 45, trajeto_min=lambda l: 59)
        self.assertEqual(p["saida"], _as("18:01"))

    def test_ilha_e_widget_saem_na_hora_e_chegam_depois(self):
        self.tarefa("Date", "19:00", local="Shopping Vizinho", estilo="date", sai_na_hora=1)
        [i] = tempo.compromissos(self.conn, _as("12:00"), rede=False)
        self.assertEqual(i["sair"], _as("19:00"))
        self.assertEqual(i["evento"], _as("19:15"))  # sem rede: a folga de 15 min
        self.assertEqual(i["ir_min"], 15)
        with patch("tempo._trajeto_local", return_value=59):
            tempo.limpar_cache()
            [i] = tempo.compromissos(self.conn, _as("17:00"))
        self.assertEqual((i["sair"], i["evento"]), (_as("19:00"), _as("19:59")))

    def test_virando_a_meia_noite_o_card_fica_so_com_a_saida(self):
        tid = self.tarefa("Balada", "23:30", dia=EM_3, estilo="balada", sai_na_hora=1)
        import cards
        card = cards.card_compromisso(self.conn, {"id": tid, "saida": {"sair": "22:00", "trajeto_min": 60}})
        self.assertEqual(card["data"]["sair"], "23:30")
        self.assertNotIn("chegada", card["data"])


class HoraAHoraTestCase(_Base):
    HORAS = [{"quando": f"2026-11-06T{h:02d}:00", "chuva_pct": 10 if h < 23 else 52, "mm": 0, "codigo": 2,
              "temp": 27 - (h - 15) if h >= 15 else 20} for h in range(24)]

    def test_texto_so_das_horas_pedidas(self):
        t = clima.hora_a_hora_texto(self.HORAS, _as("19:00"), _as("21:00"))
        self.assertEqual(t, "19h 23° 10%, 20h 22° 10%, 21h 21° 10%")
        self.assertIsNone(clima.hora_a_hora_texto([], _as("19:00"), _as("21:00")))
        sem_temp = [{"quando": "2026-11-06T19:00", "chuva_pct": 5, "temp": None}, {"quando": "lixo"}]
        self.assertEqual(clima.hora_a_hora_texto(sem_temp, _as("19:00"), _as("21:00")), "19h 5%")

    def test_previsao_de_outro_dia_traz_a_noite(self):
        dia = (HOJE + timedelta(days=2)).isoformat()
        horas = [dict(h, quando=h["quando"].replace("2026-11-06", dia)) for h in self.HORAS]
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), \
                patch("clima.geocodificar_cidade", return_value={"lat": -27.1, "lon": -48.9, "nome": "Brusque"}), \
                patch("clima.previsao_para_data", return_value={"min": 17, "max": 27, "chuva_pct": 43}), \
                patch("clima.previsao_horaria", return_value=horas) as ph:
            _, [r] = self.chat([("consultar_clima", {"data": dia})])
        self.assertEqual(ph.call_args[0][2], 4)
        self.assertIn("23h 19° 52%", r["hora_a_hora"])
        self.assertTrue(r["hora_a_hora"].startswith("0h 20°"))
        self.assertEqual(r["max"], 27)

    def test_sem_hora_a_hora_continua_com_o_dia(self):
        dia = (HOJE + timedelta(days=2)).isoformat()
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), \
                patch("clima.geocodificar_cidade", return_value={"lat": -27.1, "lon": -48.9, "nome": "Brusque"}), \
                patch("clima.previsao_para_data", return_value={"min": 17, "max": 27}), \
                patch("clima.previsao_horaria", return_value=None):
            _, [r] = self.chat([("consultar_clima", {"data": dia})])
        self.assertNotIn("hora_a_hora", r)
        self.assertEqual(r["min"], 17)

    def test_atividade_com_hora_tambem_traz(self):
        dia = (HOJE + timedelta(days=2)).isoformat()
        horas = [dict(h, quando=h["quando"].replace("2026-11-06", dia)) for h in self.HORAS]
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), \
                patch("clima.geocodificar_cidade", return_value={"lat": -27.1, "lon": -48.9, "nome": "Brusque"}), \
                patch("clima.previsao_horaria", return_value=horas):
            _, [r] = self.chat([("consultar_clima", {"data": dia, "hora": "19:00", "janela_horas": 2})])
        self.assertEqual(r["hora_a_hora"], "19h 23° 10%, 20h 22° 10%, 21h 21° 10%")


if __name__ == "__main__":
    unittest.main()
