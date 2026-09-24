# Testes da faixa A8 (Fase 7, Migracao 2 - planejamento): break_down_task,
# requebrar_tarefa, gerar_mala, resumir_link, plano_do_dia migrados pra
# ia.core.chamar_ia. Tudo com dubles: nenhuma chamada real de API, nenhuma
# credencial.
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ia import core
from ia.contrato import Adapter, Resposta
from ia.funcoes import planejamento as pl


def _resp(**sobrescrever):
    base = dict(
        ok=True, texto=None, dados=None, provedor="anthropic", modelo="claude-sonnet-5",
        esforco="", tokens_in=100, tokens_out=20, tokens_cache_lido=0,
        tokens_cache_escrito=0, custo_usd=0.00042, latencia_ms=10,
        fallback_usado=False, erro=None,
    )
    base.update(sobrescrever)
    return Resposta(**base)


class TestUsageDe(unittest.TestCase):
    def test_mapeia_campos_que_app_py_le(self):
        # app.py:359 _log_usage le usage["model"/"input_tokens"/"output_tokens"/"cost_usd"].
        resp = _resp(modelo="gpt-6-luna", tokens_in=50, tokens_out=9, custo_usd=0.001)
        usage = pl._usage_de(resp)
        self.assertEqual(
            usage, {"model": "gpt-6-luna", "input_tokens": 50, "output_tokens": 9, "cost_usd": 0.001}
        )


class TestFalhar(unittest.TestCase):
    def test_levanta_value_error_com_erro_do_nucleo(self):
        # app.py:411 _call_claude so pega (ValueError, KeyError) alem de anthropic.APIError -
        # com chamar_ia nunca sobe anthropic.APIError, entao precisa virar ValueError.
        with self.assertRaises(ValueError) as ctx:
            pl._falhar("break_down_task", _resp(ok=False, erro="teto_ia_estourado"))
        self.assertIn("teto_ia_estourado", str(ctx.exception))
        self.assertIn("break_down_task", str(ctx.exception))

    def test_erro_ausente_nao_quebra(self):
        with self.assertRaises(ValueError):
            pl._falhar("x", _resp(ok=False, erro=None))


class TestBreakDownTask(unittest.TestCase):
    def test_retorno_identico_ao_de_antes(self):
        resp = _resp(dados={"passos": ["abrir o arquivo", "escrever 1 paragrafo", "revisar"]})
        with patch.object(core, "chamar_ia", return_value=resp) as mock:
            resultado, usage = pl.break_down_task("Escrever relatorio")
        self.assertEqual(resultado, ["abrir o arquivo", "escrever 1 paragrafo", "revisar"])
        self.assertIsInstance(usage, dict)
        self.assertEqual(set(usage), {"model", "input_tokens", "output_tokens", "cost_usd"})
        mock.assert_called_once()
        args, kwargs = mock.call_args
        self.assertEqual(args[0], "break_down_task")
        self.assertEqual(kwargs["contexto_fixo"], pl.BREAKDOWN_PROMPT)
        self.assertEqual(kwargs["schema"], pl.SCHEMA_BREAKDOWN)
        self.assertIn("Escrever relatorio", args[1][0]["content"])
        self.assertEqual(args[1][0]["role"], "user")

    def test_falha_do_nucleo_vira_value_error(self):
        with patch.object(core, "chamar_ia", return_value=_resp(ok=False, erro="JSON fora do schema")):
            with self.assertRaises(ValueError):
                pl.break_down_task("Escrever relatorio")

    def test_schema_exige_passos_minimo_3_maximo_6(self):
        self.assertEqual(pl.SCHEMA_BREAKDOWN["properties"]["passos"]["minItems"], 3)
        self.assertEqual(pl.SCHEMA_BREAKDOWN["properties"]["passos"]["maxItems"], 6)
        self.assertEqual(pl.SCHEMA_BREAKDOWN["required"], ["passos"])


