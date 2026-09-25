"""Faixa uso/m5-parcela - aviso de cobranca de PARCELA (3/2/1 dia antes),
reusando o mesmo gatilho/mecanismo do aviso de assinatura
(assistente/gatilhos/f8_aviso_cobranca.py), so trocando a fonte de dado
(compra_parcelada + financas_recorrentes.parcela_info, em vez de
assinatura + proxima_cobranca_assinatura). Relogio sempre injetado (nunca
datetime.now()); banco sempre temporario."""

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402
import financas_recorrentes as fr  # noqa: E402
from assistente import avisos, caixa  # noqa: E402
from assistente.gatilhos import f8_aviso_cobranca  # noqa: E402

HOJE = date(2026, 9, 25)
AGORA = datetime(2026, 9, 25, 9, 0)


class _DbTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _criar_parcela(self, primeira_parcela, n_parcelas=10, valor_parcela=100.0,
                        descricao="Geladeira"):
        return fr.criar_compra_parcelada(
            self.conn, descricao, n_parcelas,
            valor_parcela=valor_parcela, primeira_parcela=primeira_parcela,
        )

    def _criar_assinatura(self, dia_cobranca, avisar=True, nome="Netflix"):
        aid = fr.criar_assinatura(self.conn, nome, 39.90, dia_cobranca, inicio="2026-01-01")
        if avisar:
            fr.atualizar_assinatura(self.conn, aid, avisar_antes_cobrar=True)
        return aid

    def _itens(self, subtipo=None):
        todos = [i for i in caixa.listar(self.conn) if i.get("origem", "").startswith("f8_aviso_cobranca:")]
        if subtipo is None:
            return todos
        return [i for i in todos if i["origem"] == f"f8_aviso_cobranca:{subtipo}"]


class TipoParcelaMapeadoTestCase(unittest.TestCase):
    def test_origem_parcela_mapeada_em_tipo_por_origem(self):
        self.assertEqual(avisos.TIPO_POR_ORIGEM.get(("f8_aviso_cobranca", "parcela")), "aviso_cobranca")

    def test_tipo_existe_no_catalogo(self):
        self.assertIn("aviso_cobranca", avisos.TIPOS)


class ParcelaAvisaSemFlagTestCase(_DbTestCase):
    """Parcela nao tem coluna "avisar_antes_cobrar" (decisao da faixa): a
    3a parcela de 10 (comecou em julho/2026, entao a de setembro e a
    3a) cobrando dia 28/09 -> 3 dias de hoje (25/09) -> avisa direto,
    sem precisar ligar nada."""

    def test_avisa_3_dias_antes(self):
        self._criar_parcela("2026-07-28", n_parcelas=10, valor_parcela=250.0, descricao="Geladeira")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens("parcela")
        self.assertEqual(len(itens), 1)
        titulo = itens[0]["titulo"]
        # "qual parcela" no texto: numero/total, descricao, valor e prazo.
        self.assertIn("Parcela 3/10", titulo)
        self.assertIn("Geladeira", titulo)
        self.assertIn("R$ 250.00", titulo)
        self.assertIn("em 3 dias", titulo)

    def test_avisa_2_dias_antes(self):
        self._criar_parcela("2026-09-27", n_parcelas=5, valor_parcela=80.0, descricao="Sofa")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens("parcela")
        self.assertEqual(len(itens), 1)
        self.assertIn("Parcela 1/5", itens[0]["titulo"])
        self.assertIn("em 2 dias", itens[0]["titulo"])

    def test_avisa_1_dia_antes_com_texto_amanha(self):
        self._criar_parcela("2026-09-26", n_parcelas=3, valor_parcela=60.0, descricao="Notebook")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens("parcela")
        self.assertEqual(len(itens), 1)
        self.assertIn("amanha", itens[0]["titulo"])

    def test_nao_avisa_4_dias_antes(self):
        self._criar_parcela("2026-09-29", n_parcelas=3, valor_parcela=60.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens("parcela"), [])

    def test_nao_avisa_no_dia_da_cobranca(self):
        self._criar_parcela("2026-09-25", n_parcelas=3, valor_parcela=60.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens("parcela"), [])


