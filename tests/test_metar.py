import unittest
from unittest.mock import MagicMock, patch

import requests

import metar


class MetarTestCase(unittest.TestCase):
    def test_icao_vazio_da_erro_sem_chamar_rede(self):
        with patch("metar.requests.get") as mock_get:
            r = metar.buscar_metar_taf("")
        self.assertIsNone(r["metar"])
        self.assertIsNone(r["taf"])
        self.assertIn("informe", r["erro"])
        mock_get.assert_not_called()

    def test_busca_com_sucesso(self):
        resp_metar = MagicMock()
        resp_metar.raise_for_status = lambda: None
        resp_metar.text = "SBBI 181800Z 12008KT 9999 SCT030 25/18 Q1015"
        resp_taf = MagicMock()
        resp_taf.raise_for_status = lambda: None
        resp_taf.text = "TAF SBBI 181700Z 1818/1918 12010KT CAVOK"

        with patch("metar.requests.get", side_effect=[resp_metar, resp_taf]) as mock_get:
            r = metar.buscar_metar_taf("sbbi")

        self.assertIn("SBBI", r["metar"])
        self.assertIn("TAF SBBI", r["taf"])
        self.assertIsNone(r["erro"])
        # normaliza pra maiusculo antes de mandar pro ICAO na query
        self.assertEqual(mock_get.call_args_list[0][1]["params"]["ids"], "SBBI")

    def test_metar_indisponivel_mas_taf_ok_nao_perde_o_taf(self):
        resp_taf = MagicMock()
        resp_taf.raise_for_status = lambda: None
        resp_taf.text = "TAF SBBI 181700Z 1818/1918 12010KT CAVOK"

        with patch(
            "metar.requests.get",
            side_effect=[requests.RequestException("timeout"), resp_taf],
        ):
            r = metar.buscar_metar_taf("SBBI")

        self.assertIsNone(r["metar"])
        self.assertIsNotNone(r["taf"])
        self.assertIsNotNone(r["erro"])

    def test_nenhum_dado_encontrado_da_erro_descritivo(self):
        resp_vazio = MagicMock()
        resp_vazio.raise_for_status = lambda: None
        resp_vazio.text = ""

        with patch("metar.requests.get", return_value=resp_vazio):
            r = metar.buscar_metar_taf("ZZZZ")

        self.assertIsNone(r["metar"])
        self.assertIsNone(r["taf"])
        self.assertIn("ZZZZ", r["erro"])

    def test_erro_total_de_rede(self):
        with patch("metar.requests.get", side_effect=requests.RequestException("fora do ar")):
            r = metar.buscar_metar_taf("SBBI")
        self.assertIsNone(r["metar"])
        self.assertIsNone(r["taf"])
        self.assertIsNotNone(r["erro"])


if __name__ == "__main__":
    unittest.main()
