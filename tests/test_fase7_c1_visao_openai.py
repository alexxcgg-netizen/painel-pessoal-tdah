"""Fase 7 / C1 - historia 8: visao (A9) com `ativo: true` indo pro adapter
OpenAI. ia/funcoes/visao.py monta imagem/PDF no formato nativo da Anthropic;
o adapter OpenAI agora converte (image -> image_url, PDF -> file/file_data).
Cliente OpenAI e adapter Anthropic sao dubles - nenhuma chamada real."""
import base64
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import core  # noqa: E402
from ia.adapters.openai import AdapterOpenAI  # noqa: E402
from ia.contrato import Adapter, Resposta  # noqa: E402
from ia.funcoes import visao  # noqa: E402


class ClienteOpenAIFalso:
    def __init__(self, conteudo):
        self.chamadas = []
        self._conteudo = conteudo
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._conteudo))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20, prompt_tokens_details=None),
        )


class AnthropicFalso(Adapter):
    def __init__(self, texto):
        self.texto = texto
        self.chamadas = []

    def chamar(self, **kwargs):
        self.chamadas.append(kwargs)
        return Resposta(ok=True, texto=self.texto, provedor="anthropic", modelo=kwargs["modelo"])


def _json_nota(confianca=0.95):
    return json.dumps({"valor": 42.5, "estabelecimento": "Padaria Sintetica", "data": "2026-09-24",
                       "confianca": confianca})


def _json_cotacao():
    return json.dumps({"fornecedor": "Ferragens Sinteticas", "valor": 1200.0, "prazo_texto": "5 dias",
                       "observacao": None, "confianca": 0.9})


class _Base(unittest.TestCase):
    def setUp(self):
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)
        original = core._carregar_config

        def config_ativa(funcao):
            cfg = copy.deepcopy(original(funcao))
            if funcao in (visao.FUNCAO_NOTA_FISCAL, visao.FUNCAO_COTACAO_PDF):
                cfg["ativo"] = True
            return cfg

        for p in (patch.object(core, "_carregar_config", side_effect=config_ativa),
                  patch("ia.teto.teto_permite", return_value=True),
                  patch("ia.medicao.registrar_uso"),
                  patch.object(visao, "_registrar_adapter_anthropic_compartilhado")):
            p.start()
            self.addCleanup(p.stop)

    def _registrar(self, cliente_openai, anthropic):
        core.registrar_adapter("openai", lambda: AdapterOpenAI(cliente=cliente_openai))
        core.registrar_adapter("anthropic", lambda: anthropic)
        self.addCleanup(core.registrar_adapter, "openai", None)
        self.addCleanup(core.registrar_adapter, "anthropic", None)


class VisaoAtivaNoOpenAITestCase(_Base):
    def test_nota_fiscal_vai_como_image_url_data_uri(self):
        cliente = ClienteOpenAIFalso(_json_nota())
        anthropic = AnthropicFalso(_json_nota())
        self._registrar(cliente, anthropic)
        img = b"\x89PNG\r\n\x1a\nsintetico"
        dados, uso = visao.extrair_nota_fiscal_foto(img, "image/png")
        self.assertEqual(dados["estabelecimento"], "Padaria Sintetica")
        self.assertEqual(uso["model"], "gpt-6-luna")
        self.assertEqual(anthropic.chamadas, [])  # nao caiu no fallback
        partes = cliente.chamadas[0]["messages"][-1]["content"]
        imagem = next(p for p in partes if p["type"] == "image_url")
        self.assertEqual(imagem["image_url"]["url"],
                         "data:image/png;base64," + base64.standard_b64encode(img).decode())
        self.assertFalse(any("source" in p for p in partes))

    def test_cotacao_pdf_vai_como_file_data(self):
        cliente = ClienteOpenAIFalso(_json_cotacao())
        anthropic = AnthropicFalso(_json_cotacao())
        self._registrar(cliente, anthropic)
        pdf = b"%PDF-1.4 sintetico"
        dados, _ = visao.extrair_item_cotacao_pdf(pdf)
        self.assertEqual(dados["fornecedor"], "Ferragens Sinteticas")
        self.assertEqual(anthropic.chamadas, [])
        partes = cliente.chamadas[0]["messages"][-1]["content"]
        arquivo = next(p for p in partes if p["type"] == "file")
        self.assertEqual(arquivo["file"]["file_data"],
                         "data:application/pdf;base64," + base64.standard_b64encode(pdf).decode())
        self.assertEqual(arquivo["file"]["filename"], "documento.pdf")

    def test_anthropic_de_fallback_continua_recebendo_formato_nativo(self):
        cliente = ClienteOpenAIFalso("isso nao e json")
        anthropic = AnthropicFalso(_json_nota())
        self._registrar(cliente, anthropic)
        dados, _ = visao.extrair_nota_fiscal_foto(b"img", "image/jpeg")
        self.assertEqual(dados["valor"], 42.5)
        parte = anthropic.chamadas[0]["mensagens"][0]["content"][0]
        self.assertEqual(parte["type"], "image")
        self.assertEqual(parte["source"]["media_type"], "image/jpeg")


class ConversaoDoAdapterTestCase(unittest.TestCase):
    conv = staticmethod(AdapterOpenAI._converter_parte_conteudo)

    def test_formato_proprio_da_a3_continua(self):
        self.assertEqual(self.conv({"type": "image", "data_b64": "QUJD", "mime": "image/jpeg"}),
                         {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}})

    def test_texto_perde_cache_control(self):
        self.assertEqual(self.conv({"type": "text", "text": "oi", "cache_control": {"type": "ephemeral"}}),
                         {"type": "text", "text": "oi"})

    def test_documento_nao_pdf_ou_sem_base64_falha_claro(self):
        for parte in (
            {"type": "document", "source": {"type": "base64", "media_type": "text/plain", "data": "QQ=="}},
            {"type": "document", "source": {"type": "url", "url": "https://exemplo.com/x.pdf"}},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": None}},
        ):
            with self.subTest(parte=parte), self.assertRaises(ValueError):
                self.conv(parte)

    def test_falha_de_conversao_vira_resposta_nao_ok(self):
        cliente = ClienteOpenAIFalso("{}")
        resp = AdapterOpenAI(cliente=cliente).chamar(
            modelo="gpt-6-luna", esforco="medio", sistema="", contexto_fixo="",
            mensagens=[{"role": "user", "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "text/csv", "data": "QQ=="}}]}],
            schema=None, max_tokens_saida=10, cache={}, modo="padrao")
        self.assertFalse(resp.ok)
        self.assertIn("so PDF", resp.erro)
        self.assertEqual(cliente.chamadas, [])

    def test_parte_que_nao_e_dict_vira_texto(self):
        self.assertEqual(self.conv("solto"), {"type": "text", "text": "solto"})


if __name__ == "__main__":
    unittest.main()
