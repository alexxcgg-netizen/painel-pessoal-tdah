"""Leva 2026-10-15 (docs/briefings/2026-10-15-transito-waze.md): transito de verdade + Waze.
- maps_client: transito previsto pra hora de sair (departureTime), quanto e transito
  (staticDuration), trechos lentos/parados (speedReadingIntervals) com nome, trava da cota gratis;
- card de rota com "+N min", trecho parado ("pode ser acidente ou blitz") e botao do Waze;
- aviso "hora de sair" recalcula 1x por hora e leva o transito no texto;
- tarefa com lugar ganha o link do Waze.
Nenhuma rede: requests.post/get do Google sempre mockados; banco temporario."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import maps_client  # noqa: E402
import push_client  # noqa: E402
import requests  # noqa: E402

PIN_TESTE = "123456"


def _codificar(pontos):
    """Encoded polyline do Google (o inverso de maps_client.decodificar_polyline)."""
    saida, ant = [], (0, 0)
    for lat, lon in pontos:
        atual = (round(lat * 1e5), round(lon * 1e5))
        for d in (atual[0] - ant[0], atual[1] - ant[1]):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                saida.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            saida.append(chr(v + 63))
        ant = atual
    return "".join(saida)


# 10 pontos indo pro norte, ~0,55 km entre eles (~5 km no total)
PONTOS = [(-27.0 + i * 0.005, -48.9) for i in range(10)]
INTERVALOS = [
    {"endPolylinePointIndex": 2, "speed": "NORMAL"},  # sem start = 0 (padrao do proto)
    {"startPolylinePointIndex": 2, "endPolylinePointIndex": 4, "speed": "TRAFFIC_JAM"},
    {"startPolylinePointIndex": 4, "endPolylinePointIndex": 5, "speed": "SLOW"},  # vizinho: junta
    {"startPolylinePointIndex": 6, "endPolylinePointIndex": 7, "speed": "SLOW"},  # lento curto: some
    {"startPolylinePointIndex": 7, "endPolylinePointIndex": 9, "speed": "NORMAL"},
]


def _resposta_routes(com_lentidao=True):
    rota = {
        "duration": "2220s", "staticDuration": "1500s", "distanceMeters": 5000,
        "polyline": {"encodedPolyline": _codificar(PONTOS)},
    }
    if com_lentidao:
        rota["travelAdvisory"] = {"speedReadingIntervals": INTERVALOS}
    r = MagicMock()
    r.json.return_value = {"routes": [rota]}
    r.raise_for_status.return_value = None
    return r


def _resposta_geocode():
    r = MagicMock()
    r.json.return_value = {"results": [{"address_components": [
        {"short_name": "BR-470", "long_name": "Rodovia BR-470", "types": ["route"]},
        {"long_name": "Gaspar", "types": ["administrative_area_level_2", "political"]},
    ]}]}
    r.raise_for_status.return_value = None
    return r


class _BancoLimpo(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        maps_client._cache_nome_trecho.clear()
        app._CACHE_TRAJETO_AVISO.clear()
        self._env = patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-fake", "ENDERECO_CASA": "Rua Exemplo, Brusque"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def chamadas(self, nivel):
        conn = db.get_db()
        try:
            linha = conn.execute("SELECT chamadas FROM uso_maps WHERE mes = ? AND nivel = ?",
                                 (datetime.now().strftime("%Y-%m"), nivel)).fetchone()
            return linha["chamadas"] if linha else 0
        finally:
            conn.close()

    def gastar_cota(self, nivel):
        conn = db.get_db()
        conn.execute("INSERT OR REPLACE INTO uso_maps (mes, nivel, chamadas) VALUES (?, ?, ?)",
                     (datetime.now().strftime("%Y-%m"), nivel, maps_client.COTA_MES[nivel]))
        conn.commit()
        conn.close()


class TempoDeViagemTestCase(_BancoLimpo):
    def test_transito_trecho_parado_com_nome_e_hora_de_saida(self):
        partida = datetime.now() + timedelta(hours=2)
        with patch("maps_client.requests.post", return_value=_resposta_routes()) as post, \
                patch("maps_client.requests.get", return_value=_resposta_geocode()) as get:
            v = maps_client.tempo_de_viagem("A", "B", partida=partida, lentidao=True)
        corpo = post.call_args.kwargs["json"]
        mascara = post.call_args.kwargs["headers"]["X-Goog-FieldMask"]
        self.assertEqual(corpo["routingPreference"], "TRAFFIC_AWARE")
        self.assertEqual(corpo["extraComputations"], ["TRAFFIC_ON_POLYLINE"])
        self.assertTrue(corpo["departureTime"].endswith("Z"))
        self.assertIn("routes.staticDuration", mascara)
        self.assertIn("routes.travelAdvisory.speedReadingIntervals", mascara)
        self.assertEqual(v["duracao_minutos"], 37)
        self.assertEqual(v["transito_min"], 12)  # 2220 - 1500 s
        self.assertEqual(v["destino_ll"], [round(PONTOS[-1][0], 5), -48.9])
        # parado (2-4) + lento vizinho (4-5) viram 1 trecho parado; o lento curto (6-7) some
        self.assertEqual(len(v["lentidao"]), 1, v["lentidao"])
        t = v["lentidao"][0]
        self.assertEqual(t["nivel"], "parado")
        self.assertEqual(t["nome"], "BR-470, Gaspar")
        self.assertAlmostEqual(t["de_km"], 1.1, delta=0.1)
        self.assertAlmostEqual(t["extensao_km"], 1.7, delta=0.1)
        self.assertEqual(get.call_args.kwargs["params"]["result_type"], "route")
        self.assertEqual(self.chamadas("lentidao"), 1)
        self.assertEqual(self.chamadas("lugar_nome"), 1)

    def test_partida_no_passado_nao_manda_departure_time(self):
        with patch("maps_client.requests.post", return_value=_resposta_routes(False)) as post:
            maps_client.tempo_de_viagem("A", "B", partida=datetime.now() - timedelta(minutes=5))
        corpo = post.call_args.kwargs["json"]
        self.assertNotIn("departureTime", corpo)
        self.assertNotIn("extraComputations", corpo)  # sem lentidao: faixa de 5.000 gratis
        self.assertEqual(self.chamadas("transito"), 1)
        self.assertEqual(self.chamadas("lentidao"), 0)

    def test_cota_de_lentidao_acabou_cai_pro_transito_simples(self):
        self.gastar_cota("lentidao")
        with patch("maps_client.requests.post", return_value=_resposta_routes(False)) as post:
            v = maps_client.tempo_de_viagem("A", "B", lentidao=True)
        corpo = post.call_args.kwargs["json"]
        self.assertNotIn("extraComputations", corpo)
        self.assertEqual(corpo["routingPreference"], "TRAFFIC_AWARE")
        self.assertEqual(v["lentidao"], [])
        self.assertEqual(v["transito_min"], 12)

    def test_cota_toda_acabou_nao_chama_o_google_e_vira_falha_de_rede(self):
        for nivel in ("lentidao", "transito", "basico"):
            self.gastar_cota(nivel)
        with patch("maps_client.requests.post") as post:
            with self.assertRaises(requests.RequestException):  # todo mundo ja trata como "Maps fora"
                maps_client.tempo_de_viagem("A", "B", lentidao=True)
        post.assert_not_called()
        self.assertTrue(issubclass(maps_client.CotaEsgotada, requests.RequestException))

    def test_trava_conta_ate_o_limite(self):
        with patch.dict(maps_client.COTA_MES, {"basico": 2}):
            self.assertEqual([maps_client.usar_cota("basico") for _ in range(3)], [True, True, False])
        self.assertEqual(self.chamadas("basico"), 2)

    def test_horario_de_saida_pede_transito_da_hora_de_sair_e_devolve_waze(self):
        chegar = datetime.now() + timedelta(hours=5)
        with patch("maps_client.requests.post", return_value=_resposta_routes(False)) as post:
            r = maps_client.horario_de_saida("A", "B", chegar, margem_minutos=10)
        partida = post.call_args.kwargs["json"]["departureTime"]
        esperado = (chegar - timedelta(minutes=40)).astimezone().astimezone(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(partida, esperado)  # chegar - margem - 30 (estimativa)
        self.assertEqual(r["transito_min"], 12)
        self.assertTrue(r["waze"].startswith("https://waze.com/ul?ll="))
        self.assertTrue(r["waze"].endswith("&navigate=yes"))


class TextosELinksTestCase(unittest.TestCase):
    def test_frase_nunca_afirma_a_causa(self):
        parado = {"nivel": "parado", "de_km": 12.0, "extensao_km": 2.0, "nome": "BR-470, Gaspar"}
        self.assertEqual(maps_client.frase_trecho(parado), "Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz")
        lento = {"nivel": "lento", "de_km": 3.5, "extensao_km": 1.5}
        self.assertEqual(maps_client.frase_trecho(lento), "Lento a 3,5 km da saída (1,5 km)")
        self.assertEqual(maps_client.resumo_transito({"transito_min": 12, "lentidao": [parado]}),
                         "+12 min de trânsito. Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz")
        self.assertEqual(maps_client.resumo_transito({"transito_min": 2, "lentidao": []}), "")
        self.assertEqual(maps_client.resumo_transito({}), "")

    def test_link_waze(self):
        self.assertEqual(maps_client.link_waze([-26.9, -49.07]), "https://waze.com/ul?ll=-26.90000,-49.07000&navigate=yes")
        self.assertEqual(maps_client.link_waze(None, "-26.9,-49.07"), "https://waze.com/ul?ll=-26.90000,-49.07000&navigate=yes")
        self.assertEqual(maps_client.link_waze(None, "Aeroclube de Blumenau"),
                         "https://waze.com/ul?q=Aeroclube+de+Blumenau&navigate=yes")
        self.assertIsNone(maps_client.link_waze(None, "  "))
        self.assertIsNone(maps_client.link_waze(["x", 1]))


class TrajetoECardTestCase(unittest.TestCase):
    def test_trajeto_soma_transito_pinta_o_trecho_e_waze_ate_a_1a_parada(self):
        def falso(origem, destino, _lugares=(None, None), lentidao=False, **_):
            self.assertTrue(lentidao)
            return {"duracao_minutos": 30, "distancia_km": 5.0, "transito_min": 6,
                    "lentidao": [{"nivel": "parado", "de_km": 1.1, "extensao_km": 1.7, "ponto": [0, 0], "_i": [2, 5]}],
                    "destino_ll": [-26.85, -49.1], "_polyline": _codificar(PONTOS)}

        with patch("maps_client.resolver_lugar", return_value=None), \
                patch("maps_client.tempo_de_viagem", side_effect=falso):
            r = maps_client.trajeto(["Casa", "Aeroclube", "Casa"])
        self.assertEqual(r["transito_total_min"], 12)
        self.assertEqual(r["_waze"], "https://waze.com/ul?ll=-26.85000,-49.10000&navigate=yes")
        self.assertEqual([x["trecho"] for x in r["lentidao"]], [0, 1])
        self.assertNotIn("_i", r["lentidao"][0])
        self.assertNotIn("destino_ll", r["trechos"][0])
        self.assertEqual([f["nivel"] for f in r["_traco"]["lentos"]], ["parado", "parado"])

    def test_card_rota_leva_transito_lentidao_e_waze_validado(self):
        ef = {
            "url": "https://www.google.com/maps/dir/?api=1&destination=x",
            "paradas": [{"nome": "Casa", "endereco": ""}, {"nome": "Aeroclube de Blumenau, SC", "endereco": ""},
                        {"nome": "Casa", "endereco": ""}],
            "transito_min": 12,
            "lentidao": [{"nivel": "parado", "frase": "Parado na BR-470 - pode ser acidente ou blitz"},
                         {"nivel": "inventado", "frase": "x"}],
            "waze": "https://waze.com/ul?ll=-26.85000,-49.10000&navigate=yes",
            "waze_para": "Aeroclube de Blumenau, SC",
        }
        c = cards.card_rota(ef)
        self.assertEqual(c["data"]["transito_min"], 12)
        self.assertEqual([x["nivel"] for x in c["data"]["lentidao"]], ["parado"])
        waze = [a for a in c["actions"] if "waze.com" in a["url"]]
        self.assertEqual(waze[0]["rotulo"], "Waze até Aeroclube de Blumenau")  # varias paradas: diz ate onde
        c2 = cards.card_rota({**ef, "waze": "https://evil.example/ul?x"})
        self.assertFalse([a for a in c2["actions"] if "evil" in a["url"]])


class AvisoHoraDeSairTestCase(_BancoLimpo):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        self.tid = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local) VALUES ('Date', '2026-10-11', '20:00', 'Bar Exemplo')"
        ).lastrowid
        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        super().tearDown()

    def _rodar(self, agora, viagem):
        enviados = []

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=lambda s, t, c, url="", tag="", **_: enviados.append((t, c)) or True), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._eventos_de_hoje_com_seguranca", return_value=[]), \
                patch("maps_client.configurado", return_value=True), \
                patch("maps_client.tempo_de_viagem", return_value=viagem) as tv, \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("app.date", type("D", (), {"today": staticmethod(lambda: agora.date()),
                                                   "fromisoformat": staticmethod(datetime.fromisoformat)})):
            app.verificar_e_notificar()
        return enviados, tv

    def test_recalcula_de_hora_em_hora_e_o_aviso_leva_o_transito(self):
        viagem = {"duracao_minutos": 20, "distancia_km": 10.0, "transito_min": 8, "destino_ll": [-27.1, -48.9],
                  "lentidao": [{"nivel": "parado", "de_km": 3.0, "extensao_km": 2.0, "ponto": [0, 0], "nome": "BR-470, Gaspar"}]}
        _, tv1 = self._rodar(datetime(2026, 10, 11, 18, 10), viagem)
        _, tv2 = self._rodar(datetime(2026, 10, 11, 18, 50), viagem)  # mesma hora: usa o guardado
        self.assertEqual(tv1.call_count, 1)
        self.assertEqual(tv2.call_count, 0)
        self.assertTrue(tv1.call_args.kwargs.get("lentidao"))
        enviados, tv3 = self._rodar(datetime(2026, 10, 11, 19, 38), viagem)  # hora nova: recalcula
        self.assertEqual(tv3.call_count, 1)
        sair = [c for t, c in enviados if t == "🚗 Bora, hora de sair"]
        self.assertEqual(len(sair), 1, enviados)
        self.assertIn("20 min até lá", sair[0])
        self.assertIn("+8 min de trânsito. Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz.", sair[0])


class TarefaComLugarTestCase(_BancoLimpo):
    def test_tarefa_com_lugar_ganha_waze(self):
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.execute("INSERT INTO tasks (title, local) VALUES ('Dentista', 'Rua das Flores, 100, Brusque')")
        conn.execute("INSERT INTO tasks (title) VALUES ('Ler o livro')")
        conn.commit()
        conn.close()
        cliente = app.app.test_client()
        cliente.post("/login", json={"pin": PIN_TESTE})
        tarefas = {t["title"]: t for t in cliente.get("/api/tasks").get_json()}
        self.assertEqual(tarefas["Dentista"]["waze"],
                         "https://waze.com/ul?q=Rua+das+Flores%2C+100%2C+Brusque&navigate=yes")
        self.assertIsNone(tarefas["Ler o livro"]["waze"])


if __name__ == "__main__":
    unittest.main()
