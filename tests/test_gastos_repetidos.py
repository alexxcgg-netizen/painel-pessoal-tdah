"""Gasto digitado no chat que tambem veio no extrato do banco (mesmo valor, mesmo
dia) conta uma vez so - decisao do Alex em 2026-10-15 ("se for igual junta").
Fica a linha do banco; nada e apagado. Banco temporario, sem rede."""

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import notificacoes  # noqa: E402

PIN_TESTE = "123456"


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.conn.execute("DELETE FROM memorias")
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        self.conn.commit()
        self.conta = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        self._n = 0

    def tearDown(self):
        self.conn.close()

    def chat(self, valor, created_at, descricao="almoco"):
        cur = self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (?, 'mercado', ?, 'real', ?)",
            (valor, descricao, created_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def banco(self, valor, data, descricao="RESTAURANTE X", **extra):
        self._n += 1
        db.insert_bank_transactions(
            self.conn, self.conta,
            [{"external_id": f"tx-{self._n}", "data": data, "valor": valor, "descricao": descricao,
              "categoria": "alimentacao"}],
        )
        for coluna, v in extra.items():  # tipo_operacao / categoria_pluggy (campos do Pluggy)
            self.conn.execute(f"UPDATE bank_transactions SET {coluna} = ? WHERE external_id = ?", (v, f"tx-{self._n}"))
        self.conn.commit()


class PareamentoTestCase(_Base):
    def test_mesmo_valor_mesmo_dia_junta(self):
        e = self.chat(42.5, "2026-01-10")
        self.banco(-42.5, "2026-01-10")
        self.assertEqual(db.gastos_chat_repetidos_no_banco(self.conn), {e})
        self.assertAlmostEqual(db.total_gasto_real_mes(self.conn, "2026-01"), 42.5)

    def test_valor_ou_dia_diferente_conta_os_dois(self):
        self.chat(42.5, "2026-01-10")
        self.banco(-42.0, "2026-01-10")
        self.chat(30.0, "2026-01-11")
        self.banco(-30.0, "2026-01-12")
        self.assertEqual(db.gastos_chat_repetidos_no_banco(self.conn), set())
        self.assertAlmostEqual(db.total_gasto_real_mes(self.conn, "2026-01"), 42.5 + 42.0 + 30.0 + 30.0)

    def test_um_pra_um(self):
        a = self.chat(5.0, "2026-01-10", "cafe")
        b = self.chat(5.0, "2026-01-10", "cafe de novo")
        self.banco(-5.0, "2026-01-10", "PADARIA")
        repetidos = db.gastos_chat_repetidos_no_banco(self.conn)
        self.assertEqual(len(repetidos), 1)
        self.assertTrue(repetidos <= {a, b})
        self.assertAlmostEqual(db.total_gasto_real_mes(self.conn, "2026-01"), 10.0)

    def test_entrada_do_banco_nao_pareia(self):
        self.chat(100.0, "2026-01-10")
        self.banco(100.0, "2026-01-10", "PIX RECEBIDO")
        self.assertEqual(db.gastos_chat_repetidos_no_banco(self.conn), set())

    def test_gasto_da_noite_usa_o_dia_local(self):
        # created_at e UTC: 01:30 UTC ja e o dia seguinte; a compra foi no dia local
        utc = "2026-01-11 01:30:00"
        dia_local = datetime(2026, 1, 11, 1, 30, tzinfo=timezone.utc).astimezone().date().isoformat()
        e = self.chat(80.0, utc)
        self.banco(-80.0, dia_local)
        self.assertEqual(db.gastos_chat_repetidos_no_banco(self.conn), {e})

    def test_so_dias_limita_sem_mudar_resultado(self):
        e = self.chat(12.0, "2026-01-10")
        self.banco(-12.0, "2026-01-10")
        self.chat(9.0, "2026-01-20")
        self.banco(-9.0, "2026-01-20")
        self.assertEqual(db.gastos_chat_repetidos_no_banco(self.conn, so_dias={"2026-01-10"}), {e})
        self.assertEqual(len(db.gastos_chat_repetidos_no_banco(self.conn)), 2)

    def test_nada_e_apagado(self):
        self.chat(42.5, "2026-01-10")
        self.banco(-42.5, "2026-01-10")
        db.gastos_chat_repetidos_no_banco(self.conn)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) c FROM expenses").fetchone()["c"], 1)


class OndeApareceTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def test_deteccao_e_unificados_contam_uma_vez(self):
        self.chat(39.9, "2026-01-10", "netflix")
        self.banco(-39.9, "2026-01-10", "NETFLIX.COM")
        self.chat(15.0, "2026-01-10", "pao")  # so no chat, continua
        unificado = notificacoes._gastos_reais_unificados_para_deteccao(self.conn)
        self.assertEqual(sorted(g["amount"] for g in unificado), [15.0, 39.9])
        self.assertEqual(sorted(g["amount"] for g in app._gastos_reais_unificados(self.conn)), [15.0, 39.9])

    def test_rota_gastos_unificados_lista_e_pagina(self):
        self.chat(39.9, "2026-01-10", "netflix")
        self.banco(-39.9, "2026-01-10", "NETFLIX.COM")
        self.chat(15.0, "2026-01-09", "pao")
        itens = self.client.get("/api/gastos/unificados").get_json()
        self.assertEqual(sorted((i["amount"], i["origem"]) for i in itens), [(15.0, "manual"), (39.9, "Nubank")])
        pagina = self.client.get("/api/gastos/unificados?limite=1").get_json()
        vistos = list(pagina["itens"])
        for _ in range(10):  # teto: cursor errado nunca vira laco infinito
            if not pagina.get("proximo"):
                break
            pagina = self.client.get(
                "/api/gastos/unificados", query_string={"limite": 1, "antes": pagina["proximo"]}
            ).get_json()
            vistos += pagina["itens"]
        self.assertEqual(sorted(i["amount"] for i in vistos), [15.0, 39.9])

    def test_extrato_financas_mostra_so_a_linha_do_banco(self):
        hoje = date.today().isoformat()
        self.chat(25.0, f"{hoje}")
        self.banco(25.0, hoje, "MERCADO", tipo_operacao="DEBIT")  # Pluggy: cartao vem positivo + DEBIT
        itens = self.client.get("/api/financas/extrato").get_json()["itens"]
        self.assertEqual([i["origem"] for i in itens], ["Nubank"])

    def test_transferencia_no_banco_nao_esconde_o_gasto_do_chat_nas_financas(self):
        hoje = date.today().isoformat()
        self.chat(200.0, f"{hoje}", "pintor")
        self.banco(-200.0, hoje, "PIX ENVIADO", categoria_pluggy="Transfer - PIX")
        origens = sorted(i["origem"] for i in self.client.get("/api/financas/extrato").get_json()["itens"])
        self.assertEqual(origens, ["Nubank", "manual"])

    def test_renda_perto_de_acabar_nao_soma_duas_vezes(self):
        hoje = date.today()
        self.conn.execute("INSERT INTO incomes (amount, category, created_at) VALUES (1000, 'outros', ?)",
                          (f"{hoje.isoformat()} 12:00:00",))
        self.conn.commit()
        self.chat(400.0, f"{hoje.isoformat()} 12:00:00")
        self.banco(-400.0, hoje.isoformat())
        # 400 de 1000 = 40% (antes contava 80% e avisava)
        self.assertIsNone(notificacoes.renda_perto_de_acabar(self.conn, hoje))


if __name__ == "__main__":
    unittest.main()
