"""Faixa uso/m2-sync: sincronizacao automatica do Nubank de madrugada (4h de
Brasilia = 7h UTC, ver comentario em app.py/iniciar_scheduler), mantendo o
botao manual existente (rota `POST /api/bancos/sincronizar-nubank`).

Nunca chama a Pluggy real - Pluggy SEMPRE mockado (mesmo padrao de
tests/test_fase8_f1_banco.py e tests/test_fase9_sync.py: patch em
pluggy_client.get_item/get_accounts/get_transactions). Banco temporario
(db.DB_PATH), nunca le o .env real."""

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import rotas.f8_banco as f8_banco  # noqa: E402

PIN_TESTE = "123456"

ITEM_OK = {"status": "UPDATED", "connector": {"name": "Nubank"}}
CONTAS_OK = [{"id": "conta-1", "type": "BANK", "balance": 1000.0}]
TRANSACOES_OK = [
    {"id": "tx-1", "date": "2026-09-20T00:00:00Z", "amount": -50.0, "description": "IFOOD"},
]


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        self._env_original = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_original)
        # a trava e global no modulo - nunca deixa um teste que falhou no
        # meio (ou um mock que nao chegou ao "finally") vazar lock preso
        # pro proximo teste.
        if f8_banco._lock_sincronizacao_nubank.locked():
            f8_banco._lock_sincronizacao_nubank.release()

    def _configurar_pluggy(self):
        os.environ["PLUGGY_CLIENT_ID"] = "id-fake"
        os.environ["PLUGGY_CLIENT_SECRET"] = "secret-fake"
        os.environ["PLUGGY_ITEM_ID_NUBANK"] = "item-fake"

    def _total_transacoes(self):
        conn = db.get_db()
        total = conn.execute("SELECT COUNT(*) c FROM bank_transactions").fetchone()["c"]
        conn.close()
        return total


class JobRegistradoNoSchedulerTestCase(unittest.TestCase):
    """O scheduler so sobe dentro de iniciar_scheduler() - patch na classe
    real do apscheduler (mesmo mecanismo que app.py importa) pra nunca subir
    uma thread de verdade nem precisar desligar nada depois."""

    def test_job_registrado_as_7h_utc_cron(self):
        with patch("apscheduler.schedulers.background.BackgroundScheduler") as MockScheduler:
            instancia = MockScheduler.return_value
            app.iniciar_scheduler()

        chamadas_do_job = [
            chamada
            for chamada in instancia.add_job.call_args_list
            if chamada.args and chamada.args[0] is app.rodar_sincronizacao_nubank_automatica
        ]
        self.assertEqual(len(chamadas_do_job), 1, "job de sync do Nubank não foi registrado (ou foi 2x)")
        chamada = chamadas_do_job[0]
        self.assertEqual(chamada.args[1], "cron")
        self.assertEqual(chamada.kwargs.get("hour"), 7)
        self.assertEqual(chamada.kwargs.get("minute"), 0)

        # os outros dois jobs que ja existiam continuam la (nao apaguei nada).
        self.assertTrue(
            any(c.args and c.args[0] is app.verificar_e_notificar for c in instancia.add_job.call_args_list)
        )
        self.assertTrue(
            any(
                c.args and c.args[0] is app.rodar_backup_automatico_semanal
                for c in instancia.add_job.call_args_list
            )
        )
        instancia.start.assert_called_once()


class JobSemConfiguracaoTestCase(_BaseTestCase):
    def test_sem_pluggy_configurada_nao_faz_nada_e_nao_loga(self):
        # ambiente de teste tipico: sem PLUGGY_CLIENT_ID/SECRET/ITEM_ID.
        os.environ.pop("PLUGGY_CLIENT_ID", None)
        os.environ.pop("PLUGGY_CLIENT_SECRET", None)
        os.environ.pop("PLUGGY_ITEM_ID_NUBANK", None)
        with patch("rotas.f8_banco.sincronizar_nubank") as mock_sync:
            with self.assertRaises(AssertionError):
                # assertNoLogs so existe no Python 3.10+; garantimos aqui
                # tentando capturar QUALQUER log e falhando de proposito se
                # vier vazio, o que assertLogs ja faz sozinho (levanta
                # AssertionError quando nada foi logado).
                with self.assertLogs("app", level="DEBUG"):
                    app.rodar_sincronizacao_nubank_automatica()
        mock_sync.assert_not_called()

    def test_client_secret_configurado_mas_sem_item_id_tambem_sai_em_silencio(self):
        os.environ["PLUGGY_CLIENT_ID"] = "id-fake"
        os.environ["PLUGGY_CLIENT_SECRET"] = "secret-fake"
        os.environ.pop("PLUGGY_ITEM_ID_NUBANK", None)
        with patch("rotas.f8_banco.sincronizar_nubank") as mock_sync:
            app.rodar_sincronizacao_nubank_automatica()
        mock_sync.assert_not_called()


