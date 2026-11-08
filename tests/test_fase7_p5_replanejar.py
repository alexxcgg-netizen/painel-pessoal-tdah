"""Fase 7 - faixa P5 (replanejar o dia).

Cobre `assistente/replanejar.py` (logica pura de coleta/persistencia),
`classificador_local/regras/p5_replanejar.py` (frase -> card) e
`assistente/gatilhos/p5_replanejar.py` (sugestao automatica das 14h).

`claude_client.plano_do_dia` e' sempre mockado - nenhuma chamada real de
API, nenhum dado real do Alex (fixtures sinteticas em pt-BR)."""

import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402


def fake_usage(model="claude-sonnet-5", cost=0.002):
    return {"model": model, "input_tokens": 120, "output_tokens": 40, "cost_usd": cost}


class _BaseP5TestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()

    def _criar_tarefa(self, titulo, due_date=None, hora=None, completed_at=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)",
            (titulo, due_date, hora, completed_at),
        )
        self.conn.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# assistente/replanejar.py - logica pura
# ---------------------------------------------------------------------------


class ColetarRestanteDoDiaTestCase(_BaseP5TestCase):
    def test_inclui_tarefa_de_hoje_sem_hora(self):
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("revisar contrato", due_date=hoje.isoformat())
        tarefas = replanejar.tarefas_pendentes_hoje(self.conn, hoje)
        self.assertEqual([t["titulo"] for t in tarefas], ["revisar contrato"])

    def test_inclui_tarefa_atrasada_de_hoje_com_hora_ja_passada(self):
        """'atrasei'/'perdi a manha': a tarefa das 09h que nao foi feita e
        agora sao 14h continua aparecendo (ainda precisa ser reencaixada
        no resto do dia)."""
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("ligar pro dentista", due_date=hoje.isoformat(), hora="09:00")
        tarefas = replanejar.tarefas_pendentes_hoje(self.conn, hoje)
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0]["hora"], "09:00")

    def test_ignora_tarefa_concluida(self):
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("ja fiz isso", due_date=hoje.isoformat(), completed_at="2026-09-24 08:00:00")
        tarefas = replanejar.tarefas_pendentes_hoje(self.conn, hoje)
        self.assertEqual(tarefas, [])

    def test_ignora_tarefa_de_outro_dia(self):
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("semana que vem", due_date="2026-10-01")
        tarefas = replanejar.tarefas_pendentes_hoje(self.conn, hoje)
        self.assertEqual(tarefas, [])

    def test_ordena_por_hora_sem_hora_por_ultimo(self):
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("sem hora", due_date=hoje.isoformat())
        self._criar_tarefa("tarde", due_date=hoje.isoformat(), hora="16:00")
        self._criar_tarefa("manha", due_date=hoje.isoformat(), hora="09:00")
        tarefas = replanejar.tarefas_pendentes_hoje(self.conn, hoje)
        self.assertEqual([t["titulo"] for t in tarefas], ["manha", "tarde", "sem hora"])

    def test_agenda_restante_filtra_evento_ja_comecado(self):
        import assistente.replanejar as replanejar

        agora = datetime(2026, 9, 24, 14, 0)
        eventos_fake = [
            {"titulo": "reuniao de manha", "inicio": "2026-09-24T09:00:00", "dia_inteiro": False},
            {"titulo": "call de tarde", "inicio": "2026-09-24T16:00:00", "dia_inteiro": False},
            {"titulo": "aniversario", "inicio": "2026-09-24T00:00:00", "dia_inteiro": True},
        ]
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos_fake
        ):
            restante = replanejar.agenda_restante_hoje(self.conn, agora)
        titulos = [e["titulo"] for e in restante]
        self.assertIn("call de tarde", titulos)
        self.assertIn("aniversario", titulos)
        self.assertNotIn("reuniao de manha", titulos)

    def test_agenda_restante_nao_quebra_se_icloud_falhar(self):
        import assistente.replanejar as replanejar

        agora = datetime(2026, 9, 24, 14, 0)
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", side_effect=RuntimeError("icloud fora do ar")
        ):
            restante = replanejar.agenda_restante_hoje(self.conn, agora)
        self.assertEqual(restante, [])

    def test_agenda_restante_sem_icloud_configurado(self):
        import assistente.replanejar as replanejar

        agora = datetime(2026, 9, 24, 14, 0)
        with patch("caldav_client.configurado", return_value=False):
            restante = replanejar.agenda_restante_hoje(self.conn, agora)
        self.assertEqual(restante, [])


