"""Regressao dos achados da revisao independente da Fase 2 (BRIEFING.md)."""

import os
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from test_vida_rotas import VidaBaseTestCase, fake_usage

import aprendizado
import app
import caldav_client
import db
import vida


class LogicaRevisaoTestCase(unittest.TestCase):
    def test_ficha_casa_palavra_inteira(self):
        fichas = [{"id": 1, "grupo": "Braço"}, {"id": 2, "grupo": "Perna"}, {"id": 3, "grupo": "Treino A"}]
        grupos = lambda titulo: [f["grupo"] for f in vida.ficha_para_titulo(fichas, titulo)]  # noqa: E731
        self.assertEqual(grupos("Dar um abraço na mãe"), [])
        self.assertEqual(grupos("Ligar pra Pernambucanas"), [])
        self.assertEqual(grupos("Treino academia"), ["Braço", "Perna", "Treino A"])
        self.assertEqual(grupos("Treino A"), ["Treino A"])
        self.assertEqual(grupos("treino de braço e perna"), ["Braço", "Perna"])
        self.assertEqual(grupos("Treino de pouso"), [])
        self.assertEqual(grupos(None), [])

    def test_academia_nao_e_treino_de_voo(self):
        self.assertFalse(vida.eh_dia_de_academia(["Treino de voo no aeroclube"]))
        self.assertFalse(vida.eh_dia_de_academia(["Estreino do filme"]))
        self.assertTrue(vida.eh_dia_de_academia(["Academia 18h"]))
        self.assertTrue(vida.eh_dia_de_academia(["Treino peito"]))

    def test_mesma_cidade(self):
        self.assertTrue(vida.mesma_cidade("Floripa", "Floripa, SC"))
        self.assertTrue(vida.mesma_cidade("São Paulo", "São Paulo"))
        self.assertFalse(vida.mesma_cidade("Sal", "Salvador"))
        self.assertFalse(vida.mesma_cidade("😀", "Floripa"))
        self.assertFalse(vida.mesma_cidade(None, "Floripa"))

    def test_compra_so_prefixo_vira_vazio(self):
        for texto in ["acabou o", "Acabou.", "acabaram as", "   "]:
            self.assertEqual(vida.normalizar_item_compra(texto), "", msg=texto)
        self.assertEqual(vida.normalizar_item_compra("Acabou o Café."), "cafe")
        self.assertEqual(vida.normalizar_item_compra("Acabamento"), "acabamento")

    def test_sequencia_de_sono_ancorada_na_primeira_noite(self):
        hoje = date(2026, 9, 23)
        sono = {(hoje - timedelta(days=d)).isoformat(): 5.0 for d in (1, 2, 3)}
        antes = vida.sequencia_noites_ruins(sono, {}, hoje)
        sono[hoje.isoformat()] = 4.0
        depois = vida.sequencia_noites_ruins(sono, {}, hoje)
        self.assertEqual(antes, (3, hoje - timedelta(days=3)))
        self.assertEqual(depois, (4, hoje - timedelta(days=3)))
        self.assertEqual(vida.sequencia_noites_ruins({}, {}, hoje), (0, None))

    def test_evento_icloud_com_fuso_vira_hora_local(self):
        inicio = datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc)
        comp = {"DTSTART": SimpleNamespace(dt=inicio), "DTEND": SimpleNamespace(dt=inicio + timedelta(hours=1))}
        comp_obj = SimpleNamespace(icalendar_component=_Componente(comp))
        evento = caldav_client._extrair_evento(comp_obj)
        local = inicio.astimezone().replace(tzinfo=None)
        self.assertEqual(evento["inicio"], local.isoformat())
        self.assertIsNone(datetime.fromisoformat(evento["inicio"]).tzinfo)

    def test_inteiro_no_intervalo_infinito(self):
        for valor in (float("inf"), float("-inf"), float("nan"), 1e308, "1e999"):
            self.assertIsNone(app._inteiro_no_intervalo(valor, 0, 100), msg=repr(valor))


class _Componente(dict):
    def get(self, chave, padrao=None):
        return super().get(chave, padrao)


