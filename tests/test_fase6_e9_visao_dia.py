"""Fase 6, Grupo E5 (US-E9): visao do dia (aba Hoje, abaixo do chat).

Segue o padrao de tests/test_pin_inicial.py: db.DB_PATH pra um arquivo
temporario + db.garantir_banco_nao_producao() ANTES de importar app. CalDAV
e SEMPRE mockado (patch em caldav_client.configurado/eventos_do_dia) -
nenhum teste chama iCloud de verdade."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db
import vida

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class FormatarEmQuantoTempoTestCase(unittest.TestCase):
    def test_minutos(self):
        agora = datetime(2026, 9, 23, 10, 0)
        alvo = agora + timedelta(minutes=19)
        self.assertEqual(vida.formatar_em_quanto_tempo(alvo, agora), "em 19 min")

    def test_horas_exatas(self):
        agora = datetime(2026, 9, 23, 10, 0)
        alvo = agora + timedelta(hours=2)
        self.assertEqual(vida.formatar_em_quanto_tempo(alvo, agora), "em 2h")

    def test_horas_e_minutos(self):
        agora = datetime(2026, 9, 23, 10, 0)
        alvo = agora + timedelta(hours=2, minutes=5)
        self.assertEqual(vida.formatar_em_quanto_tempo(alvo, agora), "em 2h5min")

    def test_no_passado_e_atrasada(self):
        agora = datetime(2026, 9, 23, 10, 0)
        alvo = agora - timedelta(minutes=5)
        self.assertEqual(vida.formatar_em_quanto_tempo(alvo, agora), "atrasada")

    def test_agora_mesmo_e_atrasada(self):
        agora = datetime(2026, 9, 23, 10, 0)
        self.assertEqual(vida.formatar_em_quanto_tempo(agora, agora), "atrasada")


class ItemConcluivelTestCase(unittest.TestCase):
    def test_tarefa_com_id_e_concluivel(self):
        self.assertTrue(app._item_concluivel({"origem": "tarefa", "id": 1}))

    def test_habito_com_id_e_concluivel(self):
        self.assertTrue(app._item_concluivel({"origem": "habito", "id": 1}))

    def test_calendario_nunca_e_concluivel(self):
        self.assertFalse(app._item_concluivel({"origem": "calendario", "id": None}))

    def test_sem_id_nao_e_concluivel(self):
        self.assertFalse(app._item_concluivel({"origem": "tarefa", "id": None}))


class StatusDoDiaTestCase(unittest.TestCase):
    def test_tudo_sob_controle_sem_itens(self):
        self.assertEqual(app._status_do_dia([], datetime(2026, 9, 23, 10, 0)), "tudo sob controle")

    def test_tudo_sob_controle_com_item_futuro(self):
        itens = [{"origem": "tarefa", "id": 1, "dia_inteiro": False, "concluido": False, "fim": "2026-09-23T14:00:00"}]
        self.assertEqual(app._status_do_dia(itens, datetime(2026, 9, 23, 10, 0)), "tudo sob controle")

    def test_um_item_passado_sem_confirmar(self):
        itens = [{"origem": "tarefa", "id": 1, "dia_inteiro": False, "concluido": False, "fim": "2026-09-23T08:00:00"}]
        self.assertEqual(
            app._status_do_dia(itens, datetime(2026, 9, 23, 10, 0)), "1 item passou do horario sem confirmar"
        )

    def test_varios_itens_passados(self):
        itens = [
            {"origem": "tarefa", "id": 1, "dia_inteiro": False, "concluido": False, "fim": "2026-09-23T08:00:00"},
            {"origem": "habito", "id": 2, "dia_inteiro": False, "concluido": False, "fim": "2026-09-23T09:00:00"},
        ]
        self.assertEqual(
            app._status_do_dia(itens, datetime(2026, 9, 23, 10, 0)), "2 itens passaram do horario sem confirmar"
        )

    def test_calendario_passado_nunca_conta(self):
        itens = [{"origem": "calendario", "id": None, "dia_inteiro": False, "concluido": False, "fim": "2026-09-23T08:00:00"}]
        self.assertEqual(app._status_do_dia(itens, datetime(2026, 9, 23, 10, 0)), "tudo sob controle")

    def test_concluido_nunca_conta(self):
        itens = [{"origem": "tarefa", "id": 1, "dia_inteiro": False, "concluido": True, "fim": "2026-09-23T08:00:00"}]
        self.assertEqual(app._status_do_dia(itens, datetime(2026, 9, 23, 10, 0)), "tudo sob controle")


class ProximoItemEmFocoTestCase(unittest.TestCase):
    def test_sem_itens_e_none(self):
        self.assertIsNone(app._proximo_item_em_foco([], datetime(2026, 9, 23, 10, 0)))

    def test_escolhe_o_mais_proximo_no_futuro(self):
        itens = [
            {"origem": "tarefa", "id": 1, "titulo": "Tarde", "dia_inteiro": False, "concluido": False, "inicio": "2026-09-23T18:00:00"},
            {"origem": "habito", "id": 2, "titulo": "Cedo", "dia_inteiro": False, "concluido": False, "inicio": "2026-09-23T10:19:00"},
        ]
        resultado = app._proximo_item_em_foco(itens, datetime(2026, 9, 23, 10, 0))
        self.assertEqual(resultado["titulo"], "Cedo")
        self.assertEqual(resultado["em_texto"], "em 19 min")
        self.assertEqual(resultado["origem"], "habito")
        self.assertEqual(resultado["id"], 2)

    def test_sem_futuro_pega_o_mais_atrasado_recente(self):
        itens = [
            {"origem": "tarefa", "id": 1, "titulo": "Bem atrasada", "dia_inteiro": False, "concluido": False, "inicio": "2026-09-23T06:00:00"},
            {"origem": "tarefa", "id": 2, "titulo": "Atrasada", "dia_inteiro": False, "concluido": False, "inicio": "2026-09-23T09:00:00"},
        ]
        resultado = app._proximo_item_em_foco(itens, datetime(2026, 9, 23, 10, 0))
        self.assertEqual(resultado["titulo"], "Atrasada")
        self.assertEqual(resultado["em_texto"], "atrasada")

    def test_ignora_concluidos_e_calendario(self):
        itens = [
            {"origem": "tarefa", "id": 1, "titulo": "Feita", "dia_inteiro": False, "concluido": True, "inicio": "2026-09-23T10:05:00"},
            {"origem": "calendario", "id": None, "titulo": "Reuniao", "dia_inteiro": False, "concluido": False, "inicio": "2026-09-23T10:10:00"},
        ]
        self.assertIsNone(app._proximo_item_em_foco(itens, datetime(2026, 9, 23, 10, 0)))


class Fase6E9RotasTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200
        self._caldav_patch = patch("caldav_client.configurado", return_value=False)
        self._caldav_patch.start()
        self.addCleanup(self._caldav_patch.stop)

    def tearDown(self):
        self.conn.close()

    def test_visao_dia_hoje_vazia(self):
        res = self.client.get("/api/visao-dia/hoje")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "tudo sob controle")
        self.assertIsNone(data["em_foco"])
        self.assertEqual(data["total_itens"], 0)
        self.assertEqual(data["total_concluidas"], 0)
        self.assertEqual(data["timeline"], [])

    def test_visao_dia_junta_tarefa_habito_e_calendario(self):
        hoje = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Ligar pro cliente', ?, '15:00')", (hoje,)
        )
        self.conn.commit()
        db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia",
            return_value=[
                {
                    "titulo": "Reuniao de obra",
                    "inicio": f"{hoje}T09:00:00",
                    "fim": f"{hoje}T10:00:00",
                    "dia_inteiro": False,
                }
            ],
        ):
            res = self.client.get("/api/visao-dia/hoje")
        data = res.get_json()
        self.assertEqual(data["total_itens"], 3)
        origens = {item["origem"] for item in data["timeline"]}
        self.assertEqual(origens, {"tarefa", "habito", "calendario"})
        # ordenado por horario: habito 08:00, calendario 09:00, tarefa 15:00
        self.assertEqual([i["origem"] for i in data["timeline"]], ["habito", "calendario", "tarefa"])

    def test_habito_sem_horario_fica_fora_da_linha_do_tempo(self):
        db.create_habito(self.conn, "Ler", None, "diario", None, None, None)
        res = self.client.get("/api/visao-dia/hoje")
        self.assertEqual(res.get_json()["total_itens"], 0)

    def test_concluir_tarefa_via_em_foco_some_da_pendencia(self):
        hoje = date.today().isoformat()
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora) VALUES ('Enviar orcamento', ?, '23:59')", (hoje,)
        )
        self.conn.commit()
        tarefa_id = cur.lastrowid

        antes = self.client.get("/api/visao-dia/hoje").get_json()
        self.assertEqual(antes["total_concluidas"], 0)
        self.assertIsNotNone(antes["em_foco"])
        self.assertEqual(antes["em_foco"]["origem"], "tarefa")

        r = self.client.post(f"/api/tasks/{tarefa_id}/complete")
        self.assertEqual(r.status_code, 200)

        depois = self.client.get("/api/visao-dia/hoje").get_json()
        self.assertEqual(depois["total_concluidas"], 1)
        self.assertIsNone(depois["em_foco"])

    def test_concluir_habito_via_marcar_reflete_na_visao_do_dia(self):
        habito_id = db.create_habito(self.conn, "Meditar", None, "diario", None, None, "08:00")
        antes = self.client.get("/api/visao-dia/hoje").get_json()
        self.assertEqual(antes["timeline"][0]["concluido"], False)

        r = self.client.post(f"/api/habitos/{habito_id}/marcar")
        self.assertEqual(r.status_code, 200)

        depois = self.client.get("/api/visao-dia/hoje").get_json()
        self.assertEqual(depois["timeline"][0]["concluido"], True)
        self.assertEqual(depois["total_concluidas"], 1)

    def test_visao_dia_periodo_semana_tem_7_dias(self):
        res = self.client.get("/api/visao-dia/periodo?tipo=semana")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["tipo"], "semana")
        self.assertEqual(len(data["dias"]), 7)

    def test_visao_dia_periodo_mes_tem_todos_os_dias_do_mes(self):
        res = self.client.get("/api/visao-dia/periodo?tipo=mes")
        data = res.get_json()
        self.assertEqual(data["tipo"], "mes")
        hoje = date.today()
        ultimo_dia = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        self.assertEqual(len(data["dias"]), ultimo_dia.day)

    def test_visao_dia_periodo_tipo_invalido_cai_pra_semana(self):
        res = self.client.get("/api/visao-dia/periodo?tipo=ano")
        data = res.get_json()
        self.assertEqual(data["tipo"], "semana")
        self.assertEqual(len(data["dias"]), 7)

    def test_visao_dia_periodo_conta_tarefa_no_dia_certo(self):
        daqui_3_dias = (date.today() + timedelta(days=3)).isoformat()
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Revisar contrato', ?)", (daqui_3_dias,))
        self.conn.commit()
        data = self.client.get("/api/visao-dia/periodo?tipo=semana").get_json()
        dia = next((d for d in data["dias"] if d["data"] == daqui_3_dias), None)
        if dia is not None:  # so cai na semana atual se a data ainda estiver dentro dela
            self.assertGreaterEqual(dia["total"], 1)


if __name__ == "__main__":
    unittest.main()
