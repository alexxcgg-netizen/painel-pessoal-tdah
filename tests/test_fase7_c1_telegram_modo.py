"""Fase 7 / C1 - historia 9: webhook novo (N2) x polling antigo
(telegram_bot.py) nunca rodando juntos no mesmo bot (o Telegram devolve 409).
Flag TELEGRAM_MODO + deteccao (telegram_captura.modo_telegram). Nenhuma
chamada real ao Telegram: iniciar_thread e mockado."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import telegram_captura  # noqa: E402

BASE = {"TELEGRAM_BOT_TOKEN": "111:antigo", "TELEGRAM_CHAT_ID": "42", "TELEGRAM_CHAT_ID_PERMITIDO": "42"}


class ModoTelegramTestCase(unittest.TestCase):
    def _modo(self, **extra):
        return telegram_captura.modo_telegram({**BASE, **extra})

    def test_matriz_um_bot_so_nunca_os_dois(self):
        casos = [
            ({}, (True, False)),
            ({"TELEGRAM_WEBHOOK_SECRET": "s"}, (False, True)),
            ({"TELEGRAM_MODO": "polling", "TELEGRAM_WEBHOOK_SECRET": "s"}, (True, False)),
            ({"TELEGRAM_MODO": "webhook"}, (False, True)),
            ({"TELEGRAM_MODO": "ambos", "TELEGRAM_WEBHOOK_SECRET": "s"}, (False, True)),
            ({"TELEGRAM_MODO": "desligado"}, (False, False)),
            ({"TELEGRAM_MODO": "  WEBHOOK "}, (False, True)),
            ({"TELEGRAM_MODO": "qualquer-coisa"}, (True, False)),
            ({"TELEGRAM_BOT_TOKEN_CAPTURA": "111:antigo", "TELEGRAM_WEBHOOK_SECRET": "s"}, (False, True)),
        ]
        for extra, (polling, webhook) in casos:
            with self.subTest(extra=extra):
                m = self._modo(**extra)
                self.assertEqual((m["polling"], m["webhook"]), (polling, webhook))
                self.assertFalse(m["polling"] and m["webhook"])
                self.assertFalse(m["bots_separados"])

    def test_bots_separados_podem_rodar_juntos(self):
        m = self._modo(TELEGRAM_BOT_TOKEN_CAPTURA="222:captura", TELEGRAM_WEBHOOK_SECRET="s")
        self.assertEqual((m["polling"], m["webhook"], m["bots_separados"]), (True, True, True))
        m = self._modo(TELEGRAM_BOT_TOKEN_CAPTURA="222:captura", TELEGRAM_MODO="webhook")
        self.assertEqual((m["polling"], m["webhook"]), (False, True))

    def test_captura_usa_o_token_proprio_quando_existe(self):
        with patch.dict(os.environ, {**BASE, "TELEGRAM_BOT_TOKEN_CAPTURA": "222:captura"}):
            self.assertIn("bot222:captura/sendMessage", telegram_captura._url_bot("sendMessage"))
            self.assertIn("/file/bot222:captura/", telegram_captura._url_arquivo("x/y.oga"))
        with patch.dict(os.environ, BASE):
            os.environ.pop("TELEGRAM_BOT_TOKEN_CAPTURA", None)
            self.assertIn("bot111:antigo/", telegram_captura._url_bot("getFile"))


class SubidaDoPollingTestCase(unittest.TestCase):
    def _subir(self, **extra):
        env = {**BASE, "WERKZEUG_RUN_MAIN": "true", **extra}
        with patch.dict(os.environ, env), patch("telegram_bot.iniciar_thread") as iniciar:
            for var in ("TELEGRAM_MODO", "TELEGRAM_WEBHOOK_SECRET", "TELEGRAM_BOT_TOKEN_CAPTURA"):
                if var not in env:
                    os.environ.pop(var, None)
            app.iniciar_telegram()
        return iniciar

    def test_sem_webhook_sobe_o_polling(self):
        self._subir().assert_called_once()

    def test_com_webhook_configurado_nao_sobe_o_polling(self):
        self._subir(TELEGRAM_WEBHOOK_SECRET="s").assert_not_called()

    def test_flag_forca_polling(self):
        self._subir(TELEGRAM_WEBHOOK_SECRET="s", TELEGRAM_MODO="polling").assert_called_once()


class RotaWebhookRespeitaOModoTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = app.app.test_client()

    def _post(self, env, segredo="s"):
        with patch.dict(os.environ, {**BASE, "TELEGRAM_WEBHOOK_SECRET": "s", **env}), \
                patch("telegram_captura.processar_atualizacao") as processar:
            res = self.client.post("/api/telegram/webhook", json={"update_id": 7, "message": {
                "chat": {"id": 42}, "text": "comprar pao"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": segredo})
        return res, processar

    def test_modo_polling_devolve_503_sem_processar(self):
        res, processar = self._post({"TELEGRAM_MODO": "polling"})
        self.assertEqual(res.status_code, 503)
        processar.assert_not_called()

    def test_segredo_errado_continua_401_antes_do_modo(self):
        res, _ = self._post({"TELEGRAM_MODO": "polling"}, segredo="errado")
        self.assertEqual(res.status_code, 401)

    def test_modo_auto_com_segredo_processa(self):
        res, processar = self._post({})
        self.assertEqual(res.status_code, 200)
        processar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