class ProporPlanoTestCase(_BaseP5TestCase):
    def test_propor_plano_chama_ia_com_tarefas_e_eventos_e_nao_grava_nada(self):
        import assistente.replanejar as replanejar

        hoje = date(2026, 9, 24)
        self._criar_tarefa("estudar meteorologia", due_date=hoje.isoformat())
        agora = datetime(2026, 9, 24, 14, 5)

        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("1. Faca algo.", fake_usage())
        ) as mock_plano:
            proposta = replanejar.propor_plano(self.conn, agora)

        self.assertEqual(proposta["plano_texto"], "1. Faca algo.")
        args = mock_plano.call_args[0]
        self.assertEqual(args[0], ["estudar meteorologia"])
        self.assertEqual(args[1], [])
        # nada foi aplicado ainda (so propos)
        self.assertIsNone(replanejar.ordem_do_dia(self.conn, "2026-09-24"))

    def test_propor_plano_registra_uso_de_ia(self):
        import assistente.replanejar as replanejar

        agora = datetime(2026, 9, 24, 14, 5)
        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("plano", fake_usage(cost=0.0123))
        ):
            replanejar.propor_plano(self.conn, agora)

        gasto = self.conn.execute(
            "SELECT feature, cost_usd FROM api_usage WHERE feature = 'p5_replanejar'"
        ).fetchone()
        self.assertIsNotNone(gasto)
        self.assertAlmostEqual(gasto["cost_usd"], 0.0123)

    def test_propor_plano_bloqueado_pelo_teto(self):
        import assistente.replanejar as replanejar

        agora = datetime(2026, 9, 24, 14, 5)
        with patch("assistente.replanejar.teto_permite", return_value=False), patch(
            "claude_client.plano_do_dia"
        ) as mock_plano:
            with self.assertRaises(replanejar.TetoEstouradoError):
                replanejar.propor_plano(self.conn, agora)
        mock_plano.assert_not_called()


class AplicarDesfazerPlanoTestCase(_BaseP5TestCase):
    def test_aplicar_grava_e_ordem_do_dia_reflete(self):
        import assistente.replanejar as replanejar

        token = replanejar.aplicar_plano(self.conn, "2026-09-24", "1. Faca X.")
        self.assertTrue(token)
        ordem = replanejar.ordem_do_dia(self.conn, "2026-09-24")
        self.assertEqual(ordem["plano_texto"], "1. Faca X.")

    def test_desfazer_restaura_estado_anterior_vazio(self):
        import assistente.replanejar as replanejar

        token = replanejar.aplicar_plano(self.conn, "2026-09-24", "1. Faca X.")
        ok = replanejar.desfazer_plano(self.conn, token)
        self.assertTrue(ok)
        self.assertIsNone(replanejar.ordem_do_dia(self.conn, "2026-09-24"))

    def test_desfazer_restaura_plano_anterior(self):
        import assistente.replanejar as replanejar

        replanejar.aplicar_plano(self.conn, "2026-09-24", "plano velho")
        token_novo = replanejar.aplicar_plano(self.conn, "2026-09-24", "plano novo")
        replanejar.desfazer_plano(self.conn, token_novo)
        ordem = replanejar.ordem_do_dia(self.conn, "2026-09-24")
        self.assertEqual(ordem["plano_texto"], "plano velho")

    def test_desfazer_token_desconhecido_devolve_false(self):
        import assistente.replanejar as replanejar

        self.assertFalse(replanejar.desfazer_plano(self.conn, "token-que-nao-existe"))

    def test_desfazer_duas_vezes_a_segunda_devolve_false(self):
        import assistente.replanejar as replanejar

        token = replanejar.aplicar_plano(self.conn, "2026-09-24", "1. Faca X.")
        self.assertTrue(replanejar.desfazer_plano(self.conn, token))
        self.assertFalse(replanejar.desfazer_plano(self.conn, token))


# ---------------------------------------------------------------------------
# classificador_local/regras/p5_replanejar.py
# ---------------------------------------------------------------------------


