"""Fase 9 - volta ao painel antigo (pedido do dono), com a aba Financas nova.

Garante: as 8 abas antigas; Financas com o topo novo e "Ultimos dias" recolhivel; e os dois
bugs antigos que deixavam o painel ilegivel nao voltam (comentario de CSS que fechava cedo e
anulava --cor-bg; bancos.css preso a aba #tab-bancos, que nao existe mais)."""
import glob
import re

from tests.test_fase9_c3 import _BaseTestCase  # noqa: F401  (reusa banco temporario + login)


def _sem_comentarios(texto):
    return re.sub(r"/\*.*?\*/", "", texto, flags=re.S)


def test_nenhum_comentario_css_fecha_antes_da_hora():
    ruins = [c for c in glob.glob("static/css/**/*.css", recursive=True)
             if "*/" in _sem_comentarios(open(c, encoding="utf-8").read())]
    assert ruins == []


def test_css_nao_aponta_para_aba_bancos_extinta():
    ruins = [c for c in glob.glob("static/css/**/*.css", recursive=True)
             if "#tab-bancos" in _sem_comentarios(open(c, encoding="utf-8").read())]
    assert ruins == []


class VoltaPainelTestCase(_BaseTestCase):
    def test_oito_abas_antigas_e_financas_nova(self):
        corpo = self.client.get("/").get_data(as_text=True)
        abas = re.findall(r'class="tab-btn[^"]*"[^>]*data-tab="([a-z]+)"', corpo) or re.findall(
            r'data-tab="([a-z]+)"[^>]*class="tab-btn', corpo)
        # R1 (reformulacao): barra de 5 - painel/vida/construtora/aviacao continuam
        # existindo, abertos pela tela Mais (data-abre-tela) em vez de botao na barra.
        for aba in ("hoje", "painel", "vida", "tarefas", "gastos", "construtora", "aviacao", "assistente"):
            self.assertTrue(f'data-tab="{aba}"' in corpo or f'data-abre-tela="{aba}"' in corpo, aba)
            self.assertIn(f'id="tab-{aba}"', corpo)
        self.assertIn('id="fc-card-ultimos-dias"', corpo)
        self.assertRegex(corpo, r'<details class="fc-card" id="fc-card-ultimos-dias">')
