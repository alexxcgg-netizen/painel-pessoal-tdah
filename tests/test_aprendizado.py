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


class TokenizarTestCase(unittest.TestCase):
    def test_ignora_preposicao_artigo_e_palavra_curta(self):
        self.assertEqual(
            aprendizado._tokenizar("cotar portas com o fornecedor de ferro"),
            {"cotar", "portas", "fornecedor", "ferro"},
        )

    def test_texto_vazio(self):
        self.assertEqual(aprendizado._tokenizar(""), set())
        self.assertEqual(aprendizado._tokenizar(None), set())

    def test_minusculas_e_acento_preservado(self):
        self.assertIn("licença", aprendizado._tokenizar("Licença de voo"))


class GrupoDbTestCase(unittest.TestCase):
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

    def _criar_task(self, title, due_date, completed_at):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            (title, due_date, completed_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def _criar_espera(self, quem, criado_em, resolvido_em):
        cur = self.conn.execute(
            "INSERT INTO esperas (quem, sobre, criado_em, resolvido_em) VALUES (?, ?, ?, ?)",
            (quem, "algo", criado_em, resolvido_em),
        )
        self.conn.commit()
        return cur.lastrowid

    def test_dias_atraso_por_titulo_semelhante_agrupa_por_token_comum(self):
        self._criar_task("cotar portas com fornecedor", "2026-01-01", "2026-01-04 10:00:00")  # 3
        self._criar_task("cotar vasos com fornecedor", "2026-01-10", "2026-01-13 10:00:00")  # 3
        self._criar_task("lavar o carro", "2026-01-05", "2026-01-08 10:00:00")  # 3, sem token em comum
        resultado = aprendizado.dias_atraso_por_titulo_semelhante(self.conn, "cotar piso com fornecedor")
        self.assertEqual(sorted(resultado), [3, 3])

    def test_dias_atraso_por_titulo_semelhante_sem_token_relevante_retorna_vazio(self):
        self._criar_task("cotar portas com fornecedor", "2026-01-01", "2026-01-04 10:00:00")
        resultado = aprendizado.dias_atraso_por_titulo_semelhante(self.conn, "de na o em")
        self.assertEqual(resultado, [])

    def test_dias_atraso_por_titulo_semelhante_exclui_id_informado(self):
        task_id = self._criar_task("cotar portas com fornecedor", "2026-01-01", "2026-01-04 10:00:00")
        resultado = aprendizado.dias_atraso_por_titulo_semelhante(
            self.conn, "cotar portas com fornecedor", excluir_id=task_id
        )
        self.assertEqual(resultado, [])

    def test_dias_espera_por_quem_semelhante_agrupa_por_token_comum(self):
        self._criar_espera("fornecedor de ferro", "2026-01-01 10:00:00", "2026-01-06 10:00:00")  # 5
        self._criar_espera("fornecedor de ferro ltda", "2026-02-01 10:00:00", "2026-02-08 10:00:00")  # 7
        self._criar_espera("corretora do seguro", "2026-03-01 10:00:00", "2026-03-02 10:00:00")  # 1
        resultado = aprendizado.dias_espera_por_quem_semelhante(self.conn, "o fornecedor de ferro")
        self.assertEqual(sorted(resultado), [5, 7])

    def test_dias_espera_por_quem_semelhante_exclui_id_informado(self):
        espera_id = self._criar_espera("fornecedor de ferro", "2026-01-01 10:00:00", "2026-01-06 10:00:00")
        resultado = aprendizado.dias_espera_por_quem_semelhante(
            self.conn, "fornecedor de ferro", excluir_id=espera_id
        )
        self.assertEqual(resultado, [])

    def test_janela_recente_limita_as_mais_novas(self):
        # 3 tarefas antigas com 10 dias de atraso, 2 recentes com 1 dia -
        # com janela=2, so as 2 mais recentes (por completed_at) devem contar.
        for i in range(3):
            self._criar_task(f"antiga {i}", "2020-01-01", "2020-01-11 10:00:00")
        for i in range(2):
            self._criar_task(f"recente {i}", "2026-01-01", "2026-01-02 10:00:00")
        resultado = aprendizado.dias_atraso_historico_tarefas(self.conn, janela=2)
        self.assertEqual(sorted(resultado), [1, 1])

    def test_janela_maior_que_o_historico_devolve_tudo(self):
        self._criar_task("a", "2026-01-01", "2026-01-02 10:00:00")
        self._criar_task("b", "2026-01-05", "2026-01-06 10:00:00")
        resultado = aprendizado.dias_atraso_historico_tarefas(self.conn, janela=100)
        self.assertEqual(len(resultado), 2)

    def test_janela_none_e_o_padrao_sem_quebrar_comportamento_antigo(self):
        self._criar_task("a", "2026-01-01", "2026-01-02 10:00:00")
        resultado_sem_janela = aprendizado.dias_atraso_historico_tarefas(self.conn)
        self.assertEqual(resultado_sem_janela, [1])


class AjustarPelaEficaciaTestCase(unittest.TestCase):
    def test_sem_latencia_registrada_nao_ajusta(self):
        self.assertEqual(aprendizado._ajustar_pela_eficacia(5, None, piso=1), 5)

    def test_latencia_rapida_reduz_um_dia(self):
        self.assertEqual(aprendizado._ajustar_pela_eficacia(5, 10.0, piso=1), 4)

    def test_latencia_exatamente_no_limite_de_24h_reduz(self):
        self.assertEqual(aprendizado._ajustar_pela_eficacia(5, 24.0, piso=1), 4)

    def test_latencia_lenta_nao_reduz(self):
        self.assertEqual(aprendizado._ajustar_pela_eficacia(5, 48.0, piso=1), 5)

    def test_nunca_reduz_abaixo_do_piso(self):
        self.assertEqual(aprendizado._ajustar_pela_eficacia(1, 5.0, piso=1), 1)


class LimiarTarefaTestCase(unittest.TestCase):
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

    def test_sem_historico_nenhum_usa_padrao(self):
        valor, info = aprendizado.limiar_tarefa(self.conn, "cotar portas")
        self.assertEqual(valor, 3)
        self.assertEqual(info["fonte"], "padrao")

    def test_com_historico_especifico_suficiente_usa_ele(self):
        for i in range(5):
            self.conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"cotar {i} com fornecedor", "2026-01-01", "2026-01-03 10:00:00"),  # 2 dias
            )
        self.conn.commit()
        valor, info = aprendizado.limiar_tarefa(self.conn, "cotar piso com fornecedor")
        self.assertEqual(valor, 2)
        self.assertEqual(info["fonte"], "aprendido_especifico")

    def test_sem_historico_especifico_mas_com_global_usa_global(self):
        for i in range(5):
            self.conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"tarefa qualquer {i}", "2026-01-01", "2026-01-03 10:00:00"),  # 2 dias
            )
        self.conn.commit()
        # titulo sem nenhuma palavra em comum com o historico existente
        valor, info = aprendizado.limiar_tarefa(self.conn, "xyzabc123 completamente diferente")
        self.assertEqual(valor, 2)
        self.assertEqual(info["fonte"], "aprendido_global")

    def test_eficacia_reduz_o_limiar_quando_resposta_e_rapida(self):
        for i in range(5):
            self.conn.execute(
                "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                (f"tarefa {i}", "2026-01-01", "2026-01-06 10:00:00"),  # 5 dias
            )
        self.conn.commit()
        db.registrar_interacao_aprendizado(self.conn, "tarefa_parada", 999)
        self.conn.execute(
            "UPDATE interacoes_aprendizado SET resolvido_em = datetime('now'), latencia_horas = 2 "
            "WHERE referencia_id = 999"
        )
        self.conn.commit()
        valor, info = aprendizado.limiar_tarefa(self.conn, "tarefa nova qualquer")
        self.assertEqual(valor, 4)  # 5 (aprendido) - 1 (eficacia)
        self.assertTrue(info["ajustado_pela_eficacia"])

    def test_task_id_exclui_a_propria_tarefa_do_calculo_especifico(self):
        task_id = self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            ("cotar portas com fornecedor", "2026-01-01", "2026-01-03 10:00:00"),
        ).lastrowid
        self.conn.commit()
        valor, info = aprendizado.limiar_tarefa(self.conn, "cotar portas com fornecedor", task_id=task_id)
        self.assertEqual(info["fonte"], "padrao")  # a unica amostra era ela mesma, agora excluida


