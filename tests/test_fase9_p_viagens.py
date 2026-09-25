# tests/test_fase9_p_viagens.py - Fase 9 (C5: faixa "Viagens"). Mantem o
# card da linha do tempo de planejamento (US-F11, cards-tipos.js/vida.py -
# faixa NAO edita) e acrescenta um aviaozinho SVG animado andando ate a data
# da viagem (static/js/secoes/vida/viagens-aviao.js, consumido por
# static/js/secoes/vida/viagens.js).
#
# O calculo de posicao/rotulo e a montagem do HTML sao PUROS e vivem no JS
# (nao no backend) - por isso os casos do briefing (antes do inicio, no
# meio, no dia, depois da data) sao testados via `node --test`
# (tests/js/viagens_aviao.test.js), disparado daqui como subprocesso.
# O wiring de verdade no navegador (IntersectionObserver, animacao
# .em-voo, balanco) e conferido por print Playwright, fora da suite pytest -
# ver POLISH.md desta faixa.
import os
import re
import shutil
import subprocess
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
PIN_TESTE = "123456"


class Fase9PViagensArquivosTestCase(unittest.TestCase):
    """Estrutura/registro dos arquivos novos desta faixa (sem tocar em
    cards.py/vida.py/cards-tipos.js - so os arquivos listados no briefing)."""

    def test_viagens_aviao_js_existe(self):
        caminho = RAIZ / "static" / "js" / "secoes" / "vida" / "viagens-aviao.js"
        self.assertTrue(caminho.exists(), f"{caminho} nao existe")

    def test_viagens_conversa_css_existe(self):
        caminho = RAIZ / "static" / "css" / "secoes" / "vida" / "viagens-conversa.css"
        self.assertTrue(caminho.exists(), f"{caminho} nao existe")

    def test_scripts_html_registra_viagens_aviao_antes_de_viagens(self):
        corpo = (RAIZ / "templates" / "scripts.html").read_text(encoding="utf-8")
        pos_aviao = corpo.find("secoes/vida/viagens-aviao.js")
        pos_viagens = corpo.find('secoes/vida/viagens.js"')
        self.assertNotEqual(pos_aviao, -1, "viagens-aviao.js nao esta registrado em scripts.html")
        self.assertNotEqual(pos_viagens, -1, "viagens.js nao esta em scripts.html")
        self.assertLess(pos_aviao, pos_viagens, "viagens-aviao.js precisa carregar ANTES de viagens.js (viagens.js chama window.ViagemAviao)")

    def test_fase7_css_registra_viagens_conversa(self):
        corpo = (RAIZ / "static" / "css" / "fase7.css").read_text(encoding="utf-8")
        self.assertIn('@import url("secoes/vida/viagens-conversa.css");', corpo)

    def test_viagens_js_nunca_reimplementa_o_calculo(self):
        """Regra de ouro do projeto (nunca duplicar calculo): viagens.js so
        CHAMA ViagemAviao.*, nunca reescreve a formula de fracao/dias na mao."""
        corpo = (RAIZ / "static" / "js" / "secoes" / "vida" / "viagens.js").read_text(encoding="utf-8")
        self.assertIn("ViagemAviao.renderAviaoHTML", corpo)
        self.assertNotIn("getTimezoneOffset", corpo)  # sinal de conta de data feita na mao de novo

    def test_node_check_sintaxe_dos_arquivos_js_novos(self):
        for rel in ("static/js/secoes/vida/viagens-aviao.js", "static/js/secoes/vida/viagens.js"):
            r = subprocess.run(["node", "--check", str(RAIZ / rel)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{rel}: {r.stderr}")


@unittest.skipIf(shutil.which("node") is None, "node nao disponivel neste ambiente")
class Fase9PViagensCalculoPuroTestCase(unittest.TestCase):
    """Casos do briefing (antes do inicio -> 0%, meio, no dia -> 100%, depois
    -> 100% com rotulo 'viagem hoje'/'já passou') - a funcao pura em si
    (tests/js/viagens_aviao.test.js, node --test)."""

    def test_node_test_viagens_aviao_100_por_cento(self):
        r = subprocess.run(
            ["node", "--test", str(RAIZ / "tests" / "js" / "viagens_aviao.test.js")],
            capture_output=True,
            text=True,
            cwd=RAIZ,
        )
        saida = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, saida[-4000:])
        self.assertRegex(saida, r"# fail 0")
        self.assertNotIn("# pass 0", saida)


class Fase9PViagensApiTestCase(unittest.TestCase):
    """Confere que o contrato de /api/viagens (data_ida, criado_em,
    marcos_planejamento) que viagens-aviao.js assume continua valendo -
    integracao real com o banco (nunca dado inventado no front)."""

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

    def test_viagem_internacional_daqui_a_19_dias_tem_os_campos_que_o_aviao_usa(self):
        from datetime import date, timedelta

        ida = (date.today() + timedelta(days=19)).isoformat()
        res = self.client.post(
            "/api/viagens",
            json={"destino": "Lisboa", "data_ida": ida, "internacional": True},
        )
        self.assertEqual(res.status_code, 201, res.get_json())

        res = self.client.get("/api/viagens")
        self.assertEqual(res.status_code, 200)
        viagens = res.get_json()
        self.assertEqual(len(viagens), 1)
        v = viagens[0]

        for campo in ("data_ida", "criado_em", "marcos_planejamento", "dias_ate", "destino"):
            self.assertIn(campo, v, f"campo '{campo}' sumiu de /api/viagens - viagens-aviao.js depende dele")

        self.assertEqual(v["data_ida"], ida)
        self.assertEqual(v["dias_ate"], 19)
        chaves = {m["chave"] for m in v["marcos_planejamento"]}
        # internacional: tem que ter passagem/hospedagem/seguro (a trilha do
        # aviao mostra os 3 + embarque quando presentes)
        self.assertTrue({"passagem", "hospedagem", "seguro"}.issubset(chaves), chaves)
        for m in v["marcos_planejamento"]:
            self.assertIn("data", m)
            self.assertIn("titulo", m)

    def test_viagem_nacional_sem_seguro_ainda_assim_tem_passagem_e_hospedagem(self):
        from datetime import date, timedelta

        ida = (date.today() + timedelta(days=40)).isoformat()
        res = self.client.post("/api/viagens", json={"destino": "Gramado", "data_ida": ida})
        self.assertEqual(res.status_code, 201, res.get_json())
        v = self.client.get("/api/viagens").get_json()[0]
        chaves = {m["chave"] for m in v["marcos_planejamento"]}
        self.assertIn("passagem", chaves)
        self.assertIn("hospedagem", chaves)
        self.assertNotIn("seguro", chaves)  # so viagem internacional tem seguro na regra pratica (vida.py)


if __name__ == "__main__":
    unittest.main()
