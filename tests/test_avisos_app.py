"""Avisos que o app do iPhone agenda (avisos_app.py + rotas/avisos_app.py, leva 06/11/2026) e o texto
novo dos avisos (estilo C "Amigo" + 1 emoji). Banco temporario, relogio injetado, sem rede."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import avisos_app  # noqa: E402
import notificacoes  # noqa: E402
import push_client  # noqa: E402

TOKEN = {"Authorization": "Bearer token-de-teste"}
# "adiar 1 h" conta a partir de agora se a hora ja passou: relogio fixo ao meio-dia de DIA
MEIO_DIA_BR = lambda: datetime(2026, 11, 7, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))  # noqa: E731
MEIO_DIA = datetime(2026, 11, 7, 12, 0)
DIA = "2026-11-07"
AMANHA = "2026-11-08"


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "token-de-teste"})
        env.start()
        self.addCleanup(env.stop)

    def tarefa(self, titulo, hora, dia=DIA, feita=False, estilo=None):
        c = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at, estilo) VALUES (?, ?, ?, ?, ?)",
            (titulo, dia, hora, "2026-11-07 10:00:00" if feita else None, estilo))
        self.conn.commit()
        return c.lastrowid

    def montar(self, agora=MEIO_DIA, **kw):
        kw.setdefault("url_do_aviso", app._url_do_aviso)
        kw.setdefault("de_uma_tarefa", frozenset(app._AVISOS_DE_UMA_TAREFA))
        return avisos_app.montar(self.conn, agora, **kw)


def _por_tipo(itens):
    return {(i["tipo"], i["quando"][11:16]): i for i in itens}


class TextoTestCase(unittest.TestCase):
    def test_emoji_por_assunto_sem_dobrar(self):
        self.assertEqual(notificacoes.com_emoji("se_arrumar", "Começa a se arrumar"), "🪞 Começa a se arrumar")
        self.assertEqual(notificacoes.com_emoji("hora_de_sair", "🚗 Bora, hora de sair"), "🚗 Bora, hora de sair")
        self.assertEqual(notificacoes.com_emoji("tarefa_horario", "Hora de comer"), "🍽️ Hora de comer")
        self.assertEqual(notificacoes.com_emoji("tarefa_horario", "De novo · Pagar a fatura"), "⏰ De novo · Pagar a fatura")
        self.assertEqual(notificacoes.com_emoji("gasto_elevado", "Gasto da semana"), "Gasto da semana")  # sem emoji
        self.assertEqual(notificacoes.com_emoji("se_arrumar", ""), "")

    def test_titulo_da_tarefa_curto(self):
        self.assertEqual(notificacoes.titulo_tarefa("  Pagar   a fatura "), "Pagar a fatura")
        longo = notificacoes.titulo_tarefa("x" * 200)
        self.assertEqual(len(longo), notificacoes.TITULO_MAX)
        self.assertTrue(longo.endswith("…"))
        self.assertEqual(notificacoes.titulo_tarefa(""), "Tarefa")

    def test_textos_falam_com_tu_e_nao_com_voce(self):
        planos = [{"id": 1, "titulo": "Date", "hora": "20:00", "saida": datetime(2026, 11, 7, 19, 45),
                   "comecar": datetime(2026, 11, 7, 19, 5), "evento": datetime(2026, 11, 7, 20, 0),
                   "minutos_arrumar": 40, "ja_tem_tarefa_arrumar": False, "trajeto_min": 12, "parada": None}]
        textos = notificacoes.avisos_se_arrumar(planos, datetime(2026, 11, 7, 19, 5))
        textos += notificacoes.avisos_se_arrumar(planos, datetime(2026, 11, 7, 19, 45))
        self.assertEqual([t[2] for t in textos], ["Começa a se arrumar", "Bora, hora de sair"])
        for _, _, titulo, corpo in textos:
            self.assertNotIn("você", corpo.lower())
        self.assertIn("tu sai às 19:45", textos[0][3])
        self.assertIn("12 min até lá", textos[1][3])


class MontarTestCase(_Base):
    def test_tarefa_com_hora_ganha_faltam_30_e_daqui_a_pouco(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        itens = _por_tipo(self.montar())
        preparo, chegando = itens[("tarefa_preparo", "14:30")], itens[("tarefa_horario", "14:50")]
        self.assertEqual(chegando["titulo"], "⏰ Pagar a fatura")
        self.assertEqual(chegando["tag"], f"tarefa_horario-{tid}")
        self.assertIn("Daqui a pouco, às 15:00", chegando["corpo"])
        self.assertIn("faltam 30 min", preparo["corpo"])
        self.assertTrue(chegando["acoes"])
        self.assertEqual(chegando["url"], f"/?aba=tarefas&tarefa={tid}")
        self.assertEqual(chegando["quando_ts"], int(datetime(2026, 11, 7, 14, 50).timestamp()))

    def test_refeicao_so_na_hora_com_prato(self):
        self.tarefa("Comer: almoço - arroz e frango", "13:00")
        itens = self.montar()
        self.assertEqual([(i["tipo"], i["titulo"], i["corpo"]) for i in itens],
                         [("tarefa_horario", "🍽️ Hora de comer", "Almoço - arroz e frango")])

    def test_date_ganha_a_sequencia_inteira_e_nao_o_daqui_a_pouco(self):
        tid = self.tarefa("Date", "20:00")  # sem local: 15 min de folga, 40 min pra se arrumar
        itens = self.montar()
        self.assertEqual([(i["tipo"], i["quando"][11:16]) for i in itens], [
            ("saida_preparo", "18:50"), ("se_arrumar", "19:05"), ("saida_porta", "19:40"), ("hora_de_sair", "19:45")])
        self.assertTrue(all(i["tag"].endswith(f"-{tid}") for i in itens))
        self.assertEqual(itens[1]["titulo"], "🪞 Começa a se arrumar")
        self.assertEqual(itens[3]["titulo"], "🚗 Bora, hora de sair")

    def test_amanha_entra_passado_e_feita_nao(self):
        self.tarefa("Já passou", "11:00")
        self.tarefa("Feita", "16:00", feita=True)
        self.tarefa("Dentista", "09:00", dia=AMANHA)
        quandos = [(i["tipo"], i["quando"]) for i in self.montar()]
        self.assertEqual(quandos, [("tarefa_preparo", "2026-11-08T08:30"), ("tarefa_horario", "2026-11-08T08:50"),
                                   ("tarefa_agora", "2026-11-08T09:00")])

    def test_respeita_desligado_ja_mandado_e_foco(self):
        self.tarefa("Pagar a fatura", "15:00")
        self.assertEqual({i["tipo"] for i in self.montar(ligado=lambda t: t != "tarefa_preparo")},
                         {"tarefa_horario", "tarefa_agora"})
        self.assertEqual({i["tipo"] for i in self.montar(ja_notificou=lambda t, r: t == "tarefa_horario")},
                         {"tarefa_preparo", "tarefa_agora"})
        # hiperfoco ate 16h: so o critico (tarefa_horario) passa, e o "e agora" que estende ele
        segurado = self.montar(segurar_ate=datetime(2026, 11, 7, 16, 0))
        self.assertEqual({i["tipo"] for i in segurado}, {"tarefa_horario", "tarefa_agora"})
        # tarefa_horario fora dos criticos: o "e agora" tambem fica segurado
        segurado = self.montar(segurar_ate=datetime(2026, 11, 7, 16, 0), criticos=frozenset({"voo_sair"}))
        self.assertEqual(segurado, [])

    def test_contado_como_mandado_porque_o_app_vai_tocar_continua_na_lista(self):
        # 04:14 o servidor viu que o app avisa 04:18 e marcou como mandado; a sincronizada das 04:15 nao
        # pode tirar o aviso do app (senao ninguem avisa). Bug real de 06/11.
        tid = self.tarefa("Teste", "12:48")
        agora = datetime(2026, 11, 7, 12, 15)
        ag = {f"tarefa_preparo-{tid}": [int(datetime(2026, 11, 7, 12, 18).timestamp())]}
        itens = self.montar(agora, ja_notificou=lambda t, r: t == "tarefa_preparo", agendados=ag)
        self.assertEqual([i["tipo"] for i in itens], ["tarefa_preparo", "tarefa_horario", "tarefa_agora"])
        # mandado de verdade pelo navegador (o app nao tinha agendado): sai da lista, nao chega dois
        itens = self.montar(agora, ja_notificou=lambda t, r: t == "tarefa_preparo", agendados={})
        self.assertEqual([i["tipo"] for i in itens], ["tarefa_horario", "tarefa_agora"])

    def test_ja_mandado_hoje_nao_tira_o_de_amanha(self):
        self.tarefa("Dentista", "09:00", dia=AMANHA)
        self.assertEqual(len(self.montar(ja_notificou=lambda t, r: True)), 3)

    def test_e_agora_na_hora_exata_com_botoes(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        agora = _por_tipo(self.montar())[("tarefa_agora", "15:00")]
        self.assertEqual(agora["titulo"], "⏰ Pagar a fatura")
        self.assertEqual(agora["corpo"], "Deu 15:00, é agora. Quando terminar, toca em Feito.")
        self.assertEqual(agora["tag"], f"tarefa_agora-{tid}")
        self.assertEqual(agora["id"], f"painel-tarefa_agora-{tid}-20261107")
        self.assertTrue(agora["acoes"])
        self.assertEqual(agora["url"], f"/?aba=tarefas&tarefa={tid}")
        self.assertNotIn("você", agora["corpo"].lower())

    def test_refeicao_nao_ganha_e_agora(self):
        self.tarefa("Comer: janta", "19:00")
        self.assertNotIn("tarefa_agora", {i["tipo"] for i in self.montar()})

    def test_e_agora_pode_ser_desligado(self):
        self.tarefa("Pagar a fatura", "15:00")
        self.assertNotIn("tarefa_agora", {i["tipo"] for i in self.montar(ligado=lambda t: t != "tarefa_agora")})

    def test_voo_usa_a_conta_do_servidor(self):
        c = self.conn.execute("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '15:00')", (DIA,))
        self.conn.commit()
        visto = []

        def saida(voo):
            visto.append(voo["id"])
            return {"sair_ate": datetime(2026, 11, 7, 14, 0), "texto": "Sai até 14:00 pra pegar o briefing."}

        [item] = self.montar(saida_voo=saida)
        self.assertEqual(visto, [c.lastrowid])
        self.assertEqual((item["tipo"], item["quando"][11:16], item["titulo"]), ("voo_sair", "13:38", "✈️ Bora pro voo"))
        self.assertFalse(item["acoes"])

    def test_voo_com_maps_fora_nao_derruba(self):
        self.conn.execute("INSERT INTO voos (data, origem, destino, hora) VALUES (?, 'SSBL', 'SSBL', '15:00')", (DIA,))
        self.conn.commit()

        def quebra(voo):
            raise RuntimeError("sem rede")

        self.assertEqual(self.montar(saida_voo=quebra), [])

    def test_no_maximo_40(self):
        for h in range(13, 23):
            for m in (0, 10, 20, 30, 40, 50):
                self.tarefa(f"t{h}{m}", f"{h:02d}:{m:02d}")
        itens = self.montar()
        self.assertEqual(len(itens), avisos_app.MAX_ITENS)
        self.assertEqual(itens, sorted(itens, key=lambda i: i["quando_ts"]))


class AgendadosTestCase(_Base):
    def test_coberto_dentro_da_tolerancia(self):
        t = datetime(2026, 11, 7, 14, 50)
        avisos_app.gravar_agendados(self.conn, [{"tag": "tarefa_horario-1", "quando_ts": int(t.timestamp())},
                                                {"tag": 5, "quando_ts": 1}, {"tag": "x", "quando_ts": True}, "lixo"], MEIO_DIA)
        ag = avisos_app.carregar_agendados(self.conn, t)
        self.assertEqual(list(ag), ["tarefa_horario-1"])
        self.assertTrue(avisos_app.coberto(ag, "tarefa_horario-1", t + timedelta(minutes=4)))
        self.assertFalse(avisos_app.coberto(ag, "tarefa_horario-1", t + timedelta(minutes=8)))
        self.assertFalse(avisos_app.coberto(ag, "tarefa_preparo-1", t))

    def test_app_sumido_faz_36h_o_navegador_volta(self):
        t = datetime(2026, 11, 7, 14, 50)
        avisos_app.gravar_agendados(self.conn, [{"tag": "a-1", "quando_ts": int(t.timestamp())}], t - timedelta(hours=37))
        self.assertEqual(avisos_app.carregar_agendados(self.conn, t), {})

    def test_lixo_no_banco_nao_quebra(self):
        db.definir_configuracao(self.conn, avisos_app.CHAVE, "{nao e json")
        self.conn.commit()
        self.assertEqual(avisos_app.carregar_agendados(self.conn, MEIO_DIA), {})


class RotasTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()

    def test_sem_token_401(self):
        for metodo, url in (("get", "/api/app/avisos"), ("post", "/api/app/avisos/agendados"), ("post", "/api/app/aviso/acao")):
            self.assertEqual(getattr(self.client, metodo)(url).status_code, 401, url)
            self.assertEqual(getattr(self.client, metodo)(url, headers={"Authorization": "Bearer errado"}).status_code, 401, url)
        # token na URL nao vale (so no header)
        self.assertEqual(self.client.get("/api/app/avisos?token=token-de-teste").status_code, 401)

    def test_lista_avisos_de_amanha(self):
        amanha = (datetime.now() + timedelta(days=1)).date().isoformat()
        tid = self.tarefa("Dentista", "10:00", dia=amanha)
        r = self.client.get("/api/app/avisos", headers=TOKEN)
        self.assertEqual(r.status_code, 200)
        tags = [i["tag"] for i in r.get_json()["avisos"]]
        self.assertEqual(tags, [f"tarefa_preparo-{tid}", f"tarefa_horario-{tid}", f"tarefa_agora-{tid}"])

    def test_guarda_o_que_o_app_agendou(self):
        r = self.client.post("/api/app/avisos/agendados", headers=TOKEN,
                             json={"itens": [{"tag": "tarefa_horario-3", "quando_ts": 1999999999}]})
        self.assertEqual(r.get_json(), {"ok": True, "guardados": 1})
        self.assertEqual(self.client.post("/api/app/avisos/agendados", headers=TOKEN, json={"itens": "x"}).status_code, 400)

    @patch.object(app, "_agora_brasilia", MEIO_DIA_BR)
    def test_feito_e_adiar_pelo_aviso_do_app(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": f"tarefa_horario-{tid}", "acao": "feito"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIsNotNone(self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (tid,)).fetchone()[0])
        tid2 = self.tarefa("Ligar pro banco", "15:00")
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": f"tarefa_horario-{tid2}", "acao": "adiar"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["hora"], "16:00")
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": "x" * 200, "acao": "feito"})
        self.assertEqual(r.status_code, 400)

    def test_toque_para_a_insistencia(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        tag = f"tarefa_horario-{tid}"
        db.registrar_aviso_insistente(self.conn, "tarefa_horario", tid, "Pagar a fatura", "c", tag, datetime.now())
        self.conn.commit()
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": tag, "acao": "toque"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["parou"], 1)


class SemAvisoDuplicadoTestCase(_Base):
    """No tick do servidor: o que o app agendou pra agora nao sai pelo navegador, mas conta como mandado
    (nao repete no tick seguinte) e a insistencia continua registrada."""

    def _rodar(self, agora):
        enviados = []

        def falso(sub, titulo, corpo, url="", tag="", **_):
            enviados.append({"titulo": titulo, "corpo": corpo, "tag": tag})
            return True

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar", side_effect=falso), \
                patch("telegram_bot.configurado", return_value=False), \
                patch("app._buscar_contas_a_vencer_construtora", return_value=None), \
                patch("app._eventos_de_hoje_com_seguranca", return_value=[]), \
                patch("app.datetime", _Agora), patch("notificacoes.datetime", _Agora), \
                patch("app.date", type("D", (), {"today": staticmethod(lambda: agora.date()),
                                                   "fromisoformat": staticmethod(datetime.fromisoformat)})):
            app.verificar_e_notificar()
        return enviados

    def setUp(self):
        super().setUp()
        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        self.conn.commit()

    def test_navegador_manda_com_emoji_quando_o_app_nao_agendou(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        enviados = [e for e in self._rodar(datetime(2026, 11, 7, 14, 51)) if e["tag"] == f"tarefa_horario-{tid}"]
        self.assertEqual([e["titulo"] for e in enviados], ["⏰ Pagar a fatura"])

    def test_agendado_no_app_nao_sai_pelo_navegador(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        tag = f"tarefa_horario-{tid}"
        avisos_app.gravar_agendados(self.conn, [{"tag": tag, "quando_ts": int(datetime(2026, 11, 7, 14, 50).timestamp())}],
                                    datetime(2026, 11, 7, 12, 0))
        self.assertEqual([e for e in self._rodar(datetime(2026, 11, 7, 14, 51)) if e["tag"] == tag], [])
        self.assertTrue(db.ja_notificou_hoje(self.conn, "tarefa_horario", tid))
        pend = [a for a in db.avisos_insistentes_pendentes(self.conn) if a["tag"] == tag]
        self.assertEqual(len(pend), 1)  # a insistencia continua pelo navegador
        self.assertEqual([e for e in self._rodar(datetime(2026, 11, 7, 14, 56)) if e["tag"] == tag], [])

    def test_hora_mudou_depois_de_agendar_o_navegador_avisa(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        tag = f"tarefa_horario-{tid}"
        # o app agendou pra 13:50 (tarefa era 14:00 quando sincronizou)
        avisos_app.gravar_agendados(self.conn, [{"tag": tag, "quando_ts": int(datetime(2026, 11, 7, 13, 50).timestamp())}],
                                    datetime(2026, 11, 7, 12, 0))
        self.assertEqual(len([e for e in self._rodar(datetime(2026, 11, 7, 14, 51)) if e["tag"] == tag]), 1)


if __name__ == "__main__":
    unittest.main()


class EAgoraSemDuplicarTestCase(_Base):
    """Leva 06/11 (docs/briefings/2026-11-06-ao-vivo-tarefa.md): o "e agora" so o app manda. A repeticao do
    aviso de tarefa que cairia na mesma hora fica quieta; mexer no "e agora" para a insistencia."""

    AGORA = datetime(2026, 11, 7, 15, 0, 30)

    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()

    def _repetir(self, agendados):
        enviados = []
        agora = self.AGORA

        class _Agora(datetime):
            @classmethod
            def now(cls, tz=None):
                return agora

        sub = {"subscription_json": "{}", "endpoint": "https://push.invalid/x"}
        with patch.object(push_client, "enviar", side_effect=lambda *a, **k: enviados.append(k.get("tag")) or True), \
                patch("app.datetime", _Agora):
            app._repetir_avisos_insistentes(self.conn, [sub], False, False, agendados)
        return enviados

    def _insistente(self, tid):
        db.registrar_aviso_insistente(self.conn, "tarefa_horario", tid, "Pagar a fatura", "c",
                                      f"tarefa_horario-{tid}", datetime(2026, 11, 7, 14, 50))
        self.conn.commit()

    def test_repeticao_na_hora_fica_quieta_quando_o_app_toca_o_e_agora(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        self._insistente(tid)
        ag = {f"tarefa_agora-{tid}": [int(datetime(2026, 11, 7, 15, 0).timestamp())]}
        self.assertEqual(self._repetir(ag), [])
        tentativas = self.conn.execute("SELECT tentativas FROM avisos_insistentes").fetchone()[0]
        self.assertEqual(tentativas, 2)  # contou como repetida: a proxima (30 min) segue normal

    def test_sem_o_app_a_repeticao_sai_normal(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        self._insistente(tid)
        self.assertEqual(self._repetir({}), [f"tarefa_horario-{tid}"])

    def test_mexer_no_e_agora_para_a_insistencia(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        self._insistente(tid)
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": f"tarefa_agora-{tid}", "acao": "toque"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(db.avisos_insistentes_pendentes(self.conn), [])

    @patch.object(app, "_agora_brasilia", MEIO_DIA_BR)
    def test_feito_e_adiar_pelo_e_agora(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": f"tarefa_agora-{tid}", "acao": "feito"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIsNotNone(self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (tid,)).fetchone()[0])
        tid2 = self.tarefa("Ligar pro banco", "15:00")
        r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": f"tarefa_agora-{tid2}", "acao": "adiar"})
        self.assertEqual(r.get_json()["hora"], "16:00")

    def test_tag_torta_nao_quebra(self):
        for tag in ("tarefa_agora-", "tarefa_agora-abc", "tarefa_agora-1-2"):
            r = self.client.post("/api/app/aviso/acao", headers=TOKEN, json={"tag": tag, "acao": "feito"})
            self.assertIn(r.status_code, (400, 404), tag)
