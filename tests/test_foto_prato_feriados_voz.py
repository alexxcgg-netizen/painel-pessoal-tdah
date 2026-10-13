"""Leva de 2026-10-13: foto do prato (refeicoes.py + POST /api/chat/foto + card `refeicao`),
calendario brasileiro (feriados.py + tool consultar_feriados) e voz de fundo na gravacao
(trechos_voz -> telegram_captura.texto_dos_trechos). Nenhuma rede: visao/IA sempre dubladas."""
import io
import json
import os
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import feriados  # noqa: E402
import refeicoes  # noqa: E402
import telegram_captura  # noqa: E402
from rotas import voz  # noqa: E402

PIN = "864201"

PRATO = {
    "e_comida": True,
    "refeicao": "almoco",
    "confianca": 0.8,
    "descricao": "arroz, feijão e frango",
    "dica": "Boa base de proteína.",
    "itens": [
        {"nome": "Arroz branco", "gramas": 150, "kcal": 192, "proteina_g": 3.8, "carbo_g": 42, "gordura_g": 0.3},
        {"nome": "Feijão", "gramas": 100, "kcal": 76, "proteina_g": 4.8, "carbo_g": 13.6, "gordura_g": 0.5},
        {"nome": "Frango grelhado", "gramas": 130, "kcal": 207, "proteina_g": 41.6, "carbo_g": 0, "gordura_g": 3.4},
    ],
}


class FeriadosTestCase(unittest.TestCase):
    def test_pascoa_e_moveis(self):
        self.assertEqual(feriados.pascoa(2026), date(2026, 4, 5))
        self.assertEqual(feriados.pascoa(2027), date(2027, 3, 28))
        self.assertEqual(feriados.pascoa(2025), date(2025, 4, 20))
        ano = {f["nome"]: f for f in feriados.do_ano(2026)}
        sexta = [f for f in ano.values() if "Sexta-feira Santa" in f["nome"]][0]
        self.assertEqual(sexta["data"], date(2026, 4, 3))
        self.assertEqual(sexta["tipo"], feriados.FERIADO)
        carnaval = [f for f in ano.values() if "Carnaval" in f["nome"]]
        self.assertEqual({f["data"] for f in carnaval}, {date(2026, 2, 16), date(2026, 2, 17)})
        self.assertTrue(all(f["tipo"] == feriados.FACULTATIVO for f in carnaval))  # nunca "e feriado"
        corpus = [f for f in ano.values() if "Corpus Christi" in f["nome"]][0]
        self.assertEqual(corpus["data"], date(2026, 6, 4))

    def test_ordenado_e_com_brusque_e_consciencia_negra(self):
        lista = feriados.do_ano(2026)
        self.assertEqual([f["data"] for f in lista], sorted(f["data"] for f in lista))
        datas = {f["data"]: f for f in lista}
        self.assertIn(date(2026, 8, 4), datas)
        self.assertIn(date(2026, 11, 20), datas)
        self.assertEqual(datas[date(2026, 11, 20)]["tipo"], feriados.FERIADO)

    def test_emenda(self):
        # 2026-04-21 (Tiradentes) e terca; 2026-06-04 (Corpus) e facultativo -> sem emenda
        tiradentes = feriados.do_dia(date(2026, 4, 21))[0]
        self.assertIn("segunda", feriados.emenda(tiradentes))
        self.assertIsNone(feriados.emenda(feriados.do_dia(date(2026, 6, 4))[0]))

    def test_linhas_contexto(self):
        hoje = feriados.linhas_contexto(date(2026, 10, 12))
        self.assertTrue(hoje[0].startswith("HOJE é Nossa Senhora Aparecida"))
        vespera = feriados.linhas_contexto(date(2026, 11, 1))
        self.assertFalse(any(l.startswith("HOJE") for l in vespera))
        proximos = [l for l in vespera if l.startswith("Próximos feriados")][0]
        self.assertIn("02/11 (amanhã) Finados", proximos)
        self.assertIn("20/11", proximos)
        # dia comum sem nada perto: nem linha de HOJE
        self.assertFalse(any(l.startswith("HOJE") for l in feriados.linhas_contexto(date(2026, 3, 10))))

    def test_virada_de_ano(self):
        prox = feriados.proximos(date(2026, 12, 20), 20)
        self.assertIn(date(2027, 1, 1), [f["data"] for f in prox])


