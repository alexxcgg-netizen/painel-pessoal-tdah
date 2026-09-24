# Faixa P4 (Fase 7): interpretar_regra() - caminho que chama IA quando o
# parser local nao bate. IA SEMPRE mockada (ia.core.chamar_ia) - nenhuma
# chamada real, nenhuma credencial (ver docs/agentes/fase7-regras-faixa.md).
import unittest
from unittest.mock import patch

from assistente import regras as motor
from ia import core
from ia.contrato import Resposta


class TestInterpretarRegraUsaLocalPrimeiro(unittest.TestCase):
    def test_formato_simples_nao_chama_ia(self):
        with patch.object(core, "chamar_ia") as mock_chamar:
            resultado = motor.interpretar_regra("todo dia às 18h me lembra de tomar o remédio")
        mock_chamar.assert_not_called()
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["fonte"], "local")
        self.assertEqual(resultado["regra"]["gatilho"], "horario")


class TestInterpretarRegraViaIA(unittest.TestCase):
    def test_ia_devolve_regra_valida(self):
        resposta = Resposta(ok=True, dados={
            "gatilho": "habito_nao_feito_ate",
            "condicao": {"habito_nome": "Meditar", "hora": "20:00"},
            "acao": {},
            "texto": "me avisa se eu nao meditar ate as 20h",
        })
        with patch.object(core, "chamar_ia", return_value=resposta) as mock_chamar:
            resultado = motor.interpretar_regra("me avisa se eu nao meditar ate as 20h")
        mock_chamar.assert_called_once()
        args, kwargs = mock_chamar.call_args
        self.assertEqual(args[0], "interpretar_regra")
        self.assertIn("schema", kwargs)
        self.assertEqual(kwargs["schema"], motor.SCHEMA_INTERPRETAR_REGRA)
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["fonte"], "ia")
        self.assertEqual(resultado["regra"]["gatilho"], "habito_nao_feito_ate")
        self.assertEqual(resultado["regra"]["condicao"]["habito_nome"], "Meditar")

    def test_ia_devolve_tarefa_vencida(self):
        resposta = Resposta(ok=True, dados={
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": {},
            "texto": "me avisa quando eu tiver tarefa atrasada",
        })
        with patch.object(core, "chamar_ia", return_value=resposta):
            resultado = motor.interpretar_regra("me avisa quando eu tiver tarefa atrasada")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["regra"]["gatilho"], "tarefa_vencida")

    def test_ia_devolve_sinal_iphone(self):
        resposta = Resposta(ok=True, dados={
            "gatilho": "sinal_iphone",
            "condicao": {"tipo": "cheguei", "lugar": "trabalho"},
            "acao": {"mensagem": "chegou no trabalho!"},
            "texto": "me avisa quando eu chegar no trabalho",
        })
        with patch.object(core, "chamar_ia", return_value=resposta):
            resultado = motor.interpretar_regra("me avisa quando eu chegar no trabalho")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["regra"]["condicao"]["tipo"], "cheguei")

    def test_ia_falhou_ok_false(self):
        resposta = Resposta(ok=False, erro="teto_ia_estourado")
        with patch.object(core, "chamar_ia", return_value=resposta):
            resultado = motor.interpretar_regra("me avisa se eu gastar muito com viagens esse ano inteiro")
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["fonte"], "ia")
        self.assertEqual(resultado["erro"], "teto_ia_estourado")
        self.assertIsNone(resultado["regra"])

    def test_ia_devolve_json_fora_do_schema_vira_ok_false(self):
        # gatilho fora da lista fechada -> ia.core ja rejeita (schema), erro
        # de validacao volta em Resposta(ok=False).
        resposta = Resposta(ok=False, erro="openai/gpt-6-luna: JSON fora do schema ($.gatilho: "
                                            "'chute' fora de [...])")
        with patch.object(core, "chamar_ia", return_value=resposta):
            resultado = motor.interpretar_regra("faz alguma coisa estranha que eu nem sei descrever")
        self.assertFalse(resultado["ok"])
        self.assertIn("schema", resultado["erro"])

    def test_ia_devolve_condicao_invalida_para_o_gatilho(self):
        # Passa no schema solto do ia.core (gatilho valido, condicao e um
        # objeto) mas normalizar_regra rejeita porque falta valor_limite.
        resposta = Resposta(ok=True, dados={
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "mercado", "periodo": "semana"},
            "acao": {}, "texto": "x",
        })
        with patch.object(core, "chamar_ia", return_value=resposta):
            resultado = motor.interpretar_regra("me avisa se eu gastar litros de dinheiro com mercado")
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["fonte"], "ia")
        self.assertIn("valor_limite", resultado["erro"])

    def test_ia_recebe_texto_original_na_mensagem(self):
        resposta = Resposta(ok=True, dados={
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "x",
        })
        texto = "me avisa toda vez que uma tarefa vencer, por favor"
        with patch.object(core, "chamar_ia", return_value=resposta) as mock_chamar:
            motor.interpretar_regra(texto)
        mensagens = mock_chamar.call_args[0][1]
        self.assertEqual(mensagens, [{"role": "user", "content": texto}])


