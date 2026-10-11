"""Notificacoes de 2026-10-11: o agendador que nunca rodava (waitress app:app), o aviso
"Hora de se arrumar" / "Hora de sair" pra compromisso de sair (o Alex leva 40 min pra se
arrumar pra date/festa), o aviso ~30 min antes de tarefa com hora, e o push que abre na
aba certa. Nenhuma rede: push_client.enviar e o Google sao sempre mockados."""
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import notificacoes  # noqa: E402
import push_client  # noqa: E402

PIN_TESTE = "123456"
HOJE = datetime(2026, 10, 11, 12, 0)


class _Base(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora, local=None, feita=False, dia="2026-10-11"):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, completed_at) VALUES (?, ?, ?, ?, ?)",
            (titulo, dia, hora, local, "2026-10-11 10:00:00" if feita else None),
        )
        self.conn.commit()
        return cur.lastrowid


class CompromissoDeSairTestCase(unittest.TestCase):
    def test_reconhece_date_festa_e_ignora_parecidos(self):
        for t in ("Date", "date com a Ana", "Festa do Lucas", "Aniversário da mãe", "jantar fora", "Balada",
                  "happy hour da firma", "rolê com a galera"):
            self.assertTrue(notificacoes.e_compromisso_de_sair(t), t)
        for t in ("Lavar o carro", "Atualizar planilha", "update do app", "Barbearia", "Visitar a irmã",
                  "Reunião com fornecedor"):
            self.assertFalse(notificacoes.e_compromisso_de_sair(t), t)


class PlanoSeArrumarTestCase(_Base):
    def test_conta_de_tras_pra_frente_sem_local_usa_folga(self):
        self.tarefa("Date", "20:00")
        [p] = notificacoes.plano_se_arrumar(self.conn, HOJE, 40)
        self.assertEqual(p["saida"].strftime("%H:%M"), "19:45")  # 15 min de folga
        self.assertEqual(p["comecar"].strftime("%H:%M"), "19:05")  # menos 40 min
        self.assertIsNone(p["trajeto_min"])

    def test_com_local_usa_o_trajeto_de_verdade(self):
        self.tarefa("Jantar", "20:00", local="Restaurante X, Blumenau")
        chamado = []
        [p] = notificacoes.plano_se_arrumar(
            self.conn, datetime(2026, 10, 11, 18, 0), 40, trajeto_min=lambda l: chamado.append(l) or 35
        )
        self.assertEqual(chamado, ["Restaurante X, Blumenau"])
        self.assertEqual(p["saida"].strftime("%H:%M"), "19:25")
        self.assertEqual(p["comecar"].strftime("%H:%M"), "18:45")

    def test_longe_do_horario_nao_gasta_consulta_de_trajeto(self):
        self.tarefa("Jantar", "21:00", local="Blumenau")
        planos = notificacoes.plano_se_arrumar(
            self.conn, datetime(2026, 10, 11, 9, 0), 40, trajeto_min=lambda l: self.fail("nao devia consultar")
        )
        self.assertEqual(planos[0]["caminho_min"], 15)

    def test_ignora_feito_passado_e_tarefa_comum(self):
        self.tarefa("Date", "20:00", feita=True)
        self.tarefa("Festa", "11:00")  # ja passou
        self.tarefa("Lavar o carro", "15:00")
        self.tarefa("Date", "20:00", dia="2026-10-12")  # amanha
        self.assertEqual(notificacoes.plano_se_arrumar(self.conn, HOJE, 40), [])

    def test_avisos_na_hora_de_comecar_e_de_sair(self):
        self.tarefa("Date", "20:00")
        planos = lambda agora: notificacoes.plano_se_arrumar(self.conn, agora, 40)  # noqa: E731
        # 18:59 - cedo demais
        self.assertEqual(notificacoes.avisos_se_arrumar(planos(datetime(2026, 10, 11, 18, 59)), datetime(2026, 10, 11, 18, 59)), [])
        agora = datetime(2026, 10, 11, 19, 2)
        [(tipo, _, titulo, corpo)] = notificacoes.avisos_se_arrumar(planos(agora), agora)
        self.assertEqual((tipo, titulo), ("se_arrumar", "Hora de se arrumar"))
        self.assertIn("40 min", corpo)
        self.assertIn("19:45", corpo)
        agora = datetime(2026, 10, 11, 19, 43)
        tipos = [a[0] for a in notificacoes.avisos_se_arrumar(planos(agora), agora)]
        self.assertEqual(tipos, ["se_arrumar", "hora_de_sair"])  # o dedup de hoje segura o 1o repetido

    def test_tarefa_se_arrumar_ja_marcada_nao_duplica(self):
        self.tarefa("Date", "20:00")
        self.tarefa("Me arrumar pro date", "19:05")
        agora = datetime(2026, 10, 11, 19, 3)
        tipos = [a[0] for a in notificacoes.avisos_se_arrumar(notificacoes.plano_se_arrumar(self.conn, agora, 40), agora)]
        self.assertNotIn("se_arrumar", tipos)


