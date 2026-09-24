# Testes da faixa A9 (Fase 7): migracao de extrair_nota_fiscal_foto/
# extrair_item_cotacao_pdf pra ia.core.chamar_ia, e ia/lote.py.
#
# Nada aqui faz chamada real de API (nem Anthropic nem OpenAI): tudo com
# dublê. PDF/imagem sao gerados sinteticamente aqui embaixo (bytes pequenos,
# nunca lidos de disco).
#
# Sobre mockar o provedor "anthropic": ia.funcoes.visao registra, a cada
# chamada, um AdapterAnthropic(client=ia.legado.client) - ver docstring de
# ia/funcoes/visao.py (compat com tests/test_claude_client.py) - entao
# QUALQUER core.registrar_adapter("anthropic", ...) feito num setUp seria
# imediatamente sobrescrito pela propria funcao sob teste. Por isso os testes
# abaixo mockam o mesmo lugar que tests/test_claude_client.py sempre mockou:
# `ia.legado.client.messages.create` (patch.object). Ja pra "openai" (usado
# so no cenario ativo:true) o registrar_adapter normal funciona, porque
# ia.funcoes.visao nunca mexe no adapter openai.
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
os.environ.setdefault("OPENAI_API_KEY", "teste-fake")

from ia import core
from ia import lote
from ia.contrato import Adapter, Resposta
from ia.legado import client as _client_legado
import ia.funcoes.visao as visao


# --------------------------------------------------------------------------
# Fixtures sinteticas (nunca lidas de disco)
# --------------------------------------------------------------------------

def _pdf_sintetico() -> bytes:
    """PDF minimo, so pra existir como bytes - ninguem no caminho testado
    faz parsing de verdade do conteudo (vira base64 e vai pro "documento" da
    mensagem, que os dublês abaixo nunca abrem)."""
    return b"%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<< /Root 1 0 R >>\n%%EOF"


def _imagem_sintetica_png() -> bytes:
    """PNG de verdade, 2x2, gerado com Pillow (ja no .venv) - pequeno e
    sintetico, sem ler nada do disco."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _resp_texto(texto, model="claude-sonnet-5", in_tok=100, out_tok=20):
    """Mesmo formato que tests/test_claude_client.py usa pro SDK Anthropic
    (SimpleNamespace com .content/.model/.usage) - o que
    ia/adapters/anthropic.py consome direto de `client.messages.create`."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason="end_turn",
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _json_nota_fiscal(confianca=0.95, **overrides):
    dados = {"valor": 89.9, "estabelecimento": "Supermercado Bom Preco", "data": "2026-09-20",
              "confianca": confianca}
    dados.update(overrides)
    return json.dumps(dados)


def _json_cotacao(confianca=0.95, **overrides):
    dados = {"fornecedor": "Ferragens Silva", "valor": 4500.0, "prazo_texto": "15 dias uteis",
             "observacao": "frete incluso", "confianca": confianca}
    dados.update(overrides)
    return json.dumps(dados)


class AdapterDuble(Adapter):
    """Mesmo espirito do AdapterDuble de tests/test_ia_core.py (faixa A1):
    consome uma fila de Resposta/excecao e guarda os argumentos de cada
    chamada. Usado so pro provedor "openai" aqui (ver comentario no topo do
    arquivo sobre por que "anthropic" precisa de outra estrategia)."""

    def __init__(self, roteiros=None):
        self.roteiros = list(roteiros or [])
        self.chamadas = []

    def chamar(self, **kwargs):
        self.chamadas.append(kwargs)
        roteiro = self.roteiros.pop(0) if self.roteiros else Resposta(ok=True, texto="ok")
        if isinstance(roteiro, BaseException):
            raise roteiro
        return roteiro


