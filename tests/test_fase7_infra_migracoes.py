"""Fase 7, Etapa 0: migracoes por arquivo (migracoes/*.sql aplicadas pelo
db.init_db(), uma vez so, cada uma numa transacao). Banco e pasta de
migracoes sempre temporarios."""

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()


class MigracoesTestCase(unittest.TestCase):
    def setUp(self):
        p_db = patch.object(db, "DB_PATH", Path(_tmp_dir.name) / "painel.db")
        p_db.start()
        self.addCleanup(p_db.stop)
        db.garantir_banco_nao_producao()
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        p = patch.object(db, "MIGRACOES_DIR", Path(self.pasta.name))
        p.start()
        self.addCleanup(p.stop)

    def escrever(self, nome, sql):
        (Path(self.pasta.name) / nome).write_text(sql, encoding="utf-8")

    def consultar(self, sql, params=()):
        conn = db.get_db()
        try:
            return [tuple(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def tabelas(self):
        return {r[0] for r in self.consultar("SELECT name FROM sqlite_master WHERE type='table'")}

    def aplicadas(self):
        return [r[0] for r in self.consultar("SELECT nome FROM migracoes_aplicadas ORDER BY nome")]

    # ---- caminho feliz ----

    def test_pasta_vazia_cria_so_a_tabela_de_controle(self):
        db.init_db()
        self.assertIn("migracoes_aplicadas", self.tabelas())
        self.assertEqual(self.aplicadas(), [])
        colunas = [r[1] for r in self.consultar("PRAGMA table_info(migracoes_aplicadas)")]
        self.assertEqual(colunas, ["nome", "aplicada_em"])

    def test_pasta_inexistente_nao_quebra(self):
        with patch.object(db, "MIGRACOES_DIR", Path(self.pasta.name) / "nao-existe"):
            db.init_db()
        self.assertEqual(self.aplicadas(), [])

    def test_pasta_real_do_repo_existe_e_so_tem_sql_valido(self):
        pasta_real = Path(db.__file__).parent / "migracoes"
        self.assertTrue((pasta_real / "README.md").exists())
        for arq in pasta_real.glob("*.sql"):
            self.assertRegex(arq.name, r"^\d{12}_[a-z0-9]+_[a-z0-9_]+\.sql$")

    def test_aplica_em_ordem_alfabetica_uma_vez_so(self):
        self.escrever("202609240002_x1_b.sql", "INSERT INTO ordem (passo) VALUES ('b');")
        self.escrever("202609240001_x1_a.sql", "CREATE TABLE ordem (id INTEGER PRIMARY KEY, passo TEXT);\n"
                                                "INSERT INTO ordem (passo) VALUES ('a');")
        self.escrever("leia-me.txt", "nao e sql, ignorado")
        db.init_db()
        db.init_db()
        db.init_db()
        self.assertEqual(self.consultar("SELECT passo FROM ordem ORDER BY id"), [("a",), ("b",)])
        self.assertEqual(self.aplicadas(), ["202609240001_x1_a.sql", "202609240002_x1_b.sql"])
        (quando,) = self.consultar("SELECT aplicada_em FROM migracoes_aplicadas LIMIT 1")[0]
        self.assertRegex(quando, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_arquivo_novo_depois_roda_so_ele(self):
        self.escrever("202609240001_x1_a.sql", "CREATE TABLE contador (n INTEGER); INSERT INTO contador VALUES (1);")
        db.init_db()
        self.escrever("202609240002_x1_b.sql", "INSERT INTO contador VALUES (2);")
        db.init_db()
        self.assertEqual(self.consultar("SELECT n FROM contador ORDER BY n"), [(1,), (2,)])

    def test_sql_com_trigger_string_com_ponto_e_virgula_comentario_e_sem_ponto_final(self):
        self.escrever(
            "202609240001_x1_trigger.sql",
            """-- comentario no topo; com ponto e virgula
            /* bloco; de comentario */
            CREATE TABLE notas_x (id INTEGER PRIMARY KEY, texto TEXT, log TEXT);
            CREATE TRIGGER notas_x_log AFTER INSERT ON notas_x BEGIN
                UPDATE notas_x SET log = 'inserido; ok' WHERE id = NEW.id;
            END;
            INSERT INTO notas_x (texto) VALUES ('a;b'); INSERT INTO notas_x (texto) VALUES ('c')
            -- comentario no fim
            """,
        )
        db.init_db()
        self.assertEqual(
            self.consultar("SELECT texto, log FROM notas_x ORDER BY id"),
            [("a;b", "inserido; ok"), ("c", "inserido; ok")],
        )

    def test_alter_table_em_tabela_existente(self):
        self.escrever("202609240001_x1_coluna.sql", "ALTER TABLE tasks ADD COLUMN teste_fase7 TEXT NOT NULL DEFAULT 'x';")
        db.init_db()
        db.init_db()  # segunda vez nao tenta adicionar de novo (daria erro de coluna duplicada)
        colunas = [r[1] for r in self.consultar("PRAGMA table_info(tasks)")]
        self.assertIn("teste_fase7", colunas)

    def test_arquivo_vazio_ou_so_comentario_conta_como_aplicado(self):
        self.escrever("202609240001_x1_vazio.sql", "")
        self.escrever("202609240002_x1_comentario.sql", "-- nada ainda\n")
        db.init_db()
        self.assertEqual(len(self.aplicadas()), 2)

    def test_utf8_com_bom_e_acento(self):
        (Path(self.pasta.name) / "202609240001_x1_acento.sql").write_bytes(
            "\ufeffCREATE TABLE acento (t TEXT); INSERT INTO acento VALUES ('ação');".encode("utf-8")
        )
        db.init_db()
        self.assertEqual(self.consultar("SELECT t FROM acento"), [("ação",)])

    # ---- falha: nunca deixa banco pela metade ----

    def test_falha_desfaz_o_arquivo_inteiro_e_erro_cita_o_nome(self):
        self.escrever("202609240001_x1_ok.sql", "CREATE TABLE antes_ok (id INTEGER);")
        self.escrever(
            "202609240002_x1_quebrada.sql",
            "CREATE TABLE metade (id INTEGER);\nINSERT INTO metade VALUES (1);\nINSERT INTO tabela_que_nao_existe VALUES (1);",
        )
        self.escrever("202609240003_x1_depois.sql", "CREATE TABLE depois (id INTEGER);")
        with self.assertRaises(db.ErroMigracao) as ctx:
            db.init_db()
        self.assertIn("202609240002_x1_quebrada.sql", str(ctx.exception))
        self.assertIsInstance(ctx.exception, RuntimeError)
        tabelas = self.tabelas()
        self.assertIn("antes_ok", tabelas)
        self.assertNotIn("metade", tabelas)
        self.assertNotIn("depois", tabelas)  # para no primeiro erro
        self.assertEqual(self.aplicadas(), ["202609240001_x1_ok.sql"])
        # banco nao ficou travado nem em transacao aberta
        conn = db.get_db()
        conn.execute("CREATE TABLE ainda_escreve (id INTEGER)")
        conn.commit()
        conn.close()

    def test_corrigir_com_arquivo_novo_depois_da_falha(self):
        self.escrever("202609240001_x1_quebrada.sql", "CREATE TABLE q (id INTEGER); SELEC 1;")
        with self.assertRaises(db.ErroMigracao):
            db.init_db()
        (Path(self.pasta.name) / "202609240001_x1_quebrada.sql").unlink()
        self.escrever("202609240002_x1_corrigida.sql", "CREATE TABLE q (id INTEGER);")
        db.init_db()
        self.assertIn("q", self.tabelas())

    def test_controle_de_transacao_no_arquivo_e_recusado_antes_de_rodar(self):
        for i, comando in enumerate(("BEGIN", "COMMIT", "END", "ROLLBACK", "begin transaction", "SAVEPOINT x")):
            with self.subTest(comando=comando):
                nome = f"20260924000{i}_x1_tx.sql"
                self.escrever(nome, f"CREATE TABLE tx_{i} (id INTEGER);\n{comando};\nCREATE TABLE tx2_{i} (id INTEGER);")
                with self.assertRaises(db.ErroMigracao) as ctx:
                    db.init_db()
                self.assertIn(nome, str(ctx.exception))
                self.assertNotIn(f"tx_{i}", self.tabelas())
                (Path(self.pasta.name) / nome).unlink()

    def test_duas_threads_aplicam_uma_vez_so(self):
        db.init_db()
        self.escrever("202609240001_x1_conta.sql", "CREATE TABLE IF NOT EXISTS conta (n INTEGER); INSERT INTO conta VALUES (1);")
        erros = []

        def rodar():
            try:
                db.aplicar_migracoes()
            except Exception as e:  # pragma: no cover - so pra reportar
                erros.append(e)

        threads = [threading.Thread(target=rodar) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(erros, [])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM conta"), [(1,)])

    def test_aplicar_migracoes_devolve_o_que_aplicou(self):
        db.init_db()
        self.escrever("202609240001_x1_a.sql", "CREATE TABLE ret_a (id INTEGER);")
        self.assertEqual(db.aplicar_migracoes(), ["202609240001_x1_a.sql"])
        self.assertEqual(db.aplicar_migracoes(), [])

    def test_nao_toca_banco_de_producao(self):
        with patch.object(db, "DB_PATH", db.DB_PATH_PRODUCAO):
            with self.assertRaises(RuntimeError):
                db.garantir_banco_nao_producao()


class ComandosSqlTestCase(unittest.TestCase):
    def test_divide_respeitando_string_e_trigger(self):
        cmds = db._comandos_sql(
            "CREATE TABLE a (t TEXT); INSERT INTO a VALUES ('x;y');\n"
            "CREATE TRIGGER tr AFTER INSERT ON a BEGIN SELECT 1; SELECT 2; END;\n-- fim"
        )
        self.assertEqual(len(cmds), 3)
        self.assertTrue(cmds[2].strip().startswith("CREATE TRIGGER"))
        for c in cmds:
            self.assertTrue(sqlite3.complete_statement(c))


if __name__ == "__main__":
    unittest.main()