class TrechosVozTestCase(unittest.TestCase):
    RESPOSTA = {"segments": [
        {"start": 0.0, "end": 2.0, "text": "Amanhã preciso buscar", "no_speech_prob": 0.01},
        {"start": 2.0, "end": 4.0, "text": "minha mãe às quatro.", "no_speech_prob": 0.01},
        {"start": 5.0, "end": 7.5, "text": "e no jornal de hoje a previsão", "no_speech_prob": 0.02},
    ]}

    def test_sem_trechos_fica_como_antes(self):
        self.assertIn("previsão", telegram_captura.texto_dos_trechos(self.RESPOSTA))

    def test_tira_o_que_nao_encosta_na_voz_dele(self):
        texto = telegram_captura.texto_dos_trechos(self.RESPOSTA, trechos_voz=[(0.2, 3.9)])
        self.assertEqual(texto, "Amanhã preciso buscar minha mãe às quatro.")

    def test_sobreposicao_parcial_fica(self):
        # ele falou de 5.0 a 6.0 (40% do trecho) -> fica
        texto = telegram_captura.texto_dos_trechos(self.RESPOSTA, trechos_voz=[(0.0, 4.0), (5.0, 6.0)])
        self.assertIn("previsão", texto)

    def test_validacao_do_formulario(self):
        self.assertEqual(voz._trechos_voz("[[0.4, 2.1], [2.6, 5]]"), [(0.4, 2.1), (2.6, 5.0)])
        for ruim in ("", None, "nao e json", "{}", "[[3, 1]]", "[[0, 9999]]", '[["a", 1]]', "[[1]]"):
            with self.subTest(ruim=ruim):
                self.assertIsNone(voz._trechos_voz(ruim))
        self.assertEqual(len(voz._trechos_voz(json.dumps([[i, i + 0.5] for i in range(300)]))), 200)


class RefeicoesTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_itens_limpos_corta_lixo_e_exagero(self):
        itens = refeicoes.itens_limpos([
            {"nome": "  Arroz ", "gramas": "150", "kcal": 192, "proteina_g": -3, "carbo_g": 42, "gordura_g": None},
            {"nome": "", "kcal": 100},
            "texto solto",
            {"nome": "Bolo gigante", "gramas": 99999, "kcal": 99999},
        ])
        self.assertEqual([i["nome"] for i in itens], ["Arroz", "Bolo gigante"])
        self.assertEqual(itens[0]["gramas"], 150.0)
        self.assertEqual(itens[0]["proteina_g"], 0.0)
        self.assertEqual(itens[0]["gordura_g"], 0.0)
        self.assertEqual(itens[1]["kcal"], 3000.0)
        self.assertEqual(len(refeicoes.itens_limpos([{"nome": f"i{n}"} for n in range(40)])), 15)

    def test_registra_soma_no_dia_e_vai_pro_contexto(self):
        agora = datetime(2026, 10, 13, 12, 30)
        itens = refeicoes.itens_limpos(PRATO["itens"])
        refeicoes.registrar(self.conn, itens, "almoco", agora)
        refeicoes.registrar(self.conn, itens, "inventada", datetime(2026, 10, 13, 20, 0))
        tot = refeicoes.do_dia(self.conn, agora.date())
        self.assertEqual(tot["refeicoes"], 2)
        self.assertAlmostEqual(tot["kcal"], 950.0)
        self.assertEqual(self.conn.execute("SELECT refeicao FROM refeicoes ORDER BY id DESC").fetchone()[0], "janta")
        linha = refeicoes.linha_contexto(self.conn, agora.date())
        self.assertIn("2 refeição(ões), ~950 kcal", linha)
        self.assertIsNone(refeicoes.linha_contexto(self.conn, date(2026, 10, 14)))
        self.assertIn("almoço ~475 kcal", refeicoes.fatos_do_dia(self.conn, agora.date()))

    def test_refeicao_pela_hora(self):
        self.assertEqual(
            [refeicoes.refeicao_pela_hora(h) for h in (7, 12, 16, 20, 23, 3)],
            ["cafe_da_manha", "almoco", "lanche", "janta", "ceia", "ceia"],
        )


class RotaFotoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def _enviar(self, mime="image/jpeg", conteudo=b"\xff\xd8\xff" + b"\x00" * 500, **extra):
        dados = {"imagem": (io.BytesIO(conteudo), "prato.jpg", mime), **extra}
        return self.client.post("/api/chat/foto", data=dados, content_type="multipart/form-data")

    def _contar(self):
        conn = db.get_db()
        try:
            refeicoes.criar_tabela(conn)
            return conn.execute("SELECT COUNT(*) FROM refeicoes").fetchone()[0]
        finally:
            conn.close()

    def test_prato_vira_card_com_desfazer(self):
        with patch("ia.funcoes.visao.analisar_prato", return_value=(PRATO, {})) as m:
            r = self._enviar(texto="só comi metade do arroz")
        self.assertEqual(r.status_code, 200, r.get_json())
        corpo = r.get_json()
        self.assertEqual(m.call_args.args[1], "image/jpeg")
        self.assertEqual(m.call_args.args[3], "só comi metade do arroz")
        self.assertIn("~475 kcal no almoço", corpo["resposta"])
        self.assertIn("Boa base de proteína.", corpo["resposta"])
        card = [c for c in corpo["cards"] if c["type"] == "refeicao"][0]
        self.assertEqual(card["data"]["refeicao"], "almoço")
        self.assertEqual(len(card["data"]["itens"]), 3)
        self.assertAlmostEqual(card["data"]["total"]["proteina_g"], 50.2)
        self.assertEqual(card["data"]["dica"], "Boa base de proteína.")
        self.assertEqual(self._contar(), 1)
        # historico do chat: a foto nao fica, so o texto
        hist = self.client.get("/api/chat/historico").get_json()
        textos = json.dumps(hist, ensure_ascii=False)
        self.assertIn("📷 Foto do prato - só comi metade do arroz", textos)
        # desfazer tira a refeicao
        token = [a for a in card["actions"] if a["tipo"] == "desfazer"][0]["token"]
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual(self._contar(), 0)

    def test_foto_sem_comida_nao_registra(self):
        nada = {"e_comida": False, "itens": [], "descricao": "um cachorro no sofá"}
        with patch("ia.funcoes.visao.analisar_prato", return_value=(nada, {})):
            r = self._enviar()
        self.assertEqual(r.status_code, 200)
        self.assertIn("Não vi comida", r.get_json()["resposta"])
        self.assertIn("cachorro", r.get_json()["resposta"])
        self.assertEqual(self._contar(), 0)

    def test_entrada_ruim(self):
        with patch("ia.funcoes.visao.analisar_prato") as m:
            self.assertEqual(self.client.post("/api/chat/foto", data={}, content_type="multipart/form-data").status_code, 400)
            self.assertEqual(self._enviar(mime="application/pdf").status_code, 400)
            self.assertEqual(self._enviar(conteudo=b"").status_code, 400)
        m.assert_not_called()

    def test_falha_da_ia_vem_legivel(self):
        from ia import core

        with patch("ia.funcoes.visao.analisar_prato", side_effect=core.FalhaChamadaIA("fora")):
            r = self._enviar()
        self.assertEqual(r.status_code, 502)
        self.assertIn("tenta de novo", r.get_json()["error"])
        self.assertEqual(self._contar(), 0)

    def test_modo_visitante_recusa(self):
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = time.time()
        with patch("ia.funcoes.visao.analisar_prato") as m:
            r = self._enviar()
        self.assertEqual(r.status_code, 403)
        m.assert_not_called()


class ConsultarFeriadosToolTestCase(unittest.TestCase):
    def test_tool_existe_no_chat(self):
        from ia.funcoes import chat

        nomes = {t["name"] for t in chat.CHAT_TOOLS}
        self.assertIn("consultar_feriados", nomes)

    def test_contexto_do_chat_tem_feriados(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        try:
            agora = datetime(2026, 11, 1, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
            with patch("app._agora_brasilia", return_value=agora):
                texto = app._contexto_chat(conn)
        finally:
            conn.close()
        self.assertIn("Finados", texto)


if __name__ == "__main__":
    unittest.main()


class WidgetInstalacaoTestCase(unittest.TestCase):
    """Configurações > Widget do iPhone: script + token pra copiar no celular, só com PIN."""

    def setUp(self):
        from rotas import n3a_widget

        p = patch.object(n3a_widget, "_LOG_WIDGET", str(Path(_tmp.name) / "widget.log"))
        p.start()
        self.addCleanup(p.stop)
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()

    def _logar(self):
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def test_sem_login_nao_entrega_nada(self):
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "tok-secreto"}):
            r = self.client.get("/api/widget/instalacao")
        self.assertIn(r.status_code, (302, 401))
        self.assertNotIn(b"tok-secreto", r.data)
        # o token do widget tambem nao abre esta rota (so a de leitura /api/widget)
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "tok-secreto"}):
            r = self.client.get("/api/widget/instalacao?token=tok-secreto")
        self.assertNotIn(b"tok-secreto", r.data)

    def test_com_login_entrega_script_e_token(self):
        self._logar()
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "tok-secreto"}):
            dados = self.client.get("/api/widget/instalacao").get_json()
        self.assertTrue(dados["configurado"])
        self.assertEqual(dados["token"], "tok-secreto")
        self.assertIn("function preencherNormal", dados["script"])
        self.assertIn("COMIDA HOJE", dados["script"])

    def test_sem_token_configurado_avisa(self):
        self._logar()
        env = {k: v for k, v in os.environ.items() if k != "PAINEL_WIDGET_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            dados = self.client.get("/api/widget/instalacao").get_json()
        self.assertFalse(dados["configurado"])
        self.assertIsNone(dados["token"])

    def test_modo_visitante_recusa(self):
        self._logar()
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = time.time()
        with patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "tok-secreto"}):
            r = self.client.get("/api/widget/instalacao")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn(b"tok-secreto", r.data)
