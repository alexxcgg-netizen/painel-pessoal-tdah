# Testes de scripts/ab_teste_ia.py (Fase 7, faixa A11). Tudo com --dry-run
# (dublês) - NENHUMA chamada real de API, nenhuma credencial necessaria.
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

import ab_teste_ia as ab  # noqa: E402
from ia import core  # noqa: E402


class BaseAB(unittest.TestCase):
    """Garante que nenhum teste vaza adapter/config registrado em ia.core
    (estado global do modulo) pro proximo teste - mesmo espirito de
    tests/test_ia_core.py."""

    def setUp(self):
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)
        for provedor in ("anthropic", "openai", "gemini"):
            self.addCleanup(core.registrar_adapter, provedor, None)
        # GEMINI_API_KEY nao deve vazar de/pra outros testes.
        self._gemini_key_original = os.environ.pop("GEMINI_API_KEY", None)
        self.addCleanup(self._restaurar_gemini_key)

    def _restaurar_gemini_key(self):
        if self._gemini_key_original is not None:
            os.environ["GEMINI_API_KEY"] = self._gemini_key_original
        else:
            os.environ.pop("GEMINI_API_KEY", None)


# ---------------------------------------------------------------------------
# Fixtures sinteticas: pelo menos 5 por funcao, formato valido
# ---------------------------------------------------------------------------

