"""Assistente passo a passo dos compromissos de sair (2026-11-04, docs/briefings/2026-11-04-cards-ao-vivo.md):
varios compromissos numa frase, parada no caminho (casa -> parada -> destino, 5 min parado), a sequencia de
avisos (15 min antes de se arrumar, se arrumar, 5 min pra sair, sair, chegou) com dedup, a chegada na parada pelo
onde_estou e a previsao que piora (adianta 10 min uma vez so). Banco temporario; Claude, Maps, clima e push
dublados - nenhuma rede."""
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
import cards  # noqa: E402
import notificacoes  # noqa: E402
import onde_estou  # noqa: E402
import push_client  # noqa: E402
import tempo  # noqa: E402
import vida_assistente  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN = "975310"
HOJE = date.today()
EM_3 = (HOJE + timedelta(days=3)).isoformat()
EM_4 = (HOJE + timedelta(days=4)).isoformat()
DIA = date(2026, 11, 6)
CASA = (-26.9000, -49.0000)
GURI = (-26.9500, -49.1000)
VIVA = (-26.9700, -49.1200)


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
        app._CACHE_TRAJETO_AVISO.clear()
        app._CACHE_CLIMA_AVISO.clear()
        onde_estou._cache_trajeto.clear()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": ""}),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None),
                  patch("app._eventos_de_hoje_com_seguranca", return_value=[])):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora, dia=DIA, local=None, parada=None, estilo=None, extras=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, parada, estilo, extras) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (titulo, dia.isoformat(), hora, local, parada, estilo, json.dumps(extras) if extras else None),
        )
        self.conn.commit()
        return cur.lastrowid

    def extras(self, tid):
        return db.extras_tarefa(self.conn, tid)

    def mensagens(self):
        return [r["texto"] for r in self.conn.execute("SELECT texto FROM chat_mensagens ORDER BY id")]


