import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado
import db


class MedianaTestCase(unittest.TestCase):
    def test_lista_impar(self):
        self.assertEqual(aprendizado._mediana([3, 1, 2]), 2)

    def test_lista_par(self):
        self.assertEqual(aprendizado._mediana([1, 2, 3, 4]), 2.5)

    def test_um_unico_elemento(self):
        self.assertEqual(aprendizado._mediana([7]), 7)

    def test_lista_ja_ordenada_com_repeticao(self):
        self.assertEqual(aprendizado._mediana([2, 2, 2, 2, 5]), 2)


class LimiarPersonalizadoTestCase(unittest.TestCase):
    def test_historico_vazio_usa_padrao(self):
        valor, info = aprendizado.limiar_personalizado([], padrao=3)
        self.assertEqual(valor, 3)
        self.assertEqual(info["fonte"], "padrao")
        self.assertEqual(info["amostras"], 0)
        self.assertIn("insuficiente", info["motivo"])

    def test_abaixo_do_minimo_usa_padrao(self):
        valor, info = aprendizado.limiar_personalizado([2, 4, 6, 8], padrao=3, minimo_amostras=5)
        self.assertEqual(valor, 3)
        self.assertEqual(info["fonte"], "padrao")
        self.assertEqual(info["amostras"], 4)

    def test_exatamente_no_minimo_ja_aprende(self):
        valor, info = aprendizado.limiar_personalizado(
            [2, 2, 2, 2, 2], padrao=3, minimo_amostras=5
        )
        self.assertEqual(valor, 2)
        self.assertEqual(info["fonte"], "aprendido")
        self.assertEqual(info["amostras"], 5)

    def test_mediana_impar_arredonda(self):
        # mediana de [1,2,3,4,10] = 3
        valor, info = aprendizado.limiar_personalizado([1, 2, 3, 4, 10], padrao=3)
        self.assertEqual(valor, 3)
        self.assertEqual(info["mediana_bruta"], 3)
        self.assertFalse(info["limitado"])

    def test_mediana_par_arredonda_para_par_mais_proximo(self):
        # mediana de [1,2,3,4,5,6] = 3.5 -> round(3.5) = 4 (banker's rounding do Python)
        valor, info = aprendizado.limiar_personalizado([1, 2, 3, 4, 5, 6], padrao=3)
        self.assertEqual(valor, round(3.5))

    def test_clampa_no_piso(self):
        valor, info = aprendizado.limiar_personalizado(
            [0, 0, 0, 0, 0], padrao=3, piso=1, teto=14
        )
        self.assertEqual(valor, 1)
        self.assertEqual(info["mediana_bruta"], 0)
        self.assertTrue(info["limitado"])

    def test_clampa_no_teto(self):
        valor, info = aprendizado.limiar_personalizado(
            [30, 30, 30, 30, 30], padrao=3, piso=1, teto=14
        )
        self.assertEqual(valor, 14)
        self.assertEqual(info["mediana_bruta"], 30)
        self.assertTrue(info["limitado"])

    def test_um_outlier_nao_desloca_a_mediana(self):
        # 4 valores baixos + 1 bem alto: mediana ainda fica baixa (robusta),
        # diferente de uma media que seria puxada pelo outlier.
        valor, info = aprendizado.limiar_personalizado([2, 2, 2, 2, 100], padrao=3, teto=14)
        self.assertEqual(valor, 2)

    def test_muitas_amostras_grande(self):
        amostras = list(range(1, 51))  # 1..50
        valor, info = aprendizado.limiar_personalizado(amostras, padrao=3, teto=100)
        self.assertEqual(info["amostras"], 50)
        self.assertEqual(valor, round(aprendizado._mediana(amostras)))


class HistoricoDbTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _criar_task(self, due_date, completed_at):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            ("tarefa teste", due_date, completed_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def _criar_espera(self, criado_em, resolvido_em):
        cur = self.conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em, resolvido_em) VALUES (?, ?, ?, ?)",
            ("fornecedor teste", "material", criado_em, resolvido_em),
        )
        self.conn.commit()
        return cur.lastrowid

    def test_dias_atraso_vazio_sem_tarefas(self):
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_dias_atraso_ignora_tarefa_sem_due_date(self):
        self._criar_task(None, "2026-01-05 10:00:00")
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_dias_atraso_ignora_tarefa_nao_concluida(self):
        self._criar_task("2026-01-01", None)
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_dias_atraso_ignora_concluida_no_prazo(self):
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_dias_atraso_ignora_concluida_antes_do_prazo(self):
        self._criar_task("2026-01-05", "2026-01-03 10:00:00")
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [])

    def test_dias_atraso_conta_atraso_real(self):
        self._criar_task("2026-01-01", "2026-01-04 10:00:00")
        self.assertEqual(aprendizado.dias_atraso_historico_tarefas(self.conn), [3])

    def test_dias_atraso_multiplas_tarefas(self):
        self._criar_task("2026-01-01", "2026-01-04 10:00:00")  # 3 dias
        self._criar_task("2026-01-10", "2026-01-12 10:00:00")  # 2 dias
        self._criar_task("2026-02-01", "2026-02-01 10:00:00")  # no prazo, ignora
        resultado = sorted(aprendizado.dias_atraso_historico_tarefas(self.conn))
        self.assertEqual(resultado, [2, 3])

    def test_dias_espera_vazio_sem_esperas(self):
        self.assertEqual(aprendizado.dias_espera_historico(self.conn), [])

    def test_dias_espera_ignora_ainda_aberta(self):
        self._criar_espera("2026-01-01 10:00:00", None)
        self.assertEqual(aprendizado.dias_espera_historico(self.conn), [])

    def test_dias_espera_conta_resolvida(self):
        self._criar_espera("2026-01-01 10:00:00", "2026-01-06 10:00:00")
        self.assertEqual(aprendizado.dias_espera_historico(self.conn), [5])

    def test_dias_espera_zero_dias_conta(self):
        # criada e resolvida no mesmo dia - zero e um dado valido (resolveu rapido)
        self._criar_espera("2026-01-01 08:00:00", "2026-01-01 18:00:00")
        self.assertEqual(aprendizado.dias_espera_historico(self.conn), [0])

    def test_dias_espera_multiplas(self):
        self._criar_espera("2026-01-01 10:00:00", "2026-01-06 10:00:00")  # 5
        self._criar_espera("2026-02-01 10:00:00", "2026-02-03 10:00:00")  # 2
        self._criar_espera("2026-03-01 10:00:00", None)  # aberta, ignora
        resultado = sorted(aprendizado.dias_espera_historico(self.conn))
        self.assertEqual(resultado, [2, 5])


