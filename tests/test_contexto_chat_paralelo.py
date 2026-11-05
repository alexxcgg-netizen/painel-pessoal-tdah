"""Contexto do chat com a busca de fora em paralelo + /api/chat/aquecer (2026-11-05, leva "perfeição").

Antes: iCloud (~4 s com o cache vencido), construtora e tempo saíam em fila antes de a IA começar a
responder. Agora saem juntos e o front aquece os caches quando ele toca no campo ou no microfone.
"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402


PIN = "975310"


def _icloud_com_cache(encontro):
    """eventos_do_dia de mentira com o cache de 60 s do caldav_client: só a 1a chamada vai "à rede"."""
    estado = {"chamadas": 0, "guardado": None, "trava": threading.Lock()}

    def eventos_do_dia(_dia):
        with estado["trava"]:
            estado["chamadas"] += 1
            if estado["guardado"] is not None:
                return list(estado["guardado"])
            encontro.wait()
            estado["guardado"] = [{"titulo": "Reunião de mentira", "inicio": "2026-11-05T15:00:00", "fim": "2026-11-05T16:00:00"}]
            return list(estado["guardado"])

    return eventos_do_dia, estado


def _no_encontro(encontro, valor):
    """Só volta quando as 3 buscas de fora estão no ar AO MESMO TEMPO; em fila o encontro estoura (5 s)."""
    def f(*_a, **_k):
        encontro.wait()
        return valor

    return f


class ContextoChatParaleloTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        app._AQUECIDO_EM["t"] = 0.0

    def test_busca_de_fora_sai_junta_e_o_texto_continua_igual(self):
        # prova pela sobreposição, não pelo relógio: com o PC cheio (suíte inteira) o tempo variava demais
        encontro = threading.Barrier(3, timeout=5)
        eventos_do_dia, estado = _icloud_com_cache(encontro)
        conn = db.get_db()
        try:
            with patch("app.caldav_client.configurado", return_value=True), \
                    patch("app.caldav_client.eventos_do_dia", side_effect=eventos_do_dia), \
                    patch("app._construtora_contexto_resumo", side_effect=_no_encontro(encontro, "caixa de mentira")), \
                    patch("app._buscar_resumo_construtora", return_value=None), \
                    patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                    patch("app._clima_contexto_resumo", side_effect=_no_encontro(encontro, "chuva de mentira")):
                texto = app._contexto_chat(conn)
        finally:
            conn.close()
        self.assertFalse(encontro.broken, "a busca de fora voltou a sair em fila")
        self.assertIn("Reunião de mentira as 15:00", texto)
        self.assertIn("Construtora (financeiro geral): caixa de mentira", texto)
        self.assertIn("Previsão do tempo hoje: chuva de mentira", texto)
        self.assertEqual(estado["chamadas"], 2)  # aquecimento + a de verdade (que já sai do cache)

    def test_erro_de_fora_continua_derrubando_igual_antes(self):
        conn = db.get_db()
        try:
            with patch("app._construtora_contexto_resumo", side_effect=RuntimeError("construtora caiu")), \
                    patch("app._clima_contexto_resumo", return_value=None):
                with self.assertRaises(RuntimeError):
                    app._contexto_chat(conn)
        finally:
            conn.close()

    def test_icloud_fora_do_ar_nao_quebra(self):
        conn = db.get_db()
        try:
            with patch("app.caldav_client.configurado", return_value=True), \
                    patch("app.caldav_client.eventos_do_dia", side_effect=RuntimeError("iCloud fora")), \
                    patch("app._construtora_contexto_resumo", return_value=None), \
                    patch("app._clima_contexto_resumo", return_value=None):
                texto = app._contexto_chat(conn)
        finally:
            conn.close()
        self.assertIn("Compromissos de hoje (em ordem de horário): nenhum", texto)

    def _cliente_logado(self):
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        cliente = app.app.test_client()
        self.assertEqual(cliente.post("/login", json={"pin": PIN}).status_code, 200)
        return cliente

    def test_aquecer_responde_na_hora_e_segura_repeticao(self):
        cliente = self._cliente_logado()
        pronto = threading.Event()
        chamadas = []

        def icloud():
            chamadas.append("icloud")
            pronto.set()
            return []

        with patch("app._icloud_de_hoje_seguro", side_effect=icloud), \
                patch("app._buscar_resumo_construtora", return_value=None), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None):
            t0 = time.perf_counter()
            res = cliente.post("/api/chat/aquecer")
            self.assertEqual(res.status_code, 204)
            self.assertLess(time.perf_counter() - t0, 0.5)
            self.assertTrue(pronto.wait(5))
            self.assertEqual(cliente.post("/api/chat/aquecer").status_code, 204)
            time.sleep(0.2)
        self.assertEqual(chamadas, ["icloud"])  # o segundo, dentro de 30 s, não busca de novo

    def test_aquecer_exige_login(self):
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.assertEqual(app.app.test_client().post("/api/chat/aquecer").status_code, 401)


if __name__ == "__main__":
    unittest.main()
