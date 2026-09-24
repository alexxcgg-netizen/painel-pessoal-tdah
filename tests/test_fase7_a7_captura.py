"""Faixa A7 (Migracao 1) - as 4 funcoes de ia/funcoes/captura.py que agora
chamam ia.core.chamar_ia (classify_intent, classify_capture, summarize_day,
escolher_essencial). Tudo com dubles - nenhuma chamada real de API, nenhuma
credencial, nenhum banco.

Duas camadas de teste:
- *TestCase com `patch("ia.funcoes.captura.chamar_ia")`: testa a logica de
  CADA funcao (formato de retorno, sanitizacao, resolver_data, usage,
  ErroIA) isolada do nucleo ia/core.py.
- ChamarIaIntegracaoTestCase: usa o ia/core.py de verdade (config
  temporaria, adapters dubles registrados via core.registrar_adapter, como
  tests/test_ia_core.py ja faz) pra provar que o schema explicito de cada
  funcao realmente valida contra o nucleo, e que o fallback entre
  provedores funciona fim-a-fim.
"""
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import core
from ia.contrato import Adapter, Resposta
import ia.funcoes.captura as captura


def _resp(dados=None, texto=None, modelo="claude-haiku-4-5-20251001",
          tokens_in=37, tokens_out=11, custo=0.00012):
    return Resposta(
        ok=True, texto=texto, dados=dados, provedor="anthropic", modelo=modelo,
        tokens_in=tokens_in, tokens_out=tokens_out, custo_usd=custo,
    )


def _resp_falha(erro="falha simulada"):
    return Resposta(ok=False, provedor="anthropic", modelo="claude-haiku-4-5-20251001", erro=erro)


