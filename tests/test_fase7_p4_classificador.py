# Faixa P4 (Fase 7): classificador_local/regras/p4_regra.py - contrato de
# casar()/executar() (ver classificador_local/__init__.py e
# classificador_local/README.md), tanto chamando o modulo direto quanto via
# o dispatcher classificador_local.casar/executar (pra garantir que o
# arquivo real esta registrado e no formato certo).
import sqlite3
import unittest
from unittest.mock import patch

import classificador_local
from assistente import regras as motor
from classificador_local.regras import p4_regra


class TestCasarViaDispatcher(unittest.TestCase):
    """classificador_local.casar() varre classificador_local/regras/*.py de
    verdade - se p4_regra.py estiver no formato errado, o dispatcher pula
    ele (loga) e devolve None. Passar aqui prova que o arquivo real esta
    integrado certo, nao so o modulo isolado."""

    def test_reconhece_pedido_de_lembrete(self):
        resultado = classificador_local.casar("todo dia às 18h me lembra de tomar o remédio")
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["regra"], "p4_regra")
        self.assertEqual(resultado["acao"], "criar_regra")
        self.assertEqual(resultado["parametros"], {"texto": "todo dia às 18h me lembra de tomar o remédio"})

    def test_reconhece_pedido_de_aviso_de_gasto(self):
        resultado = classificador_local.casar("me avisa se gastar mais de 300 com mercado na semana")
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["regra"], "p4_regra")

    def test_frase_qualquer_nao_casa(self):
        self.assertIsNone(classificador_local.casar("qual o meu saldo no nubank?"))

    def test_texto_vazio_nao_casa(self):
        self.assertIsNone(classificador_local.casar(""))


class TestCasarDireto(unittest.TestCase):
    def test_variedade_de_frases_reconhecidas(self):
        frases = [
            "me avisa se eu gastar mais de 100 com farmacia",
            "me lembra de comprar pao quando eu passar no mercado",
            "me lembra sempre de tomar agua depois do treino",
            "todo dia me lembra de beber agua",
            "todo dia às 7h me lembra de tomar agua",
            "toda segunda às 9h me lembra de pagar o boleto",
            "todo sábado às 10h me lembra de lavar o carro",
        ]
        for frase in frases:
            with self.subTest(frase=frase):
                self.assertIsNotNone(p4_regra.casar(frase))

    def test_frases_nao_reconhecidas(self):
        frases = [
            "oi", "quanto eu gastei esse mes?", "cria uma tarefa pra amanha", "",
            # recorrencia sem pedido ao assistente: remedio/tarefa, fica com a IA
            "tenho que tomar Losartana 50mg todo dia as 8h",
            "tenho que tomar remedio todo dia as 8h",
            "academia toda segunda e quarta",
            # lembrete de uma vez so (sem repeticao nem condicao): a IA cria a tarefa
            "me lembra de tomar o remedio as 7",
            "me lembra de ligar pro contador",
            "me lembra de pagar o ipva dia 15",
            # brain dump: varias frases ou texto longo nunca vira uma regra so
            "Gastei 45 no mercado. Me lembra de renovar o CMA dia 1 de outubro.",
            "me lembra de " + "x" * 200,
            "me avisa se\nchover amanha",
        ]
        for frase in frases:
            with self.subTest(frase=frase):
                self.assertIsNone(p4_regra.casar(frase))

    def test_nao_e_string(self):
        self.assertIsNone(p4_regra.casar(None))
        self.assertIsNone(p4_regra.casar(123))


class TestExecutarCardDeConfirmacao(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def test_formato_simples_monta_card_sem_ia(self):
        from ia import core
        with patch.object(core, "chamar_ia") as mock_chamar:
            saida = p4_regra.executar(self.conn, {"texto": "todo dia às 18h me lembra de tomar o remédio"})
        mock_chamar.assert_not_called()

        self.assertEqual(len(saida["cards"]), 1)
        card = saida["cards"][0]
        self.assertEqual(card["type"], "p4_regra_confirmacao")
        self.assertEqual(card["data"]["gatilho"], "horario")
        self.assertEqual(card["data"]["interpretado_por"], "local")
        self.assertIn("Confirma?", saida["resumo_texto"])
        rotulos = {a["tipo"] for a in card["actions"]}
        self.assertEqual(rotulos, {"confirmar_regra", "cancelar_regra"})
        self.assertTrue(saida["passos"])

    def test_card_data_tem_tudo_que_a_rota_confirmar_precisa(self):
        saida = p4_regra.executar(self.conn, {"texto": "me avisa se gastar mais de 300 com mercado na semana"})
        data = saida["cards"][0]["data"]
        # rotas/p4_regras.py:confirmar espera exatamente estes campos.
        regra_reconstruida = {
            "gatilho": data["gatilho"], "condicao": data["condicao"],
            "acao": data["acao"], "texto": data["texto"],
        }
        motor.normalizar_regra(regra_reconstruida)  # nao pode levantar

    def test_recusa_regra_sobre_relacionamento_sem_card(self):
        saida = p4_regra.executar(self.conn, {"texto": "todo dia às 20h me lembra de ligar pro meu namorado"})
        self.assertEqual(saida["cards"], [])
        self.assertIn("vida amorosa", saida["resumo_texto"].lower())
        self.assertTrue(saida["passos"][0].get("erro"))

    def test_texto_vazio_nao_quebra(self):
        saida = p4_regra.executar(self.conn, {"texto": ""})
        self.assertEqual(saida["cards"], [])

    def test_parametros_vazios_nao_quebra(self):
        saida = p4_regra.executar(self.conn, {})
        self.assertEqual(saida["cards"], [])

    def test_via_dispatcher_executar_devolve_envelope_com_id_numerado(self):
        resultado = classificador_local.casar("todo dia às 18h me lembra de tomar o remédio")
        saida = classificador_local.executar(self.conn, resultado)
        self.assertIsNotNone(saida)
        self.assertEqual(saida["cards"][0]["id"], "c1")
        self.assertEqual(saida["cards"][0]["type"], "p4_regra_confirmacao")


if __name__ == "__main__":
    unittest.main()