class BaseA9(unittest.TestCase):
    """setUp comum: medicao/teto virados dublê (sem tocar banco nenhum - ver
    tests/test_ia_core.py, mesma tecnica), cache do ia.core limpo entre
    testes, e adapter "openai" registrado com um AdapterDuble por padrao
    (limpo no tearDown)."""

    def setUp(self):
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)

        self.usos = []
        self.teto_ok = True
        medicao_falso = types.ModuleType("ia.medicao")
        medicao_falso.registrar_uso = lambda funcao, provedor, modelo, **kw: self.usos.append(
            {"funcao": funcao, "provedor": provedor, "modelo": modelo, **kw})
        teto_falso = types.ModuleType("ia.teto")
        teto_falso.teto_permite = lambda funcao: self.teto_ok
        patcher_mods = patch.dict(sys.modules, {"ia.medicao": medicao_falso, "ia.teto": teto_falso})
        patcher_mods.start()
        self.addCleanup(patcher_mods.stop)

        self.openai = AdapterDuble()
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "openai", None)
        self.addCleanup(core.registrar_adapter, "anthropic", None)

    def _mock_anthropic(self, *respostas_ou_excecoes):
        """patch.object(ia.legado.client.messages, "create", ...) com uma
        fila de retornos/excecoes, um por chamada - mesma tecnica de
        tests/test_claude_client.py."""
        fila = list(respostas_ou_excecoes)

        def _create(**kwargs):
            self._chamadas_anthropic.append(kwargs)
            item = fila.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        self._chamadas_anthropic = []
        patcher = patch.object(_client_legado.messages, "create", side_effect=_create)
        patcher.start()
        self.addCleanup(patcher.stop)
        return self._chamadas_anthropic


# --------------------------------------------------------------------------
# Retorno identico (mesma assinatura/campos de hoje) + formato de mensagem
# --------------------------------------------------------------------------

class RetornoIdenticoTestCase(BaseA9):
    def test_extrai_nota_fiscal_retorna_tuple_dict_dict(self):
        chamadas = self._mock_anthropic(_resp_texto(_json_nota_fiscal()))
        dados, usage = visao.extrair_nota_fiscal_foto(_imagem_sintetica_png(), "image/png")

        self.assertEqual(dados["valor"], 89.9)
        self.assertEqual(dados["estabelecimento"], "Supermercado Bom Preco")
        self.assertEqual(dados["data"], "2026-09-20")
        self.assertEqual(usage["input_tokens"], 100)
        self.assertEqual(usage["output_tokens"], 20)
        self.assertIn("cost_usd", usage)
        self.assertEqual(usage["model"], "claude-sonnet-5")

        conteudo = chamadas[0]["messages"][0]["content"]
        blocos_imagem = [b for b in conteudo if b["type"] == "image"]
        self.assertEqual(len(blocos_imagem), 1)
        self.assertEqual(blocos_imagem[0]["source"]["media_type"], "image/png")
        self.assertEqual(blocos_imagem[0]["source"]["type"], "base64")

    def test_extrai_cotacao_pdf_retorna_tuple_dict_dict(self):
        chamadas = self._mock_anthropic(_resp_texto(_json_cotacao()))
        dados, usage = visao.extrair_item_cotacao_pdf(_pdf_sintetico())

        self.assertEqual(dados["fornecedor"], "Ferragens Silva")
        self.assertEqual(dados["valor"], 4500.0)
        self.assertEqual(dados["prazo_texto"], "15 dias uteis")
        self.assertEqual(usage["input_tokens"], 100)

        conteudo = chamadas[0]["messages"][0]["content"]
        blocos_doc = [b for b in conteudo if b["type"] == "document"]
        self.assertEqual(len(blocos_doc), 1)
        self.assertEqual(blocos_doc[0]["source"]["media_type"], "application/pdf")

    def test_campos_nulos_quando_ilegivel(self):
        self._mock_anthropic(_resp_texto(_json_nota_fiscal(
            valor=None, estabelecimento=None, data=None)))
        dados, _ = visao.extrair_nota_fiscal_foto(b"foto ilegivel", "image/jpeg")
        self.assertIsNone(dados["valor"])
        self.assertIsNone(dados["estabelecimento"])

    def test_media_types_imagem_validos_preservado(self):
        self.assertEqual(
            visao.MEDIA_TYPES_IMAGEM_VALIDOS,
            {"image/jpeg", "image/png", "image/webp", "image/heic"},
        )


# --------------------------------------------------------------------------
# Fallback por confianca baixa e por JSON invalido (config ativo:false real -
# modelo_atual == fallback[0] == anthropic/claude-sonnet-5, dedup pra 1
# tentativa por chamada; o "refaz" e a segunda chamada explicita de
# ia.funcoes.visao._chamar_com_retry)
# --------------------------------------------------------------------------