class NaoDuplicaTestCase(_DbTestCase):
    def test_rodar_de_novo_no_mesmo_dia_nao_duplica(self):
        self._criar_parcela("2026-09-28", n_parcelas=10, valor_parcela=100.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(len(self._itens("parcela")), 1)

    def test_rodar_de_novo_mais_tarde_no_mesmo_dia_nao_duplica(self):
        self._criar_parcela("2026-09-28", n_parcelas=10, valor_parcela=100.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, datetime(2026, 9, 25, 20, 0))
        self.assertEqual(len(self._itens("parcela")), 1)

    def test_dia_seguinte_com_novo_prazo_gera_aviso_novo_e_distinto(self):
        # 25/09: parcela cobra 28/09 -> 3 dias, avisa. 26/09: mesma parcela
        # (mesmo numero, mesma compra) agora a 2 dias -> aviso NOVO (chave
        # muda o numero de dias), nao repete o de "3 dias" de ontem.
        self._criar_parcela("2026-09-28", n_parcelas=10, valor_parcela=100.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, datetime(2026, 9, 26, 9, 0))
        itens = self._itens("parcela")
        self.assertEqual(len(itens), 2)

    def test_parcela_seguinte_da_mesma_compra_gera_aviso_proprio(self):
        # Parcela 1/2 comecando hoje (25/09), cobra dia 25 do mes que vem
        # (25/10) -> nao esta nos 3/2/1 dias ainda em setembro. Simula
        # virada de mes: no dia 22/10 (3 dias antes da 2a parcela), o
        # aviso tem que ser da parcela 2/2 - chave nao pode colidir com a
        # parcela 1 (que ja passou, nem chegou a avisar aqui de proposito).
        cid = self._criar_parcela("2026-09-25", n_parcelas=2, valor_parcela=50.0, descricao="Fone")
        f8_aviso_cobranca.executar(self.conn, datetime(2026, 10, 22, 9, 0))
        itens = self._itens("parcela")
        self.assertEqual(len(itens), 1)
        self.assertIn("Parcela 2/2", itens[0]["titulo"])
        info = fr.parcela_info(fr.obter_compra_parcelada(self.conn, cid), date(2026, 10, 22))
        self.assertEqual(info["parcela_atual_calculada"], 2)


class ParcelaQuitadaOuUltimaJaPagaNaoAvisaTestCase(_DbTestCase):
    def test_compra_de_parcela_unica_ja_quitada_nao_avisa(self):
        # 1 parcela so, comecou em julho -> em setembro ja quitou (mes
        # seguinte ao da unica parcela) - nao aparece nem em
        # listar_compras_parceladas(apenas_em_andamento=True).
        self._criar_parcela("2026-07-25", n_parcelas=1, valor_parcela=500.0)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens("parcela"), [])

    def test_ultima_parcela_ja_no_mes_seguinte_ao_termino_nao_avisa(self):
        # 2 parcelas, comecou em agosto -> setembro e o mes da ULTIMA
        # parcela (quitada so no mes seguinte, entao ainda "em andamento"
        # em setembro, mas se a cobranca dela (dia_cobranca) ja passou
        # nao ha proxima_cobranca futura pra essa compra).
        self._criar_parcela("2026-08-20", n_parcelas=2, valor_parcela=100.0)
        # dia 20 de setembro ja passou (hoje = 25/09) - proxima_cobranca do
        # mes corrente foi cravada no dia 20, no passado; ainda assim a
        # funcao so avisa 3/2/1 dias antes de uma data FUTURA, entao nao
        # deve gerar aviso hoje pra essa parcela (dias seria negativo).
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens("parcela"), [])


class AssinaturaContinuaAvisandoComoAntesTestCase(_DbTestCase):
    """Regressao: o mesmo executar() ainda avisa assinatura exatamente como
    antes de generalizar pra parcela (mesmo formato de titulo, mesma
    idempotencia, mesmo respeito ao interruptor por assinatura)."""

    def test_assinatura_com_flag_ligada_avisa_3_dias(self):
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens("assinatura")
        self.assertEqual(len(itens), 1)
        self.assertIn("Netflix cobra de novo em 3 dias", itens[0]["titulo"])

    def test_assinatura_sem_flag_nao_avisa(self):
        self._criar_assinatura(28, avisar=False, nome="Spotify")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens("assinatura"), [])

    def test_assinatura_e_parcela_juntas_nao_se_atrapalham(self):
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        self._criar_parcela("2026-07-28", n_parcelas=10, valor_parcela=250.0, descricao="Geladeira")
        resultado = f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(resultado["avisos_criados"], 2)
        self.assertEqual(len(self._itens("assinatura")), 1)
        self.assertEqual(len(self._itens("parcela")), 1)
        # Rodar de novo no mesmo dia nao duplica nenhuma das duas.
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(len(self._itens()), 2)


if __name__ == "__main__":
    unittest.main()
