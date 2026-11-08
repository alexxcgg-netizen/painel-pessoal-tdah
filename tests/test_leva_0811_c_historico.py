"""Leva 08/11, A8 + C5: mensagem automatica do painel (aviso proativo) nao ocupa a janela de historico que
vai pra IA, e o resumo do historico confere com o que esta aberto no banco (nao guarda pendencia velha).
Banco em memoria, IA sempre mockada."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia import core, historico  # noqa: E402
from ia.contrato import Resposta  # noqa: E402

MIGRACAO_SQL = (Path(__file__).resolve().parent.parent / "migracoes" / "202609241100_a5_historico.sql").read_text(
    encoding="utf-8")


def _conectar(com_tarefas=False) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE chat_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    if com_tarefas:
        conn.executescript(
            """
            CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, due_date TEXT, completed_at TEXT,
                                recorrencia TEXT);
            CREATE TABLE esperas (id INTEGER PRIMARY KEY, quem TEXT, sobre TEXT, resolvido_em TEXT);
            """
        )
    conn.executescript(MIGRACAO_SQL)
    conn.commit()
    return conn


def _inserir(conn, *pares):
    for papel, texto in pares:
        conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES (?, ?)", (papel, texto))
    conn.commit()


def _conversa(n, prefixo="msg"):
    pares = []
    for i in range(n):
        pares += [("user", f"{prefixo} pergunta {i}"), ("assistant", f"{prefixo} resposta {i}")]
    return pares


def _avisos(n, prefixo="aviso"):
    return [("assistant", f"{prefixo} {i}") for i in range(n)]


class MarcarProativasTestCase(unittest.TestCase):
    def test_assistant_depois_de_assistant_e_automatica(self):
        msgs = [{"papel": p} for p in ("user", "assistant", "assistant", "assistant", "user", "assistant")]
        self.assertEqual(historico.marcar_proativas(msgs), [False, False, True, True, False, False])

    def test_primeira_assistant_sem_contexto_nao_e_marcada(self):
        self.assertEqual(historico.marcar_proativas([{"papel": "assistant"}]), [False])
        self.assertEqual(historico.marcar_proativas([{"papel": "assistant"}], "assistant"), [True])
        self.assertEqual(historico.marcar_proativas([{"papel": "assistant"}], "user"), [False])


class JanelaSemProativasTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.addCleanup(self.conn.close)

    def test_avisos_nao_ocupam_as_20_vagas(self):
        # 6 interacoes antigas, 12 avisos automaticos no meio, 5 interacoes novas, 4 avisos no fim
        _inserir(self.conn, *_conversa(6, "velha"), *_avisos(12, "meio"), *_conversa(5, "nova"), *_avisos(4, "fim"))
        with patch.object(core, "chamar_ia") as mock_chamar:
            ctx = historico.montar_contexto(self.conn)
        mock_chamar.assert_not_called()
        textos = [m["content"] for m in ctx["mensagens"]]
        # as 20 de conversa: 5 velhas (pergunta+resposta 1..5) + 5 novas inteiras
        conversa = [t for t in textos if "pergunta" in t or "resposta" in t]
        self.assertEqual(len(conversa), 20)
        self.assertIn("velha pergunta 1", textos)
        self.assertNotIn("velha pergunta 0", textos)
        # dos 12 do meio, so os 2 ultimos (vem uma fala dele depois); dos 4 do fim, os 2 ultimos
        self.assertEqual([t for t in textos if t.startswith("meio")], ["meio 10", "meio 11"])
        self.assertEqual([t for t in textos if t.startswith("fim")], ["fim 2", "fim 3"])
        self.assertEqual(ctx["mensagens"][0]["role"], "user")
        self.assertEqual(len(ctx["meta"]), len(ctx["mensagens"]))

    def test_sem_avisos_fica_igual_ao_antes(self):
        _inserir(self.conn, *_conversa(15))
        ctx = historico.montar_contexto(self.conn)
        self.assertEqual(len(ctx["mensagens"]), historico.MENSAGENS_LITERAIS_MAX)
        self.assertEqual(ctx["mensagens"][0]["content"], "msg pergunta 5")

    def test_fallback_do_app_tambem_nao_conta_avisos(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        import db

        antigo = db.DB_PATH
        self.addCleanup(setattr, db, "DB_PATH", antigo)
        db.DB_PATH = Path(tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        import app

        conn = db.get_db()
        self.addCleanup(conn.close)
        for papel, texto in [*_conversa(4, "velha"), *_avisos(30), *_conversa(8, "nova"), *_avisos(1, "fim")]:
            db.salvar_mensagem_chat(conn, papel, texto)
        janela = app._janela_chat_sem_proativas(conn, 20)
        textos = [m["texto"] for m in janela]
        self.assertEqual(len([t for t in textos if "pergunta" in t or "resposta" in t]), 20)
        self.assertEqual([t for t in textos if t.startswith("aviso")], ["aviso 28", "aviso 29"])
        self.assertIn("fim 0", textos)
        self.assertEqual(janela[0]["papel"], "user")


class ResumoConfereComOBancoTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar(com_tarefas=True)
        self.addCleanup(self.conn.close)
        self.conn.execute("INSERT INTO tasks (title) VALUES ('Tarefa aberta de teste')")
        self.conn.execute("INSERT INTO tasks (title, completed_at) VALUES ('Tarefa ja feita de teste', '2026-11-01')")
        self.conn.execute("INSERT INTO esperas (quem, sobre) VALUES ('Fulana', 'o orcamento')")
        self.conn.commit()

    def test_reconstrucao_manda_os_abertos_e_tira_aviso_sem_resposta(self):
        grande = "x" * 1500
        pares = []
        for i in range(12):
            pares += [("user", f"pergunta {i} {grande}"), ("assistant", f"resposta {i} {grande}")]
            if i == 3:
                pares += [("assistant", "AVISO SOLTO 1"), ("assistant", "AVISO SOLTO 2"),
                          ("assistant", "AVISO SOLTO 3")]
        _inserir(self.conn, *pares)
        resposta = Resposta(ok=True, texto="resumo novo")
        with patch.object(core, "chamar_ia", return_value=resposta) as mock_chamar:
            historico.montar_contexto(self.conn)
        mock_chamar.assert_called_once()
        args, kwargs = mock_chamar.call_args
        transcript = args[1][0]["content"]
        self.assertIn("Abertos agora no banco", transcript)
        self.assertIn("Tarefa aberta de teste", transcript)
        self.assertNotIn("Tarefa ja feita de teste", transcript)
        self.assertIn("Fulana: o orcamento", transcript)
        self.assertNotIn("AVISO SOLTO 1", transcript)  # antes dos 2 ultimos da sequencia
        self.assertIn("AVISO SOLTO 3", transcript)  # veio fala dele depois: pode ser o que ele respondeu
        self.assertIn("NAO guarde", kwargs["sistema"])

    def test_sem_tabela_de_tarefas_nao_quebra(self):
        conn = _conectar(com_tarefas=False)
        self.addCleanup(conn.close)
        self.assertEqual(historico._abertos_no_banco(conn), "")


if __name__ == "__main__":
    unittest.main()
