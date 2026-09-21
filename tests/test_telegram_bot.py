import os
import threading
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import telegram_bot


class ConfiguradoTestCase(unittest.TestCase):
    def test_configurado_false_sem_env(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            self.assertFalse(telegram_bot.configurado())

    def test_configurado_false_so_com_token(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": ""}):
            self.assertFalse(telegram_bot.configurado())

    def test_configurado_true_com_os_dois(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}):
            self.assertTrue(telegram_bot.configurado())


class ExtrairTextoEChatIdTestCase(unittest.TestCase):
    def test_extrai_texto_e_chat_id_de_update_valido(self):
        update = {"message": {"text": "oi", "chat": {"id": 123}}}
        self.assertEqual(telegram_bot.extrair_texto_e_chat_id(update), ("oi", "123"))

    def test_none_sem_message(self):
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id({}))

    def test_none_message_nao_e_dict(self):
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id({"message": "nao e dict"}))

    def test_none_sem_texto_ex_foto(self):
        update = {"message": {"photo": [{"file_id": "x"}], "chat": {"id": 123}}}
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id(update))

    def test_none_texto_vazio(self):
        update = {"message": {"text": "", "chat": {"id": 123}}}
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id(update))

    def test_none_sem_chat(self):
        update = {"message": {"text": "oi"}}
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id(update))

    def test_none_chat_sem_id(self):
        update = {"message": {"text": "oi", "chat": {}}}
        self.assertIsNone(telegram_bot.extrair_texto_e_chat_id(update))


class ProcessarUpdateTestCase(unittest.TestCase):
    def test_chama_chat_fn_quando_chat_autorizado(self):
        chat_fn = MagicMock(return_value="resposta da IA")
        update = {"message": {"text": "gastei 50 no mercado", "chat": {"id": 999}}}
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            resultado = telegram_bot.processar_update(update, chat_fn)
        self.assertEqual(resultado, "resposta da IA")
        chat_fn.assert_called_once_with("gastei 50 no mercado")

    def test_ignora_chat_nao_autorizado(self):
        chat_fn = MagicMock(return_value="resposta da IA")
        update = {"message": {"text": "oi", "chat": {"id": 111}}}
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            resultado = telegram_bot.processar_update(update, chat_fn)
        self.assertIsNone(resultado)
        chat_fn.assert_not_called()

    def test_ignora_update_sem_texto(self):
        chat_fn = MagicMock(return_value="resposta da IA")
        update = {"message": {"sticker": {}, "chat": {"id": 999}}}
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            resultado = telegram_bot.processar_update(update, chat_fn)
        self.assertIsNone(resultado)
        chat_fn.assert_not_called()

    def test_sem_telegram_chat_id_configurado_nao_autoriza_ninguem(self):
        chat_fn = MagicMock(return_value="resposta da IA")
        update = {"message": {"text": "oi", "chat": {"id": 999}}}
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}):
            resultado = telegram_bot.processar_update(update, chat_fn)
        self.assertIsNone(resultado)
        chat_fn.assert_not_called()


class EnviarMensagemTestCase(unittest.TestCase):
    def test_sem_configurado_retorna_false_sem_chamar_rede(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), patch(
            "requests.post"
        ) as mock_post:
            self.assertFalse(telegram_bot.enviar_mensagem("oi"))
        mock_post.assert_not_called()

    def test_sucesso_retorna_true(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            ok = telegram_bot.enviar_mensagem("oi, tudo bem?")
        self.assertTrue(ok)
        args, kwargs = mock_post.call_args
        self.assertIn("abc", args[0])
        self.assertEqual(kwargs["json"]["chat_id"], "123")
        self.assertEqual(kwargs["json"]["text"], "oi, tudo bem?")

    def test_erro_http_retorna_false(self):
        mock_resposta = MagicMock(status_code=403)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta):
            self.assertFalse(telegram_bot.enviar_mensagem("oi"))

    def test_falha_de_rede_retorna_false_sem_explodir(self):
        import requests as requests_module

        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", side_effect=requests_module.RequestException("timeout")):
            self.assertFalse(telegram_bot.enviar_mensagem("oi"))

    def test_corta_texto_maior_que_o_limite(self):
        mock_resposta = MagicMock(status_code=200)
        texto_grande = "a" * 5000
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            telegram_bot.enviar_mensagem(texto_grande)
        texto_enviado = mock_post.call_args.kwargs["json"]["text"]
        self.assertEqual(len(texto_enviado), telegram_bot.LIMITE_TEXTO_TELEGRAM)


class IniciarPollingTestCase(unittest.TestCase):
    def test_processa_update_e_manda_resposta_depois_para(self):
        parar_evento = threading.Event()
        update = {"update_id": 1, "message": {"text": "oi", "chat": {"id": 999}}}

        def fake_buscar_updates(offset):
            parar_evento.set()  # so um round - evita loop infinito no teste
            return [update]

        chat_fn = MagicMock(return_value="resposta")
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}), patch(
            "telegram_bot._buscar_updates", side_effect=fake_buscar_updates
        ), patch("telegram_bot.enviar_mensagem", return_value=True) as mock_enviar:
            telegram_bot.iniciar_polling(chat_fn, parar_evento=parar_evento)

        chat_fn.assert_called_once_with("oi")
        mock_enviar.assert_called_once_with("resposta")

    def test_erro_de_rede_nao_derruba_o_loop(self):
        parar_evento = threading.Event()
        chamadas = []

        def fake_buscar_updates(offset):
            chamadas.append(offset)
            if len(chamadas) >= 2:
                parar_evento.set()
                return []
            raise __import__("requests").RequestException("timeout")

        with patch("telegram_bot._buscar_updates", side_effect=fake_buscar_updates), patch(
            "telegram_bot.time.sleep"
        ):
            telegram_bot.iniciar_polling(MagicMock(), parar_evento=parar_evento)

        self.assertGreaterEqual(len(chamadas), 2)


if __name__ == "__main__":
    unittest.main()
