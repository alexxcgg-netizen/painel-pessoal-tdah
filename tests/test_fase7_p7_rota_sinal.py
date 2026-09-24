# Teste HTTP fim-a-fim da faixa P7 (POST /api/sinal, rotas/p7_sinais.py).
#
# A rota so e registrada de verdade quando a infra "rotas por Blueprint com
# carga automatica" (Fase 7, Etapa 0/X1: rotas/__init__.py, rotas/_base.py,
# chamada de rotas.registrar_todas(app) no fim de app.py) ja estiver
# mesclada em fase7/integracao - ver docs/agentes/fase7-regras-faixa.md,
# secao "Infra rotas/migracoes chega pela Etapa 0". Enquanto essa infra nao
# chega nesta branch, a classe inteira fica pulada (skip, nao falha) - assim
# que a infra for mesclada e esta branch atualizada (git merge
# origin/fase7/integracao), este arquivo passa a rodar de verdade sem
# precisar tocar em nada aqui. A logica de negocio em si (token, validacao,
# gravacao, reacoes) ja esta 100% coberta, sem depender disso, em
# tests/test_fase7_p7_sinais.py.
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")


def _infra_de_rotas_disponivel() -> bool:
    try:
        import rotas  # noqa: F401
        from rotas._base import app_modulo  # noqa: F401
    except ImportError:
        return False
    return True


INFRA_DISPONIVEL = _infra_de_rotas_disponivel()

if INFRA_DISPONIVEL:
    import auth
    import db

    _tmp_dir = tempfile.TemporaryDirectory()
    db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
    db.garantir_banco_nao_producao()

    import app  # noqa: E402
    from assistente.sinais import ultimos_sinais  # noqa: E402

    MIGRACAO_SQL = (
        Path(__file__).resolve().parent.parent / "migracoes" / "202609241240_p7_sinais.sql"
    ).read_text(encoding="utf-8")

    ROTA_REGISTRADA = any(r.rule == "/api/sinal" for r in app.app.url_map.iter_rules())
else:
    ROTA_REGISTRADA = False

TOKEN = "segredo-teste-p7"


@unittest.skipUnless(
    INFRA_DISPONIVEL and ROTA_REGISTRADA,
    "infra de rotas por Blueprint (Etapa 0/X1) ainda nao chegou em fase7/integracao "
    "(ou /api/sinal nao foi registrada) - ver docs/agentes/fase7-regras-faixa.md",
)
class RotaSinalTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.executescript(MIGRACAO_SQL)
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.env_patch = patch.dict(os.environ, {"PAINEL_SINAL_TOKEN": TOKEN})
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def _post(self, corpo, token=TOKEN):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return self.client.post("/api/sinal", json=corpo, headers=headers)

    def test_sem_token_401(self):
        res = self.client.post("/api/sinal", json={"tipo": "acordei"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.get_json(), {"error": "token invalido"})

    def test_token_errado_401(self):
        res = self._post({"tipo": "acordei"}, token="errado")
        self.assertEqual(res.status_code, 401)

    def test_sem_painel_sinal_token_configurado_fecha_mesmo_com_token_certo(self):
        self.env_patch.stop()
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PAINEL_SINAL_TOKEN", None)
                res = self._post({"tipo": "acordei"})
        finally:
            self.env_patch.start()
        self.assertEqual(res.status_code, 401)

    def test_rota_nao_exige_sessao_de_pin(self):
        # e ROTAS_COM_TOKEN: passa sem /login nenhum, so com o token certo.
        res = self._post({"tipo": "acordei"})
        self.assertEqual(res.status_code, 201)

    def test_tipo_invalido_400(self):
        res = self._post({"tipo": "voando"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("tipo invalido", res.get_json()["error"])

    def test_tipo_ausente_400(self):
        res = self._post({})
        self.assertEqual(res.status_code, 400)

    def test_corpo_nao_json_nao_derruba_a_rota(self):
        res = self.client.post(
            "/api/sinal", data="nao e json", headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "text/plain"}
        )
        self.assertIn(res.status_code, (400, 415))

    def test_grava_e_devolve_id(self):
        res = self._post({"tipo": "dormir"})
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self.assertTrue(corpo["ok"])
        self.assertIsInstance(corpo["id"], int)

        conn = db.get_db()
        registros = ultimos_sinais(conn, tipo="dormir")
        conn.close()
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["id"], corpo["id"])

    def test_grava_com_lugar_e_quando(self):
        res = self._post({"tipo": "cheguei", "lugar": "trabalho", "quando": "2026-09-24T09:00:00"})
        self.assertEqual(res.status_code, 201)
        conn = db.get_db()
        registros = ultimos_sinais(conn, tipo="cheguei")
        conn.close()
        self.assertEqual(registros[0]["lugar"], "trabalho")
        self.assertEqual(registros[0]["quando"], "2026-09-24T09:00:00")

    def test_quando_ausente_usa_horario_do_servidor(self):
        res = self._post({"tipo": "carregando"})
        conn = db.get_db()
        registros = ultimos_sinais(conn, tipo="carregando")
        conn.close()
        self.assertIsNotNone(registros[0]["quando"])

    def test_quando_invalido_400(self):
        res = self._post({"tipo": "dormir", "quando": "nao-e-data"})
        self.assertEqual(res.status_code, 400)

    def test_lugar_tipo_errado_400(self):
        res = self._post({"tipo": "cheguei", "lugar": 123})
        self.assertEqual(res.status_code, 400)

    def test_reacao_cheguei_mercado_enfileira_sem_derrubar_a_rota(self):
        # P1a (assistente/caixa.py) pode nao existir ainda nesta integracao -
        # o importante e a rota continuar respondendo 201 e gravando o sinal.
        conn = db.get_db()
        conn.execute("INSERT INTO compras (item, item_normalizado) VALUES ('arroz', 'arroz')")
        conn.commit()
        conn.close()
        res = self._post({"tipo": "cheguei", "lugar": "mercado"})
        self.assertEqual(res.status_code, 201)


if __name__ == "__main__":
    unittest.main()