class FallbackConfiancaEJsonTestCase(BaseA9):
    def test_confianca_baixa_refaz_e_usa_segunda_resposta(self):
        chamadas = self._mock_anthropic(
            _resp_texto(_json_nota_fiscal(confianca=0.4)),   # 1a tentativa: baixa confianca
            _resp_texto(_json_nota_fiscal(confianca=0.92, estabelecimento="Padaria")),  # refeita
        )
        dados, _ = visao.extrair_nota_fiscal_foto(_imagem_sintetica_png(), "image/png")
        self.assertEqual(dados["estabelecimento"], "Padaria")
        self.assertEqual(dados["confianca"], 0.92)
        self.assertEqual(len(chamadas), 2)

    def test_json_invalido_refaz_e_usa_segunda_resposta(self):
        chamadas = self._mock_anthropic(
            _resp_texto("isso nao e json de jeito nenhum"),
            _resp_texto(_json_cotacao(confianca=0.9)),
        )
        dados, _ = visao.extrair_item_cotacao_pdf(_pdf_sintetico())
        self.assertEqual(dados["fornecedor"], "Ferragens Silva")
        self.assertEqual(len(chamadas), 2)

    def test_confianca_baixa_nas_duas_tentativas_levanta_erro(self):
        self._mock_anthropic(
            _resp_texto(_json_nota_fiscal(confianca=0.2)),
            _resp_texto(_json_nota_fiscal(confianca=0.3)),
        )
        with self.assertRaises(RuntimeError):
            visao.extrair_nota_fiscal_foto(_imagem_sintetica_png(), "image/png")

    def test_erro_tecnico_nas_duas_tentativas_levanta_erro(self):
        self._mock_anthropic(RuntimeError("timeout simulado"), RuntimeError("timeout simulado"))
        with self.assertRaises(RuntimeError):
            visao.extrair_item_cotacao_pdf(_pdf_sintetico())

    def test_confianca_no_limiar_nao_refaz(self):
        """confianca == CONFIANCA_MINIMA (0.7) passa no schema (minimum e
        inclusivo) - so 1 chamada."""
        chamadas = self._mock_anthropic(_resp_texto(_json_nota_fiscal(confianca=0.7)))
        dados, _ = visao.extrair_nota_fiscal_foto(_imagem_sintetica_png(), "image/png")
        self.assertEqual(dados["confianca"], 0.7)
        self.assertEqual(len(chamadas), 1)


# --------------------------------------------------------------------------
# Fallback automatico via config (ativo:true - alvo openai gpt-6-luna,
# fallback anthropic sonnet 5, dois modelos DISTINTOS: o schema com
# "confianca.minimum" faz o proprio ia.core cair pro fallback numa unica
# chamada de chamar_ia, sem precisar do retry explicito de visao.py)
# --------------------------------------------------------------------------

