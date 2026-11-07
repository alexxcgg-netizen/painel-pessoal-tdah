"""Avisos novos ligados (leva 07/11/2026 (2), docs/briefings/2026-11-07-lugar-certo-e-avisos.md):
transito_piorou, chegou_casa, meta_batida e sequencia (avisos_novos.py). Banco temporario, Maps sempre
mockado (tempo_fn injetado), push mockado."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import avisos_novos as an  # noqa: E402
import avisos_pendentes  # noqa: E402
import avisos_texto  # noqa: E402
import hora_certa  # noqa: E402
import onde_estou  # noqa: E402
import push_client  # noqa: E402
from assistente import avisos as avisos_assistente  # noqa: E402

PIN = "135790"
HOJE = date.today()


def _em(h, m=0, dia=None):
    return datetime.combine(dia or HOJE, datetime.min.time()).replace(hour=h, minute=m)


class _Banco(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        auth.definir_pin(self.conn, PIN, PIN)
        # silencio global fora do caminho dos testes (cada teste liga quando quer)
        db.definir_configuracao(self.conn, "silencio_inicio", "23:58")
        db.definir_configuracao(self.conn, "silencio_fim", "23:59")
        self.conn.commit()
        p = patch("maps_client.requests.post", side_effect=AssertionError("rede de verdade"))
        p.start()
        self.addCleanup(p.stop)
        g = patch("maps_client.requests.get", side_effect=AssertionError("rede de verdade"))
        g.start()
        self.addCleanup(g.stop)

    def tearDown(self):
        self.conn.close()

    def silencio_o_dia_todo(self):
        db.definir_configuracao(self.conn, "silencio_inicio", "00:00")
        db.definir_configuracao(self.conn, "silencio_fim", "23:59")
        self.conn.commit()

    def tarefa(self, titulo="Reunião no banco", hora="20:00", local="Banco Central", dia=None, **extra):
        cols = {"title": titulo, "hora": hora, "local": local, "due_date": (dia or HOJE).isoformat(), **extra}
        cur = self.conn.execute(
            f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", tuple(cols.values()))
        self.conn.commit()
        return cur.lastrowid


# ====================================================================== transito_piorou

class TransitoTest(_Banco):
    def setUp(self):
        super().setUp()
        self.chamadas = []
        self.minutos = 20
        na = patch("na_rua.estado", return_value=None)
        na.start()
        self.addCleanup(na.stop)

    def tempo(self, conn, local):
        self.chamadas.append(local)
        return self.minutos

    def com_base(self, tid, base=20):
        db.salvar_extras_tarefa(self.conn, tid, {"saida": {"sair": "19:35", "trajeto_min": base}})

    def test_piorou_10_min_ou_mais_avisa_com_nova_hora_de_sair(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)  # plano: sai 19:35
        self.minutos = 35
        r = an.avisos_transito(self.conn, _em(19, 0), self.tempo)
        self.assertEqual(len(r), 1)
        ref, titulo, corpo = r[0]
        self.assertEqual(ref, tid)
        self.assertIn("19:20", corpo)  # 20:00 - 35 - 5
        self.assertTrue(avisos_texto.cabe(titulo, corpo))
        self.assertNotIn("você", (titulo + corpo).lower())

    def test_piorou_pouco_nao_avisa(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)
        self.minutos = 29
        self.assertEqual(an.avisos_transito(self.conn, _em(19, 0), self.tempo), [])
        self.assertEqual(len(self.chamadas), 1)

    def test_fora_da_janela_nem_consulta_o_maps(self):
        tid = self.tarefa(hora="22:00")
        self.com_base(tid, 20)  # sai 21:35, janela 20:35-21:35
        self.minutos = 60
        self.assertEqual(an.avisos_transito(self.conn, _em(19, 0), self.tempo), [])
        self.assertEqual(an.avisos_transito(self.conn, _em(21, 40), self.tempo), [])  # passou da hora de sair
        self.assertEqual(self.chamadas, [])

    def test_cota_no_maximo_uma_consulta_a_cada_15_min_por_tarefa(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)
        self.minutos = 22
        for m in (0, 5, 10, 14):
            an.avisos_transito(self.conn, _em(18, 40 + m), self.tempo)
        self.assertEqual(len(self.chamadas), 1)
        an.avisos_transito(self.conn, _em(18, 55), self.tempo)
        self.assertEqual(len(self.chamadas), 2)

    def test_sem_trajeto_no_plano_a_primeira_medida_vira_base(self):
        self.tarefa(hora="20:00")
        self.minutos = 20
        self.assertEqual(an.avisos_transito(self.conn, _em(18, 45), self.tempo), [])  # janela 18:40-19:40 (sem base: 15)
        self.minutos = 31
        r = an.avisos_transito(self.conn, _em(19, 0), self.tempo)
        self.assertEqual(len(r), 1)
        self.assertIn("19:24", r[0][2])

    def test_ja_achou_nao_consulta_de_novo_e_avisou_nao_repete(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)
        self.minutos = 40
        r1 = an.avisos_transito(self.conn, _em(19, 0), self.tempo)
        r2 = an.avisos_transito(self.conn, _em(19, 20), self.tempo)  # tick seguro (silencio/foco): mesmo aviso
        self.assertEqual(r1, r2)
        self.assertEqual(len(self.chamadas), 1)
        db.marcar_notificado(self.conn, "transito_piorou", tid)
        self.assertEqual(an.avisos_transito(self.conn, _em(19, 25), self.tempo), [])

    def test_silencio_nao_gasta_consulta(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)
        self.silencio_o_dia_todo()
        self.minutos = 50
        self.assertEqual(an.avisos_transito(self.conn, _em(19, 0), self.tempo), [])
        self.assertEqual(self.chamadas, [])

    def test_sai_na_hora_parada_e_ja_na_rua_ficam_de_fora(self):
        self.tarefa(hora="20:00", sai_na_hora=1)
        self.tarefa(hora="20:00", parada="casa do guri")
        self.minutos = 50
        self.assertEqual(an.avisos_transito(self.conn, _em(19, 0), self.tempo), [])
        self.assertEqual(self.chamadas, [])
        self.tarefa(hora="20:00")
        with patch("na_rua.estado", return_value={"lugar": None, "onde": "na rua"}):
            self.assertEqual(an.avisos_transito(self.conn, _em(19, 0), self.tempo), [])
        self.assertEqual(self.chamadas, [])

    def test_tick_reaproveita_a_medida_do_aviso_de_sair_da_mesma_hora(self):
        agora = datetime.now()
        app._CACHE_TRAJETO_AVISO[(agora.date().isoformat(), agora.hour, "banco central")] = {"min": 33, "resumo": ""}
        self.addCleanup(app._CACHE_TRAJETO_AVISO.clear)
        with patch("maps_client.tempo_de_viagem") as tv:
            self.assertEqual(app._tempo_transito_aviso(self.conn, "Banco Central"), 33)
            tv.assert_not_called()

    def test_maps_padrao_sem_configurar_nao_chama_rede(self):
        tid = self.tarefa(hora="20:00")
        self.com_base(tid, 20)
        with patch.dict(os.environ, {"ENDERECO_CASA": ""}):
            self.assertEqual(an.avisos_transito(self.conn, _em(19, 0)), [])


# ====================================================================== chegou_casa

class ChegouCasaTest(_Banco):
    def setUp(self):
        super().setUp()
        self.enviados = []
        env = patch.dict(os.environ, {"ENDERECO_CASA": "Rua de Casa, 1"})
        env.start()
        self.addCleanup(env.stop)

    def enviar(self, conn, tipo, ref, titulo, corpo, agora, url="/", categoria=""):
        self.enviados.append({"tipo": tipo, "ref": ref, "titulo": titulo, "corpo": corpo, "url": url,
                              "categoria": categoria})

    def visita(self, lugar, chegada, saida=None):
        cur = self.conn.execute("INSERT INTO visitas (lat, lon, chegada, saida, lugar) VALUES (1, 1, ?, ?, ?)",
                                (chegada.isoformat(timespec="seconds"),
                                 saida.isoformat(timespec="seconds") if saida else None, lugar))
        self.conn.commit()
        return cur.lastrowid

    def voltou(self, saiu_de_casa, chegou):
        self.visita("casa", saiu_de_casa - timedelta(hours=8), saiu_de_casa)
        return self.visita("casa", chegou)

    def test_voltou_com_tarefa_de_fora_aberta_avisa_com_feito_amanha(self):
        tid = self.tarefa("Pagar boleto no banco", hora="15:00", local="Banco Central")
        self.tarefa("Lavar a louça", hora=None, local=None)  # sem lugar: nao e "fora"
        vid = self.voltou(_em(14, 0), _em(16, 0))
        self.assertTrue(an.chegou_casa(self.conn, vid, _em(16, 2), self.enviar))
        self.assertEqual(len(self.enviados), 1)
        e = self.enviados[0]
        self.assertEqual((e["tipo"], e["ref"], e["categoria"]), ("chegou_casa", tid, "casa"))
        self.assertEqual(e["url"], f"/?aba=tarefas&tarefa={tid}")
        self.assertTrue(db.ja_notificou_hoje(self.conn, "chegou_casa", tid))

    def test_varias_tarefas_de_fora_sem_botao(self):
        self.tarefa("Banco", hora="10:00", local="Banco Central")
        self.tarefa("Mercado", hora=None, local="Mercado Bom")
        vid = self.voltou(_em(9, 0), _em(12, 0))
        self.assertTrue(an.chegou_casa(self.conn, vid, _em(12, 1), self.enviar))
        self.assertEqual((self.enviados[0]["ref"], self.enviados[0]["categoria"]), (0, ""))

    def test_fora_menos_de_30_min_nao_avisa(self):
        self.tarefa(hora="10:00")
        vid = self.voltou(_em(11, 40), _em(12, 0))
        self.assertFalse(an.chegou_casa(self.conn, vid, _em(12, 1), self.enviar))
        self.assertEqual(self.enviados, [])

    def test_sem_tarefa_de_fora_ou_tarefa_ainda_por_vir_nao_avisa(self):
        self.tarefa("Ler", hora=None, local=None)
        self.tarefa("Dentista", hora="18:00", local="Clínica")  # ainda vai
        self.tarefa("Arrumar o quarto", hora="09:00", local="casa")
        vid = self.voltou(_em(9, 0), _em(12, 0))
        self.assertFalse(an.chegou_casa(self.conn, vid, _em(12, 1), self.enviar))

    def test_mesma_chegada_uma_vez_e_no_maximo_1_a_cada_3_h(self):
        self.tarefa(hora="09:30")
        vid = self.voltou(_em(9, 0), _em(11, 0))
        self.assertTrue(an.chegou_casa(self.conn, vid, _em(11, 1), self.enviar))
        self.assertFalse(an.chegou_casa(self.conn, vid, _em(11, 6), self.enviar))
        self.conn.execute("UPDATE visitas SET saida = ? WHERE id = ?", (_em(12, 0).isoformat(), vid))
        vid2 = self.visita("casa", _em(13, 0))
        self.assertFalse(an.chegou_casa(self.conn, vid2, _em(13, 1), self.enviar))  # 2 h depois
        self.conn.execute("UPDATE visitas SET saida = ? WHERE id = ?", (_em(13, 10).isoformat(), vid2))
        vid3 = self.visita("casa", _em(14, 30))
        self.assertTrue(an.chegou_casa(self.conn, vid3, _em(14, 31), self.enviar))  # 3,5 h depois
        self.assertEqual(len(self.enviados), 2)

    def test_silencio_segura_e_tenta_de_novo_depois(self):
        self.tarefa(hora="09:30")
        vid = self.voltou(_em(9, 0), _em(11, 0))
        self.silencio_o_dia_todo()
        self.assertFalse(an.chegou_casa(self.conn, vid, _em(11, 1), self.enviar))
        db.definir_configuracao(self.conn, "silencio_inicio", "23:58")
        self.conn.commit()
        self.assertTrue(an.chegou_casa(self.conn, vid, _em(11, 6), self.enviar))

    def test_desligado_em_assistente_avisos_nao_sai(self):
        self.tarefa(hora="09:30")
        vid = self.voltou(_em(9, 0), _em(11, 0))
        avisos_assistente.definir_tipo("chegou_casa", ligado=False, conn=self.conn)
        self.assertFalse(an.chegou_casa(self.conn, vid, _em(11, 1), self.enviar))

    def test_nao_duplica_com_casa_tarefa_na_mesma_chegada(self):
        self.tarefa(hora="18:00")
        vid = self.voltou(_em(17, 0), _em(19, 0))
        self.assertTrue(an.chegou_casa(self.conn, vid, _em(19, 1), self.enviar))
        with patch("onde_estou.mensagem_chegada", return_value=None):
            hora_certa.detectar(self.conn, _em(19, 2))
        self.assertEqual([i for i in hora_certa.pendentes(self.conn, _em(19, 3)) if i["tipo"] == "casa_tarefa"], [])
        # e o contrario: casa_tarefa ja falou nessa chegada -> chegou_casa fica quieto
        self.conn.execute("UPDATE visitas SET saida = ? WHERE id = ?", (_em(19, 30).isoformat(), vid))
        db.definir_configuracao(self.conn, an.CHAVE_ULTIMO_CASA, "")
        vid2 = self.visita("casa", _em(20, 30))
        hora_certa.marcar_chave(self.conn, f"casa:{vid2}", _em(20, 30))
        self.assertFalse(an.chegou_casa(self.conn, vid2, _em(20, 31), self.enviar))

    def test_entrega_vai_pra_fila_do_app_com_categoria_casa(self):
        tid = self.tarefa(hora="09:30")
        vid = self.voltou(_em(9, 0), _em(11, 0))
        agora = _em(11, 1)
        avisos_pendentes.marcar_contato(self.conn, agora)
        with patch.object(push_client, "configurado", return_value=True), \
                patch.object(push_client, "enviar") as env, patch("telegram_bot.configurado", return_value=False):
            self.assertTrue(an.chegou_casa(self.conn, vid, agora))
            env.assert_not_called()
        fila = avisos_pendentes.para_app(self.conn, agora)
        meu = [f for f in fila if f.get("tipo") == "chegou_casa"]
        self.assertEqual(len(meu), 1, fila)
        self.assertEqual(meu[0].get("categoria"), "casa")
        self.assertTrue(meu[0]["titulo"].startswith("🏠"))
        self.assertIn(str(tid), json.dumps(meu[0]))

    def test_gancho_no_reagir_da_visita(self):
        self.tarefa(hora="09:30")
        vid = self.voltou(_em(9, 0), _em(11, 0))
        with patch("avisos_novos.entregar_evento", side_effect=self.enviar), \
                patch("onde_estou._onde_vou", return_value=[]), patch("onde_estou.checar_atraso", return_value=None), \
                patch("onde_estou._avisar", return_value=False):
            feito = onde_estou.reagir(self.conn, vid, _em(11, 2))
        self.assertIn("chegou_casa", feito)
        self.assertEqual(len(self.enviados), 1)


# ====================================================================== meta_batida

class MetaTest(_Banco):
    def test_agua_do_dia_uma_vez_por_dia(self):
        db.definir_configuracao(self.conn, "agua_meta_copos", "2")
        self.conn.commit()
        self.assertEqual(an.avisos_meta(self.conn, _em(10)), [])
        db.registrar_hidratacao(self.conn, HOJE.isoformat())
        db.registrar_hidratacao(self.conn, HOJE.isoformat())
        r = an.avisos_meta(self.conn, _em(11))
        self.assertEqual([x[0] for x in r], [an.REF_AGUA])
        self.assertIn("2 copos de água", r[0][1] + r[0][2])
        db.marcar_notificado(self.conn, "meta_batida", an.REF_AGUA)
        self.assertEqual(an.avisos_meta(self.conn, _em(12)), [])

    def test_ja_batida_quando_ligou_nao_avisa_nova_avisa_uma_vez(self):
        g_velha = db.create_goal(self.conn, "Reserva", 100, None)
        db.add_to_goal(self.conn, g_velha, 150)
        self.assertEqual(an.avisos_meta(self.conn, _em(10)), [])  # 1a passada: base
        g = db.create_goal(self.conn, "Viagem pro Chile", 1000, None)
        db.add_to_goal(self.conn, g, 500)
        self.assertEqual(an.avisos_meta(self.conn, _em(10)), [])
        db.add_to_goal(self.conn, g, 500)
        r = an.avisos_meta(self.conn, _em(11))
        self.assertEqual([x[0] for x in r], [an.REF_GOAL + g])
        self.assertIn("Viagem pro Chile", r[0][1] + r[0][2])
        db.marcar_notificado(self.conn, "meta_batida", an.REF_GOAL + g)
        self.assertEqual(an.avisos_meta(self.conn, _em(12)), [])

    def test_horas_de_voo(self):
        db.definir_configuracao(self.conn, "aviacao_meta_horas", "10")
        self.conn.commit()
        an.avisos_meta(self.conn, _em(9))  # base (nada batido)
        self.conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES (?, 'SSBL', 'SSBL', 11)",
                          ((HOJE - timedelta(days=1)).isoformat(),))
        self.conn.commit()
        r = an.avisos_meta(self.conn, _em(10))
        self.assertEqual([x[0] for x in r], [an.REF_VOO_TOTAL + 10])
        self.assertIn("10 horas de voo", r[0][1] + r[0][2])


# ====================================================================== sequencia

class SequenciaTest(_Banco):
    def treino(self, dias_atras):
        self.conn.execute("INSERT INTO treinos (data, grupo) VALUES (?, 'peito')",
                          ((HOJE - timedelta(days=dias_atras)).isoformat(),))
        self.conn.commit()

    def test_treino_3_dias_seguidos_avisa_no_marco_e_uma_vez(self):
        self.treino(1)
        self.treino(2)
        self.assertEqual(an.avisos_sequencia(self.conn, _em(10)), [])  # hoje ainda nao
        self.treino(0)
        r = an.avisos_sequencia(self.conn, _em(19))
        self.assertEqual(len(r), 1)
        self.assertIn("3", r[0][1] + r[0][2])
        self.assertIn("Treino", r[0][1] + r[0][2])
        db.marcar_notificado(self.conn, "sequencia", r[0][0])
        self.assertEqual(an.avisos_sequencia(self.conn, _em(20)), [])

    def test_fora_do_marco_nao_avisa(self):
        for d in range(4):
            self.treino(d)
        self.assertEqual(an.avisos_sequencia(self.conn, _em(19)), [])

    def test_sequencia_nova_depois_de_quebrar_vale_de_novo(self):
        a = an.ref_sequencia("treino", HOJE - timedelta(days=10), 3)
        b = an.ref_sequencia("treino", HOJE - timedelta(days=2), 3)
        self.assertNotEqual(a, b)

    def test_remedio_diario_5_dias(self):
        cur = self.conn.execute("INSERT INTO tasks (title, hora, recorrencia) VALUES ('Tomar Creatina', '08:00', 'diaria')")
        modelo = cur.lastrowid
        self.conn.execute("INSERT INTO medicamentos (nome, horario, recorrencia, tarefa_modelo_id) "
                          "VALUES ('Creatina', '08:00', 'diaria', ?)", (modelo,))
        for d in range(5):
            dia = (HOJE - timedelta(days=d)).isoformat()
            self.conn.execute("INSERT INTO tasks (title, hora, due_date, recorrente_origem_id, completed_at) "
                              "VALUES ('Tomar Creatina', '08:00', ?, ?, ?)", (dia, modelo, dia + " 08:05:00"))
        self.conn.commit()
        r = an.avisos_sequencia(self.conn, _em(9))
        textos = [x[1] + " " + x[2] for x in r]
        self.assertTrue(any("Creatina" in t and "5" in t for t in textos), textos)

    def test_tarefas_em_dia_precisa_de_tudo_feito(self):
        for d in range(3):
            dia = (HOJE - timedelta(days=d)).isoformat()
            self.conn.execute("INSERT INTO tasks (title, due_date, completed_at) VALUES ('x', ?, ?)", (dia, dia + " 12:00:00"))
        aberta = self.tarefa("aberta", hora=None, local=None)
        self.conn.commit()
        self.assertEqual(an.avisos_sequencia(self.conn, _em(20)), [])
        db.complete_task(self.conn, aberta)
        self.conn.commit()
        r = an.avisos_sequencia(self.conn, _em(20))
        self.assertEqual(len(r), 1)
        self.assertIn("Tarefas em dia", r[0][1] + r[0][2])


# ====================================================================== tick (silencio, dedup, desligar)

class TickTest(_Banco):
    def rodar(self, agora):
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
                patch("maps_client.configurado", return_value=False):
            app.verificar_e_notificar()
        return [e for e in enviados if e["tag"].startswith("sequencia-")]

    def setUp(self):
        super().setUp()
        db.save_push_subscription(self.conn, "https://push.exemplo/1", json.dumps({"endpoint": "https://push.exemplo/1"}))
        for d in range(3):
            self.conn.execute("INSERT INTO treinos (data, grupo) VALUES (?, 'costas')",
                              ((HOJE - timedelta(days=d)).isoformat(),))
        self.conn.commit()

    def test_silencio_segura_depois_sai_uma_vez_com_emoji(self):
        self.silencio_o_dia_todo()
        self.assertEqual(self.rodar(_em(19)), [])
        db.definir_configuracao(self.conn, "silencio_inicio", "23:58")
        self.conn.commit()
        primeiro = self.rodar(_em(19, 5))
        self.assertEqual(len(primeiro), 1)
        self.assertTrue(primeiro[0]["titulo"].startswith("🔥"))
        self.assertEqual(self.rodar(_em(19, 10)), [])

    def test_desligado_nao_sai(self):
        avisos_assistente.definir_tipo("sequencia", ligado=False, conn=self.conn)
        self.assertEqual(self.rodar(_em(19)), [])

    def test_tipos_novos_no_catalogo_de_avisos(self):
        for t in ("transito_piorou", "chegou_casa", "meta_batida", "sequencia"):
            self.assertIn(t, avisos_assistente.TIPOS)


if __name__ == "__main__":
    unittest.main()
