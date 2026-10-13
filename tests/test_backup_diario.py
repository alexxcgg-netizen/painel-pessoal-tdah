"""Backup automatico diario (backup_diario.py). Banco temporario, nunca toca
o banco real; BACKUP_DIR sempre apontado pra uma pasta temporaria."""

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import backup_diario  # noqa: E402


class BackupDiarioTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir_banco = Path(self.tmp.name) / "data"
        self.dir_banco.mkdir()
        self.banco = self.dir_banco / "painel.db"
        conn = sqlite3.connect(self.banco)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('ola')")
        conn.commit()
        conn.close()
        p = patch.object(db, "DB_PATH", self.banco)
        p.start()
        self.addCleanup(p.stop)
        # sem BACKUP_DIR -> cai na pasta irma do banco (data/backups)
        p2 = patch.dict(os.environ, {"BACKUP_DIR": ""})
        p2.start()
        self.addCleanup(p2.stop)
        self.pasta = self.dir_banco / "backups"

    def test_cria_snapshot_consistente_na_pasta_irma_do_banco(self):
        agora = datetime(2026, 10, 13, 3, 30)
        caminho = backup_diario.rodar_backup_diario(agora)
        self.assertEqual(caminho, self.pasta / "painel-2026-10-13.db")
        copia = sqlite3.connect(caminho)
        try:
            self.assertEqual(copia.execute("SELECT v FROM t").fetchall(), [("ola",)])
        finally:
            copia.close()
        # nenhum temporario sobrando
        self.assertEqual([p.name for p in self.pasta.iterdir()], ["painel-2026-10-13.db"])

    def test_respeita_backup_dir(self):
        alvo = Path(self.tmp.name) / "outro"
        with patch.dict(os.environ, {"BACKUP_DIR": str(alvo)}):
            caminho = backup_diario.rodar_backup_diario(datetime(2026, 1, 2))
        self.assertEqual(caminho, alvo / "painel-2026-01-02.db")
        self.assertTrue(caminho.exists())

    def test_mantem_so_os_14_mais_recentes_e_nao_mexe_em_outros_arquivos(self):
        self.pasta.mkdir()
        base = datetime(2026, 9, 1)
        for i in range(20):
            d = base + timedelta(days=i)
            (self.pasta / f"painel-{d:%Y-%m-%d}.db").write_bytes(b"x")
        semanal = self.pasta / "painel-backup-2026-09-27_030000.db"
        semanal.write_bytes(b"x")
        backup_diario.rodar_backup_diario(datetime(2026, 9, 21))
        nomes = [p.name for p in backup_diario.listar_backups(self.pasta)]
        self.assertEqual(len(nomes), backup_diario.BACKUP_DIARIO_MANTER)
        self.assertEqual(nomes[-1], "painel-2026-09-21.db")
        self.assertNotIn("painel-2026-09-01.db", nomes)
        self.assertTrue(semanal.exists())

    def test_mesmo_dia_sobrescreve_sem_duplicar(self):
        agora = datetime(2026, 10, 13, 3, 30)
        backup_diario.rodar_backup_diario(agora)
        backup_diario.rodar_backup_diario(agora)
        self.assertEqual(len(backup_diario.listar_backups(self.pasta)), 1)

    def test_falha_nao_levanta_e_nao_deixa_temporario(self):
        with patch("backup_diario.sqlite3.connect", side_effect=sqlite3.OperationalError("disco cheio")):
            with self.assertLogs("app", level="ERROR"):
                self.assertIsNone(backup_diario.rodar_backup_diario(datetime(2026, 10, 13)))
        self.assertEqual(list(self.pasta.glob("*.parcial")), [])

    def test_falha_no_meio_preserva_o_backup_bom_do_mesmo_dia(self):
        agora = datetime(2026, 10, 13, 3, 30)
        bom = backup_diario.rodar_backup_diario(agora)
        conteudo = bom.read_bytes()
        with patch("backup_diario.os.replace", side_effect=OSError("trancado")):
            with self.assertLogs("app", level="ERROR"):
                self.assertIsNone(backup_diario.rodar_backup_diario(agora))
        self.assertEqual(bom.read_bytes(), conteudo)
        self.assertEqual(list(self.pasta.glob("*.parcial")), [])

    def test_pasta_impossivel_de_criar_nao_levanta(self):
        arquivo = Path(self.tmp.name) / "arquivo-no-lugar-da-pasta"
        arquivo.write_text("x")
        with patch.dict(os.environ, {"BACKUP_DIR": str(arquivo / "sub")}):
            with self.assertLogs("app", level="ERROR"):
                self.assertIsNone(backup_diario.rodar_backup_diario())

    def test_ao_subir_sem_nenhum_backup_faz(self):
        self.assertIsNotNone(backup_diario.backup_se_atrasado(datetime(2026, 10, 13, 10, 0)))
        self.assertEqual(len(backup_diario.listar_backups(self.pasta)), 1)

    def test_ao_subir_com_backup_recente_nao_faz(self):
        agora = datetime.now()
        backup_diario.rodar_backup_diario(agora)
        self.assertIsNone(backup_diario.backup_se_atrasado(agora + timedelta(hours=23)))

    def test_ao_subir_com_backup_velho_faz(self):
        agora = datetime.now()
        backup_diario.rodar_backup_diario(agora)
        novo = backup_diario.backup_se_atrasado(agora + timedelta(hours=25))
        self.assertEqual(novo, self.pasta / f"painel-{(agora + timedelta(hours=25)):%Y-%m-%d}.db")

    def test_checagem_ao_subir_nunca_levanta(self):
        with patch("backup_diario.listar_backups", side_effect=RuntimeError("boom")):
            with self.assertLogs("app", level="ERROR"):
                self.assertIsNone(backup_diario.backup_se_atrasado())


class SchedulerRegistraBackupDiarioTestCase(unittest.TestCase):
    def test_iniciar_scheduler_registra_cron_e_disparo_ao_subir(self):
        import app

        with patch("apscheduler.schedulers.background.BackgroundScheduler") as classe:
            app.iniciar_scheduler()
        chamadas = classe.return_value.add_job.call_args_list
        cron = [c for c in chamadas if c.args and c.args[0] is backup_diario.rodar_backup_diario]
        self.assertEqual(len(cron), 1)
        self.assertEqual(cron[0].args[1], "cron")
        self.assertEqual((cron[0].kwargs["hour"], cron[0].kwargs["minute"]), (3, 30))
        subida = [c for c in chamadas if c.args and c.args[0] is backup_diario.backup_se_atrasado]
        self.assertEqual(len(subida), 1)
        self.assertEqual(subida[0].args[1], "date")


if __name__ == "__main__":
    unittest.main()
