"""Testes de ia/adapters/gemini.py (faixa A15). Mocka SOMENTE
o SDK genai (google-genai), nunca a rede de verdade - nenhum teste aqui
pode fazer uma chamada HTTP real. Cobre: chamada basica, erro de conexao/timeout
SOBE como excecao (retry com ia/core.py, faixa A1), erro de API vira
Resposta(ok=False), schema com JSON valido e invalido na resposta, e a
descoberta do adapter via criar_adapter(). O Gemini nao tem cache de prompt
nativo como Anthropic, mas mantemos os parametros por compatibilidade com o
contrato."""

import os
import sys
import unittest
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock, patch, MagicMock

os.environ.setdefault("GEMINI_API_KEY", "teste-fake")

# Mock google.genai se nao estiver instalado (testes nao precisam do SDK real)
if "google.genai" not in sys.modules:
    mock_genai = MagicMock()
    sys.modules["google.genai"] = mock_genai
    sys.modules["google"] = MagicMock()

from ia.adapters.gemini import AdapterGemini, criar_adapter
from ia.contrato import Resposta


def _resposta_fake(texto: str, *, tokens_in=100, tokens_out=50,
                    cache_lido=0, cache_escrito=0):
    """Monta um objeto com a MESMA forma do retorno de
    client.models.generate_content (so os campos que o adapter le:
    .text e .usage_metadata.*)."""
    return SimpleNamespace(
        text=texto,
        usage_metadata=SimpleNamespace(
            prompt_token_count=tokens_in,
            candidates_token_count=tokens_out,
            cached_content_input_token_count=cache_lido,
            cache_creation_input_token_count=cache_escrito,
        ),
    )


class TestChamadaBasica(unittest.TestCase):
    def setUp(self):
        # Injeta um cliente mock - o adapter nao tentara configura()
        self.mock_client = Mock()
        self.adapter = AdapterGemini(client=self.mock_client)

    def test_chamada_basica_devolve_resposta_ok(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake(
            "Ola, tudo bem?", tokens_in=120, tokens_out=40
        )

        resposta = self.adapter.chamar(
            modelo="gemini-3.5-flash-lite", esforco="medio",
            sistema="voce e util", contexto_fixo="",
            mensagens=[{"role": "user", "parts": [{"text": "oi"}]}],
            schema=None, max_tokens_saida=1024, cache={}, modo="padrao",
        )

        self.assertIsInstance(resposta, Resposta)
        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.texto, "Ola, tudo bem?")
        self.assertIsNone(resposta.dados)
        self.assertEqual(resposta.provedor, "gemini")
        self.assertEqual(resposta.modelo, "gemini-3.5-flash-lite")
        self.assertEqual(resposta.esforco, "medio")
        self.assertEqual(resposta.tokens_in, 120)
        self.assertEqual(resposta.tokens_out, 40)
        self.assertEqual(resposta.tokens_cache_lido, 0)
        self.assertEqual(resposta.tokens_cache_escrito, 0)
        self.assertGreaterEqual(resposta.latencia_ms, 0)
        self.assertFalse(resposta.fallback_usado)
        self.assertIsNone(resposta.erro)

    def test_max_tokens_saida_vira_max_output_tokens_na_chamada(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="gemini-pro", esforco="alto", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=777, cache={}, modo="padrao",
        )

        kwargs = self.mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs["generation_config"]["max_output_tokens"], 777)
        self.assertEqual(kwargs["model"], "gemini-pro")

    def test_sistema_e_contexto_fixo_montam_system_instruction(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="gemini-pro", esforco="baixo", sistema="voce e util",
            contexto_fixo="Contexto importante aqui",
            mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        kwargs = self.mock_client.models.generate_content.call_args.kwargs
        system_instr = kwargs["system_instruction"]
        self.assertIn("voce e util", system_instr)
        self.assertIn("Contexto importante aqui", system_instr)

    def test_resposta_sem_text_retorna_texto_vazio(self):
        resposta_vazia = SimpleNamespace(
            text="",
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                candidates_token_count=0,
                cached_content_input_token_count=0,
                cache_creation_input_token_count=0,
            ),
        )
        self.mock_client.models.generate_content.return_value = resposta_vazia

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="meio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.texto, "")


