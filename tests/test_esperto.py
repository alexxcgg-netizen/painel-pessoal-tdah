"""Painel mais esperto, frente 7 (06/11/2026): voo decidido na vespera (voo_vespera.py), pergunta na hora certa
(hora_certa.py), descobre rotinas / tarefa adiada 3x (rotinas_esperto.py) e as rotas (rotas/esperto.py).
Banco temporario, TAF falso (buscar injetado), clima e Claude nunca chamados de verdade."""
import json
import os
import tempfile
import time as _time
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import auth  # noqa: E402
import avisos_app  # noqa: E402
import cards  # noqa: E402
import criptografia  # noqa: E402
import hora_certa  # noqa: E402
import rotinas_esperto  # noqa: E402
import voo_vespera  # noqa: E402

PIN = "246813"
HOJE = date.today()
AMANHA = HOJE + timedelta(days=1)


def _em(hhmm: str, dia: date | None = None) -> datetime:
    return datetime.combine(dia or HOJE, time(*map(int, hhmm.split(":"))))


def _taf(corpo: str) -> str:
    """TAF de SBNF emitido hoje 17Z (14h local), valendo de hoje 18Z a amanha 18Z (15h local)."""
    return f"TAF SBNF {HOJE.day:02d}1700Z {HOJE.day:02d}18/{AMANHA.day:02d}18 {corpo}"


BOM = _taf("09003KT 9999 FEW030")
RUIM_MELHORA = _taf(f"09003KT 9999 BKN008 FM{AMANHA.day:02d}1500 12003KT 9999 SCT040")
RUIM_SEMPRE = _taf("09003KT 9999 BKN008")
MVFR = _taf("09003KT 9999 BKN025")


def _buscar(taf):
    import metar

    def f(icao):
        if taf is None:
            return {"taf": None}
        return {"taf": taf, "taf_segmentos": metar.decodificar_taf(metar._tokens_uteis_taf(taf))}
    return f


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()

    def voo(self, hora="09:30", dia=AMANHA, origem="SSBL"):
        c = self.conn.execute("INSERT INTO voos (data, hora, origem, destino) VALUES (?, ?, ?, ?)",
                              (dia.isoformat(), hora, origem, origem))
        self.conn.commit()
        return c.lastrowid

    def tarefa(self, titulo, dia=HOJE, hora=None, **extra):
        cols = ["title", "due_date", "hora"] + list(extra)
        c = self.conn.execute(f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                              (titulo, dia.isoformat() if dia else None, hora, *extra.values()))
        self.conn.commit()
        return c.lastrowid

    def card_vespera(self, voo_id, acordar="07:00", sair="07:45"):
        db.salvar_mensagem_chat(self.conn, "assistant", "Amanhã tem voo.",
                                [{"type": "vespera_voo", "id": "c1", "data": {"id": voo_id, "acordar": acordar, "sair": sair}}])

    def chat(self):
        saida = []
        for r in self.conn.execute("SELECT texto, cards_json FROM chat_mensagens ORDER BY id").fetchall():
            cs = json.loads(criptografia.descriptografar(r["cards_json"])) if r["cards_json"] else []
            saida.append((r["texto"], cs))
        return saida

    def visita(self, lugar, chegada, saida=None):
        self.conn.execute("INSERT INTO visitas (lat, lon, precisao, chegada, saida, lugar) VALUES (0, 0, 10, ?, ?, ?)",
                          (chegada.isoformat(timespec="seconds"), saida.isoformat(timespec="seconds") if saida else None, lugar))
        self.conn.commit()


