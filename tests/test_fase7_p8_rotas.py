"""Fase 7, faixa P8: rotas/p8_avisos.py. A infra de carga automatica de
rotas (`rotas.registrar_todas`, Etapa 0/e0-backend) ainda nao chegou em
`fase7/integracao` nesta sessao (sem `rotas/__init__.py`/`_base.py`), entao
este teste registra o Blueprint `bp` sozinho, num Flask app minimo, em vez
de subir `app.py` inteiro - o modulo de rota (`rotas/p8_avisos.py`) so usa
`db`/`flask`, sem nada de `rotas._base`, entao continua funcionando sem
mudanca nenhuma quando essa infra for integrada.

Sessao aqui e' so um detalhe de nome (o prompt pede "sessao, nao token") -
a autenticacao de verdade fica com app.py (global, fora do escopo desta
faixa); estes testes chamam a rota direto, sem PIN."""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from flask import Flask

import db
from assistente import avisos
from rotas.p8_avisos import bp


class _BaseRotaTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()

        app = Flask(__name__)
        app.register_blueprint(bp)
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _put(self, path, corpo):
        return self.client.put(path, data=json.dumps(corpo), content_type="application/json")


class ListarAvisosTestCase(_BaseRotaTestCase):
    def test_get_devolve_catalogo_inteiro(self):
        resp = self.client.get("/api/assistente/avisos")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertIn("tipos", corpo)
        self.assertIn("silencio", corpo)
        self.assertEqual(len(corpo["tipos"]), len(avisos.TIPOS))
        self.assertEqual(corpo["silencio"], {"inicio": "22:00", "fim": "07:00"})

    def test_get_tipo_tem_os_campos_esperados(self):
        resp = self.client.get("/api/assistente/avisos")
        corpo = resp.get_json()
        item = next(t for t in corpo["tipos"] if t["tipo"] == "cartao_limite")
        for campo in ("tipo", "label", "conhecido", "ligado", "canal", "silencio_inicio", "silencio_fim"):
            self.assertIn(campo, item)
        self.assertTrue(item["conhecido"])
        self.assertTrue(item["ligado"])
        self.assertEqual(item["canal"], "ambos")


class AtualizarTipoTestCase(_BaseRotaTestCase):
    def test_desligar_tipo_via_put(self):
        resp = self._put("/api/assistente/avisos/cartao_limite", {"ligado": False})
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertFalse(corpo["ligado"])

        # persistiu: uma nova leitura reflete a mudanca
        resp2 = self.client.get("/api/assistente/avisos")
        item = next(t for t in resp2.get_json()["tipos"] if t["tipo"] == "cartao_limite")
        self.assertFalse(item["ligado"])

    def test_mudar_canal_via_put(self):
        resp = self._put("/api/assistente/avisos/lembrete", {"canal": "caixa"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["canal"], "caixa")

    def test_canal_invalido_devolve_400(self):
        resp = self._put("/api/assistente/avisos/lembrete", {"canal": "fax"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_ligado_nao_booleano_devolve_400(self):
        resp = self._put("/api/assistente/avisos/lembrete", {"ligado": "sim"})
        self.assertEqual(resp.status_code, 400)

    def test_tipo_desconhecido_devolve_404(self):
        resp = self._put("/api/assistente/avisos/nao_existe_esse_tipo", {"ligado": False})
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.get_json())

    def test_silencio_por_tipo_via_put(self):
        resp = self._put(
            "/api/assistente/avisos/briefing_noite",
            {"silencio_inicio": "23:00", "silencio_fim": "06:00"},
        )
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertEqual(corpo["silencio_inicio"], "23:00")
        self.assertEqual(corpo["silencio_fim"], "06:00")
        self.assertTrue(corpo["silencio_customizado"])

    def test_silencio_por_tipo_invalido_devolve_400(self):
        resp = self._put(
            "/api/assistente/avisos/briefing_noite",
            {"silencio_inicio": "25:99", "silencio_fim": "06:00"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_put_sem_json_nao_quebra(self):
        resp = self.client.put("/api/assistente/avisos/lembrete")
        # Corpo vazio: nenhum campo pra mudar, devolve o estado atual (200).
        self.assertEqual(resp.status_code, 200)


class AtualizarSilencioGlobalTestCase(_BaseRotaTestCase):
    def test_put_silencio_global(self):
        resp = self._put("/api/assistente/avisos/silencio", {"inicio": "23:00", "fim": "06:30"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["silencio"], {"inicio": "23:00", "fim": "06:30"})

        resp2 = self.client.get("/api/assistente/avisos")
        self.assertEqual(resp2.get_json()["silencio"], {"inicio": "23:00", "fim": "06:30"})

    def test_put_silencio_global_invalido_devolve_400(self):
        resp = self._put("/api/assistente/avisos/silencio", {"inicio": "vinte e duas", "fim": "06:00"})
        self.assertEqual(resp.status_code, 400)

    def test_put_silencio_global_sem_campos_devolve_400(self):
        resp = self._put("/api/assistente/avisos/silencio", {})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
