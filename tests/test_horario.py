"""Leva 22/10 (horario.py): a IA propoe o horario - agenda + folga + costume + sono."""
import unittest
from datetime import date, datetime, time
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import db
import horario

HOJE = date(2026, 10, 22)


class EscolherTestCase(unittest.TestCase):
    def test_folga_depois_do_compromisso_e_maior_espaco(self):
        e = horario.escolher([("08:00", "09:00", "Reunião"), ("12:00", "18:00", "Obra")], "06:00", "22:00", 60)
        self.assertEqual((e["inicio"], e["fim"], e["depois_de"]), ("18:15", "19:15", "Obra"))
        self.assertEqual(e["janela"], {"inicio": "18:15", "fim": "22:00"})

    def test_comeco_do_dia_nao_ganha_folga_e_sem_espaco_e_none(self):
        self.assertEqual(horario.escolher([], "20:15", "22:00", 45)["inicio"], "20:15")
        self.assertIsNone(horario.escolher([("06:00", "21:30", "Trabalho")], "06:00", "22:00", 30))  # 21:45 nao cabe

    def test_costume_puxa_pra_perto_da_hora_de_sempre(self):
        e = horario.escolher([("08:00", "09:00", "Reunião")], "06:00", "22:00", 60, costume="18:00")
        self.assertEqual((e["inicio"], e["no_costume"]), ("18:00", True))
        # costume dentro de um compromisso: vai pro espaco mais perto (antes ou depois)
        e = horario.escolher([("17:00", "19:00", "Obra")], "06:00", "22:00", 60, costume="18:00")
        self.assertEqual((e["inicio"], e["no_costume"]), ("19:15", False))  # 75 min depois ganha de 120 antes


class DoBancoTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_costume_precisa_de_2_vezes_e_usa_a_mediana(self):
        for h in ("18:00", "18:30"):
            self.conn.execute("INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('Treino de perna', '2026-10-10', ?, '2026-10-10')", (h,))
        self.assertIsNone(horario.hora_de_costume(self.conn, "estudar", HOJE))
        self.assertEqual(horario.hora_de_costume(self.conn, "treino", HOJE), "18:15")

    def test_sono_curto_pelo_relogio_ou_pelo_checkin(self):
        self.assertIsNone(horario.sono_curto(self.conn, HOJE))
        self.conn.execute("INSERT INTO checkins (data, sono) VALUES (?, 1)", (HOJE.isoformat(),))
        self.assertEqual(horario.sono_curto(self.conn, HOJE), 0.0)

    def test_tarefa_com_hora_e_voo_ocupam_o_dia(self):
        self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Banco', ?, '10:00')", (HOJE.isoformat(),))
        self.conn.execute("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '14:00')", (HOJE.isoformat(),))
        oc = horario.ocupados_do_dia(self.conn, HOJE, [])
        self.assertIn(("10:00", "10:30", "Banco"), oc)
        self.assertIn(("13:30", "16:30", "voo"), oc)  # briefing 30 + 2 h + debriefing 30

    def test_tool_dormiu_pouco_deixa_a_noite_livre_e_aceita_amanha(self):
        import app

        self.conn.execute("INSERT INTO checkins (data, sono) VALUES (?, 1)", (HOJE.isoformat(),))
        self.conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES ('Obra', ?, '07:00')", (HOJE.isoformat(),))
        self.conn.commit()
        with patch("app._agora", return_value=datetime.combine(HOJE, time(20, 0))), \
                patch("caldav_client.configurado", return_value=False):
            hoje = app._sugerir_horario_livre(self.conn, {"duracao_minutos": 60, "titulo": "estudar"})
            amanha = app._sugerir_horario_livre(self.conn, {"duracao_minutos": 60, "titulo": "estudar", "dia": "2026-10-23"})
        self.assertEqual((hoje["inicio"], hoje["fim"]), ("20:00", "21:00"))  # fim 21h em vez de 22h
        self.assertIn("deixei a noite livre", hoje["_efeito"]["porque"])
        self.assertEqual((amanha["dia"], amanha["inicio"]), ("2026-10-23", "06:00"))
        self.assertTrue(amanha["_efeito"]["porque"].startswith("Amanhã"))


if __name__ == "__main__":
    unittest.main()