# ====================================================================== voo decidido na vespera
class VooDecisaoTestCase(_Base):
    NOITE = _em("20:30")

    def decidir(self, taf, hora="09:30", agora=None, fase="vespera"):
        vid = self.voo(hora)
        v = self.conn.execute("SELECT * FROM voos WHERE id = ?", (vid,)).fetchone()
        return voo_vespera.decidir(self.conn, v, agora or self.NOITE, _buscar(taf), fase)

    def test_bom_voa_com_os_quatro_quadradinhos(self):
        vid = self.voo()
        self.card_vespera(vid)
        v = self.conn.execute("SELECT * FROM voos WHERE id = ?", (vid,)).fetchone()
        d = voo_vespera.decidir(self.conn, v, self.NOITE, _buscar(BOM))
        self.assertEqual(d["veredito"], "voa")
        self.assertEqual(d["frase"], "Amanhã voa.")
        self.assertEqual([c["rotulo"] for c in d["conds"]], ["Teto", "Visibilidade", "Vento", "Sono"])
        self.assertEqual(d["conds"][3], {"rotulo": "Sono", "valor": "8 h · deita 23h", "tom": "ok"})
        self.assertTrue(all(c["tom"] == "ok" for c in d["conds"]))
        self.assertTrue(d["nota"].startswith("TAF das 14h cobre a hora do voo. Confiro de novo às 06:30 e te aviso se mudar."))
        self.assertIn("SBNF", d["nota"])  # SSBL nao tem TAF: diz de onde veio
        self.assertIsNone(d["remarcar"])

    def test_teto_baixo_nao_da_e_sugere_horario_que_melhora(self):
        d = self.decidir(RUIM_MELHORA)
        self.assertEqual(d["veredito"], "nao")
        self.assertEqual(d["frase"], "Amanhã não dá.")
        self.assertEqual(d["conds"][0], {"rotulo": "Teto", "valor": "800 ft", "tom": "ruim"})
        self.assertIn("Teto 800 ft na hora do voo", d["porque"])
        self.assertEqual(d["remarcar"], {"data": AMANHA.isoformat(), "hora": "12:00"})
        self.assertIn("Remarco pras 12:00?", d["nota"])

    def test_nao_da_sem_horario_bom_so_pergunta(self):
        d = self.decidir(RUIM_SEMPRE)
        self.assertEqual(d["veredito"], "nao")
        self.assertIsNone(d["remarcar"])
        self.assertTrue(d["perguntar_remarcar"])
        self.assertIn("Quer remarcar?", d["nota"])

    def test_remarcacao_pula_horario_ocupado(self):
        self.tarefa("Dentista", AMANHA, "12:30")
        d = self.decidir(RUIM_MELHORA)
        self.assertEqual(d["remarcar"]["hora"], "14:00")  # 12:00/12:30/13:00/13:30 a menos de 1h30 do dentista

    def test_mvfr_e_no_limite(self):
        d = self.decidir(MVFR)
        self.assertEqual(d["veredito"], "limite")
        self.assertEqual(d["frase"], "Amanhã dá, no limite.")
        self.assertEqual(d["conds"][0]["tom"], "limite")

    def test_taf_nao_cobre_a_hora_nunca_inventa(self):
        d = self.decidir(BOM, hora="16:00")
        self.assertEqual(d["veredito"], "incerto")
        self.assertEqual(d["frase"], "Ainda não dá pra saber.")
        self.assertEqual(d["conds"], [])
        self.assertIn("vai até amanhã 15:00 e o voo é às 16:00", d["porque"])

    def test_sem_taf_diz_que_nao_conseguiu(self):
        d = self.decidir(None)
        self.assertEqual(d["veredito"], "incerto")
        self.assertIn("Não consegui o TAF de SBNF", d["porque"])

    def test_balada_na_vespera_vira_aviso(self):
        vid = self.voo()
        self.card_vespera(vid, acordar="07:00")
        self.tarefa("Balada no Green", HOJE, "23:00", estilo="balada")
        v = self.conn.execute("SELECT * FROM voos WHERE id = ?", (vid,)).fetchone()
        d = voo_vespera.decidir(self.conn, v, self.NOITE, _buscar(BOM))
        self.assertEqual(d["veredito"], "limite")  # sono sozinho nunca vira "nao da"
        self.assertEqual(d["conds"][3], {"rotulo": "Véspera", "valor": "balada até 3h", "tom": "ruim"})
        self.assertIn("Balada até 3h: dá só 4 h de sono", d["nota"])

    def test_verificar_publica_uma_vez_e_so_avisa_se_mudar(self):
        vid = self.voo()
        voo_vespera.verificar(self.conn, self.NOITE, _buscar(BOM))
        msgs = self.chat()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0][0], "Amanhã voa.")
        self.assertEqual(msgs[0][1][0]["type"], "voo_decisao")
        fila = hora_certa.pendentes(self.conn, self.NOITE)
        self.assertEqual([(i["tipo"], i["titulo"]) for i in fila], [("voo_decisao", "Amanhã voa")])
        # mesmo tick de novo / mais tarde na noite: nada novo
        voo_vespera.verificar(self.conn, self.NOITE + timedelta(minutes=5), _buscar(BOM))
        self.assertEqual(len(self.chat()), 1)
        # de manha, igual: fica quieto
        manha = _em("06:30", AMANHA)
        voo_vespera.verificar(self.conn, manha, _buscar(BOM))
        self.assertEqual(len(self.chat()), 1)
        # mudou: avisa
        voo_vespera.verificar(self.conn, manha + timedelta(minutes=5), _buscar(RUIM_MELHORA))
        self.assertEqual(len(self.chat()), 1)  # so reconfere na hora marcada (proxima ja passou: nada ate amanha)
        st = json.loads(db.obter_configuracao(self.conn, f"voo_decisao_{vid}"))
        self.assertIsNone(st["proxima"])

    def test_manha_muda_veredito(self):
        self.voo()
        voo_vespera.verificar(self.conn, self.NOITE, _buscar(BOM))
        voo_vespera.verificar(self.conn, _em("06:30", AMANHA), _buscar(RUIM_MELHORA))
        msgs = self.chat()
        self.assertEqual(len(msgs), 2)
        self.assertTrue(msgs[1][0].startswith("Mudou: hoje não dá."), msgs[1][0])

    def test_fora_da_janela_nao_faz_nada(self):
        self.voo()
        voo_vespera.verificar(self.conn, _em("15:00"), _buscar(BOM))
        self.assertEqual(self.chat(), [])

    def test_incerto_reconfere_de_hora_em_hora(self):
        vid = self.voo("16:00")
        voo_vespera.verificar(self.conn, self.NOITE, _buscar(BOM))
        st = json.loads(db.obter_configuracao(self.conn, f"voo_decisao_{vid}"))
        self.assertEqual(st["proxima"], _em("21:00").isoformat(timespec="minutes"))
        fila = hora_certa.pendentes(self.conn, self.NOITE)
        self.assertEqual(fila[0]["titulo"], "Voo de amanhã: ainda não dá pra saber")
        self.assertIn("Confiro de novo às 21:00.", fila[0]["corpo"])

    def test_push_da_vespera_vira_um_so(self):
        vid = self.voo()
        self.card_vespera(vid, "06:15", "07:00")
        db.marcar_notificado(self.conn, "vespera_voo_chat", vid)
        voo_vespera.verificar(self.conn, self.NOITE, _buscar(BOM))
        fila = hora_certa.pendentes(self.conn, self.NOITE)
        self.assertIn("Acorda 06:15, sai 07:00.", fila[0]["corpo"])
        self.assertTrue(db.ja_notificou_hoje(self.conn, "vespera_voo"))

    def test_remarcar_com_desfazer(self):
        vid = self.voo()
        r = voo_vespera.remarcar(self.conn, vid, "12:00")
        self.assertEqual(r["hora"], "12:00")
        self.assertEqual(self.conn.execute("SELECT hora FROM voos WHERE id = ?", (vid,)).fetchone()["hora"], "12:00")
        c = app.app.test_client()
        c.post("/login", json={"pin": PIN})
        self.assertEqual(c.post(f"/api/desfazer/{r['token']}").status_code, 200)
        self.assertEqual(self.conn.execute("SELECT hora FROM voos WHERE id = ?", (vid,)).fetchone()["hora"], "09:30")
        self.assertIsNone(voo_vespera.remarcar(self.conn, vid, "25:00"))
        self.assertIsNone(voo_vespera.remarcar(self.conn, 999, "12:00"))

    def test_card_no_contrato(self):
        self.assertIn("voo_decisao", cards.TIPOS_CARD)
        self.assertIn("rotina_proposta", cards.TIPOS_CARD)
        self.assertIn("tarefa_adiada", cards.TIPOS_CARD)