# ---------------------------------------------------------------- varias numa frase
class VariasNumaFraseTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def chat(self, chamadas):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Fechado.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "sexta date 19h, sabado balada 23h no Viva Beach"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def test_prompt_e_ferramenta_pedem_um_registro_por_compromisso_com_parada(self):
        self.assertIn("VARIOS COMPROMISSOS DE SAIR NUMA FRASE", chat_mod.CHAT_SYSTEM_PROMPT)
        self.assertIn("sem emoji", chat_mod.CHAT_SYSTEM_PROMPT.split("VARIOS COMPROMISSOS DE SAIR")[1][:800])
        tools = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        self.assertIn("parada", tools["registrar_tarefa"]["input_schema"]["properties"])
        self.assertIn("parada", tools["ajustar_tarefa"]["input_schema"]["properties"])
        self.assertIn("sem_parada", tools["ajustar_tarefa"]["input_schema"]["properties"])

    def test_dois_compromissos_na_mesma_rodada_cada_um_com_hora_lugar_e_estilo(self):
        corpo, res = self.chat([
            ("registrar_tarefa", {"titulo": "Date", "quando_data": EM_3, "hora": "19:00", "estilo": "date",
                                  "parada": "casa do guri"}),
            ("registrar_tarefa", {"titulo": "Balada", "quando_data": EM_4, "hora": "23:00", "estilo": "balada",
                                  "lugar": "Viva Beach"}),
        ])
        linhas = self.conn.execute("SELECT title, due_date, hora, local, estilo, parada FROM tasks ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in linhas], [
            ("Date", EM_3, "19:00", None, "date", "casa do guri"),
            ("Balada", EM_4, "23:00", "Viva Beach", "balada", None),
        ])
        # sem Maps: casa -> parada 15 + 5 parado + parada -> destino 15 = sai 18:25; a balada so a folga de 15
        self.assertEqual(res[0]["plano"]["sair_de_casa"], "18:25")
        self.assertEqual(res[0]["plano"]["comecar_a_se_arrumar"], "17:45")
        self.assertIn("casa do guri", res[0]["plano"]["parada"])
        self.assertEqual(res[1]["plano"]["sair_de_casa"], "22:45")
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertIn("date", tipos)
        self.assertIn("balada", tipos)
        d = next(c for c in corpo["cards"] if c["type"] == "date")["data"]
        self.assertEqual(d["parada"], {"nome": "casa do guri", "min_ate": 15})
        self.assertEqual(d["sair"], "18:25")
        self.assertNotIn("parada", next(c for c in corpo["cards"] if c["type"] == "balada")["data"])

    def test_parada_com_maps_usa_o_apelido_dentro_da_frase_e_cada_perna(self):
        vida_assistente.salvar_apelido(self.conn, "guri", "Rua do Guri, 10, Brusque")
        vida_assistente.salvar_apelido(self.conn, "viva beach", "Viva Beach, Balneario Camboriu")
        self.conn.commit()
        pernas = {("casa de teste", "Rua do Guri, 10, Brusque"): 10,
                  ("Rua do Guri, 10, Brusque", "Viva Beach, Balneario Camboriu"): 12}
        with patch.dict(os.environ, {"ENDERECO_CASA": "casa de teste"}), \
                patch("maps_client.configurado", return_value=True), \
                patch("maps_client.tempo_de_viagem",
                      side_effect=lambda o, d, **k: {"duracao_minutos": pernas[(o, d)]}):
            corpo, res = self.chat([("registrar_tarefa", {
                "titulo": "Date", "quando_data": EM_3, "hora": "19:00", "estilo": "date",
                "lugar": "viva beach", "parada": "casa do guri"})])
        self.assertEqual(res[0]["plano"]["sair_de_casa"], "18:33")  # 19:00 - (10 + 5 + 12)
        d = next(c for c in corpo["cards"] if c["type"] == "date")["data"]
        self.assertEqual(d["parada"], {"nome": "casa do guri", "min_ate": 10})
        self.assertEqual(d["trajeto_min"], 22)

    def test_previsao_guardada_quando_o_plano_nasce(self):
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Brusque"}), \
                patch("clima.geocodificar_cidade", return_value={"lat": -27.1, "lon": -48.9}), \
                patch("clima.previsao_na_hora", return_value={"temp": 19, "chuva_pct": 30, "codigo": 2}):
            _, res = self.chat([("registrar_tarefa", {"titulo": "Date", "quando_data": EM_3, "hora": "19:00",
                                                      "estilo": "date"})])
        tid = self.conn.execute("SELECT id FROM tasks").fetchone()["id"]
        self.assertEqual(self.extras(tid)["plano_chuva"], {"pct": 30, "hora": "19:00"})

    def test_parada_sem_dia_e_hora_nao_grava(self):
        self.chat([("registrar_tarefa", {"titulo": "Comprar presente", "parada": "shopping"})])
        self.assertIsNone(self.conn.execute("SELECT parada FROM tasks").fetchone()["parada"])

    def test_ajustar_tarefa_poe_e_tira_a_parada_com_desfazer(self):
        self.tarefa("Date", "19:00", dia=HOJE + timedelta(days=3), estilo="date")
        corpo, res = self.chat([("ajustar_tarefa", {"titulo": "Date", "parada": "casa do guri"})])
        self.assertEqual(self.conn.execute("SELECT parada FROM tasks").fetchone()["parada"], "casa do guri")
        self.assertEqual(res[0]["plano"]["sair_de_casa"], "18:25")
        self.assertEqual(res[0]["parada"], {"nome": "casa do guri", "min_ate": 15})
        card = next(c for c in corpo["cards"] if c["type"] == "edicao")
        token = next(a["token"] for a in card["actions"] if a["tipo"] == "desfazer")
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertIsNone(self.conn.execute("SELECT parada FROM tasks").fetchone()["parada"])
        self.chat([("ajustar_tarefa", {"titulo": "Date", "parada": "posto"})])
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Date", "sem_parada": True})])
        self.assertIsNone(self.conn.execute("SELECT parada FROM tasks").fetchone()["parada"])
        self.assertEqual(res[0]["plano"]["sair_de_casa"], "18:45")


