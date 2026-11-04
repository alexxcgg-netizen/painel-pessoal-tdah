"""tests/banco_modelo.py: a copia tem que ser igual ao init_db de verdade e nunca tocar outro banco."""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db


def _retrato(caminho: Path) -> dict:
    conn = sqlite3.connect(caminho)
    try:
        esquema = sorted(
            (t, n, s or "")
            for t, n, s in conn.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
        )
        linhas = {}
        for tabela in [n for t, n, _ in esquema if t == "table"]:
            colunas = [c[1] for c in conn.execute(f'PRAGMA table_info("{tabela}")')]
            variam = {"criado_em", "created_at", "aplicada_em", "atualizado_em", "updated_at"}
            fixas = ", ".join(f'"{c}"' for c in colunas if c not in variam) or "1"
            linhas[tabela] = sorted(map(repr, conn.execute(f'SELECT {fixas} FROM "{tabela}"').fetchall()))
        return {"esquema": esquema, "linhas": linhas}
    finally:
        conn.close()


class BancoModeloTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        caminho = db.DB_PATH
        self.addCleanup(setattr, db, "DB_PATH", caminho)
        db.DB_PATH = self.pasta / "teste.db"

    def test_copia_igual_ao_init_db_de_verdade(self):
        db.init_db()
        copia = _retrato(db.DB_PATH)
        db.DB_PATH = self.pasta / "de_verdade.db"
        db.init_db.original()
        self.assertEqual(copia, _retrato(db.DB_PATH))

    def test_cada_banco_nasce_independente(self):
        db.init_db()
        conn = db.get_db()
        conn.execute("CREATE TABLE so_neste (x)")
        conn.commit()
        conn.close()
        db.DB_PATH = self.pasta / "outro.db"
        db.init_db()
        self.assertNotIn("so_neste", str(_retrato(db.DB_PATH)["esquema"]))

    def test_banco_que_ja_existe_vai_pelo_init_db_original(self):
        db.init_db()
        with patch.object(shutil, "copyfile") as copiar:
            db.init_db()
        copiar.assert_not_called()

    def test_banco_antigo_recebe_as_migracoes(self):
        conn = sqlite3.connect(db.DB_PATH)
        conn.execute("CREATE TABLE antiga (x)")
        conn.commit()
        conn.close()
        db.init_db()
        retrato = str(_retrato(db.DB_PATH)["esquema"])
        self.assertIn("antiga", retrato)
        self.assertIn("migracoes_aplicadas", retrato)

    def test_pasta_de_migracoes_trocada_nao_usa_o_modelo(self):
        vazia = self.pasta / "migracoes"
        vazia.mkdir()
        with patch.object(db, "MIGRACOES_DIR", vazia), patch.object(shutil, "copyfile") as copiar:
            db.init_db()
        copiar.assert_not_called()
        conn = db.get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM migracoes_aplicadas").fetchone()[0], 0)
        conn.close()

    def test_banco_real_nunca_recebe_copia(self):
        with patch.object(db, "DB_PATH", db.DB_PATH_PRODUCAO), patch(
            "db.sqlite3.connect", side_effect=ConnectionAbortedError("parou antes de abrir")
        ), patch("banco_modelo.shutil.copyfile") as copiar, self.assertRaises(ConnectionAbortedError):
            db.init_db()
        copiar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
