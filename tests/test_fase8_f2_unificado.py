"""Fase 8, faixa F2: "Proximas cobrancas" (assinaturas + parcelas, Fase 7) na
mesma tela unificada de gastos (Fase 8 F1), sem duplicar uma cobranca que ja
veio do Nubank e tambem esta cadastrada como assinatura manual.

Nunca chama a Pluggy real - tests/conftest.py trava rede pra toda a suite."""

import os
import tempfile
import unittest
import unittest.mock
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import financas_recorrentes as fr  # noqa: E402
from rotas.f8_banco import cruzar_proximas_cobrancas_com_gastos  # noqa: E402

PIN_TESTE = "123456"


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def _criar_assinatura(self, **kw):
        conn = db.get_db()
        campos = dict(
            nome="Netflix",
            valor=39.90,
            dia_cobranca=5,
            inicio="2026-01-05",
            cartao_ou_forma="cartao",
        )
        campos.update(kw)
        fr.criar_assinatura(conn, **campos)
        conn.commit()
        conn.close()


class ProximasCobrancasRotaTestCase(_BaseTestCase):
    def test_assinatura_sem_par_no_banco_aparece_normal(self):
        self._criar_assinatura()
        resp = self.client.get("/api/gastos/proximas-cobrancas")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertEqual(len(corpo), 1)
        self.assertEqual(corpo[0]["nome"], "Netflix")
        self.assertFalse(corpo[0]["duplicado"])
        self.assertIsNone(corpo[0]["aviso"])

    def test_duplicidade_nubank_x_assinatura_vira_um_item_com_aviso(self):
        self._criar_assinatura(nome="Spotify", valor=21.90, dia_cobranca=(date.today() + timedelta(days=3)).day)
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        data_proxima = fr.proxima_cobranca_assinatura(
            {"inicio": "2026-01-01", "dia_cobranca": (date.today() + timedelta(days=3)).day},
            date.today(),
        )
        db.insert_bank_transactions(
            conn,
            conta_id,
            [
                {
                    "external_id": "tx-spotify",
                    "data": data_proxima.isoformat(),
                    "valor": -21.90,
                    "descricao": "SPOTIFY AB",
                    "categoria": "lazer",
                }
            ],
        )
        conn.commit()
        conn.close()

        resp = self.client.get("/api/gastos/proximas-cobrancas")
        corpo = resp.get_json()
        self.assertEqual(len(corpo), 1)
        self.assertTrue(corpo[0]["duplicado"])
        self.assertIn("possivel duplicidade", corpo[0]["aviso"])

    def test_nunca_chama_pluggy_de_verdade(self):
        import pluggy_client

        self._criar_assinatura()
        with unittest.mock.patch.object(pluggy_client, "get_item") as mock_item:
            resp = self.client.get("/api/gastos/proximas-cobrancas")
            mock_item.assert_not_called()
        self.assertEqual(resp.status_code, 200)


class CruzamentoFuncaoPuraTestCase(unittest.TestCase):
    def test_bate_por_nome_valor_e_data_proxima(self):
        cobrancas = [{"nome": "Netflix", "valor": 39.90, "data": "2026-10-05", "dias": 10}]
        gastos = [
            {"description": "NETFLIX.COM", "amount": 40.30, "created_at": "2026-10-03", "origem": "Nubank"},
        ]
        resultado = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
        self.assertTrue(resultado[0]["duplicado"])

    def test_nao_bate_gasto_manual(self):
        cobrancas = [{"nome": "Netflix", "valor": 39.90, "data": "2026-10-05", "dias": 10}]
        gastos = [
            {"description": "NETFLIX.COM", "amount": 39.90, "created_at": "2026-10-03", "origem": "manual"},
        ]
        resultado = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
        self.assertFalse(resultado[0]["duplicado"])

    def test_nao_bate_fora_da_tolerancia_de_valor(self):
        cobrancas = [{"nome": "Netflix", "valor": 39.90, "data": "2026-10-05", "dias": 10}]
        gastos = [
            {"description": "NETFLIX.COM", "amount": 45.00, "created_at": "2026-10-05", "origem": "Nubank"},
        ]
        resultado = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
        self.assertFalse(resultado[0]["duplicado"])

    def test_nao_bate_fora_da_tolerancia_de_data(self):
        cobrancas = [{"nome": "Netflix", "valor": 39.90, "data": "2026-10-05", "dias": 10}]
        gastos = [
            {"description": "NETFLIX.COM", "amount": 39.90, "created_at": "2026-09-01", "origem": "Nubank"},
        ]
        resultado = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
        self.assertFalse(resultado[0]["duplicado"])

    def test_nao_bate_nome_diferente(self):
        cobrancas = [{"nome": "Netflix", "valor": 39.90, "data": "2026-10-05", "dias": 10}]
        gastos = [
            {"description": "IFOOD", "amount": 39.90, "created_at": "2026-10-05", "origem": "Nubank"},
        ]
        resultado = cruzar_proximas_cobrancas_com_gastos(cobrancas, gastos)
        self.assertFalse(resultado[0]["duplicado"])


if __name__ == "__main__":
    unittest.main()
