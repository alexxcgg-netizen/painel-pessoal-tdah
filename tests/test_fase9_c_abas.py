# tests/test_fase9_c_abas.py - Fase 9 (faixa C-abas): 8 abas viram 4 (Hoje,
# Tarefas, Financas, Vida) + folha de Configuracoes. Conteudo antigo das abas
# Painel/Construtora/Aviacao/Assistente foi movido pra dentro das 4 abas que
# ficam (contrato: docs/fase9-mapa-abas.md e a instrucao da faixa) - nada foi
# apagado, so mudou de lugar. Aqui so testamos o HTML renderizado.
import os
import re
import tempfile
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


class Fase9CAbasTestCase(unittest.TestCase):
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

    # ---- as 4 abas continuam existindo ----

    def test_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_quatro_abas_presentes(self):
        for tab_id in ("tab-hoje", "tab-tarefas", "tab-gastos", "tab-vida"):
            self.assertIn(f'id="{tab_id}"', self.corpo)

    # ---- as 4 abas antigas sumiram ----

    def test_abas_antigas_nao_existem_mais(self):
        for tab_id in ("tab-painel", "tab-aviacao", "tab-construtora", "tab-assistente"):
            self.assertNotIn(f'id="{tab_id}"', self.corpo)

    # ---- Hoje recebe resumo/agenda/plano/devo-sair/fechamento (Painel) + avisos (Assistente) ----

    def test_tab_hoje_contem_secoes_migradas(self):
        inicio = self.corpo.index('id="tab-hoje"')
        fim = self.corpo.index('id="tab-vida"')
        bloco = self.corpo[inicio:fim]
        # ja existia
        self.assertIn('id="caixa-assistente"', bloco)
        self.assertIn('id="chat-mensagens"', bloco)
        # migrado do Painel
        self.assertIn('id="viagem-btn"', bloco)  # devo-sair.html
        self.assertIn('id="plano-btn"', bloco)  # plano-do-dia.html
        self.assertIn("Agend", bloco)  # agenda-de-hoje.html (titulo "Agend. de Hoje")
        # migrado do Assistente
        self.assertIn('id="avisos-lista"', bloco)
        # "caixa" nao pode estar duplicada (so a injecao dinamica #caixa-assistente)
        self.assertNotIn('id="secao-caixa-assistente"', bloco)

    # ---- Vida recebe Aviacao inteira no topo + saude/medicamentos/etc (Painel) no fim ----

    def test_tab_vida_secao_aviacao_no_topo(self):
        inicio_vida = self.corpo.index('id="tab-vida"')
        inicio_aviacao = self.corpo.index('id="secao-aviacao"')
        inicio_primeira_secao_antiga = self.corpo.index('id="habito-abrir-btn"')
        self.assertGreater(inicio_aviacao, inicio_vida)
        self.assertLess(inicio_aviacao, inicio_primeira_secao_antiga)

    def test_tab_vida_contem_secoes_migradas(self):
        inicio = self.corpo.index('id="tab-vida"')
        fim = self.corpo.index('id="tab-tarefas"')
        bloco = self.corpo[inicio:fim]
        # aviacao
        self.assertIn('id="voo-abrir-btn"', bloco)
        # migrado do Painel
        self.assertIn('id="lista-medicamentos"', bloco)
        self.assertIn('id="lista-diario-decisoes"', bloco)
        self.assertIn('id="brain-dump-texto"', bloco)
        self.assertIn('id="lista-esperas"', bloco)
        self.assertIn('data-secao-id="painel-memoria-rotina-planos"', bloco)

    # ---- Financas recebe Construtora inteira no fim ----

    def test_tab_gastos_secao_construtora_no_fim(self):
        inicio_gastos = self.corpo.index('id="tab-gastos"')
        inicio_construtora = self.corpo.index('id="secao-construtora"')
        # #tab-gastos e a ultima aba de templates/index.html - o fim dela e onde
        # comeca a navegacao (navegacao.html, incluido logo depois do </main>).
        fim_gastos = self.corpo.index('id="sheet-config"')
        self.assertGreater(inicio_construtora, inicio_gastos)
        self.assertLess(inicio_construtora, fim_gastos)
        bloco = self.corpo[inicio_construtora:fim_gastos]
        self.assertIn('id="construtora-card"', bloco)
        self.assertIn('id="lista-contas-a-vencer"', bloco)

    # ---- folha de Configuracoes (custo de IA + regras) ----

    def test_sheet_config_existe_com_custo_ia_e_regras(self):
        self.assertIn('id="sheet-config"', self.corpo)
        inicio = self.corpo.index('id="sheet-config"')
        # o sheet e o ultimo bloco grande do body - pega ate o fim do documento
        bloco = self.corpo[inicio:]
        self.assertIn('id="custo-ia-v2-box"', bloco)
        self.assertIn('id="regras-lista"', bloco)

    def test_botao_config_no_cabecalho(self):
        # Fase 9 (P-topo): o <header> ganhou uma classe (layout da linha 1,
        # secoes/topo.css) - o teste so procurava a tag sem atributo nenhum.
        inicio = self.corpo.index("<header")
        fim = self.corpo.index("</header>")
        cabecalho = self.corpo[inicio:fim]
        self.assertIn('id="btn-config"', cabecalho)
        self.assertIn('data-abre-sheet="sheet-config"', cabecalho)
        self.assertIn("Configura", cabecalho)

    # ---- nenhum id duplicado na pagina inteira ----

    def test_nenhum_id_duplicado(self):
        ids = re.findall(r'\sid="([^"]+)"', self.corpo)
        vistos = {}
        for i in ids:
            vistos[i] = vistos.get(i, 0) + 1
        duplicados = {i: n for i, n in vistos.items() if n > 1}
        self.assertEqual(duplicados, {}, f"ids duplicados: {duplicados}")


if __name__ == "__main__":
    unittest.main()