# ---------------------------------------------------------------- parada no calculo
class ParadaNoCalculoTestCase(_Base):
    def test_caminho_com_parada_soma_as_pernas_e_os_5_min(self):
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "casa do guri", 10, 12),
                         (27, {"nome": "casa do guri", "min_ate": 10}))
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "posto", None, None),
                         (35, {"nome": "posto", "min_ate": 15}))
        self.assertEqual(notificacoes.caminho_com_parada(20, 15), (20, None))
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "  "), (15, None))
        self.assertEqual(notificacoes.caminho_com_parada(-3, 15), (15, None))

    def test_compromissos_expoe_parada_e_conta_casa_parada_destino(self):
        self.tarefa("Date", "19:00", local="Viva Beach", parada="casa do guri", estilo="date")
        self.tarefa("Balada", "23:00", estilo="balada")
        sem_rede = tempo.compromissos(self.conn, _as("12:00"), rede=False)
        self.assertEqual(sem_rede[0]["parada"], {"nome": "casa do guri", "min_ate": 15})
        self.assertEqual(sem_rede[0]["sair"], _as("18:25"))
        self.assertEqual(sem_rede[0]["comecar"], _as("17:45"))
        self.assertIsNone(sem_rede[1]["parada"])
        with patch("app._trajetos_parada_aviso", return_value=(10, 12)) as pernas:
            com_rede = tempo.compromissos(self.conn, _as("16:00"))
        pernas.assert_called_once_with(self.conn, "casa do guri", "Viva Beach")
        self.assertEqual(com_rede[0]["sair"], _as("18:33"))
        self.assertEqual(com_rede[0]["parada"], {"nome": "casa do guri", "min_ate": 10})
        self.assertEqual(com_rede[0]["ir_min"], 27)

    def test_parada_vira_saida_mesmo_sem_lugar_nem_estilo(self):
        self.tarefa("Consulta", "15:00", parada="farmácia")
        [i] = tempo.compromissos(self.conn, _as("09:00"), rede=False)
        self.assertTrue(i["tem_saida"])
        self.assertEqual(i["sair"], _as("14:25"))

    def test_plano_se_arrumar_com_parada_e_aviso_hora_de_sair_diz_ate_a_parada(self):
        self.tarefa("Date", "19:00", local="Viva Beach", parada="casa do guri", estilo="date")
        chamado = []
        [p] = notificacoes.plano_se_arrumar(
            self.conn, _as("18:00"), 40, trajeto_min=lambda l: self.fail("sem parada nao devia"),
            trajeto_parada=lambda parada, local: chamado.append((parada, local)) or (10, 12))
        self.assertEqual(chamado, [("casa do guri", "Viva Beach")])
        self.assertEqual((p["saida"], p["comecar"]), (_as("18:33"), _as("17:53")))
        avisos = notificacoes.avisos_se_arrumar([p], _as("18:31"))
        sair = next(a for a in avisos if a[0] == "hora_de_sair")
        self.assertEqual(sair[2:], ("Bora, hora de sair", "10 min até casa do guri. Depois Date às 19:00."))

    def test_resolver_parada_acha_o_apelido_dentro_da_frase(self):
        vida_assistente.salvar_apelido(self.conn, "guri", "Rua do Guri, 10")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "casa do guri"), "Rua do Guri, 10")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "o guri"), "Rua do Guri, 10")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "posto Ipiranga"), "posto Ipiranga")
        self.assertIsNone(vida_assistente.apelido_dentro(self.conn, "gurizada"))