class LimiarEsperaTestCase(unittest.TestCase):
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

    def test_sem_historico_usa_padrao(self):
        valor, info = aprendizado.limiar_espera(self.conn, "fornecedor de ferro")
        self.assertEqual(valor, 5)
        self.assertEqual(info["fonte"], "padrao")

    def test_com_historico_especifico_por_quem_usa_ele(self):
        for i in range(5):
            self.conn.execute(
                "INSERT INTO esperas (quem, sobre, criado_em, resolvido_em) VALUES (?, ?, ?, ?)",
                (
                    "fornecedor de ferro",
                    f"item {i}",
                    "2026-01-01 10:00:00",
                    "2026-01-04 10:00:00",  # 3 dias
                ),
            )
        self.conn.commit()
        valor, info = aprendizado.limiar_espera(self.conn, "o fornecedor de ferro")
        self.assertEqual(valor, 3)
        self.assertEqual(info["fonte"], "aprendido_especifico")


class ProdutividadePorDiaSemanaTestCase(unittest.TestCase):
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
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            ("tarefa", due_date, completed_at),
        )
        self.conn.commit()

    def test_sem_historico_devolve_vazio(self):
        self.assertEqual(aprendizado.produtividade_por_dia_semana(self.conn), {})

    def test_dia_abaixo_do_minimo_de_amostras_fica_de_fora(self):
        # segunda-feira 2026-01-05, so 2 amostras (minimo padrao e 3)
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self.assertEqual(aprendizado.produtividade_por_dia_semana(self.conn), {})

    def test_taxa_no_prazo_calculada_corretamente(self):
        # 2026-01-05 e uma segunda (weekday 0) - 3 tarefas, 2 no prazo, 1 atrasada
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self._criar_task("2026-01-05", "2026-01-04 10:00:00")
        self._criar_task("2026-01-05", "2026-01-10 10:00:00")  # atrasada
        resultado = aprendizado.produtividade_por_dia_semana(self.conn)
        self.assertAlmostEqual(resultado[0], 2 / 3)

    def test_tarefa_ainda_nao_vencida_nao_conta(self):
        futuro = (date.today() + timedelta(days=30)).isoformat()
        self._criar_task(futuro, None)
        self._criar_task(futuro, None)
        self._criar_task(futuro, None)
        self.assertEqual(aprendizado.produtividade_por_dia_semana(self.conn), {})

    def test_tarefa_nunca_concluida_e_vencida_conta_como_fora_do_prazo(self):
        passado = "2020-01-06"  # segunda
        for _ in range(3):
            self._criar_task(passado, None)
        resultado = aprendizado.produtividade_por_dia_semana(self.conn)
        self.assertEqual(resultado[0], 0.0)


