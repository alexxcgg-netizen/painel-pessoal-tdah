"""Testes de ia/adapters/anthropic.py (faixa A2). Mocka SOMENTE
client.messages.create (o SDK), nunca a rede de verdade - nenhum teste aqui
pode fazer uma chamada HTTP real. Cobre: chamada basica, cache ligado com
contexto grande o bastante, cache desligado/contexto pequeno (sem
cache_control), erro de conexao/timeout SOBE como excecao (retry e com o
ia/core.py, faixa A1), erro de status (4xx/5xx) vira Resposta(ok=False),
schema com JSON valido e invalido na resposta, e a descoberta do adapter via
criar_adapter()."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import anthropic

from ia.adapters.anthropic import AdapterAnthropic, criar_adapter
from ia.contrato import Resposta


def _resposta_fake(texto: str, *, tokens_in=100, tokens_out=50,
                    cache_lido=0, cache_escrito=0):
    """Monta um objeto com a MESMA forma do retorno de client.messages.create
    (so os campos que o adapter le: .content[].type/.text e .usage.*)."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        usage=SimpleNamespace(
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cache_read_input_tokens=cache_lido,
            cache_creation_input_tokens=cache_escrito,
        ),
    )


class TestChamadaBasica(unittest.TestCase):
    def setUp(self):
        self.adapter = AdapterAnthropic(client=Mock())

    def test_chamada_basica_devolve_resposta_ok(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            "Ola, tudo bem?", tokens_in=120, tokens_out=40
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="voce e util",
            contexto_fixo="", mensagens=[{"role": "user", "content": "oi"}],
            schema=None, max_tokens_saida=1024, cache={}, modo="padrao",
        )

        self.assertIsInstance(resposta, Resposta)
        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.texto, "Ola, tudo bem?")
        self.assertIsNone(resposta.dados)
        self.assertEqual(resposta.provedor, "anthropic")
        self.assertEqual(resposta.modelo, "claude-opus-5")
        self.assertEqual(resposta.esforco, "medio")
        self.assertEqual(resposta.tokens_in, 120)
        self.assertEqual(resposta.tokens_out, 40)
        self.assertEqual(resposta.tokens_cache_lido, 0)
        self.assertEqual(resposta.tokens_cache_escrito, 0)
        self.assertGreaterEqual(resposta.latencia_ms, 0)
        self.assertFalse(resposta.fallback_usado)
        self.assertIsNone(resposta.erro)

    def test_max_tokens_saida_vira_max_tokens_na_chamada(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="claude-sonnet-5", esforco="alto", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=777, cache={}, modo="padrao",
        )

        kwargs = self.adapter._client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 777)
        self.assertEqual(kwargs["model"], "claude-sonnet-5")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "x"}])

    def test_esforco_baixo_omite_thinking_mas_mantem_effort_low(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="claude-opus-5", esforco="baixo", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        kwargs = self.adapter._client.messages.create.call_args.kwargs
        self.assertNotIn("thinking", kwargs)
        self.assertEqual(kwargs["output_config"], {"effort": "low"})

    def test_esforco_medio_liga_thinking_adaptativo_e_mapeia_effort(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        kwargs = self.adapter._client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["thinking"], {"type": "adaptive"})
        self.assertEqual(kwargs["output_config"], {"effort": "medium"})

    def test_esforco_xhigh_e_max_passam_direto_sem_traducao(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        for esforco in ("xhigh", "max"):
            self.adapter.chamar(
                modelo="claude-opus-5", esforco=esforco, sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
            kwargs = self.adapter._client.messages.create.call_args.kwargs
            self.assertEqual(kwargs["output_config"], {"effort": esforco})

    def test_esforco_vazio_nao_manda_effort_nem_thinking(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        for esforco in ("", None):
            self.adapter.chamar(
                modelo="claude-sonnet-5", esforco=esforco, sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )
            kwargs = self.adapter._client.messages.create.call_args.kwargs
            self.assertNotIn("output_config", kwargs)
            self.assertNotIn("thinking", kwargs)

    def test_haiku_nunca_recebe_effort_nem_thinking(self):
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")

        self.adapter.chamar(
            modelo="claude-haiku-4-5-20251001", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        kwargs = self.adapter._client.messages.create.call_args.kwargs
        self.assertNotIn("output_config", kwargs)
        self.assertNotIn("thinking", kwargs)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.adapter = AdapterAnthropic(client=Mock())
        self.adapter._client.messages.create.return_value = _resposta_fake("ok")
        # >= CACHE_MIN_TOKENS_POR_MODELO["claude-opus-5"] (2048) * 4 chars/token
        self.contexto_grande = "a" * (2048 * 4 + 100)
        self.contexto_pequeno = "contexto curto demais pra cachear"

    def _system_blocks(self):
        kwargs = self.adapter._client.messages.create.call_args.kwargs
        return kwargs["system"]

    def test_cache_ativo_e_contexto_grande_marca_cache_control(self):
        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo=self.contexto_grande,
            mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100,
            cache={"ativo": True, "ttl": "1h"}, modo="padrao",
        )

        blocos = self._system_blocks()
        bloco_contexto = blocos[-1]
        self.assertEqual(bloco_contexto["text"], self.contexto_grande)
        self.assertEqual(
            bloco_contexto["cache_control"],
            {"type": "ephemeral", "ttl": "1h"},
        )

    def test_cache_ativo_usa_ttl_padrao_5m_quando_nao_informado(self):
        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo=self.contexto_grande,
            mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100,
            cache={"ativo": True}, modo="padrao",
        )

        bloco_contexto = self._system_blocks()[-1]
        self.assertEqual(bloco_contexto["cache_control"]["ttl"], "5m")

    def test_cache_desativado_nao_marca_cache_control_mesmo_com_contexto_grande(self):
        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo=self.contexto_grande,
            mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100,
            cache={"ativo": False}, modo="padrao",
        )

        bloco_contexto = self._system_blocks()[-1]
        self.assertNotIn("cache_control", bloco_contexto)

    def test_cache_ativo_mas_contexto_pequeno_nao_marca_cache_control(self):
        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo=self.contexto_pequeno,
            mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100,
            cache={"ativo": True}, modo="padrao",
        )

        bloco_contexto = self._system_blocks()[-1]
        self.assertNotIn("cache_control", bloco_contexto)

    def test_sem_contexto_fixo_nao_gera_bloco_de_contexto(self):
        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100,
            cache={"ativo": True}, modo="padrao",
        )

        blocos = self._system_blocks()
        self.assertEqual(len(blocos), 1)
        self.assertEqual(blocos[0]["text"], "sistema base")