class RotasRevisaoTestCase(VidaBaseTestCase):
    def test_numero_gigante_nao_da_500(self):
        casos = [
            ("/api/manutencoes", {"item": "x", "intervalo_meses": 1e999}),
            ("/api/treino", {"duracao_min": 1e999}),
            ("/api/treino", {"duracao_min": -1e999}),
        ]
        for rota, corpo in casos:
            self.assertEqual(self.client.post(rota, json=corpo).status_code, 400, msg=rota)
        r = self.client.post("/api/atalho/local", json={"evento": "saiu", "lugar": "casa", "bateria": 1e999})
        self.assertEqual(r.status_code, 200)

    def test_bateria_quebrada_ou_texto(self):
        def mensagem(bateria):
            with patch("app.datetime") as dt:
                dt.now.return_value = datetime.combine(date.today(), datetime.min.time()).replace(hour=8)
                dt.fromisoformat = datetime.fromisoformat
                app.definir_configuracao(self._conn(), "local_casa_saiu", "")
                corpo = {"evento": "saiu", "lugar": "casa", "bateria": bateria}
                return self.client.post("/api/atalho/local", json=corpo).get_json()["mensagem"]

        self.assertIn("carregador (bateria em 48%)", mensagem(47.5))
        self.assertIn("carregador (bateria em 30%)", mensagem("30"))
        self.assertNotIn("carregador", mensagem("80"))
        self.assertNotIn("carregador", mensagem("abc"))

    def test_chegou_em_casa_com_evento_com_fuso(self):
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=12)
        evento = {
            "titulo": "Dentista",
            "inicio": (agora + timedelta(hours=3)).astimezone(timezone.utc).isoformat(),
            "dia_inteiro": False,
        }
        with patch("app._eventos_de_hoje_com_seguranca", return_value=[evento]), patch("app.datetime") as dt:
            dt.now.return_value = agora
            dt.fromisoformat = datetime.fromisoformat
            r = self.client.post("/api/atalho/local", json={"evento": "chegou", "lugar": "casa"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Dentista", r.get_json()["mensagem"])

    def test_rotas_de_localizacao_e_apps_nao_ficam_abertas(self):
        anonimo = app.app.test_client()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PAINEL_ATALHOS_TOKEN", None)
            self.assertEqual(
                anonimo.post("/api/atalho/local", json={"evento": "chegou", "lugar": "mercado"}).status_code, 401
            )
            self.assertEqual(anonimo.post("/api/atalho/app", json={"app": "X", "evento": "abriu"}).status_code, 401)
            self.assertEqual(
                self.client.post("/api/atalho/app", json={"app": "X", "evento": "abriu"}).status_code, 200
            )

    def test_adiado_leve_respeita_silencio(self):
        conn = self._conn()
        with patch("app.date") as d:
            d.today.return_value = date.today()
            app._adiar_aviso(conn, "fechamento_noturno", "Fechando o dia", "x")
            app._adiar_aviso(conn, "rotina_manha", "Bom dia", "y")
        tipos = [t for t, *_ in app._liberar_avisos_adiados(conn, date.today())]
        self.assertEqual(tipos, ["adiado_hiperfoco_leve", "adiado_hiperfoco"])
        self.assertNotIn("adiado_hiperfoco_leve", app.NOTIFICACOES_URGENTES)
        self.assertIn("adiado_hiperfoco_leve", vida.CRITICOS_HIPERFOCO)

    def test_pessoa_mesmo_nome_nao_duplica(self):
        self.assertEqual(self.client.post("/api/pessoas", json={"nome": "Mãe", "frequencia_dias": 7}).status_code, 201)
        r = self.client.post("/api/pessoas", json={"nome": "mae", "frequencia_dias": 3})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["atualizada"])
        pessoas = self.client.get("/api/pessoas").get_json()
        self.assertEqual([(p["nome"], p["frequencia_dias"]) for p in pessoas], [("Mãe", 3)])

    def test_criado_em_convertido_pra_hora_local(self):
        conn = self._conn()
        conn.execute("INSERT INTO responder (quem, criado_em) VALUES ('Ana', '2026-09-23 01:30:00')")
        conn.commit()
        esperado = (
            datetime(2026, 9, 23, 1, 30, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
            .isoformat(sep=" ", timespec="seconds")
        )
        self.assertEqual(db.list_responder_pendentes(conn)[0]["criado_em"], esperado)

    def test_dica_sono_humor_sem_rotulo_repetido(self):
        medias = {"7h ou mais": 2.4, "menos de 6h": 1.6}
        with patch("aprendizado.media_checkin_por_faixa_sono", return_value=medias):
            dica = aprendizado.dica_sono_humor(self._conn())
        self.assertIn("fica melhor depois de 7h ou mais de sono do que depois de menos de 6h", dica)
        self.assertNotIn("'ok' depois de 7h ou mais de sono e mais pra 'ok'", dica)


if __name__ == "__main__":
    unittest.main()


# ---- Revisao independente da Fase 3 ----

import http.server  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import leitura  # noqa: E402


class _Pagina(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/pinga":
            self.send_response(200)
            self.end_headers()
            for _ in range(30):
                try:
                    self.wfile.write(b"a")
                    self.wfile.flush()
                except OSError:
                    return
                time.sleep(0.5)
            return
        if self.path == "/gzip":
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            self.wfile.write(b"x")
            return
        corpo = f"<title>Host {self.headers.get('Host')}</title><p>caf\xe9</p>".encode("latin-1")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=xyz-inexistente" if self.path == "/charset" else
                         "text/html; charset=iso-8859-1")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


class LeituraSeguraTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Pagina)
        cls.porta = cls.servidor.server_address[1]
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()

    def _baixar(self, caminho):
        # "site.test" finge ser publico mas o IP e o servidor local do teste -
        # prova que a conexao vai pro IP validado com o Host original.
        real = leitura._resolver
        with patch("leitura._resolver", side_effect=lambda h: ["127.0.0.1"] if h == "site.test" else real(h)):
            return leitura.baixar_pagina(f"http://site.test:{self.porta}{caminho}")

    def test_conecta_no_ip_validado_com_host_original(self):
        pagina = self._baixar("/")
        self.assertIn(f"Host site.test:{self.porta}", pagina)
        self.assertIn("café", pagina)

    def test_truques_de_url_bloqueados(self):
        for url in [f"http://127.0.0.1:{self.porta}\\@site.test/", "http://u:p@site.test/", "http://[::1",
                    "http://[abc]/", "http://[::1]@example.com/", "http://a..b/", "http://" + "a" * 64 + ".com/",
                    "http://.example.com/", "http://[::127.0.0.1]/", "http://[64:ff9b::7f00:1]/",
                    "http://2130706433/", "http://0x7f.1/", "http://site.test:99999/"]:
            with self.assertRaises(leitura.LinkInvalido, msg=url):
                leitura.baixar_pagina(url)

    def test_prazo_total_e_sem_compressao(self):
        with patch("leitura.PRAZO_TOTAL", 2):
            inicio = time.monotonic()
            with self.assertRaises(leitura.LinkInvalido):
                self._baixar("/pinga")
            self.assertLess(time.monotonic() - inicio, 6)
        with self.assertRaises(leitura.LinkInvalido):
            self._baixar("/gzip")

    def test_charset_desconhecido_nao_quebra(self):
        self.assertIn("Host", self._baixar("/charset"))

    def test_html_hostil_e_linear(self):
        for pagina in ["<script>" * 200000, "<meta " * 300000, "<title>x" * 200000, "<a" * 700000]:
            inicio = time.monotonic()
            leitura.extrair(pagina[:1_500_000])
            self.assertLess(time.monotonic() - inicio, 2)

    def test_dominio_com_acento(self):
        with patch("leitura._resolver", return_value=["93.184.216.34"]):
            self.assertEqual(leitura.validar_url("https://ação.com.br/x"), "https://ação.com.br/x")


class RotasRevisaoFase3TestCase(VidaBaseTestCase):
    def test_salvar_link_estranho_nao_da_500(self):
        for url in ["http://[::1", "http://[abc]/", "http://a..b/", "http://" + "a" * 64 + ".com/"]:
            self.assertEqual(self.client.post("/api/salvos", json={"url": url}).status_code, 400, msg=url)
        with patch("leitura._resolver", return_value=["93.184.216.34"]), \
                patch("leitura.baixar_pagina", side_effect=LookupError("xyz")):
            r = self.client.post("/api/salvos", json={"url": "https://exemplo.com/a"})
        self.assertEqual(r.status_code, 201)
        self.assertIn("link ficou salvo", r.get_json()["aviso"])

    def test_meta_com_deposito_simbolico(self):
        conn = self._conn()
        gid = conn.execute("INSERT INTO goals (titulo, valor_alvo, valor_guardado) VALUES ('Casa', 1000000, 0)").lastrowid
        conn.commit()
        self.client.post(f"/api/metas/{gid}/guardar", json={"valor": 1})
        r = self.client.get("/api/metas")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()[0]["previsao"])
        self.assertEqual(self.client.post(f"/api/metas/{gid}/guardar", json={"valor": 1e999}).status_code, 400)
        self.assertEqual(self.client.get("/api/progresso").status_code, 200)

    def test_revisao_mensal_mes_absurdo(self):
        for mes in ["9999-12", "0001-01", "2026-13", "abc"]:
            self.assertEqual(self.client.get(f"/api/revisao-mensal?mes={mes}").status_code, 400, msg=mes)
        self.assertEqual(self.client.get("/api/revisao-mensal?mes=2026-12").status_code, 200)

    def test_pos_voo_de_noite_pergunta_de_manha(self):
        conn = self._conn()
        hoje = date.today()
        ontem = (hoje - timedelta(days=1)).isoformat()
        conn.execute("INSERT INTO voos (data, destino, hora) VALUES (?, 'SBJV', '20:30')", (ontem,))
        conn.commit()
        manha = datetime.combine(hoje, datetime.min.time()).replace(hour=7, minute=5)
        tipos = [t for t, *_ in app._avisos_fase3(conn, manha)]
        self.assertIn("pos_voo", tipos)
        tarde = manha.replace(hour=13)
        self.assertNotIn("pos_voo", [t for t, *_ in app._avisos_fase3(conn, tarde)])

    def test_contar_voo_completa_o_agendado(self):
        conn = self._conn()
        hoje = date.today().isoformat()
        conn.execute("INSERT INTO voos (data, destino, hora) VALUES (?, 'SBJV', '10:00')", (hoje,))
        conn.commit()
        resultados = []

        def fake_chat(mensagens, contexto, memorias, executores):
            resultados.append(executores["registrar_voo"](
                {"data": hoje, "destino": "sbjv", "horas": 1.2, "observacao": "pousos com vento"}))
            return "Anotado.", ["registrar_voo"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "voei 1.2h pro sbjv, pousos com vento"})
        self.assertTrue(resultados[0].get("atualizado"))
        voos = self._conn().execute("SELECT destino, horas, observacao FROM voos").fetchall()
        self.assertEqual([tuple(v) for v in voos], [("SBJV", 1.2, "pousos com vento")])

    def test_projecao_conta_vencida_nao_paga(self):
        hoje = date.today()
        vencida = hoje - timedelta(days=3)
        if vencida.month != hoje.month:
            self.skipTest("inicio do mes")
        conn = self._conn()
        conn.execute(
            "INSERT INTO contas_pessoais (nome, valor, dia_vencimento, criado_em) VALUES ('Aluguel', 1500, ?, ?)",
            (vencida.day, (hoje - timedelta(days=60)).isoformat() + " 10:00:00"),
        )
        conn.commit()
        projecao = self.client.get("/api/sobra-do-mes").get_json()["projecao"]
        self.assertEqual(projecao["contas_pendentes"], 1500)

    def test_aprender_tema_longo_explica(self):
        r = self.client.post("/api/aprender", json={"tema": "x" * 81})
        self.assertIn("muito longo", r.get_json()["error"])
        r = self.client.post("/api/aprender", json={"tema": "FII", "nota": "n" * 400})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.client.get("/api/aprender").get_json()[0]["nota"]), 300)

    def test_eventos_app_antigos_sao_limpos(self):
        conn = self._conn()
        db.registrar_evento_app(conn, "X", "abriu", "2026-01-01T10:00:00")
        db.registrar_evento_app(conn, "X", "abriu", "2026-09-23T10:00:00")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM app_eventos").fetchone()[0], 1)

    def test_burocracia_visto(self):
        self.assertFalse(vida.eh_burocracia("Já tinha visto esse filme"))
        self.assertTrue(vida.eh_burocracia("Renovar visto americano"))
