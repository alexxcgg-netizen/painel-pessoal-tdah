"""Fase 7 (M1): ligacoes feitas pelo integrador em app.py.

- verificar_e_notificar respeita o liga/desliga por tipo da tela
  Assistente > Avisos (assistente.avisos.esta_ligado), sem trocar o silencio
  antigo (urgente continua passando).
- registrar_tarefa do chat grava a data resolvida em codigo
  (claude_client.resolver_quando_data), nao a conta do modelo.
"""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402
import claude_client  # noqa: E402
from assistente import avisos  # noqa: E402

PIN = "482913"
SUB = {"endpoint": "https://exemplo.com/m1", "keys": {"p256dh": "x", "auth": "y"}}


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        p = patch("notificacoes.dentro_do_horario_silencioso", return_value=False)
        p.start()
        self.addCleanup(p.stop)


class AvisoDesligadoNaoSaiTestCase(_Base):
    def _orcamento_estourado(self):
        conn = db.get_db()
        conn.execute("INSERT INTO orcamentos (categoria, valor_limite) VALUES ('mercado', 100)")
        conn.execute("INSERT INTO expenses (amount, category, tipo) VALUES (110, 'mercado', 'real')")
        conn.commit()
        conn.close()

    def _verificar(self):
        with patch("push_client.configurado", return_value=True), patch(
            "push_client.enviar", return_value=True
        ) as mock_enviar, patch("app.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 9, 23, 14, 0)
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.combine = datetime.combine
            self.client.post("/api/push/inscrever", json=SUB)
            res = self.client.post("/api/notificacoes/verificar-agora")
        return res.get_json()["avisos_enviados"], mock_enviar

    def test_ligado_por_padrao_manda(self):
        self._orcamento_estourado()
        enviados, _ = self._verificar()
        self.assertEqual(enviados, 1)

    def test_tipo_desligado_nao_manda_e_nao_marca_como_notificado(self):
        self._orcamento_estourado()
        conn = db.get_db()
        avisos.definir_tipo("orcamento", ligado=False, conn=conn)
        conn.commit()
        conn.close()
        enviados, mock_enviar = self._verificar()
        self.assertEqual(enviados, 0)
        self.assertEqual(mock_enviar.call_count, 0)
        # religou: sai na proxima rodada (nao ficou marcado como ja enviado)
        conn = db.get_db()
        avisos.definir_tipo("orcamento", ligado=True, conn=conn)
        conn.commit()
        conn.close()
        enviados, _ = self._verificar()
        self.assertEqual(enviados, 1)

    def test_config_corrompida_nao_derruba_o_loop(self):
        self._orcamento_estourado()
        conn = db.get_db()
        db.definir_configuracao(conn, avisos.CHAVE_CONFIG, "{nao e json")
        conn.commit()
        conn.close()
        enviados, _ = self._verificar()
        self.assertEqual(enviados, 1)


class DataDaTarefaDoChatTestCase(_Base):
    def _registrar_via_chat(self, entrada):
        def falso_chat(historico, contexto, memorias, executores, **kw):
            executores["registrar_tarefa"](entrada)
            return "ok", ["registrar_tarefa"], {"model": "x", "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        with patch("claude_client.chat", side_effect=falso_chat), patch(
            "app._plano_local_chat", return_value=None
        ):
            res = self.client.post("/api/chat", json={"mensagem": "nova tarefa"})
        self.assertLess(res.status_code, 500, res.get_data(as_text=True))
        conn = db.get_db()
        row = conn.execute("SELECT due_date FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return row["due_date"] if row else "SEM-LINHA"

    def test_amanha_vira_data_em_codigo_mesmo_com_modelo_errando(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        entrada = {"titulo": "ligar pro dentista", "quando": "amanha", "quando_data": "1999-01-01"}
        self.assertEqual(self._registrar_via_chat(entrada), amanha)

    def test_sem_pista_de_dia_usa_quando_data_valido_do_modelo(self):
        entrada = {"titulo": "pagar boleto", "quando": None, "quando_data": "2026-10-05"}
        self.assertEqual(self._registrar_via_chat(entrada), "2026-10-05")

    def test_quando_data_invalido_nao_quebra(self):
        entrada = {"titulo": "algo", "quando": None, "quando_data": "31/02/xx"}
        self.assertIsNone(self._registrar_via_chat(entrada))

    def test_reexport_no_claude_client(self):
        self.assertTrue(callable(claude_client.resolver_quando_data))


if __name__ == "__main__":
    unittest.main()
