# tests/test_fase9_c2.py - Fase 9 (faixa C2 "Hoje"): topo da aba Hoje vira uma
# conversa (mensagens do assistente com cartoes, sem IA) e a pilha antiga de secoes
# continua abaixo, cada uma recolhida por padrao - nada some (mesmo contrato de
# tests/test_fase9_ui.py: so testamos o HTML renderizado, nao as rotas de dados,
# que sao de outras faixas).
import os
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


class Fase9C2TestCase(unittest.TestCase):
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

    def test_conversa_hoje_existe_e_vem_antes_das_secoes_antigas(self):
        self.assertIn('id="conversa-hoje"', self.corpo)
        pos_conversa = self.corpo.index('id="conversa-hoje"')
        pos_tab_hoje = self.corpo.index('id="tab-hoje"')
        self.assertGreater(pos_conversa, pos_tab_hoje, "conversa-hoje devia estar dentro de #tab-hoje")
        # todo id de secao antiga vem DEPOIS da conversa (contrato: conversa no topo,
        # pilha antiga recolhida abaixo)
        for id_antigo in ("sobrecarga-box", "rotina-box", "checkin-box", "essencial-box"):
            self.assertIn(f'id="{id_antigo}"', self.corpo)
            pos_antigo = self.corpo.index(f'id="{id_antigo}"')
            self.assertGreater(pos_antigo, pos_conversa, f"{id_antigo} devia vir depois de #conversa-hoje")

    def test_cartoes_da_conversa_presentes(self):
        self.assertIn('id="card-gasto-mes"', self.corpo)
        self.assertIn('id="gasto-valor"', self.corpo)
        self.assertIn('id="gasto-grafico"', self.corpo)
        self.assertIn('id="gasto-hoje"', self.corpo)
        self.assertIn('id="gasto-fatura"', self.corpo)
        self.assertIn('id="gasto-conta"', self.corpo)
        self.assertIn('id="card-foco-agora"', self.corpo)
        self.assertIn('id="foco-texto"', self.corpo)
        self.assertIn('id="card-proximos"', self.corpo)
        self.assertIn('id="proximos-lista"', self.corpo)

    def test_chips_de_sugestao_presentes(self):
        self.assertIn('id="conversa-chips"', self.corpo)
        self.assertIn("O que tenho agora?", self.corpo)
        self.assertIn("Quanto gastei hoje?", self.corpo)
        self.assertIn("Planejar o dia", self.corpo)

    def test_chat_continua_logo_apos_a_conversa(self):
        self.assertIn('id="chat-mensagens"', self.corpo)
        self.assertIn('id="chat-form"', self.corpo)
        pos_conversa = self.corpo.index('id="conversa-hoje"')
        pos_chat = self.corpo.index('id="chat-mensagens"')
        pos_primeira_secao_antiga = self.corpo.index('data-secao-id="hoje-saudacao"')
        self.assertGreater(pos_chat, pos_conversa)
        self.assertLess(pos_chat, pos_primeira_secao_antiga)

    def test_secoes_antigas_continuam_presentes_e_recolhidas(self):
        # nenhum id antigo sumiu (mesmas secoes de antes, so agora dentro de
        # .secao-recolhivel com data-aberto="false")
        ids_antigos = [
            "sobrecarga-box",
            "previa-noite-box",
            "rotina-box",
            "checkin-box",
            "essencial-box",
            "essencial-modo-btn",
            "essencial-lista",
            "fechamento-box",
        ]
        for id_antigo in ids_antigos:
            self.assertIn(f'id="{id_antigo}"', self.corpo, f"id antigo sumiu: {id_antigo}")

        secoes_recolhidas = [
            "hoje-saudacao",
            "hoje-sobrecarga",
            "hoje-previa-noite",
            "hoje-rotina",
            "hoje-checkin",
            "hoje-essencial",
            "hoje-resumo",
            "hoje-agenda",
            "hoje-plano-do-dia",
            "hoje-devo-sair",
            "hoje-fechamento",
            "hoje-avisos-assistente",
        ]
        for secao_id in secoes_recolhidas:
            self.assertIn(f'data-secao-id="{secao_id}"', self.corpo, f"secao recolhivel faltando: {secao_id}")
        self.assertEqual(self.corpo.count('data-aberto="false" data-secao-id="hoje-'), len(secoes_recolhidas))

    def test_visao_do_dia_e_caixa_assistente_continuam(self):
        self.assertIn('id="caixa-assistente"', self.corpo)
        self.assertIn('data-secao-id="visao-dia-hoje"', self.corpo)

    def test_avisos_assistente_migrados_continuam(self):
        self.assertIn('id="secao-avisos-assistente"', self.corpo)


if __name__ == "__main__":
    unittest.main()
