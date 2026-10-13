import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import claude_client
import db

# Banco proprio: o teto de IA (ia/teto.py) e o registro de uso leem/escrevem no db.DB_PATH da
# hora. Sem isto o arquivo herdava o banco do ultimo modulo que rodou no mesmo processo - com
# gasto alto ou ja apagado, o teto bloqueava (TetoEstourado) conforme a ORDEM dos arquivos
# (apareceu rodando a suite em paralelo com pytest-xdist).
_tmp_dir = tempfile.TemporaryDirectory()


def setUpModule():
    db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
    db.garantir_banco_nao_producao()
    db.init_db()


def _resp(content, stop_reason="end_turn", model=claude_client.SONNET, in_tok=100, out_tok=20):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _text_block(texto):
    return SimpleNamespace(type="text", text=texto)


def _tool_block(nome, entrada, id_="tool_1"):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


class ChatLoopTestCase(unittest.TestCase):
    def test_resposta_direta_sem_ferramenta(self):
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block("Oi! Como posso ajudar?")]),
        ):
            texto, acoes, usage = claude_client.chat([], "contexto", [], {})
        self.assertEqual(texto, "Oi! Como posso ajudar?")
        self.assertEqual(acoes, [])
        self.assertEqual(usage["input_tokens"], 100)

    def test_usa_ferramenta_e_depois_responde(self):
        respostas = [
            _resp([_tool_block("registrar_tarefa", {"titulo": "ligar pro dentista"})], stop_reason="tool_use"),
            _resp([_text_block("Beleza, registrei.")]),
        ]
        chamada = {}

        def exec_tarefa(entrada):
            chamada["input"] = entrada
            return {"ok": True}

        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, usage = claude_client.chat([], "contexto", [], {"registrar_tarefa": exec_tarefa})

        self.assertEqual(texto, "Beleza, registrei.")
        self.assertEqual(acoes, ["registrar_tarefa"])
        self.assertEqual(chamada["input"]["titulo"], "ligar pro dentista")
        self.assertEqual(usage["input_tokens"], 200)

    def test_executa_mais_de_uma_ferramenta_na_mesma_resposta(self):
        respostas = [
            _resp(
                [
                    _tool_block("registrar_tarefa", {"titulo": "lavar o carro"}, id_="t1"),
                    _tool_block("registrar_gasto", {"titulo": "gasolina", "valor": 100}, id_="t2"),
                ],
                stop_reason="tool_use",
            ),
            _resp([_text_block("Registrei as duas coisas.")]),
        ]
        executados = []
        executores = {
            "registrar_tarefa": lambda e: executados.append("tarefa") or {"ok": True},
            "registrar_gasto": lambda e: executados.append("gasto") or {"ok": True},
        }
        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, _usage = claude_client.chat([], "contexto", [], executores)
        self.assertEqual(texto, "Registrei as duas coisas.")
        self.assertEqual(sorted(acoes), ["registrar_gasto", "registrar_tarefa"])
        self.assertEqual(sorted(executados), ["gasto", "tarefa"])

    def test_para_depois_de_poucas_rodadas_pra_nao_ficar_preso(self):
        resposta_tool = _resp([_tool_block("gerar_plano_do_dia", {})], stop_reason="tool_use")
        with patch.object(claude_client.client.messages, "create", return_value=resposta_tool):
            texto, _acoes, _usage = claude_client.chat(
                [], "contexto", [], {"gerar_plano_do_dia": lambda e: {"plano": "..."}}
            )
        self.assertIn("complicado", texto.lower())

    def test_ferramenta_sem_executor_nao_quebra_o_loop(self):
        respostas = [
            _resp([_tool_block("ferramenta_desconhecida", {})], stop_reason="tool_use"),
            _resp([_text_block("Tudo bem, vamos por outro caminho.")]),
        ]
        with patch.object(claude_client.client.messages, "create", side_effect=respostas):
            texto, acoes, _usage = claude_client.chat([], "contexto", [], {})
        self.assertEqual(texto, "Tudo bem, vamos por outro caminho.")
        self.assertEqual(acoes, [])

    def test_system_prompt_inclui_data_de_hoje(self):
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block("oi")]),
        ) as mock_create:
            claude_client.chat([], "contexto", [], {})
        system_enviado = mock_create.call_args.kwargs["system"]
        self.assertIn(claude_client.date.today().isoformat(), system_enviado)

    def test_registrar_memoria_e_ferramenta_disponivel(self):
        nomes = [t["name"] for t in claude_client.CHAT_TOOLS]
        self.assertIn("registrar_memoria", nomes)
        self.assertIn("quando_data", claude_client.CHAT_TOOLS[0]["input_schema"]["properties"])

    def test_cotacao_tools_disponiveis(self):
        nomes = [t["name"] for t in claude_client.CHAT_TOOLS]
        self.assertIn("registrar_item_cotacao", nomes)
        self.assertIn("comparar_cotacao", nomes)


