"""Leva 08/11, frente A, terceira rodada (achados dos revisores): saida que fecha sem ele ter ido, aviso de chegada
do banco/consulta, "casa da X" sem apelido com chegada absurda, "passou da hora" junto da "Ultima chamada", manha
perdida no silencio, texto de repeticao contra o GPS, com_pessoa com sigla/maiuscula, "tem alguem te esperando"
sem ninguem, "casa" no titulo, "saindo no horario" depois da hora, Maps a cada tick, "dia(s)", lembrete com hora e
loja "Casa do X".

Banco temporario; Maps/push dublados (nada sai pra rede). Nomes e lugares inventados."""
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import aviso_cara  # noqa: E402
import avisos_texto  # noqa: E402
import conversa_proativa as cp  # noqa: E402
import maps_client  # noqa: E402
import notificacoes  # noqa: E402
import onde_estou  # noqa: E402
import onde_vou  # noqa: E402
import vida_assistente  # noqa: E402

HOJE = date.today()
CASA = (-26.9000, -49.0000)
OFICINA = (-26.9100, -49.0600)
LONGE = (-26.9500, -49.1000)


def _em(hhmm: str, dia: date = HOJE) -> datetime:
    return datetime.combine(dia, time(*map(int, hhmm.split(":"))))


def _utc(local: datetime) -> str:
    return local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)

    def tarefa(self, titulo, hora, local=None, estilo=None, sai_na_hora=None, dia=HOJE):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, estilo, sai_na_hora) VALUES (?, ?, ?, ?, ?, ?)",
            (titulo, dia.isoformat(), hora, local, estilo, sai_na_hora))
        self.conn.commit()
        return cur.lastrowid

    def avisou(self, tipo, ref, quando: datetime):
        self.conn.execute("INSERT INTO notificacoes_enviadas (tipo, referencia_id, data, criado_em) VALUES (?, ?, ?, ?)",
                          (tipo, ref, quando.date().isoformat(), _utc(quando)))
        self.conn.commit()

    def linha(self, tid):
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()

    def ultimo_chat(self):
        r = self.conn.execute("SELECT texto FROM chat_mensagens ORDER BY id DESC LIMIT 1").fetchone()
        return r["texto"] if r else None


class _BaseGps(_Base):
    def setUp(self):
        super().setUp()
        onde_estou._cache_trajeto.clear()
        maps_client._cache_coords.clear()
        env = {"ENDERECO_CASA": f"{CASA[0]},{CASA[1]}", "GOOGLE_MAPS_API_KEY": "chave-falsa"}
        self.tv = MagicMock(return_value={"duracao_minutos": 25})
        self.avisar = MagicMock(return_value=True)
        for p in (patch.object(onde_estou, "REAGIR_EM_THREAD", False), patch.dict(os.environ, env),
                  patch("maps_client.localizar", MagicMock(side_effect=lambda e: OFICINA if "Oficina" in e else LONGE)),
                  patch("maps_client.tempo_de_viagem", self.tv),
                  patch("maps_client.usar_cota", return_value=True),
                  patch.object(onde_estou, "_avisar", self.avisar),
                  patch("onde_vou.recado_parado", return_value=False),
                  patch("hora_certa.avisar_evento", return_value=1)):
            p.start()
            self.addCleanup(p.stop)
        vida_assistente.salvar_apelido(self.conn, "a oficina", "Rua da Oficina, 100, Brusque")
        vida_assistente.salvar_apelido(self.conn, "escola", "Rua da Escola, 10, Brusque")
        self.conn.commit()

    def visita_crua(self, lugar, chegada, saida=None, ponto=LONGE):
        self.conn.execute("INSERT INTO visitas (lat, lon, chegada, saida, lugar) VALUES (?, ?, ?, ?, ?)",
                          (ponto[0], ponto[1], chegada.isoformat(), saida.isoformat() if saida else None, lugar))
        self.conn.commit()

    def visita(self, ponto, chegada, saida=None):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": 30.0, "chegada": chegada, "saida": saida}
        return onde_estou.registrar(self.conn, dados, saida or chegada)[0]


# ------------------------------------------------------------------ 1. fechar so com o GPS cobrindo a hora

