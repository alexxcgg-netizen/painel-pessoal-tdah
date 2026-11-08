"""Leva 08/11/2026, frente B item 14: o atalho local do chat (aprendizado.consulta_conhecida) so responde o que
foi perguntado.

Bug real da conversa: "que horas vou chegar em casa?" caia no card de horario livre (sugerir_horario_livre com
titulo "chegar em casa"). A varredura com ~60 frases achou a mesma familia em trajeto ("quando vou buscar...",
"qual o melhor horario pra sair?"), horario de compromisso ("que horas e o treino?" virava o historico de
treinos), lugar ("onde fica a academia?"), clima, conselho ("devo beber mais agua?" virava o card de saude),
"como fazer" ("como manter um habito?") e meta que nao e financeira ("qual minha meta de agua?").
Frases inventadas, sem rede, sem banco."""
import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado  # noqa: E402

VAO_PRA_IA = [
    # trajeto / ir e voltar / buscar alguem
    "que horas vou chegar em casa?",
    "que horas eu vou chegar la?",
    "que horas vou sair?",
    "como vou pra casa da Bia?",
    "como eu vou pro aeroclube?",
    "quando vou buscar o Leo?",
    "quando eu vou buscar a menina?",
    "que horas vou pra casa?",
    "que horas vou voltar pra casa?",
    "quando consigo chegar no shopping?",
    "qual o melhor horario pra sair?",
    "qual o melhor horario pra ir pra Itajai?",
    "como faco pra chegar no aeroporto?",
    "me mostra o caminho pra academia",
    "onde fica a academia?",
    # horario de compromisso / lugar
    "que horas e o treino?",
    "a que horas tenho academia?",
    "quando e a academia amanha?",
    "qual o horario da academia?",
    "a academia ta aberta?",
    "academia abre que horas?",
    "quanto custa a academia?",
    "quando vou ver a Ana?",
    "que horas vou almocar?",
    "que horas vou dormir?",
    "quando posso jantar com a Ana?",
    "qual o melhor horario pra ligar pra Ana?",
    "quando consigo me arrumar?",
    "quando posso ir no mercado?",
    "quando e a viagem?",
    "que dia e a viagem?",
    "como vai ser a viagem pra Floripa?",
    # treino de agora (comecar_treino, nao o historico)
    "qual meu treino de hoje?",
    "hoje e qual treino?",
    "que treino eu faco hoje?",
    "ver o treino de amanha",
    # conselho / como fazer / porque
    "devo beber mais agua?",
    "quanto de agua eu preciso beber?",
    "como manter um habito?",
    "como faco pra manter o habito de ler?",
    "como melhorar meu treino?",
    "qual o melhor treino pra ganhar massa?",
    "vale a pena ir na academia hoje?",
    "como funciona a meta?",
    "como faco o treino de peito?",
    "como faco pra estudar meteorologia?",
    "por que meus treinos cairam?",
    # meta que nao e a financeira
    "qual minha meta de agua?",
    "qual minha meta de proteina?",
]

# (frase, fonte esperada, titulo da sugestao quando for o card de horario livre)
CONTINUAM_LOCAIS = [
    ("como encaixo meu treino hoje?", "sugestao", "treino"),
    ("que horas eu vou pra academia hoje?", "sugestao", "academia"),
    ("que horas vou treinar?", "sugestao", "treinar"),
    ("que horas vou fazer academia?", "sugestao", "academia"),
    ("quando consigo estudar hoje?", "sugestao", "estudar"),
    ("quando consigo estudar pra prova?", "sugestao", "estudar pra prova"),
    ("quando faço o treino?", "sugestao", "treino"),
    ("quando da pra encaixar a corrida hoje?", "sugestao", "corrida"),
    ("quando posso ir pra academia?", "sugestao", "academia"),
    ("quando consigo arrumar o quarto?", "sugestao", "arrumar o quarto"),
    ("qual o melhor horario pra estudar?", "sugestao", "estudar"),
    ("como foram meus treinos nos ultimos 7 dias?", "treinos", None),
    ("como foi o treino de hoje?", "treinos", None),
    ("quando foi meu ultimo treino?", "treinos", None),
    ("qual foi meu último treino?", "treinos", None),
    ("quantos treinos fiz essa semana?", "treinos", None),
    ("como estao meus habitos?", "habitos", None),
    ("e ai, como tão meus hábitos?", "habitos", None),
    ("como ta minha saude hoje?", "saude_dia", None),
    ("quanta agua eu bebi hoje?", "saude_dia", None),
    ("mostra meus copos de agua", "saude_dia", None),
    ("Me mostra o projeto da viagem e a meta", "projeto", None),
    ("como vai o projeto reforma do quarto?", "projeto", None),
    ("como esta o projeto da casa?", "projeto", None),
    ("status da viagem", "projeto", None),
    ("quais minhas metas", "meta", None),
    ("quanto falta pra meta?", "meta", None),
]


class AtalhoLocalTestCase(unittest.TestCase):
    def test_pergunta_de_trajeto_compromisso_conselho_vai_pra_ia(self):
        for frase in VAO_PRA_IA:
            with self.subTest(frase=frase):
                self.assertIsNone(aprendizado.consulta_conhecida(frase), "o atalho responderia outra coisa")

    def test_trajeto_e_lugar_exigem_ia_tambem_no_padrao_aprendido(self):
        # exige_ia barra ate padrao aprendido (app._plano_local_chat): trajeto nunca vira consulta local
        for frase in ("que horas vou chegar em casa?", "quando vou buscar o Leo?", "onde fica a academia?",
                      "a academia ta aberta?", "quanto custa a academia?", "que horas vou sair?"):
            with self.subTest(frase=frase):
                self.assertTrue(aprendizado.exige_ia(frase))

    def test_atalhos_legitimos_continuam(self):
        for frase, fonte, titulo in CONTINUAM_LOCAIS:
            with self.subTest(frase=frase):
                plano = aprendizado.consulta_conhecida(frase)
                self.assertIsNotNone(plano, "era atalho legitimo")
                primeira = plano["parametros"]["fontes"][0]
                self.assertEqual(primeira["fonte"], fonte)
                if titulo:
                    self.assertEqual(primeira["titulo"], titulo)

    def test_copo_de_agua_continua_registrando(self):
        for frase in ("tomei um copo de agua", "bebi agua agora", "tomei água"):
            with self.subTest(frase=frase):
                self.assertEqual(aprendizado.consulta_conhecida(frase)["parametros"], {"campo": "hidratacao"})

    def test_lixo_nao_quebra(self):
        for lixo in (None, "", "   ", 123, "como", "que horas", "quando vou", "?" * 300, "como " * 50):
            with self.subTest(lixo=lixo):
                resultado = aprendizado.consulta_conhecida(lixo)
                self.assertTrue(resultado is None or resultado["acao"] in ("consultar", "registrar_checkin"))


class DicaDeSonoComTuTestCase(unittest.TestCase):
    def test_dica_fala_de_tu(self):
        from unittest.mock import patch

        medias = {"7h ou mais": 2.6, "menos de 6h": 1.4}
        with patch("aprendizado.media_checkin_por_faixa_sono", return_value=medias):
            dica = aprendizado.dica_sono_humor(None)
        self.assertTrue(dica.startswith("Pelo teu check-in, "))
        self.assertIn("teu humor", dica)
        self.assertIn("tua energia", dica)
        self.assertNotIn("seu", dica)


if __name__ == "__main__":
    unittest.main()
