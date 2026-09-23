import base64
import io
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import notificacoes
import vida

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class SomarMesesTestCase(unittest.TestCase):
    def test_mes_simples(self):
        self.assertEqual(vida.somar_meses(date(2026, 1, 15), 1), date(2026, 2, 15))

    def test_vira_ano(self):
        self.assertEqual(vida.somar_meses(date(2026, 12, 1), 2), date(2027, 2, 1))

    def test_crava_no_ultimo_dia_do_mes_destino(self):
        self.assertEqual(vida.somar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_zero_meses(self):
        self.assertEqual(vida.somar_meses(date(2026, 5, 10), 0), date(2026, 5, 10))


class GarantiasDbTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_create_list_get_delete(self):
        gid = db.create_garantia(self.conn, "Geladeira", "2026-01-01", 12, None)
        itens = db.list_garantias(self.conn)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["produto"], "Geladeira")
        self.assertEqual(itens[0]["notificado"], 0)
        self.assertEqual(db.get_garantia(self.conn, gid)["produto"], "Geladeira")
        db.delete_garantia(self.conn, gid)
        self.assertEqual(db.list_garantias(self.conn), [])

    def test_marcar_notificada(self):
        gid = db.create_garantia(self.conn, "TV", "2026-01-01", 12, None)
        db.marcar_garantia_notificada(self.conn, gid)
        self.assertEqual(db.get_garantia(self.conn, gid)["notificado"], 1)

    def test_anexo_persistido(self):
        anexo = base64.b64encode(b"conteudo-fake-pdf").decode("ascii")
        gid = db.create_garantia(self.conn, "Notebook", "2026-01-01", 24, anexo)
        self.assertEqual(db.get_garantia(self.conn, gid)["nota_fiscal_anexo"], anexo)