class CorrelacaoSonoProdutividadeTestCase(unittest.TestCase):
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
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            ("tarefa", due_date, completed_at),
        )
        self.conn.commit()

    def _gravar_sono(self, data, horas):
        self.conn.execute(
            "INSERT INTO saude_dados (data, sono_horas) VALUES (?, ?)", (data, horas)
        )
        self.conn.commit()

    def test_sem_historico_devolve_vazio(self):
        self.assertEqual(aprendizado.correlacao_sono_produtividade(self.conn), {})

    def test_dia_com_sono_mas_sem_tarefa_e_ignorado(self):
        self._gravar_sono("2026-01-05", 8.0)
        self.assertEqual(aprendizado.correlacao_sono_produtividade(self.conn), {})

    def test_bucket_abaixo_do_minimo_de_amostras_fica_de_fora(self):
        self._gravar_sono("2026-01-05", 8.0)
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self.assertEqual(aprendizado.correlacao_sono_produtividade(self.conn), {})

    def test_agrupa_por_faixa_de_sono_corretamente(self):
        self._gravar_sono("2026-01-05", 5.5)
        for _ in range(3):
            self._criar_task("2026-01-05", None)  # nunca concluida = fora do prazo
        self._gravar_sono("2026-01-06", 8.5)
        for _ in range(3):
            self._criar_task("2026-01-06", "2026-01-06 10:00:00")  # no prazo
        resultado = aprendizado.correlacao_sono_produtividade(self.conn)
        self.assertEqual(resultado["<6h"], 0.0)
        self.assertEqual(resultado["8h+"], 1.0)

    def test_dica_none_sem_dado_suficiente(self):
        self.assertIsNone(aprendizado.dica_sono_produtividade(self.conn))

    def test_dica_none_quando_diferenca_pequena(self):
        self._gravar_sono("2026-01-05", 5.5)
        for _ in range(3):
            self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self._gravar_sono("2026-01-06", 8.5)
        for _ in range(3):
            self._criar_task("2026-01-06", "2026-01-06 10:00:00")
        self.assertIsNone(aprendizado.dica_sono_produtividade(self.conn))

    def test_dica_sugere_dormir_mais_quando_faixa_maior_e_melhor(self):
        self._gravar_sono("2026-01-05", 5.5)
        for _ in range(3):
            self._criar_task("2026-01-05", None)
        self._gravar_sono("2026-01-06", 8.5)
        for _ in range(3):
            self._criar_task("2026-01-06", "2026-01-06 10:00:00")
        dica = aprendizado.dica_sono_produtividade(self.conn)
        self.assertIn("8h+", dica)
        self.assertIn("<6h", dica)
        self.assertIn("dormir mais", dica)

    def test_dica_sem_sugestao_quando_faixa_menor_e_melhor(self):
        # inverso do caso "faz sentido dormir mais" - aqui a faixa MENOR de
        # sono que teve mais produtividade, entao nao faz sentido sugerir
        # "durma mais" (seria o oposto do que o dado mostra).
        self._gravar_sono("2026-01-05", 5.5)
        for _ in range(3):
            self._criar_task("2026-01-05", "2026-01-05 10:00:00")
        self._gravar_sono("2026-01-06", 8.5)
        for _ in range(3):
            self._criar_task("2026-01-06", None)
        dica = aprendizado.dica_sono_produtividade(self.conn)
        self.assertNotIn("dormir mais", dica)