class ClassifyIntentTestCase(unittest.TestCase):
    def test_formato_de_retorno_e_tupla_dict_usage(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "registrar_gasto", "confianca": 0.9, "parametros": {"valor": 50}}
        )) as mock_chamar:
            resultado, usage = captura.classify_intent("gastei 50 no mercado")
        self.assertIsInstance(resultado, dict)
        self.assertIsInstance(usage, dict)
        self.assertEqual(
            resultado,
            {"acao": "registrar_gasto", "confianca": 0.9, "parametros": {"valor": 50},
             "precisa_confirmacao": False},
        )
        self.assertEqual(usage, {"model": "claude-haiku-4-5-20251001", "input_tokens": 37,
                                  "output_tokens": 11, "cost_usd": 0.00012})
        mock_chamar.assert_called_once()
        self.assertEqual(mock_chamar.call_args.args[0], "classify_intent")
        self.assertEqual(mock_chamar.call_args.kwargs["schema"], captura.INTENT_SCHEMA)
        self.assertIn("contexto_fixo", mock_chamar.call_args.kwargs)

    FRASES_POR_ACAO = [
        ("lembra de ligar pro dentista", "registrar_tarefa", {"titulo": "Ligar pro dentista"}, 0.9),
        ("marca reuniao amanha as 10h", "registrar_tarefa", {"titulo": "Reuniao"}, 0.85),
        ("gastei 30 no lanche", "registrar_gasto", {"valor": 30}, 0.92),
        ("paguei 120 de luz", "registrar_gasto", {"valor": 120, "categoria": "contas"}, 0.9),
        ("minha energia hoje ta boa", "registrar_checkin", {}, 0.8),
        ("dormi mal essa noite", "registrar_checkin", {}, 0.75),
        ("abre os gastos", "navegar_tela", {"tela": "gastos"}, 0.9),
        ("mostra minhas metas", "navegar_tela", {"tela": "metas"}, 0.9),
        ("quanto eu gastei esse mes", "consultar", {"pergunta": "quanto gastou esse mes"}, 0.88),
        ("quantas tarefas eu tenho pendente", "consultar", {"pergunta": "tarefas pendentes"}, 0.85),
        ("nao, isso e gasto", "corrigir_ultimo", {}, 0.87),
        ("corrige pra tarefa", "corrigir_ultimo", {}, 0.86),
        ("bla bla bla sem sentido nenhum", "desconhecido", {}, 0.1),
        ("oi", "desconhecido", {}, 0.2),
        ("tanto faz", "desconhecido", {}, 0.15),
        ("vou pra viagem em 6 meses, tenho que juntar 3000", "registrar_tarefa", {}, 0.55),
        ("cade meu carro", "consultar", {"pergunta": "onde esta o carro"}, 0.6),
    ]

    def test_cada_frase_classifica_na_acao_certa(self):
        self.assertGreaterEqual(len(self.FRASES_POR_ACAO), 15)
        for texto, acao_esperada, parametros, confianca in self.FRASES_POR_ACAO:
            with self.subTest(texto=texto):
                with patch.object(captura, "chamar_ia", return_value=_resp(
                    {"acao": acao_esperada, "confianca": confianca, "parametros": parametros}
                )):
                    resultado, usage = captura.classify_intent(texto)
                self.assertEqual(resultado["acao"], acao_esperada)
                self.assertEqual(resultado["parametros"], parametros)
                self.assertEqual(usage["model"], "claude-haiku-4-5-20251001")

    def test_confianca_baixa_precisa_confirmacao_true(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "registrar_tarefa", "confianca": 0.3, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("texto ambiguo qualquer")
        self.assertTrue(resultado["precisa_confirmacao"])

    def test_confianca_alta_nao_precisa_confirmacao(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "registrar_gasto", "confianca": 0.95, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("gastei 30 no lanche")
        self.assertFalse(resultado["precisa_confirmacao"])

    def test_acao_fora_da_lista_fechada_vira_desconhecido(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "fazer_cafe", "confianca": 0.9, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("texto qualquer")
        self.assertEqual(resultado["acao"], "desconhecido")

    def test_confianca_fora_do_intervalo_e_limitada(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "consultar", "confianca": 5, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 1.0)

    def test_confianca_negativa_e_limitada_a_zero(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "consultar", "confianca": -3, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 0.0)

    def test_confianca_ausente_ou_tipo_errado_vira_zero(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "consultar", "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 0.0)
        self.assertTrue(resultado["precisa_confirmacao"])

    def test_confianca_booleana_nao_conta_como_numero(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "consultar", "confianca": True, "parametros": {}}
        )):
            resultado, _usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 0.0)

    def test_parametros_fora_do_tipo_dict_vira_vazio(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"acao": "consultar", "confianca": 0.9, "parametros": "nao e dict"}
        )):
            resultado, _usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["parametros"], {})

    def test_falha_da_ia_levanta_erroia_subclasse_de_valueerror(self):
        with patch.object(captura, "chamar_ia", return_value=_resp_falha("teto_ia_estourado")):
            with self.assertRaises(captura.ErroIA) as ctx:
                captura.classify_intent("qualquer coisa")
        self.assertIsInstance(ctx.exception, ValueError)
        self.assertIn("teto_ia_estourado", str(ctx.exception))

    def test_acoes_intent_e_a_lista_fechada_do_contrato(self):
        self.assertEqual(
            captura.ACOES_INTENT,
            ("registrar_tarefa", "registrar_gasto", "registrar_checkin", "navegar_tela",
             "consultar", "corrigir_ultimo", "desconhecido"),
        )

    def test_confianca_minima_intent_inalterada(self):
        self.assertEqual(captura.CONFIANCA_MINIMA_INTENT, 0.6)