class TestFixturesSinteticas(BaseAB):
    def test_toda_funcao_tem_pelo_menos_5_fixtures_sinteticas(self):
        for funcao in ab.FUNCOES:
            fixtures = ab.carregar_fixtures_sinteticas(funcao)
            self.assertGreaterEqual(len(fixtures), 5, f"{funcao}: menos de 5 fixtures sinteticas")
            for fx in fixtures:
                self.assertIn("id", fx, f"{funcao}: fixture sem 'id'")
                self.assertIn("entrada", fx, f"{funcao}: fixture {fx.get('id')} sem 'entrada'")

    def test_funcao_sem_arquivo_de_fixture_devolve_lista_vazia(self):
        self.assertEqual(ab.carregar_fixtures_sinteticas("funcao_que_nao_existe"), [])

    def test_arquivo_de_fixture_que_nao_e_lista_da_erro_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "quebrada.json").write_text('{"nao": "e lista"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                ab.carregar_fixtures_sinteticas("quebrada", Path(tmp))


class TestFixturesReais(BaseAB):
    def test_arquivo_unico_e_pasta_sao_combinados(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "minha_funcao.json").write_text(
                json.dumps([{"id": "x1", "entrada": {"texto": "a"}}]), encoding="utf-8")
            pasta = base / "minha_funcao"
            pasta.mkdir()
            (pasta / "x2.json").write_text(
                json.dumps({"id": "x2", "entrada": {"texto": "b"}}), encoding="utf-8")
            fixtures = ab.carregar_fixtures_reais("minha_funcao", base)
            self.assertEqual({f["id"] for f in fixtures}, {"x1", "x2"})

    def test_imagem_path_e_convertido_pra_base64(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "foto.jpg").write_bytes(b"conteudo-fake-de-foto")
            (base / "extrair_nota_fiscal_foto.json").write_text(
                json.dumps([{"id": "real1", "entrada": {"imagem_path": "foto.jpg", "media_type": "image/jpeg"}}]),
                encoding="utf-8")
            fixtures = ab.carregar_fixtures_reais("extrair_nota_fiscal_foto", base)
            self.assertEqual(len(fixtures), 1)
            self.assertIn("imagem_b64", fixtures[0]["entrada"])
            import base64
            self.assertEqual(base64.standard_b64decode(fixtures[0]["entrada"]["imagem_b64"]),
                            b"conteudo-fake-de-foto")

    def test_carregar_fixtures_junta_sinteticas_e_reais(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "classify_intent.json").write_text(
                json.dumps([{"id": "real_extra", "entrada": {"texto": "oi"}, "esperado": {"acao": "consultar"}}]),
                encoding="utf-8")
            fixtures = ab.carregar_fixtures("classify_intent", base)
            ids = {f["id"] for f in fixtures}
            self.assertIn("real_extra", ids)
            self.assertGreaterEqual(len(fixtures), 6)  # 5+ sinteticas + 1 real

    def test_pasta_reais_ausente_nao_quebra(self):
        fixtures = ab.carregar_fixtures("classify_intent", Path("/tmp/isso-nao-existe-de-jeito-nenhum"))
        self.assertGreaterEqual(len(fixtures), 5)


# ---------------------------------------------------------------------------
# montar_<funcao>
# ---------------------------------------------------------------------------

class TestMontar(BaseAB):
    def test_montar_json_devolve_schema_e_mensagens(self):
        montado = ab.montar_classify_capture({"text": "gastei 10 reais"}, "anthropic")
        self.assertEqual(montado["schema"], ab.SCHEMA_CAPTURE)
        self.assertEqual(montado["mensagens"][0]["role"], "user")
        self.assertIn("gastei 10 reais", montado["mensagens"][0]["content"])

    def test_montar_texto_nao_tem_schema(self):
        montado = ab.montar_chat({"mensagem": "oi"}, "anthropic")
        self.assertIsNone(montado["schema"])

    def test_montar_nota_fiscal_formato_difere_por_provedor(self):
        entrada = {"imagem_b64": "QUJD", "media_type": "image/png"}
        anthropic_msg = ab.montar_nota_fiscal(entrada, "anthropic")["mensagens"][0]["content"][0]
        openai_msg = ab.montar_nota_fiscal(entrada, "openai")["mensagens"][0]["content"][0]
        self.assertIn("source", anthropic_msg)          # formato nativo Anthropic
        self.assertIn("data_b64", openai_msg)            # convencao do adapter A3

    def test_montar_cotacao_pdf_nao_suportado_pra_openai(self):
        with self.assertRaises(ab.NaoSuportado):
            ab.montar_cotacao_pdf({"pdf_b64": "QUJD"}, "openai")
        # anthropic funciona normalmente:
        montado = ab.montar_cotacao_pdf({"pdf_b64": "QUJD"}, "anthropic")
        self.assertEqual(montado["mensagens"][0]["content"][0]["type"], "document")


# ---------------------------------------------------------------------------
# avaliar_<funcao> (acerto)
# ---------------------------------------------------------------------------

class TestAvaliarAcerto(BaseAB):
    def test_classify_intent_acao_certa_e_errada(self):
        self.assertTrue(ab.avaliar_classify_intent({"acao": "consultar"}, None, {"acao": "consultar"}))
        self.assertFalse(ab.avaliar_classify_intent({"acao": "desconhecido"}, None, {"acao": "consultar"}))

    def test_classify_intent_sem_gabarito_e_none(self):
        self.assertIsNone(ab.avaliar_classify_intent({"acao": "consultar"}, None, {}))
        self.assertIsNone(ab.avaliar_classify_intent({"acao": "consultar"}, None, None))

    def test_classify_capture_compara_tipo_e_valor(self):
        self.assertTrue(ab.avaliar_classify_capture(
            {"tipo": "gasto", "valor": 45.0}, None, {"tipo": "gasto", "valor": 45}))
        self.assertFalse(ab.avaliar_classify_capture(
            {"tipo": "tarefa", "valor": None}, None, {"tipo": "gasto", "valor": 45}))
        self.assertFalse(ab.avaliar_classify_capture(
            {"tipo": "gasto", "valor": 999}, None, {"tipo": "gasto", "valor": 45}))

    def test_texto_contem_case_insensitive(self):
        self.assertTrue(ab.avaliar_texto_contem(None, "Tem CIMENTO nessa frase", {"contem": ["cimento"]}))
        self.assertFalse(ab.avaliar_texto_contem(None, "nada a ver", {"contem": ["cimento"]}))
        self.assertFalse(ab.avaliar_texto_contem(None, None, {"contem": ["cimento"]}))

    def test_lista_contem_verifica_qualquer_item(self):
        self.assertTrue(ab.avaliar_lista_contem(["Levar Passaporte", "Roupa"], None, {"contem": ["passaporte"]}))
        self.assertFalse(ab.avaliar_lista_contem(["Roupa", "Sapato"], None, {"contem": ["passaporte"]}))
        self.assertFalse(ab.avaliar_lista_contem("nao e lista", None, {"contem": ["x"]}))

    def test_tamanho_lista_dentro_e_fora_da_faixa(self):
        self.assertTrue(ab.avaliar_tamanho_lista(["a", "b", "c"], None, {"min": 3, "max": 6}))
        self.assertFalse(ab.avaliar_tamanho_lista(["a"], None, {"min": 3, "max": 6}))
        self.assertFalse(ab.avaliar_tamanho_lista(["a"] * 10, None, {"min": 3, "max": 6}))

    def test_escolher_essencial_compara_conjunto_de_ids(self):
        dados = [{"id": 1, "motivo": "x"}, {"id": 2, "motivo": "y"}]
        self.assertTrue(ab.avaliar_escolher_essencial(dados, None, {"ids": [2, 1]}))
        self.assertFalse(ab.avaliar_escolher_essencial(dados, None, {"ids": [3]}))

    def test_nota_fiscal_tolerancia_numerica_e_substring(self):
        dados = {"valor": 87.5, "estabelecimento": "Supermercado Bom Preco Ltda", "data": "2026-09-20"}
        self.assertTrue(ab.avaliar_nota_fiscal(dados, None, {"valor": 87.50, "estabelecimento": "bom preco"}))
        self.assertFalse(ab.avaliar_nota_fiscal(dados, None, {"valor": 999}))

    def test_cego_nunca_avalia(self):
        self.assertIsNone(ab.avaliar_cego({"qualquer": "coisa"}, "texto", {"campo": "valor"}))


# ---------------------------------------------------------------------------
# aplicar_simulacao (--dry-run)
# ---------------------------------------------------------------------------

class TestAplicarSimulacao(BaseAB):
    def test_sem_simulacao_devolve_original(self):
        texto, dados, falhou, mult, extra = ab.aplicar_simulacao("t", {"a": 1}, None)
        self.assertEqual((texto, dados, falhou, mult, extra), ("t", {"a": 1}, False, 1.0, 0))

    def test_api_falhou(self):
        texto, dados, falhou, mult, extra = ab.aplicar_simulacao("t", {"a": 1}, {"api_falhou": True})
        self.assertTrue(falhou)
        self.assertIsNone(texto)
        self.assertIsNone(dados)

    def test_json_invalido(self):
        texto, dados, falhou, _, _ = ab.aplicar_simulacao("{}", {"a": 1}, {"json_invalido": True})
        self.assertFalse(falhou)
        self.assertIsNone(dados)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(texto)

    def test_errar_campo(self):
        _, dados, _, _, _ = ab.aplicar_simulacao(
            "{}", {"tipo": "gasto"}, {"errar_campo": {"campo": "tipo", "valor": "tarefa"}})
        self.assertEqual(dados["tipo"], "tarefa")

    def test_ids_errados(self):
        _, dados, _, _, _ = ab.aplicar_simulacao(
            "[]", [{"id": 1, "motivo": "x"}], {"ids_errados": [999]})
        self.assertEqual([d["id"] for d in dados], [999])

    def test_sem_conteudo_esperado_lista_fica_generica_mas_valida(self):
        texto, dados, falhou, _, _ = ab.aplicar_simulacao(
            '["passaporte"]', ["passaporte"], {"sem_conteudo_esperado": True})
        self.assertFalse(falhou)
        self.assertNotIn("passaporte", [d.casefold() for d in dados])
        self.assertEqual(json.loads(texto), dados)  # continua JSON valido

    def test_custo_e_latencia_extra(self):
        _, _, _, mult, extra = ab.aplicar_simulacao(
            "t", None, {"custo_multiplicador": 3.0, "latencia_extra_ms": 500})
        self.assertEqual(mult, 3.0)
        self.assertEqual(extra, 500)


# ---------------------------------------------------------------------------
# avaliar_json (reaproveita core._extrair_json/core.validar_schema)
# ---------------------------------------------------------------------------

class TestAvaliarJson(BaseAB):
    def test_schema_none_e_nao_aplicavel(self):
        from ia.contrato import Resposta
        dados, valido = ab.avaliar_json(Resposta(ok=True, texto="oi"), None)
        self.assertIsNone(dados)
        self.assertIsNone(valido)

    def test_resposta_none_ou_nao_ok_e_invalida(self):
        from ia.contrato import Resposta
        schema = {"type": "object"}
        self.assertEqual(ab.avaliar_json(None, schema), (None, False))
        self.assertEqual(ab.avaliar_json(Resposta(ok=False, erro="x"), schema)[1], False)

    def test_json_valido_bate_schema(self):
        from ia.contrato import Resposta
        schema = {"type": "object", "required": ["a"]}
        dados, valido = ab.avaliar_json(Resposta(ok=True, texto='{"a": 1}'), schema)
        self.assertEqual(dados, {"a": 1})
        self.assertTrue(valido)

    def test_json_invalido_ou_fora_do_schema(self):
        from ia.contrato import Resposta
        schema = {"type": "object", "required": ["a"]}
        self.assertFalse(ab.avaliar_json(Resposta(ok=True, texto="nao e json"), schema)[1])
        self.assertFalse(ab.avaliar_json(Resposta(ok=True, texto='{"b": 1}'), schema)[1])

    def test_schema_com_raiz_lista_funciona(self):
        from ia.contrato import Resposta
        schema = {"type": "array", "items": {"type": "string"}}
        dados, valido = ab.avaliar_json(Resposta(ok=True, texto='["a", "b"]'), schema)
        self.assertEqual(dados, ["a", "b"])
        self.assertTrue(valido)


# ---------------------------------------------------------------------------
# Execucao ponta-a-ponta com --dry-run (nenhuma chamada real)
# ---------------------------------------------------------------------------

class TestExecutarDryRun(BaseAB):
    def test_nenhuma_chave_de_api_necessaria(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            resultado = ab.executar(dry_run=True, fixtures_reais_dir=None,
                                    funcoes_filtro=["classify_capture"])
        self.assertIn("classify_capture", resultado)

    def test_so_adapters_dublê_sao_instanciados_em_dry_run(self):
        ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        for adapter in core._CACHE_ADAPTERS.values():
            self.assertIsInstance(adapter, ab.AdapterDubleAB)

    def test_contexto_adapters_limpa_registro_ao_sair(self):
        ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        self.assertEqual(core._FABRICAS_REGISTRADAS, {})

    def test_funcoes_filtro_restringe_execucao(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"])
        self.assertEqual(set(resultado), {"chat"})

    def test_todas_as_funcoes_rodam_sem_excecao(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=None)
        self.assertEqual(set(resultado), set(ab.FUNCOES))
        for funcao, dados in resultado.items():
            for apelido, r in dados["resultados"].items():
                # todo item processado (considerado ou pulado) - nunca perdido
                self.assertEqual(len(r.itens), dados["total_fixtures"], funcao)

    def test_classify_capture_recomenda_luna_com_fixtures_padrao(self):
        # Sem simulacao_dry_run em classify_capture.json - luna deve sair
        # mais barata, 100% de acerto e JSON valido -> recomendado.
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        recs = resultado["classify_capture"]["recomendacoes"]
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0].recomendar)

    def test_escolher_essencial_simulacao_de_erro_derruba_recomendacao(self):
        # essencial_prazo_vencendo_hoje simula luna_medio errando o id -> acerto < 100%
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["escolher_essencial"])
        r_luna = resultado["escolher_essencial"]["resultados"]["luna_medio"]
        self.assertLess(r_luna.acerto_pct, 100)
        self.assertFalse(resultado["escolher_essencial"]["recomendacoes"][0].recomendar)

    def test_cotacao_pdf_luna_fica_pulado_no_relatorio(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None,
                                funcoes_filtro=["extrair_item_cotacao_pdf"])
        r_luna = resultado["extrair_item_cotacao_pdf"]["resultados"]["luna_medio"]
        self.assertEqual(r_luna.total, 0)
        self.assertEqual(r_luna.pulados, len(r_luna.itens))
        self.assertTrue(all(i.pulado for i in r_luna.itens))
        r_sonnet = resultado["extrair_item_cotacao_pdf"]["resultados"]["sonnet5_medio"]
        self.assertGreater(r_sonnet.total, 0)

    def test_falha_de_api_simulada_nao_conta_como_erro_de_acerto(self):
        # extrair_nota_fiscal_foto tem 1 fixture com luna_medio api_falhou=true
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None,
                                funcoes_filtro=["extrair_nota_fiscal_foto"])
        r_luna = resultado["extrair_nota_fiscal_foto"]["resultados"]["luna_medio"]
        self.assertEqual(r_luna.falhas, 1)
        # a falha fica de fora da media de acerto (so 4 itens avaliaveis, todos corretos)
        self.assertEqual(r_luna.acerto_pct, 100.0)

    def test_gemini_so_entra_com_env_var(self):
        sem_gemini = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_intent"])
        self.assertNotIn("gemini_flash_lite", sem_gemini["classify_intent"]["resultados"])

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key-de-teste"}):
            com_gemini = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_intent"])
        self.assertIn("gemini_flash_lite", com_gemini["classify_intent"]["resultados"])

    def test_seed_determina_embaralhamento_reprodutivel(self):
        r1 = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"], seed=7)
        r2 = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"], seed=7)
        ordem1 = [it["ordem"] for it in r1["chat"]["itens_cego"]]
        ordem2 = [it["ordem"] for it in r2["chat"]["itens_cego"]]
        self.assertEqual(ordem1, ordem2)


