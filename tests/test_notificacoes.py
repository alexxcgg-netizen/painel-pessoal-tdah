import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db
import notificacoes


class NotificacoesTestCase(unittest.TestCase):
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

    def test_silencio_dentro_da_janela_normal(self):
        agora = datetime(2026, 9, 21, 13, 0)
        self.assertTrue(notificacoes.dentro_do_horario_silencioso(agora, "12:00", "14:00"))

    def test_silencio_fora_da_janela_normal(self):
        agora = datetime(2026, 9, 21, 15, 0)
        self.assertFalse(notificacoes.dentro_do_horario_silencioso(agora, "12:00", "14:00"))

    def test_silencio_janela_cruza_meia_noite_depois_do_inicio(self):
        agora = datetime(2026, 9, 21, 23, 30)
        self.assertTrue(notificacoes.dentro_do_horario_silencioso(agora, "22:00", "07:00"))

    def test_silencio_janela_cruza_meia_noite_antes_do_fim(self):
        agora = datetime(2026, 9, 22, 5, 0)
        self.assertTrue(notificacoes.dentro_do_horario_silencioso(agora, "22:00", "07:00"))

    def test_silencio_janela_cruza_meia_noite_fora_da_janela(self):
        agora = datetime(2026, 9, 21, 12, 0)
        self.assertFalse(notificacoes.dentro_do_horario_silencioso(agora, "22:00", "07:00"))

    def test_silencio_nos_limites_exatos(self):
        # inicio inclusivo, fim exclusivo
        self.assertTrue(
            notificacoes.dentro_do_horario_silencioso(datetime(2026, 9, 21, 22, 0), "22:00", "07:00")
        )
        self.assertFalse(
            notificacoes.dentro_do_horario_silencioso(datetime(2026, 9, 21, 7, 0), "22:00", "07:00")
        )

    def test_silencio_inicio_igual_fim_desativa(self):
        agora = datetime(2026, 9, 21, 23, 0)
        self.assertFalse(notificacoes.dentro_do_horario_silencioso(agora, "22:00", "22:00"))

    def test_tarefas_aguardando_bom_tempo_filtra_pela_flag(self):
        self.conn.execute(
            "INSERT INTO tasks (title, depende_do_tempo) VALUES (?, 1)", ("limpar o quarto",)
        )
        self.conn.execute("INSERT INTO tasks (title, depende_do_tempo) VALUES (?, 0)", ("outra coisa",))
        self.conn.commit()
        r = notificacoes.tarefas_aguardando_bom_tempo(self.conn)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["title"], "limpar o quarto")

    def test_tarefas_aguardando_bom_tempo_ignora_concluida(self):
        self.conn.execute(
            "INSERT INTO tasks (title, depende_do_tempo, completed_at) VALUES (?, 1, datetime('now'))",
            ("limpar o quarto",),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.tarefas_aguardando_bom_tempo(self.conn), [])

    def test_sem_tarefa_atrasada_retorna_none(self):
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_tarefa_atrasada_e_contada(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", ontem))
        self.conn.commit()
        self.assertEqual(notificacoes.tarefas_atrasadas(self.conn), "Voce tem 1 tarefa atrasada.")

    def test_tarefa_concluida_nao_conta_como_atrasada(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("pagar conta", ontem),
        )
        self.conn.commit()
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_tarefa_sem_data_nao_conta_como_atrasada(self):
        self.conn.execute("INSERT INTO tasks (title) VALUES (?)", ("algo vago",))
        self.conn.commit()
        self.assertIsNone(notificacoes.tarefas_atrasadas(self.conn))

    def test_tarefas_paradas_vazio_sem_tarefa_atrasada(self):
        self.assertEqual(notificacoes.tarefas_paradas(self.conn), [])

    def test_tarefas_paradas_ignora_atraso_recente(self):
        dois_dias = (date.today() - timedelta(days=2)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", dois_dias))
        self.conn.commit()
        self.assertEqual(notificacoes.tarefas_paradas(self.conn, dias_minimo=3), [])

    def test_tarefas_paradas_detecta_parada_no_limite(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("pagar conta", tres_dias))
        self.conn.commit()
        avisos = notificacoes.tarefas_paradas(self.conn, dias_minimo=3)
        self.assertEqual(len(avisos), 1)
        tarefa_id, msg = avisos[0]
        self.assertIn("pagar conta", msg)
        self.assertIn("3 dias", msg)
        self.assertIsInstance(tarefa_id, int)

    def test_tarefas_paradas_ignora_concluida(self):
        tres_dias = (date.today() - timedelta(days=3)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, datetime('now'))",
            ("pagar conta", tres_dias),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.tarefas_paradas(self.conn), [])

    def test_ja_notificado_alguma_vez_ignora_a_data(self):
        self.assertFalse(db.ja_notificado_alguma_vez(self.conn, "tarefa_parada", 42))
        db.marcar_notificado(self.conn, "tarefa_parada", 42)
        self.assertTrue(db.ja_notificado_alguma_vez(self.conn, "tarefa_parada", 42))
        # outro tipo ou outra referencia nao conta como "ja notificado"
        self.assertFalse(db.ja_notificado_alguma_vez(self.conn, "tarefa_parada", 43))
        self.assertFalse(db.ja_notificado_alguma_vez(self.conn, "outro_tipo", 42))

    def test_tarefas_paradas_lista_varias_com_dias_corretos(self):
        cinco_dias = (date.today() - timedelta(days=5)).isoformat()
        dez_dias = (date.today() - timedelta(days=10)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("tarefa a", cinco_dias))
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("tarefa b", dez_dias))
        self.conn.commit()
        avisos = notificacoes.tarefas_paradas(self.conn)
        self.assertEqual(len(avisos), 2)
        textos = " ".join(msg for _, msg in avisos)
        self.assertIn("5 dias", textos)
        self.assertIn("10 dias", textos)

    def test_meta_fora_do_ritmo_e_detectada(self):
        criado = (datetime.now() - timedelta(days=50)).isoformat()
        prazo = (date.today() + timedelta(days=50)).isoformat()
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("Moto", 10000, prazo, 100, criado),
        )
        self.conn.commit()
        avisos = notificacoes.metas_fora_do_ritmo(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Moto", avisos[0][1])

    def test_meta_no_ritmo_nao_e_avisada(self):
        criado = (datetime.now() - timedelta(days=50)).isoformat()
        prazo = (date.today() + timedelta(days=50)).isoformat()
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("Moto", 10000, prazo, 5000, criado),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.metas_fora_do_ritmo(self.conn), [])

    def test_meta_sem_prazo_e_ignorada(self):
        self.conn.execute(
            "INSERT INTO goals (titulo, valor_alvo, valor_guardado) VALUES (?, ?, ?)",
            ("Sem prazo", 10000, 0),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.metas_fora_do_ritmo(self.conn), [])

    def test_gasto_semana_elevado_detectado(self):
        hoje = date.today()
        for i in range(1, 4):
            dia = hoje - timedelta(days=7 * i + 2)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (500, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        msg = notificacoes.gasto_semana_elevado(self.conn)
        self.assertIsNotNone(msg)
        self.assertIn("500.00", msg)

    def test_gasto_semana_normal_nao_avisa(self):
        hoje = date.today()
        for i in range(0, 4):
            dia = hoje - timedelta(days=7 * i + 1)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.commit()
        self.assertIsNone(notificacoes.gasto_semana_elevado(self.conn))

    def test_gasto_dia_semana_atipico_detectado(self):
        hoje = date.today()
        for i in range(1, 5):
            dia = hoje - timedelta(days=7 * i)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (300, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        msg = notificacoes.gasto_dia_semana_atipico(self.conn, hoje=hoje)
        self.assertIsNotNone(msg)
        self.assertIn("300.00", msg)

    def test_gasto_dia_semana_normal_nao_avisa(self):
        hoje = date.today()
        for i in range(1, 5):
            dia = hoje - timedelta(days=7 * i)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (55, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        self.assertIsNone(notificacoes.gasto_dia_semana_atipico(self.conn, hoje=hoje))

    def test_gasto_dia_semana_sem_gasto_hoje_nao_avisa(self):
        hoje = date.today()
        for i in range(1, 5):
            dia = hoje - timedelta(days=7 * i)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.commit()
        self.assertIsNone(notificacoes.gasto_dia_semana_atipico(self.conn, hoje=hoje))

    def test_gasto_dia_semana_sem_historico_nao_avisa(self):
        hoje = date.today()
        semana_passada = hoje - timedelta(days=7)
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (50, "mercado", semana_passada.isoformat()),
        )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (500, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        # so 1 amostra de historico (precisa de pelo menos 2 pra comparar)
        self.assertIsNone(notificacoes.gasto_dia_semana_atipico(self.conn, hoje=hoje))

    def test_gasto_dia_semana_ignora_gasto_planejado(self):
        hoje = date.today()
        for i in range(1, 5):
            dia = hoje - timedelta(days=7 * i)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at, tipo) VALUES (?, ?, ?, 'planejado')",
            (500, "mercado", hoje.isoformat()),
        )
        self.conn.commit()
        self.assertIsNone(notificacoes.gasto_dia_semana_atipico(self.conn, hoje=hoje))

    def test_gasto_dia_semana_atipico_menciona_dia_da_semana(self):
        segunda = date(2026, 9, 21)  # segunda-feira
        for i in range(1, 5):
            dia = segunda - timedelta(days=7 * i)
            self.conn.execute(
                "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
                (50, "mercado", dia.isoformat()),
            )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, created_at) VALUES (?, ?, ?)",
            (300, "mercado", segunda.isoformat()),
        )
        self.conn.commit()
        msg = notificacoes.gasto_dia_semana_atipico(self.conn, hoje=segunda)
        self.assertIn("segunda-feira", msg)

    def test_lembrete_unico_proximo_e_avisado(self):
        data = (date.today() + timedelta(days=3)).isoformat()
        db.create_lembrete(self.conn, "Renovar seguro do carro", data, recorrente=False)
        avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Renovar seguro do carro", avisos[0][1])
        self.assertIn("3 dias", avisos[0][1])

    def test_lembrete_unico_longe_nao_avisa(self):
        data = (date.today() + timedelta(days=30)).isoformat()
        db.create_lembrete(self.conn, "Renovar seguro do carro", data, recorrente=False)
        self.assertEqual(notificacoes.lembretes_proximos(self.conn), [])

    def test_lembrete_unico_ja_passou_nao_avisa(self):
        data = (date.today() - timedelta(days=2)).isoformat()
        db.create_lembrete(self.conn, "Coisa antiga", data, recorrente=False)
        self.assertEqual(notificacoes.lembretes_proximos(self.conn), [])

    def test_lembrete_recorrente_calcula_proximo_aniversario(self):
        data_original = (date.today() - timedelta(days=360)).isoformat()
        db.create_lembrete(self.conn, "Validade da licenca de piloto", data_original, recorrente=True)
        avisos = notificacoes.lembretes_proximos(self.conn, dias=10)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Validade da licenca de piloto", avisos[0][1])

    def test_lembrete_recorrente_hoje(self):
        data_original = date.today().replace(year=date.today().year - 1).isoformat()
        db.create_lembrete(self.conn, "Aniversario", data_original, recorrente=True)
        avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("e hoje", avisos[0][1])

    def test_tarefa_com_horario_ja_chegado_e_avisada(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "14:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=14, minute=5)
        avisos = notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora)
        self.assertEqual(len(avisos), 1)
        self.assertIn("colocar o lixo pra fora", avisos[0][1])

    def test_tarefa_com_horario_ainda_nao_chegado_nao_avisa(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("colocar o lixo pra fora", hoje, "14:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=13, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_com_horario_de_outro_dia_nao_avisa(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)",
            ("consulta amanha", amanha, "09:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_sem_horario_nunca_avisa_aqui(self):
        hoje = date.today().isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("so com prazo", hoje))
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_tarefa_com_horario_concluida_nao_avisa(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, datetime('now'))",
            ("ja fiz", hoje, "08:00"),
        )
        self.conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=59)
        self.assertEqual(notificacoes.tarefas_com_horario_chegando(self.conn, agora=agora), [])

    def test_voo_de_hoje_com_hora_e_sem_horas_e_candidato(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO voos (data, destino, hora) VALUES (?, ?, ?)", (hoje, "Navegantes", "14:00")
        )
        self.conn.commit()
        candidatos = notificacoes.voos_de_hoje_com_horario(self.conn)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["destino"], "Navegantes")
        self.assertEqual(candidatos[0]["hora"], "14:00")

    def test_voo_sem_hora_nao_e_candidato(self):
        hoje = date.today().isoformat()
        self.conn.execute("INSERT INTO voos (data, destino) VALUES (?, ?)", (hoje, "Navegantes"))
        self.conn.commit()
        self.assertEqual(notificacoes.voos_de_hoje_com_horario(self.conn), [])

    def test_voo_ja_realizado_nao_e_candidato(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO voos (data, destino, hora, horas) VALUES (?, ?, ?, ?)",
            (hoje, "Navegantes", "14:00", 1.5),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.voos_de_hoje_com_horario(self.conn), [])

    def test_voo_de_outro_dia_nao_e_candidato(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.conn.execute(
            "INSERT INTO voos (data, destino, hora) VALUES (?, ?, ?)", (amanha, "Navegantes", "14:00")
        )
        self.conn.commit()
        self.assertEqual(notificacoes.voos_de_hoje_com_horario(self.conn), [])

    def _domingo_as(self, hora, minuto):
        """Acha o domingo mais proximo (indo pra tras) e devolve com esse horario."""
        hoje = date.today()
        domingo = hoje - timedelta(days=(hoje.weekday() + 1) % 7)
        return datetime.combine(domingo, datetime.min.time()).replace(hour=hora, minute=minuto)

    def test_planejamento_semanal_devido_domingo_as_2030(self):
        self.assertTrue(notificacoes.planejamento_semanal_devido(self._domingo_as(20, 30)))
        self.assertTrue(notificacoes.planejamento_semanal_devido(self._domingo_as(20, 34)))

    def test_planejamento_semanal_nao_devido_fora_da_janela(self):
        self.assertFalse(notificacoes.planejamento_semanal_devido(self._domingo_as(20, 29)))
        self.assertFalse(notificacoes.planejamento_semanal_devido(self._domingo_as(20, 35)))
        self.assertFalse(notificacoes.planejamento_semanal_devido(self._domingo_as(9, 0)))

    def test_planejamento_semanal_nao_devido_em_outro_dia_da_semana(self):
        segunda = self._domingo_as(20, 30) + timedelta(days=1)
        self.assertFalse(notificacoes.planejamento_semanal_devido(segunda))

    def _hoje_as(self, hora, minuto):
        return datetime.combine(date.today(), datetime.min.time()).replace(hour=hora, minute=minuto)

    def test_hora_de_dormir_devida_as_22h(self):
        self.assertTrue(notificacoes.hora_de_dormir_devida(self._hoje_as(22, 0)))
        self.assertTrue(notificacoes.hora_de_dormir_devida(self._hoje_as(22, 4)))

    def test_hora_de_dormir_nao_devida_fora_da_janela(self):
        self.assertFalse(notificacoes.hora_de_dormir_devida(self._hoje_as(21, 59)))
        self.assertFalse(notificacoes.hora_de_dormir_devida(self._hoje_as(22, 5)))
        self.assertFalse(notificacoes.hora_de_dormir_devida(self._hoje_as(9, 0)))

    def test_currency_voo_sem_voo_nenhum_e_none(self):
        self.assertIsNone(notificacoes.currency_voo_baixa(self.conn))

    def test_currency_voo_dentro_do_limiar_nao_avisa(self):
        recente = (date.today() - timedelta(days=5)).isoformat()
        self.conn.execute(
            "INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)", (recente, "Navegantes", 1.0)
        )
        self.conn.commit()
        self.assertIsNone(notificacoes.currency_voo_baixa(self.conn, limiar_dias=21))

    def test_currency_voo_acima_do_limiar_avisa(self):
        antigo = (date.today() - timedelta(days=25)).isoformat()
        self.conn.execute(
            "INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)", (antigo, "Navegantes", 1.0)
        )
        self.conn.commit()
        msg = notificacoes.currency_voo_baixa(self.conn, limiar_dias=21)
        self.assertIsNotNone(msg)
        self.assertIn("25 dias", msg)

    def test_currency_voo_ignora_voo_so_agendado(self):
        antigo = (date.today() - timedelta(days=25)).isoformat()
        self.conn.execute("INSERT INTO voos (data, destino) VALUES (?, ?)", (antigo, "Navegantes"))
        self.conn.commit()
        self.assertIsNone(notificacoes.currency_voo_baixa(self.conn, limiar_dias=21))


if __name__ == "__main__":
    unittest.main()