class ClassifyCaptureTestCase(unittest.TestCase):
    def _dados(self, **sobrescrever):
        base = {"tipo": "tarefa", "titulo": "Ir ao dentista", "valor": None, "categoria": None,
                "status": None, "quando": None, "hora": None, "duvida": None, "memoria": None}
        base.update(sobrescrever)
        return base

    def test_formato_de_retorno_e_tupla_dict_usage(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(self._dados())) as mock_chamar:
            resultado, usage = captura.classify_capture("marca dentista")
        self.assertIsInstance(resultado, dict)
        self.assertIsInstance(usage, dict)
        self.assertEqual(set(usage), {"model", "input_tokens", "output_tokens", "cost_usd"})
        mock_chamar.assert_called_once()
        self.assertEqual(mock_chamar.call_args.args[0], "classify_capture")
        self.assertEqual(mock_chamar.call_args.kwargs["schema"], captura.CAPTURE_SCHEMA)

    def test_campos_que_app_py_consome_estao_todos_presentes(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(self._dados())):
            resultado, _usage = captura.classify_capture("marca dentista")
        for campo in ("tipo", "titulo", "valor", "categoria", "status", "quando",
                      "quando_data", "hora", "prazo", "duvida", "memoria"):
            self.assertIn(campo, resultado)

    def test_modelo_nao_manda_mais_quando_data_nem_prazo_no_schema(self):
        self.assertNotIn("quando_data", captura.CAPTURE_SCHEMA["properties"])
        self.assertNotIn("prazo", captura.CAPTURE_SCHEMA["properties"])

    def test_tarefa_com_quando_relativo_vira_quando_data_resolvida(self):
        from datetime import timedelta
        with patch.object(captura, "chamar_ia",
                           return_value=_resp(self._dados(quando="amanha"))):
            resultado, _usage = captura.classify_capture("marca dentista amanha")
        self.assertEqual(resultado["quando_data"], (date.today() + timedelta(days=1)).isoformat())
        self.assertIsNone(resultado["prazo"])

    def test_tarefa_com_hora_sem_dia_assume_hoje(self):
        with patch.object(captura, "chamar_ia",
                           return_value=_resp(self._dados(hora="14:00", quando=None))):
            resultado, _usage = captura.classify_capture("tenho consulta as 14h")
        self.assertEqual(resultado["quando_data"], date.today().isoformat())

    def test_tarefa_sem_quando_nem_hora_fica_sem_data(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(self._dados())):
            resultado, _usage = captura.classify_capture("estudar python")
        self.assertIsNone(resultado["quando_data"])

    def test_meta_usa_quando_como_prazo_nao_como_quando_data(self):
        dados = self._dados(tipo="meta", titulo="Viagem", valor=3000.0, quando="em 6 meses")
        with patch.object(captura, "chamar_ia", return_value=_resp(dados)):
            resultado, _usage = captura.classify_capture("quero juntar 3000 pra viagem em 6 meses")
        self.assertIsNone(resultado["quando_data"])
        self.assertIsNotNone(resultado["prazo"])

    def test_gasto_nao_calcula_data_nenhuma(self):
        dados = self._dados(tipo="gasto", titulo="Mercado", valor=40.0, categoria="mercado",
                             status="real")
        with patch.object(captura, "chamar_ia", return_value=_resp(dados)):
            resultado, _usage = captura.classify_capture("gastei 40 no mercado")
        self.assertIsNone(resultado["quando_data"])
        self.assertIsNone(resultado["prazo"])

    def test_duvida_passa_direto(self):
        dados = self._dados(duvida="Isso e gasto ou meta?")
        with patch.object(captura, "chamar_ia", return_value=_resp(dados)):
            resultado, _usage = captura.classify_capture("juntar uma grana")
        self.assertEqual(resultado["duvida"], "Isso e gasto ou meta?")

    def test_memoria_passa_direto(self):
        dados = self._dados(memoria="Esposa se chama Ana")
        with patch.object(captura, "chamar_ia", return_value=_resp(dados)):
            resultado, _usage = captura.classify_capture("minha esposa Ana pediu pra eu lembrar")
        self.assertEqual(resultado["memoria"], "Esposa se chama Ana")

    def test_contexto_correcao_none_vira_texto_padrao_na_mensagem(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(self._dados())) as mock_chamar:
            captura.classify_capture("marca dentista", contexto_correcao=None)
        mensagem = mock_chamar.call_args.args[1][0]["content"]
        self.assertIn("nenhuma correcao parecida no historico", mensagem)

    def test_contexto_correcao_presente_vai_na_mensagem(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(self._dados())) as mock_chamar:
            captura.classify_capture("marca dentista", contexto_correcao="corrigido pra tarefa antes")
        mensagem = mock_chamar.call_args.args[1][0]["content"]
        self.assertIn("corrigido pra tarefa antes", mensagem)

    def test_falha_da_ia_levanta_erroia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp_falha("rede fora")):
            with self.assertRaises(captura.ErroIA):
                captura.classify_capture("qualquer coisa")


class SummarizeDayTestCase(unittest.TestCase):
    def test_formato_de_retorno_e_texto_com_strip(self):
        with patch.object(captura, "chamar_ia",
                           return_value=_resp(texto="  Dia tranquilo, sem gastos.  \n")) as mock_chamar:
            texto, usage = captura.summarize_day(["a"], ["b"], [])
        self.assertEqual(texto, "Dia tranquilo, sem gastos.")
        self.assertIsInstance(usage, dict)
        self.assertEqual(mock_chamar.call_args.args[0], "summarize_day")
        self.assertIsNone(mock_chamar.call_args.kwargs["schema"])

    def test_texto_none_vira_string_vazia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(texto=None)):
            texto, _usage = captura.summarize_day([], [], [])
        self.assertEqual(texto, "")

    def test_listas_vazias_nao_quebram(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(texto="ok")) as mock_chamar:
            captura.summarize_day([], [], [], eventos=None, memorias=None, saude=None,
                                   construtora=None, clima=None)
        mensagem = mock_chamar.call_args.args[1][0]["content"]
        self.assertIn("nenhuma", mensagem)

    def test_falha_da_ia_levanta_erroia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp_falha()):
            with self.assertRaises(captura.ErroIA):
                captura.summarize_day([], [], [])


