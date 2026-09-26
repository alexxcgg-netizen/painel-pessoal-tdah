import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
os.environ.setdefault("OPENAI_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

RAIZ = Path(__file__).resolve().parent.parent
CSS = (RAIZ / "static" / "css" / "login.css").read_text(encoding="utf-8")


def _pin_caixas_ok(html, quantidade_esperada):
    caixas = re.findall(r'<input[^>]*class="pin-caixa"[^>]*>', html)
    assert len(caixas) == quantidade_esperada, f"esperado {quantidade_esperada} caixas, achou {len(caixas)}"
    for caixa in caixas:
        assert 'maxlength="1"' in caixa
    return caixas


class LoginVisualTestCase(unittest.TestCase):
    """So cobre a tela (HTML/CSS) do redesenho - logica de auth fica em test_auth.py/test_app.py."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.client = app.app.test_client()

    def tearDown(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_login_get_sem_pin_configurado_redireciona_para_configurar(self):
        # sem PIN no banco, /login redireciona pro fluxo de primeiro acesso
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/configurar-pin", res.headers["Location"])

    def test_configurar_pin_get_sem_pin_renderiza_dois_grupos(self):
        res = self.client.get("/configurar-pin")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('id="pin-grupo"', html)
        self.assertIn('id="confirmacao-grupo"', html)
        self.assertIn('id="mensagem"', html)
        self.assertIn('id="espera"', html)
        _pin_caixas_ok(html, 12)  # 6 do PIN + 6 da confirmacao

    def test_login_get_com_pin_configurado_renderiza_seis_caixas(self):
        conn = db.get_db()
        auth.definir_pin(conn, "123456", "123456")
        conn.commit()
        conn.close()

        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('id="pin-grupo"', html)
        self.assertIn('id="mensagem"', html)
        self.assertIn('id="espera"', html)
        _pin_caixas_ok(html, 6)

    def test_css_sem_verde_antigo_nem_aurora(self):
        self.assertNotIn("#41aa75", CSS)
        self.assertNotIn("aurora", CSS.lower())

    def test_css_fundo_preto_puro(self):
        self.assertRegex(CSS, r"--fundo:\s*#000\b")
        self.assertIn("background: var(--fundo)", CSS)

    def test_css_sem_sombra_luminosa(self):
        # nenhuma linha de box-shadow/text-shadow pode referenciar cor de
        # destaque/perigo (isso seria glow/neon) - so preto/neutro e permitido
        self.assertNotIn("text-shadow", CSS)
        for linha in CSS.splitlines():
            if "box-shadow" in linha:
                self.assertNotIn("acento", linha)
                self.assertNotIn("perigo", linha)
                self.assertNotIn("#8e8ea0", linha)
                self.assertNotIn("#e5746f", linha)

    def test_css_usa_cor_de_acento_correta_do_painel(self):
        # Faixa vis/C1 (paleta "Gelo preto"): acento cinza -> azul-gelo,
        # perigo -> --cor-saida (mesmo tom em tokens.css).
        self.assertIn("--acento: #bfe6ff", CSS)
        self.assertIn("--perigo: #f47671", CSS)

    def test_css_reduced_motion_zera_animacoes(self):
        self.assertIn("prefers-reduced-motion: reduce", CSS)


if __name__ == "__main__":
    unittest.main()
