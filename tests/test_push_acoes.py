"""Leva 22/10: botoes "Feito" / "Adiar 1 h" no proprio aviso de uma tarefa (marcar sem abrir o app) e o
aviso de teste que diz se o iPhone mostrou os botoes (/api/push/acao)."""
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tests.test_assistente_vida import _Base

import app
import push_client

AGORA = datetime(2026, 10, 22, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


class PushAcoesTestCase(_Base):
    def _tarefa(self, hora="15:00", due="2026-10-22"):
        self.sql("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", ("Ligar pro banco", due, hora))
        return self.sql("SELECT max(id) i FROM tasks")[0]["i"]

    def _acao(self, tag, acao):
        with patch.object(app, "_agora_brasilia", return_value=AGORA):
            return self.client.post("/api/push/acao", json={"tag": tag, "acao": acao})

    def test_feito_conclui_a_tarefa_e_para_de_insistir(self):
        tid = self._tarefa()
        r = self._acao(f"tarefa_horario-{tid}", "feito")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["titulo"], "Ligar pro banco")
        self.assertIsNotNone(self.sql("SELECT completed_at FROM tasks WHERE id = ?", (tid,))[0]["completed_at"])
        # de novo: ja feita, nao quebra
        self.assertTrue(self._acao(f"tarefa_horario-{tid}", "feito").get_json()["ja_feita"])

    def test_adiar_empurra_uma_hora_ou_vai_pra_amanha(self):
        tid = self._tarefa("15:00")
        self.assertEqual(self._acao(f"tarefa_preparo-{tid}", "adiar").get_json()["hora"], "16:00")
        atrasada = self._tarefa("09:00")  # ja passou: 1 h a partir de agora
        self.assertEqual(self._acao(f"tarefa_horario_passou-{atrasada}", "adiar").get_json()["hora"], "15:00")
        tarde = self._tarefa("23:30")
        r = self._acao(f"tarefa_horario-{tarde}", "adiar").get_json()
        self.assertEqual((r["due_date"], r["hora"]), ("2026-10-23", "23:30"))
        sem_hora = self._tarefa(None)
        self.assertEqual(self._acao(f"tarefa_parada-{sem_hora}", "adiar").get_json()["due_date"], "2026-10-23")

    def test_pedido_ruim_e_aviso_sem_botao_recusam(self):
        tid = self._tarefa()
        self.assertEqual(self._acao(f"tarefa_horario-{tid}", "apagar").status_code, 400)
        self.assertEqual(self._acao(f"conta_pessoal-{tid}", "feito").status_code, 400)
        self.assertEqual(self._acao("tarefa_horario-99999", "feito").status_code, 404)
        self.assertEqual(self.client.post("/api/push/acao", json=["x"]).status_code, 400)
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self._acao(f"tarefa_horario-{tid}", "feito").status_code, 403)

    def test_teste_guarda_o_que_foi_tocado_e_o_status_mostra(self):
        self.assertIsNone(self.client.get("/api/push/status").get_json()["teste_botoes"])
        self.assertTrue(self._acao("teste-0", "toque").get_json()["teste"])
        self.assertEqual(self.client.get("/api/push/status").get_json()["teste_botoes"]["acao"], "toque")
        self._acao("teste-0", "feito")
        self.assertEqual(self.client.get("/api/push/status").get_json()["teste_botoes"]["acao"], "feito")

    def test_aviso_de_uma_tarefa_sai_com_os_botoes(self):
        self.assertEqual([a["action"] for a in app._acoes_do_aviso("tarefa_horario", "tarefa_horario-7")], ["feito", "adiar"])
        self.assertIsNone(app._acoes_do_aviso("tarefa_horario", "tarefa_horario-0"))
        self.assertIsNone(app._acoes_do_aviso("conta_pessoal", "conta_pessoal-7"))
        self.client.post("/api/push/inscrever", json={"endpoint": "https://exemplo.com/p", "keys": {"p256dh": "x", "auth": "y"}})
        with patch("push_client.configurado", return_value=True), patch("push_client.enviar", return_value=True) as env:
            self.client.post("/api/push/testar")
        self.assertEqual(env.call_args.kwargs["tag"], "teste-0")
        self.assertEqual(len(env.call_args.kwargs["acoes"]), 2)

    def test_payload_leva_no_maximo_dois_botoes(self):
        with patch("push_client.webpush") as wp:
            push_client.enviar({"endpoint": "x"}, "T", "C", tag="a-1", acoes=[{"action": str(i), "title": "b"} for i in range(4)])
        self.assertEqual(len(json.loads(wp.call_args.kwargs["data"])["acoes"]), 2)


if __name__ == "__main__":
    unittest.main()