class FecharSoNaHoraTestCase(_BaseGps):
    def setUp(self):
        super().setUp()
        self.tid = self.tarefa("Buscar a Ana na escola", "17:30", local="escola")

    def test_passou_na_escola_de_tarde_e_ta_em_casa_nao_fecha(self):
        self.visita_crua("escola", _em("15:40"), _em("15:50"))
        self.visita_crua("casa", _em("16:00"), ponto=CASA)
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:31")), [])
        self.assertIsNone(self.linha(self.tid)["completed_at"])

    def test_chegou_na_escola_registrado_cedo_nao_fecha(self):
        self.avisou(onde_estou.TIPO_CHEGOU_DESTINO, self.tid, _em("15:42"))
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:31")), [])
        self.conn.execute("DELETE FROM notificacoes_enviadas WHERE tipo = ?", (onde_estou.TIPO_CHEGOU_DESTINO,))
        self.avisou(onde_estou.TIPO_CHEGOU_DESTINO, self.tid, _em("17:20"))
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:31")), [self.tid])

    def test_indo_pra_so_com_destino_confirmado_e_perto_da_hora(self):
        self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, destino, hora_evento, saiu_em, chegou_em) "
                          "VALUES (?, ?, 'escola', '17:30', ?, ?)",
                          (HOJE.isoformat(), self.tid, _em("17:05").isoformat(), _em("17:20").isoformat()))
        self.conn.commit()
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:31")), [])  # sem "E isso"
        self.conn.execute("UPDATE indo_pra SET resposta = 'sim'")
        self.conn.commit()
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:32")), [self.tid])

    def test_visita_que_cobre_a_hora_fecha(self):
        self.visita_crua("escola", _em("17:25"))  # ainda la
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("17:31")), [self.tid])

    def test_sinal_fora_da_hora_pergunta_uma_vez_sem_fechar(self):
        self.visita_crua("escola", _em("15:40"), _em("15:50"))
        onde_estou.fechar_saidas_que_rolaram(self.conn, _em("18:00"))
        self.avisar.assert_not_called()  # ainda cedo pra perguntar
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("18:31")), [])
        self.assertIn("Rolou?", self.ultimo_chat())
        self.assertEqual([c.args[1] for c in self.avisar.call_args_list], [onde_estou.TIPO_SAIDA_ROLOU])
        onde_estou.fechar_saidas_que_rolaram(self.conn, _em("19:00"))
        self.assertEqual(self.avisar.call_count, 1)
        self.assertIsNone(self.linha(self.tid)["completed_at"])


# ------------------------------------------------------------------ 2. aviso de chegada sem pessoa

class ChegadaSemPessoaTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.avisar_evento = MagicMock(return_value=1)
        for p in (patch("hora_certa.avisar_evento", self.avisar_evento),
                  patch.object(onde_estou, "_avisar", return_value=True),
                  patch.object(onde_estou, "_trajeto_min", return_value=40)):
            p.start()
            self.addCleanup(p.stop)

    def _indo(self, tid, destino):
        self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, destino, hora_evento, saiu_em) VALUES (?, ?, ?, '14:00', ?)",
                          (HOJE.isoformat(), tid, destino, _em("13:40").isoformat()))
        self.conn.commit()

    def test_consulta_atrasada_ganha_aviso_de_chegada_sem_recado(self):
        tid = self.tarefa("Consulta", "14:00", local="Clínica Norte")
        self._indo(tid, "Clínica Norte")
        self.assertEqual(onde_vou.atualizar_posicao(self.conn, -26.9, -49.0, _em("13:50")), ["chegada"])
        tipo, titulo, corpo = self.avisar_evento.call_args.args[1:4]
        self.assertEqual(tipo, onde_vou.TIPO_RECADO)
        self.assertEqual(titulo, "Vai chegar 14:30, consulta é 14:00")  # o mesmo titulo do recado de antes
        self.assertNotIn("recado", corpo.lower())
        self.assertIn("Vai chegar 14:30", self.ultimo_chat())
        cards_msg = db.cards_de_mensagem_chat(db.list_chat_mensagens(self.conn)[-1])
        self.assertFalse([c for c in cards_msg if c["type"] == "recado_atraso"])
        # mesma conta no proximo tick: nao repete
        self.assertEqual(onde_vou.atualizar_posicao(self.conn, -26.9, -49.0, _em("13:51")), [])

    def test_com_pessoa_segue_com_recado(self):
        tid = self.tarefa("Buscar a Bruna", "14:00", local="Rua do Parque, 5")
        self._indo(tid, "Rua do Parque, 5")
        self.assertEqual(onde_vou.atualizar_posicao(self.conn, -26.9, -49.0, _em("13:50")), ["recado"])


