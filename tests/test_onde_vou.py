"""Leva 06/11 "painel mais esperto" (frentes 4 e 7): pra onde vou, diario do dia por lugar, aprende teus
tempos reais e recado de atraso (onde_vou.py, diario_lugares.py, rotas/onde_vou.py). Banco temporario;
Maps, clima, push e Telegram dublados. Dados inventados."""

import json
import os
import tempfile
import time as _time
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402
import criptografia  # noqa: E402
import diario_lugares  # noqa: E402
import fechamento_dia  # noqa: E402
import notificacoes  # noqa: E402
import onde_estou  # noqa: E402
import onde_vou  # noqa: E402
import tempo  # noqa: E402
import vida_assistente  # noqa: E402

PIN = "246813"
CASA = (-26.9000, -49.0000)
MECANICO = (-26.9100, -49.0600)
PRAIA = (-26.9500, -48.9500)
HOJE = date.today()
VIAGEM = {
    "duracao_minutos": 25, "distancia_km": 12.0, "transito_min": 4,
    "lentidao": [{"nivel": "lento", "de_km": 5.0, "extensao_km": 2.0, "nome": "BR-470, Gaspar", "ponto": [0, 0]}],
    "destino_ll": [PRAIA[0], PRAIA[1]],
}


def _em(hhmm: str, dia: date | None = None) -> datetime:
    return datetime.combine(dia or HOJE, time(*map(int, hhmm.split(":"))))


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        self.conn.commit()
        onde_estou._cache_trajeto.clear()
        app._CACHE_TRAJETO_AVISO.clear()
        tempo.limpar_cache()
        for alvo, valor in ((onde_estou, "REAGIR_EM_THREAD"),):
            p = patch.object(alvo, valor, False)
            p.start()
            self.addCleanup(p.stop)
        env = {"ENDERECO_CASA": f"{CASA[0]},{CASA[1]}", "GOOGLE_MAPS_API_KEY": "chave-falsa"}
        p = patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        self.geocodificar = self._patch("maps_client.geocodificar",
                                        side_effect=lambda e: PRAIA if "Viva" in e else MECANICO)
        self.tempo_de_viagem = self._patch("maps_client.tempo_de_viagem", return_value=dict(VIAGEM))
        self._patch("maps_client.usar_cota", return_value=True)
        self.clima = self._patch("app._clima_aviso", return_value={"chuva_pct": 10})
        self.avisar = self._patch_obj(onde_estou, "_avisar", return_value=True)
        vida_assistente.salvar_apelido(self.conn, "o mecânico", "Rua do Mecânico, 100, Brusque")
        self.conn.commit()

    def _patch(self, alvo, **kw):
        p = patch(alvo, **kw)
        m = p.start()
        self.addCleanup(p.stop)
        return m

    def _patch_obj(self, obj, nome, **kw):
        p = patch.object(obj, nome, **kw)
        m = p.start()
        self.addCleanup(p.stop)
        return m

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora, local=None, estilo=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, estilo) VALUES (?, ?, ?, ?, ?)",
            (titulo, HOJE.isoformat(), hora, local, estilo),
        )
        self.conn.commit()
        return cur.lastrowid

    def visita(self, ponto, chegada, saida=None, **extra):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": 30.0, "chegada": chegada, "saida": saida, **extra}
        return onde_estou.registrar(self.conn, dados, saida or chegada)[0]

    def cards_do_chat(self, tipo=None):
        saida = []
        for r in self.conn.execute("SELECT texto, cards_json FROM chat_mensagens ORDER BY id"):
            lista = json.loads(criptografia.descriptografar(r["cards_json"])) if r["cards_json"] else []
            for c in lista:
                if tipo is None or c["type"] == tipo:
                    saida.append(c)
        return saida

    def avisos(self, tipo):
        return [c for c in self.avisar.call_args_list if c.args[1] == tipo]

    def amostras(self, tipo, valores, faixa=None):
        for i, v in enumerate(valores):
            onde_vou._guardar_amostra(self.conn, tipo, v, HOJE.isoformat(), 1000 + i + (100 if faixa else 0), faixa)


