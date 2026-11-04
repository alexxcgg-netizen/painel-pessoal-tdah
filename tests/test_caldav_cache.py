"""caldav_client.eventos_do_dia: cache curto pra nao ir ao iCloud duas vezes por chamada."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import caldav_client

DIA = date(2026, 10, 30)


def _resultado(titulo="Reuniao"):
    return MagicMock(icalendar_component={"DTSTART": MagicMock(dt=DIA), "SUMMARY": titulo})


def _cliente(*calendarios):
    cliente = MagicMock()
    cliente.__enter__.return_value = cliente
    cliente.principal.return_value.calendars.return_value = list(calendarios)
    return cliente


def _calendario(*resultados):
    calendario = MagicMock()
    calendario.search.return_value = list(resultados)
    return calendario


class CacheEventosTestCase(unittest.TestCase):
    def setUp(self):
        caldav_client.limpar_cache()
        self.addCleanup(caldav_client.limpar_cache)

    def test_segunda_busca_nao_volta_ao_icloud(self):
        calendario = _calendario(_resultado())
        with patch("caldav_client._client", return_value=_cliente(calendario)) as client:
            primeira = caldav_client.eventos_do_dia(DIA)
            segunda = caldav_client.eventos_do_dia(DIA)
        self.assertEqual(primeira, segunda)
        self.assertEqual(client.call_count, 1)

    def test_quem_mexe_no_resultado_nao_suja_o_cache(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario(_resultado()))):
            caldav_client.eventos_do_dia(DIA)
            guardada = caldav_client.eventos_do_dia(DIA)
            guardada[0]["titulo"] = "mexido"
            guardada.clear()
            self.assertEqual(caldav_client.eventos_do_dia(DIA)[0]["titulo"], "Reuniao")

    def test_primeira_busca_tambem_nao_divide_o_dict_com_o_cache(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario(_resultado()))):
            caldav_client.eventos_do_dia(DIA)[0]["titulo"] = "mexido"
            self.assertEqual(caldav_client.eventos_do_dia(DIA)[0]["titulo"], "Reuniao")

    def test_cache_vence(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario(_resultado()))) as client, patch(
            "caldav_client.monotonic", side_effect=[100.0, 100.0 + caldav_client._CACHE_SEGUNDOS + 1, 200.0]
        ):
            caldav_client.eventos_do_dia(DIA)
            caldav_client.eventos_do_dia(DIA)
        self.assertEqual(client.call_count, 2)

    def test_dias_diferentes_nao_se_misturam(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario(_resultado()))) as client:
            caldav_client.eventos_do_dia(DIA)
            caldav_client.eventos_do_dia(date(2026, 10, 31))
        self.assertEqual(client.call_count, 2)

    def test_busca_parcial_nao_entra_no_cache(self):
        ruim = MagicMock()
        ruim.search.side_effect = RuntimeError("iCloud instavel")
        with patch("caldav_client._client", return_value=_cliente(ruim, _calendario(_resultado()))) as client:
            self.assertEqual(len(caldav_client.eventos_do_dia(DIA)), 1)
            caldav_client.eventos_do_dia(DIA)
        self.assertEqual(client.call_count, 2)

    def test_criar_evento_limpa_o_cache(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario())) as client, patch(
            "caldav_client.configurado", return_value=True
        ), patch("caldav_client._calendario_painel"):
            caldav_client.eventos_do_dia(DIA)
            from datetime import datetime

            caldav_client.criar_evento("X", datetime(2026, 10, 30, 14), datetime(2026, 10, 30, 15))
            antes = client.call_count
            caldav_client.eventos_do_dia(DIA)
        self.assertEqual(client.call_count, antes + 1)

    def test_apagar_evento_limpa_o_cache(self):
        with patch("caldav_client._client", return_value=_cliente(_calendario())) as client, patch(
            "caldav_client.configurado", return_value=True
        ), patch("caldav_client._calendario_painel"), patch("caldav_client._achar_por_uid"):
            caldav_client.eventos_do_dia(DIA)
            self.assertTrue(caldav_client.apagar_evento("uid"))
            antes = client.call_count
            caldav_client.eventos_do_dia(DIA)
        self.assertEqual(client.call_count, antes + 1)


if __name__ == "__main__":
    unittest.main()
