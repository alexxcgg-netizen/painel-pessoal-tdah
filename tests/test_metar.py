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

    def test_busca_com_sucesso_anexa_decodificacao(self):
        resp_metar = MagicMock()
        resp_metar.raise_for_status = lambda: None
        resp_metar.text = "SBBI 182200Z 09007KT 060V140 9999 BKN008 OVC013 15/13 Q1025"
        resp_taf = MagicMock()
        resp_taf.raise_for_status = lambda: None
        resp_taf.text = "TAF SBBI 181600Z 1818/1906 08007KT 8000 BKN013 BECMG 1820/1822 BKN010 RMK PAG"

        with patch("metar.requests.get", side_effect=[resp_metar, resp_taf]):
            r = metar.buscar_metar_taf("SBBI")

        self.assertEqual(r["metar_decodificado"]["teto_ft"], 800)
        self.assertIn("800", r["metar_falado"])
        self.assertEqual(len(r["taf_segmentos"]), 2)
        self.assertIn("Tornando-se", r["taf_falado"])

    def test_sem_dado_nenhum_decodificacao_fica_none(self):
        resp_vazio = MagicMock()
        resp_vazio.raise_for_status = lambda: None
        resp_vazio.text = ""
        with patch("metar.requests.get", return_value=resp_vazio):
            r = metar.buscar_metar_taf("ZZZZ")
        self.assertIsNone(r["metar_decodificado"])
        self.assertIsNone(r["metar_falado"])
        self.assertIsNone(r["taf_segmentos"])
        self.assertIsNone(r["taf_falado"])


