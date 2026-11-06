"""GPS mais esperto do iPhone (leva 06/11 "painel mais esperto", frente 3): cercas, viagem acompanhada
(POST /api/localizacao/posicao) e o kind `viagem` do /api/ao-vivo. Banco temporario, relogio injetado,
`viagem_planejada` dublado (contrato da outra frente), sem rede. Coordenadas inventadas."""

import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import onde_estou  # noqa: E402
import tempo  # noqa: E402
import viagem_acompanhada as va  # noqa: E402
from rotas import ao_vivo, localizacao_viagem  # noqa: E402

try:  # o modulo de verdade da outra frente (contrato plano_ativo/encerrar), se ja existir
    import viagem_planejada as VP_REAL  # noqa: E402
except ImportError:
    VP_REAL = None

TOKEN = "token-de-teste-gps"
CAB = {"Authorization": f"Bearer {TOKEN}"}
DIA = "2026-11-07"
GRAU_KM = 110.57  # o mesmo fator de viagem_acompanhada.projetar_km (rota num meridiano: projecao exata)
LNG = -50.0


def _lat(km: float) -> float:
    return -20.0 + km / GRAU_KM


def _h(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{DIA}T{hhmm}:00")


def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone().replace(tzinfo=None)


def plano(**extra) -> dict:
    """300 km a 60 km/h: sai 08:00, posto no km 150 as 10:30, chega 13:00; chuva do km 200 ao 230."""
    p = {
        "id": 7,
        "destino": "Cidade Teste, XX",
        "saida_em": f"{DIA}T08:00:00",
        "chegada_em": f"{DIA}T13:00:00",
        "total_km": 300,
        "traco": "",
        "pontos_km": [[_lat(k), LNG, k] for k in range(0, 301, 50)],
        "postos": [{"km": 150, "nome": "Posto Teste", "lat": _lat(150), "lng": LNG, "passa_em": f"{DIA}T10:30:00"}],
        "chuva": [{"de_km": 200, "ate_km": 230, "tipo": "chuva", "inicio_em": None}],
    }
    p.update(extra)
    return p


class Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        tempo.limpar_cache()
        ao_vivo._CACHE_CLIMA.clear()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": TOKEN})
        env.start()
        self.addCleanup(env.stop)
        self.client = app.app.test_client()
        # viagem_planejada dublado: `self.plano` e o que plano_ativo devolve; encerrar fica anotado
        self.plano = None
        self.encerradas = []
        stub = types.ModuleType("viagem_planejada")
        stub.plano_ativo = lambda conn, agora: self.plano
        stub.encerrar = lambda conn, vid: self.encerradas.append(vid)
        mods = patch.dict(sys.modules, {"viagem_planejada": stub})
        mods.start()
        self.addCleanup(mods.stop)

    def ao_vivo(self, agora):
        with patch.object(ao_vivo, "_agora", return_value=agora), patch.object(ao_vivo, "_rede", return_value=False):
            r = self.client.get("/api/ao-vivo", headers=CAB)
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def posicao(self, km, agora, em=None, headers=CAB, **extra):
        corpo = {"lat": _lat(km), "lng": LNG, "velocidade": 25.0, "precisao": 12.0,
                 "em": (em or agora).isoformat(timespec="seconds")}
        corpo.update(extra)
        with patch.object(localizacao_viagem, "_agora", return_value=agora):
            return self.client.post("/api/localizacao/posicao", json=corpo, headers=headers)

    def guardadas(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM viagem_posicoes ORDER BY id")]

    def tarefa(self, titulo, hora, estilo=None, local=None):
        c = self.conn.execute("INSERT INTO tasks (title, due_date, hora, local, estilo) VALUES (?, ?, ?, ?, ?)",
                              (titulo, DIA, hora, local, estilo))
        self.conn.commit()
        return c.lastrowid


class TokenTest(Base):
    def test_rotas_sem_token_ou_token_errado_sao_401(self):
        for cab in ({}, {"Authorization": "Bearer errado"}, {"Authorization": TOKEN}, {"Authorization": "Bearer "}):
            with self.subTest(cab=cab):
                self.assertEqual(self.client.get("/api/localizacao/cercas", headers=cab).status_code, 401)
                self.assertEqual(self.posicao(10, _h("08:10"), headers=cab).status_code, 401)
        self.assertEqual(self.guardadas(), [])

    def test_token_na_url_nao_vale(self):
        self.assertEqual(self.client.get(f"/api/localizacao/cercas?token={TOKEN}").status_code, 401)
        r = self.client.post(f"/api/localizacao/posicao?token={TOKEN}", json={"lat": -20, "lng": -50})
        self.assertEqual(r.status_code, 401)

    def test_sem_token_configurado_e_401(self):
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": ""}):
            self.assertEqual(self.client.get("/api/localizacao/cercas", headers=CAB).status_code, 401)

    def test_modo_visitante_nao_grava(self):
        self.plano = plano()
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self.posicao(10, _h("08:10")).status_code, 403)
        self.assertEqual(self.guardadas(), [])


class ValidacaoTest(Base):
    def test_corpo_ruim_e_400(self):
        self.plano = plano()
        agora = _h("08:10")
        with patch.object(localizacao_viagem, "_agora", return_value=agora):
            for corpo in (None, [], {"lat": "x", "lng": 1}, {"lat": 0, "lng": 0}, {"lat": 95, "lng": 1},
                          {"lat": float("nan"), "lng": 1}):
                with self.subTest(corpo=corpo):
                    r = self.client.post("/api/localizacao/posicao", json=corpo, headers=CAB)
                    self.assertEqual(r.status_code, 400)
        self.assertEqual(self.posicao(10, agora, em=agora + timedelta(hours=1)).status_code, 400)
        self.assertEqual(self.posicao(10, agora, em=agora - timedelta(hours=3)).status_code, 400)
        self.assertEqual(self.guardadas(), [])

    def test_velocidade_absurda_vira_nula_e_coordenada_arredonda(self):
        self.plano = plano()
        self.assertEqual(self.posicao(10, _h("08:10"), velocidade=900, lat=-19.912345678).status_code, 200)
        g = self.guardadas()[0]
        self.assertIsNone(g["velocidade"])
        self.assertEqual(g["lat"], -19.9123)


class CercasTest(Base):
    def lugares(self, lista):
        return patch.object(onde_estou, "lugares_com_coordenada", return_value=lista)

    def test_ordem_casa_dia_apelidos_sem_coordenada_e_duplicada_fora(self):
        import vida_assistente

        vida_assistente.salvar_apelido(self.conn, "academia", "Rua Inventada, 1")
        vida_assistente.salvar_apelido(self.conn, "mercado", "Rua Inventada, 2")
        self.conn.commit()
        lista = [
            {"apelido": "academia", "endereco": "Rua Inventada, 1", "coord": (-21.0, -51.0)},
            {"apelido": "mercado", "endereco": "Rua Inventada, 2", "coord": None},
            {"apelido": "casa", "endereco": "x", "coord": (-21.1, -51.1)},
            {"apelido": "viva teste", "endereco": "Viva Teste", "coord": (-21.2, -51.2)},
            {"apelido": "rua perto", "endereco": "Rua Inventada, 3", "coord": (-21.2003, -51.2)},  # ~33 m
        ]
        with self.lugares(lista):
            r = self.client.get("/api/localizacao/cercas", headers=CAB)
        self.assertEqual(r.status_code, 200)
        c = r.get_json()["cercas"]
        self.assertEqual([x["nome"] for x in c], ["Casa", "Viva Teste", "Academia"])
        self.assertEqual(c[0]["id"], "casa")
        self.assertEqual(set(c[1]), {"id", "nome", "lat", "lng", "raio_m"})
        self.assertEqual(c[1]["raio_m"], va.RAIO_CERCA_M)
        self.assertNotIn("Rua", " ".join(x["nome"] for x in c))  # endereco nunca vira nome

    def test_no_maximo_20_e_apelido_mais_visitado_primeiro(self):
        import vida_assistente

        lista = []
        for i in range(30):
            vida_assistente.salvar_apelido(self.conn, f"lugar {i:02d}", f"Lugar {i}")
            lista.append({"apelido": f"lugar {i:02d}", "endereco": f"Lugar {i}", "coord": (-21.0 - i * 0.01, -51.0)})
        self.conn.execute("INSERT INTO visitas (lat, lon, chegada, lugar) VALUES (-21.29, -51.0, ?, 'lugar 29')",
                          (f"{DIA}T10:00:00",))
        self.conn.commit()
        with self.lugares(lista):
            c = self.client.get("/api/localizacao/cercas", headers=CAB).get_json()["cercas"]
        self.assertEqual(len(c), va.MAX_CERCAS)
        self.assertEqual(c[0]["nome"], "Lugar 29")

    def test_visita_da_cerca_com_campo_extra_e_aceita(self):
        # o app manda entrou/saiu da cerca pro POST de visita de sempre, com `fonte` e `cerca` a mais
        agora = datetime.now().replace(microsecond=0)
        with patch.object(onde_estou, "REAGIR_EM_THREAD", False), patch.object(onde_estou, "reagir_depois"),                 self.lugares([]):
            r = self.client.post("/api/localizacao/visita", headers=CAB, json={
                "lat": -21.0, "lon": -51.0, "precisao": 150, "chegada": agora.isoformat(), "saida": None,
                "fonte": "cerca", "cerca": "casa"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM visitas").fetchone()[0], 1)

    def test_falha_nos_lugares_vira_lista_vazia(self):
        with patch.object(onde_estou, "lugares_com_coordenada", side_effect=RuntimeError("rede")):
            r = self.client.get("/api/localizacao/cercas", headers=CAB)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["cercas"], [])


class PosicaoTest(Base):
    def test_sem_viagem_nem_compromisso_nao_guarda_e_manda_parar(self):
        self.conn.execute("INSERT INTO viagem_posicoes (chave, lat, lng, em) VALUES ('viagem-1', -20, -50, ?)",
                          (f"{DIA}T07:00:00",))
        self.conn.commit()
        r = self.posicao(10, _h("08:10"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"ok": True, "guardou": False, "acompanhar": False})
        self.assertEqual(self.guardadas(), [])  # e a velha sumiu junto

    def test_sem_modulo_viagem_planejada_e_sem_viagem(self):
        with patch.dict(sys.modules, {"viagem_planejada": None}):
            r = self.posicao(10, _h("08:10"))
            self.assertFalse(r.get_json()["acompanhar"])
            self.assertNotEqual(self.ao_vivo(_h("08:10")).get("kind"), "viagem")
        self.assertEqual(self.guardadas(), [])

    def test_plano_de_outro_dia_ainda_nao_acompanha(self):
        self.plano = plano()
        self.assertFalse(self.posicao(0, _h("07:00")).get_json()["acompanhar"])  # 1 h antes da saida
        self.assertTrue(self.posicao(0, _h("07:40")).get_json()["acompanhar"])  # 20 min antes: ja vale

    def test_viagem_guarda_e_ao_vivo_refaz_chegada_posto_e_chuva(self):
        self.plano = plano()
        r = self.posicao(100, _h("10:00"), em=_h("09:58"))
        self.assertEqual(r.get_json(), {"ok": True, "guardou": True, "acompanhar": True})
        d = self.ao_vivo(_h("10:00"))
        self.assertEqual((d["kind"], d["titulo"], d["icone"], d["cor"]), ("viagem", "Cidade Teste", "car.fill", "#8fd0ff"))
        self.assertTrue(d["acompanhar"])
        v = d["viagem"]
        self.assertEqual((v["falta_km"], v["total_km"]), (200, 300))
        # pelo plano, km 100 era 09:40; passou 09:58: 18 min atrasado -> chega 13:18, posto 10:48
        self.assertEqual(_local(d["passos"][-1]["em"]), _h("13:18"))
        self.assertEqual((v["posto_km"], v["posto_nome"]), (50, "Posto Teste"))
        self.assertEqual(_local(v["posto_em"]), _h("10:48"))
        self.assertEqual((v["chuva"], v["chuva_rotulo"]), ("daqui 1 h 40", "Chuva"))
        # a barra: na hora da posicao esta em 1/3 e enche ate a chegada
        desde = _local(v["barra_desde"])
        frac = (_h("09:58") - desde) / (_h("13:18") - desde)
        self.assertAlmostEqual(frac, 1 / 3, places=2)

    def test_dentro_da_chuva_diz_quanto_falta_dela(self):
        self.plano = plano()
        self.posicao(210, _h("11:30"))
        v = self.ao_vivo(_h("11:31"))["viagem"]
        self.assertEqual(v["chuva"], "chovendo, mais 20 km")
        self.assertIsNone(v["posto_km"])  # o posto ja ficou pra tras

    def test_neblina_tem_rotulo_e_nao_diz_chovendo(self):
        self.plano = plano(chuva=[{"de_km": 200, "ate_km": 230, "tipo": "neblina", "inicio_em": f"{DIA}T11:20"},
                                  {"de_km": 250, "ate_km": 260, "tipo": "chuva_forte", "inicio_em": None}])
        self.posicao(100, _h("09:50"))  # 10 min atrasado: a neblina (11:20 no plano) fica 11:30
        v = self.ao_vivo(_h("09:50"))["viagem"]
        self.assertEqual((v["chuva"], v["chuva_rotulo"]), ("daqui 1 h 40", "Neblina"))
        self.posicao(210, _h("11:30"))
        self.assertEqual(self.ao_vivo(_h("11:30"))["viagem"]["chuva"], "agora, mais 20 km")
        self.posicao(240, _h("12:00"))
        v = self.ao_vivo(_h("12:00"))["viagem"]
        self.assertEqual((v["chuva"], v["chuva_rotulo"]), ("daqui 10 min", "Chuva forte"))

    def test_chuva_passada_some(self):
        self.plano = plano()
        self.posicao(240, _h("12:00"))
        self.assertIsNone(self.ao_vivo(_h("12:01"))["viagem"]["chuva"])

    def test_parado_no_posto_nao_some_e_empurra_a_chegada(self):
        self.plano = plano()
        self.posicao(150, _h("10:30"))
        d = self.ao_vivo(_h("11:00"))  # 30 min sem posicao nova: parou
        self.assertEqual(d["kind"], "viagem")
        self.assertEqual(_local(d["passos"][-1]["em"]), _h("13:30"))

    def test_chegou_perto_do_destino_encerra_e_apaga_o_caminho(self):
        self.plano = plano()
        self.posicao(100, _h("09:40"))
        self.posicao(200, _h("11:20"))
        self.assertEqual(len(self.guardadas()), 2)
        r = self.posicao(299.5, _h("13:00")).get_json()
        self.assertEqual(r, {"ok": True, "guardou": False, "acompanhar": False, "chegou": True})
        self.assertEqual(self.guardadas(), [])
        self.assertEqual(self.encerradas, [7])
        # mesmo se o plano ainda vier ativo (encerrar nao rodou), nao volta a acompanhar nem mostrar
        self.assertFalse(self.posicao(300, _h("13:05")).get_json()["acompanhar"])
        self.assertNotEqual(self.ao_vivo(_h("13:05")).get("kind"), "viagem")
        self.assertEqual(self.guardadas(), [])

    def test_viagem_acabou_no_plano_apaga_as_posicoes_no_proximo_ao_vivo(self):
        self.plano = plano()
        self.posicao(100, _h("09:40"))
        self.assertEqual(len(self.guardadas()), 1)
        self.plano = None  # viagem_planejada.encerrar rodou
        self.assertFalse(self.ao_vivo(_h("09:45"))["ativo"])
        self.assertEqual(self.guardadas(), [])

    def test_outro_plano_apaga_o_caminho_do_anterior(self):
        self.plano = plano()
        self.posicao(100, _h("09:40"))
        self.plano = plano(id=8)
        self.posicao(110, _h("09:50"))
        self.assertEqual({g["chave"] for g in self.guardadas()}, {"viagem-8"})

    def test_trava_de_24_horas(self):
        self.plano = plano()
        self.conn.execute("INSERT INTO viagem_posicoes (chave, lat, lng, em) VALUES ('viagem-7', -20, -50, ?)",
                          ("2026-11-05T09:00:00",))
        self.conn.commit()
        self.posicao(100, _h("09:40"))
        self.assertEqual(len(self.guardadas()), 1)

    def test_apagar_viagem_pra_quem_encerra(self):
        self.plano = plano()
        self.posicao(100, _h("09:40"))
        va.apagar_viagem(self.conn, 7)
        self.assertEqual(self.guardadas(), [])


class AoVivoViagemTest(Base):
    def test_sem_posicao_aparece_na_hora_da_saida_pela_hora(self):
        self.plano = plano()
        d = self.ao_vivo(_h("08:30"))
        self.assertEqual(d["kind"], "viagem")
        self.assertEqual(d["viagem"]["falta_km"], 270)  # 30 min a 60 km/h
        self.assertIsNone(d["viagem"]["posicao_em"])
        self.assertEqual(_local(d["passos"][-1]["em"]), _h("13:00"))
        self.assertEqual(self.ao_vivo(_h("07:50"))["viagem"]["falta_km"], 300)  # 10 min antes: ainda nao saiu
        self.assertNotIn("viagem", self.ao_vivo(_h("09:00")))  # 1 h depois sem posicao: some

    def test_viagem_ganha_de_tarefa(self):
        self.plano = plano()
        self.tarefa("Ligar pro contador", "10:15")
        self.posicao(100, _h("09:40"))
        d = self.ao_vivo(_h("09:45"))
        self.assertEqual(d["kind"], "viagem")
        self.assertEqual(d["proxima_tarefa"]["titulo"], "Ligar pro contador")

    def test_sem_viagem_a_tarefa_continua(self):
        self.tarefa("Ligar pro contador", "10:15")
        d = self.ao_vivo(_h("09:45"))
        self.assertEqual(d["kind"], "tarefa")
        self.assertNotIn("acompanhar", d)  # tarefa sem saida: ninguem dirige pra ela

    def test_plano_sem_pontos_usa_a_hora(self):
        self.plano = plano(pontos_km=[], postos=[], chuva=[])
        self.posicao(100, _h("09:40"))
        d = self.ao_vivo(_h("09:40"))
        self.assertEqual(d["kind"], "viagem")
        self.assertEqual(d["viagem"]["falta_km"], 200)  # sem rota pra projetar: pela hora (09:40 = km 100)
        self.assertIsNone(d["viagem"]["posto_km"])

    def test_plano_quebrado_nao_derruba(self):
        self.plano = plano(saida_em="lixo", pontos_km=[["a", 1]], postos=[None], chuva="x")
        d = self.ao_vivo(_h("09:40"))
        self.assertNotEqual(d.get("kind"), "viagem")


class CompromissoDeSaidaTest(Base):
    def test_date_na_hora_de_sair_acompanha_e_guarda_so_a_ultima(self):
        ref = self.tarefa("Date", "19:00", estilo="date", local="Viva Teste")
        # sem rede: sai 18:45 (15 min de folga)
        self.assertNotIn("acompanhar", self.ao_vivo(_h("17:00")))
        self.assertFalse(self.posicao(1, _h("17:00")).get_json()["acompanhar"])
        d = self.ao_vivo(_h("18:40"))
        self.assertTrue(d["acompanhar"])
        self.assertEqual(d["kind"], "tarefa")
        self.assertTrue(self.posicao(1, _h("18:46")).get_json()["guardou"])
        self.assertTrue(self.posicao(2, _h("18:51")).get_json()["guardou"])
        g = self.guardadas()
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["chave"], f"tarefa-{ref}-{DIA}")
        self.assertEqual(va.ultima_posicao(self.conn, _h("18:52"))["lat"], round(_lat(2), 4))
        # passou do fim do compromisso: o proximo ao vivo apaga
        self.assertFalse(self.ao_vivo(_h("19:30"))["ativo"])
        self.assertEqual(self.guardadas(), [])


@unittest.skipIf(VP_REAL is None, "viagem_planejada ainda nao existe")
class ContratoRealTest(Base):
    """Com o viagem_planejada de verdade: plano gravado em viagens_planejadas, chegada encerra la."""

    def test_plano_real_aparece_e_chegada_encerra(self):
        import json

        p = plano()
        guardado = {"destino": p["destino"], "total_km": 300, "traco": "", "pontos_km": p["pontos_km"], "escolhida": 0,
                    "saidas": [{"saida_em": p["saida_em"], "chegada_em": p["chegada_em"], "postos": p["postos"],
                                "chuva": p["chuva"]}]}
        vid = self.conn.execute(
            "INSERT INTO viagens_planejadas (destino, saida_em, chegada_em, plano_json) VALUES (?, ?, ?, ?)",
            (p["destino"], p["saida_em"], p["chegada_em"], json.dumps(guardado))).lastrowid
        self.conn.commit()
        with patch.dict(sys.modules, {"viagem_planejada": VP_REAL}):
            self.assertTrue(self.posicao(100, _h("09:40")).get_json()["guardou"])
            d = self.ao_vivo(_h("09:41"))
            self.assertEqual((d["kind"], d["viagem"]["falta_km"]), ("viagem", 200))
            self.assertTrue(self.posicao(300, _h("13:00")).get_json()["chegou"])
            fim = self.conn.execute("SELECT encerrada_em FROM viagens_planejadas WHERE id = ?", (vid,)).fetchone()[0]
            self.assertIsNotNone(fim)
            self.assertEqual(self.guardadas(), [])
            self.assertNotEqual(self.ao_vivo(_h("13:01")).get("kind"), "viagem")


class ProjecaoTest(unittest.TestCase):
    def test_projeta_no_trecho_mais_perto(self):
        pontos = [(_lat(k), LNG, float(k)) for k in (0, 50, 100)]
        km, dist = va.projetar_km(pontos, _lat(75), LNG + 0.01)  # ~1 km do lado da rota
        self.assertAlmostEqual(km, 75, delta=0.1)
        self.assertAlmostEqual(dist, 1.05, delta=0.1)
        self.assertIsNone(va.projetar_km([], 0, 0))

    def test_texto_dos_minutos(self):
        self.assertEqual(va._min_texto(25), "daqui 25 min")
        self.assertEqual(va._min_texto(60), "daqui 1 h")
        self.assertEqual(va._min_texto(125), "daqui 2 h 05")
        self.assertEqual(va._min_texto(0.2), "daqui 1 min")


if __name__ == "__main__":
    unittest.main()
