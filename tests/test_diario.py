"""Diario de cada dia + historico do chat com data (2026-10-12: na segunda a IA ainda lembrava o
Alex do "date as 20h" de sabado, e o modo visitante ligado sem querer travou o chat por 2 dias).
IA sempre dublada; nenhuma rede."""
import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import diario  # noqa: E402

PIN = "246813"
SEG = date(2026, 10, 12)  # segunda
SAB = date(2026, 10, 10)
DOM = date(2026, 10, 11)


def _resp(texto, ok=True):
    return SimpleNamespace(ok=ok, texto=texto)


def _uso():
    return {"model": "x", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def msg(self, papel, texto, utc):
        self.conn.execute("INSERT INTO chat_mensagens (papel, texto, criado_em) VALUES (?, ?, ?)", (papel, texto, utc))
        self.conn.commit()


class DatasTestCase(unittest.TestCase):
    def test_rotulos(self):
        self.assertEqual(diario.rotulo_dia(SEG, SEG), "hoje (segunda 12/10)")
        self.assertEqual(diario.rotulo_dia(DOM, SEG), "ontem (domingo 11/10)")
        self.assertEqual(diario.rotulo_dia(SAB, SEG), "anteontem (sábado 10/10)")
        self.assertEqual(diario.rotulo_dia(date(2026, 10, 8), SEG), "quinta 08/10")

    def test_resolve_sempre_pra_tras(self):
        casos = {"ontem": DOM, "anteontem": SAB, "hoje": SEG, "sábado": SAB, "sabado passado": SAB,
                 "segunda": date(2026, 10, 5), "10/10": SAB, "dia 11": DOM, "dia 20": date(2026, 9, 20),
                 "2026-10-09": date(2026, 10, 9), "15/12": date(2025, 12, 15), "": None, "xyz": None}
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(diario.resolver_dia_passado(texto, SEG), esperado)

    def test_utc_vira_brasilia(self):
        self.assertEqual(diario.utc_para_local("2026-10-11 02:30:00"), datetime(2026, 10, 10, 23, 30))


class FatosTestCase(_Base):
    def test_dia_de_brasilia_nao_de_utc(self):
        # 23:30 de sabado em Brasilia = 02:30 UTC de domingo
        self.conn.execute("INSERT INTO tasks (title, completed_at) VALUES ('Lavar o carro', '2026-10-11 02:30:00')")
        self.conn.commit()
        self.assertEqual(diario.fatos_do_dia(self.conn, SAB)["tarefas_feitas"], ["Lavar o carro (23:30)"])
        self.assertNotIn("tarefas_feitas", diario.fatos_do_dia(self.conn, DOM))

    def test_tarefa_do_dia_marcada_de_madrugada_conta_no_dia_dela(self):
        # date de sabado, marcado como feito domingo 03:20 (06:20 UTC)
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at) VALUES ('Date', '2026-10-10', '20:00', '2026-10-11 06:20:00')"
        )
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Pegar a CND', '2026-10-10')")
        self.conn.commit()
        sab = diario.fatos_do_dia(self.conn, SAB)
        self.assertEqual(sab["tarefas_feitas"], ["Date"])
        self.assertEqual(sab["tarefas_do_dia_nao_feitas"], ["Pegar a CND"])
        self.assertNotIn("tarefas_feitas", diario.fatos_do_dia(self.conn, DOM))

    def test_dia_vazio_nao_vira_linha(self):
        self.assertEqual(diario.fatos_do_dia(self.conn, SAB), {})
        self.assertIsNone(diario.fechar_dia(self.conn, SAB))


class FecharDiaTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.msg("user", "o date é às 20, tenho que buscar ela", "2026-10-10 22:54:00")
        self.msg("assistant", "SAIA AS 19H50 (fala do assistente)", "2026-10-10 22:54:01")
        self.msg("user", "tô sem sono, 3 da tarde busco minha mãe", "2026-10-11 12:15:00")

    def test_fecha_os_dias_que_passaram_so_com_a_fala_do_alex(self):
        with patch("ia.core.chamar_ia", return_value=_resp("- Teve date às 20h.")) as m:
            gravados = diario.garantir_dias_fechados(self.conn, SEG, max_ia=5)
        self.assertEqual(gravados, 2)
        enviado = " ".join(c.args[1][0]["content"] for c in m.call_args_list)
        self.assertIn("o date é às 20", enviado)
        self.assertNotIn("fala do assistente", enviado)  # assistente pode ter errado o dia
        self.assertIn("[19:54]", enviado)  # horario de Brasilia
        self.assertEqual(diario.ler_dia(self.conn, SAB)["resumo"], "- Teve date às 20h.")
        self.assertIsNone(diario.ler_dia(self.conn, SEG))  # hoje nunca fecha

    def test_uma_ia_por_vez_e_tenta_de_novo_quando_falha(self):
        with patch("ia.core.chamar_ia", return_value=_resp("", ok=False)):
            diario.garantir_dias_fechados(self.conn, SEG, max_ia=1)
        # domingo tentou e falhou; sabado nem chamou a IA (so 1 por vez) - os dois ja tem os fatos
        self.assertIsNone(diario.ler_dia(self.conn, DOM)["resumo"])
        self.assertIsNone(diario.ler_dia(self.conn, SAB)["resumo"])
        self.assertEqual(diario.ler_dia(self.conn, SAB)["fatos"]["mensagens_no_chat"], 1)
        with patch("ia.core.chamar_ia", return_value=_resp("- Buscou a mãe.")):
            diario.garantir_dias_fechados(self.conn, SEG, max_ia=1)
            diario.garantir_dias_fechados(self.conn, SEG, max_ia=1)
        self.assertEqual(diario.ler_dia(self.conn, DOM)["resumo"], "- Buscou a mãe.")
        self.assertEqual(diario.ler_dia(self.conn, SAB)["resumo"], "- Buscou a mãe.")
        with patch("ia.core.chamar_ia") as m:
            diario.garantir_dias_fechados(self.conn, SEG)
        m.assert_not_called()  # tudo fechado: nao gasta nada

    def test_ia_explodindo_nao_derruba(self):
        with patch("ia.core.chamar_ia", side_effect=RuntimeError("rede")):
            diario.garantir_dias_fechados(self.conn, SEG, max_ia=5)
        self.assertIn("mensagens_no_chat", diario.ler_dia(self.conn, DOM)["fatos"])

    def test_contexto_com_o_nome_do_dia_e_anotacao_do_alex(self):
        with patch("ia.core.chamar_ia", return_value=_resp("- Teve date às 20h.")):
            diario.garantir_dias_fechados(self.conn, SEG, max_ia=5)
        diario.anotar(self.conn, DOM, "o date foi ontem, nao hoje")
        linhas = diario.linhas_contexto(self.conn, SEG)
        self.assertIn("JÁ PASSARAM", linhas[0])
        self.assertTrue(linhas[1].startswith("- ontem (domingo 11/10): Teve date às 20h."))
        self.assertIn("O Alex corrigiu", linhas[1])
        self.assertTrue(linhas[2].startswith("- anteontem (sábado 10/10)"))
        self.assertEqual(diario.consultar(self.conn, DOM, SEG)["anotacoes_do_alex"], ["o date foi ontem, nao hoje"])

    def test_consultar_dia_sem_linha_fecha_na_hora_sem_ia(self):
        with patch("ia.core.chamar_ia") as m:
            r = diario.consultar(self.conn, SAB, SEG)
        m.assert_not_called()
        self.assertEqual(r["dia"], "anteontem (sábado 10/10)")
        self.assertEqual(r["fatos"]["mensagens_no_chat"], 1)
        self.assertIn("erro", diario.consultar(self.conn, SEG + timedelta(days=1), SEG))


