"""Testes do adapter OpenAI (ia/adapters/openai.py, faixa A3 da Fase 7).

Nenhum teste aqui faz chamada de rede de verdade - o cliente `openai.OpenAI`
e sempre substituido por um `unittest.mock.MagicMock` injetado no construtor
do `AdapterOpenAI` (ver `AdapterOpenAI.__init__`), entao nao precisa (nem
usa) `OPENAI_API_KEY` real.
"""

import json
import unittest
from unittest.mock import MagicMock

import httpx2
import openai

from ia.adapters.openai import AdapterOpenAI, criar_adapter
from ia.contrato import Resposta


def _erro_conexao():
    """`openai.APIConnectionError` real (nao um mock) - o adapter precisa
    reconhecer o TIPO de verdade pra decidir re-levantar em vez de converter
    em Resposta(ok=False)."""
    req = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APIConnectionError(request=req)


def _erro_timeout():
    req = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APITimeoutError(request=req)


def _resposta_mock(texto="ola", tokens_in=10, tokens_out=5,
                    cached_tokens=0, cache_write_tokens=0):
    """Monta um objeto que imita o formato de retorno de
    `client.chat.completions.create(...)` (ChatCompletion do SDK), so com os
    atributos que o adapter realmente le."""
    resp = MagicMock()
    choice = MagicMock()
    choice.message.content = texto
    resp.choices = [choice]
    resp.usage.prompt_tokens = tokens_in
    resp.usage.completion_tokens = tokens_out
    resp.usage.prompt_tokens_details.cached_tokens = cached_tokens
    resp.usage.prompt_tokens_details.cache_write_tokens = cache_write_tokens
    return resp


