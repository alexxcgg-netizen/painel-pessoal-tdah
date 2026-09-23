import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import claude_client
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


def _resp(content, stop_reason="end_turn", model=claude_client.SONNET, in_tok=100, out_tok=20):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
    )


def _text_block(texto):
    return SimpleNamespace(type="text", text=texto)


def _tool_block(nome, entrada, id_):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


class IdeiasPresenteDbTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_create_and_list(self):
        db.create_ideia_presente(self.conn, "Mae", "Perfume", "Aniversario")
        db.create_ideia_presente(self.conn, "Pai", "Livro", None)
        itens = db.list_ideias_presente(self.conn)
        self.assertEqual(len(itens), 2)
        nomes = {i["pessoa"] for i in itens}
        self.assertEqual(nomes, {"Mae", "Pai"})

    def test_comprados_vem_por_ultimo(self):
        id1 = db.create_ideia_presente(self.conn, "Mae", "Perfume", None)
        db.create_ideia_presente(self.conn, "Pai", "Livro", None)
        db.alternar_ideia_presente_comprada(self.conn, id1)
        itens = db.list_ideias_presente(self.conn)
        self.assertEqual(itens[-1]["pessoa"], "Mae")
        self.assertEqual(itens[-1]["comprado"], 1)

    def test_alternar_toggla_duas_vezes(self):
        id1 = db.create_ideia_presente(self.conn, "Mae", "Perfume", None)
        r1 = db.alternar_ideia_presente_comprada(self.conn, id1)
        self.assertTrue(r1)
        r2 = db.alternar_ideia_presente_comprada(self.conn, id1)
        self.assertFalse(r2)

    def test_alternar_id_inexistente(self):
        self.assertIsNone(db.alternar_ideia_presente_comprada(self.conn, 99999))

    def test_delete(self):
        id1 = db.create_ideia_presente(self.conn, "Mae", "Perfume", None)
        db.delete_ideia_presente(self.conn, id1)
        self.assertEqual(db.list_ideias_presente(self.conn), [])


class IdeiasPresenteApiTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def test_crud_completo_pela_api(self):
        res = self.client.post("/api/ideias-presente", json={"pessoa": "Ana", "ideia": "Tenis", "ocasiao": "Natal"})
        self.assertEqual(res.status_code, 201)
        ideia_id = res.get_json()["ideia_id"]

        listagem = self.client.get("/api/ideias-presente").get_json()
        self.assertEqual(len(listagem), 1)
        self.assertEqual(listagem[0]["pessoa"], "Ana")
        self.assertEqual(listagem[0]["comprado"], 0)

        res_toggle = self.client.post(f"/api/ideias-presente/{ideia_id}/comprado")
        self.assertEqual(res_toggle.status_code, 200)
        self.assertTrue(res_toggle.get_json()["comprado"])

        res_del = self.client.delete(f"/api/ideias-presente/{ideia_id}")
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(self.client.get("/api/ideias-presente").get_json(), [])

    def test_criar_sem_pessoa_da_erro(self):
        res = self.client.post("/api/ideias-presente", json={"ideia": "Tenis"})
        self.assertEqual(res.status_code, 400)

    def test_criar_sem_ideia_da_erro(self):
        res = self.client.post("/api/ideias-presente", json={"pessoa": "Ana"})
        self.assertEqual(res.status_code, 400)

    def test_toggle_id_inexistente_404(self):
        res = self.client.post("/api/ideias-presente/99999/comprado")
        self.assertEqual(res.status_code, 404)

    def test_rota_exige_login(self):
        self.client.post("/logout")
        res = self.client.get("/api/ideias-presente")
        self.assertEqual(res.status_code, 401)

    def test_chat_tool_registrar_ideia_presente(self):
        conteudo = [_tool_block("registrar_ideia_presente", {"pessoa": "Bia", "ideia": "Caneca"}, "t1")]
        with patch.object(
            claude_client.client.messages,
            "create",
            side_effect=[
                _resp(conteudo, stop_reason="tool_use"),
                _resp([_text_block("Anotado!")], stop_reason="end_turn"),
            ],
        ):
            res = self.client.post("/api/chat", json={"mensagem": "ideia de presente pra Bia: caneca"})
        self.assertEqual(res.status_code, 200)
        itens = self.client.get("/api/ideias-presente").get_json()
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["pessoa"], "Bia")
        self.assertEqual(itens[0]["ideia"], "Caneca")


if __name__ == "__main__":
    unittest.main()
