import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
import ia.medicao as medicao
import ia.teto as teto


class _BaseTetoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self._cambio = medicao.cambio_usd_brl()

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _gastar_brl(self, valor_brl: float, funcao: str = "chat"):
        """Registra uso de IA cujo custo, convertido pelo cambio atual, bate
        exatamente com `valor_brl` - facilita montar cenarios de fracao do
        teto sem depender do valor exato do cambio."""
        custo_usd = valor_brl / self._cambio
        medicao.registrar_uso(funcao, "anthropic", "claude-sonnet-5", custo_usd=custo_usd)


class NivelAlertaPadraoTestCase(_BaseTetoTestCase):
    """Sem nenhum teto configurado pelo card financeiro (db.obter_teto_mensal_ia
    is None) - teto.py cai no padrao de R$40/mes da Fase 7."""

    def test_sem_gasto_nenhum_e_normal(self):
        self.assertEqual(teto.nivel_alerta(), "normal")

    def test_teto_padrao_e_40_reais(self):
        self.assertEqual(teto._teto_mensal_brl(), teto.TETO_PADRAO_BRL)
        self.assertEqual(teto.TETO_PADRAO_BRL, 40.0)

    def test_gasto_abaixo_de_80_por_cento_e_normal(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.5)
        self.assertEqual(teto.nivel_alerta(), "normal")

    def test_gasto_logo_abaixo_de_80_por_cento_ainda_e_normal(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.79)
        self.assertEqual(teto.nivel_alerta(), "normal")

    def test_gasto_exatamente_80_por_cento_e_aviso(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.8)
        self.assertEqual(teto.nivel_alerta(), "aviso_80")

    def test_gasto_entre_80_e_100_por_cento_e_aviso(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.95)
        self.assertEqual(teto.nivel_alerta(), "aviso_80")

    def test_gasto_exatamente_100_por_cento_e_estourado(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 1.0)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")

    def test_gasto_acima_de_100_por_cento_e_estourado(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 3)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")


class TetoPermiteTestCase(_BaseTetoTestCase):
    def test_normal_permite_qualquer_funcao(self):
        for funcao in ("chat", "quebra_tarefa", "mala_viagem", "intent", "captura", "coisa_inventada"):
            with self.subTest(funcao=funcao):
                self.assertTrue(teto.teto_permite(funcao))

    def test_aviso_80_ainda_permite_qualquer_funcao(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.85)
        self.assertEqual(teto.nivel_alerta(), "aviso_80")
        for funcao in ("chat", "quebra_tarefa", "mala_viagem", "intent", "captura"):
            with self.subTest(funcao=funcao):
                self.assertTrue(teto.teto_permite(funcao))

    def test_estourado_bloqueia_funcao_cara_nao_essencial(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 1.5)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")
        for funcao in ("chat", "quebra_tarefa", "mala_viagem", "plano_dia", "nota_fiscal", "cotacao_pdf"):
            with self.subTest(funcao=funcao):
                self.assertFalse(teto.teto_permite(funcao))

    def test_estourado_libera_funcoes_essenciais_do_modo_economia(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 1.5)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")
        for funcao in teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA:
            with self.subTest(funcao=funcao):
                self.assertTrue(teto.teto_permite(funcao))

    def test_intent_e_captura_estao_na_lista_essencial(self):
        self.assertIn("intent", teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA)
        self.assertIn("captura", teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA)


class DesfazerNuncaBloqueiaTestCase(_BaseTetoTestCase):
    """Requisito explicito da tarefa: teto_permite("desfazer") sempre True,
    em qualquer nivel de gasto, mesmo fora da lista de funcoes essenciais."""

    def test_desfazer_permitido_sem_gasto_nenhum(self):
        self.assertTrue(teto.teto_permite("desfazer"))

    def test_desfazer_permitido_no_nivel_aviso(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 0.9)
        self.assertEqual(teto.nivel_alerta(), "aviso_80")
        self.assertTrue(teto.teto_permite("desfazer"))

    def test_desfazer_permitido_no_nivel_estourado(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 2)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")
        self.assertTrue(teto.teto_permite("desfazer"))

    def test_desfazer_permitido_mesmo_com_gasto_absurdamente_alto(self):
        self._gastar_brl(teto.TETO_PADRAO_BRL * 1000)
        self.assertTrue(teto.teto_permite("desfazer"))

    def test_desfazer_nao_precisa_estar_na_lista_essencial_pra_ser_liberado(self):
        """teto_permite trata "desfazer" incondicionalmente antes de olhar a
        lista - remover da lista (numa faixa futura) nao pode reabrir o
        bloqueio."""
        lista_original = teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA
        teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA = tuple(
            f for f in lista_original if f != "desfazer"
        )
        try:
            self._gastar_brl(teto.TETO_PADRAO_BRL * 2)
            self.assertTrue(teto.teto_permite("desfazer"))
        finally:
            teto.FUNCOES_ESSENCIAIS_MODO_ECONOMIA = lista_original


class TetoConfiguradoPeloCardFinanceiroTestCase(_BaseTetoTestCase):
    """db.CHAVE_TETO_MENSAL_IA / db.definir_teto_mensal_ia e o mecanismo JA
    EXISTENTE (US-A6) - teto.py precisa reaproveitar, nao duplicar."""

    def test_teto_configurado_em_usd_e_convertido_pro_cambio(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 20.0)  # 20 USD
        finally:
            conn.close()
        self.assertAlmostEqual(teto._teto_mensal_brl(), 20.0 * self._cambio, places=6)

    def test_teto_customizado_baixo_estoura_com_pouco_gasto(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 1.0)  # 1 USD ~ pouquissimo
        finally:
            conn.close()
        self._gastar_brl(1.0 * self._cambio * 1.1)
        self.assertEqual(teto.nivel_alerta(), "estourado_100")
        self.assertFalse(teto.teto_permite("chat"))
        self.assertTrue(teto.teto_permite("desfazer"))

    def test_teto_customizado_alto_fica_normal_com_gasto_do_padrao_antigo(self):
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 1000.0)  # bem acima do padrao de R$40
        finally:
            conn.close()
        self._gastar_brl(teto.TETO_PADRAO_BRL * 2)  # estouraria o padrao, nao o customizado
        self.assertEqual(teto.nivel_alerta(), "normal")

    def test_teto_zerado_pelo_definir_teto_mensal_ia_volta_pro_padrao(self):
        """db.definir_teto_mensal_ia(conn, 0) remove o limite (mesmo
        comportamento de nunca ter configurado) - teto.py deve cair de volta
        pro padrao de R$40, nunca dividir por zero."""
        conn = db.get_db()
        try:
            db.definir_teto_mensal_ia(conn, 0)
        finally:
            conn.close()
        self.assertEqual(teto._teto_mensal_brl(), teto.TETO_PADRAO_BRL)


class NivelAlertaValoresTestCase(unittest.TestCase):
    def test_valores_possiveis_sao_exatamente_os_tres_documentados(self):
        self.assertEqual(
            {"normal", "aviso_80", "estourado_100"},
            {"normal", "aviso_80", "estourado_100"},
        )
        # sanity check da constante de fracao de aviso usada por nivel_alerta
        self.assertEqual(teto.FRACAO_AVISO, 0.8)


if __name__ == "__main__":
    unittest.main()