# ---------------------------------------------------------------- sequencia de avisos
class SequenciaDeAvisosTestCase(_Base):
    def rodar(self, agora, clima=None):
        enviados = []

        def falso(sub, titulo, corpo, url="", tag="", **_):
            enviados.append({"titulo": titulo, "corpo": corpo, "tag": tag, "url": url})
            return True

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        if not db.list_push_subscriptions(self.conn):
            db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
            self.conn.commit()
        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=falso), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._clima_na_hora", return_value=clima), \
                patch.object(onde_estou, "_avisar", return_value=True), \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("app.date", type("D", (), {"today": staticmethod(lambda: agora.date()),
                                                   "fromisoformat": staticmethod(datetime.fromisoformat)})):
            app.verificar_e_notificar()
        return [e for e in enviados if "De novo ·" not in e["titulo"] and "Última chamada ·" not in e["titulo"]]

    def test_os_cinco_passos_um_de_cada_sem_duplicar(self):
        tid = self.tarefa("Date com a Júlia", "20:00", estilo="date")  # sem Maps: sai 19:45, arruma 19:05
        clima = {"temp": 16, "chuva_pct": 55}
        por_tag = {}
        for hm in ("18:40", "18:52", "18:55", "19:05", "19:10", "19:38", "19:40", "19:43", "19:47"):
            for e in self.rodar(_as(hm), clima):
                if e["tag"].endswith(f"-{tid}"):
                    por_tag.setdefault(e["tag"].rsplit("-", 1)[0], []).append((hm, e))
        self.assertEqual(sorted(por_tag), ["hora_de_sair", "saida_porta", "saida_preparo", "se_arrumar"])
        for tipo, lista in por_tag.items():
            self.assertEqual(len(lista), 1, (tipo, lista))
        hm, e = por_tag["saida_preparo"][0]
        self.assertEqual(hm, "18:52")
        self.assertEqual(e["titulo"], "🪞 Daqui 13 min")
        self.assertEqual(e["corpo"], "Começa a se arrumar pro date com a Júlia. 16° e 55% de chuva às 20h. "
                                     "Leva guarda-chuva e casaco.")
        self.assertEqual(por_tag["se_arrumar"][0][0], "19:05")
        hm, e = por_tag["saida_porta"][0]
        self.assertEqual((hm, e["titulo"], e["corpo"]), ("19:38", "🚗 7 min pra sair", "Leva guarda-chuva e casaco."))
        self.assertEqual(por_tag["hora_de_sair"][0][0], "19:43")

    def test_sem_clima_o_porta_lembra_o_basico_e_a_lista_do_lugar(self):
        tid = self.tarefa("Festa da faculdade", "22:00")
        [e] = [x for x in self.rodar(_as("21:38")) if x["tag"] == f"saida_porta-{tid}"]
        self.assertEqual(e["corpo"], "Leva notebook, carregador e crachá.")
        tid2 = self.tarefa("Balada", "23:30", estilo="balada")
        [e] = [x for x in self.rodar(_as("23:08")) if x["tag"] == f"saida_porta-{tid2}"]
        self.assertEqual(e["corpo"], "Leva chave, carteira e celular.")

    def test_balada_tarde_passa_pelo_silencio(self):
        tid = self.tarefa("Balada", "23:00", estilo="balada")  # sai 22:45, arruma 22:05: dentro do 22-07
        tags = [e["tag"] for e in self.rodar(_as("21:52"))]
        self.assertIn(f"saida_preparo-{tid}", tags)

    def test_passos_com_tarefa_se_arrumar_marcada_nao_mandam_o_15_min_antes(self):
        self.tarefa("Date", "20:00", estilo="date")
        self.tarefa("Me arrumar pro date", "19:05")
        planos = notificacoes.plano_se_arrumar(self.conn, _as("18:52"), 40)
        self.assertEqual(tempo.passos_da_saida(self.conn, planos, _as("18:52")), [])

    def test_tipos_novos_no_catalogo_e_urgentes(self):
        from assistente import avisos

        for tipo in ("saida_preparo", "saida_porta", "saida_previsao", "saida_parada", "saida_chegou"):
            self.assertIn(tipo, avisos.TIPOS)
        self.assertIn("saida_preparo", app.NOTIFICACOES_URGENTES)
        self.assertIn("saida_porta", app.NOTIFICACOES_URGENTES)