class SystemPromptConteudoTestCase(unittest.TestCase):
    """Fase 6 (US-E10/US-E11): confere REGRAS presentes no texto do system
    prompt do chat - sem chamar a API real (so inspeciona o `system=` que
    seria mandado pro Claude)."""

    def _system_prompt_enviado(self, memorias=None):
        with patch.object(
            claude_client.client.messages, "create", return_value=_resp([_text_block("ok")])
        ) as mock_create:
            claude_client.chat([{"role": "user", "content": "oi"}], "contexto", memorias or [], {})
        return mock_create.call_args.kwargs["system"]

    def test_memorias_fora_do_painel_chegam_no_prompt(self):
        # US-E10: "Fora do painel" respeitado no prompt - os textos dos 3
        # grupos fixos (aqui simulados como memorias comuns, exatamente
        # como list_memorias devolve pro chat) precisam aparecer no
        # system prompt final, sem filtro/perda nenhuma.
        memorias = list(db.MEMORIAS_INICIAIS_FASE6["fora_do_painel"])
        prompt = self._system_prompt_enviado(memorias)
        for texto in memorias:
            self.assertIn(texto, prompt)

    def test_estilo_curto_no_registro_e_com_substancia_na_conversa(self):
        # US-E11 revisto (2026-10-13): registro segue curto, mas conversa de
        # verdade (pergunta, conselho, estudo) ganha resposta com substancia.
        prompt = self._system_prompt_enviado()
        self.assertIn("sem enrolacao", prompt)
        self.assertIn("uma frase curta de\n  confirmacao", prompt)
        self.assertIn("SUBSTANCIA", prompt)
        self.assertIn("explica melhor", prompt.lower())

    def test_vale_a_pena_pede_recomendacao_explicita(self):
        # US-E11: fatos organizados (pros/contras) + recomendacao direta -
        # generalizado pra qualquer pros/contras, nao so a frase literal
        # "vale a pena".
        prompt = self._system_prompt_enviado()
        self.assertIn("Pros:", prompt)
        self.assertIn("Contras:", prompt)
        self.assertIn("RECOMENDACAO DIRETA E EXPLICITA", prompt)
        self.assertIn("mesmo sem usar exatamente essas palavras", prompt)

    def test_contexto_socio_e_pai_na_construtora_no_prompt(self):
        # US-E11: contexto de negocio (socio + pai), usado so quando pesar.
        prompt = self._system_prompt_enviado()
        self.assertIn("pai e um socio", prompt)
        self.assertIn("so quando fizer diferenca", prompt)

    def test_nunca_numero_financeiro_da_construtora_no_prompt(self):
        # US-E11: nunca citar numero financeiro real da construtora
        # (separacao entre painel pessoal e financeiro-construtora).
        prompt = self._system_prompt_enviado()
        self.assertIn("Nunca cite um valor em R$ especifico da construtora", prompt)
        self.assertIn("financeiro-construtora, sistema", prompt)

    def test_decisao_prompt_tambem_recomenda_e_nao_cita_numero_construtora(self):
        # US-E11 se aplica tambem ao card dedicado "vale a pena?"
        # (claude_client.analisar_decisao), nao so ao chat.
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block('{"resumo": "x", "pros": [], "contras": [], '
                                             '"perguntas_chave": [], "inclinacao": "vale", "porque": "y"}')]),
        ) as mock_create:
            claude_client.analisar_decisao("vale a pena expandir a construtora?", [])
        conteudo_enviado = mock_create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("inclinacao direta e explicita", conteudo_enviado)
        self.assertIn("financeiro-construtora, sistema", conteudo_enviado)
        self.assertIn("pai e o", conteudo_enviado)