# ------------------------------------------------------------------ 3. "casa da X" sem apelido

class CasaDeSemApelidoTestCase(_BaseGps):
    def test_destino_e_nenhum(self):
        t = {"title": "Buscar a Bia", "local": "casa da Bia"}
        self.assertEqual(onde_estou._destino(t, onde_estou._lugares(self.conn), self.conn), (None, None))
        self.assertEqual(onde_vou._destino_da_tarefa(self.conn, t, []), (None, None))
        vida_assistente.salvar_apelido(self.conn, "casa da bia", "Rua da Bia, 7")  # com apelido: vai
        self.conn.commit()
        self.assertEqual(onde_vou._destino_da_tarefa(self.conn, t, [])[1], "Rua da Bia, 7")

    def test_nao_diz_chegada_absurda(self):
        self.tv.side_effect = lambda o, dst, **k: {"duracao_minutos": 2158 if "casa d" in dst.lower() else 12}
        tid = self.tarefa("Buscar a Bia", "20:00", local="casa da Bia")
        self.visita(OFICINA, _em("19:00"))
        onde_estou.verificar(self.conn, _em("19:50"))
        self.assertEqual(self.linha(tid)["hora"], "20:00")
        for m in db.list_chat_mensagens(self.conn):
            self.assertNotIn("7h48", m["texto"])
            self.assertNotIn("tu chega às", m["texto"])

    def test_atraso_com_trajeto_acima_do_teto_nao_diz_chegada(self):
        tid = self.tarefa("Buscar a Bia", "20:00", local="Rua Longe, 1")
        alvo = self.linha(tid)
        r = onde_estou._atraso_sem_empurrar(self.conn, _em("19:50"), alvo, 2000, None, [alvo], 2158)
        self.assertNotIn("chega às", r["corpo"])
        self.assertIn("Não mexi no horário", r["corpo"])
        r = onde_estou._atraso_sem_empurrar(self.conn, _em("19:50"), alvo, 15, None, [alvo], 25)
        self.assertIn("chega às 20h15", r["corpo"])


# ------------------------------------------------------------------ 4 e 11. "passou da hora"

