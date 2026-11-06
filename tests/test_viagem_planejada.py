"""Leva "painel mais esperto" (06/11/2026, docs/briefings/2026-11-06-painel-esperto.md, frentes 1, 2 e 5):
combustivel.py (abastecimento, consumo real, tanque estimado), viagem_planejada.py (rota com transito na hora
de sair, chuva por trecho, posto aberto na hora que passa, 3 saidas, noite, contrato plano_ativo), cards
`viagem`/`abastecimento`, rota comum com transito previsto pra saida, cota das buscas de lugar e a rota
POST /api/viagens-planejadas/<id>/saida. Nada de rede: Google/Open-Meteo/Claude sempre mockados; banco temporario."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import combustivel  # noqa: E402
import maps_client  # noqa: E402
import viagem_planejada as vp  # noqa: E402

PIN_TESTE = "123456"
# caminho inventado: reto pro norte, ~5,5 km entre pontos, 121 pontos = ~667 km
CAMINHO = [(-27.0 + i * 0.05, -48.9) for i in range(121)]
CURTO = [(-27.0 + i * 0.02, -48.9) for i in range(91)]  # ~200 km
SEXTA = datetime(2026, 11, 6, 8, 0)


def _horario(abre: int, fecha: int) -> list:
    """Todo dia de abre:00 a fecha:00 (formato periods do Google, dia 0 = domingo)."""
    return [{"open": {"day": d, "hour": abre, "minute": 0}, "close": {"day": d, "hour": fecha, "minute": 0}} for d in range(7)]


H24 = [{"open": {"day": 0, "hour": 0, "minute": 0}}]


class MapsFalso:
    """Mesma cara do maps_client nas funcoes que a viagem usa."""

    def __init__(self, caminho=CAMINHO, km=667.0, duracao=480, postos=None, transito=None, lentidao=None):
        self.caminho, self.km, self.duracao = caminho, km, duracao
        self.postos = postos if postos is not None else []
        self.transito = transito or {}
        self.lentidao = lentidao or []
        self.partidas, self.buscas = [], []

    configurado = staticmethod(lambda: True)
    traco_desenhavel = staticmethod(maps_client.traco_desenhavel)
    link_rota = staticmethod(maps_client.link_rota)
    link_waze = staticmethod(maps_client.link_waze)
    nome_do_trecho = staticmethod(lambda lat, lon: "BR-000, Cidade Teste")

    def trajeto(self, pontos, partida=None):
        self.partidas.append(partida)
        hora = partida.hour if partida else None
        return {
            "lugares": [{"pedido": pontos[0], "endereco": pontos[0]},
                        {"pedido": pontos[1], "nome": "Destino Teste", "endereco": "Destino Teste - XX"}],
            "_place_ids": [None, "id-destino"],
            "_desenho": (self.caminho, [0, len(self.caminho) - 1], []),
            "_waze": "https://waze.com/ul?ll=-21.00000,-48.90000&navigate=yes",
            "distancia_total_km": self.km,
            "duracao_total_minutos": self.duracao + self.transito.get(hora, 0),
            "transito_total_min": self.transito.get(hora, 0),
            "lentidao": list(self.lentidao),
        }

    def postos_ao_longo(self, trecho):
        self.buscas.append(trecho)
        return [dict(p) for p in self.postos]


class ClimaFalso:
    """Chuva do km 100 ao 200 (em km geometricos do caminho) so quando sai das 8h em diante."""

    def tempo_na_rota(self, pontos, duracao, partida=None, nomear=None):
        if partida.hour < 8:
            trechos = [{"tipo": "ok", "de_km": 0, "ate_km": 667, "hora_ini": "08:00", "hora_fim": "16:00"}]
        else:
            trechos = [{"tipo": "ok", "de_km": 0, "ate_km": 100, "hora_ini": "09:00", "hora_fim": "10:00"},
                       {"tipo": "chuva", "de_km": 100, "ate_km": 200, "hora_ini": "10:30", "hora_fim": "12:00",
                        "chuva_pct": 80, "nome": "BR-000, Cidade Teste", "serra": False},
                       {"tipo": "ok", "de_km": 200, "ate_km": 667, "hora_ini": "12:00", "hora_fim": "17:00"}]
        return {"total_km": 667, "saida": partida.strftime("%H:%M"), "trechos": trechos, "resumo": "x"}


def _posto(nome, km, periodos, via_s=None, fora_km=0.05):
    lat, lng = CAMINHO[min(len(CAMINHO) - 1, round(km / 5.56))]
    return {"place_id": f"id-{nome}", "nome": nome, "endereco": "Rodovia BR-000, km 1" if "Rodovia" in nome else "Rua X",
            "lat": round(lat, 5), "lng": round(lng + fora_km / 99.0, 5), "periodos": periodos, "via_s": via_s}


class _Banco(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()


class SolEGeometriaTest(unittest.TestCase):
    def test_por_do_sol_brusque_novembro(self):
        nascer, por = vp.sol(-27.1, -48.9, date(2026, 11, 6))
        self.assertTrue(datetime(2026, 11, 6, 5, 0) <= nascer <= datetime(2026, 11, 6, 5, 45), nascer)
        self.assertTrue(datetime(2026, 11, 6, 18, 35) <= por <= datetime(2026, 11, 6, 19, 15), por)

    def test_reduzir_um_ponto_a_cada_2_a_5_km_com_o_fim(self):
        acum = vp._acumulado(CAMINHO)
        r = vp.reduzir(CAMINHO, acum, acum[-1])
        self.assertEqual(r[0][2], 0)
        self.assertAlmostEqual(r[-1][2], acum[-1], delta=0.2)
        passos = [b[2] - a[2] for a, b in zip(r, r[1:])]
        self.assertTrue(all(p <= 6 for p in passos))
        self.assertTrue(all(len(p) == 3 for p in r))

    def test_janelas_de_parada(self):
        # 48 L * 13 km/l - 60 de reserva = 564 km: 667 km precisa de 1 parada antes do km 564
        j = vp.janelas_de_parada(667, 48, 48, 13, 60, curta=False)
        self.assertEqual(len(j), 1)
        self.assertEqual(j[0], (564 - vp.JANELA_KM, 564))
        self.assertEqual(vp.janelas_de_parada(400, 48, 48, 13, 60, curta=False), [])
        # 1.012 km com meio tanque: 2 paradas
        self.assertEqual(len(vp.janelas_de_parada(1012, 24, 48, 13, 60, curta=False)), 2)
        # curta: ida e volta (400 km) nao cabe em 1/4 de tanque -> parada no caminho, janela no trecho inteiro
        self.assertEqual(vp.janelas_de_parada(200, 12, 48, 13, 60, curta=True), [(2.0, 96.0)])
        self.assertEqual(vp.janelas_de_parada(200, 48, 48, 13, 60, curta=True), [])

    def test_aberto_em(self):
        sab = datetime(2026, 11, 7, 23, 30)  # sabado
        self.assertEqual(maps_client.aberto_em(H24, sab), {"aberto": True, "24h": True, "ate": None})
        self.assertFalse(maps_client.aberto_em(_horario(6, 22), sab)["aberto"])
        self.assertEqual(maps_client.aberto_em(_horario(6, 22), sab.replace(hour=10))["ate"], "22:00")
        # passa da meia-noite: sabado 18h -> domingo 2h
        noite = [{"open": {"day": 6, "hour": 18, "minute": 0}, "close": {"day": 0, "hour": 2, "minute": 0}}]
        self.assertTrue(maps_client.aberto_em(noite, sab)["aberto"])
        self.assertTrue(maps_client.aberto_em(noite, datetime(2026, 11, 8, 1, 0))["aberto"])
        # 7 dias de 00:00 a 23:59 tambem e 24 h
        quase = [{"open": {"day": d, "hour": 0, "minute": 0}, "close": {"day": d, "hour": 23, "minute": 59}} for d in range(7)]
        self.assertTrue(maps_client.aberto_em(quase, sab)["24h"])
        self.assertIsNone(maps_client.aberto_em(None, sab))
        self.assertIsNone(maps_client.aberto_em([{"open": "x"}], sab))

    def test_codificar_polyline_volta_igual(self):
        cod = maps_client.codificar_polyline(CURTO[:10])
        self.assertEqual([tuple(round(c, 5) for c in p) for p in maps_client.decodificar_polyline(cod)],
                         [tuple(round(c, 5) for c in p) for p in CURTO[:10]])

    def test_traco_com_km_tem_um_km_por_ponto(self):
        acum = vp._acumulado(CAMINHO)
        t = maps_client.traco_desenhavel(CAMINHO, [0, 120], km=acum)
        self.assertEqual(len(t["km"]), len(t["pontos"]))
        self.assertEqual(t["km"][0], 0)
        self.assertNotIn("km", maps_client.traco_desenhavel(CAMINHO, [0, 120]))


class PlanejarTest(_Banco):
    def _planejar(self, maps, pedida=SEXTA.replace(hour=6), agora=SEXTA.replace(hour=3), **kw):
        return vp.planejar(self.conn, "Rua Exemplo", "Destino", pedida, agora, maps=maps, clima=ClimaFalso(), **kw)

    def test_parada_no_posto_24h_de_rodovia_aberto_e_tres_saidas(self):
        maps = MapsFalso(postos=[
            _posto("Posto Rodovia 24h", 500, H24, via_s=4000),
            _posto("Posto Centro", 540, _horario(7, 19), via_s=4010),
            _posto("Posto Longe", 520, H24, via_s=4500),  # +8 min fora da rota: fora
            _posto("Posto Sem Horario", 530, None, via_s=4000),  # sem horario no Google: nunca
        ])
        p = self._planejar(maps)
        self.assertEqual([s["hora"] for s in p["saidas"]], ["05:00", "06:00", "08:00"])  # longa: -1 h / +2 h
        self.assertEqual(p["escolhida"], 1)
        s = p["saidas"][1]
        self.assertEqual(len(s["postos"]), 1)
        posto = s["postos"][0]
        self.assertEqual(posto["nome"], "Posto Rodovia 24h")
        self.assertTrue(posto["h24"])
        self.assertTrue(434 <= posto["km"] <= 564)
        # chegada = saida + 480 min + 15 parado
        self.assertEqual(s["chegada_em"], (SEXTA.replace(hour=6) + timedelta(minutes=495)).isoformat(timespec="minutes"))
        self.assertEqual(s["chega"], "14:15")
        self.assertEqual(s["litros"], round(667 / 13))
        self.assertIsNone(s["custo"])  # sem abastecimento com preco: nao inventa custo
        self.assertTrue(p["tanque"]["assumido"])  # nada registrado: contou cheio e diz isso
        self.assertIn("contei cheio", s["eventos"][0]["sub"])
        # uma busca de posto so (por parada), reaproveitada pelas 3 saidas
        self.assertEqual(len(maps.buscas), 1)
        # Maps com o posto no meio, Waze ate o posto
        self.assertIn("waypoints=", s["maps_url"])
        self.assertTrue(s["waze_url"].startswith("https://waze.com/ul?ll="))
        self.assertEqual(s["waze_para"], "Posto Rodovia 24h")
        # linha do tempo em ordem: sai, abastece, chega
        tipos = [e["tipo"] for e in s["eventos"]]
        self.assertEqual(tipos[0], "")
        self.assertIn("posto", tipos)
        self.assertEqual(tipos[-1], "fim")
        # pedida no futuro: o Google recebeu a hora real de saida
        self.assertIn(SEXTA.replace(hour=6), maps.partidas)

    def test_frase_do_melhor_horario_pela_chuva_e_noite(self):
        # 06:00 sem chuva; 05:00 sem chuva mas sai de noite; 08:00 pega a chuva do km 100-200
        p = self._planejar(MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)]))
        oito = p["saidas"][2]
        self.assertTrue(oito["chuva"])
        self.assertEqual(oito["chuva"][0]["tipo"], "chuva")
        self.assertIn("inicio_em", oito["chuva"][0])
        self.assertIn("chuva", oito["dica"])
        cinco = p["saidas"][0]
        self.assertTrue(cinco["noite"])  # antes do sol nascer
        self.assertEqual(cinco["noite"][0]["de_km"], 0)
        self.assertEqual(p["melhor"], 1)
        self.assertIn("melhor", p["frase_melhor"])

    def test_noite_no_fim_vira_aviso_e_evento_escurece(self):
        maps = MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)])
        p = self._planejar(maps, pedida=SEXTA.replace(hour=13), agora=SEXTA.replace(hour=8))
        s = p["saidas"][p["escolhida"]]
        self.assertTrue(s["noite"])
        self.assertGreaterEqual(s["noite"][-1]["ate_km"], 660)
        self.assertIn("km de noite", p["aviso_noite"])
        self.assertTrue(any(e["titulo"] == "Escurece" for e in s["eventos"]))

    def test_nenhum_posto_aberto_vira_parada_sem_nome(self):
        p = self._planejar(MapsFalso(postos=[_posto("Posto Fecha Cedo", 500, _horario(6, 7), via_s=4000)]))
        s = p["saidas"][1]
        self.assertIsNone(s["postos"][0]["nome"])
        self.assertTrue(any(e["tipo"] == "alerta" and "Abastece até" in e["titulo"] for e in s["eventos"]))
        self.assertNotIn("waypoints=", s["maps_url"])

    def test_curta_com_tanque_baixo_para_no_caminho_e_cheio_nao_para(self):
        perto = {**_posto("Posto Perto", 40, _horario(6, 23), via_s=600), "lat": CURTO[20][0], "lng": -48.8995}
        maps = MapsFalso(caminho=CURTO, km=200, duracao=150, postos=[perto])
        p = self._planejar(maps, pedida=None, agora=SEXTA.replace(hour=14), tanque="1/4")
        self.assertTrue(p["curta"])
        self.assertEqual([s["hora"] for s in p["saidas"]], ["14:00", "15:00", "16:00"])  # agora: so pra frente
        self.assertEqual(p["saidas"][0]["postos"][0]["nome"], "Posto Perto")
        cheio = self._planejar(MapsFalso(caminho=CURTO, km=200, duracao=150, postos=[perto]), pedida=None,
                               agora=SEXTA.replace(hour=14), tanque="cheio")
        self.assertEqual(cheio["saidas"][0]["postos"], [])

    def test_vizinha_que_falha_fica_de_fora_e_hora_passada_e_erro(self):
        maps = MapsFalso()
        original = maps.trajeto

        def falha_nas_vizinhas(pontos, partida=None):
            if partida and partida.hour != 6:
                raise maps_client.CotaEsgotada("acabou")
            return original(pontos, partida)

        maps.trajeto = falha_nas_vizinhas
        p = self._planejar(maps)
        self.assertEqual([s["hora"] for s in p["saidas"]], ["06:00"])
        self.assertEqual(p["frase_melhor"], "")
        self.assertIn("erro", self._planejar(MapsFalso(), pedida=SEXTA.replace(hour=4), agora=SEXTA.replace(hour=6)))

    def test_custo_com_o_preco_do_ultimo_abastecimento(self):
        combustivel.registrar(self.conn, SEXTA - timedelta(days=2), litros=40, valor=240, cheio=True)
        p = self._planejar(MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)]))
        self.assertEqual(p["preco_litro"], 6.0)
        self.assertEqual(p["saidas"][1]["custo"], round(667 / 13 * 6))
        self.assertFalse(p["tanque"]["assumido"])


class ContratoTest(_Banco):
    def _salvo(self):
        maps = MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)])
        plano = vp.planejar(self.conn, "Rua Exemplo", "Destino", SEXTA.replace(hour=13), SEXTA.replace(hour=8),
                            maps=maps, clima=ClimaFalso())
        return vp.salvar(self.conn, plano), plano

    def test_plano_ativo_tem_exatamente_o_contrato_e_a_janela(self):
        id_, plano = self._salvo()
        s = plano["saidas"][plano["escolhida"]]
        saida, chegada = datetime.fromisoformat(s["saida_em"]), datetime.fromisoformat(s["chegada_em"])
        self.assertIsNone(vp.plano_ativo(self.conn, saida - timedelta(hours=2, minutes=1)))
        self.assertIsNone(vp.plano_ativo(self.conn, chegada + timedelta(hours=2, minutes=1)))
        a = vp.plano_ativo(self.conn, saida - timedelta(hours=1))
        self.assertEqual(set(a), {"id", "destino", "saida_em", "chegada_em", "total_km", "traco", "pontos_km", "postos", "chuva"})
        self.assertEqual(a["id"], id_)
        self.assertEqual(a["saida_em"], s["saida_em"])
        self.assertEqual(a["total_km"], 667)
        self.assertEqual(set(a["traco"]) >= {"w", "h", "pontos", "paradas", "lentos"}, True)
        self.assertTrue(all(len(p) == 3 for p in a["pontos_km"]))
        self.assertEqual(set(a["postos"][0]), {"km", "nome", "lat", "lng", "passa_em"})
        for c in a["chuva"]:
            self.assertEqual(set(c), {"de_km", "ate_km", "tipo", "inicio_em"})
        # fuso no agora tambem funciona
        from zoneinfo import ZoneInfo
        self.assertIsNotNone(vp.plano_ativo(self.conn, (saida - timedelta(hours=1)).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))))
        self.assertTrue(vp.encerrar(self.conn, id_))
        self.assertFalse(vp.encerrar(self.conn, id_))
        self.assertIsNone(vp.plano_ativo(self.conn, saida))

    def test_escolher_saida_muda_a_janela_e_planejar_de_novo_encerra_a_antiga(self):
        id_, plano = self._salvo()
        r = vp.escolher_saida(self.conn, id_, 2)
        self.assertEqual(r["saida_em"], plano["saidas"][2]["saida_em"])
        self.assertEqual(vp.plano_ativo(self.conn, datetime.fromisoformat(r["saida_em"]))["saida_em"], r["saida_em"])
        self.assertIsNone(vp.escolher_saida(self.conn, id_, 9))
        self.assertIsNone(vp.escolher_saida(self.conn, id_, True))
        novo, _ = self._salvo()
        linha = self.conn.execute("SELECT encerrada_em FROM viagens_planejadas WHERE id = ?", (id_,)).fetchone()
        self.assertIsNotNone(linha["encerrada_em"])
        self.assertEqual(vp.plano_ativo(self.conn, datetime.fromisoformat(r["saida_em"]))["id"], novo)

    def test_card_viagem_e_modo_visitante(self):
        combustivel.registrar(self.conn, SEXTA - timedelta(days=2), litros=40, valor=240, cheio=True)
        id_, _ = self._salvo()
        c = cards.cards_dos_efeitos(self.conn, [{"entidade": "viagem_planejada", "id": id_}])[0]
        self.assertEqual(c["type"], "viagem")
        self.assertIn("viagem", cards.TIPOS_CARD)
        self.assertEqual(len(c["data"]["custos"]), 3)
        self.assertTrue(all("custo" not in s for s in c["data"]["saidas"]))
        self.assertTrue(all("place_id" not in p for s in c["data"]["saidas"] for p in s["postos"]))
        self.assertEqual(c["actions"][0]["rotulo"], "Abrir no Maps")
        self.assertTrue(c["actions"][1]["url"].startswith("https://waze.com/ul?"))
        oculto = cards.mascarar_cards([c])[0]["data"]
        self.assertNotIn("custos", oculto)
        self.assertNotIn("preco_litro", oculto)


class CombustivelTest(_Banco):
    def test_consumo_real_de_cheio_a_cheio_com_hodometro(self):
        self.assertIsNone(combustivel.consumo_real(self.conn))
        self.assertEqual(combustivel.consumo(self.conn)["km_l"], 13.0)
        self.assertEqual(combustivel.consumo(self.conn, "cidade")["km_l"], 10.0)
        combustivel.registrar(self.conn, datetime(2026, 10, 1, 9), cheio=True, litros=40, hodometro_km=10000)
        combustivel.registrar(self.conn, datetime(2026, 10, 8, 9), litros=10)  # parcial no meio
        combustivel.registrar(self.conn, datetime(2026, 10, 15, 9), cheio=True, litros=30, hodometro_km=10440)
        real = combustivel.consumo_real(self.conn)
        self.assertEqual(real, {"km_l": 11.0, "tanques": 1, "km": 440})  # 440 km / (10 + 30) L
        self.assertEqual(combustivel.consumo(self.conn)["fonte"], "real")
        self.assertEqual(combustivel.media_km_dia(self.conn), round(440 / 14, 1))

    def test_hodometro_errado_nao_vira_consumo(self):
        combustivel.registrar(self.conn, datetime(2026, 10, 1, 9), cheio=True, litros=40, hodometro_km=10000)
        combustivel.registrar(self.conn, datetime(2026, 10, 15, 9), cheio=True, litros=30, hodometro_km=19000)
        self.assertIsNone(combustivel.consumo_real(self.conn))

    def test_estimativa_do_tanque_conta_viagens_e_parciais(self):
        self.assertIsNone(combustivel.estimativa_tanque(self.conn, SEXTA))
        combustivel.registrar(self.conn, SEXTA - timedelta(hours=10), cheio=True, litros=45)
        e = combustivel.estimativa_tanque(self.conn, SEXTA)
        self.assertTrue(e["estimativa"])
        self.assertEqual(e["litros"], 49.0)  # tanque de 49 L (migracao 202611061700)
        self.assertEqual(e["margem_l"], 4.9)
        self.assertFalse(e["tanque_conferido"])
        # viagem planejada de 260 km ja feita depois do tanque cheio: 260 / 13 = 20 L
        plano = {"saidas": [{"saida_em": (SEXTA - timedelta(hours=8)).isoformat(), "chegada_em": (SEXTA - timedelta(hours=5)).isoformat()}],
                 "escolhida": 0, "destino": "X", "total_km": 260}
        vp.salvar(self.conn, plano)
        e = combustivel.estimativa_tanque(self.conn, SEXTA)
        self.assertEqual(e["litros"], 29.0)
        self.assertEqual(e["km_desde"], 260)
        combustivel.registrar(self.conn, SEXTA - timedelta(hours=1), litros=10)
        self.assertEqual(combustivel.estimativa_tanque(self.conn, SEXTA)["litros"], 39.0)

    def test_validacao_e_tanque_do_texto(self):
        self.assertIn("erro", combustivel.registrar(self.conn, SEXTA, litros=500))
        self.assertIn("erro", combustivel.registrar(self.conn, SEXTA, valor=-3))
        self.assertIn("erro", combustivel.registrar(self.conn, SEXTA, litros="abc"))
        self.assertIn("erro", combustivel.registrar(self.conn, SEXTA))  # nada dito
        self.assertEqual(combustivel.litros_do_texto("meio", self.conn), 24.5)
        self.assertEqual(combustivel.litros_do_texto("3/4", self.conn), 36.8)
        self.assertEqual(combustivel.litros_do_texto("0.25", self.conn), 12.2)
        self.assertEqual(combustivel.litros_do_texto("reserva", self.conn), 6.0)  # 60 km / 10 km/l
        self.assertIsNone(combustivel.litros_do_texto("muito", self.conn))
        self.assertIsNone(combustivel.litros_do_texto(3, self.conn))

    def test_executar_card_e_desfazer(self):
        r = combustivel.executar(self.conn, {"litros": 30, "valor": 180, "lugar": "Posto Teste"}, SEXTA)
        self.assertTrue(r["ok"])
        self.assertEqual(r["_efeito"]["entidade"], "abastecimento")
        self.assertIn("erro", combustivel.executar(self.conn, {"cheio": True, "data": "2026-12-25"}, SEXTA))
        self.assertIn("erro", combustivel.executar(self.conn, {"cheio": True, "data": "ontem"}, SEXTA))
        criados = []

        def token(itens):
            criados.extend(itens)
            return db.criar_acao_desfazer(self.conn, itens)

        c = cards.cards_dos_efeitos(self.conn, [r["_efeito"]], criar_token=token)[0]
        self.assertEqual(c["type"], "abastecimento")
        self.assertEqual(c["data"]["preco_litro"], 6.0)
        self.assertIsNone(c["data"]["tanque"])  # sem tanque cheio registrado: nao inventa quanto tem
        self.assertEqual(c["actions"][0]["tipo"], "desfazer")
        oculto = cards.mascarar_cards([c])[0]
        self.assertNotIn("valor", oculto["data"])
        self.assertNotIn("preco_litro", oculto["data"])
        self.assertEqual(oculto["actions"], [])
        app._desfazer_itens(self.conn, criados)
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM abastecimentos").fetchone()[0], 0)


class ExecutarTest(_Banco):
    def test_executar_resolve_casa_salva_e_devolve_o_essencial(self):
        maps = MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)])
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Exemplo, 1"}):
            r = vp.executar(self.conn, {"destino": "Destino", "saida": "2026-11-06 13:00"}, agora=SEXTA,
                            maps=maps, clima=ClimaFalso())
        self.assertEqual(r["destino"], "Destino Teste")
        self.assertEqual(r["paradas_abastecer"][0]["posto"], "Posto Rodovia 24h")
        self.assertEqual(r["saida"], "13:00")
        self.assertIn("ESTIMATIVA", r["obs"])
        self.assertEqual(r["_efeito"]["entidade"], "viagem_planejada")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM viagens_planejadas").fetchone()[0], 1)
        self.assertIn("erro", vp.executar(self.conn, {}, agora=SEXTA, maps=maps, clima=ClimaFalso()))
        self.assertIn("erro", vp.executar(self.conn, {"destino": "X", "saida": "amanha cedo"}, agora=SEXTA, maps=maps,
                                          clima=ClimaFalso()))
        sem = MapsFalso()
        sem.configurado = lambda: False
        self.assertIn("GOOGLE_MAPS_API_KEY", vp.executar(self.conn, {"destino": "X"}, agora=SEXTA, maps=sem)["erro"])

    def test_rede_fora_vira_erro_sem_quebrar(self):
        maps = MapsFalso()
        maps.trajeto = MagicMock(side_effect=ValueError("sem rota"))
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Exemplo, 1"}):
            r = vp.executar(self.conn, {"destino": "Destino"}, agora=SEXTA, maps=maps, clima=ClimaFalso())
        self.assertEqual(r, {"erro": "nao consegui calcular a rota agora"})


class CotaTest(_Banco):
    def _chamadas(self, nivel):
        linha = self.conn.execute("SELECT chamadas FROM uso_maps WHERE mes = ? AND nivel = ?",
                                  (datetime.now().strftime("%Y-%m"), nivel)).fetchone()
        return linha["chamadas"] if linha else 0

    def _esgotar(self, nivel):
        self.conn.execute("INSERT OR REPLACE INTO uso_maps (mes, nivel, chamadas) VALUES (?, ?, ?)",
                          (datetime.now().strftime("%Y-%m"), nivel, maps_client.COTA_MES[nivel]))
        self.conn.commit()

    def test_cotas_novas_somam_menos_que_a_cota_gratis(self):
        self.assertLess(maps_client.COTA_MES["posto_rota"] + maps_client.COTA_MES["horario_lugar"], 1000)
        self.assertLess(maps_client.COTA_MES["lugar_busca"], 5000)
        self.assertLess(maps_client.COTA_MES["posto_perto"], 5000)

    def test_buscas_que_escapavam_agora_contam_e_travam(self):
        resp = MagicMock()
        resp.json.return_value = {"places": [], "results": [{"geometry": {"location": {"lat": 1.0, "lng": 2.0}}}]}
        resp.raise_for_status.return_value = None
        maps_client._cache_lugares.clear()
        maps_client._cache_horarios.clear()
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-fake"}), \
                patch("maps_client.requests.post", return_value=resp) as post, \
                patch("maps_client.requests.get", return_value=resp):
            maps_client.resolver_lugar("Lugar Teste Um")
            maps_client.horario_funcionamento("Lugar Teste Dois", date(2026, 11, 6))
            maps_client.geocodificar("Rua Teste, 1")
            self.assertEqual((self._chamadas("lugar_busca"), self._chamadas("horario_lugar"), self._chamadas("lugar_nome")),
                             (1, 1, 1))
            self._esgotar("lugar_busca")
            self._esgotar("horario_lugar")
            self._esgotar("lugar_nome")
            self._esgotar("posto_rota")
            self._esgotar("posto_perto")
            post.reset_mock()
            self.assertIsNone(maps_client.resolver_lugar("Lugar Teste Tres"))
            self.assertIsNone(maps_client.horario_funcionamento("Lugar Teste Quatro", date(2026, 11, 6)))
            with self.assertRaises(maps_client.CotaEsgotada):
                maps_client.geocodificar("Rua Teste, 2")
            with self.assertRaises(maps_client.CotaEsgotada):
                maps_client.postos_ao_longo(CURTO[:5])
            post.assert_not_called()

    def test_postos_ao_longo_pede_a_rota_e_le_o_desvio(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "places": [
                {"id": "a", "displayName": {"text": "Posto A"}, "formattedAddress": "BR-000",
                 "location": {"latitude": -27.0, "longitude": -48.9}, "regularOpeningHours": {"periods": H24}},
                {"id": "b", "displayName": {"text": "Posto B"}, "location": {"latitude": "x"}},  # quebrado: fora
            ],
            "routingSummaries": [{"legs": [{"duration": "100s"}, {"duration": "250s"}]}, {}],
        }
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-fake"}), \
                patch("maps_client.requests.post", return_value=resp) as post:
            r = maps_client.postos_ao_longo(CURTO[:5])
        corpo = post.call_args.kwargs["json"]
        self.assertIn("encodedPolyline", corpo["searchAlongRouteParameters"]["polyline"])
        self.assertEqual(corpo["includedType"], "gas_station")
        self.assertIn("places.regularOpeningHours", post.call_args.kwargs["headers"]["X-Goog-FieldMask"])
        self.assertIn("routingSummaries", post.call_args.kwargs["headers"]["X-Goog-FieldMask"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["via_s"], 350)
        self.assertEqual(r[0]["periodos"], H24)
        self.assertEqual(self._chamadas("posto_rota"), 1)


class TransitoPrecisoTest(_Banco):
    def test_trajeto_passa_a_hora_de_saida_pra_cada_perna(self):
        partida = datetime.now() + timedelta(days=1)
        chamadas = []

        def tempo(origem, destino, **kw):
            chamadas.append(kw.get("partida"))
            return {"distancia_km": 10.0, "duracao_minutos": 30, "transito_min": 5, "lentidao": [],
                    "destino_ll": None, "_polyline": None}

        with patch("maps_client.resolver_lugar", return_value=None), patch("maps_client.tempo_de_viagem", side_effect=tempo):
            maps_client.trajeto(["A", "B", "C"], partida=partida)
            maps_client.trajeto(["A", "B"])
        self.assertEqual(chamadas[:2], [partida, partida + timedelta(minutes=30)])
        self.assertEqual(chamadas[2], None)

    def test_horario_de_saida_refaz_quando_a_saida_cai_longe_do_chute(self):
        chegar = datetime.now() + timedelta(days=1)
        partidas = []

        def tempo(origem, destino, modo="DRIVE", **kw):
            partidas.append(kw.get("partida"))
            return {"duracao_minutos": 120, "distancia_km": 150, "transito_min": 10, "lentidao": [], "destino_ll": None}

        with patch("maps_client.tempo_de_viagem", side_effect=tempo):
            r = maps_client.horario_de_saida("A", "B", chegar, margem_minutos=10)
        self.assertEqual(len(partidas), 2)
        self.assertEqual(partidas[1], chegar - timedelta(minutes=130))
        self.assertEqual(r["sair_ate"], (chegar - timedelta(minutes=130)).isoformat())
        partidas.clear()

        def curto(origem, destino, modo="DRIVE", **kw):
            partidas.append(kw.get("partida"))
            return {"duracao_minutos": 35, "distancia_km": 20, "transito_min": 2, "lentidao": [], "destino_ll": None}

        with patch("maps_client.tempo_de_viagem", side_effect=curto):
            maps_client.horario_de_saida("A", "B", chegar, margem_minutos=10)
        self.assertEqual(len(partidas), 1)  # chute bom: nada de chamada a mais

    def test_card_rota_leva_a_hora_do_transito_previsto(self):
        ef = {"url": "https://www.google.com/maps/dir/?api=1", "paradas": [{"nome": "A"}, {"nome": "B"}],
              "transito_min": 12, "transito_saida": "19:00"}
        self.assertEqual(cards.card_rota(ef)["data"]["transito_saida"], "19:00")
        self.assertIsNone(cards.card_rota({**ef, "transito_saida": "<b>"})["data"]["transito_saida"])


class RotaEToolsTest(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)

    def test_rota_escolher_saida(self):
        conn = db.get_db()
        maps = MapsFalso(postos=[_posto("Posto Rodovia 24h", 500, H24, via_s=4000)])
        plano = vp.planejar(conn, "Rua Exemplo", "Destino", SEXTA.replace(hour=13), SEXTA.replace(hour=8),
                            maps=maps, clima=ClimaFalso())
        id_ = vp.salvar(conn, plano)
        conn.close()
        res = self.client.post(f"/api/viagens-planejadas/{id_}/saida", json={"indice": 0})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["saida_em"], plano["saidas"][0]["saida_em"])
        self.assertEqual(self.client.post(f"/api/viagens-planejadas/{id_}/saida", json={"indice": "0"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/viagens-planejadas/{id_}/saida", json={"indice": 7}).status_code, 404)
        self.assertEqual(self.client.post("/api/viagens-planejadas/999/saida", json={"indice": 0}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/viagens-planejadas/{id_}/encerrar").status_code, 200)
        self.assertEqual(self.client.post(f"/api/viagens-planejadas/{id_}/encerrar").status_code, 404)

    def test_tools_registradas_no_chat(self):
        from ia.funcoes.chat import CHAT_SYSTEM_PROMPT, CHAT_TOOLS

        nomes = {t["name"] for t in CHAT_TOOLS}
        self.assertTrue({"planejar_viagem", "registrar_abastecimento"} <= nomes)
        self.assertIn("planejar_viagem", CHAT_SYSTEM_PROMPT)
        capturado = {}

        def fake_chat(mensagens, contexto, memorias, executores):
            capturado["r"] = executores["registrar_abastecimento"]({"cheio": True, "litros": 41.5})
            capturado["v"] = executores["planejar_viagem"]({})
            return "ok", [], {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "enchi o tanque"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(capturado["r"]["ok"])
        self.assertEqual(capturado["v"], {"erro": "preciso do destino"})


if __name__ == "__main__":
    unittest.main()