class EscolherEssencialTestCase(unittest.TestCase):
    TAREFAS = [
        {"id": 1, "title": "Pagar boleto", "due_date": "2026-09-24", "hora": None},
        {"id": 2, "title": "Ler livro", "due_date": None, "hora": None},
    ]

    def test_formato_de_retorno_e_lista_de_dicts(self):
        with patch.object(captura, "chamar_ia", return_value=_resp(
            {"escolhas": [{"id": 1, "motivo": "prazo hoje"}]}
        )) as mock_chamar:
            escolhas, usage = captura.escolher_essencial(self.TAREFAS)
        self.assertEqual(escolhas, [{"id": 1, "motivo": "prazo hoje"}])
        self.assertIsInstance(usage, dict)
        self.assertEqual(mock_chamar.call_args.args[0], "escolher_essencial")
        self.assertEqual(mock_chamar.call_args.kwargs["schema"], captura.ESSENCIAL_SCHEMA)

    def test_escolhas_vazia_e_lista_vazia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp({"escolhas": []})):
            escolhas, _usage = captura.escolher_essencial(self.TAREFAS)
        self.assertEqual(escolhas, [])

    def test_escolhas_com_tipo_errado_no_json_vira_lista_vazia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp({"escolhas": "nao e lista"})):
            escolhas, _usage = captura.escolher_essencial(self.TAREFAS)
        self.assertEqual(escolhas, [])

    def test_lista_de_tarefas_vazia_nao_quebra_a_montagem_da_mensagem(self):
        with patch.object(captura, "chamar_ia", return_value=_resp({"escolhas": []})) as mock_chamar:
            captura.escolher_essencial([])
        mensagem = mock_chamar.call_args.args[1][0]["content"]
        self.assertIn("Tarefas (id", mensagem)

    def test_falha_da_ia_levanta_erroia(self):
        with patch.object(captura, "chamar_ia", return_value=_resp_falha()):
            with self.assertRaises(captura.ErroIA):
                captura.escolher_essencial(self.TAREFAS)


class UsageDeRespostaTestCase(unittest.TestCase):
    def test_mapeia_campos_da_resposta_pro_dict_que_app_py_espera(self):
        resp = Resposta(ok=True, provedor="openai", modelo="gpt-6-luna", tokens_in=123,
                         tokens_out=45, custo_usd=0.0099)
        self.assertEqual(
            captura._usage_de(resp),
            {"model": "gpt-6-luna", "input_tokens": 123, "output_tokens": 45, "cost_usd": 0.0099},
        )


# ----------------------------------------------------------------------------
# Integracao com o ia/core.py de verdade: config temporaria + adapters dubles
# (mesmo padrao de tests/test_ia_core.py), pra provar schema/fallback fim-a-fim.
# ----------------------------------------------------------------------------

class AdapterDuble(Adapter):
    def __init__(self, roteiros=None):
        self.roteiros = list(roteiros or [])
        self.chamadas = []

    def chamar(self, **kwargs):
        self.chamadas.append(kwargs)
        roteiro = self.roteiros.pop(0) if self.roteiros else Resposta(ok=True, texto="ok")
        if isinstance(roteiro, BaseException):
            raise roteiro
        return roteiro


