"""Fase 8 (D5): a "Visao do dia" (aba Hoje) comeca recolhida - so um
indicador pequeno (relogio + hora do proximo item, ou "hoje") aparece de
cara; tocar expande a visao completa (Dia/Semana/Mes, Em foco agora, linha
do tempo) que ja existia antes desta faixa - conteudo continua tudo no HTML
(nada apagado), so escondido pelo .secao-recolhivel ate abrir.
"""
import os
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

PIN_TESTE = "135790"


class VisaoDoDiaRecolhivelTestCase(unittest.TestCase):
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

    def test_botao_comeca_recolhido_com_aria_expanded_false(self):
        self.assertIn('data-secao-id="visao-dia-hoje"', self.corpo)
        self.assertIn('data-aberto="false"', self.corpo)
        idx_secao = self.corpo.index('data-secao-id="visao-dia-hoje"')
        idx_btn = self.corpo.index("secao-cabecalho", idx_secao)
        trecho_btn = self.corpo[idx_btn : idx_btn + 400]
        self.assertIn('aria-expanded="false"', trecho_btn)

    def test_indicador_pequeno_no_cabecalho(self):
        self.assertIn('id="visao-dia-indicador"', self.corpo)
        self.assertIn('id="visao-dia-indicador-texto"', self.corpo)
        self.assertIn(">hoje<", self.corpo)

    def test_conteudo_completo_continua_no_html(self):
        # nada foi apagado: seletor Dia/Semana/Mes, foco, resumo e linha do
        # tempo continuam todos presentes, so dentro do .secao-conteudo.
        for trecho in (
            'id="visao-dia-conteudo"',
            'data-periodo="dia"',
            'data-periodo="semana"',
            'data-periodo="mes"',
            'id="visao-dia-status"',
            'id="visao-dia-foco"',
            'id="visao-dia-foco-hiperfoco"',
            'id="visao-dia-foco-concluir"',
            'id="visao-dia-resumo"',
            'id="visao-dia-timeline"',
            'id="visao-dia-periodo-agregado"',
        ):
            self.assertIn(trecho, self.corpo, f"{trecho} sumiu do HTML")

    def test_alvo_de_toque_minimo_44px_no_css(self):
        css = Path("static/css/ui/componentes/secao.css").read_text(encoding="utf-8")
        self.assertIn("min-height: 44px", css)


if __name__ == "__main__":
    unittest.main()
