"""Fase 6 F3: US-F13 (Lugares que Gostei - mapa via OpenStreetMap/Nominatim).

Geocodificacao SEMPRE mockada aqui - nunca chama o Nominatim de verdade em
teste (regra do AGENTS.md + do prd desta faixa). Segue o padrao de
tests/test_pin_inicial.py: db.DB_PATH pra um arquivo temporario +
db.garantir_banco_nao_producao() ANTES de importar app."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import geocode_nominatim

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


NOMINATIM_OK = [{"lat": "-26.9195567", "lon": "-49.0658025"}]


# ---- geocode_nominatim.py (pura, so mockando requests.get) -----------------

class GeocodeNominatimTestCase(unittest.TestCase):
    def setUp(self):
        geocode_nominatim._ultima_chamada = 0.0  # reseta throttle entre testes

    def test_encontrado_devolve_lat_lng(self):
        with patch("geocode_nominatim.requests.get", return_value=FakeResp(NOMINATIM_OK)) as mock_get:
            resultado = geocode_nominatim.geocodificar("Cafe Colonial", "Blumenau")
        self.assertEqual(resultado["status"], "ok")
        self.assertAlmostEqual(resultado["lat"], -26.9195567)
        self.assertAlmostEqual(resultado["lng"], -49.0658025)
        # User-Agent proprio, nunca o default da lib
        _, kwargs = mock_get.call_args
        self.assertIn("PainelPessoalTDAH", kwargs["headers"]["User-Agent"])
        self.assertNotIn("alexxcgg", kwargs["headers"]["User-Agent"])  # nunca vaza email pessoal

    def test_nao_encontrado(self):
        with patch("geocode_nominatim.requests.get", return_value=FakeResp([])):
            resultado = geocode_nominatim.geocodificar("Lugar que nao existe no mapa nenhum", None)
        self.assertEqual(resultado["status"], "nao_encontrado")

    def test_erro_de_rede_nao_quebra(self):
        import requests as _requests

        with patch("geocode_nominatim.requests.get", side_effect=_requests.RequestException("timeout")):
            resultado = geocode_nominatim.geocodificar("Algo", "Cidade")
        self.assertEqual(resultado["status"], "erro")

    def test_nome_e_cidade_vazios_nao_chama_rede(self):
        with patch("geocode_nominatim.requests.get") as mock_get:
            resultado = geocode_nominatim.geocodificar("", None)
        mock_get.assert_not_called()
        self.assertEqual(resultado["status"], "nao_encontrado")

    def test_resposta_malformada_vira_nao_encontrado(self):
        with patch("geocode_nominatim.requests.get", return_value=FakeResp([{"sem": "lat/lon"}])):
            resultado = geocode_nominatim.geocodificar("X", "Y")
        self.assertEqual(resultado["status"], "nao_encontrado")

    def test_throttle_respeita_1_req_por_segundo(self):
        with patch("geocode_nominatim.requests.get", return_value=FakeResp(NOMINATIM_OK)):
            with patch("geocode_nominatim.time.sleep") as mock_sleep:
                geocode_nominatim._ultima_chamada = time.monotonic()  # como se tivesse acabado de chamar
                geocode_nominatim.geocodificar("X", "Y")
        mock_sleep.assert_called_once()
        self.assertGreater(mock_sleep.call_args[0][0], 0)


# ---- app.py: rotas de lugares com geocode --------------------------------

class LugaresGeocodeHTTPTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def test_criar_lugar_geocodifica_uma_vez(self):
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "ok", "lat": 1.0, "lng": 2.0}) as mock_geo:
            res = self.client.post("/api/lugares", json={"nome": "Cafe Colonial", "cidade": "Blumenau"})
        self.assertEqual(res.status_code, 201)
        mock_geo.assert_called_once_with("Cafe Colonial", "Blumenau")

        lugares = self.client.get("/api/lugares").get_json()
        alvo = next(l for l in lugares if l["nome"] == "Cafe Colonial")
        self.assertEqual(alvo["geocode_status"], "ok")
        self.assertEqual(alvo["lat"], 1.0)
        self.assertEqual(alvo["lng"], 2.0)

    def test_lugar_nao_encontrado_continua_aparecendo_com_nome(self):
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "nao_encontrado"}):
            self.client.post("/api/lugares", json={"nome": "Lugar sem mapa", "cidade": None})
        lugares = self.client.get("/api/lugares").get_json()
        alvo = next(l for l in lugares if l["nome"] == "Lugar sem mapa")
        self.assertEqual(alvo["geocode_status"], "nao_encontrado")
        self.assertIsNone(alvo["lat"])

    def test_erro_de_rede_na_criacao_nao_impede_o_lugar_de_ser_salvo(self):
        # Achado real: o GET /api/lugares faz backfill (US-F13) - se o mock
        # nao cobrir TAMBEM essa chamada, o teste chamaria o Nominatim de
        # verdade (violando a regra de nunca bater API real em teste). Por
        # isso o `with` envolve o POST *e* o GET, nao só o POST.
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "erro"}) as mock_geo:
            res = self.client.post("/api/lugares", json={"nome": "Vai falhar", "cidade": "X"})
            self.assertEqual(res.status_code, 201)
            lugares = self.client.get("/api/lugares").get_json()
        alvo = next(l for l in lugares if l["nome"] == "Vai falhar")
        # revisao da Fase 6: grava "erro" TEMPORARIO (com hora pra tentar de
        # novo), nunca um status definitivo - e o GET logo depois nao repete
        # a chamada dentro da espera.
        self.assertEqual(alvo["geocode_status"], "erro")
        self.assertTrue(alvo["geocode_tentar_depois"])
        self.assertEqual(mock_geo.call_count, 1)

    def test_get_lugares_faz_backfill_de_no_maximo_1_por_chamada(self):
        conn = db.get_db()
        id1 = db.create_lugar(conn, "Lugar A", "Cidade A", None, None)
        id2 = db.create_lugar(conn, "Lugar B", "Cidade B", None, None)
        conn.close()

        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "ok", "lat": 9.0, "lng": 8.0}) as mock_geo:
            primeira = self.client.get("/api/lugares").get_json()
        self.assertEqual(mock_geo.call_count, 1)
        geocodificados = [l for l in primeira if l["geocode_status"] is not None]
        self.assertEqual(len(geocodificados), 1)

        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "ok", "lat": 9.0, "lng": 8.0}) as mock_geo2:
            segunda = self.client.get("/api/lugares").get_json()
        self.assertEqual(mock_geo2.call_count, 1)
        self.assertTrue(all(l["geocode_status"] is not None for l in segunda))

    def test_lugar_ja_geocodificado_nunca_e_consultado_de_novo(self):
        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "nao_encontrado"}):
            self.client.post("/api/lugares", json={"nome": "Ja consultado", "cidade": None})

        with patch("app.geocode_nominatim.geocodificar") as mock_geo:
            self.client.get("/api/lugares")
            self.client.get("/api/lugares")
        mock_geo.assert_not_called()

    def test_erro_de_rede_no_backfill_nao_marca_como_definitivo(self):
        conn = db.get_db()
        db.create_lugar(conn, "Vai falhar no backfill", "X", None, None)
        conn.close()

        with patch("app.geocode_nominatim.geocodificar", return_value={"status": "erro"}):
            resultado = self.client.get("/api/lugares").get_json()
        alvo = next(l for l in resultado if l["nome"] == "Vai falhar no backfill")
        # continua pendente (status temporario "erro"), tenta de novo depois
        # de app.GEOCODE_ESPERA_APOS_ERRO - revisao da Fase 6
        self.assertEqual(alvo["geocode_status"], "erro")
        self.assertTrue(alvo["geocode_tentar_depois"])


if __name__ == "__main__":
    unittest.main()
