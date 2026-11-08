"""Faixa P3 (briefing da manha/noite) - testes de assistente/briefing.py:
montagem pura, com dado sintetico e sem nenhuma chamada de rede real (a
integracao com o financeiro-construtora e sempre mockada; iCloud/CalDAV nunca
e configurado no ambiente de teste, entao os helpers reaproveitados de
app.py ja falham fechado sozinhos)."""

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

from assistente import briefing  # noqa: E402


class HorariosEFlagsTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_horario_padrao(self):
        self.assertEqual(briefing.horario_manha(self.conn), "07:30")
        self.assertEqual(briefing.horario_noite(self.conn), "21:00")

    def test_definir_horario_persiste(self):
        briefing.definir_horario_manha(self.conn, "08:15")
        briefing.definir_horario_noite(self.conn, "22:45")
        self.assertEqual(briefing.horario_manha(self.conn), "08:15")
        self.assertEqual(briefing.horario_noite(self.conn), "22:45")

    def test_horario_valido(self):
        for valor in ("00:00", "07:30", "23:59", "21:00"):
            self.assertTrue(briefing.horario_valido(valor), valor)

    def test_horario_invalido(self):
        for valor in ("24:00", "7:30", "07:60", "abc", "", None, "07:3", 123):
            self.assertFalse(briefing.horario_valido(valor), valor)

    def test_ativo_padrao_ligado(self):
        self.assertTrue(briefing.ativo(self.conn))

    def test_ativo_desligado_explicito(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_ATIVO, "0")
        self.assertFalse(briefing.ativo(self.conn))

    def test_reescrever_ia_padrao_desligado(self):
        self.assertFalse(briefing.reescrever_ia_ativo(self.conn))

    def test_reescrever_ia_ligado_explicito(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_REESCREVER_IA, "1")
        self.assertTrue(briefing.reescrever_ia_ativo(self.conn))

    def test_humor_da_resposta_mapeia_opcoes(self):
        self.assertEqual(briefing.humor_da_resposta("Otimo"), 5)
        self.assertEqual(briefing.humor_da_resposta("bom"), 4)
        self.assertEqual(briefing.humor_da_resposta("NEUTRO"), 3)
        self.assertEqual(briefing.humor_da_resposta("Dificil"), 2)
        self.assertEqual(briefing.humor_da_resposta("pessimo"), 1)

    def test_humor_da_resposta_invalida(self):
        self.assertIsNone(briefing.humor_da_resposta("adiar"))
        self.assertIsNone(briefing.humor_da_resposta(""))
        self.assertIsNone(briefing.humor_da_resposta(None))


class MontarManhaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.hoje = date(2026, 6, 15)

    def tearDown(self):
        self.conn.close()

    def test_dia_vazio(self):
        with patch.object(app, "_eventos_de_hoje_com_seguranca", return_value=[]), patch.object(
            app, "_tarefas_pendentes_sem_horario_hoje", return_value=[]
        ), patch.object(app, "_buscar_contas_a_vencer_construtora", return_value=None):
            dados = briefing.montar_manha(self.conn, self.hoje)

        self.assertEqual(dados["tipo"], "manha")
        self.assertEqual(dados["data"], "2026-06-15")
        self.assertEqual(dados["titulo"], "Bom dia")
        self.assertIsNone(dados["opcoes"])
        self.assertIn("Sem compromisso marcado na agenda.", dados["corpo"])
        self.assertIn("Nenhuma tarefa pendente.", dados["corpo"])
        self.assertEqual(dados["agenda"], [])
        self.assertEqual(dados["tarefas"], [])
        self.assertEqual(dados["habitos"], [])
        self.assertEqual(dados["contas"], [])
        self.assertIsNone(dados["conta_construtora"])
        self.assertNotIn("Habitos", dados["corpo"])
        self.assertNotIn("Contas", dados["corpo"])

    def test_dia_cheio(self):
        eventos_fake = [{"titulo": "Reuniao", "inicio": "2026-06-15T09:00:00"}]
        tarefas_fake = [{"title": "Comprar leite"}, {"title": "Estudar"}]
        habito_id = self.conn.execute(
            "INSERT INTO habitos (nome, frequencia_tipo) VALUES ('Beber agua', 'diario')"
        ).lastrowid
        self.conn.commit()
        conta_id = db.create_conta_pessoal(self.conn, "Internet", 18, 120.0)
        self.conn.commit()

        contas_construtora_fake = {
            "status": "ok",
            "contas": [
                {
                    "fornecedor": "Fornecedor XPTO",
                    "valor": 15000.0,
                    "dias_ate_vencer": 3,
                }
            ],
        }

        with patch.object(
            app, "_eventos_de_hoje_com_seguranca", return_value=eventos_fake
        ), patch.object(
            app, "_tarefas_pendentes_sem_horario_hoje", return_value=tarefas_fake
        ), patch.object(
            app, "_buscar_contas_a_vencer_construtora", return_value=contas_construtora_fake
        ):
            dados = briefing.montar_manha(self.conn, self.hoje)

        self.assertIn("1 compromisso na agenda: 09:00 Reuniao.", dados["corpo"])
        self.assertIn("2 tarefas pendentes: Comprar leite, Estudar.", dados["corpo"])
        self.assertIn("Hábitos de hoje: Beber agua.", dados["corpo"])
        self.assertIn("Internet vence em 3 dias", dados["corpo"])  # dia_vencimento 18, hoje dia 15
        self.assertIn("Fornecedor XPTO (construtora) vence em 3 dias", dados["corpo"])

        # Regra de ouro do financeiro-construtora: nunca valor da conta da
        # construtora no briefing - so nome e quando.
        self.assertNotIn("15000", dados["corpo"])
        self.assertIsNone(dados["conta_construtora"].get("valor"))
        self.assertNotIn("valor", dados["conta_construtora"])

        # Conta pessoal, ao contrario, pode mostrar valor normalmente.
        self.assertIn("R$ 120.00", dados["corpo"])

        self.assertTrue(habito_id and conta_id)

    def test_construtora_nao_configurada_nao_aparece(self):
        with patch.object(app, "_eventos_de_hoje_com_seguranca", return_value=[]), patch.object(
            app, "_tarefas_pendentes_sem_horario_hoje", return_value=[]
        ), patch.object(app, "_buscar_contas_a_vencer_construtora", return_value=None):
            dados = briefing.montar_manha(self.conn, self.hoje)
        self.assertIsNone(dados["conta_construtora"])
        self.assertNotIn("construtora", dados["corpo"])

    def test_conta_pessoal_paga_nao_aparece(self):
        conta_id = db.create_conta_pessoal(self.conn, "Agua", 20, 80.0)
        self.conn.commit()
        venc = app._contas_pessoais_com_status(self.conn, self.hoje)[0]["proximo_vencimento"]
        db.marcar_conta_paga(self.conn, conta_id, venc)
        self.conn.commit()

        with patch.object(app, "_eventos_de_hoje_com_seguranca", return_value=[]), patch.object(
            app, "_tarefas_pendentes_sem_horario_hoje", return_value=[]
        ), patch.object(app, "_buscar_contas_a_vencer_construtora", return_value=None):
            dados = briefing.montar_manha(self.conn, self.hoje)
        self.assertEqual(dados["contas"], [])

    def test_conta_pessoal_fora_da_janela_nao_aparece(self):
        # dia_vencimento bem longe (mais de JANELA_CONTAS_DIAS a frente,
        # ainda dentro do mesmo mes pra manter a conta simples no teste).
        self.assertGreater(30 - self.hoje.day, briefing.JANELA_CONTAS_DIAS)
        db.create_conta_pessoal(self.conn, "Longe", 30, 50.0)
        self.conn.commit()

        with patch.object(app, "_eventos_de_hoje_com_seguranca", return_value=[]), patch.object(
            app, "_tarefas_pendentes_sem_horario_hoje", return_value=[]
        ), patch.object(app, "_buscar_contas_a_vencer_construtora", return_value=None):
            dados = briefing.montar_manha(self.conn, self.hoje)
        nomes = [c["nome"] for c in dados["contas"]]
        self.assertNotIn("Longe", nomes)


class MontarNoiteTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.hoje = date(2026, 6, 15)

    def tearDown(self):
        self.conn.close()

    def test_dia_vazio(self):
        dados = briefing.montar_noite(self.conn, self.hoje)
        self.assertEqual(dados["tipo"], "noite")
        self.assertEqual(dados["titulo"], "Fechando o dia")
        self.assertEqual(dados["concluidas"], 0)
        self.assertEqual(dados["pendentes"], [])
        self.assertEqual(dados["opcoes"], briefing.OPCOES_FECHAMENTO)
        self.assertIn("Nenhuma tarefa concluída hoje.", dados["corpo"])
        self.assertIn("Como foi o dia?", dados["corpo"])
        self.assertNotIn("passa pra amanha", dados["corpo"])

    def test_dia_cheio(self):
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
            ("Tarefa feita", self.hoje.isoformat(), f"{self.hoje.isoformat()} 10:00:00"),
        )
        self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
            ("Tarefa que ficou", self.hoje.isoformat()),
        )
        self.conn.commit()

        dados = briefing.montar_noite(self.conn, self.hoje)
        self.assertEqual(dados["concluidas"], 1)
        self.assertEqual(dados["pendentes"], ["Tarefa que ficou"])
        self.assertIn("1 tarefa concluída hoje.", dados["corpo"])
        self.assertIn("Ficou pendente: Tarefa que ficou.", dados["corpo"])
        self.assertIn("O que ficou passa pra amanhã.", dados["corpo"])
        self.assertIn("Como foi o dia?", dados["corpo"])


class ReescreverIaTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_flag_desligada_devolve_original(self):
        corpo = "texto original."
        self.assertEqual(briefing.reescrever_se_configurado(self.conn, corpo, "manha"), corpo)

    def test_flag_ligada_usa_resposta_da_ia(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_REESCREVER_IA, "1")
        corpo = "texto original."

        class RespostaFalsa:
            ok = True
            texto = "texto reescrito."

        with patch("ia.core.chamar_ia", return_value=RespostaFalsa()) as mock_chamar:
            resultado = briefing.reescrever_se_configurado(self.conn, corpo, "manha")
        self.assertEqual(resultado, "texto reescrito.")
        mock_chamar.assert_called_once()
        self.assertEqual(mock_chamar.call_args.args[0], "reescrever_briefing")

    def test_flag_ligada_mas_ia_falha_devolve_original(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_REESCREVER_IA, "1")
        corpo = "texto original."

        class RespostaFalha:
            ok = False
            texto = None

        with patch("ia.core.chamar_ia", return_value=RespostaFalha()):
            resultado = briefing.reescrever_se_configurado(self.conn, corpo, "noite")
        self.assertEqual(resultado, corpo)

    def test_flag_ligada_mas_ia_levanta_excecao_devolve_original(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_REESCREVER_IA, "1")
        corpo = "texto original."

        with patch("ia.core.chamar_ia", side_effect=RuntimeError("boom")):
            resultado = briefing.reescrever_se_configurado(self.conn, corpo, "manha")
        self.assertEqual(resultado, corpo)


if __name__ == "__main__":
    unittest.main()