class DecodificarGrupoTestCase(unittest.TestCase):
    def test_vento_normal(self):
        d = metar.decodificar_grupo(["09007KT"])
        self.assertEqual(d["vento"], {"direcao": 90, "variavel": False, "velocidade_kt": 7, "rajada_kt": None})

    def test_vento_com_rajada(self):
        d = metar.decodificar_grupo(["18025G40KT"])
        self.assertEqual(d["vento"]["velocidade_kt"], 25)
        self.assertEqual(d["vento"]["rajada_kt"], 40)

    def test_vento_calmo(self):
        d = metar.decodificar_grupo(["00000KT"])
        self.assertEqual(d["vento"]["velocidade_kt"], 0)
        self.assertFalse(d["vento"]["variavel"])

    def test_vento_variavel(self):
        d = metar.decodificar_grupo(["VRB03KT"])
        self.assertTrue(d["vento"]["variavel"])
        self.assertIsNone(d["vento"]["direcao"])

    def test_vento_com_direcao_variavel_entre(self):
        d = metar.decodificar_grupo(["09007KT", "060V140"])
        self.assertEqual(d["vento"]["variavel_entre"], [60, 140])

    def test_direcao_variavel_sem_vento_antes_e_ignorada(self):
        # nao deveria acontecer na pratica (sempre vem depois do grupo de
        # vento), mas nao pode quebrar se vier sozinha
        d = metar.decodificar_grupo(["060V140"])
        self.assertIsNone(d["vento"])

    def test_visibilidade_10km_ou_mais(self):
        d = metar.decodificar_grupo(["9999"])
        self.assertEqual(d["visibilidade_m"], 9999)

    def test_visibilidade_em_metros(self):
        d = metar.decodificar_grupo(["3000"])
        self.assertEqual(d["visibilidade_m"], 3000)

    def test_cavok_define_visibilidade_maxima(self):
        d = metar.decodificar_grupo(["CAVOK"])
        self.assertEqual(d["visibilidade_m"], 9999)
        self.assertEqual(d["nuvens"], [])

    def test_uma_camada_de_nuvem(self):
        d = metar.decodificar_grupo(["SCT030"])
        self.assertEqual(d["nuvens"], [{"tipo": "SCT", "altura_ft": 3000}])
        self.assertIsNone(d["teto_ft"])  # SCT nao forma teto

    def test_teto_e_a_camada_bkn_ovc_mais_baixa(self):
        d = metar.decodificar_grupo(["FEW005", "BKN008", "OVC013"])
        self.assertEqual(d["teto_ft"], 800)

    def test_few_e_sct_nunca_viram_teto_mesmo_sendo_a_unica_camada(self):
        d = metar.decodificar_grupo(["FEW005", "SCT010"])
        self.assertIsNone(d["teto_ft"])

    def test_visibilidade_vertical_conta_como_teto(self):
        d = metar.decodificar_grupo(["VV004"])
        self.assertEqual(d["teto_ft"], 400)
        self.assertEqual(d["nuvens"][0]["tipo"], "VV")

    def test_ceu_claro_nao_gera_nuvem(self):
        for tok in ["NSC", "SKC", "CLR"]:
            d = metar.decodificar_grupo([tok])
            self.assertEqual(d["nuvens"], [], msg=tok)

    def test_temperatura_positiva(self):
        d = metar.decodificar_grupo(["15/13"])
        self.assertEqual(d["temp"], 15)
        self.assertEqual(d["ponto_orvalho"], 13)

    def test_temperatura_negativa(self):
        d = metar.decodificar_grupo(["M02/M05"])
        self.assertEqual(d["temp"], -2)
        self.assertEqual(d["ponto_orvalho"], -5)

    def test_temperatura_mista(self):
        d = metar.decodificar_grupo(["03/M01"])
        self.assertEqual(d["temp"], 3)
        self.assertEqual(d["ponto_orvalho"], -1)

    def test_qnh_hectopascais(self):
        d = metar.decodificar_grupo(["Q1013"])
        self.assertEqual(d["qnh_hpa"], 1013)

    def test_altimetro_inhg(self):
        d = metar.decodificar_grupo(["A2992"])
        self.assertEqual(d["altimetro_inhg"], 29.92)

    def test_tokens_desconhecidos_sao_ignorados_sem_quebrar(self):
        d = metar.decodificar_grupo(["RA", "TSRA", "BR", "XYZ123"])
        self.assertIsNone(d["vento"])
        self.assertEqual(d["nuvens"], [])

    def test_lista_vazia(self):
        d = metar.decodificar_grupo([])
        self.assertIsNone(d["vento"])
        self.assertIsNone(d["teto_ft"])

    def test_metar_real_capturado_sbbi(self):
        tokens = metar._tokens_uteis_metar(
            "SBBI 182200Z 09007KT 060V140 9999 BKN008 OVC013 15/13 Q1025"
        )
        d = metar.decodificar_grupo(tokens)
        self.assertEqual(d["vento"]["direcao"], 90)
        self.assertEqual(d["vento"]["velocidade_kt"], 7)
        self.assertEqual(d["visibilidade_m"], 9999)
        self.assertEqual(d["teto_ft"], 800)
        self.assertEqual(d["temp"], 15)
        self.assertEqual(d["ponto_orvalho"], 13)
        self.assertEqual(d["qnh_hpa"], 1025)

    def test_tokens_uteis_metar_com_prefixo_metar_variavel(self):
        # a fonte as vezes manda o literal "METAR" na frente, as vezes nao -
        # os dois formatos tem que decodificar pro mesmo resultado
        com_prefixo = metar._tokens_uteis_metar("METAR SBBI 182300Z 08007KT 9999 BKN007 Q1025")
        sem_prefixo = metar._tokens_uteis_metar("SBBI 182300Z 08007KT 9999 BKN007 Q1025")
        self.assertEqual(
            metar.decodificar_grupo(com_prefixo), metar.decodificar_grupo(sem_prefixo)
        )


class ResumoFaladoTestCase(unittest.TestCase):
    def test_sem_nada_decodificado(self):
        vazio = metar.decodificar_grupo([])
        self.assertEqual(metar.resumo_falado(vazio), "Sem dados suficientes pra descrever.")

    def test_frase_comeca_maiuscula_e_termina_com_ponto(self):
        d = metar.decodificar_grupo(["09007KT"])
        texto = metar.resumo_falado(d)
        self.assertTrue(texto[0].isupper())
        self.assertTrue(texto.endswith("."))

    def test_menciona_teto_quando_tem_bkn_ovc(self):
        d = metar.decodificar_grupo(["BKN005"])
        self.assertIn("teto de 500 pes", metar.resumo_falado(d).lower())

    def test_nao_menciona_teto_quando_so_tem_few_sct(self):
        d = metar.decodificar_grupo(["FEW020"])
        self.assertNotIn("teto", metar.resumo_falado(d).lower())

    def test_ceu_limpo_quando_sem_nuvem(self):
        d = metar.decodificar_grupo(["9999"])
        self.assertIn("ceu limpo", metar.resumo_falado(d).lower())

    def test_nunca_menciona_categoria_de_voo(self):
        # garante que a frase falada nunca inclui julgamento tipo VFR/IFR -
        # isso tem que continuar sempre decisao do Alex, nunca do app
        d = metar.decodificar_grupo(
            ["09007KT", "9999", "BKN008", "OVC013", "15/13", "Q1025"]
        )
        texto = metar.resumo_falado(d).upper()
        for proibido in ("VFR", "IFR", "MVFR", "LIFR", "SEGURO", "PODE VOAR", "NAO VOAR"):
            self.assertNotIn(proibido, texto)