# ====================================================================== 1. pra onde vou
class PraOndeVouTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.date = self.tarefa("Date com a Júlia", "20:00", "Viva Beach", "date")
        self.casa = self.visita(CASA, _em("08:00"))

    def sair(self, hhmm, depois=1):
        vid = self.visita(CASA, _em("08:00"), _em(hhmm))
        self.assertEqual(vid, self.casa)
        return onde_estou.reagir(self.conn, vid, _em(hhmm) + timedelta(minutes=depois))

    def test_saiu_perto_da_hora_pergunta_indo_pro_date_com_trajeto(self):
        feito = self.sair("19:30")
        self.assertIn("indo", feito)
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        self.assertEqual((row["tarefa_id"], row["origem"], row["sair_aviso"], row["previsto_min"]),
                         (self.date, "casa", "19:35", 25))
        self.assertEqual(row["chegada_prevista"], _em("19:55").isoformat(timespec="seconds"))
        self.assertEqual((row["destino_lat"], row["destino_lon"]), PRAIA)
        [card] = self.cards_do_chat("indo_pra")
        d = card["data"]
        self.assertEqual(d["titulo"], "Indo pro date com a Júlia?")
        self.assertEqual((d["chega"], d["hora"], d["estilo"], d["atrasa"]), ("19:55", "20:00", "date", False))
        tipos = [e["tipo"] for e in d["eventos"]]
        self.assertEqual(tipos, ["saiu", "lento", "fim"])
        self.assertEqual(d["eventos"][0]["titulo"], "Saiu de casa")
        self.assertIn("19:35", d["eventos"][0]["sub"])
        self.assertTrue(d["eventos"][1]["titulo"].startswith("Lento na BR-470"))
        self.assertEqual(d["eventos"][1]["sub"], "+4 min, já contado")
        self.assertEqual(d["eventos"][-1]["sub"], "5 min antes")
        [aviso] = self.avisos("indo_pra")
        self.assertEqual(aviso.args[3], "🚗 Indo pro date com a Júlia?")
        self.assertIn("Chega 19:55", aviso.args[4])
        self.assertFalse(self.avisos("atraso_recado"))
        # o Maps foi chamado do ponto da saida, com trechos lentos (conta a cota no maps_client)
        self.assertTrue(any(c.kwargs.get("lentidao") for c in self.tempo_de_viagem.call_args_list))

    def test_chuva_na_chegada_entra_na_linha(self):
        self.clima.return_value = {"chuva_pct": 70}
        self.sair("19:30")
        d = self.cards_do_chat("indo_pra")[0]["data"]
        chuva = next(e for e in d["eventos"] if e["tipo"] == "chuva")
        self.assertIn("70%", chuva["sub"])

    def test_uma_vez_por_visita_e_por_tarefa(self):
        self.sair("19:30")
        onde_estou.reagir(self.conn, self.casa, _em("19:33"))
        self.assertEqual(len(self.cards_do_chat("indo_pra")), 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM indo_pra").fetchone()[0], 1)

    def test_fora_da_janela_nao_adivinha(self):
        self.sair("18:20")  # 75 min antes da hora de sair
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM indo_pra").fetchone()[0], 0)
        self.assertFalse(self.cards_do_chat("indo_pra"))

    def test_tarefa_sem_lugar_nao_entra(self):
        self.conn.execute("UPDATE tasks SET local = NULL WHERE id = ?", (self.date,))
        self.conn.commit()
        self.sair("19:30")
        self.assertFalse(self.cards_do_chat("indo_pra"))

    def test_sem_maps_pergunta_sem_hora_de_chegada(self):
        with patch("maps_client.configurado", return_value=False):
            self.sair("19:30")
        d = self.cards_do_chat("indo_pra")[0]["data"]
        self.assertIsNone(d["chega"])
        self.assertEqual([e["tipo"] for e in d["eventos"]], ["saiu"])

    def test_atrasado_manda_recado_e_nao_o_push_do_indo(self):
        feito = self.sair("19:50")
        self.assertEqual(feito[:2], ["indo", "recado"])
        [card] = self.cards_do_chat("recado_atraso")
        d = card["data"]
        self.assertEqual((d["atraso_min"], d["escolhido"], d["opcoes"], d["chega"]), (15, 15, [10, 15, 20], "20:15"))
        self.assertEqual(d["texto"], "Oi! Peguei trânsito na BR-470, chego uns 15 min atrasado. Já tô a caminho.")
        self.assertTrue(d["whatsapp"].startswith("https://wa.me/?text=Oi%21%20Peguei"))
        self.assertFalse(self.avisos("indo_pra"))
        [aviso] = self.avisos("atraso_recado")
        self.assertTrue(aviso.args[3].startswith("⏰ Vai chegar 20:15"))
        self.assertIn("Lento na BR-470", aviso.args[4])
        self.assertTrue(self.cards_do_chat("indo_pra")[0]["data"]["atrasa"])

    def test_recado_so_de_novo_se_o_atraso_crescer_mais_de_10(self):
        self.sair("19:50")
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        t = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (self.date,)).fetchone()
        agora = _em("19:55")
        self.assertFalse(onde_vou.recado(self.conn, row, t, 22, agora))
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        self.assertTrue(onde_vou.recado(self.conn, row, t, 27, agora))
        self.assertEqual(len(self.cards_do_chat("recado_atraso")), 2)

    def test_outro_lugar_nao_insiste(self):
        self.sair("19:30")
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        self.assertEqual(onde_vou.responder(self.conn, row["id"], "outro"), {"ok": True, "resposta": "outro"})
        self.tempo_de_viagem.return_value = {"duracao_minutos": 50}
        self.assertEqual(onde_vou.atualizar_posicao(self.conn, -26.92, -49.01, _em("19:40")), [])
        self.assertFalse(self.cards_do_chat("recado_atraso"))
        self.assertIsNone(onde_vou.responder(self.conn, row["id"], "talvez"))

    def test_posicao_no_caminho_reconfere_e_avisa_atraso(self):
        self.sair("19:30")
        self.tempo_de_viagem.return_value = {"duracao_minutos": 35}
        self.assertEqual(onde_vou.atualizar_posicao(self.conn, -26.92, -49.01, _em("19:40")), ["recado"])
        d = self.cards_do_chat("recado_atraso")[0]["data"]
        self.assertEqual((d["chega"], d["atraso_min"]), ("20:15", 15))

    def test_saida_pela_cerca_e_pela_visita_conta_uma_vez(self):
        # cerca fecha a casa 19:30; a visita do iOS chega depois com chegada 08:03 e saida 19:33
        feito = onde_estou.reagir(self.conn, self.visita(CASA, None, _em("19:30"), fonte="cerca", cerca="casa"),
                                  _em("19:31"))
        self.assertIn("indo", feito)
        vid = self.visita(CASA, _em("08:03"), _em("19:33"))
        self.assertEqual(vid, self.casa)
        onde_estou.reagir(self.conn, vid, _em("19:34"))
        c = self.visita(CASA, None, _em("19:32"), fonte="cerca")  # a saida da cerca repetida
        self.assertEqual(c, self.casa)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM visitas").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT saida FROM visitas").fetchone()[0],
                         _em("19:30").isoformat(timespec="seconds"))  # fica a mais cedo
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM indo_pra").fetchone()[0], 1)
        self.assertEqual(len(self.avisos(onde_vou.TIPO_INDO)), 1)

    def test_voltou_pro_mesmo_lugar_depois_de_sair_e_outra_visita(self):
        self.visita(CASA, None, _em("10:00"))
        outra = self.visita(CASA, _em("10:20"))
        self.assertNotEqual(outra, self.casa)

    def test_tick_segue_a_posicao_do_caminho(self):
        self.sair("19:30")
        self.tempo_de_viagem.return_value = {"duracao_minutos": 35}
        pos = {"lat": -26.92, "lng": -49.01, "velocidade": 15.0, "em": _em("19:38").isoformat()}
        with patch("viagem_acompanhada.ultima_posicao", return_value=pos):
            self.assertEqual(onde_vou._seguir_no_caminho(self.conn, _em("19:40")), ["recado"])
            self.assertEqual(onde_vou._seguir_no_caminho(self.conn, _em("19:42")), [])  # 10 min entre conferidas
        velha = dict(pos, em=_em("19:20").isoformat())
        with patch("viagem_acompanhada.ultima_posicao", return_value=velha):
            self.assertEqual(onde_vou._seguir_no_caminho(self.conn, _em("19:51")), [])  # posicao velha nao vale
        with patch("viagem_acompanhada.ultima_posicao", return_value=None):
            self.assertEqual(onde_vou._seguir_no_caminho(self.conn, _em("20:01")), [])

    def test_parado_e_atrasando_manda_recado_saindo(self):
        self.conn.execute("DELETE FROM visitas")
        self.conn.commit()
        vid = self.visita(MECANICO, _em("18:00"))
        self.tempo_de_viagem.return_value = {"duracao_minutos": 40}
        feito = onde_estou.reagir(self.conn, vid, _em("19:40"))
        self.assertIn("atraso", feito)
        self.assertIn("recado", feito)
        d = self.cards_do_chat("recado_atraso")[0]["data"]
        self.assertEqual(d["modelo"], "saindo")
        self.assertEqual(d["hora"], "20:00")  # a hora combinada, nao a empurrada
        self.assertIn("Já já tô saindo", d["texto"])

    def test_chegou_no_destino_guarda_as_amostras(self):
        self.sair("19:45")  # aviso era 19:35 -> +10
        vid = self.visita(PRAIA, _em("20:12"))
        feito = onde_estou.reagir(self.conn, vid, _em("20:13"))
        self.assertIn("amostra_saida", feito)
        self.assertIn("amostra_trajeto", feito)
        linhas = {r["tipo"]: (r["valor_min"], r["faixa"]) for r in self.conn.execute("SELECT * FROM tempos_reais")}
        self.assertEqual(linhas, {"saida": (10, None), "trajeto": (2, "tarde")})
        self.assertIsNotNone(self.conn.execute("SELECT chegou_em FROM indo_pra").fetchone()[0])

    def test_e_isso_tambem_conta_a_saida(self):
        self.sair("19:42")
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        onde_vou.responder(self.conn, row["id"], "sim")
        self.assertEqual(self.conn.execute("SELECT valor_min FROM tempos_reais WHERE tipo='saida'").fetchone()[0], 7)

    def test_saiu_de_outro_lugar_nao_vira_amostra_de_saida(self):
        self.conn.execute("DELETE FROM visitas")
        self.conn.commit()
        vid = self.visita(MECANICO, _em("18:00"), _em("19:40"))
        onde_estou.reagir(self.conn, vid, _em("19:41"))
        row = self.conn.execute("SELECT * FROM indo_pra").fetchone()
        self.assertEqual(row["origem"], "mecanico")
        onde_vou.responder(self.conn, row["id"], "sim")
        self.assertIsNone(self.conn.execute("SELECT 1 FROM tempos_reais WHERE tipo='saida'").fetchone())