class TestRequebrarTarefa(unittest.TestCase):
    def test_retorno_identico_ao_de_antes(self):
        resp = _resp(dados={"passos": ["mandar 1 mensagem (2 min)", "separar material", "comecar"]})
        with patch.object(core, "chamar_ia", return_value=resp) as mock:
            resultado, usage = pl.requebrar_tarefa("Organizar armario", 5, ["passo velho 1", "passo velho 2"])
        self.assertEqual(resultado, ["mandar 1 mensagem (2 min)", "separar material", "comecar"])
        self.assertIsInstance(usage, dict)
        args, kwargs = mock.call_args
        self.assertEqual(args[0], "requebrar_tarefa")
        conteudo = args[1][0]["content"]
        self.assertIn("Organizar armario", conteudo)
        self.assertIn("5", conteudo)
        self.assertIn("passo velho 1", conteudo)
        self.assertIn("passo velho 2", conteudo)
        self.assertEqual(kwargs["contexto_fixo"], pl.REQUEBRAR_PROMPT)
        self.assertEqual(kwargs["schema"], pl.SCHEMA_REQUEBRAR)

    def test_passos_antigos_vazio_vira_nenhum(self):
        with patch.object(core, "chamar_ia", return_value=_resp(dados={"passos": ["x", "y", "z"]})) as mock:
            pl.requebrar_tarefa("Tarefa", 3, [])
        conteudo = mock.call_args[0][1][0]["content"]
        self.assertIn("nenhum", conteudo)

    def test_falha_do_nucleo_vira_value_error(self):
        with patch.object(core, "chamar_ia", return_value=_resp(ok=False, erro="rede fora")):
            with self.assertRaises(ValueError):
                pl.requebrar_tarefa("Tarefa", 3, [])


class TestGerarMala(unittest.TestCase):
    def test_retorno_identico_ao_de_antes(self):
        resp = _resp(dados={"itens": ["Documento", "Carregador", "3 mudas de roupa"]})
        with patch.object(core, "chamar_ia", return_value=resp) as mock:
            resultado, usage = pl.gerar_mala("Salvador", 4, "trabalho", "quente e seco")
        self.assertEqual(resultado, ["Documento", "Carregador", "3 mudas de roupa"])
        self.assertIsInstance(usage, dict)
        args, kwargs = mock.call_args
        self.assertEqual(args[0], "gerar_mala")
        conteudo = args[1][0]["content"]
        self.assertIn("Salvador", conteudo)
        self.assertIn("trabalho", conteudo)
        self.assertIn("quente e seco", conteudo)
        self.assertEqual(kwargs["contexto_fixo"], pl.MALA_PROMPT)
        self.assertEqual(kwargs["schema"], pl.SCHEMA_MALA)

    def test_motivo_e_clima_none_viram_texto_padrao(self):
        with patch.object(core, "chamar_ia", return_value=_resp(dados={"itens": ["x"]})) as mock:
            pl.gerar_mala("Recife", 2, None, None)
        conteudo = mock.call_args[0][1][0]["content"]
        self.assertIn("nao informado", conteudo)
        self.assertIn("sem previsao", conteudo)

    def test_falha_do_nucleo_vira_value_error(self):
        with patch.object(core, "chamar_ia", return_value=_resp(ok=False, erro="teto_ia_estourado")):
            with self.assertRaises(ValueError):
                pl.gerar_mala("Recife", 2, None, None)


class TestTruncarParaResumo(unittest.TestCase):
    def test_texto_curto_nao_muda(self):
        texto = "Um texto qualquer, bem curto."
        self.assertEqual(pl._truncar_para_resumo(texto), texto)

    def test_documenta_limite_de_12000(self):
        self.assertEqual(pl.LIMITE_TEXTO_RESUMO_LINK, 12_000)

    def test_corta_no_fim_de_frase_perto_do_limite(self):
        # Uma frase curta logo antes do limite, seguida de muito mais texto - o corte
        # deve parar no fim dessa frase (nao no meio da proxima).
        limite = 200
        antes = "Fato importante que fecha aqui. "
        resto = "x" * 5000
        texto = antes.ljust(limite - 40, "a") + antes + resto
        cortado = pl._truncar_para_resumo(texto, limite=limite)
        self.assertLessEqual(len(cortado), limite)
        self.assertTrue(cortado.endswith(".") or cortado.endswith(antes.strip()))
        self.assertNotIn("x" * 10, cortado)

    def test_sem_pontuacao_corta_seco_no_limite(self):
        texto = "a" * 500
        cortado = pl._truncar_para_resumo(texto, limite=100)
        self.assertEqual(len(cortado), 100)

    def test_nunca_ultrapassa_o_limite(self):
        for limite in (10, 50, 200, 1000):
            texto = ("Frase numero um. Frase numero dois. " * 200)
            cortado = pl._truncar_para_resumo(texto, limite=limite)
            self.assertLessEqual(len(cortado), limite)