class TestErroDeApi(unittest.TestCase):
    """Contrato (ajustado pelo nucleo A1): erro de rede/timeout do SDK SOBE
    como excecao (o ia/core.py so faz retry se a excecao subir) - o adapter
    NUNCA converte esses dois em Resposta(ok=False). Os demais erros do SDK
    (status HTTP 4xx/5xx) continuam virando Resposta(ok=False, erro=...)."""

    def setUp(self):
        self.adapter = AdapterAnthropic(client=Mock())

    def test_erro_de_conexao_sobe_como_excecao_marcada_retentavel(self):
        self.adapter._client.messages.create.side_effect = anthropic.APIConnectionError(
            message="falha de rede simulada", request=Mock()
        )

        with self.assertRaises(anthropic.APIConnectionError) as ctx:
            self.adapter.chamar(
                modelo="claude-opus-5", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertIn("falha de rede simulada", str(ctx.exception))
        self.assertTrue(ctx.exception.retentavel)

    def test_timeout_sobe_como_excecao_marcada_retentavel(self):
        # APITimeoutError e subclasse de APIConnectionError - precisa subir
        # igual, pro core conseguir dar retry num timeout de verdade.
        self.adapter._client.messages.create.side_effect = anthropic.APITimeoutError(
            request=Mock()
        )

        with self.assertRaises(anthropic.APITimeoutError) as ctx:
            self.adapter.chamar(
                modelo="claude-opus-5", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertIsInstance(ctx.exception, anthropic.APIConnectionError)
        self.assertTrue(ctx.exception.retentavel)

    def test_erro_de_status_vira_resposta_ok_false(self):
        response_fake = Mock()
        response_fake.headers = {}
        self.adapter._client.messages.create.side_effect = anthropic.RateLimitError(
            message="limite de taxa excedido", response=response_fake, body=None
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="baixo", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertFalse(resposta.ok)
        self.assertIn("limite de taxa excedido", resposta.erro)

    def test_excecao_generica_tambem_nao_sobe_crua(self):
        self.adapter._client.messages.create.side_effect = ValueError("bug qualquer")

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertFalse(resposta.ok)
        self.assertIn("bug qualquer", resposta.erro)


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.adapter = AdapterAnthropic(client=Mock())
        self.schema = {"type": "object", "properties": {"nome": {"type": "string"}}}

    def test_schema_adiciona_instrucao_no_sistema(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            '{"nome": "Alex"}'
        )

        self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        kwargs = self.adapter._client.messages.create.call_args.kwargs
        texto_sistema = kwargs["system"][0]["text"]
        self.assertIn("sistema base", texto_sistema)
        self.assertIn("JSON", texto_sistema)
        self.assertIn('"nome"', texto_sistema)

    def test_schema_com_json_valido_popula_dados(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            '{"nome": "Alex"}'
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertEqual(resposta.dados, {"nome": "Alex"})

    def test_schema_com_json_envolto_em_bloco_markdown_ainda_parseia(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            '```json\n{"nome": "Alex"}\n```'
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertEqual(resposta.dados, {"nome": "Alex"})

    def test_schema_com_json_invalido_nao_derruba_a_chamada(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            "desculpe, nao consigo responder em JSON agora"
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=self.schema, max_tokens_saida=100, cache={}, modo="padrao",
        )

        self.assertTrue(resposta.ok)
        self.assertIsNone(resposta.dados)
        self.assertIsNone(resposta.erro)

    def test_sem_schema_nunca_tenta_parsear_json(self):
        self.adapter._client.messages.create.return_value = _resposta_fake(
            '{"nome": "Alex"}'
        )

        resposta = self.adapter.chamar(
            modelo="claude-opus-5", esforco="medio", sistema="sistema base",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )

        # dados so e preenchido quando schema foi passado - mesmo com texto
        # que por acaso e JSON valido.
        self.assertIsNone(resposta.dados)


class TestCustoUsd(unittest.TestCase):
    def test_sem_ia_precos_json_custo_fica_zero(self):
        adapter = AdapterAnthropic(client=Mock())
        adapter._client.messages.create.return_value = _resposta_fake(
            "ok", tokens_in=1000, tokens_out=500
        )

        with patch("ia.adapters.anthropic.CAMINHO_PRECOS", "/caminho/que/nao/existe.json"):
            resposta = adapter.chamar(
                modelo="claude-opus-5", esforco="medio", sistema="s",
                contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
                schema=None, max_tokens_saida=100, cache={}, modo="padrao",
            )

        self.assertEqual(resposta.custo_usd, 0.0)


class TestClienteSemApiKey(unittest.TestCase):
    def test_construir_adapter_sem_env_var_nao_falha(self):
        # Regressao: instanciar o adapter (e portanto anthropic.Anthropic())
        # nunca deve exigir ANTHROPIC_API_KEY - so falharia numa chamada real.
        with patch.dict(os.environ, {}, clear=False):
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            adapter = AdapterAnthropic()
            self.assertIsNotNone(adapter)


class TestCriarAdapter(unittest.TestCase):
    def test_criar_adapter_devolve_instancia_utilizavel(self):
        # ia/core.py (faixa A1) descobre o adapter por criar_adapter() ou
        # pela classe AdapterAnthropic - as duas formas tem que funcionar.
        adapter = criar_adapter()
        self.assertIsInstance(adapter, AdapterAnthropic)

        adapter._client = Mock()
        adapter._client.messages.create.return_value = _resposta_fake("ok")
        resposta = adapter.chamar(
            modelo="claude-opus-5", esforco="baixo", sistema="s",
            contexto_fixo="", mensagens=[{"role": "user", "content": "x"}],
            schema=None, max_tokens_saida=100, cache={}, modo="padrao",
        )
        self.assertTrue(resposta.ok)


if __name__ == "__main__":
    unittest.main()