# ====================================================================== pergunta na hora certa
class HoraCertaTestCase(_Base):
    def setUp(self):
        super().setUp()
        p = patch("onde_estou.mensagem_chegada", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_chegou_em_casa_lembra_a_mais_curta(self):
        self.tarefa("Organizar a gaveta", esforco="media")
        curta = self.tarefa("Pagar o boleto (até 18:00)", esforco="baixa")
        self.tarefa("Date (até 23:00)", hora="21:00", estilo="date")
        self.visita("casa", _em("19:10"))
        saida = hora_certa.para_push(self.conn, _em("19:12"), {})
        self.assertEqual(len(saida), 1)
        tipo, ref, titulo, corpo = saida[0]
        self.assertEqual((tipo, ref, titulo), ("casa_tarefa", curta, "Chegou em casa"))
        self.assertTrue(corpo.startswith("Ainda falta “Pagar o boleto” hoje."), corpo)
        # mesma chegada no proximo tick: nada novo
        app_marca = [t for t, *_ in hora_certa.para_push(self.conn, _em("19:17"), {})]
        self.assertEqual(app_marca, ["casa_tarefa"])  # ainda pendente (nao marcado); o loop do app marca
        db.marcar_notificado(self.conn, "casa_tarefa", curta)
        self.assertEqual(hora_certa.para_push(self.conn, _em("19:22"), {}), [])

    def test_inegociavel_vem_primeiro_e_tarefa_com_hora_futura_fica_de_fora(self):
        self.tarefa("Ligar pro banco", hora="21:30")
        ineg = self.tarefa("Remédio", inegociavel=1)
        self.tarefa("Rápida", esforco="baixa")
        self.visita("casa", _em("19:00"))
        saida = hora_certa.para_push(self.conn, _em("19:05"), {})
        self.assertEqual(saida[0][1], ineg)

    def test_antes_das_18h_ou_sem_tarefa_nao_avisa(self):
        self.tarefa("Algo")
        self.visita("casa", _em("17:30"))
        self.assertEqual(hora_certa.para_push(self.conn, _em("17:35"), {}), [])
        self.conn.execute("DELETE FROM tasks")
        self.conn.commit()
        self.visita("casa", _em("19:00"))
        self.assertEqual(hora_certa.para_push(self.conn, _em("19:05"), {}), [])

    def test_onde_estou_ja_falou_nao_repete(self):
        self.tarefa("Algo")
        self.visita("casa", _em("19:00"))
        with patch("onde_estou.mensagem_chegada", return_value=("x", "Chegou em casa", "Próxima: ...")):
            self.assertEqual(hora_certa.para_push(self.conn, _em("19:05"), {}), [])

    def test_mesma_tarefa_nao_repete_no_dia(self):
        t = self.tarefa("Algo")
        db.marcar_notificado(self.conn, "casa_tarefa", t)
        self.visita("casa", _em("19:00"))
        self.assertEqual(hora_certa.para_push(self.conn, _em("19:05"), {}), [])

    def test_app_agenda_e_push_nao_repete(self):
        t = self.tarefa("Algo")
        self.visita("casa", _em("19:00"))
        agora = _em("19:05")
        app_itens = hora_certa.para_app(self.conn, agora, {})
        self.assertEqual(len(app_itens), 1)
        tipo, ref, quando, titulo, _ = app_itens[0]
        self.assertEqual((tipo, ref), ("casa_tarefa", t))
        self.assertTrue(agora < quando <= agora + timedelta(minutes=2))
        agendados = {f"casa_tarefa-{t}": [quando.timestamp()]}
        self.assertEqual(hora_certa.para_push(self.conn, agora, agendados), [])  # o app toca
        hora_certa.para_push(self.conn, quando + timedelta(minutes=1), agendados)  # tocou: sai da fila
        self.assertTrue(db.ja_notificou_hoje(self.conn, "casa_tarefa", t))

    def test_montar_do_app_inclui_o_aviso_sem_botao(self):
        t = self.tarefa("Algo")
        self.visita("casa", _em("19:00"))
        itens = avisos_app.montar(self.conn, _em("19:05"), url_do_aviso=app._url_do_aviso,
                                  de_uma_tarefa=frozenset(app._AVISOS_DE_UMA_TAREFA))
        casa = [i for i in itens if i["tipo"] == "casa_tarefa"]
        self.assertEqual(len(casa), 1)
        self.assertEqual(casa[0]["tag"], f"casa_tarefa-{t}")
        self.assertFalse(casa[0]["acoes"])  # o app nativo so tem Feito/Adiar 1 h: o toque abre a tarefa

    def test_botoes_do_push(self):
        self.assertEqual(app._acoes_do_aviso("casa_tarefa", "casa_tarefa-5"), hora_certa.ACOES_CASA)
        self.assertEqual(app._url_do_aviso("casa_tarefa", "casa_tarefa-5"), "/?aba=tarefas&tarefa=5")
        self.assertEqual(app._url_do_aviso("voo_decisao", "voo_decisao-1"), "/?aba=assistente")
        self.assertEqual(app._url_do_aviso("tarefa_adiada", "tarefa_adiada-1"), "/?aba=assistente")
        self.assertIn("voo_decisao", app.NOTIFICACOES_URGENTES)

    def test_feito_e_amanha_pelo_aviso(self):
        a = self.tarefa("Algo", hora="08:00")
        b = self.tarefa("Outra")
        c = app.app.test_client()
        c.post("/login", json={"pin": PIN})
        r = c.post("/api/push/acao", json={"tag": f"casa_tarefa-{a}", "acao": "feito"}).get_json()
        self.assertTrue(r["ok"])
        self.assertIsNotNone(self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (a,)).fetchone()[0])
        r = c.post("/api/push/acao", json={"tag": f"casa_tarefa-{b}", "acao": "adiar"}).get_json()
        self.assertEqual(r["mensagem"], "Passei pra amanhã.")
        self.assertEqual(self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (b,)).fetchone()[0], AMANHA.isoformat())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tarefas_adiadas WHERE task_id = ?", (b,)).fetchone()[0], 1)

    def test_saiu_da_academia_pergunta_do_treino(self):
        db.salvar_ficha_treino(self.conn, "Peito", "Supino reto 4x10\nCrucifixo 3x12")
        self.visita("academia", _em("18:00"), _em("19:10"))
        saida = hora_certa.para_push(self.conn, _em("19:15"), {})
        self.assertEqual([(t, ti) for t, _, ti, _ in saida], [("treino_pergunta", "Como foi o treino?")])
        msgs = self.chat()
        self.assertEqual(len(msgs), 1)
        self.assertTrue(msgs[0][0].startswith("Saiu da academia. Como foi?"), msgs[0][0])
        self.assertEqual(msgs[0][1][0]["type"], "treino_agora")
        # outra saida no mesmo dia: nao pergunta de novo
        self.visita("academia", _em("19:30"), _em("19:40"))
        hora_certa.para_push(self.conn, _em("19:45"), {})
        self.assertEqual(len(self.chat()), 1)

    def test_treino_ja_registrado_nao_pergunta(self):
        self.conn.execute("INSERT INTO treinos (data, grupo) VALUES (?, 'Peito')", (HOJE.isoformat(),))
        self.conn.commit()
        self.visita("academia", _em("18:00"), _em("19:10"))
        self.assertEqual(hora_certa.para_push(self.conn, _em("19:15"), {}), [])
        self.assertEqual(self.chat(), [])

    def test_silencio_segura_menos_o_voo(self):
        hora_certa.enfileirar(self.conn, "casa_tarefa", 1, "a", "b", _em("22:30"), _em("23:00"))
        hora_certa.enfileirar(self.conn, "voo_decisao", 2, "a", "b", _em("22:30"), _em("23:00"))
        tipos = [t for t, *_ in hora_certa.para_app(self.conn, _em("22:30"), {})]
        self.assertEqual(tipos, ["voo_decisao"])


