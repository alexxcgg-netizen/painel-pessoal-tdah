# Testes do nucleo de IA (ia/core.py, faixa A1). Tudo com dubles: nenhuma API
# real, nenhuma credencial, nenhum banco.
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ia import core
from ia.contrato import Adapter, Resposta


class AdapterDuble(Adapter):
    """Adapter falso: consome uma fila de 'roteiros' (Resposta ou excecao) e
    guarda os argumentos de cada chamada."""

    def __init__(self, provedor, roteiros=None):
        self.provedor = provedor
        self.roteiros = list(roteiros or [])
        self.chamadas = []

    def chamar(self, **kwargs):
        self.chamadas.append(kwargs)
        roteiro = self.roteiros.pop(0) if self.roteiros else Resposta(ok=True, texto="ok")
        if isinstance(roteiro, BaseException):
            raise roteiro
        return roteiro


class APIConnectionError(Exception):
    """Imita o nome da excecao de conexao dos SDKs anthropic/openai."""


def _config(**sobrescrever):
    base = {
        "funcao": "classify_capture",
        "ativo": False,
        "modelo_atual": {"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"},
        "alvo": {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"},
        "fallback": [{"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}],
        "max_tokens_saida": 300,
        "cache": {"ativo": False, "ttl": "5m"},
        "modo": "padrao",
    }
    base.update(sobrescrever)
    return base


SCHEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["tarefa", "gasto", "meta"]},
        "valor": {"type": ["number", "null"]},
    },
    "required": ["tipo"],
}


class BaseIACore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher_dir = patch.object(core, "DIR_CONFIG", Path(self.tmp.name))
        patcher_dir.start()
        self.addCleanup(patcher_dir.stop)
        patcher_espera = patch.object(core, "ESPERA_RETRY_S", 0)
        patcher_espera.start()
        self.addCleanup(patcher_espera.stop)
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)

        self.anthropic = AdapterDuble("anthropic")
        self.openai = AdapterDuble("openai")
        core.registrar_adapter("anthropic", lambda: self.anthropic)
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        self.addCleanup(core.registrar_adapter, "openai", None)

        # Medicao/teto falsos (ia.medicao e ia.teto sao da faixa A4).
        self.usos = []
        self.teto_ok = True
        medicao = types.ModuleType("ia.medicao")
        medicao.registrar_uso = lambda funcao, provedor, modelo, **kw: self.usos.append(
            {"funcao": funcao, "provedor": provedor, "modelo": modelo, **kw})
        teto = types.ModuleType("ia.teto")
        teto.teto_permite = lambda funcao: self.teto_ok
        patcher_mods = patch.dict(sys.modules, {"ia.medicao": medicao, "ia.teto": teto})
        patcher_mods.start()
        self.addCleanup(patcher_mods.stop)

    def escrever_config(self, nome="classify_capture", **sobrescrever):
        dados = _config(funcao=nome, **sobrescrever)
        (Path(self.tmp.name) / f"{nome}.json").write_text(json.dumps(dados), encoding="utf-8")
        return dados