class TarefaPreparoTestCase(_Base):
    def test_avisa_entre_15_e_30_min_antes(self):
        tid = self.tarefa("Visitar a irmã", "17:00")
        self.assertEqual(notificacoes.tarefas_preparo(self.conn, datetime(2026, 10, 11, 16, 20)), [])
        [(i, msg)] = notificacoes.tarefas_preparo(self.conn, datetime(2026, 10, 11, 16, 30))
        self.assertEqual(i, tid)
        self.assertIn("faltam 30 min", msg)
        self.assertEqual(notificacoes.tarefas_preparo(self.conn, datetime(2026, 10, 11, 16, 50)), [])
        self.assertEqual(notificacoes.tarefas_preparo(self.conn, datetime(2026, 10, 11, 16, 30), ignorar={tid}), [])


class VerificarENotificarTestCase(_Base):
    def _rodar(self, agora):
        enviados = []

        def falso(sub, titulo, corpo, url="", tag=""):
            enviados.append({"titulo": titulo, "corpo": corpo, "url": url, "tag": tag})
            return True

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        self.conn.commit()
        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=falso), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._eventos_de_hoje_com_seguranca", return_value=[]), \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("app.date", type("D", (), {"today": staticmethod(lambda: agora.date()),
                                                   "fromisoformat": staticmethod(datetime.fromisoformat)})):
            app.verificar_e_notificar()
        return enviados

    def test_date_manda_se_arrumar_com_link_e_tag_e_nao_o_daqui_a_pouco(self):
        tid = self.tarefa("Date", "20:00")
        enviados = self._rodar(datetime(2026, 10, 11, 19, 5))
        avisos = [e for e in enviados if e["titulo"] == "Hora de se arrumar"]
        self.assertEqual(len(avisos), 1, enviados)
        self.assertEqual(avisos[0]["url"], "/?aba=tarefas")
        self.assertEqual(avisos[0]["tag"], f"se_arrumar-{tid}")
        # 19:52 (dentro dos 10 min): sai "Hora de sair", nunca o "daqui a pouco" de tarefa comum
        enviados = self._rodar(datetime(2026, 10, 11, 19, 52))
        titulos = [e["titulo"] for e in enviados]
        self.assertIn("Hora de sair", titulos)
        self.assertNotIn("Lembrete", titulos)

    def test_tempo_de_se_arrumar_vem_da_configuracao(self):
        db.definir_configuracao(self.conn, "tempo_se_arrumar_min", "60")
        self.conn.commit()
        self.tarefa("Festa", "22:00")
        enviados = self._rodar(datetime(2026, 10, 11, 20, 45))  # 22:00 - 15 - 60 = 20:45
        self.assertTrue(any("60 min" in e["corpo"] for e in enviados if e["titulo"] == "Hora de se arrumar"), enviados)

    def test_marca_o_tick_do_agendador(self):
        app._AGENDADOR.update(iniciado=True, ultimo_tick=None)
        self._rodar(datetime(2026, 10, 11, 12, 0))
        self.assertIsNotNone(app._AGENDADOR["ultimo_tick"])


class RotasEPayloadTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.client.post("/login", json={"pin": PIN_TESTE})

    def test_status_mostra_agendador_parado(self):
        app._AGENDADOR.update(iniciado=False, ultimo_tick=None)
        corpo = self.client.get("/api/push/status").get_json()
        self.assertEqual(corpo["agendador"]["ligado"], False)
        app._AGENDADOR.update(iniciado=True, ultimo_tick=datetime.now())
        self.assertEqual(self.client.get("/api/push/status").get_json()["agendador"]["ligado"], True)

    def test_payload_leva_url_e_tag_e_ttl(self):
        with patch("push_client.webpush") as wp:
            self.assertTrue(push_client.enviar({"endpoint": "x"}, "Oi", "corpo", url="/?aba=tarefas", tag="t-1"))
        dados = json.loads(wp.call_args.kwargs["data"])
        self.assertEqual(dados, {"titulo": "Oi", "corpo": "corpo", "url": "/?aba=tarefas", "tag": "t-1"})
        self.assertGreater(wp.call_args.kwargs["ttl"], 0)

    def test_url_do_aviso(self):
        self.assertEqual(app._url_do_aviso("tarefa_horario"), "/?aba=tarefas")
        self.assertEqual(app._url_do_aviso("conta_a_vencer"), "/?aba=construtora")
        self.assertEqual(app._url_do_aviso("voo_sair"), "/?aba=aviacao")
        self.assertEqual(app._url_do_aviso("qualquer_coisa"), "/")

    def test_contexto_do_chat_tem_o_tempo_de_se_arrumar(self):
        self.assertIn("se arrumar pra sair (date, festa, jantar) = 40 min", app._contexto_chat(self.conn))
        db.definir_configuracao(self.conn, "tempo_se_arrumar_min", "lixo")
        self.assertIn("= 40 min", app._contexto_chat(self.conn))


if __name__ == "__main__":
    unittest.main()
