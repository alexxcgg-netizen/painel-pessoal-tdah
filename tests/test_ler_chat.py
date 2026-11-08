"""scripts/ler_chat.py: copia do chat pro Claude Code ler. So leitura, oculta
numero longo/senha, marca correcao do Alex, resume cards. Banco temporario."""

import importlib.util
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_spec = importlib.util.spec_from_file_location(
    "ler_chat", Path(__file__).resolve().parent.parent / "scripts" / "ler_chat.py"
)
ler_chat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ler_chat)


def _utc(ano, mes, dia, h, m):
    """Hora LOCAL -> texto UTC como o banco grava (datetime('now'))."""
    local = datetime(ano, mes, dia, h, m).astimezone()
    return local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class LerChatTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        conn = db.get_db()
        db.salvar_mensagem_chat(conn, "user", "marca voo amanhã 8h pra SBJV")
        db.salvar_mensagem_chat(
            conn, "assistant", "Feito! Voo agendado.",
            [{"type": "voo_agendado", "data": {"data": "2026-10-16", "hora": "08:00", "paradas": ["SSBL", "SBJV"]},
              "actions": [{"label": "Desfazer"}]}],
        )
        db.salvar_mensagem_chat(conn, "user", "não era isso, eu queria às 9h")
        db.salvar_mensagem_chat(conn, "user", "meu cpf 123.456.789-09 e a senha: abc123")
        conn.execute("UPDATE chat_mensagens SET criado_em = ? WHERE id = 1", (_utc(2026, 10, 14, 21, 50),))
        conn.execute("UPDATE chat_mensagens SET criado_em = ? WHERE id = 2", (_utc(2026, 10, 14, 21, 50),))
        conn.execute("UPDATE chat_mensagens SET criado_em = ? WHERE id = 3", (_utc(2026, 10, 14, 22, 30),))
        conn.execute("UPDATE chat_mensagens SET criado_em = ? WHERE id = 4", (_utc(2026, 10, 1, 10, 0),))
        conn.commit()
        conn.close()

    def tearDown(self):
        db.DB_PATH = self._original
        self._tmp.cleanup()

    def test_copia_do_dia_com_card_e_correcao(self):
        conn = ler_chat.abrir_so_leitura(db.DB_PATH)
        texto, conta = ler_chat.montar_copia(conn, date(2026, 10, 14), date(2026, 10, 14))
        conn.close()
        self.assertIn("## qua 14/10/2026", texto)
        self.assertIn("**21:50 Alex:** marca voo amanhã 8h pra SBJV", texto)
        # 22:30 local ja e 15/10 em UTC - continua no dia 14 da copia
        self.assertIn("**22:30 ⚠ Alex:** não era isso", texto)
        self.assertIn("card `voo_agendado`: data=2026-10-16 · hora=08:00 · paradas=SSBL, SBJV (botões: Desfazer)", texto)
        self.assertEqual(conta, {"alex": 2, "ia": 1, "correcoes": 1, "cards": 1})
        self.assertNotIn("cpf", texto)  # mensagem de 01/10 fora do periodo

    def test_oculta_numero_longo_e_senha(self):
        t = ler_chat.ocultar_sensivel("meu cpf 123.456.789-09 e a senha: abc123, cartão 4111 1111 1111 1111")
        self.assertNotIn("789", t)
        self.assertNotIn("abc123", t)
        self.assertNotIn("4111", t)
        self.assertIn("senha: [oculto]", t)
        self.assertEqual(ler_chat.ocultar_sensivel("gastei R$ 1.250,00 no voo de 08:00"), "gastei R$ 1.250,00 no voo de 08:00")

    def test_pista_de_correcao(self):
        for frase in ("Não era isso", "tá errado", "já falei que não", "nada a ver", "para de mandar isso"):
            self.assertTrue(ler_chat.parece_correcao(frase), frase)
        for frase in ("marca voo amanhã", "valeu, ficou ótimo", "quanto gastei no mês?"):
            self.assertFalse(ler_chat.parece_correcao(frase), frase)

    def test_so_leitura_de_verdade(self):
        conn = ler_chat.abrir_so_leitura(db.DB_PATH)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES ('user', 'x')")
        conn.close()

    def test_main_grava_arquivo(self):
        saida = Path(self._tmp.name) / "copia.md"
        antes = dict(os.environ)
        # 08/11: o main() carrega o .env de verdade (uso normal do script); sob teste isso vazava a
        # ENCRYPTION_KEY real pros testes seguintes do mesmo processo - aqui o load_dotenv e dublado
        with patch("dotenv.load_dotenv") as carregar_env:
            codigo = ler_chat.main(["--banco", str(db.DB_PATH), "--saida", str(saida), "--desde", "2026-10-01",
                                    "--ate", "2026-10-15"])
        self.assertEqual(codigo, 0)
        carregar_env.assert_called_once()  # o script continua carregando o .env fora do teste
        self.assertEqual(dict(os.environ), antes)
        texto = saida.read_text(encoding="utf-8")
        self.assertIn("qui 01/10/2026", texto)
        self.assertIn("[número oculto]", texto)

    def test_mostra_o_diagnostico_do_aparelho(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO diagnostico_cliente (tipo, dados_json, criado_em) VALUES ('mic', ?, ?)",
            ('{"evento": "detector_surdo", "ctx": "interrupted"}', _utc(2026, 10, 14, 22, 0)),
        )
        conn.commit()
        conn.close()
        conn = ler_chat.abrir_so_leitura(db.DB_PATH)
        texto, _ = ler_chat.montar_copia(conn, date(2026, 10, 14), date(2026, 10, 14))
        conn.close()
        self.assertIn("## Diagnóstico do aparelho", texto)
        self.assertIn("- 14/10 22:00 **mic**: evento=detector_surdo · ctx=interrupted", texto)

    def test_periodo_vazio(self):
        conn = ler_chat.abrir_so_leitura(db.DB_PATH)
        texto, _ = ler_chat.montar_copia(conn, date(2025, 1, 1), date(2025, 1, 2))
        conn.close()
        self.assertIn("nenhuma mensagem", texto)


if __name__ == "__main__":
    unittest.main()
