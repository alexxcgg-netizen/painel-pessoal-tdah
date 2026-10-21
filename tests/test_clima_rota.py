"""Tempo ao longo da rota (clima_rota.py, 2026-10-21): chove num trecho e no outro nao, neblina
na serra. Sem rede: o Open-Meteo e mockado."""

import unittest
from datetime import datetime
from unittest import mock

import cards
import clima_rota
import maps_client

# ~200 km em linha reta pro norte (1 grau de latitude ~ 111 km), 201 pontos
CAMINHO = [(-27.0 + i * 0.009, -48.9) for i in range(201)]


def _local(tipo_por_hora: dict, elevacao=20):
    """Resposta do Open-Meteo pra um ponto: 48 h a partir de 2026-10-21 00:00."""
    horas = [f"2026-10-{21 + h // 24}T{h % 24:02d}:00" for h in range(48)]
    base = {"precipitation_probability": [0] * 48, "precipitation": [0.0] * 48, "weathercode": [1] * 48,
            "visibility": [20000] * 48, "wind_gusts_10m": [15] * 48}
    for h, (campo, valor) in tipo_por_hora.items():
        base[campo][h] = valor
    return {"elevation": elevacao, "hourly": {"time": horas, **base}}


class TestPuro(unittest.TestCase):
    def test_amostrar_a_cada_20_km_com_inicio_e_fim(self):
        a = clima_rota.amostrar(CAMINHO)
        self.assertEqual(a[0]["km"], 0)
        self.assertAlmostEqual(a[-1]["km"], 200, delta=2)
        self.assertEqual(a[-1]["i"], len(CAMINHO) - 1)
        self.assertTrue(9 <= len(a) <= 12)

    def test_amostrar_rota_enorme_nao_passa_do_maximo(self):
        longe = [(-27.0 + i * 0.05, -48.9) for i in range(201)]  # ~1100 km
        self.assertLessEqual(len(clima_rota.amostrar(longe)), clima_rota.MAX_AMOSTRAS + 1)

    def test_classificar_pior_primeiro(self):
        c = clima_rota.classificar
        self.assertEqual(c({"codigo": 96, "visibilidade_m": 200}), "granizo")
        self.assertEqual(c({"codigo": 61, "chuva_pct": 90, "visibilidade_m": 300}), "neblina")
        self.assertEqual(c({"codigo": 45}), "neblina")
        self.assertEqual(c({"codigo": 63, "mm": 6}), "chuva_forte")
        self.assertEqual(c({"codigo": 3, "chuva_pct": 70}), "chuva")
        self.assertEqual(c({"codigo": 1, "rajada_kmh": 75}), "vento")
        self.assertEqual(c({"codigo": 1, "chuva_pct": 20, "visibilidade_m": 15000}), "ok")
        self.assertEqual(c({}), "ok")

    def test_interpretar_saida(self):
        agora = datetime(2026, 10, 21, 10, 0)
        self.assertEqual(clima_rota.interpretar_saida("14:30", agora), datetime(2026, 10, 21, 14, 30))
        self.assertEqual(clima_rota.interpretar_saida("07:00", agora), datetime(2026, 10, 22, 7, 0))
        self.assertEqual(clima_rota.interpretar_saida("2026-10-23T06:15", agora), datetime(2026, 10, 23, 6, 15))
        for ruim in (None, "", "amanha cedo", "25:99", "2026-13-01 10:00"):
            self.assertIsNone(clima_rota.interpretar_saida(ruim, agora), ruim)


class TestTempoNaRota(unittest.TestCase):
    def _rodar(self, por_ponto, partida=datetime(2026, 10, 21, 8, 0), duracao=180, nomear=None):
        def buscar(amostras, dias):
            return [por_ponto(n, a) for n, a in enumerate(amostras)]

        with mock.patch.object(clima_rota, "_buscar", side_effect=buscar), \
                mock.patch.object(clima_rota, "datetime", wraps=datetime) as dt:
            dt.now.return_value = datetime(2026, 10, 21, 7, 0)
            return clima_rota.tempo_na_rota(CAMINHO, duracao, partida, nomear=nomear)

    def test_chuva_so_no_meio_e_neblina_na_serra_no_fim(self):
        def por_ponto(n, a):
            if 40 <= a["km"] <= 100:  # passa ai entre ~8h40 e ~9h30
                return _local({h: ("precipitation_probability", 85) for h in range(24)})
            if a["km"] >= 160:
                return _local({h: ("visibility", 300) for h in range(24)}, elevacao=900)
            return _local({})

        nomes = []
        r = self._rodar(por_ponto, nomear=lambda lat, lon: nomes.append((lat, lon)) or "BR-277, Exemplo")
        tipos = [t["tipo"] for t in r["trechos"]]
        self.assertEqual(tipos, ["ok", "chuva", "ok", "neblina"])
        chuva, neblina = r["trechos"][1], r["trechos"][3]
        self.assertLess(chuva["de_km"], chuva["ate_km"])
        self.assertEqual(neblina["ate_km"], r["total_km"])
        self.assertTrue(neblina["serra"])
        self.assertEqual(neblina["visibilidade_m"], 300)
        self.assertEqual(len(nomes), 2)  # so os trechos ruins ganham nome
        self.assertIn("Neblina na serra (BR-277, Exemplo)", r["resumo"])
        self.assertIn("visibilidade 300 m", r["resumo"])
        self.assertIn("85% de chance", r["resumo"])
        self.assertIn("tempo firme", r["resumo"])
        # indices pro mapa: crescentes e dentro do caminho
        for t in r["trechos"]:
            self.assertTrue(0 <= t["i0"] <= t["i1"] < len(CAMINHO))

    def test_hora_de_passagem_acompanha_a_saida(self):
        # so chove as 15h: saindo as 8h nao pega; saindo as 14h pega no fim do caminho
        def por_ponto(n, a):
            return _local({15: ("precipitation_probability", 90)})

        self.assertEqual(self._rodar(por_ponto)["resumo"], "Tempo firme no caminho todo.")
        r = self._rodar(por_ponto, partida=datetime(2026, 10, 21, 14, 0))  # 14h -> 17h: pega no meio
        chuva = [t for t in r["trechos"] if t["tipo"] == "chuva"]
        self.assertEqual(len(chuva), 1)
        self.assertTrue(chuva[0]["hora_ini"].startswith("15"))
        self.assertEqual(r["trechos"][0]["tipo"], "ok")
        self.assertEqual(r["trechos"][-1]["tipo"], "ok")

    def test_rota_curta_ou_sem_rede_devolve_none(self):
        curto = CAMINHO[:20]  # ~20 km
        with mock.patch.object(clima_rota, "_buscar") as b:
            self.assertIsNone(clima_rota.tempo_na_rota(curto, 25))
            b.assert_not_called()
        with mock.patch.object(clima_rota, "_buscar", return_value=None):
            self.assertIsNone(clima_rota.tempo_na_rota(CAMINHO, 180))

    def test_resposta_estranha_da_api_nao_quebra(self):
        with mock.patch.object(clima_rota, "_buscar", side_effect=lambda a, d: [{"hourly": {}}] * len(a)):
            self.assertIsNone(clima_rota.tempo_na_rota(CAMINHO, 180))


