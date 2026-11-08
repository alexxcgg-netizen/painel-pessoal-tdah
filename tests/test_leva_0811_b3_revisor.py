"""Leva 08/11, 3a rodada (frente B, itens 3-7 e 9): falsos alarmes e cortes errados do revisor do chat.

Frases inventadas, parecidas com as do uso real. Na duvida o revisor nao acusa e o limpar nao corta.
"""
import os
import unittest
from datetime import datetime

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import revisor_chat as rv  # noqa: E402

AGORA = datetime(2026, 11, 3, 15, 0)
ABRE_SIMPLES, FECHA_SIMPLES = chr(0x2018), chr(0x2019)
ABRE_DUPLA, FECHA_DUPLA = chr(0x201C), chr(0x201D)


def codigos(texto, chamadas=(), anterior=None, mensagem=""):
    return [a["codigo"] for a in rv.revisar(texto, list(chamadas), AGORA, anterior=anterior, mensagem=mensagem)]


class AberturaSoCortaConfirmacaoTestCase(unittest.TestCase):
    """Item 3: limpar_abertura so tira a abertura repetida se ela for confirmacao (Beleza, Fechado, Pronto...)."""

    def test_conteudo_no_comeco_fica(self):
        for texto, anterior in (
            ("Amanhã: academia 18h e dentista 10h.", "Amanhã: voo às 8h, sai 7h10."),
            ("Dentista: sexta 10h, sai 9h35.", "Dentista: tá marcado pra sexta."),
            ("Sexta, 10h, dentista; sai 9h35.", "Sexta tu tem voo às 8h."),
            ("Hoje: 3 tarefas, a primeira às 14h.", "Hoje tu tem voo às 16h."),
            ("Fulana, 19h no restaurante; sai 18h20.", "Fulana chega 19h, tu sai 18h20."),
            ("Pronto pra amanhã: voo 8h, sai 7h10.", "Pronto, sexta 10h."),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(rv.limpar(texto, anterior), texto)

    def test_confirmacao_repetida_sai(self):
        for abertura in ("Beleza", "Fechado", "Pronto", "Feito", "Anotado", "Certo"):
            with self.subTest(abertura=abertura):
                texto = f"{abertura}, sexta 10h dentista e sai 9h35."
                self.assertEqual(rv.limpar(texto, f"{abertura}, anotei o voo."), "Sexta 10h dentista e sai 9h35.")


class OfertaSoNoFimTestCase(unittest.TestCase):
    """Item 4: "e so falar/avisar" so e oferta se a frase acaba ali ou segue com se/que."""

    def test_instrucao_fica(self):
        for texto in (
            "Pra reunião de amanhã, é só falar do orçamento e do prazo.",
            "Sai 19h40. Se atrasar, é só avisar a Fulana que ela espera.",
            "Sai 19h40. Na portaria é só dizer teu nome.",
            "No balcão da companhia é só pedir o reembolso, leva o comprovante.",
        ):
            with self.subTest(texto=texto):
                self.assertEqual(rv.limpar(texto), texto)

    def test_oferta_sai(self):
        for texto, esperado in (
            ("Dentista sexta 10h, é só falar se quiser mudar.", "Dentista sexta 10h."),
            ("Tudo certo pra sexta. É só me avisar.", "Tudo certo pra sexta."),
            ("Sai 19h40 e chega 20h, é só falar que eu ajusto.", "Sai 19h40 e chega 20h."),
            ("Botei às 18h15; se quiser outro horário é só falar.", "Botei às 18h15."),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(rv.limpar(texto), esperado)


class PontoDeMilharTestCase(unittest.TestCase):
    """Item 5: ponto entre digitos nao separa frase no corte da oferta."""

    def test_valor_com_ponto_de_milhar_fica_inteiro(self):
        self.assertEqual(rv.limpar("Gastou R$ 1.250 no mês, é só falar se quiser o detalhe."), "Gastou R$ 1.250 no mês.")
        self.assertEqual(rv.limpar("Sobra R$ 2.300,50. É só me avisar."), "Sobra R$ 2.300,50.")

    def test_frase_que_termina_em_numero_ainda_separa(self):
        self.assertEqual(rv.limpar("Sai 19h40. É só me avisar."), "Sai 19h40.")


class FalouVoceTestCase(unittest.TestCase):
    """Item 6: "voces" e plural de tu; recado pra outra pessoa nao conta."""

    def test_plural_nao_acusa(self):
        self.assertEqual(codigos("Vocês saem 19h40 pra pegar a sessão das 20h30.",
                                 mensagem="eu e a fulana vamos no cinema 20h30"), [])
        self.assertEqual(codigos("Vcs chegam 20h10.", mensagem="eu e o fulano vamos de carro"), [])

    def test_pedido_de_recado_nao_acusa(self):
        for mensagem in ("avisa a fulana que vou atrasar", "fala pra fulana que vou atrasar",
                         "diz pro fulano que não vou", "pergunta pra ela se você pode", "cobra o fulano do pix",
                         "como peço desculpa pra fulana", "como dizer não pro fulano"):
            with self.subTest(mensagem=mensagem):
                self.assertEqual(codigos("Oi, você pode me esperar uns 20 min?", mensagem=mensagem), [])

    def test_recado_entre_aspas_ou_depois_de_dois_pontos(self):
        for texto in (
            "Manda pra ela: Oi Fulana, vou atrasar uns 20 min, você me espera?",
            "Escreve assim: Oi, você consegue amanhã às 10h?",
            "Manda 'Oi Fulana, você me espera?' e sai 19h40.",
            f"Manda {ABRE_SIMPLES}Oi, você me espera?{FECHA_SIMPLES} e sai 19h40.",
            f"Manda {ABRE_DUPLA}Oi, você me espera?{FECHA_DUPLA} e sai 19h40.",
        ):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, mensagem="vou atrasar pro jantar"), [])

    def test_voce_com_ele_ainda_acusa(self):
        self.assertEqual(codigos("Você sai 19h40.", mensagem="que horas eu saio?"), ["falou_voce"])
        self.assertEqual(codigos("Vc sai 19h40.", mensagem="que horas eu saio?"), ["falou_voce"])