# ---------------------------------------------------------------- chegada (onde_estou)
class ChegadaNaParadaTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.reagir = patch.object(onde_estou, "REAGIR_EM_THREAD", False)
        self.reagir.start()
        self.addCleanup(self.reagir.stop)
        env = patch.dict(os.environ, {"ENDERECO_CASA": f"{CASA[0]},{CASA[1]}", "GOOGLE_MAPS_API_KEY": "falsa"})
        env.start()
        self.addCleanup(env.stop)
        for p in (patch("maps_client.configurado", return_value=True),
                  patch("maps_client.usar_cota", return_value=True),
                  patch("maps_client.geocodificar", return_value=VIVA),
                  patch("maps_client.tempo_de_viagem", return_value={"duracao_minutos": 12})):
            p.start()
            self.addCleanup(p.stop)
        self.aviso = patch.object(onde_estou, "_avisar", return_value=True)
        self.avisar = self.aviso.start()
        self.addCleanup(self.aviso.stop)
        vida_assistente.salvar_apelido(self.conn, "guri", f"{GURI[0]},{GURI[1]}")
        self.conn.commit()
        self.tid = self.tarefa("Date com a Júlia", "19:00", dia=HOJE, local="Viva Beach", parada="casa do guri",
                               estilo="date")

    def visita(self, ponto, chegada):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": 30.0, "chegada": chegada, "saida": None}
        return onde_estou.registrar(self.conn, dados, chegada)[0]

    def test_chegou_na_parada_diz_a_hora_de_sair_e_de_chegar_uma_vez(self):
        vid = self.visita(GURI, _as("18:40", HOJE))
        self.assertIn("chegada_saida", onde_estou.reagir(self.conn, vid, _as("18:41", HOJE)))
        # 19:00 - 12 min = 18:48 (mais que os 5 min parado a partir de 18:41)
        self.assertEqual(self.mensagens()[0], "Chegou na casa do guri. Saindo 18:48 tu chega 19:00.")
        self.avisar.assert_called_once_with(self.conn, "saida_parada", self.tid, "Chegou na casa do guri",
                                            "Saindo 18:48 tu chega 19:00.", _as("18:41", HOJE))
        # saiu e voltou no guri no mesmo dia: o passo nao repete (cai no "chegou" comum, que nao tem nada a dizer
        # alem da proxima)
        vid2 = self.visita(GURI, _as("18:50", HOJE))
        onde_estou.reagir(self.conn, vid2, _as("18:51", HOJE))
        self.assertFalse(any(m.startswith("Chegou na casa do guri. Saindo") for m in self.mensagens()[1:]))

    def test_chegou_atrasado_na_parada_conta_a_partir_de_agora(self):
        vid = self.visita(GURI, _as("18:50", HOJE))
        onde_estou.reagir(self.conn, vid, _as("18:50", HOJE))
        self.assertEqual(self.mensagens()[0], "Chegou na casa do guri. Saindo 18:55 tu chega 19:07.")

    def test_chegou_no_destino_sem_apelido_salvo(self):
        vid = self.visita(VIVA, _as("19:05", HOJE))
        self.assertIn("chegada_saida", onde_estou.reagir(self.conn, vid, _as("19:05", HOJE)))
        self.assertEqual(self.mensagens()[0], "Chegou na Viva Beach.")
        self.avisar.assert_called_once_with(self.conn, "saida_chegou", self.tid, "Chegou na Viva Beach",
                                            "5 min depois das 19h.", _as("19:05", HOJE))

    def test_em_texto_genero_e_maiuscula(self):
        self.assertEqual(onde_estou._em_texto("casa do guri"), "na casa do guri")
        self.assertEqual(onde_estou._em_texto("Casa do guri"), "na casa do guri")
        self.assertEqual(onde_estou._em_texto("o guri"), "no guri")
        self.assertEqual(onde_estou._em_texto("Lume", ["jantar no Lume"]), "no Lume")
        self.assertEqual(onde_estou._em_texto("posto"), "no posto")


