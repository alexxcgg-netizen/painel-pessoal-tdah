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

    def test_system_prompt_inclui_data_de_hoje(self):
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block("oi")]),
        ) as mock_create:
            claude_client.chat([], "contexto", [], {})
        system_enviado = mock_create.call_args.kwargs["system"]
        self.assertIn(claude_client.date.today().isoformat(), system_enviado)

    def test_registrar_memoria_e_ferramenta_disponivel(self):
        nomes = [t["name"] for t in claude_client.CHAT_TOOLS]
        self.assertIn("registrar_memoria", nomes)
        self.assertIn("quando_data", claude_client.CHAT_TOOLS[0]["input_schema"]["properties"])

    def test_cotacao_tools_disponiveis(self):
        nomes = [t["name"] for t in claude_client.CHAT_TOOLS]
        self.assertIn("registrar_item_cotacao", nomes)
        self.assertIn("comparar_cotacao", nomes)


class ExtrairItemCotacaoPdfTestCase(unittest.TestCase):
    def test_extrai_campos_do_json_devolvido(self):
        dados_json = (
            '{"fornecedor": "Ferragens Silva", "valor": 4500.0, '
            '"prazo_texto": "15 dias uteis", "observacao": "frete incluso"}'
        )
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ) as mock_create:
            dados, usage = claude_client.extrair_item_cotacao_pdf(b"%PDF-1.4 conteudo falso")

        self.assertEqual(dados["fornecedor"], "Ferragens Silva")
        self.assertEqual(dados["valor"], 4500.0)
        self.assertEqual(dados["prazo_texto"], "15 dias uteis")
        self.assertEqual(usage["input_tokens"], 100)

        conteudo_enviado = mock_create.call_args.kwargs["messages"][0]["content"]
        blocos_documento = [b for b in conteudo_enviado if b["type"] == "document"]
        self.assertEqual(len(blocos_documento), 1)
        self.assertEqual(blocos_documento[0]["source"]["media_type"], "application/pdf")

    def test_extrai_com_campos_nulos_quando_pdf_nao_tem_valor_claro(self):
        dados_json = '{"fornecedor": null, "valor": null, "prazo_texto": null, "observacao": null}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_item_cotacao_pdf(b"conteudo")
        self.assertIsNone(dados["fornecedor"])
        self.assertIsNone(dados["valor"])

    def test_extrai_ignora_markdown_ao_redor_do_json(self):
        dados_json = '```json\n{"fornecedor": "X", "valor": 100.0, "prazo_texto": null, "observacao": null}\n```'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_item_cotacao_pdf(b"conteudo")
        self.assertEqual(dados["fornecedor"], "X")


class ExtrairNotaFiscalFotoTestCase(unittest.TestCase):
    def test_extrai_campos_do_json_devolvido(self):
        dados_json = '{"valor": 89.9, "estabelecimento": "Supermercado Bom Preco", "data": "2026-09-20"}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ) as mock_create:
            dados, usage = claude_client.extrair_nota_fiscal_foto(b"fake-jpeg-bytes", "image/jpeg")

        self.assertEqual(dados["valor"], 89.9)
        self.assertEqual(dados["estabelecimento"], "Supermercado Bom Preco")
        self.assertEqual(dados["data"], "2026-09-20")
        self.assertEqual(usage["input_tokens"], 100)

        conteudo_enviado = mock_create.call_args.kwargs["messages"][0]["content"]
        blocos_imagem = [b for b in conteudo_enviado if b["type"] == "image"]
        self.assertEqual(len(blocos_imagem), 1)
        self.assertEqual(blocos_imagem[0]["source"]["media_type"], "image/jpeg")

    def test_extrai_com_campos_nulos_quando_foto_ilegivel(self):
        dados_json = '{"valor": null, "estabelecimento": null, "data": null}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_nota_fiscal_foto(b"conteudo", "image/png")
        self.assertIsNone(dados["valor"])
        self.assertIsNone(dados["estabelecimento"])

    def test_extrai_ignora_markdown_ao_redor_do_json(self):
        dados_json = '```json\n{"valor": 20.0, "estabelecimento": "Padaria", "data": null}\n```'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_nota_fiscal_foto(b"conteudo", "image/jpeg")
        self.assertEqual(dados["estabelecimento"], "Padaria")


if __name__ == "__main__":
    unittest.main()