class JobComPluggyConfiguradaTestCase(_BaseTestCase):
    def test_sucesso_chama_a_funcao_compartilhada_e_loga_info(self):
        self._configurar_pluggy()
        resultado_falso = {"ok": True, "mensagem": "1 nova(s), 0 atualizada(s), 0 sem mudanca, 0 removida(s)"}
        with patch("rotas.f8_banco.sincronizar_nubank", return_value=resultado_falso) as mock_sync:
            with self.assertLogs("app", level="INFO") as logs:
                app.rodar_sincronizacao_nubank_automatica()
        mock_sync.assert_called_once()
        # chamou com uma conexao propria (sqlite3.Connection), nao com None
        # nem reaproveitando conexao de request nenhuma.
        import sqlite3

        self.assertIsInstance(mock_sync.call_args.args[0], sqlite3.Connection)
        self.assertTrue(any("sincronização automática do Nubank" in linha for linha in logs.output))
        self.assertTrue(any("1 nova(s)" in linha for linha in logs.output))

    def test_excecao_no_pluggy_vira_log_de_erro_sem_subir_e_sem_apagar_dado(self):
        self._configurar_pluggy()

        # primeiro, um sync manual bom de verdade (via a rota), pra ter dado
        # real gravado e commitado.
        with (
            patch("pluggy_client.get_item", return_value=ITEM_OK),
            patch("pluggy_client.get_accounts", return_value=CONTAS_OK),
            patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False)),
        ):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._total_transacoes(), 1)

        # agora o job de madrugada roda e a Pluggy esta fora do ar - nao
        # pode derrubar o scheduler nem apagar o que ja estava bom.
        erro = requests.RequestException("timeout")
        with patch("pluggy_client.get_item", side_effect=erro):
            with self.assertLogs("app", level="ERROR") as logs:
                try:
                    app.rodar_sincronizacao_nubank_automatica()
                except Exception as e:  # nunca deveria chegar aqui
                    self.fail(f"rodar_sincronizacao_nubank_automatica deixou uma excecao subir: {e}")

        self.assertTrue(any("falhou" in linha for linha in logs.output))
        # dado do ultimo sync bom continua intacto.
        self.assertEqual(self._total_transacoes(), 1)

    def test_excecao_totalmente_inesperada_tambem_fica_so_no_log(self):
        self._configurar_pluggy()
        with patch("rotas.f8_banco.sincronizar_nubank", side_effect=RuntimeError("boom")):
            with self.assertLogs("app", level="ERROR") as logs:
                try:
                    app.rodar_sincronizacao_nubank_automatica()
                except Exception as e:
                    self.fail(f"excecao inesperada vazou do job: {e}")
        self.assertTrue(any("exceção inesperada" in linha for linha in logs.output))


class TravaSimplesTestCase(_BaseTestCase):
    """Evita rodar duas sincronizacoes ao mesmo tempo (botao manual x job) -
    a trava mora em sincronizar_nubank() (rotas/f8_banco.py), reusada pelos
    dois lados."""

    def test_segunda_chamada_com_lock_preso_devolve_erro_sem_travar(self):
        self._configurar_pluggy()
        conn = db.get_db()
        try:
            f8_banco._lock_sincronizacao_nubank.acquire()
            try:
                resultado = f8_banco.sincronizar_nubank(conn)
            finally:
                f8_banco._lock_sincronizacao_nubank.release()
        finally:
            conn.close()
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["status"], 409)

    def test_lock_e_liberado_depois_de_uma_sincronizacao_boa(self):
        self._configurar_pluggy()
        with (
            patch("pluggy_client.get_item", return_value=ITEM_OK),
            patch("pluggy_client.get_accounts", return_value=CONTAS_OK),
            patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False)),
        ):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(f8_banco._lock_sincronizacao_nubank.locked())


class RotaManualContinuaIgualTestCase(_BaseTestCase):
    """Regressao: a extracao de sincronizar_nubank(conn) nao pode mudar o
    contrato HTTP da rota manual (formato de resposta, codigos de erro)."""

    def test_resposta_da_rota_manual_mantem_o_mesmo_formato(self):
        self._configurar_pluggy()
        with (
            patch("pluggy_client.get_item", return_value=ITEM_OK),
            patch("pluggy_client.get_accounts", return_value=CONTAS_OK),
            patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False)),
        ):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        for chave in ("ok", "novas", "atualizadas", "sem_mudanca", "removidas", "mensagem", "banco", "contas"):
            self.assertIn(chave, corpo)
        self.assertTrue(corpo["ok"])
        self.assertEqual(corpo["banco"], "nubank")
        self.assertEqual(corpo["novas"], 1)

    def test_sem_configuracao_continua_400_sem_chamar_pluggy(self):
        with patch("pluggy_client.get_item") as mock_get_item:
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 400)
        mock_get_item.assert_not_called()

    def test_ultimo_sync_ok_aparece_no_sync_status_depois_de_sincronizar(self):
        self._configurar_pluggy()
        antes = self.client.get("/api/bancos/sync-status").get_json()
        self.assertIsNone(antes["ultimo_sync_nubank_ok"])

        with (
            patch("pluggy_client.get_item", return_value=ITEM_OK),
            patch("pluggy_client.get_accounts", return_value=CONTAS_OK),
            patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False)),
        ):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)

        depois = self.client.get("/api/bancos/sync-status").get_json()
        self.assertIsNotNone(depois["ultimo_sync_nubank_ok"])
        self.assertIn("Última sincronização", depois["info"])


if __name__ == "__main__":
    logging.disable(logging.NOTSET)
    unittest.main()
