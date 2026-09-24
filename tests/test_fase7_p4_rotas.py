# Faixa P4 (Fase 7): rotas/p4_regras.py. Segue o mesmo padrao de
# tests/test_fase7_p8_rotas.py - Flask app minimo com so o Blueprint desta
# faixa registrado (nao sobe app.py inteiro), banco temporario com
# db.init_db() (aplica migracoes/*.sql automaticamente, Etapa 0/X1 - inclui
# migracoes/202609241230_p4_regras.sql). Sem PIN aqui (autenticacao real e
# global, em app.py, fora do escopo desta faixa).
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from flask import Flask

import db
from rotas.p4_regras import bp


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

    def _post(self, path, corpo=None):
        return self.client.post(path, data=json.dumps(corpo or {}), content_type="application/json")

    def _conn(self):
        return db.get_db()


REGRA_DIARIA = {
    "gatilho": "horario",
    "condicao": {"tipo": "diario", "hora": "18:00"},
    "acao": {"mensagem": "tomar o remedio"},
    "texto": "todo dia as 18h me lembra de tomar o remedio",
}


class TestMigracaoAplicada(_BaseRotaTestCase):
    def test_tabela_p4_regras_existe(self):
        conn = self._conn()
        try:
            # nao levanta sqlite3.OperationalError
            conn.execute("SELECT id, texto_original, json, ativa, pausada_ate, criada_em, ultima_vez "
                         "FROM p4_regras").fetchall()
        finally:
            conn.close()


class TestListar(_BaseRotaTestCase):
    def test_lista_vazia(self):
        resp = self.client.get("/api/p4_regras")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"regras": []})

    def test_lista_regra_confirmada(self):
        self._post("/api/p4_regras/confirmar", {"texto_original": REGRA_DIARIA["texto"], "json": REGRA_DIARIA})
        resp = self.client.get("/api/p4_regras")
        regras = resp.get_json()["regras"]
        self.assertEqual(len(regras), 1)
        self.assertEqual(regras[0]["json"]["gatilho"], "horario")
        self.assertTrue(regras[0]["ativa"])
        self.assertIsNone(regras[0]["pausada_ate"])

    def test_ordem_mais_recente_primeiro(self):
        primeira = dict(REGRA_DIARIA, texto="primeira")
        segunda = dict(REGRA_DIARIA, texto="segunda")
        self._post("/api/p4_regras/confirmar", {"texto_original": "primeira", "json": primeira})
        self._post("/api/p4_regras/confirmar", {"texto_original": "segunda", "json": segunda})
        regras = self.client.get("/api/p4_regras").get_json()["regras"]
        self.assertEqual(regras[0]["texto_original"], "segunda")