# ====================================================================== descobre rotinas
class RotinasTestCase(_Base):
    AGORA = _em("10:00")

    def _semanas(self, n, weekday, hhmm, lugar="academia", desvio=0):
        """visitas no `weekday` das ultimas n semanas (a mais recente na semana passada)."""
        base = HOJE - timedelta(days=(HOJE.weekday() - weekday) % 7 or 7)
        for i in range(n):
            h, m = map(int, hhmm.split(":"))
            dt = datetime.combine(base - timedelta(weeks=i), time(h, m)) + timedelta(minutes=desvio * (i % 2))
            self.visita(lugar, dt, dt + timedelta(hours=1))

    def test_academia_terca_e_quinta(self):
        self._semanas(3, 1, "18:05")
        self._semanas(3, 3, "17:55")
        ps = rotinas_esperto.padroes_lugar(self.conn, self.AGORA)
        self.assertEqual(len(ps), 1)
        p = ps[0]
        self.assertEqual(p["dias"], [1, 3])
        self.assertEqual(p["hora"], "18:00")
        self.assertEqual(p["semanas"], 3)
        self.assertEqual(p["titulo"], "Academia toda terça e quinta")

    def test_duas_semanas_so_nao_e_rotina(self):
        self._semanas(2, 1, "18:00")
        self.assertEqual(rotinas_esperto.padroes_lugar(self.conn, self.AGORA), [])

    def test_hora_espalhada_nao_e_rotina(self):
        base = HOJE - timedelta(days=(HOJE.weekday() - 1) % 7 or 7)
        for i, hh in enumerate((8, 13, 19)):
            dt = datetime.combine(base - timedelta(weeks=i), time(hh, 0))
            self.visita("academia", dt, dt + timedelta(hours=1))
        self.assertEqual(rotinas_esperto.padroes_lugar(self.conn, self.AGORA), [])

    def test_casa_nunca_vira_rotina(self):
        self._semanas(4, 2, "19:00", lugar="casa")
        self.assertEqual(rotinas_esperto.padroes_lugar(self.conn, self.AGORA), [])

    def test_dias_texto(self):
        self.assertEqual(rotinas_esperto.dias_texto([5]), "todo sábado")
        self.assertEqual(rotinas_esperto.dias_texto([1, 3]), "toda terça e quinta")
        self.assertEqual(rotinas_esperto.dias_texto([0, 2, 4]), "toda segunda, quarta e sexta")
        self.assertEqual(rotinas_esperto.dias_texto([1, 5]), "toda terça e todo sábado")

    def test_tarefa_repetida_no_mesmo_dia(self):
        base = HOJE - timedelta(days=(HOJE.weekday() - 0) % 7 or 7)
        for i in range(3):
            self.tarefa("Levar o lixo" if i else "levar o LIXO", base - timedelta(weeks=i), "20:00")
        ps = rotinas_esperto.padroes_tarefa(self.conn, self.AGORA)
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0]["dias"], [0])
        self.assertEqual(ps[0]["hora"], "20:00")

    def test_card_uma_vez_sim_cria_rotina_com_desfazer(self):
        self._semanas(3, 1, "18:00")
        rotinas_esperto.verificar(self.conn, self.AGORA)
        msgs = self.chat()
        self.assertEqual(len(msgs), 1)
        c = msgs[0][1][0]
        self.assertEqual(c["type"], "rotina_proposta")
        self.assertEqual(c["data"]["sub"], "18:00 · já faz 3 semanas")
        fila = hora_certa.pendentes(self.conn, self.AGORA)
        self.assertEqual([i["tipo"] for i in fila], ["rotina_descoberta"])
        # nao repete no dia nem depois de proposta
        rotinas_esperto.verificar(self.conn, self.AGORA + timedelta(hours=1))
        self.assertEqual(len(self.chat()), 1)
        self.assertEqual(rotinas_esperto.propostas_novas(self.conn, self.AGORA), [])
        r = rotinas_esperto.responder_rotina(self.conn, c["data"]["chave"], "sim", self.AGORA)
        self.assertEqual(r["texto"], "Virou rotina: terça, 18:00.")
        t = self.conn.execute("SELECT title, recorrencia, hora, due_date FROM tasks WHERE id = ?", (r["id"],)).fetchone()
        self.assertEqual(tuple(t), ("Academia", "semanal:1", "18:00", None))
        self.assertIsNone(rotinas_esperto.responder_rotina(self.conn, c["data"]["chave"], "sim", self.AGORA))
        cli = app.app.test_client()
        cli.post("/login", json={"pin": PIN})
        self.assertEqual(cli.post(f"/api/desfazer/{r['token']}").status_code, 200)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM tasks WHERE id = ?", (r["id"],)).fetchone())

    def test_nao_nunca_mais(self):
        self._semanas(3, 1, "18:00")
        rotinas_esperto.verificar(self.conn, self.AGORA)
        chave = self.chat()[0][1][0]["data"]["chave"]
        r = rotinas_esperto.responder_rotina(self.conn, chave, "nao", self.AGORA)
        self.assertEqual(r["texto"], "Ok, não pergunto mais desse.")
        self.assertEqual(rotinas_esperto.propostas_novas(self.conn, self.AGORA + timedelta(days=7)), [])

    def test_ja_e_rotina_nao_propoe(self):
        self.conn.execute("INSERT INTO tasks (title, recorrencia, hora) VALUES ('Academia', 'semanal:1', '18:00')")
        self.conn.commit()
        self._semanas(3, 1, "18:00")
        self.assertEqual(rotinas_esperto.padroes_lugar(self.conn, self.AGORA), [])

    def test_fora_da_janela(self):
        self._semanas(3, 1, "18:00")
        rotinas_esperto.verificar(self.conn, _em("07:00"))
        self.assertEqual(self.chat(), [])


