"""Faixa uso/M4 (cache do resumo de IA do dia): GET /api/summary/today so
chama claude_client.summarize_day 1x por dia, e so gera de novo quando algo
relevante muda (tarefa importante nova/concluida hoje, gasto real grande
novo hoje ou virou o dia) - nao a cada load de pagina. Nunca le o .env real
nem chama IA de verdade (summarize_day sempre mockado); banco temporario,
mesmo padrao de tests/test_fase9_api.py (db.DB_PATH temporario + PIN por
POST /login)."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

PIN_TESTE = "123456"


def fake_usage(cost=0.001):
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 100, "output_tokens": 20, "cost_usd": cost}


class ResumoDiaCacheTestCase(unittest.TestCase):
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

    # ---- helpers --------------------------------------------------------

    def _get_resumo(self):
        with patch("claude_client.summarize_day", return_value=("Resumo mockado.", fake_usage())) as mock:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        return res, mock

    def _inserir_gasto(self, valor: float):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo) VALUES (?, 'teste', 'x', 'real')",
            (valor,),
        )
        conn.commit()
        conn.close()

    def _inserir_tarefa(self, title: str, due_date=None):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            (title, due_date),
        )
        conn.commit()
        conn.close()

    # ---- cenarios do brief -----------------------------------------------

    def test_dois_gets_seguidos_chama_ia_uma_vez_so(self):
        _, mock1 = self._get_resumo()
        self.assertEqual(mock1.call_count, 1)
        _, mock2 = self._get_resumo()
        # segundo GET usa outro mock (patch novo por chamada) - o que importa
        # e que a ROTA nao chamou summarize_day de novo (cache bateu)
        self.assertEqual(mock2.call_count, 0)

    def test_gasto_pequeno_novo_nao_invalida_cache(self):
        self._get_resumo()
        self._inserir_gasto(20.0)  # abaixo do limiar (R$100)
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 0)

    def test_gasto_grande_novo_invalida_cache(self):
        self._get_resumo()
        self._inserir_gasto(150.0)  # acima do limiar (R$100)
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_gasto_exatamente_no_limiar_invalida_cache(self):
        self._get_resumo()
        self._inserir_gasto(100.0)  # limiar e >= 100, entao conta como grande
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_tarefa_importante_nova_invalida_cache(self):
        self._get_resumo()
        self._inserir_tarefa("responder o banco", due_date=date.today().isoformat())
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_tarefa_atrasada_nova_tambem_invalida_cache(self):
        self._get_resumo()
        self._inserir_tarefa("assinar contrato", due_date=(date.today() - timedelta(days=2)).isoformat())
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_tarefa_comum_nova_nao_invalida_cache(self):
        self._get_resumo()
        self._inserir_tarefa("comprar pao")
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 0)

    def test_tarefa_pro_futuro_nao_invalida_cache(self):
        self._get_resumo()
        self._inserir_tarefa("renovar CMA", due_date=(date.today() + timedelta(days=10)).isoformat())
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 0)

    def test_tarefa_importante_concluida_hoje_invalida_cache(self):
        conn = db.get_db()
        cur = conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar imposto", date.today().isoformat()))
        task_id = cur.lastrowid
        conn.commit()
        conn.close()
        self._get_resumo()
        conn = db.get_db()
        conn.execute("UPDATE tasks SET completed_at = datetime('now') WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_virou_o_dia_invalida_cache(self):
        self._get_resumo()
        # simula "virou o dia": o cache de hoje passa a valer pra uma data
        # passada (a chave de leitura da rota e sempre date.today().isoformat(),
        # entao uma linha guardada sob outra data nunca bate - mesmo efeito
        # pratico de o dia ter virado, sem precisar congelar o relogio)
        conn = db.get_db()
        conn.execute("UPDATE resumo_dia_cache SET data = '2000-01-01'")
        conn.commit()
        conn.close()
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_erro_da_ia_nao_grava_cache(self):
        with patch("claude_client.summarize_day", side_effect=ValueError("formato ruim")):
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 502)
        conn = db.get_db()
        row = conn.execute("SELECT * FROM resumo_dia_cache").fetchall()
        conn.close()
        self.assertEqual(row, [])
        # proxima chamada, agora com sucesso, ainda chama a IA (nada ficou cacheado)
        _, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 1)

    def test_forcar_1_ignora_cache_e_regera(self):
        self._get_resumo()
        with patch(
            "claude_client.summarize_day", return_value=("Resumo forcado.", fake_usage())
        ) as mock2:
            res = self.client.get("/api/summary/today?forcar=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock2.call_count, 1)
        self.assertEqual(res.get_json()["summary"], "Resumo forcado.")

    def test_numeros_continuam_frescos_mesmo_com_cache_batendo(self):
        self._get_resumo()
        self._inserir_gasto(20.0)  # pequeno - nao invalida o texto
        res, mock2 = self._get_resumo()
        self.assertEqual(mock2.call_count, 0)
        # o texto vem do cache, mas gasto_hoje reflete o gasto novo (soma real)
        self.assertEqual(res.get_json()["gasto_hoje"], 20.0)
        self.assertEqual(res.get_json()["summary"], "Resumo mockado.")

    def test_nao_loga_uso_quando_cache_bate(self):
        self._get_resumo()
        uso_antes = self.client.get("/api/uso/total").get_json()["custo_usd"]
        self._get_resumo()
        uso_depois = self.client.get("/api/uso/total").get_json()["custo_usd"]
        self.assertAlmostEqual(uso_antes, uso_depois)


if __name__ == "__main__":
    unittest.main()
