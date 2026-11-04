"""Leva "onde eu estou" (2026-11-04): visitas do iPhone -> chegada, atraso com Desfazer e contexto
do chat (onde_estou.py + rotas/onde_estou.py). Banco temporario; Maps, push e Telegram dublados."""

import json
import os
import tempfile
import time as _time
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
import onde_estou  # noqa: E402
import vida_assistente  # noqa: E402

PIN = "246813"
TOKEN = "token-de-teste-visitas"
CABECALHO = {"Authorization": f"Bearer {TOKEN}"}
CASA = (-26.9000, -49.0000)
MECANICO = (-26.9100, -49.0600)
HOJE = date.today()


def _em(hhmm: str) -> datetime:
    return datetime.combine(HOJE, time(*map(int, hhmm.split(":"))))


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()
        onde_estou._cache_trajeto.clear()
        self._reagir = patch.object(onde_estou, "REAGIR_EM_THREAD", False)
        self._reagir.start()
        self.addCleanup(self._reagir.stop)
        env = {"PAINEL_WIDGET_TOKEN": TOKEN, "ENDERECO_CASA": f"{CASA[0]},{CASA[1]}",
               "GOOGLE_MAPS_API_KEY": "chave-falsa"}
        self._env = patch.dict(os.environ, env)
        self._env.start()
        self.addCleanup(self._env.stop)
        self.geo = patch("maps_client.geocodificar", return_value=MECANICO)
        self.geocodificar = self.geo.start()
        self.addCleanup(self.geo.stop)
        self.viagem = patch("maps_client.tempo_de_viagem", return_value={"duracao_minutos": 25})
        self.tempo_de_viagem = self.viagem.start()
        self.addCleanup(self.viagem.stop)
        p = patch("maps_client.usar_cota", return_value=True)
        p.start()
        self.addCleanup(p.stop)
        self.aviso = patch.object(onde_estou, "_avisar", return_value=True)
        self.avisar = self.aviso.start()
        self.addCleanup(self.aviso.stop)
        vida_assistente.salvar_apelido(self.conn, "o mecânico", "Rua do Mecânico, 100, Brusque")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora=None, local=None, inegociavel=0, dia=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, inegociavel) VALUES (?, ?, ?, ?, ?)",
            (titulo, (dia or HOJE).isoformat(), hora, local, inegociavel),
        )
        self.conn.commit()
        return cur.lastrowid

    def visita(self, ponto, chegada: datetime, saida: datetime | None = None, precisao=30.0):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": precisao, "chegada": chegada, "saida": saida}
        return onde_estou.registrar(self.conn, dados, chegada if saida is None else saida)[0]

    def hora(self, tid):
        return self.conn.execute("SELECT hora, title FROM tasks WHERE id = ?", (tid,)).fetchone()

    def mensagens(self):
        return [dict(r) for r in self.conn.execute("SELECT texto, cards_json FROM chat_mensagens ORDER BY id")]


class RotaTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()

    def corpo(self, **extra):
        agora = datetime.now()
        base = {"lat": -26.912345, "lon": -49.067891, "precisao": 35,
                "chegada": (agora - timedelta(minutes=5)).isoformat(timespec="seconds"), "saida": None}
        base.update(extra)
        return base

    def contar(self):
        return self.conn.execute("SELECT COUNT(*) n FROM visitas").fetchone()["n"]

    def test_sem_token_ou_errado_e_401_e_nao_grava(self):
        self.assertEqual(self.client.post("/api/localizacao/visita", json=self.corpo()).status_code, 401)
        r = self.client.post("/api/localizacao/visita", json=self.corpo(), headers={"Authorization": "Bearer errado"})
        self.assertEqual(r.status_code, 401)
        # token na URL nao vale (localizacao/token nunca na URL)
        r = self.client.post(f"/api/localizacao/visita?token={TOKEN}", json=self.corpo())
        self.assertEqual(r.status_code, 401)
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": ""}):
            r = self.client.post("/api/localizacao/visita", json=self.corpo(), headers={"Authorization": "Bearer "})
            self.assertEqual(r.status_code, 401)
        self.assertEqual(self.contar(), 0)

    def test_modo_visitante_recusa(self):
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = _time.time()
        r = self.client.post("/api/localizacao/visita", json=self.corpo(), headers=CABECALHO)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.contar(), 0)

    def test_grava_arredondado_e_hora_local(self):
        r = self.client.post("/api/localizacao/visita", headers=CABECALHO,
                             json=self.corpo(chegada="2026-11-04T10:20:00Z", lat=-26.912345, lon=-49.067891))
        self.assertEqual(r.status_code, 200, r.get_json())
        v = self.conn.execute("SELECT * FROM visitas").fetchone()
        self.assertEqual((v["lat"], v["lon"]), (-26.9123, -49.0679))
        self.assertEqual(v["chegada"], "2026-11-04T07:20:00")  # Brasilia (UTC-3)
        self.assertIsNone(v["saida"])

    def test_corpo_invalido_400(self):
        agora = datetime.now()
        futuro = (agora + timedelta(hours=2)).isoformat(timespec="seconds")
        for corpo in ([1], {}, {"lat": "x", "lon": 1, "chegada": "2026-11-04T10:00:00"},
                      {"lat": 0, "lon": 0, "chegada": "2026-11-04T10:00:00"},
                      {"lat": 95, "lon": 1, "chegada": "2026-11-04T10:00:00"},
                      self.corpo(chegada=None), self.corpo(chegada="ontem"), self.corpo(chegada=futuro),
                      self.corpo(chegada="2026-11-04T10:00:00", saida="2026-11-04T09:00:00"),
                      self.corpo(lat=float("nan"))):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post("/api/localizacao/visita", headers=CABECALHO,
                                                  json=corpo).status_code, 400)
        self.assertEqual(self.contar(), 0)

    def test_chegou_e_saiu_viram_uma_visita_e_repetido_nao_duplica(self):
        corpo = self.corpo()
        r1 = self.client.post("/api/localizacao/visita", headers=CABECALHO, json=corpo).get_json()
        r2 = self.client.post("/api/localizacao/visita", headers=CABECALHO, json=corpo).get_json()
        self.assertTrue(r1["nova"])
        self.assertFalse(r2["nova"])
        saida = datetime.now().isoformat(timespec="seconds")
        r3 = self.client.post("/api/localizacao/visita", headers=CABECALHO,
                              json={**corpo, "lat": -26.9124, "saida": saida}).get_json()
        self.assertEqual(r3["id"], r1["id"])
        self.assertEqual(self.contar(), 1)
        self.assertEqual(self.conn.execute("SELECT saida FROM visitas").fetchone()["saida"], saida)

    def test_retencao_30_dias(self):
        velho = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
        self.conn.execute("INSERT INTO visitas (lat, lon, chegada, saida) VALUES (1, 1, ?, ?)", (velho, velho))
        self.conn.commit()
        self.client.post("/api/localizacao/visita", headers=CABECALHO, json=self.corpo())
        self.assertEqual(self.contar(), 1)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM visitas WHERE lat = 1").fetchone())

    def test_chegada_pela_rota_avisa_uma_vez_so(self):
        self.tarefa("Levar o carro no mecânico")
        corpo = self.corpo(lat=MECANICO[0], lon=MECANICO[1])
        self.client.post("/api/localizacao/visita", headers=CABECALHO, json=corpo)
        self.client.post("/api/localizacao/visita", headers=CABECALHO, json=corpo)
        textos = [m["texto"] for m in self.mensagens()]
        self.assertEqual(len(textos), 1)
        self.assertTrue(textos[0].startswith("Chegou no mecânico. Agora é: levar o carro no mecânico."), textos)
        self.assertEqual(self.avisar.call_count, 1)
        self.assertEqual(self.avisar.call_args[0][1], onde_estou.TIPO_CHEGADA)