# ====================================================================== cerca na mesma rota
class CercaTestCase(_Base):
    def test_validar_aceita_fonte_e_lugar(self):
        agora = datetime.now()
        d = onde_estou.validar({"lat": CASA[0], "lon": CASA[1], "saida": agora.isoformat(), "fonte": "cerca",
                                "lugar": "Casa"}, agora)
        self.assertEqual((d["fonte"], d["lugar"]), ("cerca", "casa"))
        d = onde_estou.validar({"lat": CASA[0], "lon": CASA[1], "chegada": agora.isoformat(), "lugar": 5}, agora)
        self.assertEqual((d["fonte"], d["lugar"]), ("visita", None))
        d = onde_estou.validar({"lat": CASA[0], "lon": CASA[1], "chegada": agora.isoformat(), "fonte": "cerca",
                                "cerca": "c0123456789"}, agora)
        self.assertEqual(d["cerca"], "c0123456789")
        for ruim in ("<b>", 7, "x" * 40):
            self.assertIsNone(onde_estou.validar({"lat": CASA[0], "lon": CASA[1], "chegada": agora.isoformat(),
                                                  "cerca": ruim}, agora)["cerca"])

    def test_id_da_cerca_diz_o_lugar(self):
        from viagem_acompanhada import _id_cerca

        self.tarefa("Levar o carro", "10:30", "Mecânico do Zé, Rua X", None)
        longe = (MECANICO[0] + 0.02, MECANICO[1])  # centro arredondado/impreciso: o ponto sozinho nao bate
        ids = {x["apelido"]: _id_cerca(x["apelido"]) for x in onde_estou.lugares_com_coordenada(self.conn, HOJE.isoformat())}
        apelido = next(a for a in ids if a != "casa")
        vid = self.visita(longe, _em("10:05"), fonte="cerca", cerca=ids[apelido])
        self.assertEqual(self.conn.execute("SELECT lugar FROM visitas WHERE id = ?", (vid,)).fetchone()[0], apelido)

    def test_cerca_e_visita_do_mesmo_lugar_viram_uma_so(self):
        a = self.visita(MECANICO, _em("10:05"), fonte="cerca", lugar="mecanico")
        b = self.visita(MECANICO, _em("10:01"))
        self.assertEqual(a, b)
        self.assertEqual(self.conn.execute("SELECT chegada FROM visitas WHERE id = ?", (a,)).fetchone()[0],
                         _em("10:01").isoformat(timespec="seconds"))
        c = self.visita(MECANICO, None, _em("11:00"), fonte="cerca")
        self.assertEqual(c, a)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM visitas").fetchone()[0], 1)