class DecodificarTafTestCase(unittest.TestCase):
    def test_taf_real_capturado_sbbi(self):
        taf = (
            "TAF SBBI 181600Z 1818/1906 08007KT 8000 BKN013 TX17/1818Z TN14/1906Z "
            "BECMG 1820/1822 BKN010 BECMG 1900/1902 BKN004 RMK PAG"
        )
        tokens = metar._tokens_uteis_taf(taf)
        segs = metar.decodificar_taf(tokens)
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[0]["tipo"], "Previsao inicial")
        self.assertEqual(segs[0]["decodificado"]["teto_ft"], 1300)
        self.assertEqual(segs[1]["tipo"], "Tornando-se")
        self.assertEqual(segs[1]["decodificado"]["teto_ft"], 1000)
        self.assertEqual(segs[2]["decodificado"]["teto_ft"], 400)

    def test_taf_ignora_remarks(self):
        tokens = metar._tokens_uteis_taf("TAF SBBI 181600Z 1818/1906 9999 RMK ISSO NAO DEVERIA APARECER")
        segs = metar.decodificar_taf(tokens)
        self.assertEqual(len(segs), 1)

    def test_taf_com_fm(self):
        tokens = metar._tokens_uteis_taf("TAF SBBI 181600Z 1818/1906 9999 FM181900 18015KT 6000 BKN015")
        segs = metar.decodificar_taf(tokens)
        self.assertEqual(len(segs), 2)
        self.assertIn("18", segs[1]["tipo"])
        self.assertEqual(segs[1]["decodificado"]["teto_ft"], 1500)

    def test_taf_com_prob_e_tempo_combinados(self):
        tokens = metar._tokens_uteis_taf(
            "TAF SBBI 181600Z 1818/1906 9999 PROB30 TEMPO 1820/1822 3000 TSRA BKN008"
        )
        segs = metar.decodificar_taf(tokens)
        self.assertEqual(segs[1]["tipo"], "Probabilidade 30% temporariamente")
        self.assertEqual(segs[1]["decodificado"]["teto_ft"], 800)

    def test_taf_com_prob_sem_tempo_seguido(self):
        # gramatica incomum (PROB direto seguido de meteo, sem TEMPO/BECMG) -
        # nao pode quebrar nem perder o grupo de nuvem
        tokens = metar._tokens_uteis_taf("TAF SBBI 181600Z 1818/1906 9999 PROB40 6000 BKN010")
        segs = metar.decodificar_taf(tokens)
        self.assertEqual(segs[1]["tipo"], "Probabilidade 40%")
        self.assertEqual(segs[1]["decodificado"]["teto_ft"], 1000)

    def test_taf_sem_nenhum_grupo_meteo_nao_quebra(self):
        segs = metar.decodificar_taf([])
        self.assertEqual(len(segs), 1)
        self.assertIsNone(segs[0]["decodificado"]["teto_ft"])

    def test_resumo_falado_taf_encadeia_segmentos(self):
        taf = (
            "TAF SBBI 181600Z 1818/1906 08007KT 8000 BKN013 "
            "BECMG 1820/1822 BKN010 RMK PAG"
        )
        tokens = metar._tokens_uteis_taf(taf)
        segs = metar.decodificar_taf(tokens)
        texto = metar.resumo_falado_taf(segs)
        self.assertIn("Previsao inicial", texto)
        self.assertIn("Tornando-se", texto)
        self.assertIn("1300", texto)
        self.assertIn("1000", texto)

    def test_resumo_falado_taf_vazio(self):
        self.assertEqual(
            metar.resumo_falado_taf([{"tipo": "Previsao inicial", "periodo": None, "decodificado": metar.decodificar_grupo([])}]),
            "Sem previsao detalhada disponivel.",
        )


if __name__ == "__main__":
    unittest.main()
