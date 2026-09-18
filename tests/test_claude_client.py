import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import claude_client


def _resp(content, stop_reason="end_turn", model=claude_client.SONNET, in_tok=100, out_tok=20):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _text_block(texto):
    return SimpleNamespace(type="text", text=texto)


def _tool_block(nome, entrada, id_="tool_1"):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


class ChatLoopTestCase(unittest.TestCase):
    def test_resposta_direta_sem_ferramenta(self):
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block("Oi! Como posso ajudar?")]),
        ):
            texto, acoes, usage = claude_client.chat([], "contexto", [], {})
        self.assertEqual(texto, "Oi! Como posso ajudar?")
        self.assertEqual(acoes, [])
        self.assertEqual(usage["input_tokens"], 100)

    def test_usa_ferramenta_e_depois_responde(self):
        respostas = [
            _resp([_tool_block("registrar_tarefa", {"titulo": "ligar pro dentista"})], stop_reason="tool_use"),
            _resp([_text_block("Beleza, registrei.")]),
        ]
        chamada = {}

        def exec_tarefa(entrada):
            chamada["input"] = entrada
            return {"ok": True}

        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, usage = claude_client.chat([], "contexto", [], {"registrar_tarefa": exec_tarefa})

        self.assertEqual(texto, "Beleza, registrei.")
        self.assertEqual(acoes, ["registrar_tarefa"])
        self.assertEqual(chamada["input"]["titulo"], "ligar pro dentista")
        self.assertEqual(usage["input_tokens"], 200)

    def test_executa_mais_de_uma_ferramenta_na_mesma_resposta(self):
        respostas = [
            _resp(
                [
                    _tool_block("registrar_tarefa", {"titulo": "lavar o carro"}, id_="t1"),
                    _tool_block("registrar_gasto", {"titulo": "gasolina", "valor": 100}, id_="t2"),
                ],
                stop_reason="tool_use",
            ),
            _resp([_text_block("Registrei as duas coisas.")]),
        ]
        executados = []
        executores = {
            "registrar_tarefa": lambda e: executados.append("tarefa") or {"ok": True},
            "registrar_gasto": lambda e: executados.append("gasto") or {"ok": True},
        }
        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, _usage = claude_client.chat([], "contexto", [], executores)
        self.assertEqual(texto, "Registrei as duas coisas.")
        self.assertEqual(sorted(acoes), ["registrar_gasto", "registrar_tarefa"])
        self.assertEqual(sorted(executados), ["gasto", "tarefa"])

    def test_para_depois_de_poucas_rodadas_pra_nao_ficar_preso(self):
        resposta_tool = _resp([_tool_block("gerar_plano_do_dia", {})], stop_reason="tool_use")
        with patch.object(claude_client.client.messages, "create", return_value=resposta_tool):
            texto, _acoes, _usage = claude_client.chat(
                [], "contexto", [], {"gerar_plano_do_dia": lambda e: {"plano": "..."}}
            )
        self.assertIn("complicado", texto.lower())

    def test_ferramenta_sem_executor_nao_quebra_o_loop(self):
        respostas = [
            _resp([_tool_block("ferramenta_desconhecida", {})], stop_reason="tool_use"),
            _resp([_text_block("Tudo bem, vamos por outro caminho.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, _usage = claude_client.chat([], "contexto", [], {})
        self.assertEqual(texto, "Tudo bem, vamos por outro caminho.")
        self.assertEqual(acoes, [])


if __name__ == "__main__":
    unittest.main()