class CasarTestCase(unittest.TestCase):
    def setUp(self):
        import classificador_local.regras.p5_replanejar as regra

        self.regra = regra

    def _reconhece(self, texto):
        self.assertIsNotNone(self.regra.casar(texto), f"deveria reconhecer: {texto!r}")

    def _nao_reconhece(self, texto):
        self.assertIsNone(self.regra.casar(texto), f"nao deveria reconhecer: {texto!r}")

    def test_frases_reconhecidas(self):
        for frase in [
            "replaneja meu dia",
            "replanejar o dia",
            "Replaneja meu dia por favor",
            "da pra replanejar a tarde?",
            "reorganiza o dia pra mim",
            "reordena o que resta do dia",
            "perdi a manhã",
            "perdi a manha inteira",
            "perdi o dia hoje",
            "perdi a hora e nao fiz nada",
            "baguncei nao, mas o dia bagunçou",
            "meu dia virou bagunça",
            "quero recomeçar o dia",
        ]:
            self._reconhece(frase)

    def test_frases_nao_reconhecidas(self):
        for frase in [
            "",
            "oi, tudo bem?",
            # 08/11: atraso fica com o chat (ATRASO DITO refaz a conta do compromisso)
            "atrasei",
            "atrasei uns 20 minutos",
            "me atrasei de novo",
            "to atrasado pra tudo",
            "gasto de 50 reais no mercado",
            "que horas sao agora",
            "cria uma tarefa pra amanha",
            "quanto eu gastei esse mes",
            "estou triste hoje",
        ]:
            self._nao_reconhece(frase)


class ExecutarRegraTestCase(_BaseP5TestCase):
    def _criar_tarefa(self, titulo, due_date=None, hora=None, completed_at=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES (?, ?, ?, ?)",
            (titulo, due_date, hora, completed_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def test_executar_devolve_card_no_contrato_com_acoes(self):
        import classificador_local.regras.p5_replanejar as regra

        hoje = date(2026, 9, 24)
        self._criar_tarefa("responder email", due_date=hoje.isoformat())
        agora = datetime(2026, 9, 24, 14, 30)

        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("1. Responda o email.", fake_usage())
        ):
            resultado = regra.executar(self.conn, {"agora": agora})

        self.assertIn("cards", resultado)
        self.assertIn("resumo_texto", resultado)
        self.assertIn("passos", resultado)
        self.assertEqual(len(resultado["cards"]), 1)
        card = resultado["cards"][0]
        self.assertEqual(card["type"], "replanejamento")
        self.assertEqual(card["data"]["plano_texto"], "1. Responda o email.")
        self.assertEqual(card["data"]["dia"], "2026-09-24")
        tipos_acao = {a["tipo"] for a in card["actions"]}
        self.assertEqual(tipos_acao, {"aplicar_replanejamento", "desfazer_replanejamento"})
        self.assertTrue(resultado["resumo_texto"])
        self.assertEqual(len(resultado["passos"]), 1)

    def test_executar_ja_aplica_a_ordem_do_dia(self):
        import assistente.replanejar as replanejar
        import classificador_local.regras.p5_replanejar as regra

        agora = datetime(2026, 9, 24, 14, 30)
        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("1. Faca X.", fake_usage())
        ):
            regra.executar(self.conn, {"agora": agora})

        ordem = replanejar.ordem_do_dia(self.conn, "2026-09-24")
        self.assertEqual(ordem["plano_texto"], "1. Faca X.")

    def test_executar_token_de_desfazer_funciona(self):
        import assistente.replanejar as replanejar
        import classificador_local.regras.p5_replanejar as regra

        agora = datetime(2026, 9, 24, 14, 30)
        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("1. Faca X.", fake_usage())
        ):
            resultado = regra.executar(self.conn, {"agora": agora})

        token = next(
            a["token"] for a in resultado["cards"][0]["actions"] if a["tipo"] == "desfazer_replanejamento"
        )
        self.assertTrue(replanejar.desfazer_plano(self.conn, token))
        self.assertIsNone(replanejar.ordem_do_dia(self.conn, "2026-09-24"))

    def test_executar_bloqueado_pelo_teto_nao_chama_ia(self):
        import classificador_local.regras.p5_replanejar as regra

        agora = datetime(2026, 9, 24, 14, 30)
        with patch("classificador_local.regras.p5_replanejar.replanejar.teto_permite", return_value=False), patch(
            "claude_client.plano_do_dia"
        ) as mock_plano:
            resultado = regra.executar(self.conn, {"agora": agora})

        mock_plano.assert_not_called()
        self.assertEqual(resultado["cards"], [])
        self.assertIn("teto", resultado["resumo_texto"].lower())

    def test_executar_usa_datetime_now_quando_agora_nao_informado(self):
        import classificador_local.regras.p5_replanejar as regra

        with patch("caldav_client.configurado", return_value=False), patch(
            "claude_client.plano_do_dia", return_value=("1. Faca X.", fake_usage())
        ):
            resultado = regra.executar(self.conn, {})

        self.assertEqual(resultado["cards"][0]["data"]["dia"], date.today().isoformat())


