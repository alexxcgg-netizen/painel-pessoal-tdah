"""Fase 7 / C1 - historia 2: mensagens de erro de IA certas.

Antes: A7/A8/A9 levantavam ValueError (ou RuntimeError, na visao) em toda
falha de chamar_ia, entao rede e teto viravam "formato inesperado" (502) e a
visao virava 500 cru. Agora:
  teto estourado      -> TETO_IA_MSG (402)
  rede/provedor       -> CLAUDE_ERROR_MSG (502)
  JSON/schema ruim    -> CLAUDE_FORMAT_ERROR_MSG (502)
Tudo com adapter duble registrado no ia.core - nenhuma chamada real."""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from ia import core  # noqa: E402
from ia.contrato import Adapter, Resposta  # noqa: E402
from ia.funcoes import captura, planejamento, visao  # noqa: E402

PIN_TESTE = "123456"


class AdapterDuble(Adapter):
    """Devolve/levanta o que estiver em `roteiro` (um item por chamada; o
    ultimo se repete)."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = 0

    def chamar(self, **kwargs):
        self.chamadas += 1
        item = self.roteiro[min(self.chamadas - 1, len(self.roteiro) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item


class ClassificarFalhaTestCase(unittest.TestCase):
    def test_teto(self):
        self.assertEqual(core.classificar_falha("teto_ia_estourado"), "teto")
        self.assertEqual(core.classificar_falha("break_down_task: teto_ia_estourado"), "teto")

    def test_formato_so_quando_todas_as_tentativas_sao_de_formato(self):
        self.assertEqual(core.classificar_falha(
            "anthropic/x: JSON fora do schema ($: campo obrigatorio ausente 'passos')"), "formato")
        self.assertEqual(core.classificar_falha(
            "anthropic/x: JSON invalido na resposta (JSONDecodeError: a: b) | "
            "openai/y: resposta sem JSON (texto vazio)"), "formato")
        self.assertEqual(core.classificar_falha(
            "anthropic/x: JSON fora do schema (z) | openai/y: ConnectionError: caiu"), "provedor")

    def test_provedor_e_o_padrao(self):
        for erro in ("anthropic/x: APIConnectionError: timeout", "rate limit", "", None,
                     "nenhuma tentativa configurada", "x" * 10000, "|||", ": : :"):
            with self.subTest(erro=erro):
                self.assertEqual(core.classificar_falha(erro), "provedor")

    def test_excecoes_sao_valueerror_e_carregam_o_erro(self):
        for erro, classe in (("teto_ia_estourado", core.TetoEstourado),
                             ("anthropic/x: ReadTimeout: lento", core.ErroProvedor),
                             ("anthropic/x: JSON precisa ser objeto, veio list", core.RespostaInvalida)):
            with self.subTest(erro=erro):
                exc = core.excecao_de_resposta("f", Resposta(ok=False, erro=erro))
                self.assertIsInstance(exc, classe)
                self.assertIsInstance(exc, ValueError)
                self.assertIsInstance(exc, captura.ErroIA)  # compat A7
                self.assertIn(erro, str(exc))
                self.assertEqual(exc.erro, erro)

    def test_resposta_none(self):
        self.assertIsInstance(core.excecao_de_resposta("f", None), core.ErroProvedor)


class FuncoesLevantamExcecaoCertaTestCase(unittest.TestCase):
    def setUp(self):
        core.limpar_cache()
        self._espera = core.ESPERA_RETRY_S
        core.ESPERA_RETRY_S = 0
        self.addCleanup(setattr, core, "ESPERA_RETRY_S", self._espera)
        for mod, nome in ((captura, "_garantir_adapter_anthropic_legado"),
                          (visao, "_registrar_adapter_anthropic_compartilhado")):
            p = patch.object(mod, nome)
            p.start()
            self.addCleanup(p.stop)
        p = patch("ia.medicao.registrar_uso")
        p.start()
        self.addCleanup(p.stop)

    def _registrar(self, roteiro):
        adapter = AdapterDuble(roteiro)
        for provedor in ("anthropic", "openai", "gemini"):  # fallback tambem e duble
            core.registrar_adapter(provedor, lambda: adapter)
            self.addCleanup(core.registrar_adapter, provedor, None)
        return adapter

    def test_teto_vira_teto_estourado_sem_chamar_adapter(self):
        adapter = self._registrar([Resposta(ok=True, texto="{}")])
        with patch("ia.teto.teto_permite", return_value=False):
            with self.assertRaises(core.TetoEstourado):
                captura.classify_capture("comprar pao")
            with self.assertRaises(core.TetoEstourado):
                planejamento.break_down_task("arrumar a casa")
            with self.assertRaises(core.TetoEstourado):
                visao.extrair_nota_fiscal_foto(b"\x89PNG....", "image/png")
        self.assertEqual(adapter.chamadas, 0)

    def test_rede_vira_erro_provedor(self):
        self._registrar([ConnectionError("rede caiu")])
        with patch("ia.teto.teto_permite", return_value=True):
            with self.assertRaises(core.ErroProvedor):
                captura.classify_capture("comprar pao")
            with self.assertRaises(core.ErroProvedor):
                planejamento.gerar_mala("Recife", 2, None, None)
            with self.assertRaises(core.ErroProvedor):
                visao.extrair_item_cotacao_pdf(b"%PDF-1.4 sintetico")

    def test_json_ruim_vira_resposta_invalida(self):
        self._registrar([Resposta(ok=True, texto="isso nao e json")])
        with patch("ia.teto.teto_permite", return_value=True):
            with self.assertRaises(core.RespostaInvalida):
                planejamento.break_down_task("arrumar a casa")

    def test_visao_com_teto_nao_refaz(self):
        adapter = self._registrar([Resposta(ok=True, texto="{}")])
        with patch("ia.teto.teto_permite", return_value=False), \
                patch.object(core, "chamar_ia", wraps=core.chamar_ia) as chamar:
            with self.assertRaises(core.TetoEstourado):
                visao.extrair_nota_fiscal_foto(b"img", "image/png")
        self.assertEqual(chamar.call_count, 1)
        self.assertEqual(adapter.chamadas, 0)


class RotasTraduzemErroTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200

    def _captura_com(self, exc):
        with patch("claude_client.classify_capture", side_effect=exc):
            return self.client.post("/api/capture", json={"text": "comprar pao amanha xyz"})

    def test_capture_teto_402(self):
        res = self._captura_com(core.TetoEstourado("classify_capture: teto_ia_estourado"))
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.get_json()["error"], app.TETO_IA_MSG)

    def test_capture_rede_502_erro_de_ia(self):
        res = self._captura_com(core.ErroProvedor("classify_capture: anthropic/x: timeout"))
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.get_json()["error"], app.CLAUDE_ERROR_MSG)

    def test_capture_formato_502_formato(self):
        res = self._captura_com(core.RespostaInvalida("classify_capture: JSON fora do schema"))
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.get_json()["error"], app.CLAUDE_FORMAT_ERROR_MSG)

    def test_valueerror_generico_continua_formato(self):
        res = self._captura_com(ValueError("json quebrado"))
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.get_json()["error"], app.CLAUDE_FORMAT_ERROR_MSG)

    def test_nota_fiscal_falha_de_visao_nao_vira_500(self):
        img = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
        for exc, status in ((core.ErroProvedor("x"), 502), (core.RespostaInvalida("x"), 502),
                            (core.TetoEstourado("x"), 402)):
            with self.subTest(exc=type(exc).__name__), \
                    patch("claude_client.extrair_nota_fiscal_foto", side_effect=exc):
                res = self.client.post("/api/notas-fiscais/extrair",
                                       json={"imagem_base64": img, "media_type": "image/png"})
            self.assertEqual(res.status_code, status)

    def test_chat_teto_levantado_de_dentro_vira_402(self):
        with patch("claude_client.chat", side_effect=core.TetoEstourado("chat: teto_ia_estourado")):
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 402)

    def test_chat_erro_provedor_vira_502_erro_de_ia(self):
        with patch("claude_client.chat", side_effect=core.ErroProvedor("chat: caiu")):
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.get_json()["error"], app.CLAUDE_ERROR_MSG)

    def test_plano_dentro_do_chat_com_teto_nao_derruba_a_conversa(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["gerar_plano_do_dia"]({})
            self.assertEqual(resultado, {"erro": app.TETO_IA_MSG})
            return "Sem plano hoje, teto de IA.", ["gerar_plano_do_dia"], {
                "model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        with patch("claude_client.plano_do_dia", side_effect=core.TetoEstourado("x")), \
                patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "monta meu plano"})
        self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