class PassouDaHoraTestCase(_Base):
    def test_sai_5_min_depois_da_ultima_chamada(self):
        # o aviso da hora saiu na hora (20:00): a "Ultima chamada" da insistencia cai as 20:30
        tid = self.tarefa("Pagar o boleto", "20:00")
        self.avisou("tarefa_horario", tid, _em("20:00"))
        ultima = 20 * 60 + max(notificacoes.INSISTENCIA["tarefa_horario"])
        no_tick_da_ultima = _em(f"{ultima // 60:02d}:{ultima % 60:02d}")
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, no_tick_da_ultima), [])
        avisos = notificacoes.tarefas_horario_passou(self.conn, no_tick_da_ultima + timedelta(minutes=5))
        self.assertEqual([a[0] for a in avisos], [tid])

    def test_ja_avisado_nao_gasta_maps(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self.avisou("tarefa_horario", tid, _em("20:00"))
        caminho = MagicMock(return_value=12)
        notificacoes.tarefas_horario_passou(self.conn, _em("20:40"), caminho_min=caminho)
        self.assertEqual(caminho.call_count, 1)
        self.avisou("tarefa_horario_passou", tid, _em("20:40"))
        for hhmm in ("20:45", "21:30", "23:55"):
            notificacoes.tarefas_horario_passou(self.conn, _em(hhmm), caminho_min=caminho)
        self.assertEqual(caminho.call_count, 1)


# ------------------------------------------------------------------ 5. manha no silencio

class ManhaNoSilencioTestCase(_Base):
    def visto(self, local: datetime):
        db.definir_configuracao(self.conn, "ultimo_visto_em", local.astimezone(timezone.utc).replace(tzinfo=None)
                                .isoformat(timespec="seconds"))
        self.conn.commit()

    def test_checkin_acordou_no_silencio_sai_no_fim_dele(self):
        self.visto(_em("06:10"))
        self.assertEqual(cp.perguntar_como_esta(self.conn, _em("06:15")), [])
        self.assertFalse(db.ja_notificou_hoje(self.conn, "como_esta_chat"))
        self.assertIsNone(self.ultimo_chat())
        self.assertEqual([s[0] for s in cp.perguntar_como_esta(self.conn, _em("07:00"))], ["como_esta"])
        self.assertTrue(db.ja_notificou_hoje(self.conn, "como_esta_chat"))

    def test_repeticao_da_manha_espera_o_fim_do_silencio(self):
        rem = self.tarefa("Tomar remédio", "06:00")
        self.avisou("tarefa_horario", rem, _em("05:50"))
        self.visto(_em("06:10"))
        with patch("hora_certa.avisar_evento", return_value=1) as avisar:
            cp.repetir_manha_ao_acordar(self.conn, _em("06:15"))
            avisar.assert_not_called()
            self.assertFalse(db.ja_notificou_hoje(self.conn, cp.TIPO_MANHA_AO_ACORDAR))
            cp.repetir_manha_ao_acordar(self.conn, _em("07:00"))
        self.assertEqual(avisar.call_count, 1)
        self.assertIn("Toma agora?", avisar.call_args.args[3])

    def test_silencio_desligado_segue_na_hora(self):
        db.definir_configuracao(self.conn, "silencio_inicio", "00:00")
        db.definir_configuracao(self.conn, "silencio_fim", "00:00")
        self.visto(_em("06:10"))
        self.assertEqual([s[0] for s in cp.perguntar_como_esta(self.conn, _em("06:15"))], ["como_esta"])


# ------------------------------------------------------------------ 6, 8 e 10. cara da repeticao de saida

class RepeticaoDeSaidaTestCase(_Base):
    def _indo(self, tid, chegou=False):
        self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, destino, hora_evento, saiu_em, chegada_prevista, "
                          "chegou_em) VALUES (?, ?, 'Restaurante Lua', '20:00', ?, ?, ?)",
                          (HOJE.isoformat(), tid, _em("20:05").isoformat(), _em("20:20").isoformat(),
                           _em("20:20").isoformat() if chegou else None))
        self.conn.commit()

    def _variar(self, tid, rosto, tipo="tarefa_horario", agora="20:10", titulo="De novo · Date", corpo="corpo velho"):
        with patch.object(aviso_cara, "escolher_rosto", return_value=rosto):
            return aviso_cara.variar(self.conn, tipo, tid, f"{tipo}-{tid}", titulo, corpo, 1, _em(agora))

    def test_indo_so_o_texto_base_e_titulo_do_compromisso(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self._indo(tid)
        for rosto in aviso_cara.ROSTOS:
            titulo, corpo = self._variar(tid, rosto)
            self.assertEqual(titulo, "Date")
            for proibido in ("Antes de sair", "Chave, carteira", "te espera", "Saindo no horário"):
                self.assertNotIn(proibido, corpo, (rosto, corpo))

    def test_chegou_titulo_nao_diz_hora_de_sair(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self._indo(tid, chegou=True)
        titulo, corpo = self._variar(tid, "humor", tipo="tarefa_horario_passou", agora="20:35",
                                     titulo="De novo · " + notificacoes.TITULO_SAIDA_PASSOU)
        self.assertEqual(titulo, "Date")
        self.assertNotIn("te espera", corpo)
        self.assertEqual(notificacoes.titulo_saida_passou(self.conn, self.linha(tid), _em("20:35")), "Date")

    def test_titulo_do_passou_sem_gps_e_o_de_sempre(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self.assertEqual(notificacoes.titulo_saida_passou(self.conn, self.linha(tid), _em("20:35")),
                         notificacoes.TITULO_SAIDA_PASSOU)

    def test_hora_de_sair_repetida_nao_diz_saindo_no_horario(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        _, corpo = self._variar(tid, "porque", tipo="hora_de_sair", agora="19:45", titulo="De novo · Hora de sair",
                                corpo="Hora de sair pro Date.")
        self.assertNotIn("Saindo no horário", corpo)
        self.assertIn("Saindo já, ainda chega bem.", corpo)

    def test_te_espera_so_com_gente_esperando(self):
        banco = {"title": "Ir no banco", "local": "Banco do Centro", "estilo": None, "extras": None, "parada": None,
                 "sai_na_hora": 1, "hora": "14:00", "id": 1}
        date_ = {**banco, "title": "Jantar com a Bruna", "estilo": "date", "sai_na_hora": 0}
        for semente in range(9):
            fatos = {"nome": banco["title"], "atraso_min": -10, "passo": None, "linha": banco}
            self.assertNotIn("te espera", aviso_cara._corpo_da_saida("humor", "x", fatos, semente, "tarefa_horario"))
        frases = {aviso_cara._corpo_da_saida("humor", "x", {"nome": "Jantar", "atraso_min": -10, "passo": None,
                                                            "linha": date_}, s, "tarefa_horario") for s in range(9)}
        self.assertTrue(any("te espera" in f for f in frases))

    def test_tem_alguem_te_esperando_so_com_pessoa(self):
        self.assertFalse(avisos_texto._cond_ok("pessoa", {}))
        self.assertTrue(avisos_texto._cond_ok("pessoa", {"pessoa": True}))
        banco = self.tarefa("Ir no banco", "14:00", local="Banco do Centro", sai_na_hora=1)
        r = self.linha(banco)
        textos = {notificacoes.texto_agora_da_tarefa(r, conn=self.conn, chave=f"k{i}", agora=_em("14:00"))
                  for i in range(25)}
        self.assertTrue(all("esperando" not in t for t in textos), textos)


# ------------------------------------------------------------------ 7. com_pessoa

class ComPessoaTestCase(unittest.TestCase):
    def _r(self, titulo, local=None):
        return {"title": titulo, "local": local, "estilo": None, "extras": None, "parada": None, "sai_na_hora": 0}

    def test_sigla_coisa_e_profissional_nao_sao_pessoa(self):
        for titulo, local in (("Buscar CNH no Detran", "Detran"), ("Pegar Passaporte na PF", "Polícia Federal"),
                              ("Pegar CRLV", None), ("Levar o Onix na revisão", "Concessionária"),
                              ("Buscar Remédio", None), ("Voo com o Instrutor Carlos", "Aeroclube"),
                              ("Buscar PS5 com o vendedor", None), ("Buscar Notebook na assistência", None),
                              ("Treino com Personal", "Academia"), ("Buscar Ifood", None)):
            with self.subTest(titulo=titulo):
                self.assertFalse(notificacoes.com_pessoa(self._r(titulo, local)))
                self.assertFalse(notificacoes.e_saida(self._r(titulo, local)))

    def test_gente_continua_pessoa(self):
        for titulo, local in (("Buscar a Ana na escola", "escola"), ("Encontrar Marina", "Shopping"),
                              ("Reunião com Pedro", "Construtora"), ("Almoço com a mãe", "casa da mãe"),
                              ("Buscar Ana", None)):
            with self.subTest(titulo=titulo):
                self.assertTrue(notificacoes.com_pessoa(self._r(titulo, local)))


# ------------------------------------------------------------------ 9. "casa" no titulo

class CasaNoTituloTestCase(_BaseGps):
    def test_levar_pra_casa_ainda_avisa_o_atraso(self):
        tid = self.tarefa("Buscar a Bruna na Vila Exemplo e levar pra casa", "20:00", local="Vila Exemplo Centro")
        self.visita(CASA, _em("19:00"))
        onde_estou.verificar(self.conn, _em("19:50"))
        self.assertEqual(self.linha(tid)["hora"], "20:00")
        self.assertTrue(db.ja_notificou_hoje(self.conn, onde_estou.TIPO_ATRASO, tid))
        self.assertIn("Não mexi no horário", self.ultimo_chat())

    def test_com_o_local_no_lugar_continua_ja_esta_la(self):
        tid = self.tarefa("Buscar a Bruna na oficina", "20:00", local="a oficina")
        self.visita(OFICINA, _em("19:00"))
        onde_estou.verificar(self.conn, _em("19:50"))
        self.assertFalse(db.ja_notificou_hoje(self.conn, onde_estou.TIPO_ATRASO, tid))


# ------------------------------------------------------------------ 12. "dia(s)"

class TextosSemParentesesTestCase(_Base):
    def _garantia(self, dias_ate):
        hoje = date(2026, 11, 10)
        compra = date(2025, 11, 10) + timedelta(days=dias_ate)  # 12 meses de garantia
        self.conn.execute("INSERT INTO garantias (produto, data_compra, prazo_garantia_meses) VALUES (?, ?, 12)",
                          ("Furadeira", compra.isoformat()))
        self.conn.commit()
        texto = notificacoes.garantias_vencendo(self.conn, hoje=hoje)[0][1]
        self.conn.execute("DELETE FROM garantias")
        self.conn.commit()
        return texto

    def test_garantia_singular_plural_ha_amanha(self):
        self.assertIn("venceu há 1 dia (", self._garantia(-1))
        self.assertIn("venceu há 3 dias", self._garantia(-3))
        self.assertIn("vence hoje", self._garantia(0))
        self.assertIn("vence amanhã", self._garantia(1))
        self.assertIn("vence em 5 dias", self._garantia(5))
        for d in (-3, -1, 0, 1, 5):
            self.assertNotIn("(s)", self._garantia(d))

    def test_semana_pesada_sem_parenteses(self):
        with patch.object(notificacoes.aprendizado, "contagem_itens_semana", return_value=9), \
                patch.object(notificacoes.aprendizado, "carga_semanal_historica", return_value=[4, 4, 4]), \
                patch.object(notificacoes.aprendizado, "semana_pesada",
                             return_value={"sobrecarregada": True, "mediana_historica": 4, "amostras": 3}):
            texto = notificacoes.semana_pesada_aviso(self.conn, hoje=date(2026, 11, 8))
        self.assertNotIn("(s)", texto)
        self.assertIn("9 compromissos e tarefas marcados", texto)


# ------------------------------------------------------------------ 13. lembrete gravado com hora

class LembreteComHoraTestCase(_Base):
    def test_lembrete_com_hora_nao_some_do_tick(self):
        daqui_2 = date.today() + timedelta(days=2)
        self.conn.execute("INSERT INTO lembretes (titulo, data) VALUES (?, ?)",
                          ("Renovar seguro", f"{daqui_2.isoformat()}T09:00"))
        self.conn.commit()
        avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn(daqui_2.strftime("%d/%m"), avisos[0][1])

    def test_desperta_com_hora_tambem(self):
        cur = self.conn.execute("INSERT INTO lembretes (titulo, data) VALUES (?, ?)",
                                ("Levar o lixo", f"{HOJE.isoformat()}T09:00"))
        self.conn.execute("UPDATE lembretes SET despertar = 1 WHERE id = ?", (cur.lastrowid,))
        self.conn.commit()
        self.assertEqual(len(notificacoes.lembretes_para_despertar(self.conn, _em("10:00"))), 1)

    def test_documento_vencendo_com_hora(self):
        vence = HOJE + timedelta(days=30)
        self.conn.execute("INSERT INTO lembretes (titulo, data) VALUES (?, ?)",
                          ("Renovar CNH", f"{vence.isoformat()}T09:00"))
        self.conn.commit()
        saida = cp.documentos_vencendo(self.conn, _em("10:00"))
        self.assertEqual([s[0] for s in saida], ["documento_validade"])


# ------------------------------------------------------------------ 14. loja "Casa do X"

class LojaCasaDoTestCase(_Base):
    def test_loja_nao_e_casa_de_pessoa(self):
        for loja in ("Casa do Construtor", "Casa da Picanha", "casa do construtor"):
            with self.subTest(loja=loja):
                self.assertFalse(vida_assistente.casa_de_alguem_sem_apelido(self.conn, loja))
                self.assertEqual(vida_assistente.resolver_parada(self.conn, loja), loja)
        for gente in ("casa da Bia", "casa da bia", "casa da mãe", "casa dos meus pais"):
            with self.subTest(gente=gente):
                self.assertTrue(vida_assistente.casa_de_alguem_sem_apelido(self.conn, gente))


if __name__ == "__main__":
    unittest.main()
