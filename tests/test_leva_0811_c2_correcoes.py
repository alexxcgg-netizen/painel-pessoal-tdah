"""Leva 08/11, frente C rodada 2: bugs que o cacador achou. Data crua de lembrete/meta, "feito" que
concluia o modelo da recorrente, completed_at/criado_em/created_at em UTC lidos no dia de Brasilia,
texto de push, data normalizada + aviso de passado, habito idempotente, concluir pelo chat com os
efeitos do complete_task, frases locais com "tu". Banco temporario, IA dublada, nomes inventados."""
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
import chat_consultas  # noqa: E402
import gastos  # noqa: E402
import voz_premium  # noqa: E402
from assistente import regras  # noqa: E402

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
        return resultados


# ------------------------------------------------------------------ 1: data crua de lembrete/meta


class DataCruaTestCase(_Base):
    def test_lembrete_com_hora_grava_so_a_data(self):
        (r,) = self.chat([("registrar_lembrete", {"titulo": "Renovar documento de teste", "data": "2026-11-15T09:00"})])
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self.sql("SELECT data FROM lembretes")[0][0], "2026-11-15")

    def test_lembrete_vazio_ou_invalido_volta_erro_e_nao_grava(self):
        r_vazio, r_lixo = self.chat([
            ("registrar_lembrete", {"titulo": "Sem data", "data": ""}),
            ("registrar_lembrete", {"titulo": "Data torta", "data": "dia quinze"}),
        ])
        self.assertIn("erro", r_vazio)
        self.assertIn("erro", r_lixo)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lembretes")[0][0], 0)

    def test_meta_prazo_normalizado(self):
        r_vazio, r_hora, r_lixo = self.chat([
            ("registrar_meta", {"titulo": "Meta sem prazo", "valor": 100, "prazo": ""}),
            ("registrar_meta", {"titulo": "Meta com hora", "valor": 100, "prazo": "2026-12-01T10:00"}),
            ("registrar_meta", {"titulo": "Meta torta", "valor": 100, "prazo": "fim do ano"}),
        ])
        self.assertTrue(r_vazio.get("ok") and r_hora.get("ok"))
        self.assertIn("erro", r_lixo)
        prazos = dict(self.sql("SELECT titulo, prazo FROM goals"))
        self.assertEqual(prazos, {"Meta sem prazo": None, "Meta com hora": "2026-12-01"})

    def test_get_lembretes_nao_cai_com_linha_velha_torta(self):
        self.sql("INSERT INTO lembretes (titulo, data) VALUES ('Velho com hora', '2026-11-15T09:00')")
        self.sql("INSERT INTO lembretes (titulo, data) VALUES ('Velho vazio', '')")
        res = self.client.get("/api/lembretes")
        self.assertEqual(res.status_code, 200)
        por_titulo = {i["titulo"]: i for i in res.get_json()}
        self.assertIsNotNone(por_titulo["Velho com hora"]["proxima_ocorrencia"])
        self.assertIsNone(por_titulo["Velho vazio"]["proxima_ocorrencia"])

    def test_rota_de_lembrete_grava_isoformat(self):
        res = self.client.post("/api/lembretes", json={"titulo": "Pela rota", "data": "20261115"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.sql("SELECT data FROM lembretes")[0][0], "2026-11-15")
        self.assertEqual(self.client.post("/api/lembretes", json={"titulo": "x", "data": "amanha"}).status_code, 400)


# ------------------------------------------------------------------ 2: feito nao conclui o modelo


class MarcarFeitoTestCase(_Base):
    def test_conclui_a_instancia_de_hoje_e_nao_o_modelo(self):
        hoje = date(2026, 11, 8)
        conn = db.get_db()
        try:
            modelo = conn.execute(
                "INSERT INTO tasks (title, recorrencia, hora) VALUES ('Tomar remedio de teste', 'diaria', '08:00')"
            ).lastrowid
            ontem = conn.execute(
                "INSERT INTO tasks (title, due_date, recorrente_origem_id) VALUES ('Tomar remedio de teste', ?, ?)",
                ((hoje - timedelta(days=1)).isoformat(), modelo),
            ).lastrowid
            de_hoje = conn.execute(
                "INSERT INTO tasks (title, due_date, recorrente_origem_id) VALUES ('Tomar remedio de teste', ?, ?)",
                (hoje.isoformat(), modelo),
            ).lastrowid
            conn.commit()
            r = db.marcar_ou_criar_feito(conn, "tomar remedio", hoje=hoje)
            self.assertEqual(r["task_id"], de_hoje)
            feitas = {row["id"] for row in conn.execute("SELECT id FROM tasks WHERE completed_at IS NOT NULL")}
            self.assertEqual(feitas, {de_hoje})
            # de novo: agora vai a atrasada (a mais recente), o modelo nunca
            r2 = db.marcar_ou_criar_feito(conn, "tomar remedio", hoje=hoje)
            self.assertEqual(r2["task_id"], ontem)
            self.assertIsNone(conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (modelo,)).fetchone()[0])
        finally:
            conn.close()