class NormalizarTextoIntentTestCase(unittest.TestCase):
    def test_minusculo_espacos_e_pontuacao_de_borda(self):
        self.assertEqual(
            aprendizado.normalizar_texto_intent("  Gastei 50 no Mercado.  "), "gastei 50 no mercado"
        )

    def test_espacos_duplicados_colapsam(self):
        self.assertEqual(aprendizado.normalizar_texto_intent("abre   os gastos"), "abre os gastos")

    def test_vazio_ou_tipo_errado_vira_vazio(self):
        self.assertEqual(aprendizado.normalizar_texto_intent(""), "")
        self.assertEqual(aprendizado.normalizar_texto_intent(None), "")
        self.assertEqual(aprendizado.normalizar_texto_intent(123), "")


class PadraoIntentAprendidoTestCase(unittest.TestCase):
    """US-A3 (Fase 5): camada robo antes da IA - ver docs/INTENT.md."""

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

    def test_sem_padrao_nenhum_nao_ha_atalho(self):
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "gastei 50 no mercado"))

    def test_confirmado_uma_vez_ainda_nao_aplica(self):
        aprendizado.confirmar_padrao_intent(self.conn, "gastei 50 no mercado", "registrar_gasto", {})
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "gastei 50 no mercado"))

    def test_confirmado_abaixo_do_limiar_ainda_nao_aplica(self):
        for _ in range(aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT - 1):
            aprendizado.confirmar_padrao_intent(self.conn, "gastei 50 no mercado", "registrar_gasto", {})
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "gastei 50 no mercado"))

    def test_confirmado_n_vezes_aplica(self):
        for _ in range(aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT):
            aprendizado.confirmar_padrao_intent(
                self.conn, "gastei 50 no mercado", "registrar_gasto", {"valor": 50.0}
            )
        padrao = aprendizado.padrao_intent_confiavel(self.conn, "gastei 50 no mercado")
        self.assertIsNotNone(padrao)
        self.assertEqual(padrao["acao"], "registrar_gasto")
        self.assertEqual(padrao["parametros"], {"valor": 50.0})

    def test_texto_normalizado_diferente_bate_no_mesmo_padrao(self):
        for _ in range(aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT):
            aprendizado.confirmar_padrao_intent(self.conn, "Gastei 50 no mercado.", "registrar_gasto", {})
        self.assertIsNotNone(aprendizado.padrao_intent_confiavel(self.conn, "gastei 50 no mercado"))

    def test_texto_diferente_nao_bate(self):
        for _ in range(aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT):
            aprendizado.confirmar_padrao_intent(self.conn, "gastei 50 no mercado", "registrar_gasto", {})
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "abre os gastos"))

    def test_acao_diferente_reinicia_a_contagem(self):
        aprendizado.confirmar_padrao_intent(self.conn, "isso", "registrar_tarefa", {})
        aprendizado.confirmar_padrao_intent(self.conn, "isso", "registrar_tarefa", {})
        # a IA muda de ideia na 3a vez - nao deveria destravar so por ter 3
        # confirmacoes se a ultima discordar das anteriores
        aprendizado.confirmar_padrao_intent(self.conn, "isso", "registrar_gasto", {})
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "isso"))

    def test_forcar_confianca_alta_pula_direto_pro_limiar(self):
        aprendizado.confirmar_padrao_intent(
            self.conn, "isso e gasto", "registrar_gasto", {}, forcar_confianca_alta=True
        )
        padrao = aprendizado.padrao_intent_confiavel(self.conn, "isso e gasto")
        self.assertIsNotNone(padrao)
        self.assertEqual(padrao["acao"], "registrar_gasto")

    def test_texto_vazio_nao_registra_nada(self):
        aprendizado.confirmar_padrao_intent(self.conn, "", "registrar_gasto", {})
        self.assertIsNone(db.buscar_padrao_intent(self.conn, ""))


