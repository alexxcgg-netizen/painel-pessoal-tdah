import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
from viagem import modo_viagem_ativo

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class ModoViagemAtivoTestCase(unittest.TestCase):
    def test_sem_estado_e_falso(self):
        self.assertFalse(modo_viagem_ativo(None, date(2026, 1, 1)))
        self.assertFalse(modo_viagem_ativo({}, date(2026, 1, 1)))

    def test_toggle_ligado_sem_datas(self):
        self.assertTrue(modo_viagem_ativo({"ativo": True}, date(2026, 1, 1)))

    def test_toggle_desligado(self):
        self.assertFalse(modo_viagem_ativo({"ativo": False, "data_inicio": "2026-01-01"}, date(2026, 1, 1)))

    def test_dentro_da_janela(self):
        estado = {"ativo": True, "data_inicio": "2026-03-01", "data_fim": "2026-03-10"}
        self.assertTrue(modo_viagem_ativo(estado, date(2026, 3, 5)))
        self.assertTrue(modo_viagem_ativo(estado, date(2026, 3, 1)))
        self.assertTrue(modo_viagem_ativo(estado, date(2026, 3, 10)))

    def test_fora_da_janela_antes(self):
        estado = {"ativo": True, "data_inicio": "2026-03-01", "data_fim": "2026-03-10"}
        self.assertFalse(modo_viagem_ativo(estado, date(2026, 2, 28)))

    def test_fora_da_janela_depois_expira_sozinho(self):
        estado = {"ativo": True, "data_inicio": "2026-03-01", "data_fim": "2026-03-10"}
        self.assertFalse(modo_viagem_ativo(estado, date(2026, 3, 11)))

    def test_so_data_inicio_sem_fim(self):
        estado = {"ativo": True, "data_inicio": "2026-03-01", "data_fim": None}
        self.assertFalse(modo_viagem_ativo(estado, date(2026, 2, 1)))
        self.assertTrue(modo_viagem_ativo(estado, date(2026, 6, 1)))


class ModoViagemApiTestCase(unittest.TestCase):
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
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def test_get_estado_inicial_desligado(self):
        res = self.client.get("/api/modo-viagem")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertFalse(dados["ativo"])
        self.assertFalse(dados["ativo_agora"])

    def test_ativa_sem_datas(self):
        res = self.client.post("/api/modo-viagem", json={"ativo": True})
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertTrue(dados["ativo"])
        self.assertTrue(dados["ativo_agora"])

        res2 = self.client.get("/api/modo-viagem")
        self.assertTrue(res2.get_json()["ativo"])

    def test_ativa_com_datas_futuras_nao_fica_ativo_agora(self):
        futuro = "2099-01-01"
        res = self.client.post(
            "/api/modo-viagem", json={"ativo": True, "data_inicio": futuro, "data_fim": "2099-01-10"}
        )
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertTrue(dados["ativo"])
        self.assertFalse(dados["ativo_agora"])

    def test_data_fim_antes_do_inicio_da_erro(self):
        res = self.client.post(
            "/api/modo-viagem", json={"ativo": True, "data_inicio": "2026-03-10", "data_fim": "2026-03-01"}
        )
        self.assertEqual(res.status_code, 400)

    def test_data_invalida_da_erro(self):
        res = self.client.post("/api/modo-viagem", json={"ativo": True, "data_inicio": "nao-e-data"})
        self.assertEqual(res.status_code, 400)

    def test_desativa(self):
        self.client.post("/api/modo-viagem", json={"ativo": True})
        res = self.client.post("/api/modo-viagem", json={"ativo": False})
        self.assertFalse(res.get_json()["ativo_agora"])

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/modo-viagem")
        self.assertEqual(res.status_code, 401)


class ModoViagemSupressaoNotificacaoTestCase(unittest.TestCase):
    """Confirma que verificar_e_notificar realmente deixa de mandar avisos de
    rotina domestica (ex: hora de dormir) quando o modo viagem esta ativo,
    sem afetar avisos que nao sao de rotina domestica."""

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

    def test_hora_de_dormir_suprimida_com_modo_viagem_ativo(self):
        app.definir_configuracao(self.conn, "push_vapid_placeholder", "x")
        self.client.post("/api/modo-viagem", json={"ativo": True})
        with patch("notificacoes.hora_de_dormir_devida", return_value=True), \
             patch("push_client.configurado", return_value=True), \
             patch("telegram_bot.configurado", return_value=False), \
             patch(
                "app.list_push_subscriptions",
                return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
             ), \
             patch("push_client.enviar", return_value=True) as mock_enviar:
            app.verificar_e_notificar()
        tipos_enviados = [c.args[1] for c in mock_enviar.call_args_list]
        self.assertNotIn("Hora de desacelerar", tipos_enviados)

    def test_hora_de_dormir_normal_sem_modo_viagem(self):
        with patch("notificacoes.hora_de_dormir_devida", return_value=True), \
             patch("push_client.configurado", return_value=True), \
             patch("telegram_bot.configurado", return_value=False), \
             patch(
                "app.list_push_subscriptions",
                return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
             ), \
             patch("push_client.enviar", return_value=True) as mock_enviar:
            app.verificar_e_notificar()
        tipos_enviados = [c.args[1] for c in mock_enviar.call_args_list]
        self.assertIn("Hora de desacelerar", tipos_enviados)


if __name__ == "__main__":
    unittest.main()