# ---------------------------------------------------------------------------
# Recomendacao
# ---------------------------------------------------------------------------

class ResultadoFalso:
    def __init__(self, rotulo, acerto_pct=None, json_valido_pct=None, custo_medio=None):
        self.rotulo = rotulo
        self.acerto_pct = acerto_pct
        self.json_valido_pct = json_valido_pct
        self.custo_medio = custo_medio


class TestRecomendacao(BaseAB):
    def _recomendar(self, base, cand):
        resultados = {"base": base, "cand": cand}
        return ab.avaliar_recomendacao("f", resultados, "base", "cand")

    def test_recomenda_quando_todos_criterios_batem(self):
        base = ResultadoFalso("Base", acerto_pct=80, json_valido_pct=100, custo_medio=0.01)
        cand = ResultadoFalso("Cand", acerto_pct=85, json_valido_pct=99.5, custo_medio=0.005)
        self.assertTrue(self._recomendar(base, cand).recomendar)

    def test_nao_recomenda_se_acerto_pior(self):
        base = ResultadoFalso("Base", acerto_pct=90, json_valido_pct=100, custo_medio=0.01)
        cand = ResultadoFalso("Cand", acerto_pct=70, json_valido_pct=100, custo_medio=0.005)
        self.assertFalse(self._recomendar(base, cand).recomendar)

    def test_nao_recomenda_se_json_valido_abaixo_de_98(self):
        base = ResultadoFalso("Base", acerto_pct=80, json_valido_pct=100, custo_medio=0.01)
        cand = ResultadoFalso("Cand", acerto_pct=90, json_valido_pct=97.9, custo_medio=0.005)
        self.assertFalse(self._recomendar(base, cand).recomendar)

    def test_nao_recomenda_se_custo_nao_cai(self):
        base = ResultadoFalso("Base", acerto_pct=80, json_valido_pct=100, custo_medio=0.005)
        cand = ResultadoFalso("Cand", acerto_pct=90, json_valido_pct=100, custo_medio=0.01)
        self.assertFalse(self._recomendar(base, cand).recomendar)

    def test_sem_nenhuma_metrica_medida_nao_recomenda(self):
        base = ResultadoFalso("Base")
        cand = ResultadoFalso("Cand")
        rec = self._recomendar(base, cand)
        self.assertFalse(rec.recomendar)

    def test_acerto_nao_medido_ainda_permite_recomendar_por_custo_e_json(self):
        base = ResultadoFalso("Base", json_valido_pct=100, custo_medio=0.01)
        cand = ResultadoFalso("Cand", json_valido_pct=99, custo_medio=0.005)
        rec = self._recomendar(base, cand)
        self.assertTrue(rec.recomendar)
        self.assertTrue(any("nao medido" in m for m in rec.motivos))


