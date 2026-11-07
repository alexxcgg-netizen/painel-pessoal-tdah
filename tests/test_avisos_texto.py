"""Catalogo de textos dos avisos (avisos_texto.py, leva 07/11/2026 frente C): estilo C "Amigo" com "tu",
cabe na tela bloqueada, com acento, varia por contexto sem repetir a ultima e fica estavel por aviso.
Banco temporario; sem rede."""
import os
import random
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import avisos_texto as at  # noqa: E402
import notificacoes  # noqa: E402

# forma sem acento que nao pode aparecer (o Alex le com acento)
SEM_ACENTO = re.compile(r"\b(voce|nao|ja|ta|tao|amanha|agua|proxim\w*|ate|so|la|ai|esta|horario|previsao|transito|"
                        r"sequencia|manha|area|onibus|voo é)\b", re.I)
LONGO = {"nome": "Jantar de aniversário da Júlia no restaurante novo do centro", "lugar": "Shopping Center Gracher de Brusque",
         "parada": "casa da vó lá do outro lado da cidade", "coisa": "Estudar meteorologia pro teórico",
         "meta": "Juntar dinheiro pra viagem de fim de ano"}


def _todas():
    for assunto, c in at.CATALOGO.items():
        ex = c["exemplo"]
        padrao = (ex.get("titulo_padrao", ""), ex.get("corpo_padrao", ""))
        for i, v in enumerate(c["variacoes"]):
            yield assunto, i, v, at._render(v, ex, padrao, classica=at._classica(assunto, i))


class CatalogoTestCase(unittest.TestCase):
    def test_cada_assunto_tem_de_4_a_8_variacoes_e_emoji(self):
        for assunto, c in at.CATALOGO.items():
            self.assertTrue(4 <= len(c["variacoes"]) <= 8, assunto)
            self.assertTrue(at.emoji_do_tipo(c["tipo"]), f"{assunto}: tipo {c['tipo']} sem emoji")

    def test_toda_variacao_cabe_na_tela_bloqueada(self):
        for assunto, i, _, r in _todas():
            with self.subTest(assunto=assunto, i=i):
                self.assertIsNotNone(r, "exemplo sem os dados do template")
                titulo, corpo = r
                self.assertTrue(titulo, "titulo vazio")
                self.assertLessEqual(len(titulo), at.TITULO_LIM, titulo)
                self.assertLessEqual(len(corpo), at.CORPO_LIM, corpo)
                self.assertNotIn("\n", titulo + corpo)

    def test_fala_com_tu_com_acento_e_sem_emoji_no_texto(self):
        for assunto, i, _, (titulo, corpo) in _todas():
            with self.subTest(assunto=assunto, i=i):
                texto = f"{titulo} {corpo}"
                self.assertNotRegex(texto.lower(), r"\bvoc[eê]s?\b")
                self.assertIsNone(SEM_ACENTO.search(texto), texto)
                self.assertFalse(any(ord(ch) > 0x2600 for ch in texto), f"emoji no texto: {texto}")

    def test_nome_comprido_nunca_estoura_nas_variacoes_novas(self):
        for assunto, c in at.CATALOGO.items():
            dados = {**c["exemplo"], **{k: v for k, v in LONGO.items() if k in c["exemplo"]}}
            padrao = (dados.get("titulo_padrao", ""), dados.get("corpo_padrao", ""))
            for _ in range(30):
                i = at.escolher(assunto, dados, {"hora": 20, "chuva": True, "feitos_hoje": 5}, ultima=None,
                                rng=random.Random(_), padrao=padrao)
                if at._classica(assunto, i):
                    continue  # a classica do legado e o texto de antes (sem encurtar)
                t, corpo = at._render(c["variacoes"][i], dados, padrao)
                self.assertTrue(at.cabe(t, corpo), (assunto, i, t, corpo))

    def test_sem_conn_e_o_texto_de_antes(self):
        self.assertEqual(notificacoes.texto_tarefa_chegando("15:00", antes=True),
                         "Daqui a pouco, às 15:00. Vai fechando o que tá fazendo, sem correr.")
        self.assertEqual(notificacoes.texto_tarefa_chegando("15:00", antes=False), "Combinamos 15:00. Quando fizer, toca em Feito.")
        self.assertEqual(notificacoes.texto_tarefa_agora("15:00"), "Deu 15:00, é agora. Quando terminar, toca em Feito.")
        self.assertEqual(notificacoes.texto_tarefa_preparo("15:00", 30),
                         "Às 15:00, faltam 30 min. Dá pra fechar o que tá fazendo com calma.")

    def test_exemplos_exporta_tudo(self):
        ex = at.exemplos()
        self.assertEqual(set(ex), set(at.CATALOGO))
        self.assertTrue(all(v["variacoes"][0]["classica"] for v in ex.values()))
        self.assertTrue(ex["lugar_fechado"]["variacoes"][0]["titulo"].startswith("🚪 "))


