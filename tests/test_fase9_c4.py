# tests/test_fase9_c4.py - Fase 9 (C4: faixa "Vida"). A aba Vida (~33 secoes
# empilhadas, ~= rolagem infinita) ganhou uma tela de entrada em 7 grupos
# (templates/secoes/vida/grupos.html + static/js/secoes/vida/grupos.js).
# Aqui so testamos o HTML renderizado (servidor), nao o JS do navegador
# (isso ficou pro print antes/depois via Playwright, fora da suite pytest).
import json
import os
import re
import tempfile
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
os.environ.setdefault("OPENAI_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

import unittest

PIN_TESTE = "123456"


class Fase9C4TestCase(unittest.TestCase):
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

    # ---------- estrutura basica ----------

    def test_pagina_principal_carrega(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_vida_grupos_existe_antes_das_secoes(self):
        pos_grupos = self.corpo.find('id="vida-grupos"')
        pos_aviacao = self.corpo.find('id="secao-aviacao"')
        self.assertNotEqual(pos_grupos, -1, "#vida-grupos nao esta na pagina")
        self.assertNotEqual(pos_aviacao, -1, "#secao-aviacao nao esta na pagina")
        self.assertLess(pos_grupos, pos_aviacao, "#vida-grupos precisa vir ANTES das secoes")

    def test_vida_grupos_dentro_da_aba_vida(self):
        m_tab = re.search(r'<section id="tab-vida"', self.corpo)
        m_grupos = re.search(r'id="vida-grupos"', self.corpo)
        self.assertIsNotNone(m_tab)
        self.assertIsNotNone(m_grupos)
        self.assertLess(m_tab.start(), m_grupos.start())

    # ---------- o mapeamento JSON grupo -> ids ----------

    def _mapa_grupos(self):
        m = re.search(
            r'<script type="application/json" id="vida-grupos-dados">(.*?)</script>',
            self.corpo,
            re.S,
        )
        self.assertIsNotNone(m, "script#vida-grupos-dados nao encontrado")
        return json.loads(m.group(1))

    def test_sete_grupos_existem(self):
        dados = self._mapa_grupos()
        chaves = [g["chave"] for g in dados["grupos"]]
        self.assertEqual(len(chaves), 7, f"esperava 7 grupos, achou {chaves}")
        self.assertEqual(
            set(chaves),
            {"aviacao", "rotina", "saude", "pessoas", "coisas", "mundo", "mente"},
        )

    def test_aviacao_e_grupo_de_destaque_com_uma_secao(self):
        dados = self._mapa_grupos()
        aviacao = next(g for g in dados["grupos"] if g["chave"] == "aviacao")
        self.assertTrue(aviacao.get("destaque"))
        self.assertEqual(aviacao["ids"], ["secao-aviacao"])

    def test_cada_secao_do_mapa_tem_nome_de_exibicao(self):
        dados = self._mapa_grupos()
        todos_ids = [i for g in dados["grupos"] for i in g["ids"]]
        for id_secao in todos_ids:
            self.assertIn(id_secao, dados["nomes"], f"falta nome de exibicao pra {id_secao}")

    # ---------- cobertura: mapa bate exatamente com as secoes reais ----------

    def _ids_reais_em_tab_vida(self):
        """Ids de secao que templates/abas/vida.html realmente marcou com
        data-grupo-secao (o [hidden]+data-grupo-secao que grupos.js liga/desliga),
        dentro de #tab-vida."""
        m_tab = re.search(r'<section id="tab-vida".*?</section>\s*$', self.corpo, re.S)
        # Fallback: a aba e a ultima secao top-level da pagina - se a regex gulosa
        # acima nao fechar direito (aninhamento de </section>), procura a partir
        # do inicio da aba ate o fim do corpo carregado.
        bloco = self.corpo[self.corpo.find('<section id="tab-vida"'):] if not m_tab else m_tab.group(0)
        ids = re.findall(r'data-grupo-secao="([^"]+)"', bloco)
        return ids

    def test_mapa_cobre_todas_as_secoes_sem_sobrar_nem_repetir(self):
        dados = self._mapa_grupos()
        ids_mapa = [i for g in dados["grupos"] for i in g["ids"]]
        ids_reais = self._ids_reais_em_tab_vida()

        self.assertEqual(
            len(ids_mapa), len(set(ids_mapa)), "algum id aparece em mais de um grupo do mapa"
        )
        self.assertEqual(
            len(ids_reais), len(set(ids_reais)), "algum wrapper data-grupo-secao esta duplicado no HTML"
        )
        self.assertEqual(
            set(ids_mapa),
            set(ids_reais),
            "mapa de grupos e os wrappers reais da pagina divergem "
            f"(so no mapa: {set(ids_mapa) - set(ids_reais)}; "
            f"so na pagina: {set(ids_reais) - set(ids_mapa)})",
        )
        # ~33 no briefing (18 vida + 9 painel + 1 aviacao geraram na pratica 30 -
        # 2 secoes do briefing viraram ids dentro do mesmo grupo que outra secao
        # ja citada - "ainda-usa" e "pra-responder" - ver relatorio da faixa).
        self.assertGreaterEqual(len(ids_reais), 28)

    def test_todas_as_secoes_originais_continuam_com_o_mesmo_id(self):
        # ids que ja existiam antes da C4 (nao pode ter mudado nenhum - regra do
        # briefing "nao mude ids delas").
        ids_originais = [
            "secao-aviacao",
            "vida-pra-responder",
            "vida-lista-de-compras",
            "vida-pessoas",
            "vida-treino",
            "vida-ainda-usa",
            "vida-manutencao",
            "vida-garantia",
            "vida-viagens",
            "vida-lugares",
            "vida-ideias-presente",
            "vida-quero-aprender",
            "vida-salvos",
            "vida-mensagem-dificil",
            "vida-vale-a-pena",
            "vida-seu-progresso",
            "vida-revisao-trimestral",
            "painel-peso-e-medidas",
            "painel-memoria-rotina-planos",
        ]
        for id_secao in ids_originais:
            self.assertIn(
                f'"{id_secao}"', self.corpo, f'id/data-secao-id original "{id_secao}" sumiu da pagina'
            )

    # ---------- includes das secoes continuam todos presentes ----------

    def test_includes_de_secoes_da_vida_continuam_no_template(self):
        vida_html = Path(__file__).resolve().parent.parent / "templates" / "abas" / "vida.html"
        texto = vida_html.read_text(encoding="utf-8")
        includes_esperados = [
            "secoes/aviacao/horas-voadas.html",
            "secoes/aviacao/registrar-voo.html",
            "secoes/aviacao/proximos-voos.html",
            "secoes/aviacao/metar.html",
            "secoes/vida/habitos.html",
            "secoes/vida/projetos.html",
            "secoes/vida/agenda-painel.html",
            "secoes/vida/pra-responder.html",
            "secoes/vida/lista-de-compras.html",
            "secoes/vida/pessoas.html",
            "secoes/vida/treino.html",
            "secoes/vida/contas-pessoais.html",
            "secoes/vida/ainda-usa.html",
            "secoes/vida/manutencao.html",
            "secoes/vida/garantia.html",
            "secoes/vida/viagens.html",
            "secoes/vida/lugares.html",
            "secoes/vida/ideias-de-presente.html",
            "secoes/vida/quero-aprender.html",
            "secoes/vida/salvos.html",
            "secoes/vida/mensagem-dificil.html",
            "secoes/vida/vale-a-pena.html",
            "secoes/vida/seu-progresso.html",
            "secoes/vida/revisao-trimestral.html",
            "secoes/painel/saude-hoje.html",
            "secoes/painel/medicamentos.html",
            "secoes/painel/peso-e-medidas.html",
            "secoes/painel/datas-importantes.html",
            "secoes/painel/memoria.html",
            "secoes/painel/notas.html",
            "secoes/painel/diario-de-decisao.html",
            "secoes/painel/brain-dump.html",
            "secoes/painel/esperando-resposta.html",
        ]
        for inc in includes_esperados:
            self.assertIn(inc, texto, f'include "{inc}" sumiu de templates/abas/vida.html')

    def test_todas_as_secoes_comecam_escondidas(self):
        # Regra do briefing: "ao abrir a aba, nenhuma secao aparece - so os
        # grupos". #secao-aviacao e os 29 wrappers .grupo-item precisam ter
        # [hidden] no HTML enviado pelo servidor (antes do JS rodar).
        vida_html = Path(__file__).resolve().parent.parent / "templates" / "abas" / "vida.html"
        texto = vida_html.read_text(encoding="utf-8")
        self.assertRegex(texto, r'id="secao-aviacao"[^>]*\bhidden\b')
        linhas_grupo_item = re.findall(r'<div class="grupo-item"[^>]*>', texto)
        self.assertEqual(len(linhas_grupo_item), 29, f"esperava 29 wrappers .grupo-item, achou {len(linhas_grupo_item)}")
        for linha in linhas_grupo_item:
            self.assertIn("hidden", linha, f"wrapper sem hidden por padrao: {linha}")

    # ---------- arquivos registrados ----------

    def test_grupos_js_registrado_em_scripts_html(self):
        scripts_html = Path(__file__).resolve().parent.parent / "templates" / "scripts.html"
        texto = scripts_html.read_text(encoding="utf-8")
        self.assertIn("/static/js/secoes/vida/grupos.js", texto)

    def test_grupos_css_registrado_em_fase7_css(self):
        fase7_css = Path(__file__).resolve().parent.parent / "static" / "css" / "fase7.css"
        texto = fase7_css.read_text(encoding="utf-8")
        self.assertIn('secoes/vida/grupos.css', texto)

    def test_grupos_js_expoe_abrirsecao(self):
        grupos_js = (
            Path(__file__).resolve().parent.parent
            / "static"
            / "js"
            / "secoes"
            / "vida"
            / "grupos.js"
        )
        texto = grupos_js.read_text(encoding="utf-8")
        self.assertIn("window.VidaGrupos", texto)
        self.assertIn("abrirSecao", texto)

    def test_grupos_js_usa_localstorage_com_try_catch(self):
        grupos_js = (
            Path(__file__).resolve().parent.parent
            / "static"
            / "js"
            / "secoes"
            / "vida"
            / "grupos.js"
        )
        texto = grupos_js.read_text(encoding="utf-8")
        self.assertIn("localStorage", texto)
        self.assertIn("try {", texto)
        self.assertIn("catch (e)", texto)


if __name__ == "__main__":
    unittest.main()