# ---------------------------------------------------------------------------
# assistente/gatilhos/p5_replanejar.py
# ---------------------------------------------------------------------------


class GatilhoP5TestCase(_BaseP5TestCase):
    def _criar_tarefa_atrasada(self):
        self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", ("tarefa velha", "2020-01-01")
        )
        self.conn.commit()

    def _fake_caixa(self):
        modulo = types.ModuleType("assistente.caixa")
        modulo.enfileirar = MagicMock(return_value="item-1")
        return modulo

    def test_nao_dispara_fora_das_14h(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        gatilho.definir_flag(self.conn, True)
        self._criar_tarefa_atrasada()
        fake_caixa = self._fake_caixa()
        with patch.dict(sys.modules, {"assistente.caixa": fake_caixa}):
            gatilho.executar(self.conn, datetime(2026, 9, 24, 9, 0))
        fake_caixa.enfileirar.assert_not_called()

    def test_nao_dispara_com_flag_desligada_por_padrao(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        self._criar_tarefa_atrasada()
        self.assertFalse(gatilho.flag_ativa(self.conn))
        fake_caixa = self._fake_caixa()
        with patch.dict(sys.modules, {"assistente.caixa": fake_caixa}):
            gatilho.executar(self.conn, datetime(2026, 9, 24, 14, 10))
        fake_caixa.enfileirar.assert_not_called()

    def test_nao_dispara_sem_tarefa_atrasada(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        gatilho.definir_flag(self.conn, True)
        fake_caixa = self._fake_caixa()
        with patch.dict(sys.modules, {"assistente.caixa": fake_caixa}):
            gatilho.executar(self.conn, datetime(2026, 9, 24, 14, 10))
        fake_caixa.enfileirar.assert_not_called()

    def test_dispara_as_14h_com_flag_ligada_e_tarefa_atrasada(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        gatilho.definir_flag(self.conn, True)
        self._criar_tarefa_atrasada()
        fake_caixa = self._fake_caixa()
        with patch.dict(sys.modules, {"assistente.caixa": fake_caixa}):
            gatilho.executar(self.conn, datetime(2026, 9, 24, 14, 10))
        fake_caixa.enfileirar.assert_called_once()
        kwargs = fake_caixa.enfileirar.call_args.kwargs
        self.assertEqual(kwargs["origem"], "p5_replanejar")
        self.assertEqual(kwargs["chave_unica"], "p5_replanejar_14h:2026-09-24")

    def test_idempotente_chave_unica_estavel_dentro_do_mesmo_dia(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        gatilho.definir_flag(self.conn, True)
        self._criar_tarefa_atrasada()
        fake_caixa = self._fake_caixa()
        with patch.dict(sys.modules, {"assistente.caixa": fake_caixa}):
            gatilho.executar(self.conn, datetime(2026, 9, 24, 14, 5))
            gatilho.executar(self.conn, datetime(2026, 9, 24, 14, 40))
        chaves = {c.kwargs["chave_unica"] for c in fake_caixa.enfileirar.call_args_list}
        self.assertEqual(chaves, {"p5_replanejar_14h:2026-09-24"})

    def test_ao_resolver_sim_dispara_replanejamento(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        with patch(
            "classificador_local.regras.p5_replanejar.executar", return_value={"cards": []}
        ) as mock_executar:
            gatilho.ao_resolver(self.conn, {"origem": "p5_replanejar"}, "sim")
        mock_executar.assert_called_once()

    def test_ao_resolver_aceitar_tambem_dispara(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        with patch(
            "classificador_local.regras.p5_replanejar.executar", return_value={"cards": []}
        ) as mock_executar:
            gatilho.ao_resolver(self.conn, {"origem": "p5_replanejar"}, "aceitar")
        mock_executar.assert_called_once()

    def test_ao_resolver_nao_nao_dispara(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        with patch(
            "classificador_local.regras.p5_replanejar.executar", return_value={"cards": []}
        ) as mock_executar:
            gatilho.ao_resolver(self.conn, {"origem": "p5_replanejar"}, "nao")
        mock_executar.assert_not_called()

    def test_ao_resolver_adiar_nao_dispara(self):
        import assistente.gatilhos.p5_replanejar as gatilho

        with patch(
            "classificador_local.regras.p5_replanejar.executar", return_value={"cards": []}
        ) as mock_executar:
            gatilho.ao_resolver(self.conn, {"origem": "p5_replanejar"}, "adiar")
        mock_executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
