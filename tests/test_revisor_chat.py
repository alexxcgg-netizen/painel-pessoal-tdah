"""Revisor da resposta do chat (leva "agentes", 2026-11-05): checagens em código sobre conta de hora,
trajeto e "anotei" sem gravar, e a correção de 1 rodada no loop do chat. IA sempre mockada."""

import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import revisor_chat as rv  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

NOITE = datetime(2026, 11, 5, 18, 0)


def codigos(texto, chamadas=(), agora=NOITE):
    return [a["codigo"] for a in rv.revisar(texto, list(chamadas), agora)]


class AfirmouSemFazerTestCase(unittest.TestCase):
    def test_anotei_sem_ferramenta(self):
        self.assertEqual(codigos("Anotei o dentista pra sexta."), ["afirmou_sem_fazer"])

    def test_anotei_com_ferramenta_que_grava(self):
        feitas = [("registrar_tarefa", {"titulo": "dentista"}, {"ok": True})]
        self.assertEqual(codigos("Anotei o dentista pra sexta.", feitas), [])

    def test_so_consulta_nao_conta_como_gravar(self):
        feitas = [("consultar_tarefas", {}, {"tarefas": []})]
        self.assertEqual(codigos("Marquei pra amanhã.", feitas), ["afirmou_sem_fazer"])

    def test_ferramenta_que_deu_erro_nao_conta(self):
        feitas = [("registrar_gasto", {}, {"erro": "valor invalido"})]
        self.assertEqual(codigos("Registrei o gasto.", feitas), ["afirmou_sem_fazer"])

    def test_negacao_nao_acusa(self):
        self.assertEqual(codigos("Ainda não anotei nada, me diz o dia."), [])
        self.assertEqual(codigos("Não marquei porque falta a hora."), [])

    def test_conversa_sem_verbo_de_gravar(self):
        self.assertEqual(codigos("Dá tempo sim, o voo é só às 15h."), [])


class HoraDeSairTestCase(unittest.TestCase):
    PLANO = [("registrar_tarefa", {}, {"ok": True, "plano": {"sair_de_casa": "18:25", "comecar_a_se_arrumar": "17:40"}})]

    def test_hora_igual_ao_calculo(self):
        self.assertEqual(codigos("Marquei. Sai às 18:25 e começa a se arrumar às 17:40.", self.PLANO), [])
        self.assertEqual(codigos("Marquei, sai de casa 18h25.", self.PLANO), [])

    def test_hora_diferente_do_calculo(self):
        self.assertIn("saida_diferente_do_calculo", codigos("Marquei. Sai às 18:40.", self.PLANO))
        achado = rv.revisar("Marquei. Sai às 18:40.", self.PLANO, NOITE)[0]
        self.assertIn("18:25", achado["detalhe"])

    def test_arrumar_diferente(self):
        self.assertIn("arrumar_diferente_do_calculo", codigos("Marquei. Começa a se arrumar às 17h.", self.PLANO))

    def test_saida_que_ja_passou(self):
        self.assertEqual(codigos("Sai às 15h que dá tempo.", agora=datetime(2026, 11, 5, 16, 30)),
                         ["saida_no_passado"])

    def test_saida_no_passado_mas_de_outro_dia(self):
        self.assertEqual(codigos("Amanhã sai às 7h.", agora=datetime(2026, 11, 5, 16, 30)), [])
        self.assertEqual(codigos("Na sexta, sai às 7h30.", agora=datetime(2026, 11, 5, 16, 30)), [])

    def test_passado_dito_como_passado(self):
        self.assertEqual(codigos("Tu devia ter saído às 15h, agora vai pegar trânsito.",
                                 agora=datetime(2026, 11, 5, 16, 30)), [])

    def test_saida_futura(self):
        self.assertEqual(codigos("Sai às 19h.", agora=datetime(2026, 11, 5, 16, 30)), [])


class ContaDeIntervaloTestCase(unittest.TestCase):
    def test_conta_certa(self):
        self.assertEqual(codigos("Bloco de estudo das 14h às 16h (2 h)."), [])
        self.assertEqual(codigos("Das 9h às 10h30, são 1h e 30 min."), [])

    def test_conta_errada(self):
        self.assertEqual(codigos("Bloco de estudo das 14h às 16h (3 h)."), ["conta_de_intervalo"])
        self.assertEqual(codigos("Das 9:00 às 9:45 (90 min)."), ["conta_de_intervalo"])


class TrajetoTestCase(unittest.TestCase):
    ROTA = [("estimar_trajeto", {}, {"duracao_total_minutos": 45, "km": 38})]

    def test_trajeto_bate(self):
        self.assertEqual(codigos("São uns 45 min de carro.", self.ROTA), [])
        self.assertEqual(codigos("Leva 48 minutos de carro.", self.ROTA), [])

    def test_trajeto_errado(self):
        self.assertEqual(codigos("Leva uns 20 min de carro.", self.ROTA), ["trajeto_diferente"])

    def test_sem_rota_nesta_resposta_nao_julga(self):
        self.assertEqual(codigos("Leva uns 20 min de carro."), [])


class FechoDeRoboTestCase(unittest.TestCase):
    def test_tira_o_fecho(self):
        self.assertEqual(rv.limpar_fecho("Marquei o dentista pra sexta às 10h. Se quiser, eu te lembro antes."),
                         "Marquei o dentista pra sexta às 10h.")
        self.assertEqual(rv.limpar_fecho("Feito, ficou pra sexta às 10h.\n\nEspero ter ajudado!"),
                         "Feito, ficou pra sexta às 10h.")

    def test_mantem_pergunta_de_verdade(self):
        texto = "Ficou pra sexta. Quer às 10h ou às 14h?"
        self.assertEqual(rv.limpar_fecho(texto), texto)

    def test_nao_apaga_tudo(self):
        self.assertEqual(rv.limpar_fecho("Se quiser, eu marco."), "Se quiser, eu marco.")

    def test_fecho_no_meio_fica(self):
        texto = "Se quiser, dá pra ir de manhã. O voo é às 15h."
        self.assertEqual(rv.limpar_fecho(texto), texto)


