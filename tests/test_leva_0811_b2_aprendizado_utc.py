"""Leva 08/11, 2a rodada (frente B, item 2): completed_at e UTC - o dia de conclusao e o de Brasilia.

Coisa feita no dia depois das 21h (= 00h+ UTC do dia seguinte) contava 1 dia de atraso e entrava
errada em produtividade_por_dia_semana (sugestao de dia do registrar_tarefa) e na correlacao com sono.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado  # noqa: E402
import db  # noqa: E402

SEGUNDA = "2026-01-05"
DEPOIS_DAS_21H = "2026-01-06 01:30:00"  # UTC = 05/01 22:30 em Brasilia
DIA_SEGUINTE_DE_MANHA = "2026-01-06 13:00:00"  # UTC = 06/01 10:00 em Brasilia


class _Banco(unittest.TestCase):
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

    def task(self, due_date, completed_at):
        self.conn.execute("INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                          ("tarefa de teste", due_date, completed_at))
        self.conn.commit()


class AtrasoNoDiaLocalTestCase(_Banco):
    def test_feita_depois_das_21h_no_dia_nao_e_atraso(self):
        self.task(SEGUNDA, DEPOIS_DAS_21H)
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_feita_no_dia_seguinte_continua_atraso(self):
        self.task(SEGUNDA, DIA_SEGUINTE_DE_MANHA)
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [1])

    def test_espera_resolvida_a_noite_no_mesmo_dia_e_zero(self):
        # criada 05/01 10:00 local (13:00 UTC), resolvida 05/01 22:30 local (06/01 01:30 UTC)
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em, resolvido_em) VALUES (?, ?, ?, ?)",
                          ("fornecedor de teste", "orcamento", "2026-01-05 13:00:00", DEPOIS_DAS_21H))
        self.conn.commit()
        self.assertEqual(aprendizado.dias_espera_historico(self.conn), [0])


class ProdutividadeNoDiaLocalTestCase(_Banco):
    def test_segunda_feita_a_noite_conta_no_prazo(self):
        for _ in range(3):
            self.task(SEGUNDA, DEPOIS_DAS_21H)
        self.assertEqual(aprendizado.produtividade_por_dia_semana(self.conn)[0], 1.0)

    def test_segunda_feita_na_terca_continua_fora_do_prazo(self):
        for _ in range(3):
            self.task(SEGUNDA, DIA_SEGUINTE_DE_MANHA)
        self.assertEqual(aprendizado.produtividade_por_dia_semana(self.conn)[0], 0.0)


class SonoNoDiaLocalTestCase(_Banco):
    def test_feita_a_noite_conta_no_dia(self):
        self.conn.execute("INSERT INTO saude_dados (data, sono_horas) VALUES (?, ?)", (SEGUNDA, 8.5))
        self.conn.commit()
        for _ in range(3):
            self.task(SEGUNDA, DEPOIS_DAS_21H)
        self.assertEqual(aprendizado.correlacao_sono_produtividade(self.conn), {"8h+": 1.0})


if __name__ == "__main__":
    unittest.main()