class TestChamadaTextoBasica(unittest.TestCase):
    def test_chamada_texto_simples_devolve_resposta_ok(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock(
            texto="oi, tudo bem?", tokens_in=20, tokens_out=8, cached_tokens=4
        )
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-luna",
            esforco="medio",
            sistema="voce e um assistente factual",
            contexto_fixo="",
            mensagens=[{"role": "user", "content": "oi"}],
            schema=None,
            max_tokens_saida=256,
            cache={},
            modo="padrao",
        )

        self.assertIsInstance(resposta, Resposta)
        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.texto, "oi, tudo bem?")
        self.assertEqual(resposta.provedor, "openai")
        self.assertEqual(resposta.modelo, "gpt-6-luna")
        self.assertEqual(resposta.tokens_in, 20)
        self.assertEqual(resposta.tokens_out, 8)
        self.assertEqual(resposta.tokens_cache_lido, 4)
        self.assertFalse(resposta.fallback_usado)
        self.assertIsNone(resposta.erro)
        self.assertGreaterEqual(resposta.latencia_ms, 0)

        # A primeira mensagem enviada precisa ser role "developer" com o
        # texto de `sistema` (ver comentario no adapter sobre o motivo).
        _, kwargs = cliente.chat.completions.create.call_args
        self.assertEqual(kwargs["messages"][0]["role"], "developer")
        self.assertIn("assistente factual", kwargs["messages"][0]["content"])
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertEqual(kwargs["reasoning_effort"], "medium")
        self.assertNotIn("service_tier", kwargs)

    def test_mapa_de_esforco(self):
        casos = {"baixo": "low", "medio": "medium", "alto": "high",
                 "xhigh": "high", "max": "high", "desconhecido": "medium"}
        for esforco_entrada, esforco_esperado in casos.items():
            cliente = MagicMock()
            cliente.chat.completions.create.return_value = _resposta_mock()
            adapter = AdapterOpenAI(cliente=cliente)
            adapter.chamar(
                modelo="gpt-6-sol", esforco=esforco_entrada, sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
            _, kwargs = cliente.chat.completions.create.call_args
            self.assertEqual(kwargs["reasoning_effort"], esforco_esperado,
                              f"esforco {esforco_entrada!r}")

    def test_contexto_fixo_entra_no_prefixo_do_system(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock()
        adapter = AdapterOpenAI(cliente=cliente)
        adapter.chamar(
            modelo="gpt-6-luna", esforco="baixo", sistema="regra geral",
            contexto_fixo="contexto fixo cacheavel", mensagens=[],
            schema=None, max_tokens_saida=50, cache={}, modo="padrao",
        )
        _, kwargs = cliente.chat.completions.create.call_args
        conteudo_sistema = kwargs["messages"][0]["content"]
        self.assertIn("regra geral", conteudo_sistema)
        self.assertIn("contexto fixo cacheavel", conteudo_sistema)


class TestModoFlex(unittest.TestCase):
    def test_modo_flex_usa_service_tier_flex(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock()
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema=None, max_tokens_saida=100, cache={}, modo="flex",
        )

        self.assertTrue(resposta.ok)
        _, kwargs = cliente.chat.completions.create.call_args
        self.assertEqual(kwargs["service_tier"], "flex")

    def test_modo_padrao_nao_manda_service_tier(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock()
        adapter = AdapterOpenAI(cliente=cliente)
        adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        _, kwargs = cliente.chat.completions.create.call_args
        self.assertNotIn("service_tier", kwargs)


class TestSchemaJson(unittest.TestCase):
    def test_schema_json_valido_preenche_dados(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock(
            texto=json.dumps({"tarefa": "lavar louca", "urgente": False})
        )
        adapter = AdapterOpenAI(cliente=cliente)
        schema = {"type": "object", "properties": {"tarefa": {"type": "string"},
                                                     "urgente": {"type": "boolean"}}}

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "registra a tarefa"}],
            schema=schema, max_tokens_saida=200, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.dados, {"tarefa": "lavar louca", "urgente": False})
        self.assertFalse(resposta.fallback_usado)
        # Chamada unica (response_format aceito de primeira) - sem fallback.
        self.assertEqual(cliente.chat.completions.create.call_count, 1)
        _, kwargs = cliente.chat.completions.create.call_args
        self.assertEqual(kwargs["response_format"]["type"], "json_schema")
        self.assertEqual(kwargs["response_format"]["json_schema"]["schema"], schema)

    def test_schema_json_invalido_no_texto_devolve_dados_none(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock(
            texto="isso nao e um JSON valido {"
        )
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema={"type": "object"}, max_tokens_saida=200, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)  # a chamada em si funcionou
        self.assertIsNone(resposta.dados)  # so o parse de JSON falhou

    def test_response_format_recusado_cai_no_fallback_com_json_loads(self):
        cliente = MagicMock()
        # Primeira chamada (com response_format) falha; segunda (fallback,
        # sem response_format) funciona e devolve um JSON valido no texto.
        cliente.chat.completions.create.side_effect = [
            RuntimeError("modelo nao suporta response_format neste teste"),
            _resposta_mock(texto=json.dumps({"ok": True})),
        ]
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-sol", esforco="alto", sistema="responda em json",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
            max_tokens_saida=200, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.dados, {"ok": True})
        self.assertTrue(resposta.fallback_usado)
        self.assertEqual(cliente.chat.completions.create.call_count, 2)
        # A segunda chamada (fallback) nao deve levar response_format.
        _, kwargs_fallback = cliente.chat.completions.create.call_args
        self.assertNotIn("response_format", kwargs_fallback)
        self.assertIn("json", kwargs_fallback["messages"][0]["content"].lower())


class TestErroDeApi(unittest.TestCase):
    def test_erro_na_chamada_vira_resposta_ok_false(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = RuntimeError("falha de rede simulada")
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertIsInstance(resposta, Resposta)
        self.assertFalse(resposta.ok)
        self.assertIn("falha de rede simulada", resposta.erro)
        self.assertEqual(resposta.provedor, "openai")
        self.assertEqual(resposta.custo_usd, 0.0)

    def test_erro_tambem_no_fallback_de_schema_nao_sobe_cru(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = RuntimeError("erro 1")
        adapter = AdapterOpenAI(cliente=cliente)

        # response_format falha, fallback tambem falha (mesmo side_effect) -
        # nao pode deixar excecao subir.
        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema={"type": "object"}, max_tokens_saida=100, cache={}, modo="padrao",
        )
        self.assertFalse(resposta.ok)
        self.assertIsNotNone(resposta.erro)


class TestMensagemComImagem(unittest.TestCase):
    def test_imagem_converte_pro_formato_image_url(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock(texto="tem um gato")
        adapter = AdapterOpenAI(cliente=cliente)

        mensagens = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "o que tem nessa foto?"},
                {"type": "image", "data_b64": "ZmFrZWJhc2U2NA==", "mime": "image/jpeg"},
            ],
        }]

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=mensagens,
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        _, kwargs = cliente.chat.completions.create.call_args
        # messages[0] e o "developer" (sistema); messages[1] e a mensagem do
        # usuario com a imagem convertida.
        partes = kwargs["messages"][1]["content"]
        self.assertEqual(partes[0], {"type": "text", "text": "o que tem nessa foto?"})
        self.assertEqual(
            partes[1],
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ZmFrZWJhc2U2NA=="}},
        )

    def test_imagem_sem_mime_usa_default_png(self):
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock()
        adapter = AdapterOpenAI(cliente=cliente)

        mensagens = [{
            "role": "user",
            "content": [{"type": "image", "data_b64": "YWJj"}],
        }]
        adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="",
            contexto_fixo="", mensagens=mensagens,
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        _, kwargs = cliente.chat.completions.create.call_args
        # Sem `sistema`/`contexto_fixo`, nao ha mensagem "developer" na frente.
        self.assertEqual(kwargs["messages"][0]["content"][0]["image_url"]["url"],
                          "data:image/png;base64,YWJj")