class TestCarregarConfig(BaseIACore):
    def test_config_ausente_da_erro_claro(self):
        with self.assertRaises(core.ConfigIAErro) as ctx:
            core.chamar_ia("nao_existe", [{"role": "user", "content": "oi"}])
        self.assertIn("nao_existe", str(ctx.exception))
        self.assertIn("README", str(ctx.exception))

    def test_nome_invalido_nao_vira_caminho(self):
        for nome in ("../segredo", "Chat", "", "a/b", None):
            with self.assertRaises(core.ConfigIAErro):
                core._carregar_config(nome)

    def test_json_mal_formado(self):
        (Path(self.tmp.name) / "quebrada.json").write_text("{nao e json", encoding="utf-8")
        with self.assertRaises(core.ConfigIAErro):
            core._carregar_config("quebrada")

    def test_ativo_sem_alvo_e_erro(self):
        self.escrever_config(ativo=True, alvo=None)
        with self.assertRaises(core.ConfigIAErro):
            core._carregar_config("classify_capture")

    def test_funcao_diferente_do_arquivo(self):
        (Path(self.tmp.name) / "chat.json").write_text(
            json.dumps(_config(funcao="outra")), encoding="utf-8")
        with self.assertRaises(core.ConfigIAErro):
            core._carregar_config("chat")

    def test_campos_invalidos(self):
        casos = [
            {"max_tokens_saida": 0},
            {"max_tokens_saida": "300"},
            {"max_tokens_saida": True},
            {"fallback": {"provedor": "x"}},
            {"fallback": [{"provedor": "anthropic"}]},
            {"modelo_atual": {"provedor": "", "modelo": "x"}},
            {"ativo": "sim"},
            {"cache": []},
        ]
        for extra in casos:
            with self.subTest(extra=extra):
                core.limpar_cache()
                self.escrever_config(**extra)
                with self.assertRaises(core.ConfigIAErro):
                    core._carregar_config("classify_capture")

    def test_defaults_e_cache(self):
        arquivo = Path(self.tmp.name) / "minima.json"
        arquivo.write_text(json.dumps({
            "modelo_atual": {"provedor": "Anthropic", "modelo": "claude-haiku-4-5-20251001"}}))
        config = core._carregar_config("minima")
        self.assertEqual(config["modelo_atual"]["provedor"], "anthropic")
        self.assertEqual(config["fallback"], [])
        self.assertEqual(config["max_tokens_saida"], 1024)
        self.assertEqual(config["modo"], "padrao")
        self.assertFalse(config["cache"]["ativo"])
        self.assertIs(core._carregar_config("minima"), config)  # veio do cache

    def test_editar_arquivo_invalida_cache(self):
        self.escrever_config(ativo=False)
        self.assertFalse(core._carregar_config("classify_capture")["ativo"])
        arquivo = Path(self.tmp.name) / "classify_capture.json"
        self.escrever_config(ativo=True)
        mtime = arquivo.stat().st_mtime_ns + 1_000_000
        os.utime(arquivo, ns=(mtime, mtime))
        self.assertTrue(core._carregar_config("classify_capture")["ativo"])

    def test_carregar_todas_configs(self):
        self.escrever_config("classify_capture")
        self.escrever_config("chat")
        todas = core.carregar_todas_configs()
        self.assertEqual(sorted(todas), ["chat", "classify_capture"])


