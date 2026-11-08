"""Leva 08/11, 2a rodada (frente B, item 3): executor que estoura nao derruba o turno do chat.

Antes: a excecao subia, o turno caia com o que as ferramentas anteriores ja tinham gravado, ele via
erro, repetia o pedido e duplicava tudo. Agora: try por ferramenta, log.exception e um tool_result
{"erro": ...} com is_error, pra IA seguir o turno; a ferramenta seguinte roda normalmente.
"""
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


def _tool(nome, entrada, id_):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


def _resultados_de_ferramenta(chamada):
    achados = []
    for m in chamada.kwargs["messages"]:
        if m.get("role") == "user" and isinstance(m.get("content"), list):
            achados += [b for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]
    return achados


class ExecutorQueEstouraTestCase(unittest.TestCase):
    def test_excecao_vira_erro_e_a_seguinte_roda(self):
        rodou = []

        def quebra(entrada):
            rodou.append("tarefa")
            raise RuntimeError("banco travado de teste")

        def gasto(entrada):
            rodou.append("gasto")
            return {"ok": True}

        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "Pagar a conta de teste"}, "t1"),
                   _tool("registrar_gasto", {"titulo": "lanche de teste", "valor": 12}, "t2")],
                  stop_reason="tool_use"),
            _resp([SimpleNamespace(type="text", text="Certo.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas) as create, \
                self.assertLogs("ia.funcoes.chat", level="ERROR") as logs:
            texto, acoes, _uso = claude_client.chat(
                [], "contexto", [], {"registrar_tarefa": quebra, "registrar_gasto": gasto})

        self.assertEqual(texto, "Certo.")
        self.assertEqual(rodou, ["tarefa", "gasto"])
        self.assertEqual(acoes, ["registrar_gasto"])  # a que estourou nao conta como feita
        self.assertTrue(any("registrar_tarefa" in linha for linha in logs.output))
        self.assertTrue(any("Traceback" in linha for linha in logs.output))  # log.exception, com a pilha

        resultados = {r["tool_use_id"]: r for r in _resultados_de_ferramenta(create.call_args_list[1])}
        self.assertTrue(resultados["t1"].get("is_error"))
        self.assertIn("erro", resultados["t1"]["content"])
        self.assertIn("RuntimeError", resultados["t1"]["content"])
        self.assertNotIn("banco travado", resultados["t1"]["content"])  # curto: sem a mensagem interna
        self.assertNotIn("is_error", resultados["t2"])
        self.assertIn('"ok": true', resultados["t2"]["content"])

    def test_turno_seguinte_continua_depois_do_erro(self):
        chamadas = []

        def quebra(entrada):
            chamadas.append(entrada)
            raise ValueError("teste")

        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "Ligar pro Fulano de teste"}, "t1")], stop_reason="tool_use"),
            _resp([SimpleNamespace(type="text", text="Essa nao deu agora.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas), \
                self.assertLogs("ia.funcoes.chat", level="ERROR"):
            texto, acoes, _uso = claude_client.chat([], "contexto", [], {"registrar_tarefa": quebra})
        self.assertEqual(texto, "Essa nao deu agora.")
        self.assertEqual(acoes, [])
        self.assertEqual(len(chamadas), 1)

    def test_ferramenta_desconhecida_segue_igual(self):
        respostas = [
            _resp([_tool("nao_existe", {}, "t1")], stop_reason="tool_use"),
            _resp([SimpleNamespace(type="text", text="Certo.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas) as create:
            texto, acoes, _uso = claude_client.chat([], "contexto", [], {})
        self.assertEqual((texto, acoes), ("Certo.", []))
        [r] = _resultados_de_ferramenta(create.call_args_list[1])
        self.assertIn("ferramenta desconhecida", r["content"])
        self.assertNotIn("is_error", r)


if __name__ == "__main__":
    unittest.main()