class TestErroDeConexaoSobeParaRetry(unittest.TestCase):
    """Ajuste de contrato pedido pelo nucleo (ia/core.py, faixa A1): erro de
    rede/timeout tem que subir (raise), nao virar Resposta(ok=False), pra o
    nucleo poder re-tentar a chamada."""

    def test_timeout_sobe_como_excecao_marcada_retentavel(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = _erro_timeout()
        adapter = AdapterOpenAI(cliente=cliente)

        with self.assertRaises(openai.APITimeoutError) as ctx:
            adapter.chamar(
                modelo="gpt-6-luna", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
        self.assertTrue(getattr(ctx.exception, "retentavel", False))

    def test_erro_de_conexao_generico_tambem_sobe(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = _erro_conexao()
        adapter = AdapterOpenAI(cliente=cliente)

        with self.assertRaises(openai.APIConnectionError) as ctx:
            adapter.chamar(
                modelo="gpt-6-sol", esforco="alto", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
        self.assertTrue(getattr(ctx.exception, "retentavel", False))

    def test_timeout_na_tentativa_com_schema_sobe_sem_tentar_fallback(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = _erro_timeout()
        adapter = AdapterOpenAI(cliente=cliente)

        with self.assertRaises(openai.APITimeoutError):
            adapter.chamar(
                modelo="gpt-6-luna", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
                schema={"type": "object"}, max_tokens_saida=100, cache={}, modo="padrao",
            )
        # So a tentativa estruturada foi feita - erro de rede nao e problema
        # de schema, entao nao faz sentido gastar uma segunda chamada.
        self.assertEqual(cliente.chat.completions.create.call_count, 1)

    def test_timeout_so_na_tentativa_de_fallback_tambem_sobe(self):
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = [
            RuntimeError("response_format recusado neste teste"),
            _erro_timeout(),
        ]
        adapter = AdapterOpenAI(cliente=cliente)

        with self.assertRaises(openai.APITimeoutError) as ctx:
            adapter.chamar(
                modelo="gpt-6-luna", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
                schema={"type": "object"}, max_tokens_saida=100, cache={}, modo="padrao",
            )
        self.assertTrue(getattr(ctx.exception, "retentavel", False))
        self.assertEqual(cliente.chat.completions.create.call_count, 2)

    def test_erro_de_autenticacao_nao_e_retentavel_continua_resposta_ok_false(self):
        # Erro "comum" de API (nao de rede) continua virando Resposta, nunca
        # sobe cru - so conexao/timeout tem tratamento especial.
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = RuntimeError("401 invalid api key")
        adapter = AdapterOpenAI(cliente=cliente)

        resposta = adapter.chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        self.assertFalse(resposta.ok)
        self.assertIn("401", resposta.erro)


class TestFabricaCriarAdapter(unittest.TestCase):
    def test_criar_adapter_devolve_instancia_do_adapter(self):
        adapter = criar_adapter()
        self.assertIsInstance(adapter, AdapterOpenAI)


class TestClienteSemEnvVar(unittest.TestCase):
    def test_instanciar_adapter_sem_openai_api_key_nao_quebra(self):
        # So instanciar (sem chamar .chamar) nao deve levantar excecao mesmo
        # sem OPENAI_API_KEY no ambiente - a validacao de credencial so
        # acontece numa chamada de rede de verdade, que aqui nunca ocorre
        # porque a gente nunca chama `_client()` sem injetar um mock.
        adapter = AdapterOpenAI()
        self.assertIsNotNone(adapter)


if __name__ == "__main__":
    unittest.main()