class ExtrairItemCotacaoPdfTestCase(unittest.TestCase):
    def test_extrai_campos_do_json_devolvido(self):
        dados_json = (
            '{"fornecedor": "Ferragens Silva", "valor": 4500.0, '
            '"prazo_texto": "15 dias uteis", "observacao": "frete incluso"}'
        )
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ) as mock_create:
            dados, usage = claude_client.extrair_item_cotacao_pdf(b"%PDF-1.4 conteudo falso")

        self.assertEqual(dados["fornecedor"], "Ferragens Silva")
        self.assertEqual(dados["valor"], 4500.0)
        self.assertEqual(dados["prazo_texto"], "15 dias uteis")
        self.assertEqual(usage["input_tokens"], 100)

        conteudo_enviado = mock_create.call_args.kwargs["messages"][0]["content"]
        blocos_documento = [b for b in conteudo_enviado if b["type"] == "document"]
        self.assertEqual(len(blocos_documento), 1)
        self.assertEqual(blocos_documento[0]["source"]["media_type"], "application/pdf")

    def test_extrai_com_campos_nulos_quando_pdf_nao_tem_valor_claro(self):
        dados_json = '{"fornecedor": null, "valor": null, "prazo_texto": null, "observacao": null}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_item_cotacao_pdf(b"conteudo")
        self.assertIsNone(dados["fornecedor"])
        self.assertIsNone(dados["valor"])

    def test_extrai_ignora_markdown_ao_redor_do_json(self):
        dados_json = '```json\n{"fornecedor": "X", "valor": 100.0, "prazo_texto": null, "observacao": null}\n```'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_item_cotacao_pdf(b"conteudo")
        self.assertEqual(dados["fornecedor"], "X")


