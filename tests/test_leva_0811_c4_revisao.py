"""Leva 08/11, frente C rodada 4: o que os revisores acharam ponta a ponta. Apelido nunca sobrescrito pelo
caminho automatico, endereco com numero no nome da rua, "Casa do Construtor" nao e casa de pessoa, tarefa
sem dia que volta com dia leva tudo, "ai eu guardo" pelo lugar antigo, mes de Brasilia nas somas,
db.data_iso, 401 so do anthropic, travar pelo _editar, abertos sem arquivadas e passos depois do commit
protegidos. Banco temporario, IA/Maps dublados, nomes e enderecos inventados."""
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime
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
from assistente.gatilhos import p2_perguntas  # noqa: E402
from ia import core, historico  # noqa: E402

PIN = "135790"


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


def _utc_de_local(d: date, hhmm: str) -> str:
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
        for alvo, valor in (("maps_client.configurado", False), ("app._clima_na_hora", None)):
            p = patch(alvo, return_value=valor)
            p.start()
            self.addCleanup(p.stop)
        p = patch("onde_estou.garantir_coordenada", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def apelido(self, nome, endereco):
        conn = db.get_db()
        try:
            vida_assistente.salvar_apelido(conn, nome, endereco)
            conn.commit()
        finally:
            conn.close()

    def apelidos(self):
        conn = db.get_db()
        try:
            return vida_assistente.apelidos(conn)
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
        self.resposta = res.get_json()
        return resultados


# ------------------------------------------------------------------ 1: apelido nunca sobrescrito


class ApelidoNaoSobrescreveTestCase(_Base):
    def test_apelido_existente_com_outro_endereco_vira_conflito(self):
        self.apelido("obra", "Rua Verdadeira da Obra, 1")
        (r,) = self.chat([("registrar_tarefa", {"titulo": "Reuniao na obra com o engenheiro", "quando": "amanha",
                                                "hora": "08:00", "lugar": "Rua Errada dos Testes, 300"})])
        self.assertTrue(r.get("ok"), r)
        self.assertNotIn("lugar_salvo", r)
        self.assertEqual(r["lugar_conflito"]["apelido"], "obra")
        self.assertEqual(r["lugar_conflito"]["salvo"], "Rua Verdadeira da Obra, 1")
        self.assertEqual(self.apelidos()["obra"], "Rua Verdadeira da Obra, 1")

    def test_titulo_com_dois_lugares_nao_salva_nada(self):
        self.apelido("obra", "Rua Verdadeira da Obra, 1")
        self.apelido("aeroclube", "Rodovia do Aeroclube, 3000")
        r1, r2 = self.chat([
            ("registrar_tarefa", {"titulo": "Deixar o carro na oficina e ir pra obra", "quando": "amanha",
                                  "hora": "08:00", "lugar": "Rua da Oficina, 300"}),
            ("registrar_tarefa", {"titulo": "Buscar a Fulana no aeroclube", "quando": "amanha", "hora": "17:00",
                                  "lugar": "Rua da Casa Dela, 5"}),
        ])
        self.assertNotIn("lugar_salvo", r1)
        self.assertIn("lugar_conflito", r2)
        self.assertEqual(self.apelidos(), {"obra": "Rua Verdadeira da Obra, 1",
                                           "aeroclube": "Rodovia do Aeroclube, 3000"})

    def test_palavra_generica_nao_vira_apelido(self):
        rs = self.chat([
            ("registrar_tarefa", {"titulo": "Pagar boleto no banco", "quando": "amanha", "lugar": "Rua dos Testes, 10"}),
            ("registrar_tarefa", {"titulo": "Encontrar o Fulano no bar", "quando": "amanha", "lugar": "Rua X, 10"}),
            ("registrar_tarefa", {"titulo": "Ir na farmacia", "quando": "amanha", "lugar": "Rua Y, 20"}),
        ])
        self.assertFalse([r for r in rs if "lugar_salvo" in r])
        self.assertEqual(self.apelidos(), {})

    def test_mesmo_endereco_nao_conflita(self):
        self.apelido("obra", "Rua Verdadeira da Obra, 1")
        (r,) = self.chat([("registrar_tarefa", {"titulo": "Ir pra obra", "quando": "amanha",
                                                "lugar": "rua verdadeira da obra 1"})])
        self.assertTrue(r["lugar_salvo"]["ja_estava_salvo"])


# ------------------------------------------------------------------ 2/11: registrar_tarefa


class RegistrarTarefaTestCase(_Base):
    def test_sem_dia_que_volta_com_dia_leva_estilo_lugar_e_parada(self):
        self.sql("INSERT INTO tasks (title) VALUES ('Jantar com a Ciclana')")
        hoje = date.today().isoformat()
        (r,) = self.chat([("registrar_tarefa", {
            "titulo": "Jantar com a Ciclana", "quando": "hoje", "quando_data": hoje, "hora": "20:00",
            "estilo": "date", "lugar": "Restaurante Exemplo", "sai_na_hora": True, "parada": "floricultura"})])
        self.assertTrue(r.get("ja_existia_sem_dia"), r)
        linha = self.sql("SELECT due_date, hora, local, estilo, parada, sai_na_hora FROM tasks")
        self.assertEqual(len(linha), 1)
        self.assertEqual(tuple(linha[0]), (hoje, "20:00", "Restaurante Exemplo", "date", "floricultura", 1))
        self.assertIn("sair_de_casa", r.get("plano", {}))  # passou pelo _plano_do_estilo

    def test_passo_depois_do_commit_que_estoura_nao_vira_erro(self):
        with patch("app._saida_pro_compromisso", side_effect=RuntimeError("maps caiu")):
            (r,) = self.chat([("registrar_tarefa", {"titulo": "Date de teste", "quando": "amanha", "hora": "20:00",
                                                    "estilo": "date", "lugar": "Bar de teste"})])
        self.assertTrue(r.get("ok"), r)
        self.assertIn("plano de saida", r.get("observacao", ""))
        self.assertIn("Nao registre de novo", r["observacao"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM tasks WHERE title = 'Date de teste'")[0][0], 1)


# ------------------------------------------------------------------ 3/4/5: endereco e casa de pessoa


class EnderecoECasaTestCase(_Base):
    def test_rua_com_numero_no_nome(self):
        for sim in ("Rua 1 de Maio, 100", "Av. 1 de Maio, 1200", "Rua 25 de Julho, 80", "Rodovia SC-401, 3000",
                    "Rua XV de Novembro 500", "Rua dos Testes, 155, apto 3", "casa da Fulana, Rua 1 de Maio 100"):
            self.assertTrue(app._parece_endereco(sim), sim)
        for nao in ("Academia, 2", "Casa da mae, 302", "Mercado, 10 min", "Av. Exemplo", "Rua 1 de Maio",
                    "Aeroclube, 2 voltas", "Centro, 88010", "Shopping Exemplo, 2 andar"):
            self.assertFalse(app._parece_endereco(nao), nao)

    def test_casa_de_alguem_com_rua_depois_salva_e_nao_pergunta(self):
        (r,) = self.chat([("registrar_tarefa", {"titulo": "Jantar na casa da Fulana", "quando": "hoje", "hora": "20:00",
                                                "lugar": "casa da Fulana, Rua 1 de Maio 100"})])
        self.assertNotIn("lugar_sem_endereco", r)
        self.assertEqual(r["lugar_salvo"]["apelido"], "casa da fulana")
        self.assertEqual(self.apelidos()["casa da fulana"], "Rua 1 de Maio 100")

    def test_ai_eu_guardo_usa_o_lugar_antigo(self):
        a, = self.chat([("registrar_tarefa", {"titulo": "Date com a Fulana", "quando": "hoje", "hora": "20:00",
                                              "estilo": "date", "lugar": "casa da Fulana"})])
        self.assertIn("lugar_sem_endereco", a)
        b, = self.chat([("ajustar_tarefa", {"titulo": "Date com a Fulana", "lugar": "Rua dos Testes, 155"})])
        self.assertEqual(b["lugar_salvo"]["apelido"], "casa da fulana")
        self.assertEqual(self.apelidos(), {"casa da fulana": "Rua dos Testes, 155"})

    def test_casa_de_pessoa(self):
        for sim in ("casa da Fulana", "casa da mae", "na casa do guri", "casa dos meus pais", "casa da minha mãe",
                    "Casa da Vó", "casa da fulana", "casa do beltrano", "casa dos Silva"):
            self.assertTrue(db.casa_de_pessoa(sim), sim)
        for nao in ("Casa do Construtor", "Casa da Picanha", "Casa das Baterias", "casa do construtor",
                    "casa da Fulana, Rua X 10", "casa", "Shopping de teste", "casa das baterias",
                    "casa de shows", "casa de praia"):
            self.assertFalse(db.casa_de_pessoa(nao), nao)

    def test_loja_casa_do_construtor_nao_pede_endereco(self):
        (r,) = self.chat([("registrar_tarefa", {"titulo": "Alugar betoneira na Casa do Construtor", "quando": "hoje",
                                                "hora": "10:00", "lugar": "Casa do Construtor"})])
        self.assertNotIn("lugar_sem_endereco", r)


# ------------------------------------------------------------------ 6: mes de Brasilia


class MesDeBrasiliaTestCase(_Base):
    def test_gasto_e_renda_do_fim_do_mes_a_noite(self):
        noite = _utc_de_local(date(2026, 11, 30), "22:00")  # 01:00 UTC do dia 1/12
        self.assertTrue(noite.startswith("2026-12-01"))
        self.sql("INSERT INTO expenses (amount, category, description, tipo, created_at) "
                 "VALUES (40, 'mercado', 'Mercado de teste', 'real', ?)", (noite,))
        self.sql("INSERT INTO incomes (amount, category, description, created_at) VALUES (100, 'outros', 'x', ?)",
                 (noite,))
        conn = db.get_db()
        try:
            self.assertEqual(db.total_gastos_mes(conn, "2026-11"), 40)
            self.assertEqual(db.total_gastos_mes(conn, "2026-12"), 0)
            self.assertEqual(db.gasto_mes_por_categoria(conn, "mercado", "2026-11"), 40)
            self.assertEqual(db.total_incomes_mes(conn, "2026-11"), 100)
        finally:
            conn.close()


# ------------------------------------------------------------------ 7: db.data_iso no leitor do p2


class DataIsoTestCase(_Base):
    def test_data_iso_e_alias(self):
        self.assertIs(app._data_iso, db.data_iso)
        self.assertEqual(db.data_iso("2026-11-15T09:00"), "2026-11-15")
        self.assertIsNone(db.data_iso(""))
        with self.assertRaises(ValueError):
            db.data_iso("dia quinze")

    def test_pergunta_do_lembrete_antigo_com_hora(self):
        self.sql("INSERT INTO lembretes (titulo, data) VALUES ('Renovar documento de teste', '2026-11-01T09:00')")
        self.sql("INSERT INTO lembretes (titulo, data) VALUES ('Torto', '')")
        conn = db.get_db()
        try:
            with patch.object(p2_perguntas, "_enfileirar") as enfileirar:
                p2_perguntas._perguntar_lembretes(conn, date(2026, 11, 8))
        finally:
            conn.close()
        self.assertEqual(enfileirar.call_count, 1)
        self.assertIn("2026-11-01", enfileirar.call_args.kwargs["corpo"])


# ------------------------------------------------------------------ 8: 401 de outro provedor


class RecusaSoDoAnthropicTestCase(_Base):
    def setUp(self):
        super().setUp()
        core.limpar_chave_recusada()
        self.addCleanup(core.limpar_chave_recusada)
        self.client.post("/api/push/inscrever",
                         json={"endpoint": "https://exemplo.com/push/c4", "keys": {"p256dh": "x", "auth": "y"}})

    def _verificar(self):
        with patch("app._avisar_chave_recusada") as avisar, patch("push_client.configurado", return_value=True), \
                patch("push_client.enviar", return_value=True):
            self.client.post("/api/notificacoes/verificar-agora")
        return avisar

    def test_401_do_openai_nao_avisa_ia_fora(self):
        core.marcar_chave_recusada("openai")
        self.assertFalse(self._verificar().called)

    def test_401_do_anthropic_avisa(self):
        core.marcar_chave_recusada("anthropic")
        self.assertTrue(self._verificar().called)


# ------------------------------------------------------------------ 9: travar com hora e sem dia


class TravarTestCase(_Base):
    def _travar(self, hora, agora):
        self.sql("INSERT INTO tasks (title, hora) VALUES ('Tarefa travada de teste', ?)", (hora,))
        with patch("app._agora_brasilia", return_value=agora):
            (r,) = self.chat([("travar_tarefa", {"titulo": "Tarefa travada de teste"})])
        return r

    def test_hora_que_ainda_vem_fica_hoje_com_desfazer(self):
        r = self._travar("18:00", datetime(2026, 11, 8, 15, 0))
        self.assertEqual(r["dia_gravado"], "2026-11-08")
        self.assertNotIn("observacao", r)
        self.assertEqual(self.sql("SELECT due_date, inegociavel FROM tasks")[0][:], ("2026-11-08", 1))
        self.assertTrue([c for c in self.resposta.get("cards", []) if c.get("type") == "edicao"], self.resposta)

    def test_hora_que_ja_passou_vai_pra_amanha_com_observacao(self):
        r = self._travar("09:00", datetime(2026, 11, 8, 15, 0))
        self.assertEqual(r["dia_gravado"], "2026-11-09")
        self.assertIn("amanha", r["observacao"])


# ------------------------------------------------------------------ 10: abertos no banco


def _conn_historico():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, due_date TEXT, completed_at TEXT, recorrencia TEXT,"
        " arquivada_em TEXT);"
        "CREATE TABLE esperas (id INTEGER PRIMARY KEY, quem TEXT, sobre TEXT, resolvido_em TEXT);")
    return conn


class AbertosNoBancoTestCase(unittest.TestCase):
    def test_arquivada_nao_e_aberta(self):
        conn = _conn_historico()
        self.addCleanup(conn.close)
        conn.execute("INSERT INTO tasks (title) VALUES ('Aberta de teste')")
        conn.execute("INSERT INTO tasks (title, arquivada_em) VALUES ('Arquivada de teste', '2026-11-01')")
        texto = historico._abertos_no_banco(conn)
        self.assertIn("Aberta de teste", texto)
        self.assertNotIn("Arquivada de teste", texto)
        self.assertIn("pendencia fora daqui ja foi resolvida", texto)

    def test_lista_cortada_nao_afirma_resolvido(self):
        conn = _conn_historico()
        self.addCleanup(conn.close)
        conn.executemany("INSERT INTO tasks (title) VALUES (?)", [(f"Tarefa {i}",) for i in range(45)])
        texto = historico._abertos_no_banco(conn)
        self.assertNotIn("ja foi resolvida", texto)
        self.assertIn("CORTADA", texto)
        self.assertEqual(texto.split("tarefas: ")[1].count(";") + 1, historico.LIMITE_ABERTAS)

    def test_banco_sem_a_coluna_ainda_funciona(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, due_date TEXT, completed_at TEXT, "
                     "recorrencia TEXT)")
        conn.execute("INSERT INTO tasks (title) VALUES ('Aberta antiga')")
        self.assertIn("Aberta antiga", historico._abertos_no_banco(conn))


if __name__ == "__main__":
    unittest.main()
