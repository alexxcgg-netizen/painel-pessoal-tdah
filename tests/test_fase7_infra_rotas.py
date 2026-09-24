"""Fase 7, Etapa 0: rotas por Blueprint com carga automatica (rotas/).

Nenhum arquivo de rota de exemplo fica no app: o modulo de teste e escrito
numa pasta temporaria acrescentada ao `rotas.__path__` so durante o teste."""

import os
import sys
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import rotas  # noqa: E402
from rotas._base import app_modulo  # noqa: E402

PIN_TESTE = "123456"


class _PastaRotasTemporaria:
    """Acrescenta uma pasta temporaria ao pacote rotas com os modulos dados e
    desfaz tudo no fim (path + sys.modules)."""

    def __init__(self, modulos: dict[str, str]):
        self.modulos = modulos

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        for nome, codigo in self.modulos.items():
            (Path(self.tmp.name) / f"{nome}.py").write_text(textwrap.dedent(codigo))
        # So a pasta temporaria: modulos reais das faixas nao interferem no teste.
        self._path_antes = list(rotas.__path__)
        rotas.__path__[:] = [self.tmp.name]
        self.caminhos_antes = set(rotas.CAMINHOS_COM_TOKEN)
        self.prefixos_antes = rotas.PREFIXOS_COM_TOKEN
        return self

    def __exit__(self, *exc):
        rotas.__path__[:] = self._path_antes
        rotas.CAMINHOS_COM_TOKEN.clear()
        rotas.CAMINHOS_COM_TOKEN.update(self.caminhos_antes)
        rotas.PREFIXOS_COM_TOKEN = self.prefixos_antes
        for nome in self.modulos:
            sys.modules.pop(f"rotas.{nome}", None)
        self.tmp.cleanup()


def _registrar_no_app(fn):
    """O app ja atendeu requisicoes de outros testes na mesma sessao do
    pytest - o Flask so aceita blueprint novo antes da primeira requisicao."""
    with patch.object(app.app, "_got_first_request", False):
        return fn(app.app)


class RegistrarTodasTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.sufixo = uuid.uuid4().hex[:8]

    def _modulo_rota(self, nome_bp: str, url: str) -> str:
        return f"""
            from flask import Blueprint, jsonify
            from rotas._base import app_modulo

            bp = Blueprint("{nome_bp}", __name__)


            @bp.route("{url}", methods=["GET", "POST"])
            def rota():
                app = app_modulo()
                corpo = app._corpo_json() if app.request.method == "POST" else {{}}
                return jsonify({{"ok": True, "eco": app._texto_seguro(corpo.get("t"))}})
            """

    def test_pacote_real_so_tem_rota_de_verdade(self):
        # Todo modulo publico real de rotas/ e uma rota de faixa (com bp), nunca exemplo.
        import importlib
        self.assertIn("_base", rotas.nomes_modulos())
        for nome in rotas.nomes_modulos():
            if not nome.startswith("_"):
                self.assertTrue(hasattr(importlib.import_module(f"rotas.{nome}"), "bp"), nome)

    def test_registra_bp_em_ordem_alfabetica_e_ignora_modulo_sem_bp(self):
        s = self.sufixo
        modulos = {
            f"zz_{s}": self._modulo_rota(f"zz_{s}", f"/api/teste-fase7/zz-{s}"),
            f"aa_{s}": self._modulo_rota(f"aa_{s}", f"/api/teste-fase7/aa-{s}"),
            f"mm_{s}": "VALOR = 1\n",  # sem bp: so importa
        }
        with _PastaRotasTemporaria(modulos):
            nomes = rotas.nomes_modulos()
            self.assertLess(nomes.index(f"aa_{s}"), nomes.index(f"mm_{s}"))
            self.assertLess(nomes.index(f"mm_{s}"), nomes.index(f"zz_{s}"))
            registrados = _registrar_no_app(rotas.registrar_todas)
            self.assertEqual(registrados, [f"aa_{s}", f"zz_{s}"])
            self.assertIn(f"rotas.mm_{s}", sys.modules)  # importado mesmo sem bp

    def test_rota_de_blueprint_exige_login_igual_as_outras(self):
        s = self.sufixo
        url = f"/api/teste-fase7/login-{s}"
        with _PastaRotasTemporaria({f"login_{s}": self._modulo_rota(f"login_{s}", url)}):
            _registrar_no_app(rotas.registrar_todas)
            client = app.app.test_client()
            # sem login: 401, igual qualquer /api/ do app.py
            self.assertEqual(client.get(url).status_code, 401)
            self.assertEqual(client.get("/api/tasks").status_code, 401)
            # com login: a rota responde e usa os helpers do app via app_modulo()
            self.assertEqual(client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)
            res = client.post(url, json={"t": "  oi  "})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json(), {"ok": True, "eco": "oi"})
            # corpo malformado continua controlado pelo helper do app
            res = client.post(url, json=[1, 2])
            self.assertEqual(res.get_json(), {"ok": True, "eco": ""})

    def test_rota_de_blueprint_sem_pin_configurado_tambem_bloqueia(self):
        s = self.sufixo
        url = f"/api/teste-fase7/sem-pin-{s}"
        with _PastaRotasTemporaria({f"sempin_{s}": self._modulo_rota(f"sempin_{s}", url)}):
            _registrar_no_app(rotas.registrar_todas)
            db.DB_PATH.unlink()
            db.init_db()  # banco novo, sem PIN
            res = app.app.test_client().get(url)
            self.assertEqual(res.status_code, 401)
            self.assertIn("PIN", res.get_json()["error"])