class HistoricoComDataTestCase(_Base):
    AGORA = datetime(2026, 10, 12, 16, 30)  # Brasilia

    def itens(self):
        return [
            {"role": "user", "content": "o date é às 20", "criado_em": "2026-10-10 22:54:00"},
            {"role": "assistant", "content": "beleza", "criado_em": "2026-10-10 22:54:01"},
            {"role": "user", "content": "e aí", "criado_em": "2026-10-12 19:20:00"},
            {"role": "assistant", "content": "oi", "criado_em": "2026-10-12 19:20:01"},
        ]

    def test_mensagem_de_outro_dia_vai_marcada(self):
        saida = app._historico_com_datas(self.conn, self.itens(), self.AGORA)
        self.assertEqual(
            saida[0]["content"], "[anteontem (sábado 10/10), 19:54 - dia que já passou] o date é às 20"
        )
        self.assertEqual(saida[2], {"role": "user", "content": "e aí"})  # hoje vai igual

    def test_dia_com_diario_sai_do_historico(self):
        self.msg("user", "o date é às 20", "2026-10-10 22:54:00")
        with patch("ia.core.chamar_ia", return_value=_resp("- Teve date.")):
            diario.fechar_dia(self.conn, SAB)
        saida = app._historico_com_datas(self.conn, self.itens(), self.AGORA)
        self.assertEqual([m["content"] for m in saida], ["e aí", "oi"])

    def test_virada_da_meia_noite_continua_na_integra_e_nunca_comeca_por_assistant(self):
        itens = [
            {"role": "assistant", "content": "sobrou", "criado_em": "2026-10-12 02:50:00"},
            {"role": "user", "content": "e amanhã?", "criado_em": "2026-10-12 02:55:00"},  # 23:55 de domingo
            {"role": "assistant", "content": "amanhã tem X", "criado_em": "2026-10-12 02:55:05"},
        ]
        with patch("ia.core.chamar_ia", return_value=_resp("- algo")):
            self.msg("user", "x", "2026-10-11 15:00:00")
            diario.fechar_dia(self.conn, DOM)
        saida = app._historico_com_datas(self.conn, itens, datetime(2026, 10, 12, 0, 20))
        self.assertEqual(saida[0]["role"], "user")
        self.assertIn("[ontem (domingo 11/10), 23:55 - dia que já passou] e amanhã?", saida[0]["content"])


class ChatTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def chat(self, chamadas, vistos=None):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            if vistos is not None:
                vistos.append((mensagens, contexto))
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], _uso()

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "o date foi ontem"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return resultados

    def test_contexto_traz_o_diario_e_as_tools_funcionam(self):
        ontem = (datetime.now(diario.TZ).date() - timedelta(days=1))
        diario.criar_tabela(self.conn)
        self.conn.execute("INSERT INTO diario_dias (dia, resumo, fatos_json) VALUES (?, '- Teve date às 20h.', '{}')",
                          (ontem.isoformat(),))
        self.conn.commit()
        vistos = []
        r = self.chat([("anotar_no_diario", {"dia": "ontem", "texto": "teve date às 20h"}),
                       ("consultar_diario", {"dia": "ontem"})], vistos)
        self.assertTrue(r[0]["ok"])
        self.assertTrue(r[0]["dia"].startswith("ontem"))
        self.assertEqual(r[1]["anotacoes_do_alex"], ["teve date às 20h"])
        self.assertIn("Diário dos últimos dias", vistos[0][1])
        self.assertIn("Teve date às 20h.", vistos[0][1])

    def test_visitante_nao_anota(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        r = self.chat([("anotar_no_diario", {"dia": "ontem", "texto": "x"})])
        self.assertIn("MODO VISITANTE", r[0]["erro"])
        self.assertIn("selo", r[0]["erro"])


class ModoVisitanteTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def test_liga_e_mostra_quanto_falta(self):
        r = self.client.post("/api/modo-visitante", json={"ativar": True}).get_json()
        self.assertEqual(r, {"ativo": True, "minutos_restantes": app.MODO_VISITANTE_MINUTOS})
        self.assertTrue(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_desliga_sozinho_depois_de_1_hora(self):
        self.client.post("/api/modo-visitante", json={"ativar": True})
        with self.client.session_transaction() as s:
            s["modo_visitante_desde"] = time.time() - app.MODO_VISITANTE_MINUTOS * 60 - 5
        self.assertFalse(self.client.get("/api/modo-visitante").get_json()["ativo"])

    def test_sessao_antiga_sem_hora_ja_saiu(self):
        # o caso real: ligado em 10/10 antes de existir a hora
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
        self.assertEqual(self.client.get("/api/modo-visitante").get_json(), {"ativo": False, "minutos_restantes": 0})


if __name__ == "__main__":
    unittest.main()