class InteracoesAprendizadoTestCase(unittest.TestCase):
    """Testa as funcoes de db.py que abrem/fecham o loop de aprendizado -
    ficam aqui (nao em tests/test_app.py) porque sao puramente sobre a
    tabela interacoes_aprendizado, independente das rotas Flask que as
    chamam."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _criar_task(self, title="tarefa teste", due_date=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", (title, due_date)
        )
        self.conn.commit()
        return cur.lastrowid

    def _criar_espera(self, quem="fornecedor teste", sobre="material"):
        cur = self.conn.execute(
            "INSERT INTO esperas (quem, sobre) VALUES (?, ?)", (quem, sobre)
        )
        self.conn.commit()
        return cur.lastrowid

    def test_registrar_interacao_cria_linha_aberta(self):
        interacao_id = db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 42)
        row = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE id = ?", (interacao_id,)
        ).fetchone()
        self.assertEqual(row["tipo"], "tarefa_parada")
        self.assertEqual(row["referencia_id"], 42)
        self.assertIsNone(row["resolvido_em"])
        self.assertIsNone(row["latencia_horas"])

    def test_fechar_interacao_sem_nenhuma_aberta_e_no_op(self):
        fechou = db.fechar_interacao_aprendizado(self.conn, "tarefa_parada", 999)
        self.assertFalse(fechou)

    def test_fechar_interacao_preenche_resolvido_em_e_latencia(self):
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 7)
        fechou = db.fechar_interacao_aprendizado(self.conn, "tarefa_parada", 7)
        self.assertTrue(fechou)
        row = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = 7"
        ).fetchone()
        self.assertIsNotNone(row["resolvido_em"])
        self.assertIsNotNone(row["latencia_horas"])
        self.assertGreaterEqual(row["latencia_horas"], 0)

    def test_fechar_interacao_so_fecha_o_tipo_e_referencia_certos(self):
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 1)
        db.registrar_interacao_aprendizado(self.conn, "espera_parada", 1)
        db.fechar_interacao_aprendizado(self.conn, "tarefa_parada", 1)
        aberta = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'espera_parada' AND referencia_id = 1"
        ).fetchone()
        self.assertIsNone(aberta["resolvido_em"])

    def test_fechar_interacao_pega_a_mais_recente_quando_ha_duas_abertas(self):
        # nao deveria acontecer no uso real (dedup evita cutucar 2x), mas a
        # query precisa se comportar de forma previsivel mesmo assim: fecha
        # so uma (a mais recente), nunca as duas de uma vez.
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 5)
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 5)
        db.fechar_interacao_aprendizado(self.conn, "tarefa_parada", 5)
        abertas = self.conn.execute(
            "SELECT COUNT(*) AS n FROM interacoes_aprendizado "
            "WHERE tipo = 'tarefa_parada' AND referencia_id = 5 AND resolvido_em IS NULL"
        ).fetchone()["n"]
        self.assertEqual(abertas, 1)

    def test_latencias_resolvidas_so_traz_as_com_latencia(self):
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 1)
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 2)
        db.fechar_interacao_aprendizado(self.conn, "tarefa_parada", 1)
        resultado = db.latencias_resolvidas(self.conn, "tarefa_parada")
        self.assertEqual(len(resultado), 1)

    def test_latencias_resolvidas_tipo_sem_nada_retorna_vazio(self):
        self.assertEqual(db.latencias_resolvidas(self.conn, "espera_parada"), [])

    def test_complete_task_marca_concluida(self):
        task_id = self._criar_task()
        db.complete_task(self.conn, task_id)
        row = self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertIsNotNone(row["completed_at"])

    def test_complete_task_fecha_interacao_aberta(self):
        task_id = self._criar_task()
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", task_id)
        db.complete_task(self.conn, task_id)
        row = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = ?",
            (task_id,),
        ).fetchone()
        self.assertIsNotNone(row["resolvido_em"])

    def test_complete_task_sem_interacao_aberta_nao_quebra(self):
        task_id = self._criar_task()
        db.complete_task(self.conn, task_id)  # nao deve levantar excecao
        row = self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertIsNotNone(row["completed_at"])

    def test_resolver_espera_fecha_interacao_aberta(self):
        espera_id = self._criar_espera()
        db.registrar_interacao_aprendizado(self.conn, "espera_parada", espera_id)
        db.resolver_espera(self.conn, espera_id)
        row = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'espera_parada' AND referencia_id = ?",
            (espera_id,),
        ).fetchone()
        self.assertIsNotNone(row["resolvido_em"])

    def test_resolver_espera_inexistente_nao_fecha_nada_nem_quebra(self):
        ok = db.resolver_espera(self.conn, 9999)
        self.assertFalse(ok)


class MarcarOuCriarFeitoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def test_titulo_vazio_devolve_erro(self):
        resultado = db.marcar_ou_criar_feito(self.conn, "   ")
        self.assertFalse(resultado["ok"])
        self.assertIn("erro", resultado)

    def test_sem_tarefa_parecida_cria_nova_ja_concluida(self):
        resultado = db.marcar_ou_criar_feito(self.conn, "fui na academia")
        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["acao"], "registrada_e_concluida")
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (resultado["task_id"],)
        ).fetchone()
        self.assertEqual(row["title"], "fui na academia")
        self.assertIsNotNone(row["completed_at"])

    def test_com_tarefa_pendente_parecida_marca_ela_concluida(self):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("pagar conta de luz", date.today().isoformat()),
        )
        self.conn.commit()
        task_id = cur.lastrowid

        resultado = db.marcar_ou_criar_feito(self.conn, "conta de luz")
        self.assertEqual(resultado["acao"], "marcada_concluida")
        self.assertEqual(resultado["task_id"], task_id)
        row = self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertIsNotNone(row["completed_at"])
        # nao deve ter criado uma segunda tarefa
        total = self.conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"]
        self.assertEqual(total, 1)

    def test_nao_casa_com_tarefa_ja_concluida(self):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("pagar conta de luz", date.today().isoformat()),
        )
        self.conn.commit()
        resultado = db.marcar_ou_criar_feito(self.conn, "conta de luz")
        self.assertEqual(resultado["acao"], "registrada_e_concluida")
        self.assertNotEqual(resultado["task_id"], cur.lastrowid)

    def test_nao_casa_com_tarefa_futura(self):
        # tarefa pendente com prazo no futuro nao deveria ser "a mesma coisa
        # que ja fiz hoje" - so casa com pendentes sem prazo ou ja vencidas/de hoje
        futuro = (date.today() + timedelta(days=5)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta de luz", futuro)
        )
        self.conn.commit()
        resultado = db.marcar_ou_criar_feito(self.conn, "conta de luz")
        self.assertEqual(resultado["acao"], "registrada_e_concluida")

    def test_fecha_interacao_de_aprendizado_ao_casar_com_pendente(self):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("responder corretora", date.today().isoformat()),
        )
        self.conn.commit()
        task_id = cur.lastrowid
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", task_id)

        db.marcar_ou_criar_feito(self.conn, "corretora")

        row = self.conn.execute(
            "SELECT * FROM interacoes_aprendizado WHERE tipo = 'tarefa_parada' AND referencia_id = ?",
            (task_id,),
        ).fetchone()
        self.assertIsNotNone(row["resolvido_em"])

    def test_match_por_substring_nos_dois_sentidos(self):
        cur = self.conn.execute(
            "INSERT INTO tasks (title) VALUES (?)", ("ligar pro fornecedor de ferro",)
        )
        self.conn.commit()
        task_id = cur.lastrowid
        resultado = db.marcar_ou_criar_feito(self.conn, "fornecedor de ferro")
        self.assertEqual(resultado["task_id"], task_id)


class LatenciaMediaHorasTestCase(unittest.TestCase):
    def test_lista_vazia_retorna_none(self):
        self.assertIsNone(aprendizado.latencia_media_horas([]))

    def test_um_valor(self):
        self.assertEqual(aprendizado.latencia_media_horas([5.0]), 5.0)

    def test_media_simples(self):
        self.assertEqual(aprendizado.latencia_media_horas([1.0, 2.0, 3.0]), 2.0)

    def test_outlier_afeta_a_media_de_proposito(self):
        # diferente da mediana usada em limiar_personalizado, aqui um valor
        # extremo DEVE puxar o resultado - e sinal real, nao ruido.
        normal = aprendizado.latencia_media_horas([1.0, 1.0, 1.0])
        com_outlier = aprendizado.latencia_media_horas([1.0, 1.0, 100.0])
        self.assertGreater(com_outlier, normal)


if __name__ == "__main__":
    unittest.main()
