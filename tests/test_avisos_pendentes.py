"""Fila de avisos que o app do iPhone busca (avisos_pendentes.py + rotas/avisos_app.py, leva 07/11/2026 frente C):
o navegador vira reserva (3 min critico / 15 min o resto, ou na hora se o app sumiu ha 36 h), botoes novos e a
ferramenta `agendar_aviso` do chat. Banco temporario, relogio injetado, sem rede."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import auth  # noqa: E402
import avisos_pendentes as ap  # noqa: E402

TOKEN = {"Authorization": "Bearer token-de-teste"}
T0 = datetime(2030, 3, 11, 14, 0)
PIN = "135790"


class _Base(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "token-de-teste"})
        env.start()
        self.addCleanup(env.stop)

    def fila(self, tipo="tarefa_parada", ref=1, agora=T0, **kw):
        return ap.enfileirar(self.conn, tipo=tipo, ref=ref, titulo="🧹 E aí?", corpo="Ainda precisa?", agora=agora, **kw)


class AppVivoTestCase(_Base):
    def test_vivo_ate_36h_depois_do_contato(self):
        self.assertFalse(ap.app_vivo(self.conn, T0))
        ap.marcar_contato(self.conn, T0)
        self.assertTrue(ap.app_vivo(self.conn, T0 + timedelta(hours=35)))
        self.assertFalse(ap.app_vivo(self.conn, T0 + timedelta(hours=37)))

    def test_app_de_06_11_que_so_conta_o_agendado_vale_como_contato(self):
        import avisos_app

        avisos_app.gravar_agendados(self.conn, [], T0)
        self.assertTrue(ap.app_vivo(self.conn, T0 + timedelta(hours=1)))

    def test_quem_vai_pra_fila(self):
        ap.marcar_contato(self.conn, T0)
        self.assertTrue(ap.vai_pra_fila(self.conn, "tarefa_parada", T0))
        self.assertFalse(ap.vai_pra_fila(self.conn, "tarefa_horario", T0))  # o app agenda antes (06/11)
        self.assertFalse(ap.vai_pra_fila(self.conn, "indo_pra", T0))  # fila de hora_certa ja deu a chance
        self.assertTrue(ap.vai_pra_fila(self.conn, "tarefa_horario", T0, insistencia=True))  # repeticao vai
        self.assertFalse(ap.vai_pra_fila(self.conn, "tarefa_parada", T0 + timedelta(hours=40)))


class FilaTestCase(_Base):
    def setUp(self):
        super().setUp()
        ap.marcar_contato(self.conn, T0)

    def test_app_pega_e_o_navegador_nao_manda(self):
        aid = self.fila()
        [item] = ap.para_app(self.conn, T0)
        self.assertEqual((item["id"], item["ident"], item["tag"], item["titulo"]), (aid, f"fila-{aid}", "tarefa_parada-1", "🧹 E aí?"))
        self.assertEqual(ap.marcar_entregues(self.conn, [aid, "lixo", True], T0), 1)
        self.assertEqual(ap.para_app(self.conn, T0), [])
        enviados = []
        self.assertEqual(ap.mandar_vencidos(self.conn, T0 + timedelta(hours=1), enviados.append), 0)

    def test_prazo_critico_3_min_e_resto_15(self):
        self.fila("atraso_recado", 1)  # critico
        self.fila("tarefa_parada", 2)
        enviados = []
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=2), enviados.append)
        self.assertEqual(enviados, [])
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=3), enviados.append)
        self.assertEqual([r["tag"] for r in enviados], ["atraso_recado-1"])
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=14), enviados.append)
        self.assertEqual(len(enviados), 1)
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=15), enviados.append)
        self.assertEqual([r["tag"] for r in enviados], ["atraso_recado-1", "tarefa_parada-2"])
        # mandado pelo navegador: o app nao recebe mais (nao chega dois)
        self.assertEqual(ap.para_app(self.conn, T0 + timedelta(minutes=16)), [])

    def test_app_sumido_manda_na_hora(self):
        enviados = []
        agora = T0 + timedelta(hours=40)
        self.fila(agora=agora)
        ap.mandar_vencidos(self.conn, agora, enviados.append)
        self.assertEqual(len(enviados), 1)

    def test_entregar_fila_ou_push(self):
        chamado = []
        self.assertEqual(ap.entregar(self.conn, tipo="atraso_recado", ref=1, titulo="t", corpo="c", agora=T0,
                                     enviar_push=lambda: chamado.append(1)), "fila")
        self.assertEqual(chamado, [])
        longe = T0 + timedelta(hours=40)
        self.assertEqual(ap.entregar(self.conn, tipo="atraso_recado", ref=2, titulo="t", corpo="c", agora=longe,
                                     enviar_push=lambda: chamado.append(1)), "push")
        self.assertEqual(chamado, [1])

    def test_repeticao_troca_a_anterior_e_velho_sai_sem_mandar(self):
        self.fila(ref=5)
        self.fila(ref=5, agora=T0 + timedelta(minutes=10))
        self.assertEqual(len(ap.para_app(self.conn, T0 + timedelta(minutes=10))), 1)
        enviados = []
        ap.mandar_vencidos(self.conn, T0 + timedelta(hours=7), enviados.append)
        self.assertEqual(enviados, [])  # 7 h depois: aviso velho nao ajuda mais
        self.assertEqual(ap.resumo(self.conn, T0 + timedelta(hours=7))["cancelados"], 2)

    def test_tarefa_feita_enquanto_esperava_sai_da_fila(self):
        c = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Pagar', '2030-03-11', '15:00')")
        tid = c.lastrowid
        self.fila("tarefa_horario", tid, origem="insistencia")
        self.conn.execute("UPDATE tasks SET completed_at = '2030-03-11 14:01:00' WHERE id = ?", (tid,))
        self.conn.commit()
        self.assertEqual(ap.para_app(self.conn, T0), [])
        enviados = []
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=30), enviados.append)
        self.assertEqual(enviados, [])

    def test_resumo_conta_app_e_navegador(self):
        a = self.fila(ref=1)
        self.fila(ref=2)
        ap.marcar_entregues(self.conn, [a], T0)
        ap.mandar_vencidos(self.conn, T0 + timedelta(minutes=20), lambda r: None)
        r = ap.resumo(self.conn, T0 + timedelta(minutes=20))
        self.assertEqual((r["pelo_app"], r["pelo_navegador"], r["esperando"], r["app_vivo"]), (1, 1, 0, True))


class RotasTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()

    def test_pendentes_precisa_de_token_e_marca_contato(self):
        self.assertEqual(self.client.get("/api/app/avisos/pendentes").status_code, 401)
        agora = datetime.now()
        ap.enfileirar(self.conn, tipo="tarefa_parada", ref=3, titulo="🧹 E aí?", corpo="c", agora=agora)
        r = self.client.get("/api/app/avisos/pendentes", headers=TOKEN)
        self.assertEqual(r.status_code, 200)
        [item] = r.get_json()["avisos"]
        self.assertEqual(item["tag"], "tarefa_parada-3")
        self.assertTrue(ap.app_vivo(self.conn, datetime.now()))
        r = self.client.post("/api/app/avisos/pendentes/entregues", headers=TOKEN, json={"ids": [item["id"]]})
        self.assertEqual(r.get_json(), {"ok": True, "entregues": 1})
        self.assertEqual(self.client.post("/api/app/avisos/pendentes/entregues", headers=TOKEN, json={"ids": "x"}).status_code, 400)

    def _tarefa(self, hora="15:00"):
        c = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Pagar', ?, ?)",
                              (datetime.now().date().isoformat(), hora))
        self.conn.commit()
        return c.lastrowid

    def test_mais15_para_a_insistencia_e_tira_da_fila(self):
        tid = self._tarefa()
        tag = f"tarefa_horario-{tid}"
        db.registrar_aviso_insistente(self.conn, "tarefa_horario", tid, "Pagar", "c", tag, datetime.now())
        self.conn.commit()
        ap.marcar_contato(self.conn, datetime.now())
        ap.enfileirar(self.conn, tipo="tarefa_horario", ref=tid, titulo="⏰ De novo · Pagar", corpo="c", agora=datetime.now())
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": tag, "acao": "mais15"})
        self.assertEqual(r.get_json(), {"ok": True, "soneca_min": 15})
        self.assertEqual(db.avisos_insistentes_pendentes(self.conn), [])
        self.assertEqual(ap.para_app(self.conn, datetime.now()), [])

    def test_rota_conta_como_toque_e_acao_estranha_recusa(self):
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": "hora_de_sair-9", "acao": "rota"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": "hora_de_sair-9", "acao": "explodir"})
        self.assertEqual(r.status_code, 400)


class TickTestCase(_Base):
    """Os ganchos do tick em app.py: app vivo -> fila; vencido -> navegador."""

    def test_pra_fila_e_vencido_pelo_navegador(self):
        ap.marcar_contato(self.conn, datetime.now())
        self.assertTrue(app._pra_fila_do_app(self.conn, "tarefa_parada", "tarefa_parada-4", "🧹 E aí?", "c"))
        self.assertFalse(app._pra_fila_do_app(self.conn, "tarefa_horario", "tarefa_horario-4", "⏰ x", "c"))
        self.assertTrue(app._pra_fila_do_app(self.conn, "tarefa_horario", "tarefa_horario-4", "⏰ De novo · x", "c",
                                             origem="insistencia"))
        self.conn.execute("UPDATE avisos_pendentes SET prazo_push = '2000-01-01T00:00:00'")
        self.conn.commit()
        enviados = []
        with patch("push_client.enviar", side_effect=lambda sub, t, c, **kw: enviados.append((t, kw["tag"])) or True), \
                patch("telegram_bot.configurado", return_value=False):
            n = app._mandar_fila_vencida(self.conn, [{"subscription_json": json.dumps({"endpoint": "e"}), "endpoint": "e"}])
        self.assertEqual(n, 2)
        self.assertEqual(sorted(t for _, t in enviados), ["tarefa_horario-4", "tarefa_parada-4"])

    def test_app_sumido_nao_enfileira(self):
        self.assertFalse(app._pra_fila_do_app(self.conn, "tarefa_parada", "tarefa_parada-4", "t", "c"))


class AgendarAvisoTestCase(_Base):
    NOITE = datetime(2030, 3, 11, 14, 0)

    def setUp(self):
        super().setUp()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()
        for p in (patch("app._agora_brasilia", return_value=self.NOITE),
                  patch("maps_client.configurado", return_value=False),
                  patch("app._clima_contexto_resumo", return_value=None)):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def chat(self, entrada):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            resultados.append(executores["agendar_aviso"](entrada))
            return "Fechado.", ["agendar_aviso"], {"model": "claude-haiku-4-5-20251001", "input_tokens": 1,
                                                   "output_tokens": 1, "cost_usd": 0}

        with patch("claude_client.chat", side_effect=fake):
            r = self.client.post("/api/chat", json={"mensagem": "me avisa"})
        self.assertEqual(r.status_code, 200, r.get_json())
        return resultados[0]

    def test_ferramenta_existe(self):
        import ia.funcoes.chat as chat_mod

        self.assertIn("agendar_aviso", {t["name"] for t in chat_mod.CHAT_TOOLS})

    def test_agenda_na_hora_com_emoji_do_assunto(self):
        r = self.chat({"titulo": "Liga pro banco", "corpo": "Antes das 16h, que fecha.", "hora": "15:00", "assunto": "conversa"})
        self.assertTrue(r.get("ok"), r)
        self.assertEqual((r["quando"], r["titulo"]), ("2030-03-11T15:00", "📱 Liga pro banco"))
        row = self.conn.execute("SELECT tag, tipo, origem, quando, categoria FROM avisos_pendentes").fetchone()
        self.assertEqual(tuple(row), (f"aviso_ia-{r['id']}", "aviso_ia", "ia", "2030-03-11T15:00:00", "soneca"))
        r = self.chat({"titulo": "Tira a roupa da máquina", "em_minutos": 20})
        self.assertEqual(r["quando"], "2030-03-11T14:20")

    def test_recusa_voce_passado_longo_e_silencio(self):
        self.assertIn("tu", self.chat({"titulo": "Você precisa ligar", "hora": "15:00"})["erro"])
        self.assertIn("passou", self.chat({"titulo": "Liga", "hora": "13:00"})["erro"])
        self.assertIn("40", self.chat({"titulo": "x" * 41, "hora": "15:00"})["erro"])
        self.assertIn("silencioso", self.chat({"titulo": "Remédio", "hora": "23:30"})["erro"])
        self.assertTrue(self.chat({"titulo": "Remédio", "hora": "23:30", "mesmo_no_silencio": True}).get("ok"))

    def test_limite_de_20_por_dia(self):
        for n in range(ap.LIMITE_IA_DIA):
            self.assertTrue(ap.agendar_pelo_chat(self.conn, {"titulo": f"Aviso {n}", "hora": "16:00"}, self.NOITE).get("ok"))
        r = self.chat({"titulo": "Mais um", "hora": "16:30"})
        self.assertIn("limite", r["erro"])
        self.assertTrue(self.chat({"titulo": "Amanhã sim", "hora": "16:30", "quando_data": "2030-03-12"}).get("ok"))


if __name__ == "__main__":
    unittest.main()