class TestResumirLink(unittest.TestCase):
    def test_retorno_identico_ao_de_antes(self):
        resp = _resp(texto="- ponto 1\n- ponto 2")
        with patch.object(core, "chamar_ia", return_value=resp) as mock:
            resultado, usage = pl.resumir_link("Titulo da pagina", "Texto da pagina inteira.")
        self.assertEqual(resultado, "- ponto 1\n- ponto 2")
        self.assertIsInstance(usage, dict)
        args, kwargs = mock.call_args
        self.assertEqual(args[0], "resumir_link")
        self.assertIsNone(kwargs.get("schema"))  # resposta e texto livre, nao JSON
        self.assertEqual(kwargs["contexto_fixo"], pl.RESUMO_LINK_PROMPT)
        conteudo = args[1][0]["content"]
        self.assertIn("Titulo da pagina", conteudo)
        self.assertIn("Texto da pagina inteira.", conteudo)

    def test_titulo_none_vira_texto_padrao(self):
        with patch.object(core, "chamar_ia", return_value=_resp(texto="resumo")) as mock:
            pl.resumir_link(None, "texto qualquer")
        conteudo = mock.call_args[0][1][0]["content"]
        self.assertIn("sem titulo", conteudo)

    def test_texto_longo_e_truncado_antes_de_mandar(self):
        texto_grande = "Frase completa numero um. " * 1000  # bem acima de 12.000 chars
        self.assertGreater(len(texto_grande), pl.LIMITE_TEXTO_RESUMO_LINK)
        with patch.object(core, "chamar_ia", return_value=_resp(texto="resumo")) as mock:
            pl.resumir_link("T", texto_grande)
        conteudo = mock.call_args[0][1][0]["content"]
        # o texto mandado pro modelo (dentro do conteudo da mensagem) tem que ser bem
        # menor que o texto original - a prova de que o truncamento rodou antes da chamada.
        self.assertLess(len(conteudo), len(texto_grande))
        self.assertLessEqual(len(conteudo), pl.LIMITE_TEXTO_RESUMO_LINK + 200)  # + prefixo "Titulo:.../Texto:"

    def test_resposta_e_stripada(self):
        with patch.object(core, "chamar_ia", return_value=_resp(texto="  com espaco em volta  \n")):
            resultado, _ = pl.resumir_link("T", "texto")
        self.assertEqual(resultado, "com espaco em volta")

    def test_falha_do_nucleo_vira_value_error(self):
        with patch.object(core, "chamar_ia", return_value=_resp(ok=False, erro="pagina de login")):
            with self.assertRaises(ValueError):
                pl.resumir_link("T", "texto")


class TestPlanoDoDia(unittest.TestCase):
    def test_retorno_identico_ao_de_antes(self):
        resp = _resp(texto="1. Faca algo.\n2. Depois outra coisa.")
        eventos = [
            {"titulo": "Dentista", "inicio": "2026-09-24T14:00:00", "dia_inteiro": False},
            {"titulo": "Feriado", "inicio": "2026-09-24T00:00:00", "dia_inteiro": True},
        ]
        with patch.object(core, "chamar_ia", return_value=resp) as mock:
            resultado, usage = pl.plano_do_dia(["Lavar roupa"], eventos, ["gosta de comecar pelo mais dificil"])
        self.assertEqual(resultado, "1. Faca algo.\n2. Depois outra coisa.")
        self.assertIsInstance(usage, dict)
        args, kwargs = mock.call_args
        self.assertEqual(args[0], "plano_do_dia")
        self.assertIsNone(kwargs.get("schema"))
        self.assertEqual(kwargs["contexto_fixo"], pl.PLANO_PROMPT)
        conteudo = args[1][0]["content"]
        self.assertIn("Dentista as 14:00", conteudo)
        self.assertNotIn("Feriado", conteudo)  # dia inteiro nao entra na lista de horario fixo
        self.assertIn("Lavar roupa", conteudo)
        self.assertIn("gosta de comecar pelo mais dificil", conteudo)

    def test_sem_tarefa_nem_evento_nem_memoria(self):
        with patch.object(core, "chamar_ia", return_value=_resp(texto="Nada por hoje.")) as mock:
            pl.plano_do_dia([], [], None)
        conteudo = mock.call_args[0][1][0]["content"]
        self.assertIn("nenhum", conteudo)
        self.assertIn("nenhuma", conteudo)
        self.assertIn("nenhuma ainda", conteudo)

    def test_falha_do_nucleo_vira_value_error(self):
        with patch.object(core, "chamar_ia", return_value=_resp(ok=False, erro="teto_ia_estourado")):
            with self.assertRaises(ValueError):
                pl.plano_do_dia([], [], None)


