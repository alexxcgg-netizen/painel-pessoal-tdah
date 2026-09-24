"""Fase 7, Etapa 0: gatilhos do assistente proativo (assistente/gatilhos/).

Gatilhos falsos escritos numa pasta temporaria acrescentada ao
`assistente.gatilhos.__path__` so durante o teste."""

import sqlite3
import sys
import tempfile
import textwrap
import unittest
import uuid
from datetime import datetime
from pathlib import Path

import db

_tmp_dir = tempfile.TemporaryDirectory()

from assistente import gatilhos  # noqa: E402


class _PastaGatilhos:
    def __init__(self, modulos: dict[str, str]):
        self.modulos = modulos

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        for nome, codigo in self.modulos.items():
            (Path(self.tmp.name) / f"{nome}.py").write_text(textwrap.dedent(codigo))
        # So a pasta temporaria: modulos reais das faixas nao interferem no teste.
        self._path_antes = list(gatilhos.__path__)
        gatilhos.__path__[:] = [self.tmp.name]
        return self

    def __exit__(self, *exc):
        gatilhos.__path__[:] = self._path_antes
        for nome in self.modulos:
            sys.modules.pop(f"assistente.gatilhos.{nome}", None)
        self.tmp.cleanup()


GRAVA = """
    def executar(conn, agora):
        conn.execute("INSERT INTO log_gatilho (nome, quando) VALUES (?, ?)", ("{nome}", agora.isoformat()))
        return "{nome} rodou"
    """

EXPLODE = """
    def executar(conn, agora):
        conn.execute("INSERT INTO log_gatilho (nome, quando) VALUES ('meio', 'x')")
        raise RuntimeError("gatilho quebrado")
    """


class GatilhosTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(Path(_tmp_dir.name) / f"{uuid.uuid4().hex}.db")
        self.conn.execute("CREATE TABLE log_gatilho (nome TEXT, quando TEXT)")
        self.conn.commit()
        self.agora = datetime(2026, 9, 24, 8, 30)
        self.s = uuid.uuid4().hex[:8]

    def tearDown(self):
        self.conn.close()

    def log(self):
        return [r[0] for r in self.conn.execute("SELECT nome FROM log_gatilho ORDER BY rowid")]

    def test_sem_gatilho_nenhum_nao_executa_nada(self):
        with _PastaGatilhos({}):
            self.assertEqual(gatilhos.nomes_gatilhos(), [])
            self.assertEqual(gatilhos.executar_todos(self.conn, self.agora), {})

    def test_roda_todos_em_ordem_alfabetica_e_ignora_modulo_sem_executar(self):
        s = self.s
        with _PastaGatilhos({
            f"b_{s}": GRAVA.format(nome="b"),
            f"a_{s}": GRAVA.format(nome="a"),
            f"c_{s}": "AJUDANTE = 1\n",
        }):
            rel = gatilhos.executar_todos(self.conn, self.agora)
        self.assertEqual(self.log(), ["a", "b"])
        self.assertEqual(rel, {f"a_{s}": {"ok": True, "resultado": "a rodou"},
                               f"b_{s}": {"ok": True, "resultado": "b rodou"}})
        quando = self.conn.execute("SELECT quando FROM log_gatilho LIMIT 1").fetchone()[0]
        self.assertEqual(quando, "2026-09-24T08:30:00")

    def test_gatilho_quebrado_nao_derruba_os_outros_e_desfaz_o_que_escreveu(self):
        s = self.s
        with _PastaGatilhos({
            f"a_{s}": GRAVA.format(nome="a"),
            f"b_{s}": EXPLODE,
            f"c_{s}": "def executar(conn, agora):\n    return 1 / 0\n",
            f"d_{s}": "def executar(conn, agora:\n",  # erro de sintaxe no import
            f"e_{s}": GRAVA.format(nome="e"),
        }):
            with self.assertLogs("assistente.gatilhos", level="ERROR") as logs:
                rel = gatilhos.executar_todos(self.conn, self.agora)
        self.assertEqual(self.log(), ["a", "e"])  # "meio" do b foi desfeito
        self.assertTrue(rel[f"a_{s}"]["ok"])
        self.assertTrue(rel[f"e_{s}"]["ok"])
        self.assertEqual(rel[f"b_{s}"], {"ok": False, "erro": "RuntimeError: gatilho quebrado"})
        self.assertTrue(rel[f"c_{s}"]["erro"].startswith("ZeroDivisionError"))
        self.assertTrue(rel[f"d_{s}"]["erro"].startswith("SyntaxError"))
        self.assertTrue(any(f"b_{s}" in linha for linha in logs.output))

    def test_com_conexao_real_do_painel(self):
        with tempfile.TemporaryDirectory() as tmp:
            antes = db.DB_PATH
            db.DB_PATH = Path(tmp) / "painel.db"
            try:
                db.garantir_banco_nao_producao()
                db.init_db()
                conn = db.get_db()
                gravar_tarefa = """
                    def executar(conn, agora):
                        conn.execute("INSERT INTO tasks (title) VALUES ('do gatilho')")
                    """
                with _PastaGatilhos({f"t_{self.s}": gravar_tarefa}):
                    rel = gatilhos.executar_todos(conn, self.agora)
                conn.close()
                conn = db.get_db()
                self.assertEqual(conn.execute("SELECT title FROM tasks").fetchall()[0]["title"], "do gatilho")
                conn.close()
                self.assertEqual(rel, {f"t_{self.s}": {"ok": True, "resultado": None}})
            finally:
                db.DB_PATH = antes


if __name__ == "__main__":
    unittest.main()
