"""Fase 9 (C1): guarda dos tokens de cor/forma da direcao "Conversa".

Confere que:
- static/css/ui/tokens.css tem a paleta escolhida no laboratorio visual
  (docs/fase9-lab2/d01.js, direcao 1 "Conversa": fundo #0e0f0e, acento
  #159C82) e os tokens novos (--cor-texto-2, --cor-acento-suave, --cor-alerta,
  --cor-alerta-suave, --fonte-base, --raio-cartao/--raio-bolha/--raio-pequeno);
- static/css aponta --bg/--surface*/--border/--text*/--accent continuam
  resolvendo pros tokens (nao redeclarados como hex fixo no :root que vale);
- body usa --fonte-base (Inter);
- os arquivos mexidos por esta faixa (tokens.css, style.css) nao tem mais
  text-shadow/box-shadow "glow" colorido nos trechos globais (--glass-glow,
  .tab-btn.active, .chat-bolha.user) nem o gradiente/aurora de fundo do
  body/#app.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKENS_CSS = (RAIZ / "static" / "css" / "ui" / "tokens.css").read_text(encoding="utf-8")
STYLE_CSS = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
HEAD_HTML = (RAIZ / "templates" / "head.html").read_text(encoding="utf-8")


class TokensCorBaseTestCase(unittest.TestCase):
    def test_cor_bg_e_a_da_direcao_conversa(self):
        self.assertIn("--cor-bg: #0e0f0e;", TOKENS_CSS)

    def test_acento_e_a_da_direcao_conversa(self):
        self.assertIn("--cor-acento: #159c82;", TOKENS_CSS.lower())

    def test_superficies_e_borda(self):
        self.assertIn("--cor-superficie: #111312;", TOKENS_CSS)
        self.assertIn("--cor-superficie-2: #1a1c1b;", TOKENS_CSS)
        self.assertIn("--cor-borda: #1f211f;", TOKENS_CSS)

    def test_tokens_novos_existem(self):
        for nome in (
            "--cor-texto-2",
            "--cor-acento-suave",
            "--cor-alerta",
            "--cor-alerta-suave",
            "--fonte-base",
            "--raio-cartao",
            "--raio-bolha",
            "--raio-pequeno",
            "--raio-pilula",
        ):
            self.assertIn(nome, TOKENS_CSS, f"token {nome} nao encontrado em tokens.css")

    def test_raios_da_direcao_conversa(self):
        self.assertIn("--raio-cartao: 14px;", TOKENS_CSS)
        self.assertIn("--raio-bolha: 14px;", TOKENS_CSS)
        self.assertIn("--raio-pequeno: 9px;", TOKENS_CSS)
        self.assertIn("--raio-pilula: 99px;", TOKENS_CSS)

    def test_fonte_base_e_inter_com_fallback(self):
        m = re.search(r'--fonte-base:\s*([^;]+);', TOKENS_CSS)
        self.assertIsNotNone(m, "--fonte-base nao declarado")
        valor = m.group(1)
        self.assertIn("Inter", valor)
        # tem que ter fallback de sistema, nao so "Inter" sozinho
        self.assertTrue(
            any(f in valor for f in ("system-ui", "-apple-system", "sans-serif")),
            "fallback de sistema ausente em --fonte-base",
        )

    def test_nomes_antigos_continuam_apontando_pros_tokens(self):
        """style.css so pode ter uma unica fonte de verdade pra --bg/--surface*/
        --border/--text*/--accent no :root principal: os tokens novos
        (via var(--cor-*)) declarados em tokens.css, carregado depois. O
        :root do proprio style.css so guarda o FALLBACK (comentado como tal)
        - garante que esse comentario de fallback continua ali (senao alguem
        removeu o encadeamento e --bg passou a nao vir mais dos tokens)."""
        self.assertIn("tokens.css", STYLE_CSS)
        self.assertIn("--bg: var(--cor-bg);", TOKENS_CSS)
        self.assertIn("--surface: var(--cor-superficie);", TOKENS_CSS)
        self.assertIn("--surface-2: var(--cor-superficie-2);", TOKENS_CSS)
        self.assertIn("--border: var(--cor-borda);", TOKENS_CSS)
        self.assertIn("--text: var(--cor-texto);", TOKENS_CSS)
        self.assertIn("--text-muted: var(--cor-texto-fraco);", TOKENS_CSS)
        self.assertIn("--accent: var(--cor-acento);", TOKENS_CSS)


class SemGlowNemAuroraTestCase(unittest.TestCase):
    def test_body_usa_fonte_base(self):
        m = re.search(r"\bbody\s*\{[^}]*\}", STYLE_CSS, re.DOTALL)
        self.assertIsNotNone(m, "regra body{} nao encontrada")
        self.assertIn("--fonte-base", m.group(0))

    def test_inter_carregada_no_head(self):
        self.assertIn("Inter", HEAD_HTML)
        self.assertIn("fonts.googleapis.com", HEAD_HTML)

    def test_glass_glow_global_neutralizado(self):
        # a definicao default (:root, --glass-tint = --accent) nao pode mais
        # gerar um radial-gradient colorido.
        m = re.search(r":root\s*\{.*?--glass-glow:\s*([^;]+);", STYLE_CSS, re.DOTALL)
        self.assertIsNotNone(m, "--glass-glow do :root nao encontrado")
        self.assertEqual(m.group(1).strip(), "none")

    def test_tab_btn_active_sem_led(self):
        m = re.search(r"\.tab-btn\.active\s*\{[^}]*\}", STYLE_CSS, re.DOTALL)
        self.assertIsNotNone(m, "regra .tab-btn.active nao encontrada")
        bloco = m.group(0)
        m_shadow = re.search(r"box-shadow:\s*([^;]+);", bloco)
        self.assertIsNotNone(m_shadow, "box-shadow nao encontrado em .tab-btn.active")
        shadow = m_shadow.group(1)
        self.assertNotIn("0 0 16px", shadow)
        self.assertNotIn("color-mix", shadow)

    def test_chat_bolha_user_sem_glow_de_acento(self):
        m = re.search(r"\.chat-bolha\.user\s*\{[^}]*\}", STYLE_CSS, re.DOTALL)
        self.assertIsNotNone(m, "regra .chat-bolha.user nao encontrada")
        self.assertNotIn("var(--accent)", m.group(0))

    def test_aurora_sem_gradiente_de_fundo(self):
        for seletor in (r"\.aurora\s*\{", r"\.aurora::before\s*\{", r"\.aurora::after\s*\{"):
            m = re.search(seletor + r"[^}]*\}", STYLE_CSS, re.DOTALL)
            self.assertIsNotNone(m, f"regra {seletor} nao encontrada")
            bloco = m.group(0)
            self.assertNotIn("radial-gradient", bloco)
            self.assertNotIn("linear-gradient", bloco)
            self.assertIn("background: none", bloco)


if __name__ == "__main__":
    unittest.main()
