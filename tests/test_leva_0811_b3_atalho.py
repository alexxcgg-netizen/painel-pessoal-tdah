"""Leva 08/11, 3a rodada (frente B, itens 8 e 10): atalho local do chat (aprendizado.consulta_conhecida).

Item 8: horario livre com dia que nao e hoje ("que horas vou treinar amanha?") virava o card de HOJE - o plano
local nao manda dia pro sugerir_horario_livre, entao vai pra IA.
Item 10: consultas do banco local que a 1a rodada mandou pra IA por causa de atras*/fecha*/melhor/pior/precis*.
Essas palavras so derrubam o atalho quando nao e o estado dele num habito/treino/meta.
"""
import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado  # noqa: E402


def fontes(texto):
    r = aprendizado.consulta_conhecida(texto)
    if not r or r.get("acao") != "consultar":
        return r and r.get("acao")
    return [f["fonte"] for f in r["parametros"]["fontes"]]


class HorarioLivreDeOutroDiaTestCase(unittest.TestCase):
    def test_outro_dia_vai_pra_ia(self):
        for texto in ("que horas vou treinar amanhã?", "quando consigo estudar amanhã?", "que horas faço o treino sexta?",
                      "qual o melhor horário pra correr amanhã?", "que horas eu vou na academia amanhã?",
                      "quando dá pra encaixar a corrida amanhã?", "quando dá pra treinar depois de amanhã?",
                      "quando encaixo a corrida no fim de semana?", "que horas faço o treino dia 12?",
                      "quando consigo treinar semana que vem?", "quando consigo ler no sábado?"):
            with self.subTest(texto=texto):
                self.assertIsNone(aprendizado.consulta_conhecida(texto))

    def test_hoje_ou_sem_dia_continua_no_atalho(self):
        for texto, titulo in (("que horas faço o treino hoje?", "treino"), ("quando consigo estudar?", "estudar"),
                              ("como encaixo a leitura hoje?", "leitura"), ("quando vou pra academia?", "academia"),
                              ("qual o melhor horário pra estudar?", "estudar")):
            with self.subTest(texto=texto):
                r = aprendizado.consulta_conhecida(texto)
                self.assertEqual(r["parametros"]["fontes"], [{"fonte": "sugestao", "titulo": titulo}])


class ConsultaLocalComPalavraDeTrajetoTestCase(unittest.TestCase):
    def test_estado_dele_volta_pro_atalho(self):
        for texto, esperado in (
            ("tô atrasado nos hábitos?", ["habitos"]),
            ("quais hábitos tão atrasados?", ["habitos"]),
            ("qual hábito tá pior?", ["habitos"]),
            ("qual foi meu melhor treino?", ["treinos"]),
            ("quanto falta pra fechar a meta?", ["meta"]),
            ("preciso ver meus hábitos", ["habitos"]),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(fontes(texto), esperado)
                self.assertFalse(aprendizado.exige_ia(texto))

    def test_trajeto_lugar_e_conselho_continuam_na_ia(self):
        for texto in ("a academia fecha que horas?", "a academia fecha hoje?", "a academia tá fechada?",
                      "vou me atrasar pro treino?", "vou chegar atrasado no treino?", "tô atrasado?",
                      "a meta fecha quando?", "quanto falta pra fechar a fatura?",
                      "qual o melhor treino pra perder peso?", "é melhor treinar de manhã ou de noite?",
                      "qual hábito é melhor pra começar?", "preciso treinar mais?", "preciso melhorar meus hábitos?",
                      "preciso beber mais água?", "posso jogar uma água no carro?", "dá pra jogar uma agua no carro?"):
            with self.subTest(texto=texto):
                self.assertIsNone(aprendizado.consulta_conhecida(texto))

    def test_trajeto_sem_contexto_exige_ia(self):
        for texto in ("a academia fecha que horas?", "vou me atrasar pro treino?", "tô atrasado?",
                      "a meta fecha quando?"):
            with self.subTest(texto=texto):
                self.assertTrue(aprendizado.exige_ia(texto))

    def test_consultas_que_ja_iam_certo_seguem(self):
        for texto, esperado in (("como tá a meta?", ["meta"]), ("como vão os hábitos?", ["habitos"]),
                                ("como foi o treino de ontem?", ["treinos"]), ("mostra meus hábitos", ["habitos"]),
                                ("tomei um copo de água", "registrar_checkin")):
            with self.subTest(texto=texto):
                self.assertEqual(fontes(texto), esperado)


if __name__ == "__main__":
    unittest.main()