class FallbackAutomaticoDaConfigTestCase(BaseA9):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher_dir = patch.object(core, "DIR_CONFIG", Path(self._tmp.name))
        patcher_dir.start()
        self.addCleanup(patcher_dir.stop)
        self.addCleanup(core.limpar_cache)
        core.limpar_cache()

        config_migrada = {
            "funcao": "extrair_nota_fiscal_foto",
            "ativo": True,
            "modelo_atual": {"provedor": "anthropic", "modelo": "claude-sonnet-5"},
            "alvo": {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"},
            "fallback": [{"provedor": "anthropic", "modelo": "claude-sonnet-5"}],
            "max_tokens_saida": 500,
            "cache": {"ativo": False, "ttl": "5m"},
            "modo": "padrao",
        }
        (Path(self._tmp.name) / "extrair_nota_fiscal_foto.json").write_text(
            json.dumps(config_migrada), encoding="utf-8")

    def test_openai_com_confianca_baixa_cai_pro_fallback_sonnet_numa_chamada_so(self):
        # openai (dublê): confianca abaixo do minimo -> "fora do schema"
        # dentro do proprio ia.core, que passa pro proximo da lista (fallback
        # = anthropic/sonnet) sem visao.py precisar refazer nada.
        self.openai.roteiros = [
            Resposta(ok=True, dados={"valor": 10.0, "estabelecimento": "X", "data": None,
                                       "confianca": 0.3},
                      provedor="openai", modelo="gpt-6-luna"),
        ]
        chamadas_anthropic = self._mock_anthropic(
            _resp_texto(_json_nota_fiscal(confianca=0.95, estabelecimento="Mercado Certo")))

        dados, usage = visao.extrair_nota_fiscal_foto(_imagem_sintetica_png(), "image/png")

        self.assertEqual(dados["estabelecimento"], "Mercado Certo")
        self.assertEqual(usage["model"], "claude-sonnet-5")
        self.assertEqual(len(self.openai.chamadas), 1)
        self.assertEqual(len(chamadas_anthropic), 1)


# --------------------------------------------------------------------------
# Compat: o adapter "anthropic" usado por estas 2 funcoes tem que ser o MESMO
# client compartilhado (ia.legado.client) - e o que garante que
# tests/test_claude_client.py (que mocka esse client direto) continua
# passando sem eu editar aquele arquivo. Ver docstring de ia/funcoes/visao.py.
# --------------------------------------------------------------------------

class CompatClientCompartilhadoTestCase(BaseA9):
    def test_adapter_anthropic_registrado_usa_client_legado(self):
        core.registrar_adapter("anthropic", None)
        visao._registrar_adapter_anthropic_compartilhado()
        adapter = core._obter_adapter("anthropic")
        self.assertIs(adapter._client, _client_legado)


# --------------------------------------------------------------------------
# ia/lote.py: processar_lote sempre forca modo "flex"
# --------------------------------------------------------------------------

class ProcessarLoteTestCase(unittest.TestCase):
    def setUp(self):
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)
        medicao_falso = types.ModuleType("ia.medicao")
        medicao_falso.registrar_uso = lambda *a, **kw: None
        teto_falso = types.ModuleType("ia.teto")
        teto_falso.teto_permite = lambda funcao: True
        patcher_mods = patch.dict(sys.modules, {"ia.medicao": medicao_falso, "ia.teto": teto_falso})
        patcher_mods.start()
        self.addCleanup(patcher_mods.stop)

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher_dir = patch.object(core, "DIR_CONFIG", Path(self._tmp.name))
        patcher_dir.start()
        self.addCleanup(patcher_dir.stop)

        config = {
            "funcao": "extrair_item_cotacao_pdf",
            "ativo": False,
            "modelo_atual": {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"},
            "alvo": None,
            "fallback": [],
            "max_tokens_saida": 500,
            "cache": {"ativo": False, "ttl": "5m"},
            "modo": "padrao",
        }
        (Path(self._tmp.name) / "extrair_item_cotacao_pdf.json").write_text(
            json.dumps(config), encoding="utf-8")

        self.openai = AdapterDuble()
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "openai", None)

    def test_lote_forca_modo_flex_em_todos_os_itens(self):
        self.openai.roteiros = [
            Resposta(ok=True, texto="ok 1", provedor="openai", modelo="gpt-6-luna"),
            Resposta(ok=True, texto="ok 2", provedor="openai", modelo="gpt-6-luna"),
            Resposta(ok=True, texto="ok 3", provedor="openai", modelo="gpt-6-luna"),
        ]
        itens = [
            [{"role": "user", "content": "item 1"}],
            [{"role": "user", "content": "item 2"}],
            [{"role": "user", "content": "item 3"}],
        ]
        resultados = lote.processar_lote("extrair_item_cotacao_pdf", itens)

        self.assertEqual(len(resultados), 3)
        for (item, resp), chamada in zip(resultados, self.openai.chamadas):
            self.assertTrue(resp.ok)
            self.assertEqual(chamada["modo"], "flex")

    def test_modo_flex_sobrescreve_modo_passado_em_opcoes(self):
        self.openai.roteiros = [Resposta(ok=True, texto="ok", provedor="openai", modelo="gpt-6-luna")]
        lote.processar_lote(
            "extrair_item_cotacao_pdf",
            [[{"role": "user", "content": "item"}]],
            opcoes={"modo": "padrao"},
        )
        self.assertEqual(self.openai.chamadas[0]["modo"], "flex")

    def test_montar_mensagens_converte_item_bruto(self):
        self.openai.roteiros = [Resposta(ok=True, texto="ok", provedor="openai", modelo="gpt-6-luna")]
        itens_brutos = ["item-a"]
        lote.processar_lote(
            "extrair_item_cotacao_pdf",
            itens_brutos,
            montar_mensagens=lambda item: [{"role": "user", "content": f"convertido: {item}"}],
        )
        self.assertEqual(
            self.openai.chamadas[0]["mensagens"][0]["content"], "convertido: item-a")

    def test_um_item_falhando_nao_derruba_o_lote(self):
        self.openai.roteiros = [
            Resposta(ok=False, erro="quebrou", provedor="openai", modelo="gpt-6-luna"),
            Resposta(ok=True, texto="ok", provedor="openai", modelo="gpt-6-luna"),
        ]
        itens = [
            [{"role": "user", "content": "ruim"}],
            [{"role": "user", "content": "bom"}],
        ]
        resultados = lote.processar_lote("extrair_item_cotacao_pdf", itens)
        self.assertEqual(len(resultados), 2)
        self.assertFalse(resultados[0][1].ok)
        self.assertTrue(resultados[1][1].ok)

    def test_lote_vazio_devolve_lista_vazia(self):
        self.assertEqual(lote.processar_lote("extrair_item_cotacao_pdf", []), [])


if __name__ == "__main__":
    unittest.main()
