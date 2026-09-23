import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado
import auth
import db
import notificacoes

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class MediaEDesvioPadraoTestCase(unittest.TestCase):
    def test_lista_vazia(self):
        self.assertEqual(aprendizado.media_e_desvio_padrao([]), (0.0, 0.0))

    def test_uma_amostra_desvio_zero(self):
        media, desvio = aprendizado.media_e_desvio_padrao([50.0])
        self.assertEqual(media, 50.0)
        self.assertEqual(desvio, 0.0)

    def test_valores_iguais_desvio_zero(self):
        media, desvio = aprendizado.media_e_desvio_padrao([10.0, 10.0, 10.0])
        self.assertEqual(media, 10.0)
        self.assertEqual(desvio, 0.0)

    def test_calculo_conhecido(self):
        media, desvio = aprendizado.media_e_desvio_padrao([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        self.assertEqual(media, 5.0)
        self.assertAlmostEqual(desvio, 2.0, places=5)


def _inserir_gasto(conn, category, amount, quando: date):
    conn.execute(
        "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (?, ?, 'x', 'real', ?)",
        (amount, category, quando.isoformat() + " 12:00:00"),
    )
    conn.commit()


class GastosForaDoPadraoCategoriaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_sem_historico_suficiente_nao_alerta(self):
        hoje = date(2026, 6, 15)
        for i in range(3):
            _inserir_gasto(self.conn, "mercado", 100.0, hoje - timedelta(days=i + 1))
        _inserir_gasto(self.conn, "mercado", 900.0, hoje)
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(avisos, [])

    def test_gasto_muito_acima_da_media_dispara(self):
        hoje = date(2026, 6, 15)
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0 + (i % 2) * 5, hoje - timedelta(days=i + 1))
        _inserir_gasto(self.conn, "mercado", 900.0, hoje)
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(len(avisos), 1)
        self.assertIn("mercado", avisos[0][1])
        self.assertIn("900.00", avisos[0][1])

    def test_gasto_dentro_do_padrao_nao_dispara(self):
        hoje = date(2026, 6, 15)
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0 + (i % 3) * 10, hoje - timedelta(days=i + 1))
        _inserir_gasto(self.conn, "mercado", 105.0, hoje)
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(avisos, [])

    def test_categorias_diferentes_nao_se_misturam(self):
        hoje = date(2026, 6, 15)
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0, hoje - timedelta(days=i + 1))
            _inserir_gasto(self.conn, "lazer", 30.0, hoje - timedelta(days=i + 1))
        _inserir_gasto(self.conn, "lazer", 900.0, hoje)
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(len(avisos), 1)
        self.assertIn("lazer", avisos[0][1])

    def test_gasto_planejado_tipo_nao_real_ignorado(self):
        hoje = date(2026, 6, 15)
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0, hoje - timedelta(days=i + 1))
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (?, ?, 'x', 'planejado', ?)",
            (900.0, "mercado", hoje.isoformat() + " 12:00:00"),
        )
        self.conn.commit()
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(avisos, [])

    def test_sem_gasto_hoje_lista_vazia(self):
        hoje = date(2026, 6, 15)
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0, hoje - timedelta(days=i + 1))
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=hoje)
        self.assertEqual(avisos, [])


class VerificarNotificarGastoCategoriaTestCase(unittest.TestCase):
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

    def test_alerta_sai_e_nao_repete_no_mesmo_gasto(self):
        hoje = date.today()
        for i in range(10):
            _inserir_gasto(self.conn, "mercado", 100.0, hoje - timedelta(days=i + 1))
        _inserir_gasto(self.conn, "mercado", 900.0, hoje)
        with patch("push_client.configurado", return_value=True), \
             patch("telegram_bot.configurado", return_value=False), \
             patch(
                "app.list_push_subscriptions",
                return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
             ), \
             patch("push_client.enviar", return_value=True) as mock_enviar:
            app.verificar_e_notificar()
            enviados_1a_vez = [c.args[1] for c in mock_enviar.call_args_list]
            mock_enviar.reset_mock()
            app.verificar_e_notificar()
            enviados_2a_vez = [c.args[1] for c in mock_enviar.call_args_list]
        self.assertIn("Gasto fora do padrao da categoria", enviados_1a_vez)
        self.assertNotIn("Gasto fora do padrao da categoria", enviados_2a_vez)


if __name__ == "__main__":
    unittest.main()