class TestRoteamento(BaseIACore):
    MSGS = [{"role": "user", "content": "gastei 30 no mercado"}]

    def test_inativo_usa_modelo_atual(self):
        self.escrever_config(ativo=False)
        resp = core.chamar_ia("classify_capture", self.MSGS, sistema="S", contexto_fixo="C")
        self.assertTrue(resp.ok)
        self.assertEqual(len(self.anthropic.chamadas), 1)
        self.assertEqual(self.openai.chamadas, [])
        chamada = self.anthropic.chamadas[0]
        self.assertEqual(chamada["modelo"], "claude-haiku-4-5-20251001")
        self.assertEqual(chamada["sistema"], "S")
        self.assertEqual(chamada["contexto_fixo"], "C")
        self.assertEqual(chamada["mensagens"], self.MSGS)
        self.assertEqual(chamada["max_tokens_saida"], 300)
        self.assertEqual(chamada["modo"], "padrao")
        self.assertEqual(chamada["cache"], {"ativo": False, "ttl": "5m"})
        self.assertIsNone(chamada["schema"])
        self.assertEqual(resp.provedor, "anthropic")
        self.assertFalse(resp.fallback_usado)

    def test_ativo_usa_alvo_com_esforco(self):
        self.escrever_config(ativo=True)
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(self.anthropic.chamadas, [])
        self.assertEqual(self.openai.chamadas[0]["modelo"], "gpt-6-luna")
        self.assertEqual(self.openai.chamadas[0]["esforco"], "medio")
        self.assertEqual((resp.provedor, resp.modelo, resp.esforco),
                         ("openai", "gpt-6-luna", "medio"))
        self.assertFalse(resp.fallback_usado)

    def test_opcoes_sobrescrevem_config(self):
        self.escrever_config()
        core.chamar_ia("classify_capture", self.MSGS,
                       opcoes={"max_tokens_saida": 50, "modo": "lote",
                               "cache": {"ativo": True, "ttl": "1h"}})
        chamada = self.anthropic.chamadas[0]
        self.assertEqual(chamada["max_tokens_saida"], 50)
        self.assertEqual(chamada["modo"], "lote")
        self.assertEqual(chamada["cache"], {"ativo": True, "ttl": "1h"})

    def test_registra_uso_com_tokens(self):
        self.escrever_config()
        self.anthropic.roteiros = [Resposta(ok=True, texto="x", tokens_in=10, tokens_out=5,
                                            tokens_cache_lido=3, custo_usd=0.002, latencia_ms=42)]
        core.chamar_ia("classify_capture", self.MSGS)
        self.assertEqual(len(self.usos), 1)
        uso = self.usos[0]
        self.assertEqual((uso["funcao"], uso["provedor"], uso["modelo"]),
                         ("classify_capture", "anthropic", "claude-haiku-4-5-20251001"))
        self.assertEqual((uso["tokens_in"], uso["tokens_out"], uso["tokens_cache_lido"]),
                         (10, 5, 3))
        self.assertEqual(uso["custo_usd"], 0.002)
        self.assertEqual(uso["latencia_ms"], 42)
        self.assertTrue(uso["ok"])
        self.assertNotIn("mensagens", uso)  # nunca conteudo

    def test_teto_estourado_nao_chama_ninguem(self):
        self.escrever_config()
        self.teto_ok = False
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertFalse(resp.ok)
        self.assertEqual(resp.erro, "teto_ia_estourado")
        self.assertEqual(self.anthropic.chamadas, [])
        self.assertEqual(self.usos, [])

    def test_ignorar_teto(self):
        self.escrever_config()
        self.teto_ok = False
        resp = core.chamar_ia("classify_capture", self.MSGS, opcoes={"ignorar_teto": True})
        self.assertTrue(resp.ok)

    def test_funciona_sem_medicao_e_sem_teto(self):
        # Faixa A4 ainda nao entregou: import falha, nucleo segue.
        self.escrever_config()
        with patch.dict(sys.modules, {"ia.medicao": None, "ia.teto": None}):
            resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)

    def test_medicao_quebrada_nao_derruba(self):
        self.escrever_config()
        quebrada = types.ModuleType("ia.medicao")
        quebrada.registrar_uso = lambda *a, **k: 1 / 0
        with patch.dict(sys.modules, {"ia.medicao": quebrada}):
            resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)