class LugarTestCase(_Base):
    def test_reconhece_apelido_e_casa_pelo_raio(self):
        perto = (MECANICO[0] + 0.0009, MECANICO[1])  # ~100 m
        longe = (MECANICO[0] + 0.004, MECANICO[1])  # ~445 m
        v1 = self.visita(perto, _em("07:00"), _em("07:10"))
        v2 = self.visita(longe, _em("08:00"), _em("08:10"))
        v3 = self.visita(CASA, _em("09:00"))
        lugares = {r["id"]: r["lugar"] for r in self.conn.execute("SELECT id, lugar FROM visitas")}
        self.assertEqual(lugares, {v1: "mecanico", v2: None, v3: "casa"})
        self.assertEqual(self.geocodificar.call_count, 1)  # geocodifica uma vez e guarda
        guardado = json.loads(db.obter_configuracao(self.conn, onde_estou.CONFIG_COORDS))
        self.assertEqual(guardado["mecanico"]["lat"], MECANICO[0])

    def test_endereco_mudou_geocodifica_de_novo(self):
        onde_estou.lugares_com_coordenada(self.conn)
        vida_assistente.salvar_apelido(self.conn, "mecânico", "Outra rua, 5")
        onde_estou.lugares_com_coordenada(self.conn)
        self.assertEqual(self.geocodificar.call_count, 2)

    def test_salvar_apelido_pelo_chat_ja_geocodifica(self):
        self.assertTrue(onde_estou.garantir_coordenada(self.conn, "mecanico"))
        self.geocodificar.side_effect = ValueError("nao achei")
        vida_assistente.salvar_apelido(self.conn, "obra", "lugar que nao existe")
        self.assertFalse(onde_estou.garantir_coordenada(self.conn, "obra"))
        self.assertFalse(onde_estou.garantir_coordenada(self.conn, "obra"))
        self.assertEqual(self.geocodificar.call_count, 2)  # falha fica marcada no dia

    def test_visita_nova_fecha_a_aberta_esquecida(self):
        v1 = self.visita(CASA, _em("07:00"))
        self.visita(MECANICO, _em("07:20"))
        self.assertEqual(self.conn.execute("SELECT saida FROM visitas WHERE id = ?", (v1,)).fetchone()["saida"],
                         _em("07:20").isoformat(timespec="seconds"))


class ChegadaTestCase(_Base):
    def test_mensagem_com_tarefa_do_lugar_e_proxima_com_hora(self):
        self.tarefa("Levar o carro no mecânico", "07:30")
        self.tarefa("Imprimir as contas", "11:00")
        self.tarefa("Coisa de amanhã", "09:00", dia=HOJE + timedelta(days=1))
        vid = self.visita(MECANICO, _em("07:20"))
        self.assertEqual(onde_estou.reagir(self.conn, vid, _em("07:22")), ["chegada"])
        self.assertEqual(self.mensagens()[0]["texto"],
                         "Chegou no mecânico. Agora é: levar o carro no mecânico. Depois: imprimir as contas às 11h.")
        self.avisar.assert_called_once_with(self.conn, onde_estou.TIPO_CHEGADA, vid, "Chegou no mecânico",
                                            "Agora é: levar o carro no mecânico. Depois: imprimir as contas às 11h.",
                                            _em("07:22"))
        # uma por visita: o tick de 5 min e o POST repetido nao repetem
        self.assertEqual(onde_estou.reagir(self.conn, vid, _em("07:27")), [])
        onde_estou.verificar(self.conn, _em("07:32"))
        self.assertEqual(len(self.mensagens()), 1)
        # nao da baixa sozinho
        self.assertEqual(self.conn.execute("SELECT COUNT(*) n FROM tasks WHERE completed_at IS NOT NULL")
                         .fetchone()["n"], 0)

    def test_casa_e_feminino(self):
        self.tarefa("Arrumar o quarto", "19:00")
        vid = self.visita(CASA, _em("18:00"))
        onde_estou.reagir(self.conn, vid, _em("18:01"))
        self.assertEqual(self.mensagens()[0]["texto"], "Chegou em casa. Próxima: arrumar o quarto às 19h.")
        vida_assistente.salvar_apelido(self.conn, "obra", "-26.95,-49.1")
        self.tarefa("Medir a parede na obra")
        vid = self.visita((-26.95, -49.1), _em("18:30"))
        onde_estou.reagir(self.conn, vid, _em("18:31"))
        self.assertTrue(self.mensagens()[1]["texto"].startswith("Chegou na obra. Agora é: medir a parede na obra."))

    def test_sem_nada_pra_dizer_nao_fala_e_lugar_desconhecido_nao_fala(self):
        vid = self.visita(MECANICO, _em("07:20"))
        onde_estou.reagir(self.conn, vid, _em("07:21"))
        self.tarefa("Imprimir as contas", "11:00")
        vid = self.visita((-27.5, -48.5), _em("08:00"))
        onde_estou.reagir(self.conn, vid, _em("08:01"))
        self.assertEqual(self.mensagens(), [])

    def test_chegada_velha_da_fila_offline_nao_avisa(self):
        self.tarefa("Levar o carro no mecânico")
        vid = self.visita(MECANICO, _em("07:20"))
        onde_estou.reagir(self.conn, vid, _em("09:20"))
        self.assertEqual(self.mensagens(), [])