# ====================================================================== tarefa adiada 3 vezes
class AdiadaTestCase(_Base):
    AGORA = _em("10:00")

    def adiada(self, titulo="Separar os papéis", n=3, **kw):
        t = self.tarefa(titulo, **kw)
        for _ in range(n):
            self.conn.execute("INSERT INTO tarefas_adiadas (task_id, de, para) VALUES (?, ?, ?)",
                              (t, HOJE.isoformat(), AMANHA.isoformat()))
        self.conn.commit()
        return t

    def test_card_uma_vez_e_tira_do_travou(self):
        import foco_ideias

        t = self.adiada()
        self.adiada("Só duas", n=2)
        rotinas_esperto.verificar(self.conn, self.AGORA)
        msgs = self.chat()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0][0], "“Separar os papéis” já foi adiada 3 vezes. O que eu faço com ela?")
        self.assertEqual(msgs[0][1][0]["type"], "tarefa_adiada")
        self.assertEqual(msgs[0][1][0]["data"]["task_id"], t)
        self.assertEqual(foco_ideias.pendentes_travou(self.conn), [])  # a mesma tarefa nao ganha dois cards
        fila = hora_certa.pendentes(self.conn, self.AGORA)
        self.assertEqual(fila[0]["titulo"], "“Separar os papéis” já foi adiada 3 vezes")
        rotinas_esperto.verificar(self.conn, self.AGORA + timedelta(days=1))
        self.assertEqual(len(self.chat()), 1)

    def test_mudar_dia_sem_chuva_e_menos_corrido(self):
        t = self.adiada()
        dias = [HOJE + timedelta(days=i) for i in range(1, 9)]
        prev = [{"data": d.isoformat(), "chuva_pct": 80 if i == 0 else 10} for i, d in enumerate(dias)]
        self.tarefa("Ocupado", dias[1], "10:00")
        r = rotinas_esperto.mudar_dia(self.conn, t, self.AGORA, previsao=prev)
        self.assertEqual(r["data"], dias[2].isoformat())  # 1o chove, 2o tem tarefa
        self.assertIn("que tu tá livre e sem chuva.", r["texto"])
        self.assertIn(f"({dias[2]:%d/%m})", r["texto"])
        cli = app.app.test_client()
        cli.post("/login", json={"pin": PIN})
        self.assertEqual(cli.post(f"/api/desfazer/{r['token']}").status_code, 200)
        self.assertEqual(self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (t,)).fetchone()[0], HOJE.isoformat())

    def test_mudar_dia_sem_previsao_nao_fala_de_chuva_e_pula_voo(self):
        t = self.adiada(hora="09:00")
        self.voo("09:30", HOJE + timedelta(days=1))
        r = rotinas_esperto.mudar_dia(self.conn, t, self.AGORA, previsao=[])
        self.assertEqual(r["data"], (HOJE + timedelta(days=2)).isoformat())
        self.assertEqual(r["hora"], "09:00")
        self.assertNotIn("chuva", r["texto"])

    def test_mudar_dia_hora_ocupada_procura_outra(self):
        t = self.adiada(hora="10:00")
        alvo = HOJE + timedelta(days=1)
        for d in range(2, 8):
            self.tarefa("x", HOJE + timedelta(days=d))
            self.tarefa("y", HOJE + timedelta(days=d))
        self.tarefa("Reunião", alvo, "10:30")
        r = rotinas_esperto.mudar_dia(self.conn, t, self.AGORA, previsao=[])
        self.assertEqual(r["data"], alvo.isoformat())
        self.assertEqual(r["hora"], "08:00")


