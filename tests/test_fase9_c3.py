"""Fase 9, faixa C3 (Financas): testes de `por_dia_mes`/`por_dia_mes_anterior`
em GET /api/financas/resumo (novo contrato acrescentado por esta faixa a
rotas/f9_financas.py, que ja existia da faixa f9-api) e do render dos 3
cartoes novos da tela "Conversa" no topo da aba Financas (templates/secoes/
gastos/conversa.html). Mesmo padrao de fixture de tests/test_fase9_api.py e
tests/test_fase9_ui.py: banco temporario, nunca chama Pluggy/IA de
verdade."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

PIN_TESTE = "123456"
HOJE = date.today()


def _iso(dias_atras: int) -> str:
    return (HOJE - timedelta(days=dias_atras)).isoformat()


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def _conta(self, banco="Nubank", tipo="conta"):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, banco, tipo)
        conn.commit()
        conn.close()
        return conta_id

    def _tx(
        self,
        bank_account_id,
        external_id,
        data,
        valor,
        tipo_operacao,
        descricao="Compra Teste",
        categoria_pluggy=None,
        descricao_original=None,
    ):
        conn = db.get_db()
        conn.execute(
            """INSERT INTO bank_transactions
               (bank_account_id, data, descricao, valor, external_id, categoria,
                estabelecimento, categoria_pluggy, descricao_original, tipo_operacao,
                estorno_de_external_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bank_account_id,
                data,
                db.criptografia.criptografar(descricao),
                db._cnum(valor),
                external_id,
                None,
                None,
                categoria_pluggy,
                descricao_original if descricao_original is not None else descricao,
                tipo_operacao,
                None,
            ),
        )
        conn.commit()
        conn.close()


