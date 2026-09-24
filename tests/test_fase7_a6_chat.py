"""Fase 7 / A6: chat com layout de cache estavel, roteador (A14), limites de
saida e configs. Tudo com duble - nenhuma chamada real de API e nenhum
acesso ao banco (medicao/teto sao patchados quando entram em jogo)."""
import copy
import json
import os
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")


import claude_client
from ia import core, legado
from ia.contrato import Resposta
from ia.funcoes import chat as chat_mod


def _resp(content, stop_reason="end_turn", model=claude_client.SONNET, in_tok=100, out_tok=20,
          cache_lido=0, cache_escrito=0):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok,
                              cache_read_input_tokens=cache_lido,
                              cache_creation_input_tokens=cache_escrito),
    )


def _texto(t):
    return SimpleNamespace(type="text", text=t)


def _tool(nome, entrada, id_="t1"):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


class _Gravador:
    """Duble de client.messages.create que COPIA os kwargs na hora da chamada
    (o loop de tools muta a lista de mensagens depois)."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, **kwargs):
        copia = dict(kwargs)
        copia["messages"] = copy.deepcopy(kwargs["messages"])
        copia["tools"] = copy.deepcopy(kwargs["tools"])
        self.chamadas.append(copia)
        return self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]


def _conta_breakpoints(chamada) -> int:
    total = sum(1 for t in chamada["tools"] if "cache_control" in t)
    if isinstance(chamada["system"], list):
        total += sum(1 for b in chamada["system"] if "cache_control" in b)
    for m in chamada["messages"]:
        if isinstance(m["content"], list):
            total += sum(1 for b in m["content"] if isinstance(b, dict) and "cache_control" in b)
    return total


def _sem_cache(obj):
    if isinstance(obj, dict):
        return {k: _sem_cache(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_sem_cache(v) for v in obj]
    return obj


def _chat(historico, contexto="ctx", memorias=None, executores=None, respostas=None, **kw):
    gravador = _Gravador(respostas or [_resp([_texto("ok")])])
    with patch.object(claude_client.client.messages, "create", side_effect=gravador):
        saida = claude_client.chat(historico, contexto, memorias or [], executores or {}, **kw)
    return saida, gravador


H1 = [{"role": "user", "content": "oi"}]
H2 = H1 + [{"role": "assistant", "content": "Oi! Tudo certo?"}, {"role": "user", "content": "anota comprar pao"}]
H3 = H2 + [{"role": "assistant", "content": "Anotei."}, {"role": "user", "content": "e leite tambem"}]


class LayoutCacheTestCase(unittest.TestCase):
    def test_prefixo_identico_byte_a_byte_entre_chamadas_seguidas(self):
        (_, _, _), g1 = _chat(H1, contexto="Tarefas pendentes: a\nhora 10:00", memorias=["gosta de cafe"])
        (_, _, _), g2 = _chat(H2, contexto="Tarefas pendentes: a, b\nhora 10:05", memorias=["gosta de cafe"])
        (_, _, _), g3 = _chat(H3, contexto="Tarefas pendentes: a, b, c\nhora 10:09", memorias=["gosta de cafe"])
        c1, c2, c3 = g1.chamadas[0], g2.chamadas[0], g3.chamadas[0]

        def prefixo(c):
            return json.dumps([c["model"], c["tools"], c["system"], c["messages"][0]["content"][0]],
                              ensure_ascii=False, sort_keys=True).encode("utf-8")

        self.assertEqual(prefixo(c1), prefixo(c2))
        self.assertEqual(prefixo(c2), prefixo(c3))
        # historico estavel da chamada 2 (ate o breakpoint 3) reaparece igual na 3
        self.assertEqual(_sem_cache(c2["messages"][:2]), _sem_cache(c3["messages"][:2]))

    def test_system_nao_tem_contexto_do_dia_nem_nada_que_muda_a_cada_chamada(self):
        (_, _, _), g = _chat(H2, contexto="Gasto de hoje: R$ 12.34 MARCA-UNICA")
        chamada = g.chamadas[0]
        self.assertIsInstance(chamada["system"], str)
        self.assertNotIn("MARCA-UNICA", chamada["system"])
        self.assertNotIn("{contexto}", chat_mod.CHAT_SYSTEM_PROMPT)
        ultima = chamada["messages"][-1]
        self.assertEqual(ultima["role"], "user")
        self.assertTrue(ultima["content"][0]["text"].startswith("Contexto de agora"))
        self.assertIn("MARCA-UNICA", ultima["content"][0]["text"])
        self.assertEqual(ultima["content"][-1]["text"], "anota comprar pao")

    def test_system_continua_com_data_e_memorias(self):
        (_, _, _), g = _chat(H1, memorias=["mora em Campinas"])
        system = g.chamadas[0]["system"]
        self.assertIn(chat_mod.date.today().isoformat(), system)
        self.assertIn("- mora em Campinas", system)

    def test_cache_control_no_lugar_certo(self):
        (_, _, _), g = _chat(H3, contexto="ctx")
        c = g.chamadas[0]
        self.assertIn("cache_control", c["tools"][-1])
        self.assertTrue(all("cache_control" not in t for t in c["tools"][:-1]))
        msgs = c["messages"]
        bloco_fixo = msgs[0]["content"][0]
        self.assertEqual(bloco_fixo["text"], chat_mod.TEXTO_SEM_RESUMO)
        self.assertEqual(bloco_fixo["cache_control"], {"type": "ephemeral"})
        # fim do historico estavel = "Anotei." (penultima mensagem)
        self.assertEqual(msgs[-2]["content"][-1]["text"], "Anotei.")
        self.assertIn("cache_control", msgs[-2]["content"][-1])
        # bloco "Contexto de agora" NAO e breakpoint (muda a cada chamada) ...
        self.assertNotIn("cache_control", msgs[-1]["content"][0])
        # ... mas o ultimo bloco da mensagem nova e o breakpoint rolante
        self.assertIn("cache_control", msgs[-1]["content"][-1])
        self.assertEqual(_conta_breakpoints(c), 4)

    def test_resumo_da_a5_vira_bloco_fixo(self):
        (_, _, _), g = _chat(H2, contexto_fixo="Alex combinou obra na terca.")
        bloco = g.chamadas[0]["messages"][0]["content"][0]
        self.assertEqual(bloco["text"], chat_mod.PREFIXO_RESUMO + "Alex combinou obra na terca.")
        self.assertIn("cache_control", bloco)

    def test_historico_comecando_com_assistant_ganha_user_no_inicio(self):
        hist = [{"role": "assistant", "content": "bom dia"}, {"role": "user", "content": "oi"}]
        (_, _, _), g = _chat(hist)
        msgs = g.chamadas[0]["messages"]
        self.assertEqual(msgs[0], {"role": "user", "content": [
            {"type": "text", "text": chat_mod.TEXTO_SEM_RESUMO, "cache_control": {"type": "ephemeral"}}]})
        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertLessEqual(_conta_breakpoints(g.chamadas[0]), 4)

    def test_nao_muta_historico_de_quem_chamou(self):
        hist = copy.deepcopy(H3)
        _chat(hist)
        self.assertEqual(hist, H3)

    def test_cache_desligado_na_config_nao_marca_nada(self):
        cfg = copy.deepcopy(core._carregar_config("chat"))
        cfg["cache"] = {"ativo": False, "ttl": "5m"}
        with patch.object(chat_mod, "_config_ia", return_value=cfg):
            (_, _, _), g = _chat(H3)
        c = g.chamadas[0]
        self.assertEqual(_conta_breakpoints(c), 0)
        self.assertEqual(c["tools"], chat_mod.CHAT_TOOLS)

    def test_ttl_1h_vai_pro_cache_control(self):
        cfg = copy.deepcopy(core._carregar_config("chat"))
        cfg["cache"] = {"ativo": True, "ttl": "1h"}
        with patch.object(chat_mod, "_config_ia", return_value=cfg):
            (_, _, _), g = _chat(H2)
        self.assertEqual(g.chamadas[0]["tools"][-1]["cache_control"], {"type": "ephemeral", "ttl": "1h"})

    def test_breakpoint_rolante_no_loop_de_tools(self):
        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "pao"}, "a1")], stop_reason="tool_use"),
            _resp([_tool("registrar_tarefa", {"titulo": "leite"}, "a2")], stop_reason="tool_use"),
            _resp([_texto("Anotei os dois.")]),
        ]
        (texto, acoes, _), g = _chat(H2, executores={"registrar_tarefa": lambda e: {"ok": True}},
                                     respostas=respostas)
        self.assertEqual(texto, "Anotei os dois.")
        self.assertEqual(acoes, ["registrar_tarefa", "registrar_tarefa"])
        for chamada in g.chamadas:
            self.assertLessEqual(_conta_breakpoints(chamada), 4)
        ultima = g.chamadas[2]["messages"]
        self.assertEqual(ultima[-1]["content"][-1]["type"], "tool_result")
        self.assertIn("cache_control", ultima[-1]["content"][-1])
        # o breakpoint saiu da mensagem nova do usuario e do tool_result anterior
        self.assertNotIn("cache_control", ultima[-3]["content"][-1])
        self.assertNotIn("cache_control", ultima[-5]["content"][-1])
        # prefixo (tools + system + bloco fixo) igual entre as rodadas
        self.assertEqual(g.chamadas[0]["system"], g.chamadas[2]["system"])
        self.assertEqual(g.chamadas[0]["messages"][0]["content"][0], ultima[0]["content"][0])


class LimitesSaidaTestCase(unittest.TestCase):
    def test_chat_manda_max_tokens_500(self):
        (_, _, _), g = _chat(H1)
        self.assertEqual(g.chamadas[0]["max_tokens"], 500)
        self.assertEqual(g.chamadas[0]["model"], "claude-sonnet-5")

    def test_corte_no_limite_refaz_a_rodada_com_teto_antigo(self):
        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "cort"}, "x")], stop_reason="max_tokens", out_tok=500),
            _resp([_texto("Registrei tudo.")], out_tok=900),
        ]
        (texto, acoes, uso), g = _chat(H1, respostas=respostas)
        self.assertEqual([c["max_tokens"] for c in g.chamadas], [500, chat_mod.MAX_TOKENS_CHAT_ESCALADO])
        self.assertEqual(texto, "Registrei tudo.")
        self.assertEqual(acoes, [])
        self.assertEqual(uso["output_tokens"], 1400)
        self.assertEqual(uso["input_tokens"], 200)

    def test_uso_soma_tokens_de_cache_e_custo(self):
        (_, _, uso), _g = _chat(H1, respostas=[_resp([_texto("oi")], in_tok=10, out_tok=10,
                                                     cache_lido=1000, cache_escrito=200)])
        self.assertEqual(uso["cache_read_input_tokens"], 1000)
        self.assertEqual(uso["cache_creation_input_tokens"], 200)
        esperado = (10 * 2.0 + 10 * 10.0 + 1000 * 0.2 + 200 * 2.5) / 1_000_000
        self.assertAlmostEqual(uso["cost_usd"], esperado, places=9)
        self.assertEqual(set(uso) >= {"model", "input_tokens", "output_tokens", "cost_usd"}, True)

    def test_decisao_manda_700_e_mensagem_dificil_500(self):
        with patch("ia.teto.teto_permite", return_value=True), \
                patch("ia.medicao.registrar_uso"), \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp([_texto('{"resumo": "x"}')])) as m:
            claude_client.analisar_decisao("vale a pena?", [])
            self.assertEqual(m.call_args.kwargs["max_tokens"], 700)
            claude_client.redigir_mensagem_dificil("cobrar", "Joao")
            self.assertEqual(m.call_args.kwargs["max_tokens"], 500)
            self.assertEqual(m.call_args.kwargs["model"], "claude-sonnet-5")

    def test_config_quebrada_nao_derruba_o_chat(self):
        with patch.object(core, "_carregar_config", side_effect=core.ConfigIAErro("quebrou")):
            (texto, _, _), g = _chat(H1)
        self.assertEqual(texto, "ok")
        self.assertEqual(g.chamadas[0]["max_tokens"], chat_mod.MAX_TOKENS_CHAT_PADRAO)
        self.assertEqual(g.chamadas[0]["model"], legado.SONNET)

    def test_alvo_openai_ativo_nao_tira_o_chat_com_tools_da_anthropic(self):
        cfg = copy.deepcopy(core._carregar_config("chat"))
        cfg["ativo"] = True
        with patch.object(chat_mod, "_config_ia", return_value=cfg):
            (_, _, _), g = _chat(H1)
        self.assertEqual(g.chamadas[0]["model"], "claude-sonnet-5")


class CaminhoDiretoMedidoTestCase(unittest.TestCase):
    """C1: decisao/mensagem dificil com `ativo: false` (SDK direto) tambem
    respeitam o teto unico e gravam em uso_ia (fonte unica do gasto)."""

    def test_caminho_direto_grava_uso_ia_uma_vez(self):
        with patch("ia.teto.teto_permite", return_value=True) as teto, \
                patch("ia.medicao.registrar_uso") as reg, \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp([_texto('{"resumo": "x"}')], in_tok=30, out_tok=7)):
            _dados, uso = claude_client.analisar_decisao("vale a pena?", [])
        teto.assert_called_once_with("analisar_decisao")
        reg.assert_called_once()
        args, kwargs = reg.call_args
        self.assertEqual(args, ("analisar_decisao", "anthropic", "claude-sonnet-5"))
        self.assertEqual((kwargs["tokens_in"], kwargs["tokens_out"]), (30, 7))
        self.assertAlmostEqual(kwargs["custo_usd"], uso["cost_usd"], places=9)

    def test_caminho_direto_com_teto_estourado_nao_chama_api(self):
        with patch("ia.teto.teto_permite", return_value=False), \
                patch("ia.medicao.registrar_uso") as reg, \
                patch.object(claude_client.client.messages, "create") as create:
            with self.assertRaises(core.TetoEstourado):
                claude_client.redigir_mensagem_dificil("cobrar", None)
        create.assert_not_called()
        reg.assert_not_called()


class ConfigsTestCase(unittest.TestCase):
    def test_configs_da_faixa_validas_e_desligadas(self):
        todas = core.carregar_todas_configs()
        esperados = {"chat": 500, "analisar_decisao": 700, "redigir_mensagem_dificil": 500}
        for funcao, limite in esperados.items():
            cfg = todas[funcao]
            self.assertFalse(cfg["ativo"], funcao)
            self.assertEqual(cfg["max_tokens_saida"], limite, funcao)
            self.assertEqual(cfg["modelo_atual"]["provedor"], "anthropic")
            self.assertEqual(cfg["modelo_atual"]["modelo"], "claude-sonnet-5")
            self.assertEqual(cfg["alvo"], {"provedor": "openai", "modelo": "gpt-6-sol", "esforco": "medio"})
            # esforco explicito: "" viraria output_config.effort="" no adapter
            self.assertIn(cfg["modelo_atual"]["esforco"], ("baixo", "medio"))
        self.assertFalse(todas["chat_simples"]["ativo"])


class MedicaoTetoTestCase(unittest.TestCase):
    def test_sem_medir_uso_nao_toca_medicao_nem_teto(self):
        with patch("ia.medicao.registrar_uso") as reg, patch("ia.teto.teto_permite") as teto:
            _chat(H1)
        reg.assert_not_called()
        teto.assert_not_called()

    def test_medir_uso_registra_cada_rodada_em_uso_ia(self):
        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "a"})], stop_reason="tool_use", in_tok=50, cache_lido=900),
            _resp([_texto("feito")], in_tok=5, out_tok=7),
        ]
        with patch("ia.medicao.registrar_uso") as reg, patch("ia.teto.teto_permite", return_value=True) as teto:
            _chat(H1, executores={"registrar_tarefa": lambda e: {"ok": True}}, respostas=respostas,
                  medir_uso=True)
        teto.assert_called_once_with("chat")
        self.assertEqual(reg.call_count, 2)
        args, kwargs = reg.call_args_list[0]
        self.assertEqual(args, ("chat", "anthropic", "claude-sonnet-5"))
        self.assertEqual(kwargs["tokens_in"], 50)
        self.assertEqual(kwargs["tokens_cache_lido"], 900)
        self.assertTrue(kwargs["ok"])

    def test_teto_estourado_nao_chama_a_api(self):
        with patch("ia.teto.teto_permite", return_value=False), \
                patch("ia.medicao.registrar_uso") as reg, \
                patch.object(claude_client.client.messages, "create") as create:
            texto, acoes, uso = claude_client.chat(H1, "ctx", [], {}, medir_uso=True)
        create.assert_not_called()
        reg.assert_not_called()
        self.assertIn("teto", texto)
        self.assertEqual((acoes, uso["cost_usd"]), ([], 0.0))

    def test_falha_na_medicao_nao_derruba_o_chat(self):
        with patch("ia.medicao.registrar_uso", side_effect=RuntimeError("db travado")), \
                patch("ia.teto.teto_permite", return_value=True):
            (texto, _, _), _g = _chat(H1, medir_uso=True)
        self.assertEqual(texto, "ok")

    def test_erro_no_teto_bloqueia(self):
        with patch("ia.teto.teto_permite", side_effect=RuntimeError("sem tabela")), \
                patch.object(claude_client.client.messages, "create") as create:
            texto, _, _ = claude_client.chat(H1, "ctx", [], {}, medir_uso=True)
        create.assert_not_called()
        self.assertIn("teto", texto)


class RoteadorTestCase(unittest.TestCase):
    def test_flag_desligada_vai_sempre_pro_padrao(self):
        with patch.object(core, "chamar_ia") as chamar:
            (texto, _, _), g = _chat([{"role": "user", "content": "oi"}])
        chamar.assert_not_called()
        self.assertEqual(len(g.chamadas), 1)
        self.assertEqual(texto, "ok")

    def test_roteador_recebe_mensagem_nova_e_historico_anterior(self):
        with patch("ia.roteador_chat.decidir", return_value="padrao") as decidir:
            _chat(H2, conn="CONN")
        mensagem, contexto = decidir.call_args.args
        self.assertEqual(mensagem, "anota comprar pao")
        self.assertEqual(contexto["historico"], H2[:-1])
        self.assertEqual(contexto["conn"], "CONN")

    def test_luna_responde_sem_tools_via_chat_simples(self):
        resp = Resposta(ok=True, texto=" Bom dia! ", provedor="anthropic", modelo="claude-sonnet-5",
                        tokens_in=30, tokens_out=5, custo_usd=0.0001)
        with patch("ia.roteador_chat.decidir", return_value="luna"), \
                patch.object(core, "chamar_ia", return_value=resp) as chamar, \
                patch.object(claude_client.client.messages, "create") as create:
            texto, acoes, uso = claude_client.chat(H1, "Tarefas: nenhuma", ["gosta de cafe"], {},
                                                   contexto_fixo="resumo X")
        create.assert_not_called()
        self.assertEqual((texto, acoes), ("Bom dia!", []))
        self.assertEqual(uso["input_tokens"], 30)
        self.assertEqual(uso["model"], "claude-sonnet-5")
        args, kwargs = chamar.call_args
        self.assertEqual(args[0], "chat_simples")
        self.assertIn(chat_mod.MARCADOR_PRECISA_FERRAMENTA, kwargs["sistema"])
        self.assertIn("- gosta de cafe", kwargs["sistema"])
        self.assertEqual(kwargs["contexto_fixo"], chat_mod.PREFIXO_RESUMO + "resumo X")
        ultima = args[1][-1]
        self.assertEqual(ultima["role"], "user")
        self.assertIn("Tarefas: nenhuma", ultima["content"])
        self.assertTrue(ultima["content"].endswith("oi"))
        self.assertNotIn("tools", kwargs)

    def test_luna_que_precisa_de_ferramenta_cai_pro_padrao(self):
        for resp in (Resposta(ok=True, texto=chat_mod.MARCADOR_PRECISA_FERRAMENTA),
                     Resposta(ok=False, erro="teto_ia_estourado"),
                     Resposta(ok=True, texto="   ")):
            with self.subTest(resp=resp), patch("ia.roteador_chat.decidir", return_value="luna"), \
                    patch.object(core, "chamar_ia", return_value=resp):
                (texto, _, _), g = _chat(H1)
            self.assertEqual(texto, "ok")
            self.assertEqual(len(g.chamadas), 1)
            self.assertTrue(g.chamadas[0]["tools"])

    def test_luna_com_excecao_cai_pro_padrao(self):
        with patch("ia.roteador_chat.decidir", return_value="luna"), \
                patch.object(core, "chamar_ia", side_effect=core.ConfigIAErro("x")):
            (texto, _, _), g = _chat(H1)
        self.assertEqual((texto, len(g.chamadas)), ("ok", 1))

    def test_local_ou_destino_estranho_ou_erro_seguem_no_padrao(self):
        for efeito in ({"return_value": "local"}, {"return_value": "???"},
                       {"side_effect": RuntimeError("boom")}):
            with self.subTest(efeito=efeito), patch("ia.roteador_chat.decidir", **efeito), \
                    patch.object(core, "chamar_ia") as chamar:
                (texto, _, _), g = _chat(H1)
            chamar.assert_not_called()
            self.assertEqual((texto, len(g.chamadas)), ("ok", 1))

    def test_flag_ligada_de_verdade_manda_mensagem_simples_pra_luna(self):
        from ia import roteador_chat

        resp = Resposta(ok=True, texto="De nada!", modelo="claude-sonnet-5")
        with patch.object(roteador_chat, "_flag_ativa", return_value=True), \
                patch.object(roteador_chat, "_casar_classificador_local", return_value=False), \
                patch.object(roteador_chat, "_resolve_local_aprendido", return_value=False), \
                patch.object(core, "chamar_ia", return_value=resp) as chamar, \
                patch.object(claude_client.client.messages, "create") as create:
            texto, _, _ = claude_client.chat([{"role": "user", "content": "valeu, obrigado"}], "ctx", [], {})
        self.assertEqual(texto, "De nada!")
        create.assert_not_called()
        self.assertEqual(chamar.call_args.args[0], "chat_simples")


class ContratoJsonTestCase(unittest.TestCase):
    """analisar_decisao/redigir_mensagem_dificil com `ativo: true` passam
    por ia.core.chamar_ia."""

    def _cfg_ativo(self, funcao):
        cfg = copy.deepcopy(core._carregar_config(funcao))
        cfg["ativo"] = True
        return cfg

    def test_ativo_passa_por_chamar_ia(self):
        resp = Resposta(ok=True, texto='```json\n{"direta": "a", "gentil": "b"}\n```', modelo="gpt-6-sol",
                        tokens_in=11, tokens_out=22, custo_usd=0.5)
        with patch.object(chat_mod, "_config_ia", return_value=self._cfg_ativo("redigir_mensagem_dificil")), \
                patch.object(core, "chamar_ia", return_value=resp) as chamar, \
                patch.object(claude_client.client.messages, "create") as create:
            dados, uso = claude_client.redigir_mensagem_dificil("cobrar", None)
        create.assert_not_called()
        self.assertEqual(dados, {"direta": "a", "gentil": "b"})
        self.assertEqual(uso, {"model": "gpt-6-sol", "input_tokens": 11, "output_tokens": 22, "cost_usd": 0.5})
        self.assertEqual(chamar.call_args.args[0], "redigir_mensagem_dificil")
        self.assertIn("nao informado", chamar.call_args.args[1][0]["content"])

    def test_falha_no_contrato_vira_excecao_dedicada_e_json_ruim_vira_valueerror(self):
        # C1: teto -> core.TetoEstourado; rede/provedor -> core.ErroProvedor
        # (ambas ValueError; app._call_claude traduz em TETO_IA_MSG/CLAUDE_ERROR_MSG).
        with patch.object(chat_mod, "_config_ia", return_value=self._cfg_ativo("analisar_decisao")):
            with patch.object(core, "chamar_ia", return_value=Resposta(ok=False, erro="teto_ia_estourado")):
                with self.assertRaises(core.TetoEstourado) as ctx:
                    claude_client.analisar_decisao("vale?", [])
                self.assertIn("teto_ia_estourado", str(ctx.exception))
            with patch.object(core, "chamar_ia", return_value=Resposta(ok=False, erro="openai/gpt-6-sol: timeout")):
                with self.assertRaises(core.ErroProvedor):
                    claude_client.analisar_decisao("vale?", [])
            with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="nao e json")):
                with self.assertRaises(ValueError):
                    claude_client.analisar_decisao("vale?", [])

    def test_adapter_anthropic_do_nucleo_usa_o_cliente_legado(self):
        core.registrar_adapter("anthropic", None)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        chat_mod._garantir_adapter_anthropic_legado()
        adapter = core._obter_adapter("anthropic")
        self.assertIs(adapter._client, legado.client)
        # nao sobrescreve duble ja registrado por outra faixa/teste
        duble = object()
        core.registrar_adapter("anthropic", lambda: duble)
        chat_mod._garantir_adapter_anthropic_legado()
        self.assertIs(core._obter_adapter("anthropic"), duble)

    def test_caminho_do_contrato_ponta_a_ponta_com_cliente_mockado(self):
        """Nucleo de verdade + adapter de verdade, cliente legado mockado,
        medicao/teto patchados (sem banco)."""
        core.registrar_adapter("anthropic", None)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        cfg = self._cfg_ativo("analisar_decisao")
        cfg["alvo"] = {"provedor": "anthropic", "modelo": "claude-sonnet-5", "esforco": "baixo"}
        with patch.object(chat_mod, "_config_ia", return_value=cfg), \
                patch.object(core, "_carregar_config", return_value=cfg), \
                patch("ia.teto.teto_permite", return_value=True), \
                patch("ia.medicao.registrar_uso") as reg, \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp([_texto('{"inclinacao": "vale"}')])) as create:
            dados, uso = claude_client.analisar_decisao("vale a pena?", ["x"])
        self.assertEqual(dados, {"inclinacao": "vale"})
        self.assertEqual(create.call_args.kwargs["max_tokens"], 700)
        self.assertEqual(create.call_args.kwargs["output_config"], {"effort": "low"})
        self.assertNotIn("thinking", create.call_args.kwargs)
        self.assertEqual(reg.call_count, 1)
        self.assertEqual(uso["input_tokens"], 100)


class FachadaTestCase(unittest.TestCase):
    def test_fachada_reexporta_e_patch_claude_client_chat_funciona(self):
        self.assertIs(claude_client.chat, chat_mod.chat)
        self.assertIs(claude_client.analisar_decisao, chat_mod.analisar_decisao)
        with patch("claude_client.chat", return_value=("fake", [], {})) as m:
            self.assertEqual(claude_client.chat([], "c", [], {}), ("fake", [], {}))
        m.assert_called_once()
        self.assertIs(claude_client.chat, chat_mod.chat)

    def test_app_usa_o_patch_de_claude_client_chat(self):
        import app

        self.assertIs(app.claude_client, claude_client)


class FuzzLayoutTestCase(unittest.TestCase):
    """Stress: 150 historicos aleatorios/malformados - o montador nunca
    levanta, a 1a mensagem e sempre user, nunca passa de 4 breakpoints e
    nunca muta a entrada."""

    def test_fuzz_montar_mensagens(self):
        rnd = random.Random(20260924)
        conteudos = ["", "oi", "x" * 5000, None, 123, ["solto"], [{"type": "text", "text": "bloco"}],
                     "😀 acentuação", "\x00\n\t", '{"json": true}']
        controle = {"type": "ephemeral"}
        for i in range(150):
            hist = []
            for _ in range(rnd.randint(0, 12)):
                papel = rnd.choice(["user", "assistant", "user", "assistant", "system", None])
                item = {"role": papel, "content": rnd.choice(conteudos)} if rnd.random() > 0.05 else "lixo"
                hist.append(item)
            original = copy.deepcopy(hist)
            contexto = rnd.choice(["", None, "ctx", "c" * 3000])
            fixo = rnd.choice(["", None, "resumo", "r" * 2000])
            with self.subTest(i=i):
                msgs = chat_mod.montar_mensagens_chat(hist, contexto, fixo, controle)
                self.assertEqual(hist, original)
                self.assertEqual(msgs[0]["role"], "user")
                self.assertEqual(msgs[-1]["role"], "user")
                self.assertTrue(msgs[-1]["content"])
                marcados = sum(1 for m in msgs for b in m["content"]
                               if isinstance(b, dict) and "cache_control" in b)
                self.assertLessEqual(marcados + 1, 4)  # +1 = ultimo tool
                for m in msgs:
                    self.assertIn(m["role"], ("user", "assistant"))
                    for b in m["content"]:
                        if isinstance(b, dict) and b.get("type") == "text":
                            self.assertTrue(b["text"])


if __name__ == "__main__":
    unittest.main()
