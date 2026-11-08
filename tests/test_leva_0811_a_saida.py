"""Leva 08/11/2026, frente A (docs/briefings/2026-11-08-leva-conversa-inteira.md): compromisso de sair (date,
balada, buscar alguem) nao e tarefa comum. A1 texto de saida, A2 parede na cascata, A3 fecha sozinho quando o
GPS viu que ele foi, A4 parada absurda / "casa d@ <nome>", A5 recado so com alguem esperando, A6 aviso atrasado
numa mensagem so, A7 o aviso da manha repete no primeiro sinal de acordado.
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
import conversa_proativa as cp  # noqa: E402
import maps_client  # noqa: E402
import notificacoes  # noqa: E402
import onde_estou  # noqa: E402
import onde_vou  # noqa: E402
import vida_assistente  # noqa: E402

HOJE = date.today()
PROIBIDO = ("primeiro passo", "na tua lista há", "Feito", "ainda dá tempo de resolver hoje")
CASA = (-26.9000, -49.0000)
OFICINA = (-26.9100, -49.0600)


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

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, hora, local=None, estilo=None, sai_na_hora=None, parada=None, dia=HOJE, criada=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, local, estilo, sai_na_hora, parada) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (titulo, dia.isoformat(), hora, local, estilo, sai_na_hora, parada),
        )
        if criada:
            self.conn.execute("UPDATE tasks SET created_at = ? WHERE id = ?", (criada, cur.lastrowid))
        self.conn.commit()
        return cur.lastrowid

    def avisou(self, tipo, ref, quando: datetime):
        self.conn.execute("INSERT INTO notificacoes_enviadas (tipo, referencia_id, data, criado_em) VALUES (?, ?, ?, ?)",
                          (tipo, ref, quando.date().isoformat(), _utc(quando)))
        self.conn.commit()

    def linha(self, tid):
        return self.conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()


# ------------------------------------------------------------------ A1: texto de saida
class TextoDeSaidaTestCase(_Base):
    def test_depois_da_hora_diz_quando_chega_saindo_agora(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        avisos = dict(notificacoes.tarefas_com_horario_chegando(self.conn, _em("20:05"), caminho_min=lambda r: 12))
        self.assertIn("20:17", avisos[tid])  # 20:05 + 12 min de trajeto
        self.assertIn("Saindo agora", avisos[tid])
        for frase in PROIBIDO:
            self.assertNotIn(frase, avisos[tid])
        # sem conn (texto classico): o exemplo do briefing
        self.assertEqual(notificacoes.texto_saida_depois(None, self.linha(tid), _em("20:05"), lambda r: 10),
                         "Ainda em casa? Saindo agora tu chega às 20:15.")

    def test_buscar_alguem_com_sai_na_hora_tambem_e_saida(self):
        tid = self.tarefa("Buscar a Bruna", "18:00", sai_na_hora=1)
        corpo = dict(notificacoes.tarefas_com_horario_chegando(self.conn, _em("18:02")))[tid]
        self.assertIn("18:17", corpo)  # sem trajeto: a folga de 15 min
        self.assertNotIn("Feito", corpo)

    def test_gps_viu_que_saiu_ou_chegou(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, destino, hora_evento, saiu_em, chegada_prevista) "
                          "VALUES (?, ?, 'Restaurante Lua', '20:00', ?, ?)",
                          (HOJE.isoformat(), tid, _em("19:50").isoformat(), _em("20:09").isoformat()))
        self.conn.commit()
        indo = notificacoes.texto_saida_depois(self.conn, self.linha(tid), _em("20:01"))
        self.assertNotIn("Ainda em casa", indo)
        self.assertEqual(notificacoes._estado_saida(self.conn, tid, HOJE), ("indo", "20:09"))
        self.avisou("saida_chegou", tid, _em("20:05"))
        self.assertEqual(notificacoes._estado_saida(self.conn, tid, HOJE)[0], "chegou")
        self.assertIn("Chegou", notificacoes.texto_saida_depois(self.conn, self.linha(tid), _em("20:06")))

    def test_passou_da_hora_da_saida_sem_ainda_da_tempo(self):
        tid = self.tarefa("Festa da firma", "20:00", local="Salão Azul")
        self.avisou("tarefa_horario", tid, _em("20:05"))
        avisos = dict(notificacoes.tarefas_horario_passou(self.conn, _em("20:40"), caminho_min=lambda r: 20))
        self.assertIn("Festa da firma", avisos[tid])
        self.assertIn("21:00", avisos[tid])
        self.assertNotIn("ainda dá tempo", avisos[tid])

    def test_cara_do_aviso_de_saida_nunca_fala_de_tarefa(self):
        cinco_dias = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date", criada=cinco_dias)
        notificacoes.tarefas_com_horario_chegando(self.conn, _em("20:05"), caminho_min=lambda r: 15)  # guarda 15 min
        velho = "Ainda em casa? Saindo agora tu chega às 20:20."
        for rosto in aviso_cara.ROSTOS:
            with self.subTest(rosto=rosto), patch.object(aviso_cara, "escolher_rosto", return_value=rosto):
                _, corpo = aviso_cara.variar(self.conn, "tarefa_horario", tid, f"tarefa_horario-{tid}",
                                             "De novo · Date", velho, 1, _em("20:20"))
                for frase in PROIBIDO + ("passo de", "Quanto antes"):
                    self.assertNotIn(frase, corpo)
                self.assertIn("20:35", corpo)  # refeito pra hora da repeticao (20:20 + 15), nao o 20:20 velho
            with self.subTest(rosto=rosto, tipo="se_arrumar"), patch.object(aviso_cara, "escolher_rosto", return_value=rosto):
                _, corpo = aviso_cara.variar(self.conn, "se_arrumar", tid, f"se_arrumar-{tid}", "De novo · Date",
                                             "Date às 20:00. Começa agora e às 19:45 tu tá na porta.", 1, _em("19:10"))
                for frase in PROIBIDO + ("passo de",):
                    self.assertNotIn(frase, corpo)

    def test_e_agora_do_app_pra_saida_nao_pede_feito(self):
        saida = self.tarefa("Buscar a Bruna", "18:00", sai_na_hora=1)
        comum = self.tarefa("Pagar a fatura", "15:00")
        self.assertEqual(notificacoes.texto_agora_da_tarefa(self.linha(saida)), "Deu 18:00. Hora de ir: chave, carteira, celular.")
        self.assertEqual(notificacoes.texto_agora_da_tarefa(self.linha(comum)),
                         "Deu 15:00, é agora. Quando terminar, toca em Feito.")

    def test_caminho_da_tarefa_pro_gancho_do_tick(self):
        fake = MagicMock()
        fake._trajeto_min_aviso.return_value = 22
        fake._trajetos_parada_aviso.return_value = (2158, 10)  # perna absurda: teto -> folga
        com_lugar = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        casa_de = self.tarefa("Date", "21:00", local="casa do Tiago", estilo="date")
        parada = self.tarefa("Festa", "22:00", local="Salão Azul", parada="casa da Bruna")
        with patch.object(onde_vou, "_app", return_value=fake):
            self.assertEqual(onde_vou.caminho_min_tarefa(self.conn, self.linha(com_lugar)), 22)
            self.assertIsNone(onde_vou.caminho_min_tarefa(self.conn, self.linha(casa_de)))
            self.assertEqual(onde_vou.caminho_min_tarefa(self.conn, self.linha(parada)), 15 + notificacoes.PARADA_MIN + 10)
        fake._trajeto_min_aviso.assert_called_once()

    def test_tarefa_comum_continua_igual(self):
        tid = self.tarefa("Pagar a fatura", "15:00")
        self.assertFalse(notificacoes.e_saida(self.linha(tid)))
        self.assertEqual(dict(notificacoes.tarefas_com_horario_chegando(self.conn, _em("15:02")))[tid],
                         "Combinamos 15:00. Quando fizer, toca em Feito.")


class QuemEsperaTestCase(unittest.TestCase):
    def test_com_pessoa_e_saida(self):
        sim = [{"title": "Buscar a Ana"}, {"title": "Almoço com a mãe"}, {"title": "Date", "estilo": "date"},
               {"title": "Encontrar o Tiago", "local": "Praça"}, {"title": "Cinema", "extras": '{"com_quem": "Bia"}'}]
        nao = [{"title": "Ir no banco", "local": "Banco do Centro"}, {"title": "Consulta com a Dra Paula"},
               {"title": "Pagar com Pix"}, {"title": "Comer: almoço com a mãe"}, {"title": "Renovar CNH no Detran"}]
        for r in sim:
            self.assertTrue(notificacoes.com_pessoa(r), r)
        for r in nao:
            self.assertFalse(notificacoes.com_pessoa(r), r)
        self.assertFalse(notificacoes.e_saida({"title": "Estudar com o Pedro"}))  # sem lugar nem verbo de ir
        self.assertTrue(notificacoes.e_saida({"title": "Aeroclube", "sai_na_hora": 1}))
        self.assertTrue(notificacoes.e_saida({"title": "Mercado", "parada": "posto"}))


# ------------------------------------------------------------------ A6: aviso atrasado, uma mensagem so
class AvisoAtrasadoTestCase(_Base):
    def test_mais_de_1h_atrasado_diz_o_atraso_real(self):
        tid = self.tarefa("Pagar o boleto", "08:00")
        corpo = dict(notificacoes.tarefas_com_horario_chegando(self.conn, _em("10:30")))[tid]
        self.assertIn("2 h 30 min", corpo)
        self.assertNotIn("pouquinho", corpo)
        self.assertEqual(notificacoes.texto_atraso(75), "1 h 15 min")
        self.assertEqual(notificacoes.texto_atraso(120), "2 h")

    def test_passou_da_hora_nao_sai_junto_com_o_aviso_da_hora(self):
        tid = self.tarefa("Pagar o boleto", "08:00")
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, _em("10:30")), [])  # o da hora ainda nao saiu
        self.avisou("tarefa_horario", tid, _em("10:30"))
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, _em("10:45")), [])
        # rodada 3: 5 min depois da "Ultima chamada" (30 min) da insistencia, nunca no mesmo tick dela
        self.assertEqual(notificacoes.tarefas_horario_passou(self.conn, _em("11:01")), [])
        avisos = notificacoes.tarefas_horario_passou(self.conn, _em("11:06"))
        self.assertEqual([a[0] for a in avisos], [tid])  # mesma quantidade: so espaca

    def test_aviso_da_hora_desligado_nao_segura_o_passou(self):
        tid = self.tarefa("Pagar o boleto", "08:00")
        with patch.object(notificacoes, "_tarefa_horario_ligado", return_value=False):
            self.assertEqual([a[0] for a in notificacoes.tarefas_horario_passou(self.conn, _em("08:31"))], [tid])


# ------------------------------------------------------------------ A4: parada absurda
class ParadaAbsurdaTestCase(_Base):
    def test_teto_na_perna_da_parada(self):
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "casa da Bruna", 2158, 10),
                         (15 + notificacoes.PARADA_MIN + 10, {"nome": "casa da Bruna", "min_ate": 15}))
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "casa da Bruna", 2158, 10, ate_parada_dito=8)[0],
                         8 + notificacoes.PARADA_MIN + 10)
        self.assertEqual(notificacoes.caminho_com_parada(None, 15, "posto", 12, 2000)[0], 12 + notificacoes.PARADA_MIN + 15)

    def test_casa_de_alguem_sem_apelido_nao_vai_pro_google(self):
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "casa da Bruna"), "")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "posto Central"), "posto Central")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "casa da Bruna, Rua das Flores 10"),
                         "casa da Bruna, Rua das Flores 10")
        vida_assistente.salvar_apelido(self.conn, "bruna", "Rua das Acácias, 5")
        self.assertEqual(vida_assistente.resolver_parada(self.conn, "casa da Bruna"), "Rua das Acácias, 5")

    def test_plano_nao_pergunta_trajeto_de_casa_de_alguem_sem_apelido(self):
        self.tarefa("Date", "20:00", local="casa do Tiago", estilo="date")
        trajeto = MagicMock(return_value=2158)
        plano = notificacoes.plano_se_arrumar(self.conn, _em("18:00"), 40, trajeto_min=trajeto)
        trajeto.assert_not_called()
        self.assertEqual(plano[0]["caminho_min"], 15)
        vida_assistente.salvar_apelido(self.conn, "tiago", "Rua do Tiago, 1")
        notificacoes.plano_se_arrumar(self.conn, _em("18:00"), 40, trajeto_min=trajeto)
        trajeto.assert_called_once()

    def test_onde_estou_nao_geocodifica_casa_de_alguem(self):
        self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date", parada="casa da Bruna")
        apelidos = {x["apelido"] for x in onde_estou._lugares(self.conn, HOJE.isoformat())}
        self.assertIn("restaurante lua", apelidos)
        self.assertNotIn("casa da bruna", apelidos)


# ------------------------------------------------------------------ A5: recado so com alguem esperando
class RecadoSoComPessoaTestCase(_Base):
    def setUp(self):
        super().setUp()
        for p in (patch("hora_certa.avisar_evento", return_value=1), patch.object(onde_estou, "_avisar", return_value=True)):
            p.start()
            self.addCleanup(p.stop)

    def test_banco_nao_ganha_recado_date_ganha(self):
        banco = self.tarefa("Ir no banco", "14:00", local="Banco do Centro")
        date_ = self.tarefa("Jantar com a Bruna", "20:00", local="Restaurante Lua", estilo="date")
        self.assertFalse(onde_vou.recado_parado(self.conn, {"tarefa_id": banco, "atraso_min": 20}, _em("13:55")))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM indo_pra WHERE tarefa_id = ?", (banco,)).fetchone())
        self.assertTrue(onde_vou.recado_parado(self.conn, {"tarefa_id": date_, "atraso_min": 20}, _em("19:55")))

    def test_a_caminho_atrasado_pro_banco_nao_ganha_recado(self):
        banco = self.tarefa("Ir no banco", "14:00", local="Banco do Centro")
        date_ = self.tarefa("Jantar com a Bruna", "14:00", local="Restaurante Lua", estilo="date")
        for tid, destino in ((banco, "Banco do Centro"), (date_, "Restaurante Lua")):
            self.conn.execute("INSERT INTO indo_pra (dia, tarefa_id, destino, hora_evento, saiu_em) VALUES (?, ?, ?, '14:00', ?)",
                              (HOJE.isoformat(), tid, destino, _em("13:40").isoformat()))
        self.conn.commit()
        with patch.object(onde_estou, "_trajeto_min", return_value=40), \
                patch.object(onde_vou, "recado", return_value=True) as recado:
            onde_vou.atualizar_posicao(self.conn, -26.9, -49.0, _em("13:50"))
        self.assertEqual([c.args[2]["id"] for c in recado.call_args_list], [date_])


# ------------------------------------------------------------------ A2/A3: GPS (onde_estou)
class _BaseGps(_Base):
    def setUp(self):
        super().setUp()
        onde_estou._cache_trajeto.clear()
        maps_client._cache_coords.clear()
        env = {"ENDERECO_CASA": f"{CASA[0]},{CASA[1]}", "GOOGLE_MAPS_API_KEY": "chave-falsa"}
        self.loc = MagicMock(side_effect=lambda e: OFICINA if "Oficina" in e else (-26.95, -49.10))
        self.avisar = MagicMock(return_value=True)
        for p in (patch.object(onde_estou, "REAGIR_EM_THREAD", False), patch.dict(os.environ, env),
                  patch("maps_client.localizar", self.loc),
                  patch("maps_client.tempo_de_viagem", MagicMock(return_value={"duracao_minutos": 25})),
                  patch("maps_client.usar_cota", return_value=True),
                  patch.object(onde_estou, "_avisar", self.avisar),
                  patch("onde_vou.recado_parado", return_value=False),
                  patch("hora_certa.avisar_evento", return_value=1)):
            p.start()
            self.addCleanup(p.stop)
        vida_assistente.salvar_apelido(self.conn, "a oficina", "Rua da Oficina, 100, Brusque")
        self.conn.commit()

    def visita(self, ponto, chegada, saida=None):
        dados = {"lat": ponto[0], "lon": ponto[1], "precisao": 30.0, "chegada": chegada, "saida": saida}
        return onde_estou.registrar(self.conn, dados, saida or chegada)[0]

    def hora(self, tid):
        return self.linha(tid)["hora"]


class CascataParedeTestCase(_BaseGps):
    def test_cascata_para_no_compromisso_de_sair(self):
        antes = self.tarefa("Imprimir as contas", "19:00", local="Gráfica Central")
        date_ = self.tarefa("Date", "19:30", local="Restaurante Lua", estilo="date")
        self.visita(OFICINA, _em("18:00"))
        onde_estou.verificar(self.conn, _em("18:50"))
        self.assertNotEqual(self.hora(antes), "19:00")  # a de antes andou
        self.assertEqual(self.hora(date_), "19:30")  # o date nao (antes ia junto)

    def test_compromisso_de_sair_atrasado_avisa_sem_empurrar(self):
        date_ = self.tarefa("Buscar a Bruna", "20:00", local="Restaurante Lua")
        self.visita(OFICINA, _em("19:00"))
        onde_estou.verificar(self.conn, _em("19:50"))
        self.assertEqual(self.hora(date_), "20:00")
        texto = self.conn.execute("SELECT texto FROM chat_mensagens ORDER BY id DESC LIMIT 1").fetchone()["texto"]
        self.assertIn("Não mexi no horário", texto)
        self.assertIn("20h15", texto)  # 19:50 + 25 min
        self.assertTrue(db.ja_notificou_hoje(self.conn, onde_estou.TIPO_ATRASO, date_))


class SaidaQueRolouTestCase(_BaseGps):
    def test_chegou_no_destino_fecha_com_desfazer_uma_vez(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        self.avisou(onde_estou.TIPO_CHEGOU_DESTINO, tid, _em("19:57"))
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("19:58")), [])  # antes da hora: nao
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("20:00")), [tid])
        self.assertIsNotNone(self.linha(tid)["completed_at"])
        m = db.list_chat_mensagens(self.conn)[-1]
        self.assertIn("marquei como feito", m["texto"])
        self.assertTrue(any(c["type"] == "edicao" for c in db.cards_de_mensagem_chat(m)))
        self.avisar.assert_called_once()
        # desfez: nao fecha de novo
        self.conn.execute("UPDATE tasks SET completed_at = NULL WHERE id = ?", (tid,))
        self.conn.commit()
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("20:30")), [])

    def test_visita_no_lugar_perto_da_hora_fecha_a_de_ontem(self):
        ontem = HOJE - timedelta(days=1)
        tid = self.tarefa("Balada", "23:00", local="Boate Norte", estilo="balada", dia=ontem)
        self.conn.execute("INSERT INTO visitas (lat, lon, chegada, saida, lugar) VALUES (-26.95, -49.10, ?, ?, 'boate norte')",
                          (_em("23:20", ontem).isoformat(), _em("03:00").isoformat()))
        self.conn.commit()
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("09:00")), [tid])

    def test_sem_gps_nao_fecha(self):
        tid = self.tarefa("Date", "20:00", local="Restaurante Lua", estilo="date")
        comum = self.tarefa("Ir no banco", "14:00", local="Banco do Centro")
        self.avisou(onde_estou.TIPO_CHEGOU_DESTINO, comum, _em("14:00"))
        self.assertEqual(onde_estou.fechar_saidas_que_rolaram(self.conn, _em("21:00")), [])
        self.assertIsNone(self.linha(tid)["completed_at"])
        self.assertIsNone(self.linha(comum)["completed_at"])  # tarefa comum: so ele marca


# ------------------------------------------------------------------ A7: manha no primeiro sinal de acordado
class AcordouTestCase(_Base):
    def visto(self, local: datetime):
        db.definir_configuracao(self.conn, "ultimo_visto_em", local.astimezone(timezone.utc).replace(tzinfo=None)
                                .isoformat(timespec="seconds"))
        self.conn.commit()

    def test_primeiro_sinal_guarda_o_primeiro(self):
        self.assertIsNone(vida_assistente.primeiro_sinal_acordado(self.conn, _em("09:00")))
        self.visto(_em("04:30"))  # madrugada nao conta
        self.assertIsNone(vida_assistente.primeiro_sinal_acordado(self.conn, _em("09:00")))
        self.visto(_em("09:50"))
        self.assertEqual(vida_assistente.primeiro_sinal_acordado(self.conn, _em("10:00")), _em("09:50"))
        self.visto(_em("10:40"))  # o batimento do app anda; o primeiro sinal fica
        self.assertEqual(vida_assistente.primeiro_sinal_acordado(self.conn, _em("10:45")), _em("09:50"))

    def test_saiu_de_casa_pelo_gps_e_sinal(self):
        self.conn.execute("INSERT INTO visitas (lat, lon, chegada, saida, lugar) VALUES (-26.9, -49.0, ?, ?, 'casa')",
                          ((_em("00:00") - timedelta(hours=2)).isoformat(), _em("10:12").isoformat()))
        self.conn.commit()
        self.assertEqual(vida_assistente.primeiro_sinal_acordado(self.conn, _em("10:20")), _em("10:12"))

    def test_checkin_espera_ele_acordar_com_teto(self):
        self.assertEqual(cp.perguntar_como_esta(self.conn, _em("07:05")), [])  # antes saia as 07:00 fixo
        self.assertEqual(cp.perguntar_como_esta(self.conn, _em("09:30")), [])
        self.visto(_em("09:52"))
        self.assertEqual([s[0] for s in cp.perguntar_como_esta(self.conn, _em("09:55"))], ["como_esta"])

    def test_checkin_sai_no_teto_sem_sinal(self):
        self.assertEqual([s[0] for s in cp.perguntar_como_esta(self.conn, _em("11:30"))], ["como_esta"])

    def test_remedio_e_aviso_da_manha_repetem_quando_acorda(self):
        rem = self.tarefa("Tomar remédio", "08:00")
        a = self.tarefa("Pagar o boleto", "08:30")
        b = self.tarefa("Responder a Bruna", "09:00")
        cedo = self.tarefa("Ligar pra oficina", "10:30")  # depois de acordar: o aviso dela sai normal
        comer = self.tarefa("Comer: café", "08:15")
        visto_acordado = self.tarefa("Alongar", "09:55")
        for tid, quando in ((rem, "07:50"), (a, "08:20"), (b, "08:50"), (comer, "08:15"), (visto_acordado, "09:55")):
            self.avisou("tarefa_horario", tid, _em(quando))
        self.visto(_em("09:50"))
        with patch("hora_certa.avisar_evento", return_value=1) as avisar:
            self.assertEqual(cp.repetir_manha_ao_acordar(self.conn, _em("10:00")), [])
            self.assertEqual(cp.repetir_manha_ao_acordar(self.conn, _em("10:05")), [])  # uma vez por dia
        chamadas = [(c.args[1], c.args[2], c.args[3]) for c in avisar.call_args_list]
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(chamadas[0][1], "Tomar remédio")  # remedio primeiro, sozinho
        self.assertIn("Toma agora?", chamadas[0][2])
        self.assertIn("Pagar o boleto", chamadas[1][2])
        self.assertIn("Responder a Bruna", chamadas[1][2])
        self.assertNotIn("Alongar", chamadas[1][2])
        self.assertNotIn("café", chamadas[1][2])
        self.assertIsNotNone(cedo)

    def test_sem_sinal_nao_repete(self):
        rem = self.tarefa("Tomar remédio", "08:00")
        self.avisou("tarefa_horario", rem, _em("07:50"))
        with patch("hora_certa.avisar_evento", return_value=1) as avisar:
            cp.repetir_manha_ao_acordar(self.conn, _em("10:00"))
        avisar.assert_not_called()
        self.assertIn(cp.repetir_manha_ao_acordar, _passos_do_verificar())


def _passos_do_verificar():
    """O passo novo esta na lista do tick (conversa_proativa.verificar)."""
    import inspect

    fonte = inspect.getsource(cp.verificar)
    return [cp.repetir_manha_ao_acordar] if "repetir_manha_ao_acordar" in fonte else []


if __name__ == "__main__":
    unittest.main()
