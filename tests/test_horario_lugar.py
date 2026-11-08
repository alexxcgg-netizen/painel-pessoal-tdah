"""'Ta aberto?' (frente D, leva 07/11/2026 - docs/briefings/2026-11-07-lugar-certo-e-avisos.md).

horario_lugar.py (aberto ate X / fechando em < 30 min / fechado, abre Y / fechado temporariamente / de vez,
com currentOpeningHours pra feriado e horario especial), maps_client.dados_horario (campos, cache curto,
cota), a ferramenta do chat ver_horario_lugar e o automatico (tarefa de hoje com lugar -> linha no card +
aviso lugar_fechado 1x por tarefa por dia). Nada de rede: Google sempre mockado; banco temporario."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import horario_lugar as hl  # noqa: E402
import maps_client  # noqa: E402
import push_client  # noqa: E402

PIN = "135790"
SABADO = datetime(2026, 11, 7)  # 07/11/2026 e sabado (Google: dia 6)


def _todo_dia(abre, fecha):
    return [{"open": {"day": d, "hour": abre, "minute": 0}, "close": {"day": d, "hour": fecha, "minute": 0}}
            for d in range(7)]


def _ponto(dt):
    return {"date": {"year": dt.year, "month": dt.month, "day": dt.day}, "day": (dt.weekday() + 1) % 7,
            "hour": dt.hour, "minute": dt.minute}


def _atual(*faixas):
    return [{"open": _ponto(a), "close": _ponto(b)} for a, b in faixas]


def _dados(regular=None, atual=None, status="OPERATIONAL", buscado=SABADO, nome="Shopping"):
    return {"nome": nome, "regular": regular, "atual": atual, "status": status, "utc_offset": -180,
            "buscado_em": buscado}


SHOPPING = _dados(_todo_dia(10, 22))
H24 = [{"open": {"day": 0, "hour": 0, "minute": 0}}]
# seg-sex 9-12 e 13-17 (cartorio)
CARTORIO = [p for d in range(1, 6) for p in (
    {"open": {"day": d, "hour": 9, "minute": 0}, "close": {"day": d, "hour": 12, "minute": 0}},
    {"open": {"day": d, "hour": 13, "minute": 0}, "close": {"day": d, "hour": 17, "minute": 0}})]


class SituacaoTest(unittest.TestCase):
    def test_aberto_ate_fechando_e_fechado_com_a_hora_que_abre(self):
        s = hl.situacao(SHOPPING, SABADO.replace(hour=21))
        self.assertEqual((s["estado"], s["fecha_as"], s["frase"]), ("aberto", "22:00", "aberto até 22h"))
        s = hl.situacao(SHOPPING, SABADO.replace(hour=21, minute=45))
        self.assertEqual((s["estado"], s["fecha_em_min"]), ("fechando", 15))
        self.assertEqual(hl.frase_chegada(s, SABADO.replace(hour=21, minute=45))[0],
                         "Fecha às 22h, só 15 min depois de tu chegar.")
        s = hl.situacao(SHOPPING, SABADO.replace(hour=22, minute=10))
        self.assertEqual((s["estado"], s["fechou_as"], s["abre_as"], s["abre_dia"]), ("fechado", "22:00", "10:00", "2026-11-08"))
        self.assertEqual(s["frase"], "fechado nessa hora, abre amanhã às 10h")
        self.assertEqual(hl.frase_chegada(s, SABADO.replace(hour=22, minute=10)),
                         ("Fecha às 22h e tu chega 22h10.", "fecha 22h, tu chega 22h10"))
        # 30 min ou mais antes de fechar ainda e "aberto"
        self.assertEqual(hl.situacao(SHOPPING, SABADO.replace(hour=21, minute=30))["estado"], "aberto")

    def test_almoco_e_fim_de_semana(self):
        sexta = datetime(2026, 11, 6, 12, 10)
        s = hl.situacao(_dados(CARTORIO, nome="Cartório"), sexta)
        self.assertEqual(s["estado"], "fechado")
        self.assertEqual(hl.frase_chegada(s, sexta)[0], "Fecha das 12h às 13h e tu chega 12h10.")
        s = hl.situacao(_dados(CARTORIO), SABADO.replace(hour=10))
        self.assertEqual(s["frase"], "fechado nessa hora, abre segunda às 9h")
        self.assertNotIn("fechou_as", s)  # fechou ontem: nao e "fecha as 17h"

    def test_feriado_pelo_current_opening_hours(self):
        # 20/11 (sexta, feriado): a semana tipica diz aberto, o horario atual do Google nao tem a sexta
        regular = CARTORIO
        atual = _atual((datetime(2026, 11, 19, 9), datetime(2026, 11, 19, 17)),
                       (datetime(2026, 11, 23, 9), datetime(2026, 11, 23, 17)))
        d = _dados(regular, atual, buscado=datetime(2026, 11, 19, 8))
        s = hl.situacao(d, datetime(2026, 11, 20, 10))
        self.assertEqual((s["estado"], s["abre_as"], s["abre_dia"]), ("fechado", "09:00", "2026-11-23"))
        # fora da janela de 7 dias do horario atual volta a semana tipica
        self.assertEqual(hl.situacao(d, datetime(2026, 11, 27, 10))["estado"], "aberto")
        with patch("maps_client.dados_horario", return_value=d):
            self.assertEqual(maps_client.horario_funcionamento("Cartório", date(2026, 11, 20)),
                             {"nome": "Shopping", "fechado": True})
            self.assertEqual(maps_client.horario_funcionamento("Cartório", date(2026, 11, 19))["faixas"], [["09:00", "17:00"]])

    def test_horario_especial_fecha_mais_cedo(self):
        d = _dados(_todo_dia(10, 22), _atual((datetime(2026, 12, 24, 10), datetime(2026, 12, 24, 18))),
                   buscado=datetime(2026, 12, 23, 9))
        s = hl.situacao(d, datetime(2026, 12, 24, 19))
        self.assertEqual((s["estado"], s["fechou_as"]), ("fechado", "18:00"))
        self.assertEqual(hl.situacao(d, datetime(2026, 12, 24, 17, 50))["estado"], "fechando")

    def test_24h(self):
        for d in (_dados(H24), _dados(None, H24), _dados(_todo_dia(0, 0)[:0] + H24, H24)):
            s = hl.situacao(d, SABADO.replace(hour=3))
            self.assertEqual((s["estado"], s["frase"]), ("aberto", "aberto 24h"), d)
        with patch("maps_client.dados_horario", return_value=_dados(H24)):
            self.assertEqual(maps_client.horario_funcionamento("Posto", SABADO.date())["faixas"], [["00:00", "24:00"]])

    def test_cruza_a_meia_noite_inclusive_sabado_pra_domingo(self):
        noite = [{"open": {"day": d, "hour": 18, "minute": 0}, "close": {"day": (d + 1) % 7, "hour": 2, "minute": 0}}
                 for d in (5, 6)]  # sexta e sabado ate 2h
        d = _dados(noite, nome="Bar")
        s = hl.situacao(d, SABADO.replace(hour=1))
        self.assertEqual((s["estado"], s["fecha_as"]), ("aberto", "02:00"))
        s = hl.situacao(d, datetime(2026, 11, 8, 1, 40))  # domingo 1h40: faixa que vem de sabado
        self.assertEqual((s["estado"], s["fecha_em_min"]), ("fechando", 20))
        self.assertEqual(hl.situacao(d, datetime(2026, 11, 8, 3))["abre_dia"], "2026-11-13")
        # horario atual com data cruzando a meia-noite
        d2 = _dados(None, _atual((SABADO.replace(hour=22), datetime(2026, 11, 8, 2))))
        self.assertEqual(hl.situacao(d2, datetime(2026, 11, 8, 1))["estado"], "aberto")
        with patch("maps_client.dados_horario", return_value=d):
            self.assertEqual(maps_client.horario_funcionamento("Bar", SABADO.date())["faixas"], [["18:00", "24:00"]])

    def test_fechado_temporariamente_e_de_vez(self):
        s = hl.situacao(_dados(_todo_dia(10, 22), status="CLOSED_TEMPORARILY"), SABADO.replace(hour=15))
        self.assertEqual((s["estado"], s["aberto"]), ("fechado_temporariamente", False))
        self.assertEqual(hl.frase_chegada(s, SABADO)[1], "fechado temporariamente")
        s = hl.situacao(_dados(None, status="CLOSED_PERMANENTLY"), SABADO.replace(hour=15))
        self.assertEqual(s["estado"], "fechado_de_vez")
        with patch("maps_client.dados_horario", return_value=_dados(_todo_dia(10, 22), status="CLOSED_TEMPORARILY")):
            self.assertTrue(maps_client.horario_funcionamento("Loja", SABADO.date())["fechado"])

    def test_sem_dado_ninguem_afirma(self):
        self.assertIsNone(hl.situacao(None, SABADO))
        self.assertIsNone(hl.situacao(_dados(None, None), SABADO))
        with patch("maps_client.configurado", return_value=True), patch("maps_client.dados_horario", return_value=None):
            self.assertIsNone(hl.consultar("Shopping", SABADO))
        with patch("maps_client.configurado", return_value=False), patch("maps_client.dados_horario") as dh:
            self.assertIsNone(hl.consultar("Shopping", SABADO))
            dh.assert_not_called()
        with patch("maps_client.configurado", return_value=True), patch("maps_client.dados_horario") as dh:
            self.assertIsNone(hl.consultar("-27.1,-48.9", SABADO))  # coordenada nao tem horario
            dh.assert_not_called()


class _Banco(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()
        maps_client._cache_horarios.clear()
        # rede nunca: se algo escapar do mock, quebra
        p = patch("maps_client.requests.post", side_effect=AssertionError("rede de verdade"))
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.conn.close()


class DadosHorarioTest(_Banco):
    def _resp(self, corpo):
        r = MagicMock()
        r.raise_for_status.return_value = None
        r.json.return_value = corpo
        return r

    def test_pede_os_5_campos_cacheia_por_horas_e_respeita_a_cota(self):
        lugar = {"displayName": {"text": "Shopping Teste"}, "regularOpeningHours": {"periods": _todo_dia(10, 22)},
                 "currentOpeningHours": {"periods": []}, "businessStatus": "OPERATIONAL", "utcOffsetMinutes": -180}
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-fake"}), \
                patch("maps_client.requests.post", return_value=self._resp({"places": [lugar]})) as post:
            d = maps_client.dados_horario("Shopping Teste")
            maps_client.dados_horario("shopping teste ")
            self.assertEqual(post.call_count, 1)
            mascara = post.call_args.kwargs["headers"]["X-Goog-FieldMask"]
            for campo in ("places.displayName", "places.regularOpeningHours", "places.currentOpeningHours",
                          "places.businessStatus", "places.utcOffsetMinutes"):
                self.assertIn(campo, mascara)
            self.assertEqual((d["nome"], d["status"], d["atual"]), ("Shopping Teste", "OPERATIONAL", []))
            # atual vazio + operando: vale a semana tipica
            self.assertEqual(hl.situacao(d, datetime.now().replace(hour=15, minute=0))["estado"], "aberto")
            # passou a validade: busca de novo
            chave = "shopping teste"
            maps_client._cache_horarios[chave] = (datetime.now() - maps_client.HORARIO_VALIDADE - timedelta(minutes=1),
                                                  maps_client._cache_horarios[chave][1])
            maps_client.dados_horario("Shopping Teste")
            self.assertEqual(post.call_count, 2)

    def test_sem_cota_ou_rede_caida_devolve_none_sem_cachear(self):
        import requests

        mes = datetime.now().strftime("%Y-%m")
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "chave-fake"}), \
                patch("maps_client.requests.post", side_effect=requests.ConnectionError("fora")) as post:
            self.assertIsNone(maps_client.dados_horario("Loja X"))
            self.assertNotIn("loja x", maps_client._cache_horarios)
            self.conn.execute("INSERT OR REPLACE INTO uso_maps (mes, nivel, chamadas) VALUES (?, 'horario_lugar', ?)",
                              (mes, maps_client.COTA_MES["horario_lugar"]))
            self.conn.commit()
            post.reset_mock()
            self.assertIsNone(maps_client.dados_horario("Loja Y"))
            post.assert_not_called()


def _agora_br(hora, minuto=0):
    return datetime.combine(date.today(), datetime.min.time()).replace(hour=hora, minute=minuto, tzinfo=ZoneInfo("America/Sao_Paulo"))


class ChatTest(_Banco):
    def setUp(self):
        super().setUp()
        for p in (patch.dict(os.environ, {"ENDERECO_CASA": "", "CIDADE_PADRAO": ""}),
                  patch("app._clima_contexto_resumo", return_value=None),
                  patch("app._agora_brasilia", return_value=_agora_br(20))):
            p.start()
            self.addCleanup(p.stop)
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def chat(self, chamadas):
        resultados = []

        def fake(mensagens, contexto, memorias, executores):
            for tool, entrada in chamadas:
                resultados.append(executores[tool](entrada))
            return "Feito.", [t for t, _ in chamadas], {"model": "claude-haiku-4-5-20251001", "input_tokens": 1,
                                                        "output_tokens": 1, "cost_usd": 0}

        with patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "vou no shopping"})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json(), resultados

    def test_ferramenta_existe_e_responde_na_hora_de_chegada(self):
        import ia.funcoes.chat as chat_mod

        self.assertIn("ver_horario_lugar", {t["name"] for t in chat_mod.CHAT_TOOLS})
        d = _dados(_todo_dia(10, 22), buscado=datetime.now())
        with patch("maps_client.configurado", return_value=True), patch("maps_client.dados_horario", return_value=d):
            _, res = self.chat([("ver_horario_lugar", {"lugar": "Shopping", "quando": "22:10"}),
                                ("ver_horario_lugar", {"lugar": "Shopping"}),
                                ("ver_horario_lugar", {"lugar": "Shopping", "quando": "amanha cedo"})])
        self.assertEqual((res[0]["estado"], res[0]["fechou_as"]), ("fechado", "22:00"))
        self.assertEqual(res[0]["horario_do_dia"], "10:00-22:00")
        self.assertEqual((res[1]["estado"], res[1]["situacao"]), ("aberto", "aberto até 22h"))  # 20h (agora)
        self.assertIn("erro", res[2])

    def test_sem_dado_a_ferramenta_manda_nao_afirmar(self):
        with patch("maps_client.configurado", return_value=True), patch("maps_client.dados_horario", return_value=None):
            _, res = self.chat([("ver_horario_lugar", {"lugar": "Loja"}), ("ver_horario_lugar", {"lugar": " "})])
        self.assertTrue(res[0]["sem_dado"])
        self.assertIn("NAO diga", res[0]["aviso"])
        self.assertIn("erro", res[1])

    def test_tarefa_de_hoje_com_lugar_fechado_avisa_a_ia_e_poe_a_linha_no_card(self):
        d = _dados(_todo_dia(10, 22), buscado=datetime.now())
        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.dados_horario", return_value=d), \
                patch("maps_client.horario_de_saida", return_value=None), \
                patch("app._saida_pro_compromisso", return_value=None):
            corpo, res = self.chat([("registrar_tarefa", {
                "titulo": "Comprar tênis", "quando": "hoje", "quando_data": date.today().isoformat(), "hora": "22:10",
                "lugar": "Shopping"})])
        self.assertIn("Fecha às 22h e tu chega 22h10.", res[0]["lugar_na_chegada"])
        card = next(c for c in corpo["cards"] if c["type"] == "tarefas_criadas")
        self.assertEqual(card["data"]["lugar_fechado"]["curta"], "fecha 22h, tu chega 22h10")


class AutomaticoTest(_Banco):
    def tarefa(self, hora, local="Shopping", dia=None, sai_na_hora=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, sai_na_hora) VALUES (?, ?, ?, ?, ?)",
            ("Comprar tênis", dia or date.today().isoformat(), hora, local, sai_na_hora))
        self.conn.commit()
        return cur.lastrowid

    def test_confere_uma_vez_por_chegada_e_guarda_nos_extras(self):
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=20)
        fechado = self.tarefa("22:10")
        aberto = self.tarefa("21:00")
        self.tarefa("22:10", local="casa")
        self.tarefa("22:10", dia=(date.today() + timedelta(days=1)).isoformat())
        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.dados_horario", return_value=_dados(_todo_dia(10, 22), buscado=agora)) as dh:
            hl.conferir_tarefas_de_hoje(self.conn, agora)
            self.assertEqual(dh.call_count, 2)  # casa e amanha nao consultam
            hl.conferir_tarefas_de_hoje(self.conn, agora + timedelta(minutes=5))
            self.assertEqual(dh.call_count, 2)  # mesma chegada: sai dos extras
        reg = db.extras_tarefa(self.conn, fechado)["horario_lugar"]
        self.assertEqual((reg["estado"], reg["chegada"]), ("fechado", "22:10"))
        self.assertEqual(db.extras_tarefa(self.conn, aberto)["horario_lugar"]["estado"], "aberto")
        card = cards.card_tarefas_criadas(self.conn, [fechado])
        self.assertEqual(card["data"]["lugar_fechado"]["estado"], "fechado")
        self.assertNotIn("lugar_fechado", cards.card_tarefas_criadas(self.conn, [aberto])["data"])
        avisos = hl.avisos_lugar_fechado(self.conn, agora)
        self.assertEqual([a[0] for a in avisos], [fechado])
        self.assertEqual(avisos[0][1], "Shopping vai estar fechado")
        self.assertNotIn("você", avisos[0][2])
        # depois da chegada nao avisa mais
        self.assertEqual(hl.avisos_lugar_fechado(self.conn, agora.replace(hour=22, minute=30)), [])

    def test_sai_na_hora_usa_a_chegada_e_nao_a_saida(self):
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=20)
        tid = self.tarefa("21:50", sai_na_hora=1)  # sai 21h50, chega ~22h05
        with patch("maps_client.configurado", return_value=True), \
                patch("maps_client.dados_horario", return_value=_dados(_todo_dia(10, 22), buscado=agora)):
            reg = hl.conferir_tarefa(self.conn, tid, agora)
            self.assertEqual((reg["chegada"], reg["estado"]), ("22:05", "fechado"))
            reg = hl.conferir_tarefa(self.conn, tid, agora, chegada_hhmm="21:58")
            self.assertEqual(reg["estado"], "fechando")

    def test_aviso_lugar_fechado_sai_uma_vez_por_tarefa_por_dia(self):
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=19)
        tid = self.tarefa("22:10")
        enviados = []

        def falso(sub, titulo, corpo, url="", tag="", **_):
            enviados.append({"titulo": titulo, "corpo": corpo, "url": url, "tag": tag})
            return True

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        self.conn.commit()
        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=falso), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._eventos_de_hoje_com_seguranca", return_value=[]), \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("maps_client.configurado", return_value=True), \
                patch("maps_client.dados_horario", return_value=_dados(_todo_dia(10, 22), buscado=agora)):
            app.verificar_e_notificar()
            app.verificar_e_notificar()
        meus = [e for e in enviados if e["tag"] == f"lugar_fechado-{tid}"]
        self.assertEqual(len(meus), 1, enviados)
        self.assertIn("Fecha às 22h e tu chega 22h10.", meus[0]["corpo"])
        self.assertEqual(meus[0]["url"], f"/?aba=tarefas&tarefa={tid}")


if __name__ == "__main__":
    unittest.main()