# ====================================================================== 2. tempos reais
class TemposReaisTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.date = self.tarefa("Date com a Júlia", "20:00", "Viva Beach", "date")

    def plano(self, agora="18:00"):
        [p] = notificacoes.plano_se_arrumar(self.conn, _em(agora), 40, trajeto_min=lambda local: 25)
        return p

    def test_sem_amostra_igual_a_hoje(self):
        p = self.plano()
        self.assertEqual((p["saida"], p["meu_tempo_min"]), (_em("19:35"), 0))
        self.amostras("saida", [8, 12])  # 2 ainda nao bastam
        self.assertEqual(self.plano()["saida"], _em("19:35"))

    def test_tres_amostras_adiantam_a_saida_pela_mediana(self):
        self.amostras("saida", [8, 12, 10])
        p = self.plano()
        self.assertEqual((p["saida"], p["meu_tempo_min"]), (_em("19:25"), 10))
        a = onde_vou.ajuste(self.conn, _em("20:00"))
        self.assertEqual(a["frase"], "tu costuma sair 10 min depois do aviso")
        self.assertEqual(a["amostras"], [8, 12, 10])
        [(_, _, _, corpo)] = [x for x in notificacoes.avisos_se_arrumar([p], _em("19:24")) if x[0] == "hora_de_sair"]
        self.assertIn("Avisei 10 min antes: é o teu jeito.", corpo)

    def test_so_as_ultimas_seis_e_nunca_atrasa_o_aviso(self):
        self.amostras("saida", [40, 40, 40, 1, 1, 1, 1, 1, 1])
        self.assertEqual(onde_vou.ajuste(self.conn, _em("20:00"))["saida_min"], 1)
        self.conn.execute("DELETE FROM tempos_reais")
        self.amostras("saida", [-10, -8, -12])  # sai antes do aviso: nao empurra o aviso pra depois
        self.assertEqual(onde_vou.ajuste(self.conn, _em("20:00"))["min"], 0)

    def test_trajeto_por_faixa_do_dia(self):
        self.amostras("trajeto", [6, 7, 5], faixa="tarde")
        self.assertEqual(onde_vou.ajuste(self.conn, _em("19:00"))["trajeto_min"], 6)
        self.assertEqual(onde_vou.ajuste(self.conn, _em("09:00"))["trajeto_min"], 0)
        self.assertEqual(onde_vou.ajuste(self.conn, _em("19:00"), so_saida=True)["min"], 0)

    def test_padrao_desliga_o_meu_tempo(self):
        self.amostras("saida", [10, 10, 10])
        onde_vou.definir_preferencia(self.conn, "padrao")
        self.assertEqual(self.plano()["saida"], _em("19:35"))
        a = onde_vou.ajuste(self.conn, _em("20:00"))
        self.assertEqual((a["min"], a["aprendido"], a["usar"]), (0, 10, "padrao"))

    def test_fita_usa_a_mesma_conta(self):
        self.amostras("saida", [10, 10, 10])
        i = next(x for x in tempo.compromissos(self.conn, _em("18:00"), rede=False) if x["ref"] == self.date)
        self.assertEqual(i["sair"], _em("19:35"))  # sem rede: folga de 15 + 10 dele
        self.assertEqual(i["adiantado_min"], 0)  # o jeito dele nao vai pro extras.adiantar_min

    def test_card_meu_tempo_na_hora_de_se_arrumar_uma_vez(self):
        self.amostras("saida", [8, 12, 10])
        onde_vou.verificar(self.conn, _em("18:00"))
        self.assertFalse(self.cards_do_chat("meu_tempo"))
        onde_vou.verificar(self.conn, _em("18:46"))
        onde_vou.verificar(self.conn, _em("18:51"))
        [card] = self.cards_do_chat("meu_tempo")
        d = card["data"]
        self.assertEqual((d["sair_meu"], d["sair_padrao"], d["ajuste_min"], d["usar"]), ("19:25", "19:35", 10, "meu"))
        self.assertEqual(d["amostras"], [8, 12, 10])
        self.assertGreater(d["sair_padrao_s"], d["sair_meu_s"])