# ====================================================================== rotas
class RotasTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)

    def test_rotina(self):
        self.assertEqual(self.client.post("/api/esperto/rotina", json={"chave": "x", "resposta": "talvez"}).status_code, 400)
        self.assertEqual(self.client.post("/api/esperto/rotina", json={"chave": "x", "resposta": "sim"}).status_code, 409)
        props = {"lugar:academia:1": {"dados": {"dias": [1], "hora": "18:00", "tarefa_titulo": "Academia", "fonte": "lugar",
                                                "semanas": 3}, "em": "x", "resposta": None}}
        db.definir_configuracao(self.conn, rotinas_esperto.PROPOSTAS, json.dumps(props))
        r = self.client.post("/api/esperto/rotina", json={"chave": "lugar:academia:1", "resposta": "sim"}).get_json()
        self.assertTrue(r["ok"])
        self.assertTrue(r["token"])

    def test_mudar_dia(self):
        t = self.tarefa("Algo")
        with patch("rotinas_esperto._previsao", return_value=None):
            r = self.client.post(f"/api/esperto/tarefa/{t}/mudar-dia").get_json()
        self.assertTrue(r["ok"])
        self.assertEqual(self.client.post("/api/esperto/tarefa/9999/mudar-dia").status_code, 404)

    def test_remarcar(self):
        vid = self.voo()
        r = self.client.post(f"/api/esperto/voo/{vid}/remarcar", json={"hora": "12:00"}).get_json()
        self.assertEqual(r["texto"], "Remarquei pras 12:00.")
        self.assertEqual(self.client.post(f"/api/esperto/voo/{vid}/remarcar", json={"hora": "meio-dia"}).status_code, 400)
        self.assertEqual(self.client.post("/api/esperto/voo/999/remarcar", json={"hora": "12:00"}).status_code, 404)

    def test_visitante_recusa(self):
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = _time.time()
        self.assertEqual(self.client.post("/api/esperto/rotina", json={"chave": "x", "resposta": "sim"}).status_code, 403)
        self.assertEqual(self.client.post("/api/esperto/tarefa/1/mudar-dia").status_code, 403)
        self.assertEqual(self.client.post("/api/esperto/voo/1/remarcar", json={"hora": "12:00"}).status_code, 403)

    def test_sem_login_nao_entra(self):
        c = app.app.test_client()
        self.assertIn(c.post("/api/esperto/voo/1/remarcar", json={"hora": "12:00"}).status_code, (302, 401))


