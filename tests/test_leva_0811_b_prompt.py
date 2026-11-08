"""Leva 08/11/2026, frente B: regras de jeito de falar no prompt do chat (itens 1, 2, 4 a 12) e o exemplo da
limpeza da fala (item 15). Confere so o texto fixo - o comportamento de verdade e do modelo (mockado nos outros
testes). Sem rede, sem banco."""
import os
import re
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia.funcoes import chat as chat_mod  # noqa: E402
from ia.funcoes import fala  # noqa: E402

P = chat_mod.CHAT_SYSTEM_PROMPT
P1 = " ".join(P.split())  # sem quebra de linha, pra procurar frase que atravessa linha


def _exemplos_entre_aspas(texto):
    return re.findall(r'"([^"]{0,240})"', texto)


class JeitoDeFalarTestCase(unittest.TestCase):
    def test_tu_e_a_primeira_regra_do_jeito_de_falar(self):
        bloco = P[P.index("JEITO DE FALAR"):]
        primeira = bloco[bloco.index("\n- "):].split("\n- ")[1]
        self.assertIn('SEMPRE "tu"', primeira)
        self.assertIn('NUNCA "voce", "seu", "sua"', primeira)
        self.assertIn('"tu"', chat_mod.CHAT_SIMPLES_PROMPT)

    def test_exemplo_de_fala_nao_usa_voce_nem_seu(self):
        # o unico com "seu" e o exemplo do que e proibido
        for exemplo in _exemplos_entre_aspas(P):
            if re.search(r"\b(?:seu|sua|voce)\b", exemplo) and len(exemplo.split()) > 2:
                self.assertIn("adicionei a tarefa X ao seu painel", exemplo)

    def test_sem_exemplo_que_semeia_anotei_ou_e_so_falar(self):
        for exemplo in _exemplos_entre_aspas(P):
            with self.subTest(exemplo=exemplo):
                self.assertIsNone(re.match(r"\s*anotei\b", exemplo, re.IGNORECASE), "exemplo comecando com Anotei")
        # "e so falar" / "me fala que eu ajusto" so aparecem uma vez: na lista do que e proibido
        self.assertEqual(len(re.findall(r"\be so falar\b", P1)), 1)
        self.assertEqual(P1.count("me fala que eu ajusto"), 1)
        self.assertNotIn("muda o que quiser", P)
        self.assertNotIn("se nao for essa, me fala", P1)
        self.assertNotIn("e que da pra mudar", P1)
        self.assertIn('"e so falar", "me fala que eu ajusto"', P1)  # agora na lista do proibido

    def test_oq_nao_entendi_repete(self):
        self.assertIn('"oq?", "o que?", "nao entendi", "repete"', P1)
        self.assertIn("sem ferramenta e sem se defender", P1)

    def test_vale_a_pena_veredito_primeiro_sem_lista(self):
        regra = P1[P1.index("VALE A PENA / COMPENSA"):][:500]
        self.assertIn("VEREDITO vem na PRIMEIRA frase", regra)
        self.assertIn("so se ele pedir ou se nao estiver com pressa", regra)
        self.assertIn("sem lista", regra)
        self.assertNotIn("em listas de ate 4 itens", P1)

    def test_reenvio_ja_ta(self):
        self.assertIn("MENSAGEM REENVIADA", P)
        self.assertIn('diga "ja ta: ..."', P1)
        self.assertIn('nem "antes nao tinha feito"', P1)

    def test_horario_relativo_vale_pra_ultima_coisa(self):
        regra = P1[P1.index("HORARIO SOLTO LOGO DEPOIS"):][:700]
        for trecho in ('"daqui 10 min"', '"em meia hora"', '"depois da janta"', "da ultima coisa dita"):
            self.assertIn(trecho, regra)

    def test_aviso_de_se_arrumar_mostra_horarios(self):
        regra = P1[P1.index("MARCA O AVISO DE SE ARRUMAR"):][:400]
        self.assertIn('nao responda que "dispara sozinho"', regra)
        self.assertIn("consultar_agenda", regra)
        self.assertIn("se arrumar 19h05 · sai 19h45 · chega 20h", regra)

    def test_atraso_dito_refaz_e_ajusta(self):
        regra = P1[P1.index("ATRASO DITO"):][:500]
        self.assertIn('"vou atrasar 20 min"', regra)
        self.assertIn("tempo de se arrumar", regra)
        self.assertIn("`ajustar_tarefa` no proximo compromisso", regra)
        self.assertIn("diga a hora nova", regra)

    def test_ligar_falar_cobrar_cria_antes_de_perguntar(self):
        self.assertIn("Ligar/falar/cobrar alguem", P1)
        self.assertIn("so depois pergunte o que faltar", P1)

    def test_plano_que_ele_anunciou_nao_muda_sozinho(self):
        self.assertIn("PLANO QUE ELE ANUNCIOU manda", P1)
        self.assertIn("avise em UMA frase e siga o plano dele", P1)
        self.assertIn("sem sugerir refazer depois", P1)  # rodada com a IA de verdade: listava o que dava errado

    def test_baixa_pelo_que_ele_conta(self):
        for trecho in ('"sai do cartorio"', '"ja fiz o pix"', '"depositei"', '"Fui mas nao deu"'):
            self.assertIn(trecho, P1)
        self.assertIn("tambem nao conclui", P1)

    def test_regras_que_outros_testes_conferem_continuam(self):
        for trecho in ("REGRA DE FONTE UNICA", "HORARIO QUE ELE NAO DISSE", "LISTA DE TAREFAS SEM DIA",
                       "BAIXA PELO QUE ELE CONTA", "A CAMINHO NAO E FEITO", "LUGARES QUE ELE ENSINA",
                       "TAREFA COM DIA GANHA HORA", "HORA DE SAIR OU DE CHEGAR"):
            self.assertIn(trecho, P)

    def test_prompt_fixo_sem_nada_dinamico(self):
        # cache do prompt: so {hoje} e {memorias} variam
        self.assertEqual(sorted(set(re.findall(r"\{(\w+)\}", P))), ["hoje", "memorias"])


class LimpezaDaFalaTestCase(unittest.TestCase):
    def test_justo_os_horarios_e_ajusta(self):
        self.assertIn('"Justo os horários" / "Juste os horários" = "Ajusta os horários"', fala.PROMPT_LIMPAR_FALA)


if __name__ == "__main__":
    unittest.main()