class PorDiaMesTestCase(_BaseTestCase):
    def test_acumulado_do_ultimo_dia_bate_com_gasto_mes(self):
        conta_id = self._conta("Nubank", "conta")
        primeiro_dia_mes = HOJE.replace(day=1)
        # 3 gastos espalhados no mes ate hoje (dia 2, dia do meio, hoje).
        self._tx(conta_id, "d1", primeiro_dia_mes.isoformat(), 15.0, "DEBIT", descricao="Padaria")
        meio = primeiro_dia_mes + timedelta(days=max(0, (HOJE - primeiro_dia_mes).days // 2))
        self._tx(conta_id, "d2", meio.isoformat(), 40.0, "DEBIT", descricao="Mercado")
        self._tx(conta_id, "d3", HOJE.isoformat(), 25.5, "DEBIT", descricao="Farmacia")

        resumo = self.client.get("/api/financas/resumo").get_json()
        self.assertGreater(len(resumo["por_dia_mes"]), 0)
        ultimo = resumo["por_dia_mes"][-1]
        self.assertEqual(ultimo["dia"], HOJE.day)
        self.assertEqual(ultimo["acumulado"], resumo["gasto_mes"])
        self.assertEqual(resumo["gasto_mes"], 80.5)
        # Acumulado e monotonico nao-decrescente dia a dia.
        acumulados = [d["acumulado"] for d in resumo["por_dia_mes"]]
        self.assertEqual(acumulados, sorted(acumulados))

    def test_parcela_futura_nao_entra_no_acumulado(self):
        cartao_id = self._conta("Nubank", "cartao")
        data_futura = (HOJE + timedelta(days=200)).isoformat()
        self._tx(cartao_id, "fut1", data_futura, 999.0, "DEBIT", descricao="Parcela 3/12")
        self._tx(cartao_id, "hoje1", HOJE.isoformat(), 10.0, "DEBIT", descricao="Compra hoje")

        resumo = self.client.get("/api/financas/resumo").get_json()
        self.assertEqual(resumo["por_dia_mes"][-1]["acumulado"], 10.0)
        total = sum(d["acumulado"] for d in resumo["por_dia_mes"])
        # se a parcela futura tivesse entrado, o total acumulado explodiria.
        self.assertLess(total, 999.0)

    def test_pagamento_de_fatura_nao_entra_no_acumulado(self):
        conta_id = self._conta("Nubank", "conta")
        self._tx(
            conta_id,
            "pgto1",
            HOJE.isoformat(),
            500.0,
            "DEBIT",
            descricao="Pagamento de fatura",
            categoria_pluggy="Credit card payment",
        )
        self._tx(conta_id, "g1", HOJE.isoformat(), 12.0, "DEBIT", descricao="Padaria")

        resumo = self.client.get("/api/financas/resumo").get_json()
        self.assertEqual(resumo["por_dia_mes"][-1]["acumulado"], 12.0)

    def test_por_dia_mes_anterior_cobre_o_mes_inteiro_passado(self):
        primeiro_dia_mes = HOJE.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes - timedelta(days=1)
        primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
        dias_no_mes_anterior = (ultimo_dia_mes_anterior - primeiro_dia_mes_anterior).days + 1

        resumo = self.client.get("/api/financas/resumo").get_json()
        self.assertEqual(len(resumo["por_dia_mes_anterior"]), dias_no_mes_anterior)
        self.assertEqual(resumo["por_dia_mes_anterior"][0]["dia"], 1)
        self.assertEqual(resumo["por_dia_mes_anterior"][-1]["dia"], ultimo_dia_mes_anterior.day)

    def test_modo_visitante_devolve_listas_vazias_sem_erro(self):
        res_ativar = self.client.post("/api/modo-visitante", json={"ativar": True})
        assert res_ativar.status_code == 200, res_ativar.get_json()
        try:
            res = self.client.get("/api/financas/resumo")
            corpo = res.get_json()
            self.assertEqual(res.status_code, 200)
            self.assertEqual(corpo["por_dia_mes"], [])
            self.assertEqual(corpo["por_dia_mes_anterior"], [])
        finally:
            self.client.post("/api/modo-visitante", json={"pin": PIN_TESTE})


class TelaFinancasConversaUiTestCase(unittest.TestCase):
    """So o HTML renderizado (ids dos cartoes novos) - a logica de cada
    cartao (categoria/evolucao/fatura-conta) e testada via API acima; o
    preenchimento em si e JS (gastos.js), fora do alcance do teste Python."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        self.corpo = self.client.get("/").get_data(as_text=True)

    def test_topo_conversa_presente_antes_do_resto_da_aba(self):
        self.assertIn('id="financas-conversa"', self.corpo)
        self.assertIn('id="fc-frase-resumo"', self.corpo)
        pos_conversa = self.corpo.index('id="financas-conversa"')
        pos_bancos = self.corpo.index('id="lista-bancos"')
        self.assertLess(pos_conversa, pos_bancos, "topo Conversa devia vir antes de Bancos na aba")

    def test_tres_cartoes_novos_presentes(self):
        self.assertIn('id="fc-card-categoria"', self.corpo)
        self.assertIn('id="fc-card-evolucao"', self.corpo)
        self.assertIn('id="fc-card-fatura-conta"', self.corpo)
        self.assertIn('id="fc-lista-categoria"', self.corpo)
        self.assertIn('id="fc-grafico-evolucao"', self.corpo)
        self.assertIn('id="fc-fatura-barra"', self.corpo)
        self.assertIn('id="fc-conta-barra"', self.corpo)
        self.assertIn('id="fc-patrimonio-valor"', self.corpo)

    def test_extrato_ultimos_dias_migrou_pro_cartao_do_topo_sem_duplicar_id(self):
        self.assertEqual(self.corpo.count('id="lista-extrato-financas"'), 1)
        self.assertEqual(self.corpo.count('id="btn-carregar-mais-extrato"'), 1)
        pos_extrato = self.corpo.index('id="lista-extrato-financas"')
        pos_conversa = self.corpo.index('id="financas-conversa"')
        pos_extrato_completo = self.corpo.index('data-secao-id="gastos-extrato-completo"')
        self.assertLess(pos_conversa, pos_extrato)
        self.assertLess(pos_extrato, pos_extrato_completo)

    def test_metas_e_construtora_recolhidos(self):
        self.assertIn('data-secao-id="metas"', self.corpo)
        self.assertIn('data-secao-id="construtora"', self.corpo)

    def test_ids_antigos_de_resumo_continuam_no_html(self):
        # Contrato de tests/test_fase9_ui.py (nao e meu arquivo) - o card
        # antigo fica escondido via CSS, mas os ids continuam existindo.
        self.assertIn('id="resumo-financas-box"', self.corpo)
        self.assertIn('id="resumo-financas-gasto"', self.corpo)
        self.assertIn('id="resumo-financas-fatura"', self.corpo)
        self.assertIn('id="resumo-financas-saldo"', self.corpo)


if __name__ == "__main__":
    unittest.main()