class AfirmouSemFazerTestCase(unittest.TestCase):
    """Item 7: negacao atravessa virgula, "passei o olho" nao e gravar, "ta anotado" e o "ja ta"."""

    def test_falsos_alarmes(self):
        consultou = [("consultar_agenda", {}, {"itens": []})]
        for texto, chamadas in (
            ("Não mexi, deixei como tava: sexta 10h.", ()),
            ("Não mexi; deixei como tava.", ()),
            ("Passei o olho na tua agenda: sexta tá livre depois das 14h.", consultou),
            ("Passei o olho na agenda e sexta tá livre.", ()),
            ("Tá anotado, sexta 10h.", ()),
            ("Está anotado pra sexta 10h.", ()),
            ("Deixei como tava.", ()),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, chamadas, mensagem="anota dentista sexta 10h"), [])

    def test_afirmacao_de_verdade_ainda_acusa(self):
        for texto in ("Passei pra sexta.", "Passei o dentista pra sexta.", "Deixei pras 10h.",
                      "Deixei o dentista pra amanhã.", "Anotei o dentista sexta 10h.", "Não, anotei pra sexta.",
                      "Anotado: dentista sexta."):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, mensagem="anota dentista sexta 10h"), ["afirmou_sem_fazer"])

    def test_nota_manda_conferir_antes_de_gravar_de_novo(self):
        achados = rv.revisar("Anotei o dentista.", [], AGORA, mensagem="anota dentista sexta 10h")
        nota = rv.nota_de_correcao(achados)
        self.assertIn("confere primeiro", nota)
        self.assertIn("já tá", nota)
        self.assertIn("não grava de novo", nota)
        self.assertNotIn("chama a ferramenta certa agora", nota)


class FalouDoSistemaTestCase(unittest.TestCase):
    """Item 9: "painel" tambem e o do aviao - so verbo que so o app faz."""

    def test_painel_do_aviao_nao_acusa(self):
        for texto in ("No 152 o painel mostra a velocidade em nós, não em km/h.",
                      "Quando o painel indica pane, tu segue o checklist.",
                      "O painel diz a altitude em pés."):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, mensagem="a velocidade no cessna é em nós ou km/h"), [])

    def test_painel_do_app_e_card_ainda_acusam(self):
        for texto in ("O painel calculou sair 19h40.", "O painel sugeriu 18h.", "O painel registrou o gasto.",
                      "O card mostra a rota.", "Usei a ferramenta de rota e dá 25 min."):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, mensagem="que horas eu saio pro jantar"), ["falou_do_sistema"])


if __name__ == "__main__":
    unittest.main()