# ------------------------------------------------------------------ 3/4/9: UTC lido no dia de Brasilia


class DiaDeBrasiliaTestCase(_Base):
    def test_helpers(self):
        self.assertEqual(db.dia_local("2026-11-09 00:30:00"), "2026-11-08")
        self.assertEqual(db.dia_local("2026-11-08T14:00:00"), "2026-11-08")
        self.assertEqual(db.dia_local("2026-11-08"), "2026-11-08")  # so data fica como esta
        self.assertIsNone(db.dia_local(""))
        self.assertEqual(db.datahora_local("2026-11-09 00:30:00"), datetime(2026, 11, 8, 21, 30))
        conn = db.get_db()
        try:
            sql = db.dia_local_sql("x")
            self.assertEqual(conn.execute(f"SELECT {sql} FROM (SELECT '2026-11-09 00:30:00' AS x)").fetchone()[0],
                             "2026-11-08")
            self.assertEqual(conn.execute(f"SELECT {sql} FROM (SELECT '2026-11-08' AS x)").fetchone()[0],
                             "2026-11-08")
        finally:
            conn.close()

    def test_consultar_tarefas_e_voz_contam_a_feita_as_22h(self):
        hoje = date(2026, 11, 3)
        conn = db.get_db()
        try:
            conn.execute("INSERT INTO tasks (title, completed_at) VALUES ('Feita de noite sem dia', ?)",
                         (_utc_de_local(hoje, "22:30"),))
            conn.commit()
            res = chat_consultas.consultar_tarefas(conn, {"status": "concluidas"}, hoje=hoje)
            self.assertEqual(res["total"], 1)
            self.assertEqual(res["tarefas"][0]["concluida_em"], "2026-11-03 22:30")
            amanha = chat_consultas.consultar_tarefas(
                conn, {"status": "concluidas", "de": "2026-11-04", "ate": "2026-11-04"}, hoje=hoje)
            self.assertEqual(amanha["total"], 0)
            self.assertIn("Fechou 1 de 1 hoje.", voz_premium.frase_curta_noite(conn, hoje))
        finally:
            conn.close()

    def test_gasto_das_21h30_conta_hoje(self):
        hoje = date(2026, 11, 3)
        noite = _utc_de_local(hoje, "21:30")  # 00:30 UTC do dia 4
        self.assertTrue(noite.startswith("2026-11-04"))
        historico = gastos.historico_diario([{"amount": 50.0, "created_at": noite}], 7, hoje)
        self.assertEqual(historico[-1], {"data": "2026-11-03", "total": 50.0})
        # na semana que termina no dia 3 (o gasto e do dia 3 a noite, nao do dia 4)
        semana = gastos.resumo_semanal([{"amount": 50.0, "category": "mercado", "created_at": noite}], hoje)
        self.assertEqual(semana["total_semana"], 50.0)
        conn = db.get_db()
        try:
            conn.execute("INSERT INTO expenses (amount, category, description, tipo, created_at) "
                         "VALUES (50, 'mercado', 'Mercado de teste', 'real', ?)", (noite,))
            conn.commit()
            self.assertEqual(regras.total_gasto_periodo(conn, "mercado", hoje, hoje), 50.0)
            self.assertEqual(regras.total_gasto_periodo(conn, "mercado", hoje + timedelta(days=1),
                                                        hoje + timedelta(days=1)), 0.0)
        finally:
            conn.close()

    def test_responder_anotado_ontem_as_22h_conta_1_dia(self):
        ontem = date.today() - timedelta(days=1)
        self.sql("INSERT INTO responder (quem, sobre, criado_em) VALUES ('Fulano de Teste', 'o orcamento', ?)",
                 (_utc_de_local(ontem, "22:30"),))
        res = self.client.get("/api/responder")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()[0]["dias"], 1)


# ------------------------------------------------------------------ 5: texto do push de conta


class TextoContaTestCase(unittest.TestCase):
    def test_singular_plural_e_acento(self):
        q = app._quando_conta_construtora
        self.assertEqual(q(-1, passado="venceu há"), "venceu há 1 dia")
        self.assertEqual(q(-3, passado="venceu há"), "venceu há 3 dias")
        self.assertEqual(q(0), "vence hoje")
        self.assertEqual(q(1), "vence amanhã")
        self.assertEqual(q(2), "vence em 2 dias")
        self.assertNotIn("(s)", q(-1))


