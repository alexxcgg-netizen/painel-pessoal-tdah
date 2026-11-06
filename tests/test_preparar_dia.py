"""Preparo do dia (2026-11-05, leva "agentes"): de madrugada o painel gera as 3 tarefas essenciais e o
resumo do dia, que antes so saiam no primeiro toque (resumo: agenda + tempo + construtora + ~2,3 s de IA).
Na abertura os dois vem do cache. IA sempre mockada; banco temporario."""

import os
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN = "246810"


def fake_usage():
    return {"model": "claude-haiku-5-5", "input_tokens": 100, "output_tokens": 20, "cost_usd": 0.001}


class PrepararDiaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        hoje = date.today().isoformat()
        conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Pagar a fatura', ?)", (hoje,))
        conn.commit()
        conn.close()
        self.cliente = app.app.test_client()
        self.assertEqual(self.cliente.post("/login", json={"pin": PIN}).status_code, 200)
        self._fora = [
            patch("app._construtora_contexto_resumo", return_value=None),
            patch("app._clima_contexto_resumo", return_value=None),
            patch("app.caldav_client.configurado", return_value=False),
        ]
        for p in self._fora:
            p.start()
            self.addCleanup(p.stop)

    def test_madrugada_deixa_resumo_pronto_e_a_abertura_nao_chama_a_ia(self):
        with patch("claude_client.summarize_day", return_value=("Dia leve, uma conta pra pagar.", fake_usage())) as resumo, \
                patch("claude_client.escolher_essencial", return_value=([], fake_usage())):
            app.preparar_dia()
        self.assertEqual(resumo.call_count, 1)

        with patch("claude_client.summarize_day", side_effect=AssertionError("a abertura chamou a IA")) as resumo2:
            res = self.cliente.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["summary"], "Dia leve, uma conta pra pagar.")
        resumo2.assert_not_called()

    def test_madrugada_gera_as_essenciais_uma_vez_so(self):
        with patch("claude_client.summarize_day", return_value=("ok", fake_usage())), \
                patch("claude_client.escolher_essencial", return_value=([], fake_usage())) as essencial:
            app.preparar_dia()
            app.preparar_dia()  # 7h05: ja gerado hoje, nao chama de novo
        self.assertEqual(essencial.call_count, 1)
        conn = db.get_db()
        try:
            self.assertEqual(db.obter_configuracao(conn, "essencial_gerado_em"), date.today().isoformat())
        finally:
            conn.close()
        with patch("claude_client.escolher_essencial", side_effect=AssertionError("a abertura gerou de novo")):
            self.assertEqual(self.cliente.get("/api/essencial").status_code, 200)

    def test_ia_fora_do_ar_nao_derruba_o_agendador(self):
        with patch("claude_client.summarize_day", side_effect=RuntimeError("rede caiu")), \
                patch("claude_client.escolher_essencial", side_effect=RuntimeError("rede caiu")):
            app.preparar_dia()  # nao pode levantar
        # sem resumo pronto, a abertura gera normalmente (comportamento de antes)
        with patch("claude_client.summarize_day", return_value=("Gerado na abertura.", fake_usage())):
            res = self.cliente.get("/api/summary/today")
        self.assertEqual(res.get_json()["summary"], "Gerado na abertura.")

    def test_excecao_inesperada_fica_no_log(self):
        with patch("app._gerar_essencial", side_effect=KeyError("bug")):
            app.preparar_dia()  # nao pode levantar

    def test_agendado_as_5h30_e_7h05(self):
        with patch("apscheduler.schedulers.background.BackgroundScheduler") as Mock:
            app.iniciar_scheduler()
        horarios = sorted(
            (c.kwargs.get("hour"), c.kwargs.get("minute"))
            for c in Mock.return_value.add_job.call_args_list
            if c.args and c.args[0] is app.preparar_dia
        )
        self.assertEqual(horarios, [(5, 30), (7, 5)])

    def test_resumo_busca_construtora_e_tempo_juntos(self):
        # prova pela sobreposicao (nao pelo relogio): em fila o encontro estoura
        encontro = threading.Barrier(2, timeout=5)

        def no_encontro(valor):
            def f(*_a, **_k):
                encontro.wait()
                return valor
            return f

        for p in self._fora[:2]:
            p.stop()
        with patch("app._construtora_contexto_resumo", side_effect=no_encontro("caixa de mentira")), \
                patch("app._clima_contexto_resumo", side_effect=no_encontro("sol de mentira")), \
                patch("claude_client.summarize_day", return_value=("ok", fake_usage())) as resumo:
            res = self.cliente.get("/api/summary/today")
        for p in self._fora[:2]:
            p.start()
        self.assertEqual(res.status_code, 200)
        self.assertFalse(encontro.broken, "construtora e tempo voltaram a sair em fila")
        args = resumo.call_args.args
        self.assertIn("caixa de mentira", args)
        self.assertIn("sol de mentira", args)


if __name__ == "__main__":
    unittest.main()