class TestConfirmar(_BaseRotaTestCase):
    def test_cria_regra_valida(self):
        resp = self._post("/api/p4_regras/confirmar",
                           {"texto_original": REGRA_DIARIA["texto"], "json": REGRA_DIARIA})
        self.assertEqual(resp.status_code, 201)
        corpo = resp.get_json()
        self.assertTrue(corpo["ok"])
        self.assertIsInstance(corpo["id"], int)

        conn = self._conn()
        try:
            linha = conn.execute("SELECT * FROM p4_regras WHERE id = ?", (corpo["id"],)).fetchone()
        finally:
            conn.close()
        self.assertEqual(linha["texto_original"], REGRA_DIARIA["texto"])
        self.assertEqual(linha["ativa"], 1)
        salvo = json.loads(linha["json"])
        self.assertEqual(salvo["condicao"]["hora"], "18:00")

    def test_sem_texto_original_400(self):
        resp = self._post("/api/p4_regras/confirmar", {"json": REGRA_DIARIA})
        self.assertEqual(resp.status_code, 400)

    def test_sem_json_400(self):
        resp = self._post("/api/p4_regras/confirmar", {"texto_original": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_json_invalido_400(self):
        bruto = dict(REGRA_DIARIA, condicao={"tipo": "diario", "hora": "25:99"})
        resp = self._post("/api/p4_regras/confirmar", {"texto_original": "x", "json": bruto})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_recusa_regra_de_relacionamento(self):
        bruto = dict(REGRA_DIARIA, texto="todo dia as 18h me lembra de ligar pro meu namorado")
        resp = self._post("/api/p4_regras/confirmar", {"texto_original": bruto["texto"], "json": bruto})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("vida amorosa", resp.get_json()["error"].lower())
        # garante que nada foi criado
        self.assertEqual(self.client.get("/api/p4_regras").get_json()["regras"], [])

    def test_aceita_chave_regra_como_alternativa_a_json(self):
        resp = self._post("/api/p4_regras/confirmar",
                           {"texto_original": REGRA_DIARIA["texto"], "regra": REGRA_DIARIA})
        self.assertEqual(resp.status_code, 201)

    def test_normaliza_antes_de_gravar(self):
        # categoria em maiuscula/com espaco extra deve ser normalizada.
        bruto = {
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "  Mercado  ", "periodo": "semana", "valor_limite": "300"},
            "acao": {}, "texto": "x",
        }
        resp = self._post("/api/p4_regras/confirmar", {"texto_original": "x", "json": bruto})
        self.assertEqual(resp.status_code, 201)
        salvo = self.client.get("/api/p4_regras").get_json()["regras"][0]["json"]
        self.assertEqual(salvo["condicao"]["categoria"], "mercado")
        self.assertEqual(salvo["condicao"]["valor_limite"], 300.0)


class TestPausarRetomar(_BaseRotaTestCase):
    def _criar_regra(self) -> int:
        resp = self._post("/api/p4_regras/confirmar",
                           {"texto_original": REGRA_DIARIA["texto"], "json": REGRA_DIARIA})
        return resp.get_json()["id"]

    def test_pausar_sem_parametro_pausa_indeterminadamente(self):
        regra_id = self._criar_regra()
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        regra = self.client.get("/api/p4_regras").get_json()["regras"][0]
        self.assertIsNotNone(regra["pausada_ate"])

    def test_pausar_com_data_especifica(self):
        regra_id = self._criar_regra()
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar", {"ate": "2026-10-15"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["pausada_ate"], "2026-10-15")

    def test_pausar_com_dias(self):
        regra_id = self._criar_regra()
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar", {"dias": 7})
        self.assertEqual(resp.status_code, 200)

    def test_pausar_com_dias_invalido(self):
        regra_id = self._criar_regra()
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar", {"dias": 0})
        self.assertEqual(resp.status_code, 400)
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar", {"dias": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_pausar_com_data_invalida(self):
        regra_id = self._criar_regra()
        resp = self._post(f"/api/p4_regras/{regra_id}/pausar", {"ate": "amanha de manha"})
        self.assertEqual(resp.status_code, 400)

    def test_pausar_regra_inexistente_404(self):
        resp = self._post("/api/p4_regras/999/pausar")
        self.assertEqual(resp.status_code, 404)

    def test_retomar_limpa_pausa(self):
        regra_id = self._criar_regra()
        self._post(f"/api/p4_regras/{regra_id}/pausar")
        resp = self._post(f"/api/p4_regras/{regra_id}/retomar")
        self.assertEqual(resp.status_code, 200)
        regra = self.client.get("/api/p4_regras").get_json()["regras"][0]
        self.assertIsNone(regra["pausada_ate"])
        self.assertTrue(regra["ativa"])

    def test_retomar_regra_inexistente_404(self):
        resp = self._post("/api/p4_regras/999/retomar")
        self.assertEqual(resp.status_code, 404)


class TestApagar(_BaseRotaTestCase):
    def test_apaga_regra_existente(self):
        resp = self._post("/api/p4_regras/confirmar",
                           {"texto_original": REGRA_DIARIA["texto"], "json": REGRA_DIARIA})
        regra_id = resp.get_json()["id"]
        resp = self.client.delete(f"/api/p4_regras/{regra_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get("/api/p4_regras").get_json()["regras"], [])

    def test_apagar_regra_inexistente_404(self):
        resp = self.client.delete("/api/p4_regras/999")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