class RotasComTokenTestCase(unittest.TestCase):
    """Rota maquina-a-maquina declarada por blueprint (ROTAS_COM_TOKEN /
    PREFIXOS_COM_TOKEN) passa sem login; a propria rota checa o token."""

    MODULO = """
        import hmac
        from flask import Blueprint, jsonify, request

        bp = Blueprint("{nome}", __name__)
        ROTAS_COM_TOKEN = {{"{base}/tick"}}
        PREFIXOS_COM_TOKEN = ("{base}/widget/",)


        def _token_ok():
            return hmac.compare_digest(request.headers.get("X-Token", ""), "segredo-teste")


        @bp.route("{base}/tick", methods=["POST"])
        def tick():
            if not _token_ok():
                return jsonify({{"error": "token invalido"}}), 401
            return jsonify({{"ok": True}})


        @bp.route("{base}/widget/<nome>")
        def widget(nome):
            if not _token_ok():
                return jsonify({{"error": "token invalido"}}), 401
            return jsonify({{"widget": nome}})


        @bp.route("{base}/privada")
        def privada():
            return jsonify({{"segredo": 42}})
        """

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.s = uuid.uuid4().hex[:8]
        self.base = f"/api/teste-fase7-token-{self.s}"

    def _modulo(self, **extra):
        return textwrap.dedent(self.MODULO.format(nome=f"tok_{self.s}", base=self.base)) + "".join(
            f"\n{k} = {v!r}\n" for k, v in extra.items()
        )

    def test_rota_declarada_responde_sem_login_e_checa_o_proprio_token(self):
        with _PastaRotasTemporaria({f"tok_{self.s}": self._modulo()}):
            _registrar_no_app(rotas.registrar_todas)
            self.assertIn(f"{self.base}/tick", rotas.CAMINHOS_COM_TOKEN)
            client = app.app.test_client()
            # sem sessao e sem token: quem responde e a rota (401 dela), nao o login
            res = client.post(f"{self.base}/tick")
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.get_json(), {"error": "token invalido"})
            res = client.post(f"{self.base}/tick", headers={"X-Token": "segredo-teste"})
            self.assertEqual(res.status_code, 200)
            res = client.get(f"{self.base}/widget/tarefas", headers={"X-Token": "segredo-teste"})
            self.assertEqual(res.get_json(), {"widget": "tarefas"})

    def test_rota_nao_declarada_do_mesmo_blueprint_continua_exigindo_login(self):
        with _PastaRotasTemporaria({f"tok_{self.s}": self._modulo()}):
            _registrar_no_app(rotas.registrar_todas)
            client = app.app.test_client()
            res = client.get(f"{self.base}/privada")
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.get_json(), {"error": "nao autenticado"})
            self.assertFalse(rotas.rota_com_token(f"{self.base}/privada"))
            self.assertFalse(rotas.rota_com_token(f"{self.base}/tick/extra"))
            self.assertFalse(rotas.rota_com_token("/api/tasks"))
            self.assertEqual(client.get("/api/tasks").status_code, 401)

    def test_rota_com_token_funciona_mesmo_sem_pin_configurado(self):
        with _PastaRotasTemporaria({f"tok_{self.s}": self._modulo()}):
            _registrar_no_app(rotas.registrar_todas)
            db.DB_PATH.unlink()
            db.init_db()
            res = app.app.test_client().post(f"{self.base}/tick", headers={"X-Token": "segredo-teste"})
            self.assertEqual(res.status_code, 200)

    def test_tupla_antiga_do_app_continua_liberada(self):
        res = app.app.test_client().post("/api/atalho/capturar", json={"text": "x"})
        self.assertNotEqual(res.get_json().get("error"), "nao autenticado")

    def test_prefixo_largo_demais_ou_invalido_derruba(self):
        for extra in (
            {"PREFIXOS_COM_TOKEN": ("/",)},
            {"PREFIXOS_COM_TOKEN": ("/api/",)},
            {"PREFIXOS_COM_TOKEN": ("/api",)},
            {"PREFIXOS_COM_TOKEN": ("/ab",)},
            {"PREFIXOS_COM_TOKEN": "/widget/"},
            {"ROTAS_COM_TOKEN": {"api/sem-barra"}},
            {"ROTAS_COM_TOKEN": "/api/string-solta"},
            # cobre /api/tasks (rota de app.py, nao do blueprint)
            {"PREFIXOS_COM_TOKEN": ("/api/tas",)},
        ):
            with self.subTest(extra=extra):
                self.s = uuid.uuid4().hex[:8]
                self.base = f"/api/teste-fase7-token-{self.s}"
                with _PastaRotasTemporaria({f"tok_{self.s}": self._modulo(**extra)}):
                    with self.assertRaises(ValueError):
                        _registrar_no_app(rotas.registrar_todas)
                    self.assertFalse(rotas.rota_com_token("/api/tasks"))


class AppModuloTestCase(unittest.TestCase):
    def test_devolve_o_modulo_app_carregado(self):
        self.assertIs(app_modulo(), app)

    def test_prefere_main_quando_app_roda_como_script(self):
        falso_main = type(sys)("__main__")
        falso_main._verificar_autenticacao = lambda: None
        with patch.dict(sys.modules, {"__main__": falso_main}):
            self.assertIs(app_modulo(), falso_main)

    def test_sem_app_carregado_erro_claro(self):
        falso_main = type(sys)("__main__")
        with patch.dict(sys.modules, {"__main__": falso_main}):
            del sys.modules["app"]
            with self.assertRaises(RuntimeError):
                app_modulo()
        self.assertIs(sys.modules["app"], app)

    def test_app_py_chama_registrar_todas(self):
        codigo = Path(app.__file__).read_text()
        pos_chamada = codigo.index("rotas.registrar_todas(app)")
        self.assertLess(pos_chamada, codigo.index('if __name__ == "__main__":'))


if __name__ == "__main__":
    unittest.main()