class EscolhaTestCase(unittest.TestCase):
    def test_contexto_forte_ganha_e_hora_do_dia_filtra(self):
        dados = {"nome": "Date", "hora": "20:00", "min": 40, "sai": "19:45"}
        chuva = [i for i, v in enumerate(at.CATALOGO["se_arrumar"]["variacoes"]) if v["se"] == "chuva"]
        noite = [i for i, v in enumerate(at.CATALOGO["se_arrumar"]["variacoes"]) if v["se"] == "noite"]
        self.assertEqual(at.escolher("se_arrumar", dados, {"hora": 19, "chuva": True}, ultima=0), chuva[0])
        rng = random.Random(1)
        vistos = {at.escolher("se_arrumar", dados, {"hora": 10}, ultima=None, rng=rng) for _ in range(200)}
        self.assertFalse(vistos & set(noite + chuva))  # de manha sem chuva: nem a da noite nem a da chuva
        self.assertGreater(len(vistos), 2)

    def test_nunca_repete_a_ultima(self):
        rng = random.Random(7)
        ultima = None
        for _ in range(100):
            i = at.escolher("tarefa_agora", {"hora": "15:00"}, {"hora": 15}, ultima=ultima, rng=rng)
            self.assertNotEqual(i, ultima)
            ultima = i

    def test_sem_dado_a_variacao_nao_entra(self):
        # sem trajeto, as de hora_de_sair que precisam dele nao servem: cai na classica
        self.assertEqual(at.escolher("hora_de_sair", {"nome": "Date", "hora": "20:00"}, {"hora": 19}, ultima=0), 0)


class MemoriaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)

    def test_primeira_e_classica_depois_varia_sem_repetir_e_estavel_por_chave(self):
        dados = {"hora": "15:00"}
        t1 = at.texto("tarefa_agora", dados, conn=self.conn, chave="tarefa_agora-1-2026-11-07", ctx={"hora": 15})
        self.assertEqual(t1[1], "Deu 15:00, é agora. Quando terminar, toca em Feito.")
        anterior = t1
        for n in range(2, 25):
            t = at.texto("tarefa_agora", dados, conn=self.conn, chave=f"tarefa_agora-{n}-2026-11-07", ctx={"hora": 15})
            self.assertNotEqual(t, anterior)
            anterior = t
        # o mesmo aviso (sincronizada de novo do app / push do servidor) mantem o texto
        de_novo = at.texto("tarefa_agora", dados, conn=self.conn, chave="tarefa_agora-24-2026-11-07", ctx={"hora": 15})
        self.assertEqual(de_novo, anterior)

    def test_geradores_com_conn_variam(self):
        corpos = {notificacoes.texto_tarefa_chegando("15:00", True, conn=self.conn, chave=f"k{n}") for n in range(12)}
        self.assertGreater(len(corpos), 2)
        self.assertTrue(all(len(c) <= at.CORPO_LIM for c in corpos))

    def test_variar_titulo_so_no_generico(self):
        primeiro = at.variar_titulo(self.conn, "agua_pausa", "Bora uma água?", "corpo", chave="a1")
        self.assertEqual(primeiro, ("Bora uma água?", "corpo"))
        segundo = at.variar_titulo(self.conn, "agua_pausa", "Bora uma água?", "corpo", chave="a2")
        self.assertNotEqual(segundo[0], "Bora uma água?")
        self.assertEqual(segundo[1], "corpo")
        self.assertEqual(at.variar_titulo(self.conn, "agua_pausa", "De novo · Bora uma água?", "c", chave="a3"),
                         ("De novo · Bora uma água?", "c"))
        self.assertEqual(at.variar_titulo(self.conn, "gasto_elevado", "Gasto da semana", "c"), ("Gasto da semana", "c"))

    def test_lugar_fechado_pra_frente_d(self):
        t, c = at.lugar_fechado(self.conn, "Shopping", "21:40", abre="10:00", chave="lf-1")
        self.assertEqual((t, c), ("Ó, Shopping tá fechado", "Tu chegaria às 21:40 e ele tá fechado. Abre às 10:00."))
        self.assertEqual(notificacoes.com_emoji("lugar_fechado", t), "🚪 Ó, Shopping tá fechado")
        t, c = at.lugar_fechado(self.conn, "Banco", "15:40", fecha="16:00", chave="lf-2")
        self.assertIn("16:00", t + c)
        t, c = at.lugar_fechado(self.conn, "Padaria do Zé", temporario=True, chave="lf-3")
        self.assertIn("Padaria", t + c)
        t, c = at.lugar_fechado(None, "Cartório", "18:30")
        self.assertIn("18:30", c)
        for t, c in (at.lugar_fechado(self.conn, LONGO["lugar"], "21:40", abre="10:00", chave=f"x{n}") for n in range(8)):
            self.assertLessEqual(len(t), at.TITULO_LIM)
            self.assertLessEqual(len(c), at.CORPO_LIM)


if __name__ == "__main__":
    unittest.main()