# ====================================================================== 3. diario do dia
class DiarioLugaresTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.tarefa("Levar o carro no mecânico", "08:30")
        ontem = HOJE - timedelta(days=1)
        self.visita(CASA, _em("22:00", ontem), _em("08:10"))
        self.visita(MECANICO, _em("08:30"), _em("09:40"))
        self.visita((-26.9130, -49.0600), _em("10:00"), _em("10:20"))  # ~330 m do mecanico, sem apelido
        self.visita((-26.8000, -48.8000), _em("10:30"), _em("10:33"))  # parada de 3 min: some
        self.visita(CASA, _em("11:00"))
        self.agora = _em("12:00")

    def test_estadias_com_nome_tempo_e_sem_caminho(self):
        d = diario_lugares.dados(self.conn, HOJE, self.agora)
        nomes = [(l["lugar"], l["hora"], l["min"]) for l in d["lugares"]]
        self.assertEqual(nomes, [("Casa", "00:00", 490), ("Mecânico", "08:30", 70),
                                 ("Perto do mecânico", "10:00", 20), ("Casa", "11:00", 60)])
        self.assertEqual(d["lugares"][0]["sub"], "desde ontem, saiu 08:10")
        self.assertEqual(d["lugares"][-1]["sub"], "até agora")
        self.assertEqual(d["n_lugares"], 3)
        self.assertEqual(d["fora_min"], 720 - 490 - 60)
        self.assertEqual(d["titulo"], "Teu dia, por onde passou")
        self.assertTrue(any(b.get("vazio") for b in d["barra"]))
        self.assertNotIn("lat", json.dumps(d))
        self.assertIn("nunca o caminho", d["nota"])

    def test_tarefa_feita_durante_a_estadia_vira_a_linha(self):
        utc = (_em("09:00") + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute("UPDATE tasks SET completed_at = ? WHERE title LIKE 'Levar%'", (utc,))
        self.conn.commit()
        d = diario_lugares.dados(self.conn, HOJE, self.agora)
        self.assertEqual(d["lugares"][1]["sub"], "feito: levar o carro no mecânico")

    def test_lugar_sem_nome_longe_de_tudo(self):
        self.visita((-27.5000, -48.5000), _em("11:10"), _em("11:40"))
        nomes = [l["lugar"] for l in diario_lugares.dados(self.conn, HOJE, _em("12:00"))["lugares"]]
        self.assertIn("Lugar sem nome", nomes)
        self.geocodificar.reset_mock()
        diario_lugares.dados(self.conn, HOJE, _em("12:00"))
        self.geocodificar.assert_not_called()  # nunca chama API por nome de lugar

    def test_ontem_e_dia_sem_visita(self):
        self.assertIsNone(diario_lugares.dados(self.conn, HOJE - timedelta(days=5), self.agora))
        d = diario_lugares.dados(self.conn, HOJE - timedelta(days=1), self.agora)
        self.assertEqual(d["titulo"], "Ontem, por onde passou")
        self.assertEqual([(l["lugar"], l["hora"], l["min"]) for l in d["lugares"]], [("Casa", "22:00", 120)])

    def test_consultar_diario_ganha_os_lugares_e_o_card(self):
        r = diario_lugares.no_consultar(self.conn, HOJE, {"dia": "hoje"}, self.agora)
        self.assertEqual(r["lugares_do_dia"][1], "Mecânico 08:30-09:40 (1 h 10)")
        self.assertEqual(r["_efeito"], {"entidade": "diario_lugares", "dia": HOJE.isoformat(), "consulta": True})
        self.assertEqual(diario_lugares.no_consultar(self.conn, HOJE, {"erro": "x"}), {"erro": "x"})
        card = cards._card_de_efeito_modulo(self.conn, r["_efeito"], None)
        self.assertEqual(card["type"], "diario_lugares")

    def test_pouso_do_dia_leva_o_card(self):
        self.conn.execute("INSERT INTO tasks (title, due_date) VALUES ('Ligar pro contador', ?)", (HOJE.isoformat(),))
        self.conn.commit()
        texto, lista = fechamento_dia.pouso_do_dia(self.conn, HOJE, "21:00")
        self.assertEqual([c["type"] for c in lista], ["placar_feito", "pouso_dia", "diario_lugares"])

    def test_visitante_nao_ve_os_lugares(self):
        card = diario_lugares.card(self.conn, HOJE, self.agora)
        [m] = cards.mascarar_cards([card])
        self.assertTrue(m["data"]["oculto"])
        self.assertNotIn("lugares", m["data"])
        self.assertEqual(diario_lugares.duracao(218), "3 h 38")
        self.assertEqual(diario_lugares.duracao(60), "1 h")


# ====================================================================== rotas
class RotasTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        self.date = self.tarefa("Date", "20:00", "Viva Beach", "date")
        cur = self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, hora_evento, origem, sair_aviso, saiu_em) "
                                "VALUES (?, ?, '20:00', 'casa', '19:35', ?)",
                                (HOJE.isoformat(), self.date, _em("19:40").isoformat(timespec="seconds")))
        self.conn.commit()
        self.id = cur.lastrowid

    def test_resposta(self):
        r = self.client.post(f"/api/onde-vou/{self.id}/resposta", json={"resposta": "sim"})
        self.assertEqual(r.get_json(), {"ok": True, "resposta": "sim"})
        self.assertEqual(self.client.post(f"/api/onde-vou/{self.id}/resposta", json={"resposta": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/onde-vou/9999/resposta", json={"resposta": "sim"}).status_code, 404)

    def test_usar_meu_ou_padrao(self):
        r = self.client.post("/api/tempos-reais/usar", json={"usar": "padrao"})
        self.assertEqual(r.get_json(), {"ok": True, "usar": "padrao"})
        self.assertEqual(onde_vou.preferencia(self.conn), "padrao")
        self.assertEqual(self.client.post("/api/tempos-reais/usar", json={"usar": "x"}).status_code, 400)
        self.assertEqual(self.client.get("/api/tempos-reais").get_json()["usar"], "padrao")

    def test_visitante_recusa(self):
        with self.client.session_transaction() as s:
            s["modo_visitante"] = True
            s["modo_visitante_desde"] = _time.time()
        self.assertEqual(self.client.post(f"/api/onde-vou/{self.id}/resposta", json={"resposta": "sim"}).status_code, 403)
        self.assertEqual(self.client.post("/api/tempos-reais/usar", json={"usar": "meu"}).status_code, 403)

    def test_sem_login_nao_entra(self):
        c = app.app.test_client()
        self.assertIn(c.post("/api/tempos-reais/usar", json={"usar": "meu"}).status_code, (302, 401))


class TextoTestCase(unittest.TestCase):
    def test_recado_e_chips(self):
        self.assertEqual(onde_vou.texto_recado("transito", 15, "BR-470"),
                         "Oi! Peguei trânsito na BR-470, chego uns 15 min atrasado. Já tô a caminho.")
        self.assertEqual(onde_vou.texto_recado("transito", 10), "Oi! Peguei trânsito, chego uns 10 min atrasado. Já tô a caminho.")
        self.assertEqual(onde_vou.texto_recado("caminho", 20), "Oi! Vou chegar uns 20 min atrasado. Já tô a caminho.")
        self.assertEqual((onde_vou.arredonda_atraso(4), onde_vou.arredonda_atraso(12), onde_vou.arredonda_atraso(15)), (5, 15, 15))
        self.assertEqual((onde_vou.opcoes_atraso(5), onde_vou.opcoes_atraso(15), onde_vou.opcoes_atraso(35)),
                         ([5, 10, 15], [10, 15, 20], [30, 35, 40]))
        self.assertEqual(onde_vou.link_whatsapp("Oi! a&b"), "https://wa.me/?text=Oi%21%20a%26b")

    def test_tipos_registrados(self):
        from assistente import avisos

        for tipo in ("indo_pra", "atraso_recado"):
            self.assertIn(tipo, avisos.TIPOS)
            self.assertIn(tipo, notificacoes.EMOJI_DO_AVISO)
        for t in ("indo_pra", "diario_lugares", "meu_tempo", "recado_atraso"):
            self.assertIn(t, cards.TIPOS_CARD)


if __name__ == "__main__":
    unittest.main()
