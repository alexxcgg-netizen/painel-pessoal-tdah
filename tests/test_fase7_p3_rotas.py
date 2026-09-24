"""Faixa P3 (briefing) - testes de rotas/p3_briefing.py. A infra de
auto-registro de Blueprint (Etapa 0/X1) ainda nao esta na integracao, entao
o teste sobe um Flask app minimo so com este Blueprint (sem o
before_request de autenticacao do app.py de verdade - essa parte e testada
pela suite do integrador quando a rota estiver registrada de verdade)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

from flask import Flask  # noqa: E402

from rotas.p3_briefing import bp  # noqa: E402


def _novo_app_de_teste() -> Flask:
    app_teste = Flask(__name__)
    app_teste.register_blueprint(bp)
    return app_teste


class HorariosRotaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = _novo_app_de_teste().test_client()

    def test_get_horarios_padrao(self):
        res = self.client.get("/api/assistente/briefing/horarios")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"manha": "07:30", "noite": "21:00"})

    def test_put_horarios_valido(self):
        res = self.client.put(
            "/api/assistente/briefing/horarios", json={"manha": "08:00", "noite": "22:30"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"manha": "08:00", "noite": "22:30"})

        res2 = self.client.get("/api/assistente/briefing/horarios")
        self.assertEqual(res2.get_json(), {"manha": "08:00", "noite": "22:30"})

    def test_put_horarios_so_um_campo(self):
        res = self.client.put("/api/assistente/briefing/horarios", json={"manha": "06:45"})
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados["manha"], "06:45")
        self.assertEqual(dados["noite"], "21:00")

    def test_put_horarios_invalido(self):
        res = self.client.put("/api/assistente/briefing/horarios", json={"manha": "25:99"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

    def test_put_horarios_corpo_vazio(self):
        res = self.client.put("/api/assistente/briefing/horarios", json={})
        self.assertEqual(res.status_code, 400)

    def test_put_horarios_corpo_nao_json(self):
        res = self.client.put(
            "/api/assistente/briefing/horarios", data="nao e json", content_type="text/plain"
        )
        self.assertEqual(res.status_code, 400)


class PreviaRotaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = _novo_app_de_teste().test_client()

    def test_previa_manha(self):
        res = self.client.get("/api/assistente/briefing/previa?tipo=manha")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados["tipo"], "manha")
        self.assertIn("titulo", dados)
        self.assertIn("corpo", dados)

    def test_previa_noite(self):
        res = self.client.get("/api/assistente/briefing/previa?tipo=noite")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertEqual(dados["tipo"], "noite")
        self.assertIsInstance(dados["opcoes"], list)
        self.assertGreater(len(dados["opcoes"]), 0)

    def test_previa_tipo_padrao_e_manha(self):
        res = self.client.get("/api/assistente/briefing/previa")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["tipo"], "manha")

    def test_previa_tipo_invalido(self):
        res = self.client.get("/api/assistente/briefing/previa?tipo=tarde")
        self.assertEqual(res.status_code, 400)

    def test_previa_nao_enfileira_nada(self):
        # "monta sem enviar" (contrato). C1: antes conferia que
        # assistente.caixa nunca entrava em sys.modules - frágil (dependia da
        # ordem dos testes; qualquer import do app ja carrega a Caixa). Agora
        # confere o que importa: nenhuma chamada a enfileirar.
        from unittest.mock import patch

        from assistente import caixa

        with patch.object(caixa, "enfileirar", side_effect=AssertionError("previa nao enfileira")) as enf:
            for tipo in ("manha", "noite"):
                res = self.client.get(f"/api/assistente/briefing/previa?tipo={tipo}")
                self.assertEqual(res.status_code, 200)
        enf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