# ---------------------------------------------------------------- previsao que piora
class PrevisaoQuePioraTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.aviso = patch.object(onde_estou, "_avisar", return_value=True)
        self.avisar = self.aviso.start()
        self.addCleanup(self.aviso.stop)

    def rodar(self, agora, pct):
        with patch("app._clima_aviso", return_value={"temp": 18, "chuva_pct": pct}):
            return tempo.previsao_que_piora(self.conn, agora)

    def test_passa_de_70_adianta_10_min_uma_vez_so(self):
        tid = self.tarefa("Date", "20:00", estilo="date", extras={"plano_chuva": {"pct": 40, "hora": "20:00"}})
        self.rodar(_as("15:00"), 60)
        self.assertNotIn("adiantar_min", self.extras(tid))
        self.rodar(_as("16:00"), 75)
        e = self.extras(tid)
        self.assertEqual(e["adiantar_min"], 10)
        self.assertEqual((e["previsao_piorou"]["de"], e["previsao_piorou"]["para"]), (40, 75))
        self.assertEqual(self.mensagens(), ["A previsão piorou: 75% de chuva às 20h. Adiantei a saída pra 19:35."])
        self.avisar.assert_called_once_with(self.conn, "saida_previsao", tid, "A previsão piorou",
                                            "75% de chuva às 20h. Adiantei a saída pra 19:35.", _as("16:00"))
        # os avisos e a fita usam a saida nova
        [p] = notificacoes.plano_se_arrumar(self.conn, _as("16:05"), 40)
        self.assertEqual((p["saida"], p["comecar"]), (_as("19:35"), _as("18:55")))
        self.assertEqual(tempo.compromissos(self.conn, _as("16:05"), rede=False)[0]["sair"], _as("19:35"))
        # piorou mais: nao adianta de novo nem repete o aviso
        self.rodar(_as("17:00"), 95)
        self.assertEqual(self.extras(tid)["adiantar_min"], 10)
        self.assertEqual(len(self.mensagens()), 1)
        self.avisar.assert_called_once()

    def test_sem_previsao_guardada_guarda_a_de_agora_e_ja_alta_nao_mexe(self):
        tid = self.tarefa("Balada", "23:00", estilo="balada")
        self.rodar(_as("15:00"), 80)
        self.assertEqual(self.extras(tid)["plano_chuva"], {"pct": 80, "hora": "23:00"})
        self.rodar(_as("16:00"), 95)
        self.assertNotIn("adiantar_min", self.extras(tid))
        self.assertEqual(self.mensagens(), [])

    def test_hora_mudou_guarda_de_novo_e_depois_de_sair_nao_mexe(self):
        tid = self.tarefa("Date", "20:00", estilo="date", extras={"plano_chuva": {"pct": 20, "hora": "19:00"}})
        self.rodar(_as("15:00"), 75)  # previsao guardada era pra outra hora: so guarda a nova
        self.assertEqual(self.extras(tid)["plano_chuva"], {"pct": 75, "hora": "20:00"})
        self.assertNotIn("adiantar_min", self.extras(tid))
        tid2 = self.tarefa("Festa", "21:00", extras={"plano_chuva": {"pct": 10, "hora": "21:00"}})
        self.rodar(_as("20:50"), 90)  # ja passou da hora de sair (20:45)
        self.assertNotIn("adiantar_min", self.extras(tid2))

    def test_esta_na_lista_do_tick(self):
        import inspect

        import conversa_proativa

        self.assertIn("tempo.previsao_que_piora", inspect.getsource(conversa_proativa.verificar))


if __name__ == "__main__":
    unittest.main()
