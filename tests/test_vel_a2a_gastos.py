"""Faixa vel/A2a: paginacao de /api/gastos/unificados (aba Financeiro >
Gastos travando ao abrir com volume real de dados - 3000 transacoes +
1500 gastos manuais no cenario medido).

Mesmo padrao de tests/test_fase8_f1_banco.py: sobe app.py inteiro (a rota
usa app_modulo()), banco temporario, nunca chama Pluggy/rede de verdade."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


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

    def _povoar(self, n_manuais=45, n_banco=40):
        """n_manuais gastos manuais (expenses, tipo='real') + n_banco
        transacoes bancarias, metade negativa (gasto) metade positiva
        (renda, deve ficar de fora da lista unificada) - datas diferentes
        pra ordem ficar bem definida (mais recente primeiro)."""
        conn = db.get_db()
        for i in range(n_manuais):
            conn.execute(
                "INSERT INTO expenses (amount, category, description, source_text, created_at, tipo) "
                "VALUES (?, ?, ?, ?, ?, 'real')",
                (10.0 + i, "mercado", f"manual-{i:03d}", "teste", f"2026-01-{(i % 27) + 1:02d} 12:00:00"),
            )
        conn.commit()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        transacoes = []
        for i in range(n_banco):
            valor = -20.0 - i if i % 2 == 0 else 15.0 + i  # metade gasto, metade renda
            transacoes.append(
                {
                    "external_id": f"tx-{i:03d}",
                    "data": f"2026-02-{(i % 27) + 1:02d}",
                    "valor": valor,
                    "descricao": f"banco-{i:03d}",
                    "categoria": "transporte",
                }
            )
        db.insert_bank_transactions(conn, conta_id, transacoes)
        conn.commit()
        conn.close()
        n_gastos_banco = sum(1 for t in transacoes if t["valor"] < 0)
        return n_manuais + n_gastos_banco


class TestPaginacaoGastosUnificados(_BaseTestCase):
    def test_sem_parametros_mantem_lista_completa_como_antes(self):
        total_esperado = self._povoar()
        resp = self.client.get("/api/gastos/unificados")
        self.assertEqual(resp.status_code, 200)
        itens = resp.get_json()
        self.assertIsInstance(itens, list)
        self.assertEqual(len(itens), total_esperado)

    def test_tudo_1_devolve_lista_completa_igual_ao_sem_parametros(self):
        self._povoar()
        sem_parametros = self.client.get("/api/gastos/unificados").get_json()
        com_tudo = self.client.get("/api/gastos/unificados?tudo=1").get_json()
        self.assertEqual(sem_parametros, com_tudo)

    def test_lista_vazia_sem_parametros_continua_array_vazio(self):
        resp = self.client.get("/api/gastos/unificados")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_primeira_pagina_tem_exatamente_limite_itens(self):
        self._povoar()
        resp = self.client.get("/api/gastos/unificados?limite=10")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertIn("itens", corpo)
        self.assertIn("proximo", corpo)
        self.assertEqual(len(corpo["itens"]), 10)
        self.assertIsNotNone(corpo["proximo"])

    def test_limite_default_e_30_e_teto_e_200(self):
        self._povoar(n_manuais=45, n_banco=0)
        # `limite` invalido (nao-numero) com paginacao ja acionada por ele
        # estar presente -> cai no padrao (30), nunca derruba a rota.
        resp = self.client.get("/api/gastos/unificados?limite=abc")
        corpo = resp.get_json()
        self.assertEqual(len(corpo["itens"]), 30)

        resp2 = self.client.get("/api/gastos/unificados?limite=999999")
        corpo2 = resp2.get_json()
        self.assertLessEqual(len(corpo2["itens"]), 200)

    def test_cursor_encadeia_sem_repetir_nem_pular_e_bate_com_lista_completa(self):
        total_esperado = self._povoar(n_manuais=37, n_banco=26)
        completa = self.client.get("/api/gastos/unificados?tudo=1").get_json()
        self.assertEqual(len(completa), total_esperado)

        paginado = []
        cursor = None
        paginas = 0
        while True:
            paginas += 1
            self.assertLess(paginas, 50, "paginacao nao deveria precisar de tantas paginas nesse volume")
            url = "/api/gastos/unificados?limite=8"
            if cursor:
                url += f"&antes={cursor}"
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            corpo = resp.get_json()
            paginado.extend(corpo["itens"])
            cursor = corpo["proximo"]
            if cursor is None:
                break

        self.assertEqual(len(paginado), len(completa))
        # mesmo CONJUNTO de itens da lista completa - a ordem entre itens
        # com a MESMA data pode divergir do desempate da lista antiga (que
        # nunca foi um contrato), mas nenhum item pode faltar, duplicar ou
        # trocar de valor.
        descricoes_paginado = [i["description"] for i in paginado]
        descricoes_completa = [i["description"] for i in completa]
        self.assertEqual(len(descricoes_paginado), len(set(descricoes_paginado)), "nao pode repetir item entre paginas")
        self.assertEqual(sorted(descricoes_paginado), sorted(descricoes_completa))

        # ordem por DATA (ignorando desempate dentro do mesmo dia) nunca
        # pode regredir de uma pagina pra outra - e o que garante "mais
        # recente primeiro" continuar valendo com paginacao.
        datas = [str(i["created_at"])[:10] for i in paginado]
        self.assertEqual(datas, sorted(datas, reverse=True))

    def test_fim_da_lista_devolve_proximo_none(self):
        self._povoar(n_manuais=5, n_banco=0)
        resp = self.client.get("/api/gastos/unificados?limite=30")
        corpo = resp.get_json()
        self.assertEqual(len(corpo["itens"]), 5)
        self.assertIsNone(corpo["proximo"])

    def test_cursor_invalido_nao_derruba_a_rota_volta_do_comeco(self):
        self._povoar(n_manuais=5, n_banco=0)
        resp = self.client.get("/api/gastos/unificados?limite=5&antes=lixo-invalido")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertEqual(len(corpo["itens"]), 5)

    def test_origem_manual_e_banco_continuam_certas_na_paginacao(self):
        self._povoar(n_manuais=3, n_banco=4)
        resp = self.client.get("/api/gastos/unificados?limite=200")
        itens = resp.get_json()["itens"]
        origens = {i["description"]: i["origem"] for i in itens}
        self.assertEqual(origens["manual-000"], "manual")
        # bancos-000, banco-002 sao os de valor negativo (i par) -> "Nubank"
        self.assertEqual(origens["banco-000"], "Nubank")
        self.assertNotIn("banco-001", origens)  # valor positivo (renda), fora da lista


if __name__ == "__main__":
    unittest.main()
