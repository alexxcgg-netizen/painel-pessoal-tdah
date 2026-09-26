# tests/test_fase9_ui.py - Fase 9 (f9-ui): "Bancos" e "Gastos" viram uma unica
# aba "Financas" - sem OFX, sem Pluggy Connect na UI, um so botao de
# sincronizar e paginacao de 15 em 15 dias no extrato (contrato de
# rotas/f9_financas.py, implementado em paralelo por outra faixa - aqui so
# testamos o HTML renderizado, nao a rota).
import os
import tempfile
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

import unittest

PIN_TESTE = "123456"


class Fase9UiTestCase(unittest.TestCase):
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
        self.corpo = self.client.get("/").get_data(as_text=True)

    def test_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_nao_ha_mais_aba_bancos_na_navegacao(self):
        self.assertNotIn('data-tab="bancos"', self.corpo)
        self.assertNotIn('id="tab-bancos"', self.corpo)

    def test_aba_gastos_agora_se_chama_financas(self):
        self.assertIn('data-tab="gastos"', self.corpo)
        self.assertIn("Finanças", self.corpo)

    def test_um_unico_botao_de_sincronizar(self):
        self.assertEqual(self.corpo.count('id="btn-sincronizar-nubank"'), 1)
        self.assertEqual(self.corpo.count('id="conectar-btn"'), 0)

    def test_nenhum_ofx_ou_importar_extrato_na_pagina(self):
        corpo_lower = self.corpo.lower()
        # "ofx-input-label" e uma classe css generica reaproveitada pela foto de
        # nota fiscal (input de arquivo estilizado) - o que importa e que nao
        # sobrou nenhum rastro do FORMULARIO/rota de importar extrato OFX.
        self.assertNotIn("importar extrato", corpo_lower)
        self.assertNotIn('id="importar-form"', self.corpo)
        self.assertNotIn('id="importar-btn"', self.corpo)
        self.assertNotIn('id="ofx-input"', self.corpo)
        self.assertNotIn('id="banco-select"', self.corpo)

    def test_botao_carregar_mais_extrato_presente(self):
        self.assertIn('id="btn-carregar-mais-extrato"', self.corpo)
        self.assertIn('id="lista-extrato-financas"', self.corpo)

    def test_resumo_financas_presente_e_separa_fatura_de_saldo(self):
        self.assertIn('id="resumo-financas-box"', self.corpo)
        self.assertIn('id="resumo-financas-gasto"', self.corpo)
        self.assertIn('id="resumo-financas-fatura"', self.corpo)
        self.assertIn('id="resumo-financas-saldo"', self.corpo)

    def test_contas_e_assinaturas_dentro_da_aba_financas(self):
        self.assertIn('id="lista-bancos"', self.corpo)
        self.assertIn('data-secao-id="assinaturas"', self.corpo)

    def test_rota_ofx_removida(self):
        res = self.client.post("/api/bancos/importar", data={"banco": "nubank"})
        self.assertEqual(res.status_code, 404)

    def test_arquivo_bank_ofx_nao_existe_mais(self):
        self.assertFalse((Path(__file__).resolve().parent.parent / "bank_ofx.py").exists())


if __name__ == "__main__":
    unittest.main()