# ---- no loop do chat -------------------------------------------------------------------------------


def _texto(t):
    return SimpleNamespace(type="text", text=t)


def _tool(nome, entrada, id_):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


def _resp(blocos, stop_reason="end_turn"):
    uso = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0,
                          cache_creation_input_tokens=0)
    return SimpleNamespace(content=blocos, stop_reason=stop_reason, usage=uso, model="claude-haiku-5-5")


class LoopDoChatTestCase(unittest.TestCase):
    def _rodar(self, respostas, executores=None):
        enviados = []

        def criar(**kw):
            enviados.append(kw["messages"][-1])
            return respostas.pop(0)

        historico = [{"role": "user", "content": "marca o jantar hoje às 20h no centro"}]
        with patch.object(chat_mod, "_decidir_rota", return_value="padrao"), \
                patch.object(chat_mod.client.messages, "create", side_effect=criar):
            saida = chat_mod.chat(historico, "agora: 18:00", [], executores or {})
        return saida, enviados

    def test_hora_errada_volta_pro_modelo_uma_vez(self):
        plano = {"ok": True, "plano": {"sair_de_casa": "19:35"}}
        respostas = [
            _resp([_tool("registrar_tarefa", {"titulo": "Jantar"}, "t1")], stop_reason="tool_use"),
            _resp([_texto("Marquei o jantar às 20h. Sai às 19:50.")]),
            _resp([_texto("Marquei o jantar às 20h. Sai às 19:35.")]),
        ]
        chamadas = []

        def registrar(entrada):
            chamadas.append(entrada)
            return plano

        (texto, acoes, _uso), enviados = self._rodar(respostas, {"registrar_tarefa": registrar})
        self.assertEqual(texto, "Marquei o jantar às 20h. Sai às 19:35.")
        self.assertEqual(acoes, ["registrar_tarefa"])
        self.assertEqual(len(chamadas), 1, "a correcao nao pode gravar de novo")
        nota = enviados[-1]["content"][0]["text"]
        self.assertIn("19:35", nota)
        self.assertIn("Não chama ferramenta de novo", nota)

    def test_corrige_so_uma_vez(self):
        respostas = [_resp([_texto("Anotei.")]), _resp([_texto("Anotei sim.")])]
        (texto, _a, _u), _e = self._rodar(respostas)
        self.assertEqual(texto, "Anotei sim.")
        self.assertEqual(respostas, [])

    def test_anotei_sem_gravar_deixa_chamar_a_ferramenta(self):
        respostas = [
            _resp([_texto("Anotei o jantar.")]),
            _resp([_tool("registrar_tarefa", {"titulo": "Jantar"}, "t1")], stop_reason="tool_use"),
            _resp([_texto("Anotei o jantar pra hoje às 20h.")]),
        ]
        (texto, acoes, _u), enviados = self._rodar(respostas, {"registrar_tarefa": lambda e: {"ok": True}})
        self.assertEqual(acoes, ["registrar_tarefa"])
        self.assertEqual(texto, "Anotei o jantar pra hoje às 20h.")
        self.assertNotIn("Não chama ferramenta de novo", enviados[1]["content"][0]["text"])

    def test_resposta_certa_nao_gasta_rodada(self):
        respostas = [_resp([_texto("Dá tempo, o jantar é só às 20h.")])]
        (texto, _a, _u), _e = self._rodar(respostas)
        self.assertEqual(texto, "Dá tempo, o jantar é só às 20h.")

    def test_fecho_de_robo_sai_sem_nova_chamada(self):
        respostas = [_resp([_texto("O jantar é às 20h. Se quiser, eu te lembro antes.")])]
        (texto, _a, _u), _e = self._rodar(respostas)
        self.assertEqual(texto, "O jantar é às 20h.")


class RoteadorTestCase(unittest.TestCase):
    """Buracos do roteador achados na leitura de 30 dias (2026-11-05)."""

    def test_opiniao_e_planejar_o_dia_vao_pro_modelo_de_conversa(self):
        from ia import roteador_chat as r
        for m in ("o que tu acha?", "tu acha que dá tempo?", "me ajuda a planejar o dia",
                  "reorganiza meu dia", "monta minha tarde"):
            with self.subTest(m=m):
                self.assertTrue(r.e_conversa(m))
        for m in ("marca dentista amanhã às 10h", "gastei 50 no mercado", "anota: planejar o dia"):
            with self.subTest(m=m):
                self.assertFalse(r.e_conversa(m))

    def test_pergunta_curta_depois_de_conversa_nao_troca_de_modelo(self):
        from ia import roteador_chat as r
        self.assertTrue(r.e_continuacao("chego que horas?", "me ajuda a planejar o dia"))
        self.assertFalse(r.e_continuacao("chego que horas?", "gastei 50 no mercado"))
        self.assertFalse(r.e_continuacao("marca às 19?", "reorganiza meu dia"))
        self.assertFalse(r.e_continuacao("ok, valeu", "me ajuda a planejar o dia"))
        self.assertFalse(r.e_continuacao("chego que horas?", None))


if __name__ == "__main__":
    unittest.main()