class TestConfigsCarregam(unittest.TestCase):
    """ia/config.d/*.json das 5 funcoes: valida contra ia.core (nao so JSON
    valido - o formato normalizado que chamar_ia realmente usa)."""

    FUNCOES_ESPERADAS = {
        "gerar_mala": {"max_tokens_saida": 500, "modelo_atual": "claude-haiku-4-5-20251001"},
        "resumir_link": {"max_tokens_saida": 500, "modelo_atual": "claude-haiku-4-5-20251001"},
        "break_down_task": {"max_tokens_saida": 600, "modelo_atual": "claude-sonnet-5"},
        "requebrar_tarefa": {"max_tokens_saida": 600, "modelo_atual": "claude-sonnet-5"},
        "plano_do_dia": {"max_tokens_saida": 800, "modelo_atual": "claude-sonnet-5"},
    }

    def test_todas_carregam_sem_erro(self):
        core.limpar_cache()
        todas = core.carregar_todas_configs()
        for nome in self.FUNCOES_ESPERADAS:
            self.assertIn(nome, todas)

    def test_ativo_false_e_alvo_gpt_6_luna_medio(self):
        for nome in self.FUNCOES_ESPERADAS:
            cfg = core._carregar_config(nome)
            self.assertFalse(cfg["ativo"], nome)
            self.assertEqual(cfg["alvo"], {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"}, nome)

    def test_max_tokens_e_modelo_atual_batem_com_o_spec(self):
        for nome, esperado in self.FUNCOES_ESPERADAS.items():
            cfg = core._carregar_config(nome)
            self.assertEqual(cfg["max_tokens_saida"], esperado["max_tokens_saida"], nome)
            self.assertEqual(cfg["modelo_atual"]["modelo"], esperado["modelo_atual"], nome)
            self.assertEqual(cfg["modelo_atual"]["provedor"], "anthropic", nome)

    def test_fallback_conforme_o_pedido_na_faixa(self):
        for nome in ("gerar_mala", "resumir_link"):
            cfg = core._carregar_config(nome)
            self.assertEqual(
                cfg["fallback"], [{"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001", "esforco": ""}],
                nome,
            )
        for nome in ("break_down_task", "requebrar_tarefa", "plano_do_dia"):
            cfg = core._carregar_config(nome)
            self.assertEqual(
                cfg["fallback"], [{"provedor": "openai", "modelo": "gpt-6-sol", "esforco": "medio"}], nome
            )

    def test_funcao_de_ia_bate_com_nome_do_arquivo(self):
        # ia/core.py:97 exige isso - protege contra copia/cola errado entre os 5 arquivos.
        for arquivo in Path("ia/config.d").glob("*.json"):
            if arquivo.stem in self.FUNCOES_ESPERADAS:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                self.assertEqual(dados["funcao"], arquivo.stem)


class AdapterDuble(Adapter):
    """Adapter falso minimo (mesmo espirito do de tests/test_ia_core.py): consome uma fila
    de roteiros (Resposta ou excecao) e guarda os kwargs de cada chamada."""

    def __init__(self, roteiros=None):
        self.roteiros = list(roteiros or [])
        self.chamadas = []

    def chamar(self, **kwargs):
        self.chamadas.append(kwargs)
        roteiro = self.roteiros.pop(0) if self.roteiros else Resposta(ok=True, texto="ok")
        if isinstance(roteiro, BaseException):
            raise roteiro
        return roteiro


class TestIntegracaoComNucleoReal(unittest.TestCase):
    """Fim a fim (sem mockar core.chamar_ia) usando o ia/core.py de verdade e um
    adapter falso - prova que a config + o codigo de planejamento.py realmente se
    encaixam no contrato do nucleo (schema, fallback, teto), nao so que a funcao
    chama alguma coisa chamada chamar_ia."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Copia so as 5 configs desta faixa pro diretorio temporario de config do nucleo.
        origem = Path("ia/config.d")
        destino = Path(self.tmp.name)
        for nome in TestConfigsCarregam.FUNCOES_ESPERADAS:
            (destino / f"{nome}.json").write_text(
                (origem / f"{nome}.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
        patcher_dir = patch.object(core, "DIR_CONFIG", destino)
        patcher_dir.start()
        self.addCleanup(patcher_dir.stop)
        patcher_espera = patch.object(core, "ESPERA_RETRY_S", 0)
        patcher_espera.start()
        self.addCleanup(patcher_espera.stop)
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)

        self.anthropic = AdapterDuble()
        self.openai = AdapterDuble()
        core.registrar_adapter("anthropic", lambda: self.anthropic)
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        self.addCleanup(core.registrar_adapter, "openai", None)

        self.teto_ok = True
        medicao = types.ModuleType("ia.medicao")
        medicao.registrar_uso = lambda *a, **kw: None
        teto = types.ModuleType("ia.teto")
        teto.teto_permite = lambda funcao: self.teto_ok
        patcher_mods = patch.dict(sys.modules, {"ia.medicao": medicao, "ia.teto": teto})
        patcher_mods.start()
        self.addCleanup(patcher_mods.stop)

    def test_modelo_atual_anthropic_responde_hoje_ativo_false(self):
        # ativo=false -> usa modelo_atual (anthropic), nao o alvo (openai).
        self.anthropic.roteiros = [Resposta(ok=True, dados={"itens": ["Documento", "Carregador"]})]
        itens, usage = pl.gerar_mala("Fortaleza", 3, "ferias", "ensolarado")
        self.assertEqual(itens, ["Documento", "Carregador"])
        self.assertEqual(len(self.anthropic.chamadas), 1)
        self.assertEqual(len(self.openai.chamadas), 0)
        self.assertEqual(usage["model"], "claude-haiku-4-5-20251001")

    def test_teto_estourado_bloqueia_sem_chamar_nenhum_adapter(self):
        self.teto_ok = False
        with self.assertRaises(ValueError) as ctx:
            pl.gerar_mala("Fortaleza", 3, "ferias", "ensolarado")
        self.assertIn("teto_ia_estourado", str(ctx.exception))
        self.assertEqual(len(self.anthropic.chamadas), 0)
        self.assertEqual(len(self.openai.chamadas), 0)

    def test_fallback_de_break_down_task_quando_ativo(self):
        # Com ativo=true (simulado sobrescrevendo o arquivo), a principal (openai/alvo)
        # falha e cai pro fallback (openai/gpt-6-sol, conforme break_down_task.json).
        cfg_path = Path(core.DIR_CONFIG) / "break_down_task.json"
        dados = json.loads(cfg_path.read_text(encoding="utf-8"))
        dados["ativo"] = True
        cfg_path.write_text(json.dumps(dados), encoding="utf-8")

        self.openai.roteiros = [
            Resposta(ok=False, erro="rate limit"),  # tentativa 1: alvo gpt-6-luna
            Resposta(ok=True, dados={"passos": ["a", "b", "c"]}),  # tentativa 2: fallback gpt-6-sol
        ]
        passos, usage = pl.break_down_task("Organizar a garagem")
        self.assertEqual(passos, ["a", "b", "c"])
        self.assertEqual(len(self.openai.chamadas), 2)
        self.assertEqual(self.openai.chamadas[0]["modelo"], "gpt-6-luna")
        self.assertEqual(self.openai.chamadas[1]["modelo"], "gpt-6-sol")

    def test_json_fora_do_schema_falha_e_vira_value_error(self):
        # dados sem a chave "itens" -> nao bate o schema -> ok=False -> ValueError aqui.
        self.anthropic.roteiros = [Resposta(ok=True, dados={"coisas": ["x"]})]
        with self.assertRaises(ValueError):
            pl.gerar_mala("Recife", 2, None, None)

    def test_contexto_fixo_chega_identico_ao_adapter(self):
        self.anthropic.roteiros = [Resposta(ok=True, texto="resumo")]
        pl.resumir_link("T", "texto qualquer")
        self.assertEqual(self.anthropic.chamadas[0]["contexto_fixo"], pl.RESUMO_LINK_PROMPT)
        self.assertIsNone(self.anthropic.chamadas[0]["schema"])


if __name__ == "__main__":
    unittest.main()
