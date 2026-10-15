"""Problemas de card vistos lendo o chat do Alex (2026-10-15, scripts/ler_chat.py):
- "tomei 4 copos" -> 4 cards de agua iguais: agora 1 card, 1 Desfazer pros 4;
- card de sugestao "15:00" do lado do horario que a IA gravou de verdade (9h45): sugestao some
  quando a mesma resposta ja criou/editou a tarefa."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402
import cards  # noqa: E402


class CardsLidosNoChatTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()
        self.tokens = []

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._original
        self._tmp.cleanup()

    def criar_token(self, itens):
        self.tokens.append(list(itens))
        return f"tok{len(self.tokens)}"

    def test_varios_copos_um_card_so(self):
        hoje = date.today().isoformat()
        efeitos = []
        for _ in range(4):
            db.registrar_hidratacao(self.conn, hoje)
            rid = self.conn.execute("SELECT MAX(id) AS id FROM hidratacao_registros").fetchone()["id"]
            efeitos.append({"entidade": "hidratacao", "id": rid})
        lista = cards.cards_dos_efeitos(self.conn, efeitos, self.criar_token)
        agua = [c for c in lista if c["type"] == "agua"]
        self.assertEqual(len(agua), 1)
        self.assertEqual(agua[0]["data"]["copos"], 4)
        self.assertEqual(len(self.tokens), 1)
        self.assertEqual(len(self.tokens[0]), 4)

    def test_sugestao_some_quando_a_resposta_gravou_o_horario(self):
        tid = self.conn.execute("INSERT INTO tasks (title) VALUES ('Pagar a conta de luz')").lastrowid
        self.conn.commit()
        sugestao = {"entidade": "sugestao", "titulo": "Pagar a conta de luz", "inicio": "2026-10-13T15:00",
                    "duracao_min": 10, "porque": "maior espaço livre", "consulta": True}
        so_sugestao = cards.cards_dos_efeitos(self.conn, [sugestao], self.criar_token)
        self.assertEqual([c["type"] for c in so_sugestao], ["sugestao"])
        com_edicao = cards.cards_dos_efeitos(
            self.conn,
            [sugestao, {"entidade": "edicao", "tabela": "tasks", "id": tid, "rotulo": "Tarefa",
                        "titulo": "Pagar a conta de luz", "antes": {"due_at": None},
                        "depois": {"due_at": "2026-10-13T09:45"}}],
            self.criar_token,
        )
        self.assertNotIn("sugestao", [c["type"] for c in com_edicao])


if __name__ == "__main__":
    unittest.main()
