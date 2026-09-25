"""Fase 8, faixa F3 - testes de assistente/gatilhos/f8_aviso_cobranca.py:
padrao desligado nao avisa; ligado avisa em 3/2/1 dia (idempotente); outro
dia nao avisa; e a rota de toggle persiste. Relogio sempre injetado (nunca
datetime.now())."""

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

    def _criar_assinatura(self, dia_cobranca, avisar=False, nome="Netflix"):
        aid = fr.criar_assinatura(self.conn, nome, 39.90, dia_cobranca, inicio="2026-01-01")
        if avisar:
            fr.atualizar_assinatura(self.conn, aid, avisar_antes_cobrar=True)
        return aid

    def _itens_aviso_cobranca(self):
        return [i for i in caixa.listar(self.conn) if i.get("origem", "").startswith("f8_aviso_cobranca:")]


class TipoRegistradoTestCase(unittest.TestCase):
    def test_origem_mapeada_em_tipo_por_origem(self):
        self.assertEqual(avisos.TIPO_POR_ORIGEM.get(("f8_aviso_cobranca", "assinatura")), "aviso_cobranca")

    def test_tipo_existe_no_catalogo(self):
        self.assertIn("aviso_cobranca", avisos.TIPOS)


class PadraoDesligadoTestCase(_DbTestCase):
    def test_assinatura_recem_criada_nao_avisa(self):
        # cobra dia 28 -> 3 dias de HOJE (25/09) - mas o interruptor esta
        # desligado por padrao (0), entao nao deve avisar.
        self._criar_assinatura(28, avisar=False)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens_aviso_cobranca(), [])


class AvisaQuandoLigadoTestCase(_DbTestCase):
    def test_avisa_3_dias_antes(self):
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens_aviso_cobranca()
        self.assertEqual(len(itens), 1)
        self.assertIn("Netflix cobra de novo em 3 dias", itens[0]["titulo"])

    def test_avisa_2_dias_antes(self):
        self._criar_assinatura(27, avisar=True, nome="Spotify")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens_aviso_cobranca()
        self.assertEqual(len(itens), 1)
        self.assertIn("Spotify cobra de novo em 2 dias", itens[0]["titulo"])

    def test_avisa_1_dia_antes_com_texto_amanha(self):
        self._criar_assinatura(26, avisar=True, nome="iCloud")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        itens = self._itens_aviso_cobranca()
        self.assertEqual(len(itens), 1)
        self.assertIn("iCloud cobra de novo amanha", itens[0]["titulo"])

    def test_nao_avisa_4_dias_antes(self):
        self._criar_assinatura(29, avisar=True)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens_aviso_cobranca(), [])

    def test_nao_avisa_no_dia_da_cobranca(self):
        self._criar_assinatura(25, avisar=True)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(self._itens_aviso_cobranca(), [])

    def test_nao_repete_no_mesmo_ciclo(self):
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, AGORA)
        self.assertEqual(len(self._itens_aviso_cobranca()), 1)

    def test_nao_repete_rodando_de_novo_no_mesmo_dia_mais_tarde(self):
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, datetime(2026, 9, 25, 20, 0))
        self.assertEqual(len(self._itens_aviso_cobranca()), 1)

    def test_dia_seguinte_com_novo_prazo_gera_novo_aviso_distinto(self):
        # 26/09, cobranca dia 28 -> agora sao 2 dias, nao repete o aviso de
        # "3 dias" de ontem, cria um NOVO (chave inclui os dias).
        self._criar_assinatura(28, avisar=True, nome="Netflix")
        f8_aviso_cobranca.executar(self.conn, AGORA)
        f8_aviso_cobranca.executar(self.conn, datetime(2026, 9, 26, 9, 0))
        itens = self._itens_aviso_cobranca()
        self.assertEqual(len(itens), 2)


class ToggleRotaTestCase(_DbTestCase):
    def test_atualizar_assinatura_liga_e_persiste(self):
        aid = self._criar_assinatura(28, avisar=False)
        a_antes = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a_antes["avisar_antes_cobrar"], 0)
        fr.atualizar_assinatura(self.conn, aid, avisar_antes_cobrar=True)
        a_depois = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a_depois["avisar_antes_cobrar"], 1)

    def test_desligar_de_novo_persiste(self):
        aid = self._criar_assinatura(28, avisar=True)
        fr.atualizar_assinatura(self.conn, aid, avisar_antes_cobrar=False)
        a = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a["avisar_antes_cobrar"], 0)


if __name__ == "__main__":
    unittest.main()
