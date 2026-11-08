"""Degrau "pensar" do chat (07/11/2026): o Alex pediu que o painel pense de verdade as vezes, mesmo gastando
mais ou demorando mais. Mensagem dificil (decisao com varias condicoes, conta de horario, correcao dele,
"pensa direito", remontar o dia) sobe pro modelo maior com pensamento; registro e pergunta simples seguem
no modelo barato. IA sempre mockada, sem rede."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import core, roteador_chat  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

DIFICEIS = [
    # as duas mensagens reais de 07/11 (sem nomes): hora de chegada com varias condicoes, e "compensa?"
    "Vou dar uma lavadinha por fora do carro agora, então atrasou tudo. Estimando uns 20 minutos na lavagem, "
    "depois tomo banho e vou buscar a menina. Que hora que eu vou chegar lá?",
    "Tá, 84% de chuva, compensa lavar o carro ou não? Vale a pena?",
    "Será que eu devo sair mais cedo por causa do trânsito?",
    "pensa direito nisso",
    "pensa melhor, isso tá errado",
    "isso tá errado, refaz",
    "refaz meu dia com o atraso",
    "tu errou a conta de novo",
    "não é isso que eu perguntei",
]
SIMPLES = [
    "gastei 50 no mercado",
    "tomei um copo de água",
    "anota comprar pão",
    "que horas é o date?",
    "oi",
    "marca o dentista amanhã às 10h",
    "bom dia",
]


class PrecisaPensarTestCase(unittest.TestCase):
    def test_dificil_pensa(self):
        for frase in DIFICEIS:
            with self.subTest(frase=frase):
                self.assertTrue(roteador_chat.precisa_pensar(frase), frase)

    def test_simples_nao_gasta_a_toa(self):
        for frase in SIMPLES:
            with self.subTest(frase=frase):
                self.assertFalse(roteador_chat.precisa_pensar(frase), frase)

    def test_lixo_nao_quebra(self):
        for lixo in (None, "", "   ", 123, [], {"a": 1}):
            self.assertFalse(roteador_chat.precisa_pensar(lixo))


class ConfigDoDegrauTestCase(unittest.TestCase):
    def test_chat_json_tem_o_degrau_pensar(self):
        config = core._carregar_config("chat")
        pensar = config["pensar"]
        self.assertEqual(pensar["provedor"], "anthropic")
        self.assertTrue(pensar["modelo"].startswith("claude-opus"))
        self.assertGreaterEqual(pensar["max_tokens_saida"], 8000)  # pensamento + resposta cabem

    def test_pensamento_por_modelo(self):
        self.assertEqual(chat_mod._pensamento({"modelo": "claude-haiku-5-5", "esforco": "alto"}), {})
        self.assertEqual(chat_mod._pensamento({"modelo": "claude-opus-5-5", "esforco": ""}), {})
        alto = chat_mod._pensamento({"modelo": "claude-opus-5-5", "esforco": "alto"})
        self.assertEqual(alto, {"output_config": {"effort": "high"}, "thinking": {"type": "adaptive"}})
        baixo = chat_mod._pensamento({"modelo": "claude-sonnet-5", "esforco": "baixo"})
        self.assertEqual(baixo, {"output_config": {"effort": "low"}})  # sem pensar a fundo

    def test_modelo_pensar_so_na_mensagem_dificil(self):
        config = core._carregar_config("chat")
        escolha = chat_mod._modelo_pensar(config, DIFICEIS[1])
        self.assertIsNotNone(escolha)
        self.assertTrue(escolha[0].startswith("claude-opus"))
        self.assertEqual(escolha[2]["thinking"], {"type": "adaptive"})
        self.assertIsNone(chat_mod._modelo_pensar(config, "gastei 50 no mercado"))
        self.assertIsNone(chat_mod._modelo_pensar(None, DIFICEIS[1]))  # sem config: nada muda
        sem = dict(config, pensar=None)
        self.assertIsNone(chat_mod._modelo_pensar(sem, DIFICEIS[1]))


def _resp(texto, modelo):
    uso = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0,
                          cache_creation_input_tokens=0)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)], stop_reason="end_turn",
                           usage=uso, model=modelo)


class NoLoopDoChatTestCase(unittest.TestCase):
    def _pedido(self, frase):
        enviados = []

        def criar(**kw):
            enviados.append(kw)
            return _resp("Resposta pensada.", kw["model"])

        with patch.object(chat_mod, "_decidir_rota", return_value="padrao"), \
                patch.object(chat_mod.client.messages, "create", side_effect=criar):
            chat_mod.chat([{"role": "user", "content": frase}], "agora: 18:00", [], {})
        return enviados[0]

    def test_mensagem_dificil_vai_pro_modelo_maior_com_pensamento(self):
        pedido = self._pedido(DIFICEIS[1])
        self.assertTrue(pedido["model"].startswith("claude-opus"), pedido["model"])
        self.assertEqual(pedido["thinking"], {"type": "adaptive"})
        self.assertEqual(pedido["output_config"], {"effort": "high"})

    def test_registro_simples_continua_barato_e_sem_pensamento(self):
        pedido = self._pedido("oi, tudo bem")
        self.assertFalse(pedido["model"].startswith("claude-opus"), pedido["model"])
        self.assertNotIn("thinking", pedido)
        self.assertNotIn("output_config", pedido)

    def test_conversa_comum_pensa_no_sonnet_sem_ir_pro_opus(self):
        pedido = self._pedido("me explica o que é sustentação de uma asa")
        self.assertFalse(pedido["model"].startswith("claude-opus"), pedido["model"])
        self.assertEqual(pedido["thinking"], {"type": "adaptive"})
        self.assertEqual(pedido["output_config"], {"effort": "medium"})


if __name__ == "__main__":
    unittest.main()
