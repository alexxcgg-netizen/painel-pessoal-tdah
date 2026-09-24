"""Fase 7 (X2): guarda da estrutura do frontend dividido por secao.

- todo script/CSS que a pagina carrega existe e esta no precache do service worker
  (senao o app para de abrir offline sem ninguem perceber);
- toda camada importada por static/css/fase7.css existe e esta no precache;
- toda secao HTML (templates/secoes/<aba>/<secao>.html) tem seu CSS de camada.
"""
import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

RAIZ = Path(__file__).resolve().parent.parent
PIN_TESTE = "135790"


def _assets_service_worker():
    sw = (RAIZ / "static" / "service-worker.js").read_text(encoding="utf-8")
    bloco = sw[sw.index("const ASSETS = [") : sw.index("];", sw.index("const ASSETS = ["))]
    return set(re.findall(r'"(/[^"]*)"', bloco))


class EstruturaFrontendFase7TestCase(unittest.TestCase):
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

    def test_scripts_e_css_da_pagina_existem_e_estao_no_precache(self):
        corpo = self.client.get("/").get_data(as_text=True)
        recursos = re.findall(r'<script src="(/static/[^"]+)"', corpo)
        recursos += re.findall(r'<link rel="stylesheet" href="(/static/[^"]+)"', corpo)
        self.assertIn("/static/js/nucleo/init.js", recursos)
        self.assertIn("/static/css/fase7.css", recursos)
        assets = _assets_service_worker()
        for url in recursos:
            self.assertEqual(self.client.get(url).status_code, 200, f"{url} nao e servido")
            self.assertIn(url, assets, f"{url} fora do precache do service-worker.js")

    def test_camadas_do_fase7_css_existem_e_estao_no_precache(self):
        fase7 = (RAIZ / "static" / "css" / "fase7.css").read_text(encoding="utf-8")
        imports = re.findall(r'@import url\("([^"]+)"\);', fase7)
        self.assertIn("ui/tokens.css", imports)
        assets = _assets_service_worker()
        for rel in imports:
            self.assertTrue((RAIZ / "static" / "css" / rel).is_file(), f"{rel} nao existe")
            self.assertIn(f"/static/css/{rel}", assets, f"{rel} fora do precache")

    def test_toda_secao_html_tem_css_de_camada(self):
        fase7 = (RAIZ / "static" / "css" / "fase7.css").read_text(encoding="utf-8")
        imports = set(re.findall(r'@import url\("([^"]+)"\);', fase7))
        secoes = sorted((RAIZ / "templates" / "secoes").glob("*/*.html"))
        self.assertGreater(len(secoes), 40)
        for html in secoes:
            aba, secao = html.parent.name, html.stem
            self.assertIn(f"secoes/{aba}/{secao}.css", imports, f"secao {aba}/{secao} sem CSS de camada")

    def test_aba_assistente_existe_escondida_e_ponto_de_montagem_na_hoje(self):
        corpo = self.client.get("/").get_data(as_text=True)
        self.assertIn('<section id="tab-assistente" class="tab-content" hidden>', corpo)
        self.assertIn('<div id="caixa-assistente"></div>', corpo)


if __name__ == "__main__":
    unittest.main()
