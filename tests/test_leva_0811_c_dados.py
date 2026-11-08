"""Leva 08/11 (docs/briefings/2026-11-08-leva-conversa-inteira.md), frente C - dados e lugares:
C1 completed_at em UTC e os leitores descontando 3 h, C2 ajustar_tarefa registra adiamento, C3 tarefa
repetida sem dia ganha o dia, C4 endereco vira apelido + vocabulario, C6 voo/treino parado, C8 voz.
Banco temporario, IA dublada, nada de rede; nomes e enderecos inventados."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import vida_assistente  # noqa: E402
from assistente import briefing  # noqa: E402

PIN = "135790"


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


def _utc_de_local(d: date, hhmm: str) -> str:
    """Hora local de Brasilia -> texto UTC no formato do datetime('now')."""
    h, m = (int(x) for x in hhmm.split(":"))
    local = datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo("America/Sao_Paulo"))
    return local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


class _Base(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        sem_maps = patch("maps_client.configurado", return_value=False)
        sem_maps.start()
        self.addCleanup(sem_maps.stop)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def chat(self, chamadas):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "teste"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def tarefa(self, titulo, due_date=None, hora=None):
        conn = db.get_db()
        cur = conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", (titulo, due_date, hora))
        conn.commit()
        conn.close()
        return cur.lastrowid


# ------------------------------------------------------------------ C1


class CompletedAtUtcTestCase(_Base):
    def test_concluir_pelo_chat_grava_utc_igual_ao_sqlite(self):
        self.tarefa("Pagar o boleto de teste", date.today().isoformat())
        self.chat([("ajustar_tarefa", {"titulo": "Pagar o boleto de teste", "status": "concluir"})])
        dif = self.sql("SELECT ABS(julianday(completed_at) - julianday('now')) * 86400 FROM tasks")[0][0]
        self.assertLess(dif, 120)  # UTC (datetime('now')), nao a hora local (3 h de diferenca)

    def test_tarefa_feita_as_22h_conta_no_dia_dela(self):
        hoje = date(2026, 11, 3)
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                     ("Feita de noite", hoje.isoformat(), _utc_de_local(hoje, "22:30")))  # 01:30 UTC do dia 4
        conn.execute("INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                     ("Feita ontem de noite", (hoje - timedelta(days=1)).isoformat(),
                      _utc_de_local(hoje - timedelta(days=1), "23:50")))
        conn.commit()
        try:
            self.assertEqual(briefing.montar_noite(conn, hoje)["concluidas"], 1)
            fatos = app._fatos_periodo(conn, hoje, hoje)
            self.assertEqual(fatos["tarefas_feitas"], 1)
        finally:
            conn.close()

    def test_rotas_de_resumo_e_fechamento_usam_o_dia_de_brasilia(self):
        hoje = date.today()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                     ("Feita de noite hoje", hoje.isoformat(), _utc_de_local(hoje, "23:10")))
        conn.commit()
        conn.close()
        res = self.client.get("/api/fechamento-do-dia")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Feita de noite hoje", str(res.get_json()))


# ------------------------------------------------------------------ C2


class AdiamentoPeloChatTestCase(_Base):
    def test_empurrar_pra_frente_registra_adiamento(self):
        hoje = date.today()
        self.tarefa("Levar o documento", hoje.isoformat(), "10:00")
        amanha = (hoje + timedelta(days=1)).isoformat()
        self.chat([("ajustar_tarefa", {"titulo": "Levar o documento", "quando_data": amanha})])
        linhas = self.sql("SELECT de, para FROM tarefas_adiadas")
        self.assertEqual([tuple(r) for r in linhas], [(hoje.isoformat(), amanha)])

    def test_trazer_pra_antes_nao_e_adiamento(self):
        hoje = date.today()
        self.tarefa("Levar o documento", (hoje + timedelta(days=3)).isoformat())
        self.chat([("ajustar_tarefa", {"titulo": "Levar o documento", "quando_data": hoje.isoformat()})])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tarefas_adiadas")[0][0], 0)

    def test_tarefa_sem_dia_ganhando_dia_nao_e_adiamento(self):
        self.tarefa("Levar o documento")
        amanha = (date.today() + timedelta(days=1)).isoformat()
        self.chat([("ajustar_tarefa", {"titulo": "Levar o documento", "quando_data": amanha})])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tarefas_adiadas")[0][0], 0)


# ------------------------------------------------------------------ C3


class TarefaRepetidaGanhaODiaTestCase(_Base):
    def test_mesma_tarefa_sem_dia_volta_e_hoje_grava_o_dia_sem_duplicar(self):
        tid = self.tarefa("Imprimir as contas de teste")
        _, res = self.chat([("registrar_tarefa", {"titulo": "Imprimir as contas de teste", "quando": "hoje",
                                                   "hora": "11:00"})])
        self.assertTrue(res[0].get("ja_existia_sem_dia"), res[0])
        linhas = self.sql("SELECT id, due_date, hora FROM tasks")
        self.assertEqual(len(linhas), 1)
        self.assertEqual(tuple(linhas[0]), (tid, date.today().isoformat(), "11:00"))

    def test_duplicata_no_mesmo_dia_continua_recusada(self):
        self.tarefa("Imprimir as contas de teste", date.today().isoformat(), "11:00")
        _, res = self.chat([("registrar_tarefa", {"titulo": "Imprimir as contas de teste", "quando": "hoje", "hora": "11:00"})])
        self.assertTrue(res[0].get("nao_criei"))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks")[0][0], 1)

    def test_travar_tarefa_com_hora_e_sem_dia_vira_de_hoje(self):
        self.tarefa("Imprimir as contas de teste", None, "11:00")
        _, res = self.chat([("travar_tarefa", {"titulo": "Imprimir as contas de teste"})])
        self.assertEqual(res[0].get("dia_gravado"), app._agora_brasilia().date().isoformat())
        linha = self.sql("SELECT due_date, inegociavel FROM tasks")[0]
        self.assertEqual(tuple(linha), (app._agora_brasilia().date().isoformat(), 1))

    def test_travar_sem_hora_nao_inventa_dia(self):
        self.tarefa("Organizar a gaveta de teste")
        self.chat([("travar_tarefa", {"titulo": "Organizar a gaveta de teste"})])
        self.assertIsNone(self.sql("SELECT due_date FROM tasks")[0][0])


# ------------------------------------------------------------------ C4


class EnderecoViraApelidoTestCase(_Base):
    def test_parece_endereco(self):
        for t in ("Rua dos Testes, 155", "av. Exemplo 900", "Travessa Imaginaria, n 12", "Avenida Ficticia 1500",
                  "rua dos testes 155 - fundos", "Alameda Inventada, nº 40", "Rodovia Teste, 3000"):
            self.assertTrue(app._parece_endereco(t), t)
        for t in ("casa da Fulana", "shopping", "rua sem numero", "mercado do bairro", "", None, "oficina 2"):
            self.assertFalse(app._parece_endereco(t), t)

    def test_nome_do_lugar(self):
        self.assertEqual(app._nome_do_lugar("Jantar na casa da Fulana às 20h", "Rua dos Testes, 155"),
                         "casa da fulana")
        # rodada 4: "trabalho" e categoria de uma palavra (o trabalho DELA) - nao vira apelido
        self.assertIsNone(app._nome_do_lugar("Buscar a Beltrana no trabalho e levar pra casa", "Rua Teste 10"))
        self.assertEqual(app._nome_do_lugar("Visita", "casa da Ciclana, Rua dos Testes 155"), "casa da ciclana")
        self.assertEqual(app._nome_do_lugar("Levar o carro na oficina do Beltrano amanhã", "Av. Exemplo 900"),
                         "oficina do beltrano")
        self.assertEqual(app._nome_do_lugar("Churrasco na casa da Fulana no centro", "Rua dos Testes 155"),
                         "casa da fulana")
        self.assertIsNone(app._nome_do_lugar("Ir até a farmácia", "Rua dos Testes 155"))  # categoria (rodada 4)
        self.assertEqual(app._nome_do_lugar("Ir até a farmácia do centro", "Rua dos Testes 155"),
                         "farmacia do centro")
        self.assertIsNone(app._nome_do_lugar("Reunião com o contador", "Rua dos Testes, 155"))
        self.assertIsNone(app._nome_do_lugar("Buscar a Fulana na casa dela", "Rua dos Testes, 155"))

    def test_registrar_tarefa_com_endereco_salva_o_apelido(self):
        _, res = self.chat([("registrar_tarefa", {"titulo": "Jantar na casa da Fulana", "quando": "hoje",
                                                   "hora": "20:00", "lugar": "Rua dos Testes, 155"})])
        self.assertEqual(res[0]["lugar_salvo"]["apelido"], "casa da fulana")
        conn = db.get_db()
        try:
            self.assertEqual(vida_assistente.apelidos(conn).get("casa da fulana"), "Rua dos Testes, 155")
            self.assertEqual(vida_assistente.resolver_lugar(conn, "casa da Fulana"), "Rua dos Testes, 155")
        finally:
            conn.close()
        self.assertEqual(self.sql("SELECT local FROM tasks")[0][0], "Rua dos Testes, 155")

    def test_lugar_sem_endereco_nao_salva_e_pede_pra_perguntar(self):
        _, res = self.chat([("registrar_tarefa", {"titulo": "Jantar na casa da Fulana", "quando": "hoje",
                                                   "hora": "20:00", "lugar": "casa da Fulana"})])
        self.assertIn("lugar_sem_endereco", res[0])
        self.assertNotIn("lugar_salvo", res[0])
        conn = db.get_db()
        try:
            self.assertEqual(vida_assistente.apelidos(conn), {})
        finally:
            conn.close()

    def test_casa_com_apelido_ja_salvo_nao_pergunta(self):
        conn = db.get_db()
        vida_assistente.salvar_apelido(conn, "casa da Fulana", "Rua dos Testes, 155")
        conn.commit()
        conn.close()
        _, res = self.chat([("registrar_tarefa", {"titulo": "Jantar na casa da Fulana", "quando": "hoje",
                                                   "hora": "20:00", "lugar": "casa da Fulana"})])
        self.assertNotIn("lugar_sem_endereco", res[0])

    def test_ajustar_tarefa_com_endereco_salva_o_apelido(self):
        self.tarefa("Levar o carro na oficina do Beltrano", date.today().isoformat(), "14:00")
        _, res = self.chat([("ajustar_tarefa", {"titulo": "Levar o carro na oficina do Beltrano",
                                                 "lugar": "Avenida Exemplo, 900"})])
        self.assertEqual(res[0]["lugar_salvo"]["apelido"], "oficina do beltrano")
        conn = db.get_db()
        try:
            self.assertEqual(vida_assistente.apelidos(conn)["oficina do beltrano"], "Avenida Exemplo, 900")
        finally:
            conn.close()

    def test_vocabulario_tem_lugar_das_tarefas_e_titulo_feito_recente(self):
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title, local, completed_at) VALUES (?, ?, datetime('now'))",
                     ("Consulta no Consultorio Inventado", "Clinica Ficticia Centro"))
        conn.execute("INSERT INTO tasks (title, completed_at, created_at) VALUES (?, datetime('now'), "
                     "datetime('now', '-40 days'))", ("Tarefa velha esquecida",))
        conn.commit()
        try:
            vocab = app._vocabulario_do_alex(conn)
        finally:
            conn.close()
        self.assertIn("Clinica Ficticia Centro", vocab)
        self.assertIn("Consulta no Consultorio Inventado", vocab)
        self.assertNotIn("Tarefa velha esquecida", vocab)


# ------------------------------------------------------------------ C6 e C8


class AtividadeParadaTestCase(_Base):
    def test_voo_de_mais_de_60_dias_e_parado(self):
        hoje = date(2026, 11, 8)
        conn = db.get_db()
        try:
            self.assertTrue(db.atividade_parada(conn, "voo", hoje))  # nunca voou
            conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                         ((hoje - timedelta(days=400)).isoformat(), "SXXX", 1.2))
            conn.commit()
            self.assertEqual(db.dias_desde_ultimo_voo(conn, hoje), 400)
            self.assertTrue(db.atividade_parada(conn, "voo", hoje))
            conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                         ((hoje - timedelta(days=10)).isoformat(), "SXXX", 1.0))
            conn.commit()
            self.assertFalse(db.atividade_parada(conn, "voo", hoje))
        finally:
            conn.close()

    def test_voo_futuro_e_sem_horas_nao_contam(self):
        hoje = date(2026, 11, 8)
        conn = db.get_db()
        try:
            conn.execute("INSERT INTO voos (data, destino) VALUES (?, ?)", ((hoje - timedelta(days=3)).isoformat(), "SX"))
            conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                         ((hoje + timedelta(days=3)).isoformat(), "SX", 1.0))
            conn.commit()
            self.assertIsNone(db.dias_desde_ultimo_voo(conn, hoje))
        finally:
            conn.close()

    def test_treino_parado(self):
        hoje = date(2026, 11, 8)
        conn = db.get_db()
        try:
            self.assertTrue(db.atividade_parada(conn, "treino", hoje))
            conn.execute("INSERT INTO treinos (data, grupo) VALUES (?, ?)", ((hoje - timedelta(days=70)).isoformat(), "A"))
            conn.commit()
            self.assertTrue(db.atividade_parada(conn, "treino", hoje))
            conn.execute("INSERT INTO treinos (data, grupo) VALUES (?, ?)", ((hoje - timedelta(days=2)).isoformat(), "B"))
            conn.commit()
            self.assertFalse(db.atividade_parada(conn, "treino", hoje))
        finally:
            conn.close()


class ModoVozTestCase(unittest.TestCase):
    def test_sem_numero_do_jeito_que_se_fala(self):
        self.assertNotIn("jeito que se fala", app.MODO_VOZ_INSTRUCAO)
        self.assertIn("sem lista", app.MODO_VOZ_INSTRUCAO)


if __name__ == "__main__":
    unittest.main()