class TiposDeAvisoTestCase(unittest.TestCase):
    def test_liga_desliga_e_emoji(self):
        from assistente import avisos
        import notificacoes

        for t in ("voo_decisao", "casa_tarefa", "treino_pergunta", "rotina_descoberta", "tarefa_adiada"):
            self.assertIn(t, avisos.TIPOS)
            self.assertIn(t, notificacoes.EMOJI_DO_AVISO)


if __name__ == "__main__":
    unittest.main()


# ====================================================================== app do iPhone: Amanha e avisos do "pra onde vou"
class AppIphoneTestCase(_Base):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {"PAINEL_WIDGET_TOKEN": "token-de-teste"})
        env.start()
        self.addCleanup(env.stop)
        p = patch("onde_estou.mensagem_chegada", return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def app_sincronizou(self, agora):
        avisos_app.gravar_agendados(self.conn, [], agora)

    def test_casa_tem_categoria_e_amanha_pelo_app(self):
        t = self.tarefa("Algo")
        self.visita("casa", _em("19:00"))
        itens = avisos_app.montar(self.conn, _em("19:05"), url_do_aviso=app._url_do_aviso,
                                  de_uma_tarefa=frozenset(app._AVISOS_DE_UMA_TAREFA))
        casa = [i for i in itens if i["tipo"] == "casa_tarefa"][0]
        self.assertEqual(casa["categoria"], "casa")
        c = app.app.test_client()
        r = c.post("/api/app/aviso/acao", json={"tag": f"casa_tarefa-{t}", "acao": "amanha"},
                   headers={"Authorization": "Bearer token-de-teste"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["mensagem"], "Passei pra amanhã.")
        self.assertEqual(self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (t,)).fetchone()[0], AMANHA.isoformat())
        # "amanha" so vale pro aviso de casa
        outra = self.tarefa("Outra", hora="10:00")
        r = c.post("/api/app/aviso/acao", json={"tag": f"tarefa_horario-{outra}", "acao": "amanha"},
                   headers={"Authorization": "Bearer token-de-teste"})
        self.assertEqual(r.status_code, 400)

    def test_categoria_dos_outros(self):
        it = avisos_app._item("tarefa_horario", 3, _em("10:00"), "a", "b", app._url_do_aviso,
                              frozenset(app._AVISOS_DE_UMA_TAREFA))
        self.assertEqual(it["categoria"], "tarefa")
        it = avisos_app._item("indo_pra", 3, _em("10:00"), "a", "b", app._url_do_aviso, frozenset())
        self.assertEqual((it["categoria"], it["url"]), ("", "/?aba=assistente"))

    def test_evento_sem_app_vai_na_hora_pelo_push(self):
        agora = _em("19:30")
        with patch("onde_estou._avisar", return_value=True) as av:
            ref = hora_certa.avisar_evento(self.conn, "indo_pra", "Indo pro date?", "Chega 19:55.", agora, ref_legado=7)
        self.assertEqual(av.call_args.args[1:5], ("indo_pra", 7, "🚗 Indo pro date?", "Chega 19:55."))
        self.assertTrue(db.ja_notificou_hoje(self.conn, "indo_pra", ref))
        self.assertEqual(hora_certa.para_push(self.conn, agora + timedelta(minutes=5), {}), [])
        self.assertEqual(hora_certa.para_app(self.conn, agora, {}), [])

    def test_evento_com_app_vai_pelo_aviso_local_e_o_push_espera(self):
        agora = _em("19:30")
        self.app_sincronizou(agora - timedelta(minutes=4))
        with patch("onde_estou._avisar") as av:
            ref = hora_certa.avisar_evento(self.conn, "atraso_recado", "Vai chegar 19:52, o date é 19:40",
                                           "Lento na BR-470. Quer mandar um recado? O texto tá pronto.", agora, ref_legado=7)
        av.assert_not_called()
        itens = avisos_app.montar(self.conn, agora, url_do_aviso=app._url_do_aviso,
                                  de_uma_tarefa=frozenset(app._AVISOS_DE_UMA_TAREFA))
        rec = [i for i in itens if i["tipo"] == "atraso_recado"]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["tag"], f"atraso_recado-{ref}")
        self.assertEqual(rec[0]["url"], "/?aba=assistente")
        self.assertNotIn("wa.me", rec[0]["corpo"])
        # o push espera o app pegar
        self.assertEqual(hora_certa.para_push(self.conn, agora + timedelta(minutes=1), {}), [])
        # o app agendou (ainda vai tocar): o push nao repete
        agendados = {rec[0]["tag"]: [rec[0]["quando_ts"] + 600]}
        self.assertEqual(hora_certa.para_push(self.conn, agora + timedelta(minutes=4), agendados), [])
        # o app sumiu: depois da espera sai pelo navegador
        self.assertEqual([t for t, *_ in hora_certa.para_push(self.conn, agora + timedelta(minutes=4), {})],
                         ["atraso_recado"])