class AtrasoTestCase(_Base):
    def preparar(self):
        self.contas = self.tarefa("Imprimir as contas", "11:00")
        self.boleto = self.tarefa("Pagar boleto (até 12:30)", "12:00")
        self.cadeado = self.tarefa("Reunião do banco", "13:00", inegociavel=1)
        self.depois = self.tarefa("Ligar pro João", "14:00")
        self.carro = self.tarefa("Levar o carro no mecânico", "10:30")
        return self.visita(MECANICO, _em("10:00"))

    def test_empurra_com_desfazer_e_para_no_inegociavel(self):
        vid = self.preparar()
        with patch.object(onde_estou, "CHEGADA_RECENTE_MIN", 0):
            self.assertEqual(onde_estou.reagir(self.conn, vid, _em("10:50")), ["atraso"])
        # 10:50 + 25 min de trajeto = 11:15 -> 15 min de atraso
        self.assertEqual(self.hora(self.contas)["hora"], "11:15")
        self.assertEqual(tuple(self.hora(self.boleto)), ("12:15", "Pagar boleto (até 12:45)"))
        self.assertEqual(self.hora(self.cadeado)["hora"], "13:00")  # cadeado: parede
        self.assertEqual(self.hora(self.depois)["hora"], "14:00")  # depois da parede: nao mexe
        self.assertEqual(self.hora(self.carro)["hora"], "10:30")  # a do lugar ele ja esta fazendo
        msg = self.mensagens()[-1]
        self.assertEqual(msg["texto"],
                         "Atrasou no mecânico: empurrei imprimir as contas pras 11h15 (e a seguinte também).")
        self.avisar.assert_called_with(self.conn, onde_estou.TIPO_ATRASO, vid, "Atrasou no mecânico",
                                       "Empurrei imprimir as contas pras 11h15 (e a seguinte também).", _em("10:50"))
        # destino sem local = casa; origem = a visita
        self.assertEqual(self.tempo_de_viagem.call_args[0], (f"{MECANICO[0]},{MECANICO[1]}", f"{CASA[0]},{CASA[1]}"))

        # Desfazer pelo botao do card (mesma rota dos outros cards)
        card = json.loads(app.criptografia.descriptografar(msg["cards_json"]))[0]
        self.assertEqual(card["type"], "edicao")
        acao = next(a for a in card["actions"] if a["tipo"] == "desfazer")
        client = app.app.test_client()
        self.assertEqual(client.post("/login", json={"pin": PIN}).status_code, 200)
        self.assertEqual(client.post(f"/api/desfazer/{acao['token']}").status_code, 200)
        self.assertEqual(self.hora(self.contas)["hora"], "11:00")
        self.assertEqual(tuple(self.hora(self.boleto)), ("12:00", "Pagar boleto (até 12:30)"))

    def test_uma_vez_por_tarefa_por_dia(self):
        vid = self.preparar()
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual(self.hora(self.contas)["hora"], "11:15")
        onde_estou.verificar(self.conn, _em("11:20"))  # ainda la, mais atrasado: nao empurra de novo
        self.assertEqual(self.hora(self.contas)["hora"], "11:15")
        self.assertEqual(sum(1 for m in self.mensagens() if m["texto"].startswith("Atrasou")), 1)
        self.assertEqual(self.tempo_de_viagem.call_count, 1)
        self.assertTrue(vid)

    def test_no_horario_nao_mexe(self):
        self.preparar()
        onde_estou.verificar(self.conn, _em("10:40"))  # 10:40 + 25 = 11:05: so 5 min, tolera
        self.assertEqual(self.hora(self.contas)["hora"], "11:00")
        self.assertFalse([m for m in self.mensagens() if m["texto"].startswith("Atrasou")])

    def test_proxima_inegociavel_nao_mexe_em_nada(self):
        cadeado = self.tarefa("Prova da faculdade", "11:00", inegociavel=1)
        voo = self.tarefa("Voo SSBL", "11:30")
        outra = self.tarefa("Mercado", "12:00")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:55"))
        self.assertEqual([self.hora(t)["hora"] for t in (cadeado, voo, outra)], ["11:00", "11:30", "12:00"])

    def test_voo_e_parede(self):
        contas = self.tarefa("Imprimir as contas", "11:00")
        voo = self.tarefa("Voo local", "12:00")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:50"))
        self.assertEqual(self.hora(contas)["hora"], "11:15")
        self.assertEqual(self.hora(voo)["hora"], "12:00")

    def test_ao_sair_tambem_confere(self):
        contas = self.tarefa("Imprimir as contas", "11:00")
        vid = self.visita(MECANICO, _em("10:00"), _em("10:50"))
        onde_estou.reagir(self.conn, vid, _em("10:51"))
        self.assertEqual(self.hora(contas)["hora"], "11:20")  # 10:51 + 25 = 11:16 -> 16 min -> 20

    def test_ja_esta_no_lugar_da_tarefa_nao_empurra(self):
        contas = self.tarefa("Imprimir as contas", "11:00")
        self.visita(CASA, _em("10:00"))
        onde_estou.verificar(self.conn, _em("11:15"))
        self.assertEqual(self.hora(contas)["hora"], "11:00")
        self.tempo_de_viagem.assert_not_called()

    def test_tarefa_longe_no_tempo_nao_gasta_cota(self):
        self.tarefa("Imprimir as contas", "16:00")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:30"))
        self.tempo_de_viagem.assert_not_called()

    def test_trajeto_com_cache(self):
        self.tarefa("Imprimir as contas", "11:00")
        self.tarefa("Outra", "11:30")
        self.visita(MECANICO, _em("10:00"))
        onde_estou.verificar(self.conn, _em("10:20"))  # 10:20 + 25 = 10:45: no horario
        onde_estou.verificar(self.conn, _em("10:25"))
        self.assertEqual(self.tempo_de_viagem.call_count, 1)


