import contextlib
import os
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import telegram_bot


@contextlib.contextmanager
def tempfile_arquivo():
    """Arquivo temporario de verdade no disco - enviar_documento abre o
    caminho com open(), entao precisa existir mesmo (nao da pra mockar isso
    com um caminho fake sem tambem mockar open, o que esconderia bug real)."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(b"conteudo fake de backup")
        tmp.flush()
        yield tmp.name


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

    def test_sem_botoes_nao_manda_reply_markup(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            telegram_bot.enviar_mensagem("oi")
        self.assertNotIn("reply_markup", mock_post.call_args.kwargs["json"])

    def test_com_botoes_manda_inline_keyboard(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            telegram_bot.enviar_mensagem("parada", botoes=[("Marcar como feito", "completar_tarefa:5")])
        teclado = mock_post.call_args.kwargs["json"]["reply_markup"]["inline_keyboard"]
        self.assertEqual(teclado, [[{"text": "Marcar como feito", "callback_data": "completar_tarefa:5"}]])


class EnviarDocumentoTestCase(unittest.TestCase):
    def test_sem_configurado_retorna_false_sem_chamar_rede(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), patch(
            "requests.post"
        ) as mock_post, tempfile_arquivo() as caminho:
            self.assertFalse(telegram_bot.enviar_documento(caminho))
        mock_post.assert_not_called()

    def test_sucesso_retorna_true_e_manda_multipart(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post, tempfile_arquivo() as caminho:
            ok = telegram_bot.enviar_documento(caminho, legenda="backup semanal")
        self.assertTrue(ok)
        args, kwargs = mock_post.call_args
        self.assertIn("abc", args[0])
        self.assertIn("sendDocument", args[0])
        self.assertEqual(kwargs["data"]["chat_id"], "123")
        self.assertEqual(kwargs["data"]["caption"], "backup semanal")
        self.assertIn("document", kwargs["files"])

    def test_sem_legenda_nao_manda_caption(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post, tempfile_arquivo() as caminho:
            telegram_bot.enviar_documento(caminho)
        self.assertNotIn("caption", mock_post.call_args.kwargs["data"])

    def test_erro_http_retorna_false(self):
        mock_resposta = MagicMock(status_code=403)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta), tempfile_arquivo() as caminho:
            self.assertFalse(telegram_bot.enviar_documento(caminho))

    def test_falha_de_rede_retorna_false_sem_explodir(self):
        import requests as requests_module

        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", side_effect=requests_module.RequestException("timeout")), tempfile_arquivo() as caminho:
            self.assertFalse(telegram_bot.enviar_documento(caminho))

    def test_arquivo_inexistente_retorna_false_sem_explodir(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}):
            self.assertFalse(telegram_bot.enviar_documento("/caminho/que/nao/existe.db"))


class ResponderCallbackTestCase(unittest.TestCase):
    def test_sem_configurado_retorna_false_sem_chamar_rede(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), patch(
            "requests.post"
        ) as mock_post:
            self.assertFalse(telegram_bot.responder_callback("cb1"))
        mock_post.assert_not_called()

    def test_sucesso_manda_callback_query_id(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            self.assertTrue(telegram_bot.responder_callback("cb1", "Feito!"))
        self.assertEqual(mock_post.call_args.kwargs["json"], {"callback_query_id": "cb1", "text": "Feito!"})

    def test_sem_texto_nao_inclui_campo_text(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            telegram_bot.responder_callback("cb1")
        self.assertNotIn("text", mock_post.call_args.kwargs["json"])

    def test_falha_de_rede_retorna_false(self):
        import requests as requests_module

        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", side_effect=requests_module.RequestException("timeout")):
            self.assertFalse(telegram_bot.responder_callback("cb1"))


class RemoverBotoesTestCase(unittest.TestCase):
    def test_sem_configurado_retorna_false(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), patch(
            "requests.post"
        ) as mock_post:
            self.assertFalse(telegram_bot.remover_botoes("123", 42))
        mock_post.assert_not_called()

    def test_sucesso_manda_reply_markup_vazio(self):
        mock_resposta = MagicMock(status_code=200)
        with patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}
        ), patch("requests.post", return_value=mock_resposta) as mock_post:
            self.assertTrue(telegram_bot.remover_botoes("123", 42))
        corpo = mock_post.call_args.kwargs["json"]
        self.assertEqual(corpo["message_id"], 42)
        self.assertEqual(corpo["reply_markup"], {"inline_keyboard": []})


class ProcessarCallbackTestCase(unittest.TestCase):
    def _update(self, dados="completar_tarefa:5", chat_id=999, callback_id="cb1", message_id=42):
        return {
            "callback_query": {
                "id": callback_id,
                "data": dados,
                "message": {"message_id": message_id, "chat": {"id": chat_id}},
            }
        }

    def test_chamado_autorizado_chama_callback_fn(self):
        callback_fn = MagicMock(return_value="Marquei como feita!")
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            resultado = telegram_bot.processar_callback(self._update(), callback_fn)
        callback_fn.assert_called_once_with("completar_tarefa:5")
        self.assertEqual(
            resultado,
            {"callback_query_id": "cb1", "chat_id": "999", "message_id": 42, "texto_resposta": "Marquei como feita!"},
        )

    def test_chat_nao_autorizado_ignora_em_silencio(self):
        callback_fn = MagicMock(return_value="Marquei como feita!")
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            resultado = telegram_bot.processar_callback(self._update(chat_id=111), callback_fn)
        self.assertIsNone(resultado)
        callback_fn.assert_not_called()

    def test_none_sem_callback_query(self):
        callback_fn = MagicMock()
        self.assertIsNone(telegram_bot.processar_callback({"message": {}}, callback_fn))
        callback_fn.assert_not_called()

    def test_none_sem_data(self):
        update = self._update()
        del update["callback_query"]["data"]
        callback_fn = MagicMock()
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}):
            self.assertIsNone(telegram_bot.processar_callback(update, callback_fn))
        callback_fn.assert_not_called()

    def test_none_sem_message(self):
        update = {"callback_query": {"id": "cb1", "data": "completar_tarefa:5"}}
        callback_fn = MagicMock()
        self.assertIsNone(telegram_bot.processar_callback(update, callback_fn))
        callback_fn.assert_not_called()

    def test_none_sem_chat_id_no_message(self):
        update = self._update()
        del update["callback_query"]["message"]["chat"]
        callback_fn = MagicMock()
        self.assertIsNone(telegram_bot.processar_callback(update, callback_fn))
        callback_fn.assert_not_called()

    def test_sem_telegram_chat_id_configurado_nao_autoriza_ninguem(self):
        callback_fn = MagicMock()
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}):
            self.assertIsNone(telegram_bot.processar_callback(self._update(), callback_fn))
        callback_fn.assert_not_called()


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

    def test_callback_fn_processa_toque_de_botao_e_nao_chama_chat_fn(self):
        parar_evento = threading.Event()
        update = {
            "update_id": 1,
            "callback_query": {
                "id": "cb1",
                "data": "completar_tarefa:5",
                "message": {"message_id": 42, "chat": {"id": 999}},
            },
        }

        def fake_buscar_updates(offset):
            parar_evento.set()
            return [update]

        chat_fn = MagicMock()
        callback_fn = MagicMock(return_value="Marquei como feita!")
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "999"}), patch(
            "telegram_bot._buscar_updates", side_effect=fake_buscar_updates
        ), patch("telegram_bot.responder_callback", return_value=True) as mock_responder, patch(
            "telegram_bot.remover_botoes", return_value=True
        ) as mock_remover:
            telegram_bot.iniciar_polling(chat_fn, parar_evento=parar_evento, callback_fn=callback_fn)

        callback_fn.assert_called_once_with("completar_tarefa:5")
        chat_fn.assert_not_called()
        mock_responder.assert_called_once_with("cb1", "Marquei como feita!")
        mock_remover.assert_called_once_with("999", 42)

    def test_sem_callback_fn_update_de_botao_e_ignorado(self):
        # sem callback_fn configurado, um callback_query cai no caminho normal
        # (processar_update) - que ignora silenciosamente por nao ter "message"
        parar_evento = threading.Event()
        update = {
            "update_id": 1,
            "callback_query": {
                "id": "cb1",
                "data": "completar_tarefa:5",
                "message": {"message_id": 42, "chat": {"id": 999}},
            },
        }

        def fake_buscar_updates(offset):
            parar_evento.set()
            return [update]

        chat_fn = MagicMock()
        with patch("telegram_bot._buscar_updates", side_effect=fake_buscar_updates), patch(
            "telegram_bot.enviar_mensagem"
        ) as mock_enviar:
            telegram_bot.iniciar_polling(chat_fn, parar_evento=parar_evento)

        chat_fn.assert_not_called()
        mock_enviar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
