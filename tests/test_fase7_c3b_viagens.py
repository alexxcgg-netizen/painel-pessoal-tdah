"""Fase 7 C3b: guarda da estrutura visual de Viagens, Lugares, Cotacoes e Aviacao.

So le os arquivos (sem servidor): confere que as secoes seguem o contrato de UI
(docs/agentes/fase7-visual.md) e que as regressoes achadas na auditoria nao voltam.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TPL = RAIZ / "templates" / "secoes"
SHEETS = {
    "vida/viagens.html": "viagem-sheet",
    "vida/lugares.html": "lugar-sheet",
    "construtora/cotacoes.html": "cotacao-sheet",
    "aviacao/registrar-voo.html": "voo-sheet",
}
RECOLHIVEIS = {
    "vida/viagens.html": "vida-viagens",
    "vida/lugares.html": "vida-lugares",
    "construtora/cotacoes.html": "construtora-cotacoes",
    "aviacao/proximos-voos.html": "aviacao-proximos-voos",
    "aviacao/metar.html": "aviacao-metar",
}


def _ler(rel):
    return (TPL / rel).read_text(encoding="utf-8")


def _bloco_sheet(html, sheet_id):
    inicio = html.index(f'id="{sheet_id}"')
    return html[inicio:]


class EstruturaC3bTestCase(unittest.TestCase):
    def test_secoes_longas_sao_recolhiveis_e_ids_unicos(self):
        vistos = set()
        for rel, secao_id in RECOLHIVEIS.items():
            html = _ler(rel)
            self.assertIn(f'class="secao-recolhivel" data-aberto="true" data-secao-id="{secao_id}"', html, rel)
            self.assertIn('class="secao-cabecalho" aria-expanded="true"', html, rel)
            self.assertIn('class="secao-conteudo"', html, rel)
            self.assertNotIn(secao_id, vistos)
            vistos.add(secao_id)
        # data-secao-id e unico no app inteiro (a chave do localStorage depende disso)
        todos = []
        for arq in TPL.rglob("*.html"):
            todos += re.findall(r'data-secao-id="([^"]+)"', arq.read_text(encoding="utf-8"))
        for secao_id in RECOLHIVEIS.values():
            self.assertEqual(todos.count(secao_id), 1, secao_id)

    def test_sheets_deixam_o_v0d_montar_a_estrutura(self):
        for rel, sheet_id in SHEETS.items():
            html = _ler(rel)
            self.assertIn(f'<div class="bottom-sheet" id="{sheet_id}"', html, rel)
            bloco = _bloco_sheet(html, sheet_id)
            # painel escrito a mao faz o V0d pular o fundo escurecido/alca/toque-fora
            self.assertNotIn("bottom-sheet-painel", bloco, rel)
            self.assertIn('class="sheet-titulo"', bloco, rel)
            self.assertRegex(bloco, r'class="btn btn-primario">Salvar \w+', rel)
            self.assertIn('class="btn btn-secundario">Cancelar', bloco, rel)
            self.assertIn('class="campo-rotulo"', bloco, rel)

    def test_botao_adicionar_sem_icone_duplicado(self):
        for rel in SHEETS:
            html = _ler(rel)
            m = re.search(r'<button type="button" id="[a-z-]+-abrir-btn" class="btn btn-adicionar">([^<]*)</button>', html)
            self.assertIsNotNone(m, rel)  # o "+" vem do ::before do componente, sem <svg> dentro

    def test_registrar_voo_nao_fica_sempre_aberto_na_aba(self):
        html = _ler("aviacao/registrar-voo.html")
        self.assertLess(html.index('id="voo-abrir-btn"'), html.index('id="voo-form"'))
        self.assertIn('id="voo-form"', _bloco_sheet(html, "voo-sheet"))

    def test_css_local_do_sheet_foi_removido(self):
        for rel in ("vida/viagens.css", "vida/lugares.css", "construtora/cotacoes.css"):
            css = (RAIZ / "static" / "css" / "secoes" / rel).read_text(encoding="utf-8")
            self.assertNotIn(".bottom-sheet-painel {", css, rel)
            self.assertNotIn("rgba(0, 0, 0, 0.55)", css, rel)
            self.assertNotIn("!important", css, rel)

    def test_leaflet_mantem_sri_e_popup_por_textcontent(self):
        js = (RAIZ / "static" / "js" / "secoes" / "vida" / "lugares.js").read_text(encoding="utf-8")
        self.assertIn('LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="', js)
        self.assertIn('LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="', js)
        self.assertIn("popup.textContent = l.nome", js)
        self.assertIn("bindPopup(popup)", js)

    def test_mapa_leaflet_tem_altura_propria(self):
        css = (RAIZ / "static" / "css" / "secoes" / "vida" / "lugares.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"#lista-lugares \.lugar-mapa\.leaflet-container \{[^}]*height: 180px")


if __name__ == "__main__":
    unittest.main()
