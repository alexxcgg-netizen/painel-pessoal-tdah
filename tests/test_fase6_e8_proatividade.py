"""Fase 6, Grupo E5 (US-E8): proatividade unificada - habito que passou
batido, tarefa que passou da hora, cartao perto/estourando o limite
(US-E15), renda do mes perto de acabar, projeto juntando poeira (US-E13) e
projecao do mes seguinte apertada. Todo teste de timing usa relogio
controlado (parametro `hoje`/`agora` explicito nas funcoes de
notificacoes.py, ou patch("app.datetime") pro pipeline completo) - nunca
depende da hora real de quando o teste roda.

Segue o padrao de tests/test_pin_inicial.py: db.DB_PATH pra um arquivo
temporario + db.garantir_banco_nao_producao() ANTES de importar app."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import notificacoes
import vida

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


def _inserir_gasto(conn, category, amount, descricao, quando: date):
    conn.execute(
        "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (?, ?, ?, 'real', ?)",
        (amount, category, descricao, quando.isoformat() + " 12:00:00"),
    )
    conn.commit()


def _inserir_renda(conn, amount, quando: date):
    conn.execute(
        "INSERT INTO incomes (amount, category, created_at) VALUES (?, 'salario', ?)",
        (amount, quando.isoformat() + " 09:00:00"),
    )
    conn.commit()


class Fase6E8TestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200

    def tearDown(self):
        self.conn.close()

    # ---- Habito passou batido (1h depois do horario) -----------------------

    def test_habito_passa_batido_1h_depois(self):
        habito_id = db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        agora = datetime(2026, 9, 23, 9, 1)  # 1h01 depois de 08:00
        avisos = notificacoes.habitos_passaram_batido(self.conn, agora)
        self.assertEqual(len(avisos), 1)
        hid, msg = avisos[0]
        self.assertEqual(hid, habito_id)
        self.assertEqual(msg, "08:00 ja foi e o habito Meditar segue intocado.")

    def test_habito_nao_passa_batido_antes_de_1h(self):
        db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        agora = datetime(2026, 9, 23, 8, 30)  # so 30 min depois
        self.assertEqual(notificacoes.habitos_passaram_batido(self.conn, agora), [])

    def test_habito_marcado_nao_avisa(self):
        habito_id = db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        db.alternar_habito_dia(self.conn, "2026-09-23", habito_id)
        agora = datetime(2026, 9, 23, 9, 30)
        self.assertEqual(notificacoes.habitos_passaram_batido(self.conn, agora), [])

    def test_habito_sem_horario_nunca_avisa(self):
        db.create_habito(self.conn, "Ler", None, "diario", None, None, None)
        agora = datetime(2026, 9, 23, 23, 0)
        self.assertEqual(notificacoes.habitos_passaram_batido(self.conn, agora), [])

    # ---- Tarefa passou da hora (30 min depois) ------------------------------

    def test_tarefa_passa_da_hora_30min_depois(self):
        hoje = date(2026, 9, 23)
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Ligar pro dentista', ?, '14:00')",
            (hoje.isoformat(),),
        )
        self.conn.commit()
        agora = datetime(2026, 9, 23, 14, 31)
        avisos = notificacoes.tarefas_horario_passou(self.conn, agora)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(
            avisos[0][1], "\"Ligar pro dentista\" - a tarefa era 14:00, ainda da tempo de resolver hoje."
        )

    def test_tarefa_nao_passa_da_hora_antes_de_30min(self):
        hoje = date(2026, 9, 23)
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Ligar pro dentista', ?, '14:00')",
            (hoje.isoformat(),),
        )
        self.conn.commit()
        agora = datetime(2026, 9, 23, 14, 15)
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, agora), [])

    def test_tarefa_concluida_nao_avisa(self):
        hoje = date(2026, 9, 23)
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('X', ?, '14:00', datetime('now'))",
            (hoje.isoformat(),),
        )
        self.conn.commit()
        agora = datetime(2026, 9, 23, 15, 0)
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, agora), [])

    # ---- Cartao perto/estourando o limite (US-E15) --------------------------

    def test_cartao_90_por_cento_avisa_quase(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        hoje = date(2026, 9, 23)
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": hoje.isoformat(), "descricao": "compra", "valor": -900.0, "external_id": "t1"}]
        )
        db.definir_limite_conta(self.conn, conta_id, 1000)
        avisos = notificacoes.cartoes_perto_ou_estourados(self.conn, hoje)
        self.assertEqual(len(avisos), 1)
        conta, nivel, titulo, corpo = avisos[0]
        self.assertEqual(conta, conta_id)
        self.assertEqual(nivel, "quase")
        self.assertEqual(titulo, "Cartao em 90% do limite")
        self.assertEqual(corpo, "nubank: sobram R$ 100.00.")

    def test_cartao_estourado(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        hoje = date(2026, 9, 23)
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": hoje.isoformat(), "descricao": "compra", "valor": -1200.0, "external_id": "t1"}]
        )
        db.definir_limite_conta(self.conn, conta_id, 1000)
        avisos = notificacoes.cartoes_perto_ou_estourados(self.conn, hoje)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0][1], "estourado")
        self.assertEqual(avisos[0][2], "Cartao estourou o limite")

    def test_cartao_abaixo_de_90_nao_avisa(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        hoje = date(2026, 9, 23)
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": hoje.isoformat(), "descricao": "compra", "valor": -500.0, "external_id": "t1"}]
        )
        db.definir_limite_conta(self.conn, conta_id, 1000)
        self.assertEqual(notificacoes.cartoes_perto_ou_estourados(self.conn, hoje), [])

    def test_cartao_sem_limite_nao_avisa(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        hoje = date(2026, 9, 23)
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": hoje.isoformat(), "descricao": "compra", "valor": -900.0, "external_id": "t1"}]
        )
        self.assertEqual(notificacoes.cartoes_perto_ou_estourados(self.conn, hoje), [])

    # ---- Renda perto de acabar -----------------------------------------------

    def test_renda_70_por_cento_avisa(self):
        hoje = date(2026, 9, 23)
        _inserir_renda(self.conn, 2000, date(2026, 9, 1))
        _inserir_gasto(self.conn, "mercado", 1500, "compras", date(2026, 9, 10))
        resultado = notificacoes.renda_perto_de_acabar(self.conn, hoje)
        self.assertIsNotNone(resultado)
        nivel, titulo, corpo = resultado
        self.assertEqual(nivel, "atencao")
        self.assertEqual(titulo, "75% da renda ja foi")
        self.assertEqual(corpo, "sobram R$ 500.00.")

    def test_renda_estourada(self):
        hoje = date(2026, 9, 23)
        _inserir_renda(self.conn, 1000, date(2026, 9, 1))
        _inserir_gasto(self.conn, "mercado", 1300, "compras", date(2026, 9, 10))
        nivel, titulo, corpo = notificacoes.renda_perto_de_acabar(self.conn, hoje)
        self.assertEqual(nivel, "estourado")
        self.assertIn("passou R$ 300.00 da renda", corpo)

    def test_renda_abaixo_de_70_nao_avisa(self):
        hoje = date(2026, 9, 23)
        _inserir_renda(self.conn, 2000, date(2026, 9, 1))
        _inserir_gasto(self.conn, "mercado", 500, "compras", date(2026, 9, 10))
        self.assertIsNone(notificacoes.renda_perto_de_acabar(self.conn, hoje))

    def test_renda_sem_renda_registrada_nao_avisa(self):
        hoje = date(2026, 9, 23)
        _inserir_gasto(self.conn, "mercado", 500, "compras", date(2026, 9, 10))
        self.assertIsNone(notificacoes.renda_perto_de_acabar(self.conn, hoje))

    # ---- Projeto juntando poeira (US-E13) ------------------------------------

    def test_projeto_sem_toque_desde_a_criacao(self):
        hoje = date(2026, 9, 23)
        criado = hoje - timedelta(days=25)
        projeto_id = db.create_projeto(self.conn, "Reforma da cozinha", None)
        self.conn.execute(
            "UPDATE projetos SET criado_em = ? WHERE id = ?", (criado.isoformat() + " 10:00:00", projeto_id)
        )
        self.conn.commit()
        avisos = notificacoes.projetos_juntando_poeira(self.conn, hoje)
        self.assertEqual(len(avisos), 1)
        _, titulo, corpo = avisos[0]
        self.assertEqual(titulo, "Tem projeto criando poeira")
        self.assertEqual(
            corpo, "\"Reforma da cozinha\": 25 dias sem um toque, abre e derruba a menor etapa."
        )

    def test_projeto_tocado_recentemente_nao_avisa(self):
        hoje = date(2026, 9, 23)
        projeto_id = db.create_projeto(self.conn, "Reforma da cozinha", None)
        etapa_id = db.adicionar_etapa_projeto(self.conn, projeto_id, "Comprar tinta", None)
        db.concluir_etapa_projeto(self.conn, etapa_id)
        tocado = hoje - timedelta(days=10)
        self.conn.execute(
            "UPDATE projeto_etapas SET feita_em = ? WHERE id = ?", (tocado.isoformat() + " 10:00:00", etapa_id)
        )
        self.conn.commit()
        self.assertEqual(notificacoes.projetos_juntando_poeira(self.conn, hoje), [])

    def test_projeto_pausado_nunca_avisa(self):
        hoje = date(2026, 9, 23)
        criado = hoje - timedelta(days=40)
        projeto_id = db.create_projeto(self.conn, "Projeto parado por escolha", None)
        self.conn.execute(
            "UPDATE projetos SET criado_em = ?, status = 'pausado' WHERE id = ?",
            (criado.isoformat() + " 10:00:00", projeto_id),
        )
        self.conn.commit()
        self.assertEqual(notificacoes.projetos_juntando_poeira(self.conn, hoje), [])

    def test_projeto_100_por_cento_nao_avisa(self):
        hoje = date(2026, 9, 23)
        criado = hoje - timedelta(days=40)
        projeto_id = db.create_projeto(self.conn, "Projeto concluido", None)
        etapa_id = db.adicionar_etapa_projeto(self.conn, projeto_id, "Unica etapa", None)
        db.concluir_etapa_projeto(self.conn, etapa_id)
        self.conn.execute(
            "UPDATE projetos SET criado_em = ? WHERE id = ?", (criado.isoformat() + " 10:00:00", projeto_id)
        )
        self.conn.commit()
        self.assertEqual(notificacoes.projetos_juntando_poeira(self.conn, hoje), [])

    def test_projeto_ref_dedup_muda_quando_projeto_e_tocado(self):
        hoje = date(2026, 9, 23)
        criado = hoje - timedelta(days=25)
        projeto_id = db.create_projeto(self.conn, "Projeto X", None)
        self.conn.execute(
            "UPDATE projetos SET criado_em = ? WHERE id = ?", (criado.isoformat() + " 10:00:00", projeto_id)
        )
        self.conn.commit()
        ref_antes = notificacoes.projetos_juntando_poeira(self.conn, hoje)[0][0]

        etapa_id = db.adicionar_etapa_projeto(self.conn, projeto_id, "Etapa 1", None)
        db.adicionar_etapa_projeto(self.conn, projeto_id, "Etapa 2 (ainda pendente)", None)
        db.concluir_etapa_projeto(self.conn, etapa_id)
        toque = hoje + timedelta(days=1)  # o Alex mexeu no projeto de novo
        self.conn.execute(
            "UPDATE projeto_etapas SET feita_em = ? WHERE id = ?", (toque.isoformat() + " 10:00:00", etapa_id)
        )
        self.conn.commit()
        depois = toque + timedelta(days=25)  # ficou parado de novo, outros 25 dias
        ref_depois = notificacoes.projetos_juntando_poeira(self.conn, depois)[0][0]
        self.assertNotEqual(ref_antes, ref_depois)

    # ---- Projecao do mes seguinte apertada -----------------------------------

    def test_projecao_devida_so_nos_ultimos_3_dias_do_mes(self):
        self.assertFalse(notificacoes.projecao_mes_seguinte_devida(date(2026, 9, 15)))
        self.assertTrue(notificacoes.projecao_mes_seguinte_devida(date(2026, 9, 28)))
        self.assertTrue(notificacoes.projecao_mes_seguinte_devida(date(2026, 9, 29)))
        self.assertTrue(notificacoes.projecao_mes_seguinte_devida(date(2026, 9, 30)))

    def test_mes_seguinte_apertado_outubro(self):
        hoje = date(2026, 9, 29)
        # renda media dos ultimos 3 meses fechados (jun/jul/ago) = 3000
        _inserir_renda(self.conn, 3000, date(2026, 6, 5))
        _inserir_renda(self.conn, 3000, date(2026, 7, 5))
        _inserir_renda(self.conn, 3000, date(2026, 8, 5))
        # custo fixo recorrente (aluguel) de 2400, confirmado em 2 meses
        _inserir_gasto(self.conn, "moradia", 2400, "Aluguel", date(2026, 8, 5))
        _inserir_gasto(self.conn, "moradia", 2400, "Aluguel", date(2026, 9, 5))
        resultado = notificacoes.mes_seguinte_apertado(self.conn, hoje)
        self.assertIsNotNone(resultado)
        nome_mes, fracao = resultado
        self.assertEqual(nome_mes, "Outubro")
        self.assertAlmostEqual(fracao, 0.8, places=4)

    def test_mes_seguinte_sem_renda_nao_projeta(self):
        hoje = date(2026, 9, 29)
        _inserir_gasto(self.conn, "moradia", 2400, "Aluguel", date(2026, 8, 5))
        _inserir_gasto(self.conn, "moradia", 2400, "Aluguel", date(2026, 9, 5))
        self.assertIsNone(notificacoes.mes_seguinte_apertado(self.conn, hoje))

    def test_mes_seguinte_abaixo_do_limiar_nao_avisa(self):
        hoje = date(2026, 9, 29)
        _inserir_renda(self.conn, 5000, date(2026, 6, 5))
        _inserir_renda(self.conn, 5000, date(2026, 7, 5))
        _inserir_renda(self.conn, 5000, date(2026, 8, 5))
        _inserir_gasto(self.conn, "moradia", 1000, "Aluguel", date(2026, 8, 5))
        _inserir_gasto(self.conn, "moradia", 1000, "Aluguel", date(2026, 9, 5))
        self.assertIsNone(notificacoes.mes_seguinte_apertado(self.conn, hoje))


class Fase6E8PipelineTestCase(unittest.TestCase):
    """Confere que a US-E8 passa pelo MESMO pipeline de sempre
    (app._avisos_proatividade_e8 so monta; verificar_e_notificar continua
    sendo quem despacha, dedup, filtra hiperfoco/silencioso/viagem)."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200
        self._silencio_patch = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        self._silencio_patch.start()
        self.addCleanup(self._silencio_patch.stop)

    def tearDown(self):
        self.conn.close()

    def test_monta_avisos_habito_e_tarefa(self):
        habito_id = db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        hoje = date(2026, 9, 23).isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Ligar', ?, '14:00')", (hoje,)
        )
        self.conn.commit()
        agora = datetime(2026, 9, 23, 14, 31)
        avisos = app._avisos_proatividade_e8(self.conn, agora)
        tipos = {a[0] for a in avisos}
        self.assertIn("habito_passou_batido", tipos)
        self.assertIn("tarefa_horario_passou", tipos)

    def test_dedup_nao_repete_no_mesmo_dia(self):
        db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        agora = datetime(2026, 9, 23, 9, 30)
        primeira = app._avisos_proatividade_e8(self.conn, agora)
        self.assertEqual(len(primeira), 1)
        for tipo, ref, titulo, corpo in primeira:
            db.marcar_notificado(self.conn, tipo, ref)
        segunda = app._avisos_proatividade_e8(self.conn, agora)
        self.assertEqual(segunda, [])

    def test_cartao_limite_dedup_e_alguma_vez_nao_por_dia(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": "2026-09-23", "descricao": "compra", "valor": -900.0, "external_id": "t1"}]
        )
        db.definir_limite_conta(self.conn, conta_id, 1000)
        agora = datetime(2026, 9, 23, 12, 0)
        avisos = app._avisos_proatividade_e8(self.conn, agora)
        cartoes = [a for a in avisos if a[0] == "cartao_limite"]
        self.assertEqual(len(cartoes), 1)
        for tipo, ref, titulo, corpo in cartoes:
            db.marcar_notificado(self.conn, tipo, ref)
        # dia seguinte, mesmo estado (ainda 90%) - nao repete (ja_notificado_alguma_vez)
        avisos_dia_seguinte = app._avisos_proatividade_e8(self.conn, datetime(2026, 9, 24, 12, 0))
        self.assertEqual([a for a in avisos_dia_seguinte if a[0] == "cartao_limite"], [])

    def test_hiperfoco_segura_aviso_nao_critico(self):
        db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        ate = (datetime(2026, 9, 23, 9, 0) + timedelta(minutes=30)).isoformat(timespec="seconds")
        app.definir_configuracao(self.conn, "hiperfoco_ate", ate)
        with patch("push_client.configurado", return_value=True), patch(
            "telegram_bot.configurado", return_value=False
        ), patch(
            "app.list_push_subscriptions",
            return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
        ), patch("push_client.enviar", return_value=True) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 9, 23, 9, 15)  # dentro do hiperfoco
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            app.verificar_e_notificar()
            titulos = [c.args[1] for c in mock_enviar.call_args_list]
        self.assertNotIn("Passou batido", titulos)

    def test_avisos_proatividade_passam_pelo_push_real_do_pipeline(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        db.insert_bank_transactions(
            self.conn, conta_id, [{"data": "2026-09-23", "descricao": "compra", "valor": -1200.0, "external_id": "t1"}]
        )
        db.definir_limite_conta(self.conn, conta_id, 1000)
        with patch("push_client.configurado", return_value=True), patch(
            "telegram_bot.configurado", return_value=False
        ), patch(
            "app.list_push_subscriptions",
            return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
        ), patch("push_client.enviar", return_value=True) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 9, 23, 12, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            app.verificar_e_notificar()
            titulos = [c.args[1] for c in mock_enviar.call_args_list]
            corpos = [c.args[2] for c in mock_enviar.call_args_list]
        self.assertIn("Cartao estourou o limite", titulos)
        idx = titulos.index("Cartao estourou o limite")
        self.assertIn("passou R$ 200.00 do limite", corpos[idx])
        # segunda chamada, mesmo estado - nao reenvia (ja_notificado_alguma_vez)
        with patch("push_client.configurado", return_value=True), patch(
            "telegram_bot.configurado", return_value=False
        ), patch(
            "app.list_push_subscriptions",
            return_value=[{"endpoint": "https://x", "subscription_json": json.dumps({"endpoint": "https://x", "keys": {}})}],
        ), patch("push_client.enviar", return_value=True) as mock_enviar2, patch("app.datetime") as mock_dt2:
            mock_dt2.now.return_value = datetime(2026, 9, 23, 12, 5)
            mock_dt2.fromisoformat = datetime.fromisoformat
            mock_dt2.combine = datetime.combine
            app.verificar_e_notificar()
            titulos2 = [c.args[1] for c in mock_enviar2.call_args_list]
        self.assertNotIn("Cartao estourou o limite", titulos2)


if __name__ == "__main__":
    unittest.main()
