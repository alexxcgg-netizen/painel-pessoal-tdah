"""Avisos importantes que insistem (2026-10-13): o Alex reclamou que o aviso vai uma vez so e,
se ele nao ve, passa em branco. Tarefa com hora, compromisso, hora de sair, voo e conta
repetem (mesma tag) ate ele tocar na notificacao ou concluir a tarefa; o resto continua indo
uma vez so. Nenhuma rede: push_client.enviar e sempre mockado."""
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
DIA = "2026-10-11"


class RegraPuraTestCase(unittest.TestCase):
    def _linha(self, tipo="tarefa_horario", enviado="2026-10-11T14:00:00", tentativas=1, data=DIA):
        return {"id": 1, "tipo": tipo, "data": data, "enviado_em": enviado, "tentativas": tentativas}

    def test_repete_nos_minutos_certos(self):
        a = self._linha()
        self.assertEqual(notificacoes.repeticoes_devidas([a], datetime(2026, 10, 11, 14, 9)), ([], []))
        self.assertEqual(notificacoes.repeticoes_devidas([a], datetime(2026, 10, 11, 14, 10)), ([a], []))
        b = self._linha(tentativas=2)  # ja repetiu 1x: a proxima e aos 30 min do 1o envio
        self.assertEqual(notificacoes.repeticoes_devidas([b], datetime(2026, 10, 11, 14, 29)), ([], []))
        self.assertEqual(notificacoes.repeticoes_devidas([b], datetime(2026, 10, 11, 14, 30)), ([b], []))

    def test_encerra_quando_acabou_outro_dia_ou_tipo_que_nao_insiste(self):
        acabou = self._linha(tentativas=3)
        ontem = self._linha(data="2026-10-10")
        outro = self._linha(tipo="meta_fora_do_ritmo")
        quebrado = self._linha(enviado="lixo")
        repetir, encerrar = notificacoes.repeticoes_devidas([acabou, ontem, outro, quebrado], datetime(2026, 10, 11, 20, 0))
        self.assertEqual(repetir, [])
        self.assertEqual(encerrar, [acabou, ontem, outro, quebrado])

    def test_texto_da_repeticao(self):
        self.assertEqual(notificacoes.texto_repeticao("tarefa_horario", "Tá na hora", "corpo", 1),
                         ("De novo · Tá na hora", "corpo"))
        self.assertEqual(notificacoes.texto_repeticao("tarefa_horario", "Tá na hora", "corpo", 2),
                         ("Última chamada · Tá na hora", "corpo"))
        self.assertEqual(notificacoes.texto_repeticao("hora_de_sair", "Hora de sair", "c", 1)[0],
                         "Última chamada · Hora de sair")

    def test_nao_insiste_em_aviso_de_rotina(self):
        for tipo in ("meta_fora_do_ritmo", "tarefas_atrasadas", "tarefa_parada", "hora_de_dormir", "tarefa_preparo"):
            self.assertNotIn(tipo, notificacoes.INSISTENCIA)


class InsistenciaNoTickTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN_TESTE, PIN_TESTE)
        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        self.conn.commit()
        self.client = app.app.test_client()
        self.client.post("/login", json={"pin": PIN_TESTE})

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora):
        cur = self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES (?, ?, ?)", (titulo, DIA, hora))
        self.conn.commit()
        return cur.lastrowid

    def _rodar(self, agora):
        enviados = []

        def falso(sub, titulo, corpo, url="", tag="", **_):
            enviados.append({"titulo": titulo, "corpo": corpo, "url": url, "tag": tag})
            return True

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=falso), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._eventos_de_hoje_com_seguranca", return_value=[]), \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("db.datetime", _Agora), \
                patch("app.date", type("D", (), {"today": staticmethod(lambda: agora.date()),
                                                   "fromisoformat": staticmethod(datetime.fromisoformat)})):
            app.verificar_e_notificar()
        return [e for e in enviados if e["tag"].startswith("tarefa_horario-")]

    def test_tarefa_com_hora_repete_ate_a_ultima_chamada_e_para(self):
        tid = self.tarefa("Ligar pro instrutor", "14:00")
        primeiro = self._rodar(datetime(2026, 10, 11, 14, 0))
        self.assertEqual(len(primeiro), 1)
        self.assertEqual(primeiro[0]["titulo"], "Tá na hora")
        self.assertIn("Ligar pro instrutor", primeiro[0]["corpo"])
        self.assertEqual(primeiro[0]["url"], f"/?aba=tarefas&tarefa={tid}")
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 14, 5)), [])
        segundo = self._rodar(datetime(2026, 10, 11, 14, 10))
        self.assertEqual([e["titulo"] for e in segundo], ["De novo · Tá na hora"])
        self.assertEqual(segundo[0]["tag"], f"tarefa_horario-{tid}")  # substitui a anterior no iPhone
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 14, 20)), [])
        terceiro = self._rodar(datetime(2026, 10, 11, 14, 30))
        self.assertEqual([e["titulo"] for e in terceiro], ["Última chamada · Tá na hora"])
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 15, 0)), [])
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 16, 0)), [])

    def test_tocar_na_notificacao_para_de_insistir(self):
        tid = self.tarefa("Academia", "18:00")
        self._rodar(datetime(2026, 10, 11, 18, 0))
        r = self.client.post("/api/push/aberto", json={"tag": f"tarefa_horario-{tid}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["parou"], 1)
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 18, 10)), [])
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 18, 30)), [])

    def test_concluir_a_tarefa_para_de_insistir(self):
        tid = self.tarefa("Remédio", "09:00")
        self._rodar(datetime(2026, 10, 11, 9, 0))
        self.conn.execute("UPDATE tasks SET completed_at = '2026-10-11 09:03:00' WHERE id = ?", (tid,))
        self.conn.commit()
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 9, 10)), [])
        linha = self.conn.execute("SELECT encerrado_em FROM avisos_insistentes WHERE referencia_id = ?", (tid,)).fetchone()
        self.assertIsNotNone(linha["encerrado_em"])

    def test_abrir_o_app_conta_como_visto_e_para_de_insistir(self):
        # 2026-10-16: so o toque na notificacao parava o aviso; quem abre o app sozinho continuava recebendo
        self.tarefa("Academia", "18:00")
        self.tarefa("Dentista", "18:05")
        self._rodar(datetime(2026, 10, 11, 18, 5))
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 18, 15)) != [], True)  # sem abrir: repete
        with patch("db.datetime") as relogio:
            relogio.now.return_value = datetime(2026, 10, 11, 18, 16)
            r = self.client.post("/api/push/visto")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["parou"], 2)
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 18, 30)), [])
        self.assertEqual(self._rodar(datetime(2026, 10, 11, 18, 40)), [])
        # nao mexe em aviso de outro dia nem em aviso que ja foi encerrado
        self.assertEqual(self.client.post("/api/push/visto").get_json(), {"ok": True, "parou": 0, "de_onde_parei": False})

    def test_rota_aberto_valida_a_tag(self):
        for corpo in ({}, {"tag": ""}, {"tag": 5}, {"tag": "x" * 200}):
            self.assertEqual(self.client.post("/api/push/aberto", json=corpo).status_code, 400, corpo)
        r = self.client.post("/api/push/aberto", json={"tag": "nao-existe-1"})
        self.assertEqual(r.get_json(), {"ok": True, "parou": 0})


if __name__ == "__main__":
    unittest.main()