class TestAtividadeQueAChuvaEstraga(unittest.TestCase):
    """"Vou lavar o carro as 14" (clima.analisar_janela / dia_seco_pra)."""

    def _horas(self, chuva: dict):
        return [{"quando": f"2026-10-{21 + h // 24}T{h % 24:02d}:00", "chuva_pct": chuva.get(h, (5, 0))[0],
                 "mm": chuva.get(h, (5, 0))[1], "codigo": 63 if h in chuva else 1} for h in range(48)]

    def test_chuva_5_h_depois_dentro_da_janela_quase_certa(self):
        import clima
        r = clima.analisar_janela(self._horas({19: (90, 2.5), 20: (85, 1.0)}), datetime(2026, 10, 21, 14, 0), 24)
        self.assertTrue(r["chove"])
        self.assertEqual(r["em_horas"], 5)
        self.assertEqual(r["certeza"], "quase_certa")
        self.assertEqual(r["mm_na_janela"], 3.5)
        self.assertEqual(r["condicao"], "chuva")

    def test_chance_media_e_provavel_e_fora_da_janela_nao_conta(self):
        import clima
        provavel = clima.analisar_janela(self._horas({16: (60, 0)}), datetime(2026, 10, 21, 14, 30), 6)
        self.assertEqual((provavel["em_horas"], provavel["certeza"]), (2, "provavel"))
        seco = clima.analisar_janela(self._horas({22: (90, 3)}), datetime(2026, 10, 21, 14, 0), 6)
        self.assertEqual(seco, {"coberto": True, "chove": False, "pior_pct": 5})
        self.assertFalse(clima.analisar_janela([], datetime(2026, 10, 21, 14, 0), 6)["coberto"])

    def test_dia_seco_precisa_dos_dias_seguidos(self):
        import clima
        prev = [{"data": f"2026-10-{d}", "chuva_pct": p} for d, p in
                ((22, 80), (23, 10), (24, 70), (25, 20), (26, 15))]
        self.assertEqual(clima.dia_seco_pra(prev, "2026-10-22")["data"], "2026-10-23")
        self.assertEqual(clima.dia_seco_pra(prev, "2026-10-22", dias_secos=2)["data"], "2026-10-25")
        self.assertIsNone(clima.dia_seco_pra(prev, "2026-10-22", dias_secos=4))


class TestCardEMapa(unittest.TestCase):
    def test_traco_ganha_faixas_de_tempo(self):
        t = maps_client.traco_desenhavel(CAMINHO, [0, 200], tempo=[(50, 90, "chuva"), (5, 2, "neblina")])
        self.assertEqual(len(t["tempo"]), 1)
        self.assertEqual(t["tempo"][0]["nivel"], "chuva")
        self.assertNotIn("tempo", maps_client.traco_desenhavel(CAMINHO, [0, 200]))

    def test_card_rota_filtra_o_tempo(self):
        ef = {"url": "https://www.google.com/maps/dir/?api=1", "paradas": [{"nome": "A"}, {"nome": "B"}],
              "tempo": {"total_km": 200, "saida": "08:00", "trechos": [
                  {"tipo": "chuva", "de_km": 40, "ate_km": 100, "hora_ini": "08:40", "frase": "Chuva do km 40 ao 100"},
                  {"tipo": "tornado", "de_km": 1, "ate_km": 2},
                  {"tipo": "ok", "de_km": "x", "ate_km": 3},
              ]}}
        tempo = cards.card_rota(ef)["data"]["tempo"]
        self.assertEqual([t["tipo"] for t in tempo["trechos"]], ["chuva"])
        self.assertEqual(tempo["trechos"][0]["hora"], "08:40")
        self.assertIsNone(cards.card_rota({**ef, "tempo": {"total_km": 0}})["data"]["tempo"])
        self.assertIsNone(cards.card_rota({**ef, "tempo": None})["data"]["tempo"])


if __name__ == "__main__":
    unittest.main()