class TestInterpretarRegraCasosDegenerados(unittest.TestCase):
    def test_texto_vazio_nao_chama_ia(self):
        with patch.object(core, "chamar_ia") as mock_chamar:
            resultado = motor.interpretar_regra("")
        mock_chamar.assert_not_called()
        self.assertFalse(resultado["ok"])

    def test_texto_so_espacos(self):
        with patch.object(core, "chamar_ia") as mock_chamar:
            resultado = motor.interpretar_regra("     ")
        mock_chamar.assert_not_called()
        self.assertFalse(resultado["ok"])

    def test_none(self):
        with patch.object(core, "chamar_ia") as mock_chamar:
            resultado = motor.interpretar_regra(None)
        mock_chamar.assert_not_called()
        self.assertFalse(resultado["ok"])

    def test_ia_levanta_excecao_inesperada_nao_derruba_o_chamador(self):
        # ia.core.chamar_ia (real) nunca levanta por contrato, mas se algo
        # muito inesperado acontecer, interpretar_regra nao deve quebrar o
        # chat/captura - deixa subir (comportamento documentado: quem chama
        # decide o que fazer, mas nada aqui capturava Exception generica de
        # propósito, entao confirmamos que SO ValueError é tratada).
        with patch.object(core, "chamar_ia", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                motor.interpretar_regra("um pedido bem esquisito que nao bate em nada local")


class TestSchemaInterpretarRegra(unittest.TestCase):
    def test_schema_valida_exemplo_bom(self):
        from ia.core import validar_schema
        exemplo = {
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "mercado", "periodo": "semana", "valor_limite": 300},
            "acao": {},
            "texto": "me avisa se gastar mais de 300 com mercado na semana",
        }
        self.assertIsNone(validar_schema(exemplo, motor.SCHEMA_INTERPRETAR_REGRA))

    def test_schema_rejeita_gatilho_fora_da_lista(self):
        from ia.core import validar_schema
        exemplo = {"gatilho": "chute", "condicao": {}, "acao": {}, "texto": "x"}
        self.assertIsNotNone(validar_schema(exemplo, motor.SCHEMA_INTERPRETAR_REGRA))

    def test_schema_rejeita_campo_faltando(self):
        from ia.core import validar_schema
        exemplo = {"gatilho": "tarefa_vencida", "condicao": {}, "acao": {}}
        self.assertIsNotNone(validar_schema(exemplo, motor.SCHEMA_INTERPRETAR_REGRA))

    def test_schema_rejeita_campo_extra(self):
        from ia.core import validar_schema
        exemplo = {
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "x",
            "campo_que_nao_deveria_existir": True,
        }
        self.assertIsNotNone(validar_schema(exemplo, motor.SCHEMA_INTERPRETAR_REGRA))

    def test_config_ia_existe_e_carrega(self):
        # Regressao: se o JSON de ia/config.d/interpretar_regra.json estiver
        # mal formado, isto levanta ia.core.ConfigIAErro.
        config = core.carregar_todas_configs()
        self.assertIn("interpretar_regra", config)
        self.assertFalse(config["interpretar_regra"]["ativo"])
        self.assertEqual(config["interpretar_regra"]["modelo_atual"]["provedor"], "anthropic")


if __name__ == "__main__":
    unittest.main()
