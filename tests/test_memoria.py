"""Memoria sob demanda (2026-10-18): "quando foi o dia que eu arrumei o quartinho?".
A busca so roda quando a IA chama a ferramenta; nada do passado vai sozinho pro contexto.
Banco temporario; nenhuma rede nem IA real."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import memoria  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN = "246813"
HOJE = date(2026, 10, 18)


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

    def tarefa(self, titulo, due=None, feita_em=None):
        self.conn.execute(
            "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)", (titulo, due, feita_em)
        )
        self.conn.commit()

    def fala(self, texto, quando):
        self.conn.execute(
            "INSERT INTO chat_mensagens (papel, texto, criado_em) VALUES ('user', ?, ?)", (texto, quando)
        )
        self.conn.commit()


class RaizesTestCase(unittest.TestCase):
    def test_tira_acento_palavra_vazia_e_corta_verbo(self):
        self.assertEqual(memoria.raizes("quando foi o dia que eu arrumei o quartinho?"), ["arrum", "quart"])
        self.assertEqual(memoria.raizes("Certidão"), ["certi"])
        self.assertEqual(memoria.raizes("de a o"), [])


class BuscarTestCase(_Base):
    def test_acha_tarefa_feita_com_o_dia_certo(self):
        self.tarefa("Arrumar o quartinho de baixo", "2026-10-05", "2026-10-05 15:30:00")  # 12:30 em Brasilia
        self.tarefa("Dentista", "2026-10-06", "2026-10-06 12:00:00")
        r = memoria.buscar(self.conn, "arrumei o quartinho", hoje=HOJE)
        self.assertEqual(r["total_achados"], 1)
        a = r["acertos"][0]
        self.assertEqual(a["dia"], "2026-10-05")
        self.assertEqual(a["tipo"], "tarefa feita")
        self.assertIn("segunda 05/10", a["quando"])

    def test_madrugada_utc_conta_no_dia_de_brasilia(self):
        # 01:00 UTC do dia 6 = 22:00 do dia 5 em Brasilia
        self.tarefa("Arrumar o quartinho", "2026-10-05", "2026-10-06 01:00:00")
        self.assertEqual(memoria.buscar(self.conn, "quartinho", hoje=HOJE)["acertos"][0]["dia"], "2026-10-05")

    def test_tarefa_sem_fazer_usa_o_dia_marcado(self):
        self.tarefa("Arrumar o quartinho", "2026-10-19")
        a = memoria.buscar(self.conn, "quartinho", hoje=HOJE)["acertos"][0]
        self.assertEqual((a["dia"], a["tipo"]), ("2026-10-19", "tarefa que ficou sem fazer"))

    def test_mais_recente_primeiro_e_filtro_de_periodo(self):
        self.tarefa("Arrumar quartinho", "2026-09-01", "2026-09-01 15:00:00")
        self.tarefa("Arrumar quartinho de novo", "2026-10-05", "2026-10-05 15:00:00")
        dias = [a["dia"] for a in memoria.buscar(self.conn, "quartinho", hoje=HOJE)["acertos"]]
        self.assertEqual(dias, ["2026-10-05", "2026-09-01"])
        so_set = memoria.buscar(self.conn, "quartinho", de=date(2026, 9, 1), ate=date(2026, 9, 30), hoje=HOJE)
        self.assertEqual([a["dia"] for a in so_set["acertos"]], ["2026-09-01"])

    def test_pergunta_atual_nao_conta_como_lembranca(self):
        self.fala("vou arrumar o quartinho amanha", "2026-10-10 13:00:00")
        self.fala("quando foi o dia que arrumei o quartinho?", "2026-10-18 22:00:00")
        r = memoria.buscar(self.conn, "arrumei o quartinho", hoje=HOJE)
        self.assertEqual([a["dia"] for a in r["acertos"]], ["2026-10-10"])

    def test_procura_em_chat_notas_esperas_e_diario(self):
        self.fala("o pedreiro vem ver o quartinho", "2026-10-03 14:00:00")
        self.fala("outra coisa qualquer", "2026-10-04 14:00:00")
        self.conn.execute("INSERT INTO notas (titulo, corpo, criado_em) VALUES ('Quartinho', 'medidas', '2026-10-07 12:00:00')")
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES ('Mikael', 'certidao simplificada', '2026-10-18 22:49:00')")
        diario.criar_tabela(self.conn)
        self.conn.execute("INSERT INTO diario_dias (dia, resumo, fatos_json) VALUES ('2026-10-08', '- Arrumou o quartinho.', '{}')")
        self.conn.commit()
        tipos = {a["tipo"] for a in memoria.buscar(self.conn, "quartinho", hoje=HOJE)["acertos"]}
        self.assertEqual(tipos, {"voce falou no chat", "nota", "resumo do dia"})
        self.assertEqual(memoria.buscar(self.conn, "certidao", hoje=HOJE)["acertos"][0]["tipo"], "espera")

    def test_sem_acerto_manda_nao_inventar(self):
        r = memoria.buscar(self.conn, "helicoptero", hoje=HOJE)
        self.assertEqual(r["total_achados"], 0)
        self.assertIn("sem inventar", r["obs"])

    def test_sem_assunto_da_erro_e_limite_corta(self):
        self.assertIn("erro", memoria.buscar(self.conn, "o de a", hoje=HOJE))
        for i in range(1, 9):
            self.tarefa(f"Arrumar quartinho {i}", f"2026-10-{i:02d}", f"2026-10-{i:02d} 15:00:00")
        r = memoria.buscar(self.conn, "quartinho", limite=3, hoje=HOJE)
        self.assertEqual((len(r["acertos"]), r["total_achados"]), (3, 8))
        self.assertIn("mostrando os 3", r["obs"])

    def test_tarefa_de_rotina_nao_entra(self):
        self.conn.execute("INSERT INTO tasks (title, recorrencia) VALUES ('Arrumar quartinho', 'diaria')")
        self.conn.commit()
        self.assertEqual(memoria.buscar(self.conn, "quartinho", hoje=HOJE)["total_achados"], 0)


import diario  # noqa: E402


class FerramentaTestCase(_Base):
    def test_tool_existe_com_assunto_obrigatorio_e_prompt_proibe_uso_espontaneo(self):
        por_nome = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        t = por_nome["buscar_na_memoria"]
        self.assertEqual(t["input_schema"]["required"], ["assunto"])
        self.assertIn("Nunca", t["description"])
        prompt = chat_mod.CHAT_SYSTEM_PROMPT
        self.assertIn("MEMORIA SOB DEMANDA", prompt)
        self.assertIn("Nunca use essa busca por conta propria", prompt)

    def test_executor_roda_pelo_chat_so_quando_chamado(self):
        self.tarefa("Arrumar o quartinho", "2026-10-05", "2026-10-05 15:30:00")
        client = app.app.test_client()
        self.assertEqual(client.post("/login", json={"pin": PIN}).status_code, 200)
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            self.assertNotIn("quartinho", contexto.lower())  # o passado NAO vem no contexto sozinho
            resultados.append(executores["buscar_na_memoria"]({"assunto": "quartinho"}))
            return "Foi dia 5.", ["buscar_na_memoria"], {"model": "x", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}

        with patch("claude_client.chat", side_effect=fake):
            res = client.post("/api/chat", json={"mensagem": "quando foi o dia que arrumei o quartinho?"})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(resultados[0]["acertos"][0]["dia"], "2026-10-05")

    def test_prompt_manda_criar_lista_de_tarefas_sem_pedir_confirmacao(self):
        self.assertIn("LISTA DE TAREFAS SEM DIA", chat_mod.CHAT_SYSTEM_PROMPT)
        self.assertIn("NUNCA responda \"nada foi criado ainda", chat_mod.CHAT_SYSTEM_PROMPT)

    def test_prompt_resposta_curta_continua_o_assunto(self):
        self.assertIn("RESPOSTA CURTA DELE CONTINUA O ASSUNTO", chat_mod.CHAT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