class AvisarTestCase(_Base):
    def test_avisar_manda_telegram_e_respeita_silencio(self):
        self.aviso.stop()
        with patch("telegram_bot.configurado", return_value=True), \
                patch("telegram_bot.enviar_mensagem") as tg, patch("push_client.configurado", return_value=False):
            self.assertTrue(onde_estou._avisar(self.conn, "chegou_lugar", 1, "Chegou no mecânico", "Agora é: x.",
                                               _em("10:00")))
            tg.assert_called_once_with("Chegou no mecânico\nAgora é: x.")
            self.assertFalse(onde_estou._avisar(self.conn, "chegou_lugar", 1, "t", "c", _em("23:30")))
            self.assertEqual(tg.call_count, 1)
        self.aviso.start()


class ContextoTestCase(_Base):
    def agora(self):
        return datetime.now(onde_estou.FUSO).replace(tzinfo=None, microsecond=0)

    def test_linha_no_lugar_e_depois_de_sair(self):
        agora = _em("08:00")
        self.tarefa("Levar o carro no mecânico")
        self.visita(MECANICO, _em("07:20"))
        self.assertEqual(onde_estou.linha_contexto(self.conn, agora), "Agora (pelo iPhone): no mecânico desde 07:20")
        self.conn.execute("UPDATE visitas SET saida = ?", (_em("07:50").isoformat(),))
        self.assertEqual(onde_estou.linha_contexto(self.conn, agora), "Agora (pelo iPhone): saiu do mecânico às 07:50")
        self.assertIsNone(onde_estou.linha_contexto(self.conn, _em("10:30")))  # saiu ha mais de 2 h
        self.visita(CASA, _em("08:10"), _em("08:20"))
        self.assertEqual(onde_estou.linha_contexto(self.conn, _em("08:30")), "Agora (pelo iPhone): saiu de casa às 08:20")
        self.visita((-27.5, -48.5), _em("08:40"))
        self.assertEqual(onde_estou.linha_contexto(self.conn, _em("08:45")),
                         "Agora (pelo iPhone): parado num lugar sem apelido salvo desde 08:40")

    def test_entra_no_contexto_do_chat(self):
        agora = self.agora()
        self.visita(CASA, agora - timedelta(minutes=30))
        texto = app._contexto_chat(self.conn)
        esperado = f"Agora (pelo iPhone): em casa desde {agora - timedelta(minutes=30):%H:%M}"
        if (agora - timedelta(minutes=30)).date() != agora.date():
            esperado = f"Agora (pelo iPhone): em casa desde ontem {agora - timedelta(minutes=30):%H:%M}"
        self.assertEqual(texto.splitlines()[1], esperado)

    def test_sem_visita_nao_tem_linha(self):
        self.assertNotIn("pelo iPhone", app._contexto_chat(self.conn))


if __name__ == "__main__":
    unittest.main()
