"""Leva 08/11/2026, frente B: o que o revisor do chat confere em codigo (sem IA) - itens 1, 2, 3 e 6.

- "voce" com o Alex pede refazer (com ele e sempre "tu"); recado entre aspas ou pedido de mensagem nao conta.
- falar do sistema ("o card mostra", "a ferramenta de rota", "o painel calculou", nome de funcao) pede refazer.
- abertura igual a da resposta anterior: solta ("Beleza, ...") sai no codigo; verbo colado ("Anotei o X" de
  novo) pede refazer.
- "e so falar" / "me fala que eu ajusto" sai em qualquer ponto da ultima frase.
- "anotado/ajustei/passei/deixei/empurrei/ta riscado" sem gravar = afirmou sem fazer; "ja ta: ..." (reenvio) nao.
IA sempre mockada, frases inventadas."""

import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import revisor_chat as rv  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

NOITE = datetime(2026, 11, 8, 18, 0)
GRAVOU = [("registrar_tarefa", {"titulo": "Dentista"}, {"ok": True})]


def codigos(texto, chamadas=(), **kw):
    return [a["codigo"] for a in rv.revisar(texto, list(chamadas), NOITE, **kw)]


class TuNuncaVoceTestCase(unittest.TestCase):
    def test_voce_pede_refazer(self):
        for texto in ("Você sai 19h40 pra chegar 20h.", "Vc sai 19h40.", "Marquei pra você sexta 10h."):
            with self.subTest(texto=texto):
                self.assertIn("falou_voce", codigos(texto, GRAVOU))

    def test_tu_passa(self):
        self.assertEqual(codigos("Tu sai 19h40, chega 20h.", GRAVOU), [])

    def test_recado_entre_aspas_nao_conta(self):
        self.assertEqual(codigos('Manda assim: "Oi Joao, você consegue me pagar até sexta?"'), [])
        self.assertEqual(codigos("Manda assim: \u201cOi Joao, você consegue?\u201d"), [])

    def test_pedido_de_mensagem_pra_outra_pessoa_nao_conta(self):
        self.assertEqual(codigos("Oi Joao, você consegue me pagar até sexta?",
                                 mensagem="escreve uma mensagem pro Joao cobrando o Pix"), [])


class NaoFalaDoSistemaTestCase(unittest.TestCase):
    def test_falar_do_sistema_pede_refazer(self):
        for texto in ("O card mostra a rota inteira.", "A ferramenta de rota deu 25 min.",
                      "O painel calculou que tu sai 19h40.", "Chamei consultar_tarefas e não achei nada.",
                      "Registrei no sistema."):
            with self.subTest(texto=texto):
                self.assertIn("falou_do_sistema", codigos(texto))

    def test_palavra_parecida_nao_acusa(self):
        for texto in ("Leva as ferramentas pra obra amanhã.", "A pressão no sistema hidráulico cai.",
                      "O cardápio de hoje tem frango.", "Tu sai 19h40, dá 25 min até lá."):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto), [])

    def test_ele_perguntou_do_app(self):
        self.assertEqual(codigos("O card mostra a rota inteira.", mensagem="o que é esse card?"), [])


class AberturaRepetidaTestCase(unittest.TestCase):
    def test_abertura_solta_repetida_sai_no_codigo(self):
        self.assertEqual(rv.limpar("Beleza, marquei o dentista pra sexta às 10h.", "Beleza, anotei o mercado."),
                         "Marquei o dentista pra sexta às 10h.")
        self.assertEqual(rv.limpar("Fechado. Sexta tu sai 19h40.", "Fechado, ficou pra sábado."),
                         "Sexta tu sai 19h40.")
        self.assertEqual(rv.limpar("Anotei. Sexta 10h no dentista.", "Anotei o mercado pra amanhã."),
                         "Sexta 10h no dentista.")

    def test_abertura_diferente_ou_curta_fica(self):
        self.assertEqual(rv.limpar("Show, ficou pra sexta às 10h.", "Beleza, anotei."), "Show, ficou pra sexta às 10h.")
        self.assertEqual(rv.limpar("Beleza, marquei.", "Beleza, anotei."), "Beleza, marquei.")  # sobraria pouco
        self.assertEqual(rv.limpar("Beleza, marquei o dentista.", None), "Beleza, marquei o dentista.")

    def test_verbo_colado_repetido_pede_refazer(self):
        self.assertEqual(codigos("Anotei o dentista pra sexta às 10h.", GRAVOU, anterior="Anotei o mercado pra amanhã."),
                         ["abertura_repetida"])
        self.assertEqual(codigos("Anotei o dentista pra sexta às 10h.", GRAVOU, anterior="Marquei o mercado."), [])
        self.assertEqual(codigos("ok", anterior="ok"), [])  # resposta de uma palavra nao volta pro modelo


