# tests/test_fase9_p_topo.py - Fase 9 (faixa P-topo): topo (cabecalho + captura)
# cai de ~1/3 da tela pra ~2 linhas (direcao "Conversa"). Contrato: nenhum id
# antigo sumiu (so mudou de lugar - os 5 botoes do cabecalho foram pra dentro da
# folha de Configuracoes, comando de voz/hiperfoco viraram icones/popover na
# linha 1), #caixa-assistente foi pra depois de #conversa-hoje (recolhida por
# padrao). Mesmo contrato de tests/test_fase9_c2.py e tests/test_fase9_c_abas.py:
# so testamos o HTML renderizado, nao as rotas de dados.
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


class Fase9PTopoTestCase(unittest.TestCase):
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

    def test_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    # ---- linha 1 do topo: icones novos ----

    def test_linha1_tem_relogio_voz_hiperfoco_config(self):
        inicio = self.corpo.index("<header")
        fim = self.corpo.index("</header>")
        cabecalho = self.corpo[inicio:fim]
        self.assertIn('id="btn-visao-dia"', cabecalho)
        self.assertIn('id="comando-voz-btn"', cabecalho)
        self.assertIn('id="topo-aviso-critico"', cabecalho)
        self.assertIn('id="hiperfoco-toggle-btn"', cabecalho)
        self.assertIn('id="btn-config"', cabecalho)
        self.assertIn('data-abre-sheet="sheet-config"', cabecalho)

    def test_titulo_curto_uma_linha(self):
        inicio = self.corpo.index("<header")
        fim = self.corpo.index("</header>")
        cabecalho = self.corpo[inicio:fim]
        self.assertIn("<h1>", cabecalho)

    # ---- captura (linha 2) continua com os mesmos ids/comportamento ----

    def test_captura_mesmos_ids(self):
        self.assertIn('id="captura"', self.corpo)
        self.assertIn('id="captura-input"', self.corpo)
        self.assertIn('id="captura-btn"', self.corpo)

    # ---- hiperfoco: mesmos ids, agora dentro de um popover no cabecalho ----

    def test_hiperfoco_ids_presentes(self):
        for id_antigo in (
            "hiperfoco-box",
            "hiperfoco-inativo",
            "hiperfoco-ativo",
            "hiperfoco-restante",
            "hiperfoco-parar",
        ):
            self.assertIn(f'id="{id_antigo}"', self.corpo, f"id antigo sumiu: {id_antigo}")
        self.assertEqual(self.corpo.count('data-minutos="25"'), 1)
        self.assertEqual(self.corpo.count('data-minutos="50"'), 1)
        self.assertEqual(self.corpo.count('data-minutos="90"'), 1)

    def test_hiperfoco_box_dentro_do_cabecalho(self):
        inicio = self.corpo.index("<header")
        fim = self.corpo.index("</header>")
        cabecalho = self.corpo[inicio:fim]
        self.assertIn('id="hiperfoco-box"', cabecalho)

    # ---- os 5 botoes do cabecalho antigo viraram linhas dentro do sheet ----

    def test_botoes_antigos_saem_do_header(self):
        inicio = self.corpo.index("<header")
        fim = self.corpo.index("</header>")
        cabecalho = self.corpo[inicio:fim]
        for id_antigo in (
            "silencio-btn",
            "modo-viagem-btn",
            "modo-visitante-btn",
            "backup-btn",
            "logout-btn",
        ):
            self.assertNotIn(f'id="{id_antigo}"', cabecalho, f"{id_antigo} ainda esta no <header>")

    def test_botoes_antigos_dentro_do_sheet_config(self):
        inicio = self.corpo.index('id="sheet-config"')
        bloco = self.corpo[inicio:]
        for id_antigo in (
            "silencio-btn",
            "silencio-painel",
            "modo-viagem-btn",
            "modo-viagem-painel",
            "modo-visitante-btn",
            "modo-visitante-painel",
            "backup-btn",
            "backup-painel",
            "logout-btn",
        ):
            self.assertIn(f'id="{id_antigo}"', bloco, f"id antigo sumiu: {id_antigo}")

    def test_uso_custo_saiu_do_topo(self):
        # "gasto com IA" so aparece agora dentro da folha (custo-ia-v2-box) -
        # o antigo <p id="uso-custo"> do cabecalho nao existe mais.
        self.assertNotIn('id="uso-custo"', self.corpo)
        self.assertIn('id="custo-ia-v2-box"', self.corpo)

    # ---- #caixa-assistente foi pra depois de #conversa-hoje ----

    def test_caixa_assistente_depois_da_conversa(self):
        self.assertIn('<div id="caixa-assistente"></div>', self.corpo)
        pos_conversa = self.corpo.index('id="conversa-hoje"')
        pos_caixa = self.corpo.index('id="caixa-assistente"')
        self.assertGreater(pos_caixa, pos_conversa, "#caixa-assistente devia vir depois de #conversa-hoje")

    def test_mensagem_de_pendencias_na_conversa(self):
        self.assertIn('id="conversa-pendencias-linha"', self.corpo)
        self.assertIn('id="conversa-pendencias"', self.corpo)
        pos_conversa = self.corpo.index('id="conversa-hoje"')
        pos_pendencias = self.corpo.index('id="conversa-pendencias-linha"')
        pos_caixa = self.corpo.index('id="caixa-assistente"')
        self.assertGreater(pos_pendencias, pos_conversa)
        self.assertLess(pos_pendencias, pos_caixa)

    # ---- nenhum id duplicado na pagina inteira (mesmo contrato de test_fase9_c_abas) ----

    def test_nenhum_id_duplicado(self):
        ids = re.findall(r'\sid="([^"]+)"', self.corpo)
        vistos = {}
        for i in ids:
            vistos[i] = vistos.get(i, 0) + 1
        duplicados = {i: n for i, n in vistos.items() if n > 1}
        self.assertEqual(duplicados, {}, f"ids duplicados: {duplicados}")


if __name__ == "__main__":
    unittest.main()