class GarantiasApiTestCase(unittest.TestCase):
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

    def test_criar_via_json_sem_anexo(self):
        res = self.client.post(
            "/api/garantias",
            json={"produto": "Fogao", "data_compra": "2026-01-01", "prazo_garantia_meses": 12},
        )
        self.assertEqual(res.status_code, 201)
        garantia_id = res.get_json()["garantia_id"]

        listagem = self.client.get("/api/garantias").get_json()
        self.assertEqual(len(listagem), 1)
        self.assertEqual(listagem[0]["produto"], "Fogao")
        self.assertEqual(listagem[0]["vencimento"], "2027-01-01")
        self.assertIsNone(listagem[0]["nota_fiscal_anexo"])
        self.assertIn("dias_ate", listagem[0])
        self.assertGreater(garantia_id, 0)

    def test_criar_via_multipart_com_anexo_pdf(self):
        data = {
            "produto": "Micro-ondas",
            "data_compra": "2026-01-01",
            "prazo_garantia_meses": "12",
            "nota_fiscal": (io.BytesIO(b"%PDF-1.4 fake"), "nota.pdf"),
        }
        res = self.client.post("/api/garantias", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        garantia_id = res.get_json()["garantia_id"]
        listagem = self.client.get("/api/garantias").get_json()
        item = next(i for i in listagem if i["id"] == garantia_id)
        self.assertIsNotNone(item["nota_fiscal_anexo"])
        self.assertEqual(base64.b64decode(item["nota_fiscal_anexo"]), b"%PDF-1.4 fake")

    def test_anexo_extensao_invalida_rejeitada(self):
        data = {
            "produto": "Liquidificador",
            "data_compra": "2026-01-01",
            "prazo_garantia_meses": "12",
            "nota_fiscal": (io.BytesIO(b"conteudo"), "nota.txt"),
        }
        res = self.client.post("/api/garantias", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_anexo_grande_demais_rejeitado(self):
        grande = b"0" * (6 * 1024 * 1024)
        data = {
            "produto": "Ar condicionado",
            "data_compra": "2026-01-01",
            "prazo_garantia_meses": "12",
            "nota_fiscal": (io.BytesIO(grande), "nota.pdf"),
        }
        res = self.client.post("/api/garantias", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_sem_produto_da_erro(self):
        res = self.client.post(
            "/api/garantias", json={"data_compra": "2026-01-01", "prazo_garantia_meses": 12}
        )
        self.assertEqual(res.status_code, 400)

    def test_data_compra_no_futuro_da_erro(self):
        futuro = (date.today() + timedelta(days=5)).isoformat()
        res = self.client.post(
            "/api/garantias", json={"produto": "X", "data_compra": futuro, "prazo_garantia_meses": 12}
        )
        self.assertEqual(res.status_code, 400)

    def test_prazo_invalido_da_erro(self):
        res = self.client.post(
            "/api/garantias", json={"produto": "X", "data_compra": "2026-01-01", "prazo_garantia_meses": 0}
        )
        self.assertEqual(res.status_code, 400)

    def test_deletar(self):
        res = self.client.post(
            "/api/garantias", json={"produto": "Fogao", "data_compra": "2026-01-01", "prazo_garantia_meses": 12}
        )
        garantia_id = res.get_json()["garantia_id"]
        res_del = self.client.delete(f"/api/garantias/{garantia_id}")
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(self.client.get("/api/garantias").get_json(), [])

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/garantias")
        self.assertEqual(res.status_code, 401)


class GarantiasVencendoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_garantia_vencendo_em_breve_aparece(self):
        hoje = date(2026, 6, 15)
        compra = hoje - timedelta(days=365 - 10)  # vence em 10 dias
        db.create_garantia(self.conn, "Fogao", compra.isoformat(), 12, None)
        avisos = notificacoes.garantias_vencendo(self.conn, hoje=hoje, dias_aviso=15)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Fogao", avisos[0][1])

    def test_garantia_longe_do_vencimento_nao_aparece(self):
        hoje = date(2026, 6, 15)
        db.create_garantia(self.conn, "Notebook", hoje.isoformat(), 24, None)
        avisos = notificacoes.garantias_vencendo(self.conn, hoje=hoje, dias_aviso=15)
        self.assertEqual(avisos, [])

    def test_garantia_ja_notificada_nao_repete(self):
        hoje = date(2026, 6, 15)
        compra = hoje - timedelta(days=365 - 5)
        gid = db.create_garantia(self.conn, "TV", compra.isoformat(), 12, None)
        db.marcar_garantia_notificada(self.conn, gid)
        avisos = notificacoes.garantias_vencendo(self.conn, hoje=hoje, dias_aviso=15)
        self.assertEqual(avisos, [])

    def test_garantia_ja_vencida_ainda_avisa_uma_vez(self):
        hoje = date(2026, 6, 15)
        compra = hoje - timedelta(days=400)
        db.create_garantia(self.conn, "Ventilador", compra.isoformat(), 12, None)
        avisos = notificacoes.garantias_vencendo(self.conn, hoje=hoje, dias_aviso=15)
        self.assertEqual(len(avisos), 1)
        self.assertIn("venceu ha", avisos[0][1])


class VerificarNotificarGarantiaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def tearDown(self):
        self.conn.close()

    def test_alerta_marca_notificado_e_nao_repete(self):
        hoje = date.today()
        compra = hoje - timedelta(days=360)
        gid = db.create_garantia(self.conn, "Fogao", compra.isoformat(), 12, None)
        with patch("push_client.configurado", return_value=True), \
             patch("telegram_bot.configurado", return_value=False), \
             patch(
                "app.list_push_subscriptions",
                return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
             ), \
             patch("push_client.enviar", return_value=True) as mock_enviar:
            app.verificar_e_notificar()
            self.assertIn("Garantia vencendo", [c.args[1] for c in mock_enviar.call_args_list])
            mock_enviar.reset_mock()
            app.verificar_e_notificar()
            self.assertNotIn("Garantia vencendo", [c.args[1] for c in mock_enviar.call_args_list])
        self.assertEqual(db.get_garantia(self.conn, gid)["notificado"], 1)


if __name__ == "__main__":
    unittest.main()
