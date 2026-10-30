"""Tela "Gerar relatorio" do app iOS: rota que recebe o retrato do aparelho (2026-10-30)."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

from rotas import n3a_widget  # noqa: E402

TOKEN = {"Authorization": "Bearer token-de-teste"}


class RelatorioAppIosTestCase(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "token-de-teste"})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.client = app.app.test_client()

    def linhas(self):
        conn = sqlite3.connect(db.DB_PATH)
        self.addCleanup(conn.close)
        return [json.loads(r[0]) for r in conn.execute(
            "SELECT dados_json FROM diagnostico_cliente WHERE tipo = 'app_ios' ORDER BY id")]

    def test_sem_token_e_recusado_e_nao_grava(self):
        antes = len(self.linhas())
        r = self.client.post("/api/widget/relatorio", json={"dados": {"ios": "18.1"}})
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/widget/relatorio", json={"dados": {"ios": "18.1"}},
                             headers={"Authorization": "Bearer errado"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(len(self.linhas()), antes)

    def test_grava_com_o_token_do_widget(self):
        r = self.client.post("/api/widget/relatorio", headers=TOKEN,
                             json={"dados": {"ios": "18.1", "ilha_ativas": True, "provisao_dias": 6}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.linhas()[-1], {"ios": "18.1", "ilha_ativas": True, "provisao_dias": 6})

    def test_corpo_invalido_nao_quebra(self):
        for corpo in ({}, {"dados": {}}, {"dados": "x"}, {"dados": [1]}, [1], {"dados": {"token": "abc"}}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post("/api/widget/relatorio", headers=TOKEN, json=corpo).status_code, 400)

    def test_limpa_segredo_endereco_e_excesso(self):
        d = n3a_widget.relatorio_limpo({
            "ios": "18", "url_base": "https://x", "painel_host": "x", "widget_token": "y", "minha_senha": "z",
            "aninhado": {"a": 1}, "lista": [1], "k" * 33: "longa", "texto": "a" * 500,
        })
        self.assertEqual(set(d), {"ios", "texto"})
        self.assertEqual(len(d["texto"]), 200)
        self.assertLessEqual(len(n3a_widget.relatorio_limpo({f"c{i}": i for i in range(300)})), 80)


if __name__ == "__main__":
    unittest.main()
