import unittest
from unittest.mock import MagicMock, patch

import requests

import clima


class ClimaTestCase(unittest.TestCase):
    def setUp(self):
        clima._cache_geocodificacao.clear()

    def test_geocodificar_cidade_vazia_devolve_none(self):
        self.assertIsNone(clima.geocodificar_cidade(""))
        self.assertIsNone(clima.geocodificar_cidade("   "))

    def test_geocodificar_cidade_encontrada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "results": [{"latitude": -27.0, "longitude": -49.06, "name": "Blumenau"}]
        }
        with patch("clima.requests.get", return_value=resposta) as mock_get:
            r = clima.geocodificar_cidade("Blumenau")
        self.assertEqual(r, {"lat": -27.0, "lon": -49.06, "nome": "Blumenau"})
        mock_get.assert_called_once()

    def test_geocodificar_cidade_nao_encontrada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {"results": []}
        with patch("clima.requests.get", return_value=resposta):
            self.assertIsNone(clima.geocodificar_cidade("CidadeQueNaoExiste123"))

    def test_geocodificar_usa_cache_na_segunda_chamada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "results": [{"latitude": -27.0, "longitude": -49.06, "name": "Blumenau"}]
        }
        with patch("clima.requests.get", return_value=resposta) as mock_get:
            clima.geocodificar_cidade("Blumenau")
            clima.geocodificar_cidade("Blumenau")
        self.assertEqual(mock_get.call_count, 1)

    def test_geocodificar_erro_de_rede_devolve_none(self):
        with patch("clima.requests.get", side_effect=requests.RequestException("fora do ar")):
            self.assertIsNone(clima.geocodificar_cidade("Brusque"))

    def test_geocodificar_resposta_mal_formada_devolve_none(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {"results": [{"latitude": -27.0}]}  # sem 'longitude'/'name'
        with patch("clima.requests.get", return_value=resposta):
            self.assertIsNone(clima.geocodificar_cidade("Brusque"))

    def test_previsao_para_data_encontrada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "daily": {
                "time": ["2026-09-18", "2026-09-19"],
                "weathercode": [3, 61],
                "temperature_2m_max": [24.0, 20.0],
                "temperature_2m_min": [15.0, 14.0],
                "precipitation_probability_max": [10, 80],
            }
        }
        with patch("clima.requests.get", return_value=resposta):
            r = clima.previsao_para_data(-27.0, -49.06, "2026-09-19")
        self.assertEqual(r["chuva_pct"], 80)
        self.assertEqual(r["temp_max"], 20.0)
        self.assertTrue(r["alerta_chuva"])

    def test_previsao_dia_sem_chuva_nao_alerta(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "daily": {
                "time": ["2026-09-18"],
                "weathercode": [1],
                "temperature_2m_max": [26.0],
                "temperature_2m_min": [16.0],
                "precipitation_probability_max": [5],
            }
        }
        with patch("clima.requests.get", return_value=resposta):
            r = clima.previsao_para_data(-27.0, -49.06, "2026-09-18")
        self.assertFalse(r["alerta_chuva"])

    def test_previsao_para_data_fora_da_janela_devolve_none(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "daily": {
                "time": ["2026-09-18"],
                "weathercode": [1],
                "temperature_2m_max": [26.0],
                "temperature_2m_min": [16.0],
                "precipitation_probability_max": [5],
            }
        }
        with patch("clima.requests.get", return_value=resposta):
            r = clima.previsao_para_data(-27.0, -49.06, "2027-01-01")
        self.assertIsNone(r)

    def test_previsao_erro_de_rede_devolve_none(self):
        with patch("clima.requests.get", side_effect=requests.RequestException("timeout")):
            self.assertIsNone(clima.previsao_para_data(-27.0, -49.06, "2026-09-18"))

    def test_previsao_para_cidade_e_data_encadeia_geocoding_e_previsao(self):
        resp_geo = MagicMock()
        resp_geo.raise_for_status = lambda: None
        resp_geo.json.return_value = {
            "results": [{"latitude": -27.0, "longitude": -49.06, "name": "Blumenau"}]
        }
        resp_prev = MagicMock()
        resp_prev.raise_for_status = lambda: None
        resp_prev.json.return_value = {
            "daily": {
                "time": ["2026-09-18"],
                "weathercode": [61],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [14.0],
                "precipitation_probability_max": [90],
            }
        }
        with patch("clima.requests.get", side_effect=[resp_geo, resp_prev]):
            r = clima.previsao_para_cidade_e_data("Blumenau", "2026-09-18")
        self.assertEqual(r["cidade"], "Blumenau")
        self.assertEqual(r["chuva_pct"], 90)
        self.assertTrue(r["alerta_chuva"])

    def test_previsao_para_cidade_desconhecida_devolve_none(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {"results": []}
        with patch("clima.requests.get", return_value=resposta):
            self.assertIsNone(clima.previsao_para_cidade_e_data("CidadeInventada", "2026-09-18"))


if __name__ == "__main__":
    unittest.main()
