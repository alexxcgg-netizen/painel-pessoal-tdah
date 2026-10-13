"""Briefing meteorologico do voo (2026-10-13): briefing_voo.py + ferramenta do chat +
card. Rede sempre falsa (buscar injetado / patch) - nunca chama aviationweather."""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import briefing_voo  # noqa: E402
import cards  # noqa: E402
import metar  # noqa: E402

METAR_SBNF = "METAR SBNF 131100Z 26006KT 3000 -DZ BR OVC003 19/18 Q1012"
TAF_SBNF = ("TAF SBNF 130900Z 1312/1412 26007KT 8000 SCT012 BKN020 TX22/1317Z TN18/1408Z "
            "TEMPO 1312/1316 30007KT 5000 RA BKN008 BKN020 RMK PEB")
AGORA = datetime(2026, 10, 13, 11, 22, tzinfo=timezone.utc)  # 08:22 em Brasilia


def _buscar_falso(pedidos):
    def buscar(icao):
        pedidos.append(icao)
        if icao != "SBNF":
            return {"metar": None, "taf": None, "erro": f"nenhum dado encontrado pra {icao}"}
        dec = metar.decodificar_grupo(metar._tokens_uteis_metar(METAR_SBNF))
        return {"metar": METAR_SBNF, "taf": TAF_SBNF, "erro": None, "metar_decodificado": dec,
                "metar_categoria": metar.categoria_voo(dec),
                "taf_segmentos": metar.decodificar_taf(metar._tokens_uteis_taf(TAF_SBNF))}
    return buscar


class FenomenosTestCase(unittest.TestCase):
    def test_traducoes(self):
        casos = {
            "-DZ": "chuvisco fraco", "BR": "névoa úmida", "TSRA": "trovoada com chuva",
            "VCSH": "pancadas nas proximidades", "+SHRA": "pancadas de chuva fortes", "FG": "nevoeiro",
            "BCFG": "nevoeiro em bancos", "-RA": "chuva fraca", "+TSRA": "trovoada com chuva forte",
        }
        for tok, esperado in casos.items():
            with self.subTest(tok=tok):
                self.assertEqual(briefing_voo.traduzir_fenomeno(tok), esperado)

    def test_o_que_nao_e_fenomeno_volta_none(self):
        for tok in ("9999", "Q1012", "OVC003", "26006KT", "19/18", "", None, "XYZ", "TEMPO"):
            with self.subTest(tok=tok):
                self.assertIsNone(briefing_voo.traduzir_fenomeno(tok))


class MontarTestCase(unittest.TestCase):
    def test_ssbl_cai_pra_sbnf_e_avisa(self):
        pedidos = []
        r = briefing_voo.montar(None, "ssbl", agora_utc=AGORA, buscar=_buscar_falso(pedidos))
        self.assertEqual(pedidos, ["SBNF"])
        self.assertEqual(r["icao"], "SBNF")
        self.assertEqual(r["substituto_de"], "SSBL")
        self.assertEqual(r["categoria"], "LIFR")
        self.assertEqual(r["teto_ft"], 300)
        self.assertEqual(r["observado"], "08:00")
        self.assertEqual(r["idade_min"], 22)
        self.assertEqual(r["fenomenos"], ["chuvisco fraco", "névoa úmida"])
        self.assertTrue(r["windy_url"].startswith("https://www.windy.com/?-26.880,-48.651"))

    def test_taf_em_horario_de_brasilia_com_amanha(self):
        r = briefing_voo.montar(None, "SBNF", agora_utc=AGORA, buscar=_buscar_falso([]))
        inicial, tempo = r["taf"][0], r["taf"][1]
        self.assertEqual((inicial["de"], inicial["ate"], inicial["categoria"]), ("09:00", "amanhã 09:00", "MVFR"))
        self.assertEqual((tempo["rotulo"], tempo["de"], tempo["ate"], tempo["categoria"]),
                         ("Temporariamente", "09:00", "13:00", "IFR"))
        self.assertIn("chuva", tempo["resumo"])

    def test_resumo_so_descreve_nunca_libera(self):
        r = briefing_voo.montar(None, "SBNF", agora_utc=AGORA, buscar=_buscar_falso([]))
        self.assertIn("LIFR", r["resumo"])
        self.assertIn("teto 300 pés", r["resumo"])
        for proibido in ("pode voar", "liberado", "seguro", "não voe"):
            self.assertNotIn(proibido, r["resumo"].lower())
        self.assertIn("decisão de voar é sua", r["aviso"])

    def test_sem_icao_usa_origem_do_proximo_voo(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"data": "2026-10-13", "hora": "14:00",
                                                           "origem": "SBJV", "destino": "Local"}
        pedidos = []
        r = briefing_voo.montar(conn, None, agora_utc=AGORA, buscar=_buscar_falso(pedidos))
        self.assertEqual(pedidos, ["SBJV"])
        self.assertIn("erro", r)  # o falso so conhece SBNF

    def test_icao_invalido_cai_no_padrao(self):
        pedidos = []
        with patch.dict(os.environ, {"ICAO_PADRAO": ""}):
            briefing_voo.montar(None, "x; drop", agora_utc=AGORA, buscar=_buscar_falso(pedidos))
        self.assertEqual(pedidos, ["SBNF"])  # SSBL padrao -> SBNF

    def test_rede_quebrada_nao_levanta(self):
        def quebra(_icao):
            raise RuntimeError("timeout")
        r = briefing_voo.montar(None, "SBNF", agora_utc=AGORA, buscar=quebra)
        self.assertIn("erro", r)


class CardTestCase(unittest.TestCase):
    def test_efeito_vira_card_com_link_do_windy(self):
        dados = briefing_voo.montar(None, "SBNF", agora_utc=AGORA, buscar=_buscar_falso([]))
        lista = cards.cards_dos_efeitos(None, [{"entidade": "briefing_voo", "consulta": True, "dados": dados}])
        self.assertEqual(len(lista), 1)
        c = lista[0]
        self.assertEqual(c["type"], "briefing_voo")
        self.assertEqual(c["data"]["categoria"], "LIFR")
        self.assertEqual(c["actions"][0]["tipo"], "abrir_link")
        self.assertTrue(c["actions"][0]["url"].startswith("https://www.windy.com/"))
        self.assertIn("briefing_voo", cards.TIPOS_CARD)

    def test_url_estranha_nao_vira_link(self):
        c = cards.card_briefing_voo({"dados": {"icao": "SBNF", "windy_url": "https://malicioso.example/"}})
        self.assertEqual(c["actions"], [])

    def test_ferramenta_registrada_no_chat(self):
        from ia.funcoes.chat import CHAT_TOOLS
        nomes = [t["name"] for t in CHAT_TOOLS]
        self.assertIn("briefing_meteo_voo", nomes)


if __name__ == "__main__":
    unittest.main()