class TestFallback(BaseIACore):
    MSGS = [{"role": "user", "content": "oi"}]

    def test_ok_false_cai_no_fallback(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [Resposta(ok=False, erro="500 do provedor")]
        self.anthropic.roteiros = [Resposta(ok=True, texto="salvo pelo fallback")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.texto, "salvo pelo fallback")
        self.assertTrue(resp.fallback_usado)
        self.assertEqual(resp.provedor, "anthropic")
        self.assertEqual([u["ok"] for u in self.usos], [False, True])

    def test_excecao_nao_rede_cai_direto_no_fallback(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [ValueError("parametro invalido")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(len(self.openai.chamadas), 1)  # sem retry
        self.assertTrue(resp.fallback_usado)

    def test_fallback_em_ordem(self):
        self.escrever_config(ativo=True, fallback=[
            {"provedor": "anthropic", "modelo": "m1"},
            {"provedor": "anthropic", "modelo": "m2"},
        ])
        self.openai.roteiros = [Resposta(ok=False, erro="x")]
        self.anthropic.roteiros = [Resposta(ok=False, erro="y"), Resposta(ok=True, texto="m2")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual([c["modelo"] for c in self.anthropic.chamadas], ["m1", "m2"])
        self.assertEqual(resp.modelo, "m2")

    def test_tudo_falha_devolve_erro_sem_levantar(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [Resposta(ok=False, erro="caiu openai")]
        self.anthropic.roteiros = [Resposta(ok=False, erro="caiu anthropic")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertFalse(resp.ok)
        self.assertIn("caiu openai", resp.erro)
        self.assertIn("caiu anthropic", resp.erro)
        self.assertTrue(resp.fallback_usado)

    def test_fallback_igual_a_principal_nao_repete(self):
        # Exemplo do README: inativo, fallback == modelo_atual -> 1 chamada so.
        self.escrever_config(ativo=False)
        self.anthropic.roteiros = [Resposta(ok=False, erro="falhou")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertFalse(resp.ok)
        self.assertEqual(len(self.anthropic.chamadas), 1)
        self.assertFalse(resp.fallback_usado)

    def test_adapter_indisponivel_cai_no_fallback(self):
        self.escrever_config(ativo=True)
        core.registrar_adapter("openai", None)
        with patch.dict(core.MODULOS_ADAPTER, {"openai": "ia.adapters.nao_existe_ainda"}):
            resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertTrue(resp.fallback_usado)
        self.assertEqual(resp.provedor, "anthropic")

    def test_provedor_desconhecido(self):
        self.escrever_config(ativo=True, alvo={"provedor": "gemini", "modelo": "x"})
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertTrue(resp.fallback_usado)

    def test_adapter_devolve_tipo_errado(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [{"ok": True}]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertTrue(resp.fallback_usado)


class TestSchema(BaseIACore):
    MSGS = [{"role": "user", "content": "gastei 30"}]

    def test_json_valido_vira_dados(self):
        self.escrever_config()
        self.anthropic.roteiros = [Resposta(ok=True, texto='{"tipo": "gasto", "valor": 30}')]
        resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.dados, {"tipo": "gasto", "valor": 30})
        self.assertEqual(self.anthropic.chamadas[0]["schema"], SCHEMA)

    def test_cerca_markdown_tolerada(self):
        self.escrever_config()
        self.anthropic.roteiros = [Resposta(ok=True, texto='```json\n{"tipo": "tarefa"}\n```')]
        resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.dados, {"tipo": "tarefa"})

    def test_dados_ja_parseados_pelo_adapter(self):
        self.escrever_config()
        self.anthropic.roteiros = [Resposta(ok=True, dados={"tipo": "meta"})]
        resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.dados, {"tipo": "meta"})

    def test_json_invalido_cai_no_fallback(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [Resposta(ok=True, texto="claro! aqui vai: {tipo: gasto")]
        self.anthropic.roteiros = [Resposta(ok=True, texto='{"tipo": "gasto"}')]
        resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
        self.assertTrue(resp.ok)
        self.assertTrue(resp.fallback_usado)
        self.assertEqual(resp.dados, {"tipo": "gasto"})
        self.assertEqual([u["ok"] for u in self.usos], [False, True])

    def test_json_fora_do_schema_cai_no_fallback(self):
        self.escrever_config(ativo=True)
        casos = [
            '{"tipo": "outra coisa"}',        # enum
            '{"valor": 10}',                   # required
            '{"tipo": "gasto", "valor": "10"}',  # type
            '["tipo", "gasto"]',               # nao e objeto
            "",                                # vazio
        ]
        for texto in casos:
            with self.subTest(texto=texto):
                self.openai.roteiros = [Resposta(ok=True, texto=texto)]
                self.anthropic.roteiros = [Resposta(ok=True, texto='{"tipo": "tarefa"}')]
                resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
                self.assertTrue(resp.ok)
                self.assertTrue(resp.fallback_usado)
                self.assertEqual(resp.dados, {"tipo": "tarefa"})

    def test_json_invalido_em_todos_devolve_erro(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [Resposta(ok=True, texto="nao json")]
        self.anthropic.roteiros = [Resposta(ok=True, texto='{"tipo": 1}')]
        resp = core.chamar_ia("classify_capture", self.MSGS, schema=SCHEMA)
        self.assertFalse(resp.ok)
        self.assertIn("JSON", resp.erro)
        self.assertIsNone(resp.dados)

    def test_sem_schema_nao_valida(self):
        self.escrever_config()
        self.anthropic.roteiros = [Resposta(ok=True, texto="texto livre, nao JSON")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertIsNone(resp.dados)

    def test_validar_schema_subconjunto(self):
        v = core.validar_schema
        self.assertIsNone(v({"a": [1, 2]}, {"type": "object", "properties": {
            "a": {"type": "array", "items": {"type": "integer"}, "maxItems": 2}}}))
        self.assertIsNotNone(v({"a": [1, "x"]}, {"properties": {
            "a": {"items": {"type": "integer"}}}}))
        self.assertIsNotNone(v(True, {"type": "integer"}))  # bool nao e inteiro
        self.assertIsNotNone(v({"x": 1}, {"type": "object", "properties": {},
                                          "additionalProperties": False}))
        self.assertIsNotNone(v(-1, {"type": "number", "minimum": 0}))
        self.assertIsNotNone(v("", {"type": "string", "minLength": 1}))
        self.assertIsNone(v(None, {"type": ["string", "null"]}))
        self.assertIsNone(v("x", {"formato_desconhecido": 1}))


class TestRetryRede(BaseIACore):
    MSGS = [{"role": "user", "content": "oi"}]

    def test_timeout_tenta_de_novo_no_mesmo_modelo(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [TimeoutError("demorou"), Resposta(ok=True, texto="voltou")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.texto, "voltou")
        self.assertEqual(len(self.openai.chamadas), 2)
        self.assertEqual(self.anthropic.chamadas, [])
        self.assertFalse(resp.fallback_usado)
        self.assertEqual([u["ok"] for u in self.usos], [False, True])

    def test_erro_conexao_do_sdk_tenta_de_novo(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [APIConnectionError("reset"), Resposta(ok=True, texto="ok")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(len(self.openai.chamadas), 2)

    def test_so_um_retry_depois_fallback(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [ConnectionError("1"), ConnectionError("2"),
                                Resposta(ok=True, texto="nunca chega")]
        self.anthropic.roteiros = [Resposta(ok=True, texto="fallback")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(resp.texto, "fallback")
        self.assertEqual(len(self.openai.chamadas), 2)
        self.assertTrue(resp.fallback_usado)
        self.assertEqual([u["ok"] for u in self.usos], [False, False, True])

    def test_retentavel_marcado_pelo_adapter(self):
        self.escrever_config(ativo=True)
        erro = RuntimeError("429")
        erro.retentavel = True
        self.openai.roteiros = [erro, Resposta(ok=True, texto="ok")]
        resp = core.chamar_ia("classify_capture", self.MSGS)
        self.assertTrue(resp.ok)
        self.assertEqual(len(self.openai.chamadas), 2)

        nao = TimeoutError("nao repita")
        nao.retentavel = False
        self.openai.chamadas.clear()
        self.openai.roteiros = [nao]
        core.chamar_ia("classify_capture", self.MSGS)
        self.assertEqual(len(self.openai.chamadas), 1)

    def test_espera_antes_do_retry(self):
        self.escrever_config(ativo=True)
        self.openai.roteiros = [TimeoutError("x"), Resposta(ok=True)]
        with patch.object(core, "ESPERA_RETRY_S", 0.01), patch.object(core.time, "sleep") as dormir:
            core.chamar_ia("classify_capture", self.MSGS)
        dormir.assert_called_once_with(0.01)


class TestDescobertaAdapter(BaseIACore):
    """Como o nucleo acha o adapter de ia.adapters.<provedor> (faixas A2/A3)."""

    def _modulo(self, nome, **attrs):
        mod = types.ModuleType(nome)
        for k, v in attrs.items():
            if isinstance(v, type):
                v.__module__ = nome
            setattr(mod, k, v)
        return mod

    def _resolver(self, modulo):
        core.registrar_adapter("anthropic", None)
        core.limpar_cache()
        with patch.dict(sys.modules, {"ia.adapters.anthropic": modulo}):
            return core._obter_adapter("anthropic")

    def test_criar_adapter(self):
        duble = AdapterDuble("anthropic")
        mod = self._modulo("ia.adapters.anthropic", criar_adapter=lambda: duble)
        self.assertIs(self._resolver(mod), duble)

    def test_classe_por_nome(self):
        classe = type("AdapterAnthropic", (AdapterDuble,),
                      {"__init__": lambda self: AdapterDuble.__init__(self, "anthropic")})
        mod = self._modulo("ia.adapters.anthropic", AdapterAnthropic=classe)
        self.assertIsInstance(self._resolver(mod), classe)

    def test_unica_subclasse(self):
        classe = type("QualquerNome", (Adapter,), {"chamar": lambda self, **k: Resposta(ok=True)})
        mod = self._modulo("ia.adapters.anthropic", QualquerNome=classe)
        self.assertIsInstance(self._resolver(mod), classe)

    def test_modulo_sem_adapter(self):
        mod = self._modulo("ia.adapters.anthropic")
        with self.assertRaises(LookupError):
            self._resolver(mod)


class TestFuzz(BaseIACore):
    """Entradas estranhas nunca levantam excecao fora de ConfigIAErro."""

    def test_respostas_malucas(self):
        self.escrever_config(ativo=True)
        textos = ["", " ", "null", "0", "[]", "{}", '{"tipo": null}', "\x00" * 10,
                  "{" * 5000, '{"tipo": "gasto"' + " " * 100000, "```json```", "```",
                  '{"tipo": "gasto", "valor": NaN}', '{"tipo": "gasto", "valor": 1e999}',
                  "ç" * 1000, '{"tipo": "tarefa"}garbage']
        for texto in textos:
            with self.subTest(texto=texto[:30]):
                self.openai.roteiros = [Resposta(ok=True, texto=texto)]
                self.anthropic.roteiros = [Resposta(ok=True, texto=texto)]
                resp = core.chamar_ia("classify_capture", [], schema=SCHEMA)
                self.assertIsInstance(resp, Resposta)
                if resp.ok:
                    self.assertIsNone(core.validar_schema(resp.dados, SCHEMA))

    def test_excecoes_variadas(self):
        self.escrever_config(ativo=True)
        for exc in (KeyError("x"), MemoryError(), OSError("disco"), RecursionError(),
                    TimeoutError(), ConnectionResetError()):
            with self.subTest(exc=type(exc).__name__):
                self.openai.roteiros = [exc, exc]
                self.anthropic.roteiros = [exc, exc]
                resp = core.chamar_ia("classify_capture", [])
                self.assertFalse(resp.ok)
                self.assertTrue(resp.erro)

    def test_concorrencia(self):
        import threading
        self.escrever_config(ativo=True)
        self.openai.roteiros = []  # sempre ok
        falhas = []

        def rodar():
            for _ in range(20):
                try:
                    if not core.chamar_ia("classify_capture", []).ok:
                        falhas.append("nao ok")
                except Exception as e:  # noqa: BLE001
                    falhas.append(repr(e))
                core._CACHE_CONFIG.clear()

        threads = [threading.Thread(target=rodar) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(falhas, [])


if __name__ == "__main__":
    unittest.main()