# ---------------------------------------------------------------------------
# Relatorio (HTML + gabarito separado)
# ---------------------------------------------------------------------------

class TestRelatorio(BaseAB):
    def test_gabarito_nunca_aparece_no_html_dos_itens_cego(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"])
        pagina, gabarito = ab.gerar_html(resultado, dry_run=True, gerado_em="2026-09-24")
        self.assertIn("chat", gabarito)
        for entrada in gabarito["chat"]:
            self.assertIn(entrada["A"], ("sonnet5_medio", "sol_medio"))
            self.assertIn(entrada["B"], ("sonnet5_medio", "sol_medio"))
            self.assertNotEqual(entrada["A"], entrada["B"])
        # nenhum apelido interno aparece cru no HTML (so os rotulos, na tabela agregada)
        self.assertNotIn("sonnet5_medio", pagina)
        self.assertNotIn("sol_medio", pagina)

    def test_gabarito_tem_uma_entrada_por_item_cego(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"])
        _, gabarito = ab.gerar_html(resultado, dry_run=True, gerado_em="agora")
        self.assertEqual(len(gabarito["chat"]), len(resultado["chat"]["itens_cego"]))

    def test_funcao_nao_cega_nao_entra_no_gabarito(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        _, gabarito = ab.gerar_html(resultado, dry_run=True, gerado_em="agora")
        self.assertNotIn("classify_capture", gabarito)

    def test_html_bem_formado_minimamente(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        pagina, _ = ab.gerar_html(resultado, dry_run=True, gerado_em="agora")
        self.assertTrue(pagina.startswith("<!DOCTYPE html>"))
        self.assertIn("<title>", pagina)
        self.assertIn("classify_capture", pagina)

    def test_entrada_com_html_e_escapada(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["chat"])
        # injeta um valor perigoso num item cego diretamente pra checar a fuga de HTML
        resultado["chat"]["itens_cego"][0]["entrada"] = {"mensagem": "<script>alert(1)</script>"}
        pagina, _ = ab.gerar_html(resultado, dry_run=True, gerado_em="agora")
        self.assertNotIn("<script>alert(1)</script>", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_escrever_relatorio_grava_dois_arquivos(self):
        resultado = ab.executar(dry_run=True, fixtures_reais_dir=None, funcoes_filtro=["classify_capture"])
        with tempfile.TemporaryDirectory() as tmp:
            caminho_html, caminho_gabarito = ab.escrever_relatorio(resultado, Path(tmp), dry_run=True)
            self.assertTrue(caminho_html.exists())
            self.assertTrue(caminho_gabarito.exists())
            dados_gabarito = json.loads(caminho_gabarito.read_text(encoding="utf-8"))
            self.assertIn("aviso", dados_gabarito)
            self.assertIn("gabarito", dados_gabarito)


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

class TestCLI(BaseAB):
    def test_main_dry_run_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp) / "saida"
            codigo = ab.main([
                "--dry-run", "--funcoes", "classify_capture,chat",
                "--saida", str(saida), "--fixtures-reais", str(Path(tmp) / "nao-existe"),
            ])
            self.assertEqual(codigo, 0)
            self.assertTrue((saida / "relatorio_ab.html").exists())
            self.assertTrue((saida / "relatorio_ab.gabarito.json").exists())

    def test_main_funcao_desconhecida_da_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            codigo = ab.main(["--dry-run", "--funcoes", "isso_nao_existe", "--saida", tmp])
            self.assertEqual(codigo, 2)

    def test_main_saida_padrao_usa_fixtures_reais(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixtures_reais = Path(tmp) / "fixtures_reais"
            codigo = ab.main(["--dry-run", "--funcoes", "chat", "--fixtures-reais", str(fixtures_reais)])
            self.assertEqual(codigo, 0)
            self.assertTrue((fixtures_reais / "relatorios_ab" / "relatorio_ab.html").exists())


if __name__ == "__main__":
    unittest.main()
