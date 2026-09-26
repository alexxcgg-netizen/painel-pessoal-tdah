"""Fase 6 F3: US-F11 (linha do tempo de planejamento de viagem, regra
pratica) e US-F12 (status de voo por numero, API mockada - NUNCA chama rede
de verdade aqui).

Segue o padrao de tests/test_pin_inicial.py: db.DB_PATH pra um arquivo
temporario + db.garantir_banco_nao_producao() ANTES de importar app."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import vida
import voo_status

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


# ---- US-F11: funcoes puras (vida.py) ---------------------------------------

class MarcosPlanejamentoTestCase(unittest.TestCase):
    def test_nacional_tem_tres_marcos_antes_da_ida(self):
        ida = date(2026, 12, 25)
        marcos = vida.marcos_planejamento_viagem(ida, internacional=False)
        self.assertEqual(len(marcos), 3)
        for m in marcos:
            self.assertLessEqual(date.fromisoformat(m["data"]), ida)
            self.assertIn("titulo", m)
            self.assertIn("dias_antes", m)

    def test_internacional_tem_mais_marcos_e_antecedencia_maior(self):
        ida = date(2026, 12, 25)
        nacional = vida.marcos_planejamento_viagem(ida, internacional=False)
        internacional = vida.marcos_planejamento_viagem(ida, internacional=True)
        self.assertGreater(len(internacional), len(nacional))
        passagem_nac = next(m for m in nacional if m["chave"] == "passagem")
        passagem_int = next(m for m in internacional if m["chave"] == "passagem")
        self.assertGreater(passagem_int["dias_antes"], passagem_nac["dias_antes"])

    def test_marcos_sao_deterministicos_pura_funcao_de_calendario(self):
        ida = date(2027, 3, 10)
        a = vida.marcos_planejamento_viagem(ida, True)
        b = vida.marcos_planejamento_viagem(ida, True)
        self.assertEqual(a, b)

    def test_viagem_como_projeto_detalhada_inclui_marcos_e_aviso(self):
        viagem = {
            "id": 1,
            "destino": "Lisboa",
            "data_ida": "2026-12-25",
            "data_volta": "2027-01-05",
            "criado_em": "2026-09-01",
            "internacional": 1,
        }
        detalhe = vida.viagem_como_projeto_detalhada(viagem, [], date(2026, 9, 23))
        self.assertIsInstance(detalhe["marcos_planejamento"], list)
        self.assertTrue(len(detalhe["marcos_planejamento"]) >= 3)
        aviso = detalhe["aviso_regra_pratica"].lower()
        self.assertIn("regra prática", aviso)
        self.assertIn("não e preço em tempo real", aviso)  # deixa explicito que NAO e preco real

    def test_viagem_sem_data_ida_valida_nao_quebra(self):
        viagem = {"id": 2, "destino": "X", "data_ida": None, "criado_em": "2026-09-01"}
        detalhe = vida.viagem_como_projeto_detalhada(viagem, [], date(2026, 9, 23))
        self.assertIsNone(detalhe["marcos_planejamento"])


# ---- US-F11: rotas HTTP -----------------------------------------------------

class ViagensTimelineHTTPTestCase(unittest.TestCase):
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

    def test_criar_viagem_internacional_persiste_flag(self):
        ida = (date.today() + timedelta(days=200)).isoformat()
        res = self.client.post(
            "/api/viagens", json={"destino": "Tokyo", "data_ida": ida, "internacional": True}
        )
        self.assertEqual(res.status_code, 201)
        viagem_id = res.get_json()["viagem_id"]

        listagem = self.client.get("/api/viagens").get_json()
        v = next(x for x in listagem if x["id"] == viagem_id)
        self.assertEqual(v["internacional"], 1)
        self.assertTrue(len(v["marcos_planejamento"]) >= 5)  # internacional tem mais marcos
        self.assertIn("regra prática", v["aviso_regra_pratica"].lower())

    def test_criar_viagem_nacional_por_padrao(self):
        ida = (date.today() + timedelta(days=40)).isoformat()
        res = self.client.post("/api/viagens", json={"destino": "Sao Paulo", "data_ida": ida})
        self.assertEqual(res.status_code, 201)
        viagem_id = res.get_json()["viagem_id"]
        v = next(x for x in self.client.get("/api/viagens").get_json() if x["id"] == viagem_id)
        self.assertEqual(v["internacional"], 0)
        self.assertEqual(len(v["marcos_planejamento"]), 3)

    def test_timeline_card_devolve_projeto_viagem_com_marcos(self):
        ida = (date.today() + timedelta(days=100)).isoformat()
        viagem_id = self.client.post(
            "/api/viagens", json={"destino": "Roma", "data_ida": ida, "internacional": True}
        ).get_json()["viagem_id"]

        res = self.client.get(f"/api/viagens/{viagem_id}/timeline-card")
        self.assertEqual(res.status_code, 200)
        card = res.get_json()
        self.assertEqual(card["type"], "projeto_viagem")
        self.assertEqual(card["data"]["origem"], "viagem")
        self.assertIsInstance(card["data"]["marcos_planejamento"], list)
        self.assertEqual(card["actions"], [])  # sem link circular pra propria aba

    def test_timeline_card_viagem_inexistente_404(self):
        res = self.client.get("/api/viagens/99999/timeline-card")
        self.assertEqual(res.status_code, 404)

    def test_como_projeto_ainda_funciona_sem_regressao(self):
        ida = (date.today() + timedelta(days=10)).isoformat()
        viagem_id = self.client.post("/api/viagens", json={"destino": "Curitiba", "data_ida": ida}).get_json()[
            "viagem_id"
        ]
        res = self.client.get(f"/api/viagens/{viagem_id}/como-projeto")
        self.assertEqual(res.status_code, 200)
        self.assertIn("marcos_planejamento", res.get_json())


# ---- US-F12: status de voo (voo_status.py), API SEMPRE mockada ------------

class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


AVIATIONSTACK_PAYLOAD_OK = {
    "data": [
        {
            "flight_status": "active",
            "departure": {"gate": "12", "terminal": "2", "delay": 15, "scheduled": "2026-12-25T10:00:00+00:00", "actual": "2026-12-25T10:15:00+00:00"},
        }
    ]
}


class VooStatusPuroTestCase(unittest.TestCase):
    def _cache_mem(self):
        armazenado = {}

        def obter(numero_voo, data):
            return armazenado.get((numero_voo, data))

        def salvar(numero_voo, data, resposta_json):
            armazenado[(numero_voo, data)] = {"resposta_json": resposta_json, "buscado_em": datetime.now().isoformat()}

        return obter, salvar, armazenado

    def test_sem_chave_configurada_nao_chama_rede(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVIATIONSTACK_API_KEY", None)
            obter, salvar, _ = self._cache_mem()
            with patch("voo_status.requests.get") as mock_get:
                resultado = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
            mock_get.assert_not_called()
            self.assertEqual(resultado, {"configurado": False})

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_com_chave_chama_api_mockada_e_mapeia_status(self):
        obter, salvar, armazenado = self._cache_mem()
        with patch("voo_status.requests.get", return_value=FakeResp(AVIATIONSTACK_PAYLOAD_OK)) as mock_get:
            resultado = voo_status.status_voo("la3251", "2026-12-25", obter, salvar)
        mock_get.assert_called_once()
        self.assertEqual(resultado["status"], "em_voo")
        self.assertEqual(resultado["atraso_min"], 15)
        self.assertEqual(resultado["portao"], "12")
        self.assertEqual(resultado["terminal"], "2")
        self.assertFalse(resultado["cache"])
        self.assertTrue(armazenado)  # gravou no cache

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_segunda_chamada_dentro_da_janela_usa_cache_sem_rede(self):
        obter, salvar, _ = self._cache_mem()
        with patch("voo_status.requests.get", return_value=FakeResp(AVIATIONSTACK_PAYLOAD_OK)) as mock_get:
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
            resultado2 = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
        self.assertEqual(mock_get.call_count, 1)  # so a primeira chamou a API
        self.assertTrue(resultado2["cache"])
        self.assertEqual(resultado2["status"], "em_voo")

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_cache_expira_depois_do_ttl(self):
        obter, salvar, _ = self._cache_mem()
        with patch("voo_status.requests.get", return_value=FakeResp(AVIATIONSTACK_PAYLOAD_OK)) as mock_get:
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
            depois = datetime.now() + voo_status.CACHE_TTL + timedelta(minutes=1)
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=depois)
        self.assertEqual(mock_get.call_count, 2)

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_erro_de_rede_cai_pro_cache_velho_se_existir(self):
        obter, salvar, _ = self._cache_mem()
        with patch("voo_status.requests.get", return_value=FakeResp(AVIATIONSTACK_PAYLOAD_OK)):
            voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
        import requests as _requests

        depois = datetime.now() + voo_status.CACHE_TTL + timedelta(minutes=1)
        with patch("voo_status.requests.get", side_effect=_requests.RequestException("timeout")):
            resultado = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar, agora=depois)
        self.assertTrue(resultado["configurado"])
        self.assertTrue(resultado["cache"])
        self.assertEqual(resultado["status"], "em_voo")

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_erro_de_rede_sem_cache_devolve_mensagem_amigavel(self):
        obter, salvar, _ = self._cache_mem()
        import requests as _requests

        with patch("voo_status.requests.get", side_effect=_requests.RequestException("timeout")):
            resultado = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
        self.assertTrue(resultado["configurado"])
        self.assertIn("erro", resultado)

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_numero_voo_vazio_nao_chama_api(self):
        obter, salvar, _ = self._cache_mem()
        with patch("voo_status.requests.get") as mock_get:
            resultado = voo_status.status_voo("", "2026-12-25", obter, salvar)
        mock_get.assert_not_called()
        self.assertIn("erro", resultado)

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_status_desconhecido_mapeado_com_seguranca(self):
        obter, salvar, _ = self._cache_mem()
        payload = {"data": [{"flight_status": "algo_novo_que_nao_existe_ainda", "departure": {}}]}
        with patch("voo_status.requests.get", return_value=FakeResp(payload)):
            resultado = voo_status.status_voo("LA3251", "2026-12-25", obter, salvar)
        self.assertEqual(resultado["status"], "desconhecido")

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_api_devolve_data_vazio_nao_quebra(self):
        obter, salvar, _ = self._cache_mem()
        with patch("voo_status.requests.get", return_value=FakeResp({"data": []})):
            resultado = voo_status.status_voo("LA9999", "2026-12-25", obter, salvar)
        self.assertEqual(resultado["status"], "desconhecido")


class VooStatusHTTPTestCase(unittest.TestCase):
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
        ida = (date.today() + timedelta(days=30)).isoformat()
        self.viagem_id = self.client.post("/api/viagens", json={"destino": "Miami", "data_ida": ida}).get_json()[
            "viagem_id"
        ]

    def test_sem_numero_voo_cadastrado(self):
        res = self.client.get(f"/api/viagens/{self.viagem_id}/voo-status")
        self.assertEqual(res.status_code, 200)
        self.assertIn("erro", res.get_json())

    def test_definir_numero_voo_e_consultar_status_sem_chave(self):
        res = self.client.post(f"/api/viagens/{self.viagem_id}/numero-voo", json={"numero_voo": "aa1234"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["numero_voo"], "AA1234")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AVIATIONSTACK_API_KEY", None)
            res2 = self.client.get(f"/api/viagens/{self.viagem_id}/voo-status")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json(), {"configurado": False})

    @patch.dict(os.environ, {"AVIATIONSTACK_API_KEY": "chave-de-teste-fake"})
    def test_definir_numero_voo_e_consultar_status_com_chave_mockada(self):
        self.client.post(f"/api/viagens/{self.viagem_id}/numero-voo", json={"numero_voo": "LA3251"})
        with patch("voo_status.requests.get", return_value=FakeResp(AVIATIONSTACK_PAYLOAD_OK)) as mock_get:
            res = self.client.get(f"/api/viagens/{self.viagem_id}/voo-status")
        mock_get.assert_called_once()
        dados = res.get_json()
        self.assertEqual(dados["status"], "em_voo")
        self.assertTrue(dados["configurado"])

    def test_numero_voo_viagem_inexistente_404(self):
        res = self.client.post("/api/viagens/99999/numero-voo", json={"numero_voo": "AA1"})
        self.assertEqual(res.status_code, 404)

    def test_apagar_numero_voo_com_string_vazia(self):
        self.client.post(f"/api/viagens/{self.viagem_id}/numero-voo", json={"numero_voo": "AA1234"})
        res = self.client.post(f"/api/viagens/{self.viagem_id}/numero-voo", json={"numero_voo": ""})
        self.assertIsNone(res.get_json()["numero_voo"])
        res2 = self.client.get(f"/api/viagens/{self.viagem_id}/voo-status")
        self.assertIn("erro", res2.get_json())


if __name__ == "__main__":
    unittest.main()
