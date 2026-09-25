"""M1 (uso): "Hoje mais enxuto + Aviacao na barra".

Hoje fica so com chat, foco atual (essencial + hiperfoco) e agenda do dia
(visao do dia). Saudacao, sobrecarga e o resto do antigo Hoje (previa-noite,
rotina, checkin) sobem para o topo do Painel, na ordem em que estavam.
Aviacao sobe na barra de navegacao pra logo depois de Painel.

Mesmo padrao de fixture de tests/test_fase9_c3.py / tests/test_fase9_ui.py:
banco temporario, nunca chama Pluggy/IA de verdade.
"""
import os
import re
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


def _secao(corpo, tab_id):
    """Recorta o <section id="tab_id" ...> ... </section> correspondente
    (recorte simples por indice, os templates nao aninham outra tag
    <section id="tab-..."> dentro de uma aba)."""
    inicio = corpo.index(f'id="{tab_id}"')
    # acha a proxima aba (ou o fim da <main>) pra limitar o recorte
    resto = corpo[inicio:]
    m = re.search(r'<section id="tab-(?!' + tab_id.split("tab-")[1] + r')', resto)
    fim = inicio + m.start() if m else len(corpo)
    return corpo[inicio:fim]


class M1HojeNavTestCase(unittest.TestCase):
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
        self.tab_hoje = _secao(self.corpo, "tab-hoje")
        self.tab_painel = _secao(self.corpo, "tab-painel")

    # ---- aba Hoje: so chat, foco atual e agenda do dia ----

    def test_hoje_tem_chat_foco_atual_e_agenda(self):
        self.assertIn('id="caixa-assistente"', self.tab_hoje)
        self.assertIn('id="essencial-box"', self.tab_hoje)  # foco atual
        self.assertIn('id="chat-form"', self.tab_hoje)  # chat
        self.assertIn('data-secao-id="visao-dia-hoje"', self.tab_hoje)  # agenda do dia

    def test_hoje_nao_tem_mais_saudacao_sobrecarga_e_resto_movido(self):
        for id_removido in (
            "saudacao-texto",
            "sobrecarga-box",
            "previa-noite-box",
            "rotina-box",
            "checkin-box",
        ):
            self.assertNotIn(f'id="{id_removido}"', self.tab_hoje, f"{id_removido} ainda na Hoje")

    # ---- topo do Painel: saudacao, sobrecarga e o resto do antigo Hoje ----

    def test_saudacao_e_sobrecarga_agora_no_painel(self):
        self.assertIn('id="saudacao-texto"', self.tab_painel)
        self.assertIn('id="sobrecarga-box"', self.tab_painel)

    def test_painel_tem_o_resto_movido_no_topo_e_na_ordem_antiga(self):
        # ordem original em templates/abas/hoje.html: saudacao, sobrecarga,
        # previa-noite, rotina, checkin - e o grupo inteiro tem que vir
        # ANTES do primeiro conteudo antigo do Painel (resumo do dia).
        ids_grupo_movido = [
            'id="saudacao-texto"',
            'id="sobrecarga-box"',
            'id="previa-noite-box"',
            'id="rotina-box"',
            'id="checkin-box"',
        ]
        indices = [self.tab_painel.index(i) for i in ids_grupo_movido]
        self.assertEqual(indices, sorted(indices), "grupo movido fora da ordem antiga")
        idx_resumo_do_dia = self.tab_painel.index('id="resumo-texto"')
        self.assertLess(max(indices), idx_resumo_do_dia, "grupo movido nao esta no topo do Painel")

    def test_essencial_e_hiperfoco_nao_duplicados_no_painel(self):
        # essencial/hiperfoco continuam so na Hoje (nao viraram parte do
        # Painel nem sumiram).
        self.assertNotIn('id="essencial-box"', self.tab_painel)
        self.assertEqual(self.corpo.count('id="essencial-box"'), 1)

    # ---- barra de navegacao: Aviacao logo depois de Painel ----

    def test_ordem_dos_botoes_na_barra(self):
        abas = re.findall(r'data-tab="([a-z]+)" class="tab-btn', self.corpo)
        self.assertEqual(
            abas,
            ["hoje", "painel", "aviacao", "vida", "tarefas", "gastos", "construtora", "assistente"],
        )


if __name__ == "__main__":
    unittest.main()