class OfertaNoFimTestCase(unittest.TestCase):
    def test_oferta_sai_de_qualquer_ponto_da_ultima_frase(self):
        casos = {
            "Botei às 18h15, 15 min depois da obra; se quiser outro horário é só falar.":
                "Botei às 18h15, 15 min depois da obra.",
            "Salvei a oficina: Auto Center Exemplo, R. Tal 123, Brusque - se não for essa, me fala.":
                "Salvei a oficina: Auto Center Exemplo, R. Tal 123, Brusque.",
            "Marquei sexta 10h. Qualquer coisa é só falar.": "Marquei sexta 10h.",
            "Marquei 10h. Se não der, me avisa que eu remarco.": "Marquei 10h.",
            "Sexta 10h, é só falar.": "Sexta 10h.",
            "Botei às 18h15 e se quiser outro horário é só falar.": "Botei às 18h15.",
            "Quinta: 8h30 dentista, 9h30 banco, 14h ligar pro Joao; muda o que quiser.":
                "Quinta: 8h30 dentista, 9h30 banco, 14h ligar pro Joao.",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(rv.limpar_fecho(texto), esperado)

    def test_pergunta_e_instrucao_ficam(self):
        for texto in ("Ficou pra sexta. Quer às 10h ou às 14h?", "Me fala se prefere 10h ou 14h.",
                      "Pra registrar o abastecimento é só mandar a foto da nota.",
                      "Tá marcado; é só chegar 10 min antes.", "Se quiser, eu marco."):
            with self.subTest(texto=texto):
                self.assertEqual(rv.limpar_fecho(texto), texto)


class AfirmouSemFazerAmpliadoTestCase(unittest.TestCase):
    def test_outros_jeitos_de_dizer_que_fez(self):
        for texto in ("Empurrei pra sexta.", "Ajustei o horário pra 15h.", "Passei o dentista pra quinta.",
                      "Deixei pra amanhã às 9h.", "Anotado: dentista sexta.", "Risquei o dentista."):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto), ["afirmou_sem_fazer"])

    def test_reenvio_ja_ta_nao_acusa(self):
        consultou = [("consultar_tarefas", {}, {"tarefas": [{"titulo": "Dentista"}]})]
        for texto, chamadas, mensagem in (
            ("Já tá: dentista sexta 10h.", (), ""),
            ("Já tá anotado o dentista.", (), ""),
            ("Já anotei antes, tá lá pra sexta.", (), ""),
            ("Tá anotado.", consultou, ""),
            ("Tá anotado sim, sexta 10h.", (), "anotou o dentista?"),
            # 3a rodada: "tá anotado/tá riscado" e estado, o "já tá" do reenvio
            ("Tá anotado o dentista pra sexta.", (), ""),
            ("Tá riscado.", (), ""),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(codigos(texto, chamadas, mensagem=mensagem), [])

    def test_com_ferramenta_que_grava_passa(self):
        self.assertEqual(codigos("Deixei pra quinta.", [("ajustar_tarefa", {}, {"ok": True})]), [])


# ---- no loop do chat -------------------------------------------------------------------------------


def _texto(t):
    return SimpleNamespace(type="text", text=t)


def _resp(blocos, stop_reason="end_turn"):
    uso = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0,
                          cache_creation_input_tokens=0)
    return SimpleNamespace(content=blocos, stop_reason=stop_reason, usage=uso, model="claude-haiku-5-5")


class LoopDoChatTestCase(unittest.TestCase):
    def _rodar(self, historico, respostas):
        enviados = []

        def criar(**kw):
            enviados.append(kw["messages"][-1])
            return respostas.pop(0)

        with patch.object(chat_mod, "_decidir_rota", return_value="padrao"), \
                patch.object(chat_mod.client.messages, "create", side_effect=criar):
            saida = chat_mod.chat(historico, "agora: 18:00", [], {})
        return saida, enviados

    def test_voce_volta_pro_modelo_uma_vez(self):
        historico = [{"role": "user", "content": "que horas eu saio pro jantar?"}]
        respostas = [_resp([_texto("Você sai 19h40 pra chegar 20h.")]), _resp([_texto("Tu sai 19h40, chega 20h.")])]
        (texto, _a, _u), enviados = self._rodar(historico, respostas)
        self.assertEqual(texto, "Tu sai 19h40, chega 20h.")
        nota = enviados[-1]["content"][0]["text"]
        self.assertIn('sempre "tu"', nota)
        self.assertIn("Não chama ferramenta de novo", nota)

    def test_abertura_solta_repetida_sai_sem_nova_chamada(self):
        historico = [
            {"role": "user", "content": "e o mercado?"},
            {"role": "assistant", "content": "Beleza, o mercado ficou pra amanhã às 9h."},
            {"role": "user", "content": "e a farmacia?"},
        ]
        respostas = [_resp([_texto("Beleza, a farmácia fecha às 22h, dá tempo hoje.")])]
        (texto, _a, _u), _e = self._rodar(historico, respostas)
        self.assertEqual(texto, "A farmácia fecha às 22h, dá tempo hoje.")
        self.assertEqual(respostas, [])

    def test_oferta_no_fim_sai_sem_nova_chamada(self):
        historico = [{"role": "user", "content": "quando passo no banco?"}]
        respostas = [_resp([_texto("Amanhã às 10h, o banco abre às 10h; se quiser outro horário é só falar.")])]
        (texto, _a, _u), _e = self._rodar(historico, respostas)
        self.assertEqual(texto, "Amanhã às 10h, o banco abre às 10h.")


if __name__ == "__main__":
    unittest.main()