class ClassifyIntentTestCase(unittest.TestCase):
    """US-A2 (Fase 5) - contrato em docs/INTENT.md. Cobre pelo menos 15 frases
    reais espalhadas pelos tipos de acao fechados, mockando a chamada de API
    (nunca gasta credito de verdade)."""

    FRASES_POR_ACAO = [
        # registrar_tarefa
        ("lembra de ligar pro dentista amanha", "registrar_tarefa", {"titulo": "ligar pro dentista"}, 0.9),
        ("preciso comprar material de construcao sexta", "registrar_tarefa", {"titulo": "comprar material"}, 0.85),
        ("marca pra eu levar o carro na revisao", "registrar_tarefa", {"titulo": "revisao do carro"}, 0.88),
        ("anota que tenho que estudar pra prova", "registrar_tarefa", {"titulo": "estudar pra prova"}, 0.8),
        # registrar_gasto
        ("gastei 50 reais no mercado", "registrar_gasto", {"titulo": "mercado", "valor": 50.0}, 0.95),
        ("paguei 120 de conta de luz", "registrar_gasto", {"titulo": "conta de luz", "valor": 120.0}, 0.92),
        ("comprei gasolina por 100 reais", "registrar_gasto", {"titulo": "gasolina", "valor": 100.0}, 0.9),
        # registrar_checkin
        ("minha energia hoje ta boa", "registrar_checkin", {"campo": "energia", "valor": "bom"}, 0.85),
        ("dormi mal essa noite", "registrar_checkin", {"campo": "sono", "valor": "ruim"}, 0.82),
        ("meu humor ta ok hoje", "registrar_checkin", {"campo": "humor", "valor": "ok"}, 0.8),
        # navegar_tela
        ("abre os gastos", "navegar_tela", {"tela": "gastos"}, 0.93),
        ("mostra minhas metas", "navegar_tela", {"tela": "metas"}, 0.9),
        ("vai pra tela de tarefas", "navegar_tela", {"tela": "tarefas"}, 0.9),
        # consultar
        ("quanto eu gastei esse mes", "consultar", {"pergunta": "quanto gastou esse mes"}, 0.88),
        ("quantas tarefas eu tenho pendente", "consultar", {"pergunta": "tarefas pendentes"}, 0.85),
        # corrigir_ultimo
        ("nao, isso e gasto", "corrigir_ultimo", {}, 0.87),
        ("corrige pra tarefa", "corrigir_ultimo", {}, 0.86),
    ]

    def test_pelo_menos_15_frases_cobrindo_os_tipos_de_acao(self):
        self.assertGreaterEqual(len(self.FRASES_POR_ACAO), 15)
        acoes_cobertas = {acao for _, acao, _, _ in self.FRASES_POR_ACAO}
        for esperada in (
            "registrar_tarefa",
            "registrar_gasto",
            "registrar_checkin",
            "navegar_tela",
            "consultar",
            "corrigir_ultimo",
        ):
            self.assertIn(esperada, acoes_cobertas)

    def test_cada_frase_classifica_na_acao_certa(self):
        for texto, acao_esperada, parametros, confianca in self.FRASES_POR_ACAO:
            with self.subTest(texto=texto):
                dados_json = json.dumps(
                    {"acao": acao_esperada, "confianca": confianca, "parametros": parametros}
                )
                with patch.object(
                    claude_client.client.messages,
                    "create",
                    return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
                ):
                    resultado, usage = claude_client.classify_intent(texto)
                self.assertEqual(resultado["acao"], acao_esperada)
                self.assertEqual(resultado["parametros"], parametros)
                self.assertEqual(usage["model"], claude_client.HAIKU)

    def test_confianca_baixa_precisa_confirmacao_true(self):
        dados_json = json.dumps({"acao": "registrar_tarefa", "confianca": 0.3, "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("texto ambiguo qualquer")
        self.assertTrue(resultado["precisa_confirmacao"])

    def test_confianca_alta_nao_precisa_confirmacao(self):
        dados_json = json.dumps({"acao": "registrar_gasto", "confianca": 0.95, "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("gastei 30 no lanche")
        self.assertFalse(resultado["precisa_confirmacao"])

    def test_acao_fora_da_lista_fechada_vira_desconhecido(self):
        dados_json = json.dumps({"acao": "fazer_cafe", "confianca": 0.9, "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("texto qualquer")
        self.assertEqual(resultado["acao"], "desconhecido")

    def test_confianca_fora_do_intervalo_e_limitada(self):
        dados_json = json.dumps({"acao": "consultar", "confianca": 5, "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 1.0)

    def test_confianca_ausente_ou_tipo_errado_vira_zero(self):
        dados_json = json.dumps({"acao": "consultar", "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["confianca"], 0.0)
        self.assertTrue(resultado["precisa_confirmacao"])

    def test_parametros_fora_do_tipo_dict_vira_vazio(self):
        dados_json = json.dumps({"acao": "consultar", "confianca": 0.9, "parametros": "nao e dict"})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ):
            resultado, _usage = claude_client.classify_intent("quanto eu gastei")
        self.assertEqual(resultado["parametros"], {})

    def test_usa_haiku_por_ser_mais_barato(self):
        dados_json = json.dumps({"acao": "desconhecido", "confianca": 0.0, "parametros": {}})
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)], model=claude_client.HAIKU),
        ) as mock_create:
            claude_client.classify_intent("qualquer coisa")
        self.assertEqual(mock_create.call_args.kwargs["model"], claude_client.HAIKU)

    def test_acoes_intent_e_a_lista_fechada_do_contrato(self):
        self.assertEqual(
            claude_client.ACOES_INTENT,
            (
                "registrar_tarefa",
                "registrar_gasto",
                "registrar_checkin",
                "navegar_tela",
                "consultar",
                "corrigir_ultimo",
                "desconhecido",
            ),
        )


class ExtrairNotaFiscalFotoTestCase(unittest.TestCase):
    def test_extrai_campos_do_json_devolvido(self):
        dados_json = '{"valor": 89.9, "estabelecimento": "Supermercado Bom Preco", "data": "2026-09-20"}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ) as mock_create:
            dados, usage = claude_client.extrair_nota_fiscal_foto(b"fake-jpeg-bytes", "image/jpeg")

        self.assertEqual(dados["valor"], 89.9)
        self.assertEqual(dados["estabelecimento"], "Supermercado Bom Preco")
        self.assertEqual(dados["data"], "2026-09-20")
        self.assertEqual(usage["input_tokens"], 100)

        conteudo_enviado = mock_create.call_args.kwargs["messages"][0]["content"]
        blocos_imagem = [b for b in conteudo_enviado if b["type"] == "image"]
        self.assertEqual(len(blocos_imagem), 1)
        self.assertEqual(blocos_imagem[0]["source"]["media_type"], "image/jpeg")

    def test_extrai_com_campos_nulos_quando_foto_ilegivel(self):
        dados_json = '{"valor": null, "estabelecimento": null, "data": null}'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_nota_fiscal_foto(b"conteudo", "image/png")
        self.assertIsNone(dados["valor"])
        self.assertIsNone(dados["estabelecimento"])

    def test_extrai_ignora_markdown_ao_redor_do_json(self):
        dados_json = '```json\n{"valor": 20.0, "estabelecimento": "Padaria", "data": null}\n```'
        with patch.object(
            claude_client.client.messages,
            "create",
            return_value=_resp([_text_block(dados_json)]),
        ):
            dados, _ = claude_client.extrair_nota_fiscal_foto(b"conteudo", "image/jpeg")
        self.assertEqual(dados["estabelecimento"], "Padaria")


if __name__ == "__main__":
    unittest.main()
