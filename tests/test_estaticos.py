"""estaticos.py: versão na URL de /static/, cache de 1 ano e gzip de texto (2026-11-05, leva "perfeição").

Roda num Flask de mentira com pasta static temporária (pra poder trocar arquivo e ver a versão mudar) e,
no fim, confere o app de verdade: página com ?v em tudo e o fase7.css reescrito.
"""
import gzip
import os
import tempfile
import time
import unittest
from pathlib import Path

from flask import Flask, Response, jsonify

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import estaticos  # noqa: E402

HTML = (
    '<html><head><link rel="stylesheet" href="/static/css/indice.css" />'
    '<script src="/static/js/a.js"></script><script src="/static/js/sumiu.js"></script>'
    '<a href="https://fora.example/static/x.js">fora</a></head><body>' + ("<p>texto</p>" * 300) + "</body></html>"
)


def _escrever(pasta, rel, texto):
    caminho = Path(pasta) / rel
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(texto.encode("utf-8"))  # bytes: sem a troca de fim de linha do Windows
    return caminho


def _mexer(caminho, texto):
    """Troca o conteúdo e garante data diferente (a impressão só é refeita quando data/tamanho mudam)."""
    caminho.write_bytes(texto.encode("utf-8"))
    st = caminho.stat()
    os.utime(caminho, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    estaticos.limpar()


class EstaticosTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pasta = self.tmp.name
        self.camada = _escrever(pasta, "css/camadas/um.css", ".um { color: red; }\n" * 80)
        _escrever(pasta, "css/camadas/dois.css", ".dois { color: blue; }\n")
        self.indice = _escrever(
            pasta,
            "css/indice.css",
            '@import url("camadas/um.css");\n@import url(\'camadas/dois.css\');\n'
            '@import url("https://fonts.example/x.css");\n@import url("camadas/nao-existe.css");\n',
        )
        self.js = _escrever(pasta, "js/a.js", "console.log('a');\n" * 200)
        _escrever(pasta, "js/pequeno.js", "x();\n")
        estaticos.limpar()

        app = Flask(__name__, static_folder=pasta, static_url_path="/static")

        @app.route("/")
        def pagina():
            return HTML

        @app.route("/dados")
        def dados():
            return jsonify({"lista": list(range(800))})

        @app.route("/pouco")
        def pouco():
            return jsonify({"ok": True})

        @app.route("/fluxo")
        def fluxo():
            return Response((f"data: {i}\n\n" for i in range(400)), mimetype="text/event-stream")

        estaticos.instalar(app)
        self.app = app
        self.cliente = app.test_client()

    def tearDown(self):
        estaticos.limpar()
        self.tmp.cleanup()

    # --- versão na URL ---

    def test_pagina_ganha_versao_so_no_que_existe_e_e_local(self):
        html = self.cliente.get("/").get_data(as_text=True)
        with self.app.test_request_context():
            v_js = estaticos.versao_url("/static/js/a.js")
            v_css = estaticos.versao_url("/static/css/indice.css")
        self.assertRegex(v_js, r"^[0-9a-f]{12}$")
        self.assertIn(f'src="/static/js/a.js?v={v_js}"', html)
        self.assertIn(f'href="/static/css/indice.css?v={v_css}"', html)
        self.assertIn('src="/static/js/sumiu.js"', html)  # não existe: fica como está
        self.assertIn('href="https://fora.example/static/x.js"', html)

    def test_versao_atual_sai_imutavel_e_versao_velha_nao(self):
        with self.app.test_request_context():
            v = estaticos.versao_url("/static/js/a.js")
        res = self.cliente.get(f"/static/js/a.js?v={v}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["X-Versao"], v)
        self.assertIn("immutable", res.headers["Cache-Control"])
        self.assertIn("max-age=31536000", res.headers["Cache-Control"])

        velha = self.cliente.get("/static/js/a.js?v=000000000000")
        self.assertEqual(velha.headers["X-Versao"], v)
        self.assertNotIn("immutable", velha.headers.get("Cache-Control", ""))
        sem = self.cliente.get("/static/js/a.js")
        self.assertNotIn("immutable", sem.headers.get("Cache-Control", ""))

    def test_mudar_o_arquivo_muda_a_versao(self):
        with self.app.test_request_context():
            antes = estaticos.versao_url("/static/js/a.js")
        _mexer(self.js, "console.log('b');\n" * 200)
        with self.app.test_request_context():
            depois = estaticos.versao_url("/static/js/a.js")
        self.assertNotEqual(antes, depois)

    def test_css_com_import_sai_reescrito_e_versao_inclui_as_camadas(self):
        with self.app.test_request_context():
            v_um = estaticos.versao_url("/static/css/camadas/um.css")
            v_indice = estaticos.versao_url("/static/css/indice.css")
        res = self.cliente.get(f"/static/css/indice.css?v={v_indice}")
        texto = res.get_data(as_text=True)
        self.assertEqual(res.mimetype, "text/css")
        self.assertIn(f'@import url("/static/css/camadas/um.css?v={v_um}")', texto)
        self.assertIn('@import url("/static/css/camadas/dois.css?v=', texto)
        self.assertIn('@import url("https://fonts.example/x.css")', texto)  # de fora: intacto
        self.assertIn('@import url("camadas/nao-existe.css")', texto)  # não existe: intacto
        self.assertEqual(res.headers["X-Versao"], v_indice)
        self.assertIn("immutable", res.headers["Cache-Control"])

        # mexer só na camada muda a URL do índice (senão o índice imutável apontaria pra camada velha)
        _mexer(self.camada, ".um { color: green; }\n" * 80)
        with self.app.test_request_context():
            self.assertNotEqual(estaticos.versao_url("/static/css/indice.css"), v_indice)

    def test_css_reescrito_responde_304_pela_versao_e_nao_pela_data_do_arquivo(self):
        primeira = self.cliente.get("/static/css/indice.css")
        etag = primeira.headers["ETag"]
        self.assertEqual(self.cliente.get("/static/css/indice.css", headers={"If-None-Match": etag}).status_code, 304)
        _mexer(self.camada, ".um { color: purple; }\n" * 80)
        # o índice no disco não mudou, mas o texto servido mudou: tem que vir 200
        self.assertEqual(self.cliente.get("/static/css/indice.css", headers={"If-None-Match": etag}).status_code, 200)

    def test_import_circular_nao_trava(self):
        _escrever(self.tmp.name, "css/a.css", '@import url("b.css");\n')
        _escrever(self.tmp.name, "css/b.css", '@import url("a.css");\n')
        estaticos.limpar()
        res = self.cliente.get("/static/css/a.css")
        self.assertEqual(res.status_code, 200)

    def test_caminho_que_sai_da_pasta_nao_tem_versao(self):
        with self.app.test_request_context():
            self.assertIsNone(estaticos.versao_url("/static/../segredo.py"))
            self.assertIsNone(estaticos.versao_url("/outra/coisa.js"))
        self.assertEqual(self.cliente.get("/static/js/nao-tem.js").status_code, 404)

    # --- gzip ---

    def test_gzip_na_pagina_quando_o_navegador_aceita(self):
        res = self.cliente.get("/", headers={"Accept-Encoding": "gzip, deflate, br"})
        self.assertEqual(res.headers["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", res.headers["Vary"])
        html = gzip.decompress(res.get_data()).decode()
        self.assertIn("/static/js/a.js?v=", html)
        self.assertLess(len(res.get_data()), len(html.encode()) / 3)

    def test_sem_accept_encoding_nada_e_comprimido(self):
        for rota in ("/", "/dados", "/static/js/a.js"):
            self.assertNotIn("Content-Encoding", self.cliente.get(rota).headers, rota)

    def test_json_grande_comprime_e_pequeno_nao(self):
        grande = self.cliente.get("/dados", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(grande.headers["Content-Encoding"], "gzip")
        self.assertEqual(len(gzip.decompress(grande.get_data()).decode().split(",")), 800)
        pouco = self.cliente.get("/pouco", headers={"Accept-Encoding": "gzip"})
        self.assertNotIn("Content-Encoding", pouco.headers)

    def test_fluxo_sse_nunca_e_comprimido(self):
        res = self.cliente.get("/fluxo", headers={"Accept-Encoding": "gzip"})
        self.assertNotIn("Content-Encoding", res.headers)
        self.assertIn("data: 399", res.get_data(as_text=True))

    def test_arquivo_estatico_comprime_com_etag_fraca_e_304_continua(self):
        res = self.cliente.get("/static/js/a.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(res.headers["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(res.get_data()).decode(), self.js.read_bytes().decode("utf-8"))
        self.assertTrue(res.headers["ETag"].startswith("W/"))
        self.assertNotIn("Accept-Ranges", res.headers)
        de_novo = self.cliente.get(
            "/static/js/a.js", headers={"Accept-Encoding": "gzip", "If-None-Match": res.headers["ETag"]}
        )
        self.assertEqual(de_novo.status_code, 304)

    def test_arquivo_pequeno_nao_comprime(self):
        res = self.cliente.get("/static/js/pequeno.js", headers={"Accept-Encoding": "gzip"})
        self.assertNotIn("Content-Encoding", res.headers)
        self.assertEqual(res.get_data(as_text=True), "x();\n")

    def test_pedido_de_pedaco_nao_e_comprimido(self):
        res = self.cliente.get("/static/js/a.js", headers={"Accept-Encoding": "gzip", "Range": "bytes=0-9"})
        self.assertEqual(res.status_code, 206)
        self.assertNotIn("Content-Encoding", res.headers)

    def test_erro_na_otimizacao_devolve_a_resposta_intacta(self):
        original = estaticos.versionar_html
        estaticos.versionar_html = lambda html: 1 / 0
        try:
            res = self.cliente.get("/")
        finally:
            estaticos.versionar_html = original
        self.assertEqual(res.status_code, 200)
        self.assertIn('src="/static/js/a.js"', res.get_data(as_text=True))

    def test_custo_da_pagina_fica_pequeno(self):
        self.cliente.get("/")
        t0 = time.perf_counter()
        for _ in range(20):
            self.cliente.get("/", headers={"Accept-Encoding": "gzip"})
        self.assertLess((time.perf_counter() - t0) / 20, 0.05)


class PainelDeVerdadeTestCase(unittest.TestCase):
    """O app do painel: fase7.css com ?v em cada camada."""

    @classmethod
    def setUpClass(cls):
        import db

        cls._tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(cls._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        import app as app_mod

        cls.app = app_mod.app
        estaticos.limpar()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_fase7_css_sai_com_versao_em_cada_camada(self):
        texto = self.app.test_client().get("/static/css/fase7.css").get_data(as_text=True)
        imports = [linha for linha in texto.splitlines() if linha.startswith("@import")]
        self.assertGreater(len(imports), 50)
        for linha in imports:
            self.assertRegex(linha, r'^@import url\("/static/css/[^"?]+\?v=[0-9a-f]{12}"\);$')


if __name__ == "__main__":
    unittest.main()
