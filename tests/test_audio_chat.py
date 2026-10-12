"""Audio do chat (2026-10-12): o microfone manda DIRETO, a fala e limpa por uma IA rapida
(ia/funcoes/fala.py - autocorrecao, muleta, nome mal ouvido) e o chat sabe que veio de audio.
Nenhuma rede: transcricao e IA sempre dubladas."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from ia.funcoes import fala  # noqa: E402

PIN = "975310"


def _resp(texto, ok=True):
    return SimpleNamespace(ok=ok, texto=texto)


class LimparFalaTestCase(unittest.TestCase):
    def test_usa_a_versao_limpa(self):
        with patch("ia.core.chamar_ia", return_value=_resp("Amanhã busco minha mãe no Dom Joaquim às quatro.")) as m:
            texto, ok = fala.limpar("é, tipo, amanhã busco minha mãe no dom joaquim às três, não, às quatro, né", "Dom Joaquim")
        self.assertTrue(ok)
        self.assertEqual(texto, "Amanhã busco minha mãe no Dom Joaquim às quatro.")
        self.assertIn("Dom Joaquim", m.call_args.kwargs["contexto_fixo"])  # vocabulario vai junto

    def test_cai_no_texto_cru_quando_algo_da_errado(self):
        bruto = "lembra de levar a fiorina na revisão sexta, ah não, sábado"
        casos = [
            _resp("", ok=False),  # falha da IA
            _resp(""),  # resposta vazia
            _resp("Claro! " + "Aqui está uma explicação longa e inventada. " * 10),  # respondeu/inventou
            _resp("ok"),  # cortou o pedido
        ]
        for r in casos:
            with self.subTest(r=r.texto[:20]), patch("ia.core.chamar_ia", return_value=r):
                self.assertEqual(fala.limpar(bruto), (bruto, False))
        with patch("ia.core.chamar_ia", side_effect=RuntimeError("rede")):
            self.assertEqual(fala.limpar(bruto), (bruto, False))

    def test_frase_curta_nem_chama_a_ia(self):
        with patch("ia.core.chamar_ia") as m:
            self.assertEqual(fala.limpar("beleza manda"), ("beleza manda", False))
        m.assert_not_called()


class RotasAudioTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.execute("INSERT INTO tasks (title) VALUES ('Buscar a mãe no Dom Joaquim')")
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def _enviar(self, **extra):
        dados = {"audio": (io.BytesIO(b"\x00" * 2000), "fala.m4a", "audio/mp4"), "duracao": "4", **extra}
        return self.client.post("/api/voz/transcrever", data=dados, content_type="multipart/form-data")

    def test_sem_limpar_devolve_o_cru_como_antes(self):
        with patch("telegram_captura.transcrever", return_value="é tipo amanhã"), patch("ia.funcoes.fala.limpar") as m:
            r = self._enviar()
        self.assertEqual(r.get_json(), {"texto": "é tipo amanhã"})
        m.assert_not_called()

    def test_limpar_usa_o_vocabulario_dele(self):
        with patch("telegram_captura.transcrever", return_value="busca a mãe no dom joaquim"), \
                patch("ia.funcoes.fala.limpar", return_value=("Busca a mãe no Dom Joaquim.", True)) as m:
            r = self._enviar(limpar="1").get_json()
        self.assertEqual(r, {"texto": "Busca a mãe no Dom Joaquim.", "bruto": "busca a mãe no dom joaquim", "limpo": True})
        vocabulario = m.call_args.args[1]
        self.assertIn("Buscar a mãe no Dom Joaquim", vocabulario)  # tarefa aberta
        self.assertIn("Fiorino", vocabulario)

    def test_erro_da_transcricao_vem_legivel_pro_painel(self):
        import telegram_captura
        with patch("telegram_captura.transcrever", side_effect=telegram_captura.ErroCaptura("não consegui transcrever")):
            r = self._enviar(limpar="1")
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json()["error"], "não consegui transcrever")  # nucleo/api.js le `error`

    def test_chat_sabe_que_veio_de_audio(self):
        vistos = []

        def fake(mensagens, contexto, memorias, executores):
            vistos.append(contexto)
            return "ok", [], {"model": "x", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}

        with patch("claude_client.chat", side_effect=fake):
            self.client.post("/api/chat", json={"mensagem": "busca a mãe amanhã às quatro horas", "audio": True})
            self.client.post("/api/chat", json={"mensagem": "busca a mãe amanhã às quatro horas da tarde"})
            self.client.post("/api/chat", json={"mensagem": "e amanhã, vai chover em Brusque?", "modo": "voz"})
        self.assertIn("ESTA MENSAGEM VEIO DE AUDIO", vistos[0])
        self.assertNotIn("ESTA MENSAGEM VEIO DE AUDIO", vistos[1])  # digitado: nada muda
        self.assertIn("ESTA MENSAGEM VEIO DE AUDIO", vistos[2])  # modo conversa tambem e audio


if __name__ == "__main__":
    unittest.main()
