"""Leva 08/11, 3a rodada (frente B, item 2): erro de ferramenta avisa que pode ter gravado em parte.

exec_registrar_tarefa comita e depois estoura (Maps). Com "diga ao Alex que essa parte nao deu" a IA dizia
que nao deu, ele pedia de novo e a tarefa duplicava. Agora a IA e mandada conferir antes de responder.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import claude_client  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()


def setUpModule():
    db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
    db.garantir_banco_nao_producao()
    db.init_db()


def _resp(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason, model=claude_client.SONNET,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20))


class ErroDepoisDoCommitTestCase(unittest.TestCase):
    def test_mensagem_manda_conferir_e_nao_repetir(self):
        gravadas = []

        def grava_e_estoura(entrada):
            gravadas.append(entrada["titulo"])  # o commit ja aconteceu quando o Maps estoura
            raise TimeoutError("maps de teste")

        respostas = [
            _resp([SimpleNamespace(type="tool_use", name="registrar_tarefa", input={"titulo": "Dentista de teste"},
                                   id="t1")], stop_reason="tool_use"),
            _resp([SimpleNamespace(type="text", text="Vou conferir.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas) as create, \
                self.assertLogs("ia.funcoes.chat", level="ERROR"):
            claude_client.chat([], "contexto", [], {"registrar_tarefa": grava_e_estoura})

        resultado = None
        for m in create.call_args_list[1].kwargs["messages"]:
            if m.get("role") == "user" and isinstance(m.get("content"), list):
                resultado = next((b for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"),
                                 resultado)
        self.assertTrue(resultado["is_error"])
        erro = json.loads(resultado["content"])["erro"]
        self.assertIn("pode ter gravado em parte", erro)
        self.assertIn("confira com a consulta certa antes de responder", erro)
        self.assertIn("nao repita a chamada", erro)
        self.assertIn("TimeoutError", erro)
        self.assertNotIn("nao deu", erro)
        self.assertEqual(gravadas, ["Dentista de teste"])


if __name__ == "__main__":
    unittest.main()