class TestErros(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.adapter = AdapterGemini(client=self.mock_client)

    def test_erro_de_conexao_sobe_como_excecao_com_retentavel(self):
        """Erro de rede/timeout DEVE subir com .retentavel = True pra que
        ia/core.py (faixa A1) saiba fazer retry."""
        exc = ConnectionError("Connection refused")
        self.mock_client.models.generate_content.side_effect = exc

        with self.assertRaises(ConnectionError) as ctx:
            self.adapter.chamar(
                modelo="gemini-pro", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertTrue(getattr(ctx.exception, "retentavel", False))

    def test_timeout_sobe_como_excecao(self):
        """Timeout tambem deve subir."""
        exc = TimeoutError("Request timeout")
        self.mock_client.models.generate_content.side_effect = exc

        with self.assertRaises(TimeoutError) as ctx:
            self.adapter.chamar(
                modelo="gemini-pro", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertTrue(getattr(ctx.exception, "retentavel", False))

    def test_erro_api_generico_vira_resposta_ok_false(self):
        """Erro da API (4xx/5xx equivalente no Gemini) vira Resposta(ok=False)."""
        exc = Exception("Invalid request or API error")
        exc.retentavel = False
        self.mock_client.models.generate_content.side_effect = exc

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertFalse(resposta.ok)
        self.assertEqual(resposta.provedor, "gemini")
        self.assertIn("Invalid request", resposta.erro)

    def test_google_genai_nao_instalado_retorna_resposta_erro(self):
        """Se google-genai nao estiver instalado, retorna erro claro."""
        adapter = AdapterGemini(client=None)  # Sem client injetado

        # Simula ImportError ao tentar importar genai
        with patch("builtins.__import__", side_effect=ImportError("No module named 'google.genai'")):
            resposta = adapter.chamar(
                modelo="gemini-pro", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertFalse(resposta.ok)
        self.assertIn("google-genai", resposta.erro)


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.adapter = AdapterGemini(client=self.mock_client)
        self.schema = {
            "type": "object",
            "properties": {
                "nome": {"type": "string"}
            },
            "required": ["nome"],
        }

    def test_schema_com_json_valido_extrai_dados(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake(
            '{"nome": "Alex"}'
        )

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.dados, {"nome": "Alex"})

    def test_schema_com_json_envolto_em_bloco_markdown_ainda_parseia(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake(
            '```json\n{"nome": "Alex"}\n```'
        )

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertEqual(resposta.dados, {"nome": "Alex"})

    def test_schema_com_json_invalido_nao_derruba_a_chamada(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake(
            "desculpe, nao consigo responder em JSON agora"
        )

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertIsNone(resposta.dados)
        self.assertIsNone(resposta.erro)

    def test_sem_schema_nunca_tenta_parsear_json(self):
        self.mock_client.models.generate_content.return_value = _resposta_fake(
            '{"nome": "Alex"}'
        )

        resposta = self.adapter.chamar(
            modelo="gemini-pro", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        # dados so e preenchido quando schema foi passado
        self.assertIsNone(resposta.dados)


class TestCustoUsd(unittest.TestCase):
    def test_sem_ia_precos_json_custo_fica_zero(self):
        mock_client = Mock()
        adapter = AdapterGemini(client=mock_client)
        mock_client.models.generate_content.return_value = _resposta_fake(
            "ok", tokens_in=1000, tokens_out=500
        )

        # Mocka ia.precos.custo_usd pra retornar 0.0 (modelo desconhecido ou arquivo ausente)
        with patch("ia.precos.custo_usd", return_value=0.0):
            resposta = adapter.chamar(
                modelo="gemini-pro", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertEqual(resposta.custo_usd, 0.0)


class TestClienteSemApiKey(unittest.TestCase):
    def test_construir_adapter_sem_env_var_nao_falha(self):
        # Regressao: instanciar o adapter nunca deve exigir GEMINI_API_KEY -
        # so falharia numa chamada real.
        with patch.dict(os.environ, {}, clear=False):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            adapter = AdapterGemini()
            self.assertIsNotNone(adapter)
            # Se injetarmos um client mock, ainda funciona
            adapter._client = Mock()
            adapter._client.models.generate_content.return_value = _resposta_fake("ok")
            resposta = adapter.chamar(
                modelo="gemini-pro", esforco="baixo", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
            self.assertTrue(resposta.ok)


class TestCriarAdapter(unittest.TestCase):
    def test_criar_adapter_devolve_instancia_utilizavel(self):
        # ia/core.py (faixa A1) descobre o adapter por criar_adapter() ou
        # pela classe AdapterGemini - as duas formas tem que funcionar.
        adapter = criar_adapter()
        self.assertIsInstance(adapter, AdapterGemini)

        # Injeta client mock pra nao tentar chamada real
        adapter._client = Mock()
        adapter._client.models.generate_content.return_value = _resposta_fake("ok")
        resposta = adapter.chamar(
            modelo="gemini-pro", esforco="baixo", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "parts": [{"text": "x"}]}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        self.assertTrue(resposta.ok)


if __name__ == "__main__":
    unittest.main()
