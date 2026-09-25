# tests/test_fase9_c_nav.py - Fase 9 (C-nav): a barra de baixo cai de 8 pra 4
# abas (hoje/tarefas/gastos/vida). Painel, Construtora, Aviacao e Assistente
# deixam de ser abas propria (conteudo movido por outra faixa, C-abas) - aqui
# so testamos a navegacao renderizada: exatamente 4 .tab-btn, nesta ordem, e
# nenhum data-tab de aba removida sobrevivendo na barra.
import os
import tempfile
import re
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

import unittest

PIN_TESTE = "123456"

ORDEM_ABAS_ESPERADA = ["hoje", "tarefas", "gastos", "vida"]
ABAS_REMOVIDAS = ["painel", "construtora", "aviacao", "assistente"]


class Fase9CNavTestCase(unittest.TestCase):
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
        self.corpo = self.client.get("/").get_data(as_text=True)

    def _bloco_tabbar(self):
        inicio = self.corpo.index('id="tabbar"')
        fim = self.corpo.index("</nav>", inicio)
        return self.corpo[inicio:fim]

    def test_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_barra_tem_exatamente_4_tab_btn(self):
        tabbar = self._bloco_tabbar()
        botoes = re.findall(r'<button[^>]*class="tab-btn[^"]*"', tabbar)
        self.assertEqual(len(botoes), 4, f"esperava 4 .tab-btn na barra, achou {len(botoes)}")

    def test_data_tab_na_ordem_esperada(self):
        tabbar = self._bloco_tabbar()
        encontrados = re.findall(r'data-tab="([^"]+)"', tabbar)
        self.assertEqual(encontrados, ORDEM_ABAS_ESPERADA)

    def test_nenhuma_aba_removida_na_barra(self):
        tabbar = self._bloco_tabbar()
        for aba in ABAS_REMOVIDAS:
            with self.subTest(aba=aba):
                self.assertNotIn(f'data-tab="{aba}"', tabbar)

    def test_navegacao_js_redireciona_abas_antigas(self):
        # static/js/nucleo/navegacao.js precisa continuar reconhecendo os
        # nomes antigos (voz, links internos, cards) e mandar pro destino
        # novo - conferido aqui pelo texto do arquivo servido, nao pela
        # execucao do JS (sem infra de browser no test_backend).
        js = self.client.get("/static/js/nucleo/navegacao.js").get_data(as_text=True)
        self.assertIn('painel: "hoje"', js)
        self.assertIn('assistente: "hoje"', js)
        self.assertIn('construtora: "gastos"', js)
        self.assertIn('aviacao: "vida"', js)


if __name__ == "__main__":
    unittest.main()