class CorrecaoClassificacaoViraPadraoIntentTestCase(unittest.TestCase):
    """US-A4 (Fase 5): toda correcao manual (Fase 4,
    db.registrar_correcao_classificacao) tambem vira padrao de confianca alta
    em padroes_intent_aprendidos - sem precisar repetir o erro."""

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

    def test_correcao_pra_gasto_ja_resolve_texto_parecido_de_uma_vez(self):
        db.registrar_correcao_classificacao(
            self.conn, "academia mensalidade", "tarefa", None, "gasto", "saude"
        )
        padrao = aprendizado.padrao_intent_confiavel(self.conn, "academia mensalidade")
        self.assertIsNotNone(padrao)
        self.assertEqual(padrao["acao"], "registrar_gasto")
        self.assertEqual(padrao["parametros"], {"categoria": "saude"})

    def test_correcao_pra_tarefa_ja_resolve_texto_parecido_de_uma_vez(self):
        db.registrar_correcao_classificacao(
            self.conn, "comprar racao pro gato", "gasto", "mercado", "tarefa", None
        )
        padrao = aprendizado.padrao_intent_confiavel(self.conn, "comprar racao pro gato")
        self.assertIsNotNone(padrao)
        self.assertEqual(padrao["acao"], "registrar_tarefa")

    def test_correcao_pra_meta_nao_gera_padrao_de_intent(self):
        # "meta" nao tem acao equivalente em ACOES_INTENT ainda - decisao
        # documentada em db._TIPO_CERTO_PARA_ACAO_INTENT
        db.registrar_correcao_classificacao(
            self.conn, "juntar pra viagem", "tarefa", None, "meta", None
        )
        self.assertIsNone(aprendizado.padrao_intent_confiavel(self.conn, "juntar pra viagem"))
        # mas a correcao em si continua gravada normalmente (Fase 4)
        self.assertEqual(len(db.list_correcoes_classificacao(self.conn)), 1)

    def test_correcao_com_texto_normalizado_diferente_ainda_bate(self):
        db.registrar_correcao_classificacao(
            self.conn, "Academia Mensalidade.", "tarefa", None, "gasto", "saude"
        )
        self.assertIsNotNone(aprendizado.padrao_intent_confiavel(self.conn, "academia mensalidade"))


if __name__ == "__main__":
    unittest.main()
