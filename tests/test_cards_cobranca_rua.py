"""Leva 07/11, frente B (docs/briefings/2026-11-07-lugar-certo-e-avisos.md): nome curto nos cards `indo_pra` e
`espera` (nome_curto.py), uma cobranca por tarefa a cada 48 h (cobranca.py), "ja esta na rua" sem "sair de casa"
(na_rua.py) e atraso + recado numa mensagem so. Banco temporario (o _Base do test_onde_vou); Maps dublado.
Dados inventados."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from tests.test_onde_vou import CASA, HOJE, MECANICO, PRAIA, _Base, _em

import app
import cards
import cobranca
import conversa_proativa
import criptografia
import db
import na_rua
import nome_curto
import onde_estou
import onde_vou
import rotinas_esperto
import tempo


class NomeCurtoTestCase(_Base):
    def test_apelido_salvo_vira_o_nome_do_lugar_com_acento(self):
        tid = self.tarefa("Levar o carro pra revisão no mecânico e pegar a nota fiscal", "09:00")
        t = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        self.assertEqual(nome_curto.titulo_indo(self.conn, t), "Indo pro mecânico?")

    def test_pra_e_pro_pelo_genero(self):
        casos = {
            "Reunião na obra": "Indo pra obra?",
            "Ir ao banco pagar o boleto": "Indo pro banco?",
            "Almoço com o João no Madero": "Indo pro Madero?",
            "Voltar pra casa": "Indo pra casa?",
            "Dentista": "Indo pro dentista?",
            "Levar o carro": "Indo levar o carro?",  # verbo vai sem preposicao
        }
        for titulo, esperado in casos.items():
            with self.subTest(titulo=titulo):
                self.assertEqual(nome_curto.titulo_indo(None, {"title": titulo}), esperado)

    def test_date_mantem_o_com_quem(self):
        self.assertEqual(nome_curto.titulo_indo(None, {"title": "Date com a Júlia", "estilo": "date"}),
                         "Indo pro date com a Júlia?")
        self.assertEqual(nome_curto.titulo_indo(None, {"title": "Sair com a galera", "estilo": "balada"}),
                         "Indo pra balada?")

    def test_corte_so_em_palavra_inteira(self):
        longo = "Buscar a Sta às 21h e depois passar pra pegar as encomendas do mês inteiro"
        t = nome_curto.titulo_indo(None, {"title": longo})
        self.assertLessEqual(len(t), 48)
        self.assertTrue(t.endswith("…?"), t)
        sem_fim = t[len("Indo "):-2]
        self.assertTrue(longo.startswith(sem_fim[:1].upper() + sem_fim[1:]), t)  # palavra inteira, nada pela metade
        self.assertNotIn(sem_fim.split()[-1], {"a", "o", "de", "e", "pra", "às"})
        self.assertEqual(nome_curto.cortar("Sta às 21h no colégio", 12), "Sta às 21h…")
        self.assertEqual(nome_curto.cortar("curto", 12), "curto")
        self.assertEqual(nome_curto.cortar("Paralelepipedoenorme", 8), "Paralel…")

    def test_card_indo_pra_usa_o_nome_curto(self):
        self.conn.execute("DELETE FROM tasks")
        tid = self.tarefa("Levar o carro pra revisão e trocar o óleo antes da viagem", "20:00", "o mecânico")
        self.visita(CASA, _em("08:00"))
        vid = self.visita(CASA, _em("08:00"), _em("19:30"))
        onde_estou.reagir(self.conn, vid, _em("19:31"))
        [card] = self.cards_do_chat("indo_pra")
        self.assertEqual(card["data"]["titulo"], "Indo pro mecânico?")
        self.assertEqual(card["data"]["tarefa_id"], tid)


class EsperaTestCase(_Base):
    def test_espera_fala_o_nome_curto_e_nao_junta_o_titulo(self):
        titulo = "Levar a Sta no dentista às 15 e depois passar no mercado do centro pra comprar pão"
        self.tarefa(titulo, "15:00", "Clínica Sorriso")
        tempo.modo_espera(self.conn, _em("10:00"))
        row = self.conn.execute("SELECT texto FROM chat_mensagens ORDER BY id DESC LIMIT 1").fetchone()
        texto = criptografia.descriptografar(row["texto"])
        [card] = self.cards_do_chat("espera")
        self.assertEqual(card["data"]["nome"], "Clínica Sorriso")
        self.assertIn("depois vem a Clínica Sorriso às 15:00", texto)
        self.assertNotIn("mercado", texto)

    def test_espera_nao_sai_quando_ele_ja_esta_na_rua(self):
        self.tarefa("Dentista", "15:00", "Clínica Sorriso")
        self.visita(MECANICO, _em("09:30"))
        tempo.modo_espera(self.conn, _em("10:00"))
        self.assertEqual(self.cards_do_chat("espera"), [])


class CobrancaTestCase(_Base):
    def adiar(self, tid, vezes):
        for i in range(vezes):
            self.conn.execute("INSERT INTO tarefas_adiadas (task_id, de, para) VALUES (?, ?, ?)",
                              (tid, "2026-11-01", "2026-11-02"))
        self.conn.commit()

    def test_uma_vez_a_cada_48h_somando_os_tipos(self):
        tid = self.tarefa("Separar os papéis", None)
        agora = datetime(2026, 11, 7, 10, 0)
        self.assertTrue(cobranca.pode(self.conn, tid, "tarefa_parada", agora))
        cobranca.registrar(self.conn, tid, "tarefa_parada", agora)
        self.assertFalse(cobranca.pode(self.conn, tid, "travou", agora + timedelta(hours=20)))
        self.assertFalse(cobranca.pode(self.conn, tid, "tarefa_adiada", agora + timedelta(hours=47)))
        self.assertTrue(cobranca.pode(self.conn, tid, "tarefa_adiada", agora + timedelta(hours=49)))

    def test_adiada_ganha_de_travou_e_de_parada(self):
        tid = self.tarefa("Separar os papéis", None)
        self.adiar(tid, 3)
        agora = datetime(2026, 11, 7, 10, 0)
        self.assertFalse(cobranca.pode(self.conn, tid, "travou", agora))
        self.assertFalse(cobranca.pode(self.conn, tid, "tarefa_parada", agora))
        self.assertTrue(cobranca.pode(self.conn, tid, "tarefa_adiada", agora))

    def test_no_mesmo_tick_a_tarefa_recebe_um_cutucao_so(self):
        tid = self.tarefa("Separar os papéis", None)
        self.adiar(tid, 4)
        agora = datetime.combine(HOJE, datetime.min.time()).replace(hour=10)
        with patch("hora_certa.enfileirar"):
            rotinas_esperto.verificar(self.conn, agora)
        with patch.object(conversa_proativa.foco, "segurando_avisos", return_value=False), \
                patch.object(conversa_proativa.dia_ruim, "ativo", return_value=False):
            conversa_proativa.perguntar_por_que_travou(self.conn, agora)
        tipos = [c["type"] for c in self.cards_do_chat() if c["type"] in ("tarefa_adiada", "travou")]
        self.assertEqual(tipos, ["tarefa_adiada"])
        # no dia seguinte, nada da mesma tarefa (48 h)
        self.assertFalse(cobranca.pode(self.conn, tid, "travou", agora + timedelta(days=1)))


class NaRuaTestCase(_Base):
    def test_estado(self):
        agora = _em("10:00")
        self.assertIsNone(na_rua.estado(self.conn, agora))  # sem visita: sem base, nao chuta
        self.visita(CASA, _em("08:00"))
        self.assertIsNone(na_rua.estado(self.conn, agora))  # em casa
        self.conn.execute("DELETE FROM visitas")
        self.conn.commit()
        self.tarefa("Pagar o mecânico", "11:00")  # o nome com acento vem das tarefas de hoje
        self.visita(MECANICO, _em("09:30"))
        self.assertEqual(na_rua.estado(self.conn, agora)["onde"], "no mecânico")

    def test_saiu_e_nao_chegou_ainda_e_na_rua(self):
        self.visita(CASA, _em("08:00"), _em("09:40"))
        self.assertEqual(na_rua.estado(self.conn, _em("10:00"))["onde"], "na rua")
        self.assertIsNone(na_rua.estado(self.conn, _em("13:00")))  # saida velha: sem base

    def test_lugar_sem_nome_longe_de_casa_e_na_rua(self):
        self.visita((-26.98, -49.10), _em("09:30"))
        self.assertEqual(na_rua.estado(self.conn, _em("10:00"))["onde"], "na rua")

    def test_ajustar_plano_troca_sair_de_casa_por_daqui(self):
        plano = {"sair_de_casa": "19:35", "comecar_a_se_arrumar": "18:55", "ida_min": 25}
        agora = _em("17:00")
        self.assertEqual(na_rua.ajustar_plano(self.conn, plano, HOJE.isoformat(), "20:00", "Viva Beach", agora), plano)
        self.tarefa("Pagar o mecânico", "16:30")
        self.visita(MECANICO, _em("16:00"))
        novo = na_rua.ajustar_plano(self.conn, plano, HOJE.isoformat(), "20:00", "Viva Beach", agora)
        self.assertNotIn("sair_de_casa", novo)
        self.assertNotIn("comecar_a_se_arrumar", novo)
        self.assertEqual((novo["ja_esta_na_rua"], novo["daqui_ate_la_min"], novo["sair_daqui"]),
                         ("no mecânico", 25, "19:35"))
        self.assertIn("não fala em sair de casa", novo["nota"])
        # outro dia: o plano de sempre
        amanha = (HOJE + timedelta(days=1)).isoformat()
        self.assertEqual(na_rua.ajustar_plano(self.conn, plano, amanha, "20:00", "Viva Beach", agora), plano)

    def test_replanejar_saida_ja_na_rua(self):
        # 08/11: so vale pro compromisso das proximas na_rua.HORIZONTE_H horas (o date daqui a 1 h)
        if datetime.now().strftime("%H:%M") >= "22:50":
            self.skipTest("rodando depois das 22:50")
        hora = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        tid = self.tarefa("Date com a Júlia", hora, "Viva Beach", "date")
        self.visita(MECANICO, datetime.now() - timedelta(minutes=30))
        with patch.object(app.claude_client, "avisar_passo"):
            r = app.replanejar_saida(self.conn, tid, {"hora": hora})
        self.assertNotIn("sair_de_casa", r["plano"])
        self.assertIn("ja_esta_na_rua", r["plano"])

    def test_compromisso_de_noite_com_ele_na_rua_de_manha_segue_o_plano_de_casa(self):
        """08/11 (rodada com a IA de verdade): na rua as 7h30, date as 20h -> "sai daqui 19h03" e o card sem
        "se arrumar". Longe assim ele passa em casa antes."""
        plano = {"sair_de_casa": "19:35", "comecar_a_se_arrumar": "18:55", "ida_min": 25}
        self.visita(MECANICO, _em("07:00"))
        self.assertEqual(na_rua.ajustar_plano(self.conn, plano, HOJE.isoformat(), "20:00", "Viva Beach",
                                              _em("07:30")), plano)
        self.assertNotEqual(na_rua.ajustar_plano(self.conn, plano, HOJE.isoformat(), "20:00", "Viva Beach",
                                                 _em("17:30")), plano)
        self.assertIn("plano de sempre", na_rua.linha_contexto(self.conn, _em("07:30")))

    def test_card_do_date_sem_se_arrumar_e_sair_de_casa(self):
        tid = self.tarefa("Date com a Júlia", "23:50", "Viva Beach", "date")
        ef = {"entidade": "tarefa", "id": tid, "estilo": "date",
              "na_rua": {"onde": "no mecânico", "daqui_min": 20, "sair": "23:30"}}
        d = cards.card_compromisso(self.conn, ef)["data"]
        self.assertEqual([p["rotulo"] for p in d["cadeia"]], ["Sair daqui", "Chegar"])
        self.assertEqual(d["na_rua"], {"onde": "no mecânico", "daqui_min": 20, "sair": "23:30"})
        d2 = cards.card_compromisso(self.conn, {"entidade": "tarefa", "id": tid, "estilo": "date"})["data"]
        self.assertEqual([p["rotulo"] for p in d2["cadeia"]], ["Se arrumar", "Sair", "Chegar"])

    def test_contexto_do_chat_avisa_que_ja_esta_na_rua(self):
        self.visita(MECANICO, datetime.now() - timedelta(minutes=20))
        linha = na_rua.linha_contexto(self.conn)
        self.assertIn("já está na rua", linha)
        self.assertIn("não fala em sair de casa", linha)


class AtrasoERecadoTestCase(_Base):
    def test_atraso_e_recado_numa_mensagem_so(self):
        self.tarefa("Date com a Júlia", "20:00", "Viva Beach", "date")
        vid = self.visita(MECANICO, _em("18:00"))
        self.tempo_de_viagem.return_value = {"duracao_minutos": 40}
        antes = self.conn.execute("SELECT COUNT(*) FROM chat_mensagens").fetchone()[0]
        feito = onde_estou.reagir(self.conn, vid, _em("19:40"))
        self.assertIn("atraso", feito)
        self.assertIn("recado", feito)
        msgs = self.conn.execute("SELECT texto, cards_json FROM chat_mensagens ORDER BY id").fetchall()[antes:]
        com_card = [m for m in msgs if m["cards_json"]]
        tipos = [[c["type"] for c in json.loads(criptografia.descriptografar(m["cards_json"]))] for m in com_card]
        # leva 08/11 (A2): date e parede - o horario nao anda (sem card de edicao), o recado vai na mesma mensagem
        self.assertIn(["recado_atraso"], tipos)
        self.assertEqual(sum("recado_atraso" in t for t in tipos), 1)
        texto = criptografia.descriptografar(com_card[tipos.index(["recado_atraso"])]["texto"])
        self.assertIn("Deixei o recado pronto", texto)
        self.assertIn("Não mexi no horário", texto)