# ------------------------------------------------------------------ 6/8: ajustar_tarefa


class AjustarTarefaTestCase(_Base):
    def _tarefa(self, titulo, due_date):
        conn = db.get_db()
        try:
            tid = conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", (titulo, due_date)).lastrowid
            conn.commit()
            return tid
        finally:
            conn.close()

    def test_data_compacta_vira_isoformat(self):
        self._tarefa("Levar o carro de teste", date.today().isoformat())
        (r,) = self.chat([("ajustar_tarefa", {"titulo": "Levar o carro de teste", "quando_data": "20991115"})])
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self.sql("SELECT due_date FROM tasks")[0][0], "2099-11-15")
        self.assertNotIn("observacao", r)

    def test_data_no_passado_aceita_com_observacao(self):
        self._tarefa("Tarefa pro passado", date.today().isoformat())
        ontem = (date.today() - timedelta(days=2)).isoformat()
        (r,) = self.chat([("ajustar_tarefa", {"titulo": "Tarefa pro passado", "quando_data": ontem})])
        self.assertTrue(r.get("ok"), r)
        self.assertIn("passado", r.get("observacao", ""))
        self.assertEqual(self.sql("SELECT due_date FROM tasks")[0][0], ontem)

    def test_mover_pro_passado_avisa(self):
        hoje = date.today().isoformat()
        self._tarefa("Mover de teste", hoje)
        antes = (date.today() - timedelta(days=1)).isoformat()
        (r,) = self.chat([("mover_tarefas", {"de_data": hoje, "para_data": antes})])
        self.assertTrue(r.get("ok"), r)
        self.assertIn("observacao", r)

    def test_concluir_pelo_chat_tem_os_efeitos_do_complete_task(self):
        tid = self._tarefa("Concluir com efeitos", date.today().isoformat())
        with patch("db.fechar_interacao_aprendizado", return_value=True) as fechar, \
                patch("aviso_cara.tarefa_concluida") as credito:
            (r,) = self.chat([("ajustar_tarefa", {"titulo": "Concluir com efeitos", "status": "concluir"})])
        self.assertTrue(r.get("ok"), r)
        fechar.assert_called_once()
        self.assertEqual(fechar.call_args[0][1:], ("tarefa_parada", tid))
        credito.assert_called_once()
        dif = self.sql("SELECT ABS(julianday(completed_at) - julianday('now')) * 86400 FROM tasks")[0][0]
        self.assertLess(dif, 120)  # continua UTC


# ------------------------------------------------------------------ 7: habito idempotente


class HabitoTestCase(_Base):
    def test_marcar_duas_vezes_continua_marcado_e_desmarcar_so_explicito(self):
        conn = db.get_db()
        db.create_habito(conn, "Ler de teste", None, "diario", None, None, None)
        conn.close()
        r1, r2 = self.chat([("marcar_habito", {"nome": "Ler de teste"}), ("marcar_habito", {"nome": "Ler de teste"})])
        self.assertTrue(r1["feito"] and r2["feito"])
        self.assertNotIn("obs", r1)
        self.assertEqual(r2.get("obs"), "ja estava marcado hoje")  # sem _efeito: o Desfazer nao desmarca
        self.assertEqual(self.sql("SELECT COUNT(*) FROM habito_marcacoes")[0][0], 1)
        (r3,) = self.chat([("marcar_habito", {"nome": "Ler de teste", "desmarcar": True})])
        self.assertFalse(r3["feito"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM habito_marcacoes")[0][0], 0)


# ------------------------------------------------------------------ 10: frases locais com "tu"


class FraseLocalTestCase(unittest.TestCase):
    def test_sem_voce(self):
        casos = [
            {"tool": "consultar_projeto", "resultado": {"encontrados": 0}, "entrada": {}},
            {"tool": "consultar_treinos", "resultado": {"sessoes": [1], "dias": 7}},
            {"tool": "consultar_habitos", "resultado": {"encontrados": 1}},
            {"tool": "consultar_habitos", "resultado": {"encontrados": 0}},
            {"tool": "consultar_saude_dia", "resultado": {}},
        ]
        frases = [app._frase_local(c) for c in casos]
        for f in frases:
            self.assertNotRegex(f.lower(), r"\bvoc[eê]\b|\bseus?\b|\bsuas?\b", f)
        self.assertEqual(frases[0], "Tu ainda não tem projeto nem viagem cadastrados.")
        self.assertEqual(frases[2], "Teus hábitos.")


if __name__ == "__main__":
    unittest.main()
