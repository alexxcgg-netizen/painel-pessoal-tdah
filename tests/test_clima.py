import random
import unittest
from unittest.mock import MagicMock, patch

import requests

import clima


def _hora(h, pct, temp=20.0, codigo=3):
    return {"hora": h, "chuva_pct": pct, "temp": temp, "codigo": codigo}


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

    def test_previsao_horaria_hoje_encontrada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {
            "hourly": {
                "time": ["2026-09-18T00:00", "2026-09-18T14:00"],
                "precipitation_probability": [0, 80],
                "temperature_2m": [14.0, 21.0],
                "weathercode": [3, 51],
            }
        }
        with patch("clima.requests.get", return_value=resposta):
            horas = clima.previsao_horaria_hoje(-27.0, -49.0)
        self.assertEqual(horas, [_hora(0, 0, 14.0, 3), _hora(14, 80, 21.0, 51)])

    def test_previsao_horaria_erro_de_rede_devolve_none(self):
        with patch("clima.requests.get", side_effect=requests.RequestException("timeout")):
            self.assertIsNone(clima.previsao_horaria_hoje(-27.0, -49.0))

    def test_previsao_horaria_resposta_mal_formada_devolve_none(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {"hourly": {"time": ["2026-09-18T00:00"]}}  # sem os outros campos
        with patch("clima.requests.get", return_value=resposta):
            self.assertIsNone(clima.previsao_horaria_hoje(-27.0, -49.0))


class ResumoChuvaDoDiaTestCase(unittest.TestCase):
    def setUp(self):
        clima._cache_geocodificacao.clear()

    def test_sem_horas_futuras(self):
        r = clima.resumo_chuva_do_dia([_hora(10, 90)], hora_atual=14)
        self.assertFalse(r["alerta"])
        self.assertIn("Sem mais previsao", r["texto"])

    def test_lista_vazia(self):
        r = clima.resumo_chuva_do_dia([], hora_atual=10)
        self.assertFalse(r["alerta"])

    def test_sem_risco_significativo(self):
        horas = [_hora(h, 20) for h in range(10, 20)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=10)
        self.assertFalse(r["alerta"])
        self.assertEqual(r["chuva_pct_max"], 20)

    def test_bloco_continuo_simples(self):
        horas = [_hora(10, 10), _hora(11, 30), _hora(12, 60), _hora(13, 80), _hora(14, 55), _hora(15, 20)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=10, limite_pct=50)
        self.assertTrue(r["alerta"])
        self.assertEqual(r["hora_inicio"], 12)
        self.assertEqual(r["hora_fim"], 15)
        self.assertEqual(r["chuva_pct_max"], 80)

    def test_gap_quebra_o_bloco_continuo(self):
        # pico as 15h (70%), mas 14h cai pra 20% - o bloco nao pode "pular" a hora seca
        horas = [_hora(13, 60), _hora(14, 20), _hora(15, 70), _hora(16, 55)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=13, limite_pct=50)
        self.assertTrue(r["alerta"])
        self.assertEqual(r["hora_inicio"], 15)
        self.assertEqual(r["hora_fim"], 17)

    def test_ignora_horas_ja_passadas(self):
        horas = [_hora(8, 95), _hora(14, 10)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=10, limite_pct=50)
        self.assertFalse(r["alerta"])  # a hora de 95% ja passou, so sobrou a de 10%

    def test_bloco_ate_o_fim_do_dia(self):
        horas = [_hora(h, 90) for h in range(20, 24)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=20, limite_pct=50)
        self.assertTrue(r["alerta"])
        self.assertEqual(r["hora_fim"], 24)
        self.assertIn("o fim do dia", r["texto"])

    def test_chovendo_agora_true_quando_hora_atual_esta_no_limite(self):
        horas = [_hora(14, 90), _hora(15, 30)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=14, limite_pct=50)
        self.assertTrue(r["chovendo_agora"])

    def test_chovendo_agora_false_quando_hora_atual_fica_abaixo(self):
        horas = [_hora(14, 10), _hora(15, 90)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=14, limite_pct=50)
        self.assertFalse(r["chovendo_agora"])

    def test_empate_no_pico_fica_com_a_primeira_ocorrencia(self):
        horas = [_hora(10, 80), _hora(11, 20), _hora(12, 80)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=10, limite_pct=50)
        # o pico "oficial" e o primeiro (10h), e como 11h fica abaixo do limite,
        # o bloco continuo em volta dele e so [10h, 11h) - nao junta com o de 12h
        self.assertEqual(r["hora_inicio"], 10)
        self.assertEqual(r["hora_fim"], 11)

    def test_limite_e_inclusivo(self):
        horas = [_hora(10, 50)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=10, limite_pct=50)
        self.assertTrue(r["alerta"])

    def test_horas_fora_de_ordem_no_input_nao_afetam_resultado(self):
        horas = [_hora(15, 20), _hora(12, 80), _hora(13, 70), _hora(14, 10)]
        r = clima.resumo_chuva_do_dia(horas, hora_atual=12, limite_pct=50)
        self.assertEqual(r["hora_inicio"], 12)
        self.assertEqual(r["hora_fim"], 14)

    def test_fuzz_janela_respeita_invariantes(self):
        """Stress test: gera 300 dias aleatorios de chuva hora a hora e
        confere invariantes da janela encontrada (nunca um valor exato de
        referencia, mas propriedades que TEM que valer sempre):
        - toda hora dentro da janela tem chuva >= limite
        - a hora logo antes/depois da janela (se existir nos dados) quebra
          a continuidade (chuva abaixo do limite ou hora nao consecutiva)
        - o pico (maior chuva_pct entre as horas futuras) esta dentro da janela
        """
        random.seed(7)
        limite = 50
        for _ in range(300):
            hora_atual = random.randint(0, 23)
            horas = [
                _hora(h, random.choice([0, 10, 30, 49, 50, 51, 70, 90, 100]))
                for h in range(24)
                if random.random() < 0.85
            ]
            if not horas:
                continue
            r = clima.resumo_chuva_do_dia(horas, hora_atual, limite_pct=limite)

            futuras = sorted((h for h in horas if h["hora"] >= hora_atual), key=lambda h: h["hora"])
            if not futuras:
                self.assertFalse(r["alerta"])
                continue
            pico_pct = max(h["chuva_pct"] for h in futuras)
            if pico_pct < limite:
                self.assertFalse(r["alerta"], msg=f"nao deveria alertar: {horas} hora_atual={hora_atual}")
                continue

            self.assertTrue(r["alerta"])
            por_hora = {h["hora"]: h["chuva_pct"] for h in futuras}
            janela = range(r["hora_inicio"], min(r["hora_fim"], 24))

            # pico esta dentro da janela
            pico_horas = {h["hora"] for h in futuras if h["chuva_pct"] == pico_pct}
            self.assertTrue(
                pico_horas & set(janela), msg=f"pico fora da janela: {r} pico_horas={pico_horas}"
            )

            # toda hora com dado dentro da janela esta acima do limite
            for h in janela:
                if h in por_hora:
                    self.assertGreaterEqual(por_hora[h], limite, msg=f"{r} horas={horas}")

            # a hora imediatamente anterior a janela (se existir nos dados e
            # for consecutiva) tem que estar abaixo do limite
            antes = r["hora_inicio"] - 1
            if antes in por_hora:
                self.assertLess(por_hora[antes], limite, msg=f"janela deveria ter incluido {antes}h: {r}")

            depois = r["hora_fim"]
            if depois in por_hora:
                self.assertLess(por_hora[depois], limite, msg=f"janela deveria ter incluido {depois}h: {r}")

    def test_resumo_chuva_hoje_para_cidade_encadeia_tudo(self):
        resp_geo = MagicMock()
        resp_geo.raise_for_status = lambda: None
        resp_geo.json.return_value = {
            "results": [{"latitude": -27.0, "longitude": -49.06, "name": "Blumenau"}]
        }
        resp_horaria = MagicMock()
        resp_horaria.raise_for_status = lambda: None
        resp_horaria.json.return_value = {
            "hourly": {
                "time": [f"2026-09-18T{h:02d}:00" for h in range(24)],
                "precipitation_probability": [10] * 14 + [80] * 10,
                "temperature_2m": [20.0] * 24,
                "weathercode": [3] * 24,
            }
        }
        with patch("clima.requests.get", side_effect=[resp_geo, resp_horaria]), patch(
            "clima.datetime"
        ) as mock_dt:
            mock_dt.now.return_value.hour = 12
            r = clima.resumo_chuva_hoje_para_cidade("Blumenau")
        self.assertEqual(r["cidade"], "Blumenau")
        self.assertTrue(r["alerta"])
        self.assertEqual(r["hora_inicio"], 14)

    def test_resumo_chuva_hoje_cidade_nao_encontrada(self):
        resposta = MagicMock()
        resposta.raise_for_status = lambda: None
        resposta.json.return_value = {"results": []}
        with patch("clima.requests.get", return_value=resposta):
            self.assertIsNone(clima.resumo_chuva_hoje_para_cidade("CidadeInventada"))

    def test_resumo_chuva_hoje_falha_na_previsao_horaria(self):
        resp_geo = MagicMock()
        resp_geo.raise_for_status = lambda: None
        resp_geo.json.return_value = {
            "results": [{"latitude": -27.0, "longitude": -49.06, "name": "Blumenau"}]
        }
        with patch(
            "clima.requests.get", side_effect=[resp_geo, requests.RequestException("timeout")]
        ):
            self.assertIsNone(clima.resumo_chuva_hoje_para_cidade("Blumenau"))


if __name__ == "__main__":
    unittest.main()