class ChamarIaIntegracaoTestCase(unittest.TestCase):
    """Nao mocka captura.chamar_ia - deixa rodar ia/core.py de verdade contra
    uma config temporaria, com adapters dubles. Confirma que o schema de cada
    funcao (definido em ia/funcoes/captura.py) realmente reprova JSON fora do
    formato, e que o fallback entre provedores funciona."""

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

        self.anthropic = AdapterDuble()
        self.openai = AdapterDuble()
        core.registrar_adapter("anthropic", lambda: self.anthropic)
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        self.addCleanup(core.registrar_adapter, "openai", None)

        medicao = types.ModuleType("ia.medicao")
        medicao.registrar_uso = lambda *a, **kw: None
        teto = types.ModuleType("ia.teto")
        teto.teto_permite = lambda funcao: True
        patcher_mods = patch.dict(sys.modules, {"ia.medicao": medicao, "ia.teto": teto})
        patcher_mods.start()
        self.addCleanup(patcher_mods.stop)

    def _escrever_config(self, nome, **sobrescrever):
        base = {
            "funcao": nome,
            "ativo": True,
            "modelo_atual": {"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"},
            "alvo": {"provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio"},
            "fallback": [{"provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001"}],
            "max_tokens_saida": 300,
            "cache": {"ativo": False, "ttl": "5m"},
            "modo": "padrao",
        }
        base.update(sobrescrever)
        (Path(self.tmp.name) / f"{nome}.json").write_text(json.dumps(base), encoding="utf-8")

    def test_classify_intent_schema_reprova_json_fora_do_formato_e_cai_no_fallback(self):
        self._escrever_config("classify_intent")
        # openai (alvo, tentado primeiro) devolve JSON sem "parametros" (obrigatorio no
        # schema) -> reprovado; anthropic (fallback) devolve certinho.
        self.openai.roteiros = [Resposta(ok=True, dados={"acao": "consultar", "confianca": 0.9},
                                          provedor="openai", modelo="gpt-6-luna")]
        self.anthropic.roteiros = [Resposta(
            ok=True, dados={"acao": "consultar", "confianca": 0.9, "parametros": {}},
            provedor="anthropic", modelo="claude-haiku-4-5-20251001", tokens_in=5, tokens_out=2,
            custo_usd=0.00001,
        )]
        resultado, usage = captura.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["acao"], "consultar")
        self.assertEqual(usage["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(len(self.openai.chamadas), 1)
        self.assertEqual(len(self.anthropic.chamadas), 1)

    def test_classify_capture_additional_properties_false_reprova_campo_extra(self):
        self._escrever_config("classify_capture", ativo=False)
        dados_com_campo_extra = {
            "tipo": "tarefa", "titulo": "X", "valor": None, "categoria": None, "status": None,
            "quando": None, "hora": None, "duvida": None, "memoria": None,
            "quando_data": "2026-01-01",  # o modelo NAO deveria mais mandar isso
        }
        self.anthropic.roteiros = [
            Resposta(ok=True, dados=dados_com_campo_extra, provedor="anthropic",
                     modelo="claude-haiku-4-5-20251001"),
        ]
        with self.assertRaises(captura.ErroIA):
            captura.classify_capture("teste")
        # so uma tentativa configurada (ativo=false -> fallback repete o mesmo
        # modelo_atual e e deduplicado por ia.core._montar_tentativas)
        self.assertEqual(len(self.anthropic.chamadas), 1)

    def test_escolher_essencial_fallback_quando_alvo_da_erro_de_rede(self):
        self._escrever_config("escolher_essencial")

        class ErroConexaoFake(Exception):
            retentavel = True

        self.openai.roteiros = [ErroConexaoFake("timeout")]
        self.anthropic.roteiros = [Resposta(
            ok=True, dados={"escolhas": [{"id": 1, "motivo": "prazo hoje"}]},
            provedor="anthropic", modelo="claude-haiku-4-5-20251001",
        )]
        escolhas, _usage = captura.escolher_essencial(
            [{"id": 1, "title": "Pagar boleto", "due_date": "2026-09-24", "hora": None}]
        )
        self.assertEqual(escolhas, [{"id": 1, "motivo": "prazo hoje"}])

    def test_summarize_day_sem_schema_aceita_texto_livre_de_qualquer_provedor(self):
        self._escrever_config("summarize_day")
        self.openai.roteiros = [Resposta(ok=True, texto="Dia cheio, 5 compromissos.",
                                          provedor="openai", modelo="gpt-6-luna")]
        texto, usage = captura.summarize_day(["a"], [], [])
        self.assertEqual(texto, "Dia cheio, 5 compromissos.")
        self.assertEqual(usage["model"], "gpt-6-luna")

    def test_todas_as_tentativas_falham_levanta_erroia_com_as_duas_causas(self):
        self._escrever_config("classify_intent")
        self.openai.roteiros = [Resposta(ok=False, erro="401 openai", provedor="openai",
                                          modelo="gpt-6-luna")]
        self.anthropic.roteiros = [Resposta(ok=False, erro="429 anthropic", provedor="anthropic",
                                             modelo="claude-haiku-4-5-20251001")]
        with self.assertRaises(captura.ErroIA) as ctx:
            captura.classify_intent("oi")
        self.assertIn("401 openai", str(ctx.exception))
        self.assertIn("429 anthropic", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
