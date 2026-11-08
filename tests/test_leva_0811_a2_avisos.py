"""Leva 08/11, frente A, segunda rodada: dia de Brasilia nos avisos (completed_at/created_at/criado_em sao UTC),
contexto dos avisos de amanha no iPhone, "e agora" de compromisso de sair, data crua que derrubava o ciclo de push,
textos de push no jeito ("tu", plural, acento) e o card da semana sem "no proximo voo" com voo parado.

Banco temporario, relogio injetado, sem rede, sem app.py. Nomes inventados."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import aviso_cara  # noqa: E402
import avisos_app  # noqa: E402
import avisos_texto  # noqa: E402
import conversa_proativa as cp  # noqa: E402
import notificacoes  # noqa: E402

TERCA = date(2026, 11, 10)
QUARTA = TERCA + timedelta(days=1)
AS_22H = datetime(2026, 11, 10, 22, 0)


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.addCleanup(self.conn.close)

    def tarefa(self, titulo, due=None, hora=None, feita_utc=None, criada_utc=None, local=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at, local) VALUES (?, ?, ?, ?, ?)",
            (titulo, due, hora, feita_utc, local))
        if criada_utc:
            self.conn.execute("UPDATE tasks SET created_at = ? WHERE id = ?", (criada_utc, cur.lastrowid))
        self.conn.commit()
        return cur.lastrowid

    def gasto(self, valor, criado_utc, categoria="mercado"):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) VALUES (?, ?, 'real', ?)",
            (valor, categoria, criado_utc))
        self.conn.commit()

    def aquecer_memoria(self):
        """A 1a vez de cada assunto e sempre a variacao classica (0); depois disso o contexto manda."""
        for assunto in ("tarefa_preparo", "tarefa_horario", "tarefa_agora"):
            avisos_texto.texto(assunto, {"hora": "10:00", "falta": 30}, conn=self.conn, chave="aquecer")

    def montar(self, agora=AS_22H):
        return avisos_app.montar(self.conn, agora)


# ------------------------------------------------------------------ itens 1 e 2: avisos do iPhone

class AvisosDeAmanhaNoIphoneTestCase(_Base):
    def test_aviso_de_amanha_nao_diz_sequencia_de_hoje(self):
        # 3 feitas hoje a tarde (15h de Brasilia = 18:00Z); as 22h o app pede os avisos de amanha
        for i in range(3):
            self.tarefa(f"feita {i}", feita_utc="2026-11-10 18:00:00")
        self.tarefa("Pagar a fatura", due=QUARTA.isoformat(), hora="07:00")
        self.aquecer_memoria()
        itens = [i for i in self.montar() if i["quando"].startswith(QUARTA.isoformat())]
        self.assertEqual({i["tipo"] for i in itens}, {"tarefa_preparo", "tarefa_horario", "tarefa_agora"})
        for i in itens:
            self.assertNotIn("sequência", i["corpo"], i)

    def test_feitas_depois_das_21h_nao_viram_sequencia_de_amanha(self):
        # 21h30 de Brasilia = 00:30Z do dia seguinte: em UTC elas ja "eram de amanha"
        for i in range(3):
            self.tarefa(f"feita {i}", feita_utc="2026-11-11 00:30:00")
        self.tarefa("Pagar a fatura", due=QUARTA.isoformat(), hora="07:00")
        self.aquecer_memoria()
        itens = [i for i in self.montar() if i["quando"].startswith(QUARTA.isoformat())]
        self.assertTrue(itens)
        for i in itens:
            self.assertNotIn("sequência", i["corpo"], i)

    def test_controle_aviso_de_hoje_ainda_ve_a_sequencia(self):
        for i in range(3):
            self.tarefa(f"feita {i}", feita_utc="2026-11-10 18:00:00")
        self.tarefa("Pagar a fatura", due=TERCA.isoformat(), hora="23:30")
        self.aquecer_memoria()
        horario = [i for i in self.montar() if i["tipo"] == "tarefa_horario"]
        self.assertEqual(len(horario), 1)
        self.assertIn("sequência", horario[0]["corpo"])

    def test_aviso_de_amanha_usa_a_hora_do_proprio_aviso(self):
        # as 22h a variacao "noite" cabia; o "e agora" das 07:00 de amanha nao e de noite
        self.tarefa("Pagar a fatura", due=QUARTA.isoformat(), hora="07:00")
        self.aquecer_memoria()
        agora = [i for i in self.montar() if i["tipo"] == "tarefa_agora"]
        self.assertEqual(len(agora), 1)
        self.assertNotIn("depois é só descanso", agora[0]["corpo"])

    def test_e_agora_de_compromisso_de_sair_tem_texto_de_sair(self):
        # com pessoa + local: e saida, mas nao entra no plano de se arrumar (sem palavra de sair no titulo)
        self.tarefa("Reunião com o Teodoro", due=QUARTA.isoformat(), hora="19:00", local="Escritorio central")
        agora = [i for i in self.montar() if i["tipo"] == "tarefa_agora"]
        self.assertEqual(len(agora), 1)
        self.assertNotIn("Feito", agora[0]["corpo"])
        classicos = {v["corpo"].format(hora="19:00") for v in avisos_texto.CATALOGO["saida_agora"]["variacoes"]
                     if v.get("corpo")}
        self.assertIn(agora[0]["corpo"], classicos)

    def test_e_agora_de_tarefa_comum_segue_com_feito(self):
        self.tarefa("Pagar a fatura", due=QUARTA.isoformat(), hora="19:00")
        agora = [i for i in self.montar() if i["tipo"] == "tarefa_agora"]
        self.assertEqual(len(agora), 1)
        self.assertIn("Feito", agora[0]["corpo"])


# ------------------------------------------------------------------ item 4: completed_at e UTC

class ConclusaoNoDiaLocalTestCase(_Base):
    def test_contexto_conta_feita_as_21h30_no_dia_de_hoje(self):
        for i in range(3):
            self.tarefa(f"feita {i}", feita_utc="2026-11-11 00:30:00")
        self.assertEqual(avisos_texto.contexto(self.conn, datetime(2026, 11, 10, 22, 30))["feitos_hoje"], 3)
        self.assertEqual(avisos_texto.contexto(self.conn, datetime(2026, 11, 11, 7, 0))["feitos_hoje"], 0)

    def test_fechamento_noturno_nao_conta_a_de_ontem_a_noite(self):
        # 01:30Z de terca = 22:30 de segunda
        self.tarefa("de ontem", feita_utc="2026-11-10 01:30:00")
        self.tarefa("aberta", due=TERCA.isoformat())
        msg = notificacoes.mensagem_fechamento_noturno(self.conn, hoje=TERCA)
        self.assertIn("Nenhuma tarefa concluída hoje.", msg)

    def test_fechamento_noturno_conta_a_de_hoje(self):
        self.tarefa("de hoje", feita_utc="2026-11-10 20:00:00")
        msg = notificacoes.mensagem_fechamento_noturno(self.conn, hoje=TERCA)
        self.assertIn("1 tarefa concluída hoje.", msg)


# ------------------------------------------------------------------ item 5: data crua nao derruba o ciclo

class DataCruaNaoDerrubaTestCase(_Base):
    def test_lembrete_com_data_ruim_e_pulado_e_o_resto_sai(self):
        daqui_2 = (date.today() + timedelta(days=2)).isoformat()
        self.conn.execute("INSERT INTO lembretes (titulo, data) VALUES (?, ?)", ("data torta", "15/03"))
        self.conn.execute("INSERT INTO lembretes (titulo, data) VALUES (?, ?)", ("renovar seguro", daqui_2))
        self.conn.commit()
        with self.assertLogs("notificacoes", level="WARNING") as logs:
            avisos = notificacoes.lembretes_proximos(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("renovar seguro", avisos[0][1])
        self.assertIn("15/03", " ".join(logs.output))

    def test_meta_com_prazo_ruim_e_pulada_e_o_resto_sai(self):
        criado = (datetime.now() - timedelta(days=50)).isoformat()
        prazo = (date.today() + timedelta(days=50)).isoformat()
        self.conn.execute("INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES "
                          "(?, ?, ?, ?, ?)", ("viagem", 5000, "dezembro", 0, criado))
        self.conn.execute("INSERT INTO goals (titulo, valor_alvo, prazo, valor_guardado, criado_em) VALUES "
                          "(?, ?, ?, ?, ?)", ("bicicleta", 10000, prazo, 100, criado))
        self.conn.commit()
        with self.assertLogs("notificacoes", level="WARNING"):
            avisos = notificacoes.metas_fora_do_ritmo(self.conn)
        self.assertEqual(len(avisos), 1)
        self.assertIn("bicicleta", avisos[0][1])
        self.assertIn("está atrás do ritmo", avisos[0][1])


# ------------------------------------------------------------------ item 6: gasto no dia de Brasilia

class GastoNoDiaLocalTestCase(_Base):
    def test_gasto_das_21h30_e_de_hoje_na_conversa_proativa(self):
        self.gasto(50, "2026-11-11 00:30:00")  # 21h30 de terca
        self.assertEqual(cp._gasto_no_dia(self.conn, TERCA), 50)
        self.assertEqual(cp._gasto_no_dia(self.conn, QUARTA), 0)

    def test_resumo_da_manha_ve_o_gasto_de_ontem_a_noite(self):
        self.gasto(50, "2026-11-11 00:30:00")
        msg = notificacoes.resumo_manha_gastos_pendentes(self.conn, hoje=QUARTA)
        self.assertIn("Ontem tu gastou R$ 50.00.", msg)

    def test_orcamento_do_mes_conta_o_gasto_da_ultima_noite(self):
        self.conn.execute("INSERT INTO orcamentos (categoria, valor_limite) VALUES ('mercado', 100)")
        self.conn.commit()
        self.gasto(120, "2026-12-01 01:00:00")  # 22h de 30/11
        avisos = notificacoes.orcamentos_perto_ou_estourados(self.conn, hoje=date(2026, 11, 30))
        self.assertEqual([(a[0], a[1]) for a in avisos], [("mercado", "estourado")])
        self.assertTrue(avisos[0][2].startswith("Tu já passou do orçamento"))

    def test_gasto_fora_do_normal_ve_o_gasto_da_noite(self):
        for i in range(6):
            self.gasto(30, f"2026-10-{10 + i:02d} 15:00:00")
        self.gasto(800, "2026-11-11 00:30:00")  # 21h30 de terca
        avisos = notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=TERCA)
        self.assertEqual(len(avisos), 1)
        self.assertIn("está bem acima do normal", avisos[0][1])
        self.assertEqual(notificacoes.gastos_fora_do_padrao_categoria(self.conn, hoje=QUARTA), [])


# ------------------------------------------------------------------ item 7: textos de push

class TextosDePushTestCase(_Base):
    def test_tarefas_atrasadas_com_tu_e_plural(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        self.tarefa("a", due=ontem)
        self.assertEqual(notificacoes.tarefas_atrasadas(self.conn), "Tu tem 1 tarefa atrasada.")
        self.tarefa("b", due=ontem)
        self.assertEqual(notificacoes.tarefas_atrasadas(self.conn), "Tu tem 2 tarefas atrasadas.")

    def test_tarefa_parada_com_acento_e_singular(self):
        self.tarefa("trocar o filtro", due=(TERCA - timedelta(days=1)).isoformat())
        avisos = notificacoes.tarefas_paradas(self.conn, dias_minimo=1, hoje=TERCA)
        self.assertEqual(avisos[0][1], "\"trocar o filtro\" está parada há 1 dia. Ainda precisa fazer isso?")

    def test_espera_parada_ja_faz(self):
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
                          ("a oficina", "orçamento do freio", "2026-11-03 15:00:00"))
        self.conn.commit()
        avisos = notificacoes.esperas_paradas(self.conn, dias_minimo=5, hoje=TERCA)
        self.assertEqual(len(avisos), 1)
        self.assertIn("já faz 7 dias", avisos[0][1])
        self.assertNotIn("fazem", avisos[0][1])
        self.conn.execute("UPDATE esperas SET criado_em = '2026-11-09 15:00:00'")
        self.conn.commit()
        self.assertIn("já faz 1 dia.", notificacoes.esperas_paradas(self.conn, dias_minimo=1, hoje=TERCA)[0][1])

    def test_currency_voo_diz_a_data_e_nao_a_contagem(self):
        hoje = date.today()
        antigo = hoje - timedelta(days=383)
        self.conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                          (antigo.isoformat(), "SSXX", 1.0))
        self.conn.commit()
        msg = notificacoes.currency_voo_baixa(self.conn, limiar_dias=21)
        self.assertIn(antigo.strftime("%d/%m/%Y"), msg)
        self.assertNotIn("383", msg)
        self.assertNotIn("você", msg.lower())
        self.assertTrue(msg.startswith("Teu último voo foi em"))

    def test_currency_voo_no_mesmo_ano_sem_o_ano(self):
        hoje = date.today()
        antigo = hoje - timedelta(days=25)
        self.conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                          (antigo.isoformat(), "SSXX", 1.0))
        self.conn.commit()
        msg = notificacoes.currency_voo_baixa(self.conn, limiar_dias=21)
        esperado = antigo.strftime("%d/%m") if antigo.year == hoje.year else antigo.strftime("%d/%m/%Y")
        self.assertIn(f"em {esperado}.", msg)


# ------------------------------------------------------------------ item 8: dias a partir de criado_em UTC

class DiasDesdeCriacaoTestCase(_Base):
    def test_dias_na_lista_conta_a_criada_as_22h_de_ontem(self):
        # 01:00Z de terca = 22h de segunda: ja e 1 dia na lista na terca
        tid = self.tarefa("ligar pro contador", criada_utc="2026-11-10 01:00:00")
        fatos = aviso_cara._fatos_tarefa(self.conn, tid, datetime(2026, 11, 10, 10, 0))
        self.assertEqual(fatos["dias_na_lista"], 1)

    def test_espera_criada_as_22h_conta_o_dia_local(self):
        # 01:00Z de 05/11 = 22h de 04/11: na terca 10/11 sao 6 dias, nao 5
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
                          ("a corretora", "a apólice", "2026-11-05 01:00:00"))
        self.conn.commit()
        avisos = notificacoes.esperas_paradas(self.conn, dias_minimo=6, hoje=TERCA)
        self.assertEqual(len(avisos), 1)
        self.assertIn("6 dias", avisos[0][1])

    def test_espera_com_data_ruim_nao_derruba_as_outras(self):
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES ('x', 'y', 'ontem')")
        self.conn.execute("INSERT INTO esperas (quem, sobre, criado_em) VALUES (?, ?, ?)",
                          ("a corretora", "a apólice", "2026-11-01 15:00:00"))
        self.conn.commit()
        with self.assertLogs("notificacoes", level="WARNING"):
            avisos = notificacoes.esperas_paradas(self.conn, dias_minimo=5, hoje=TERCA)
        self.assertEqual(len(avisos), 1)


# ------------------------------------------------------------------ item 3 (C6): card da semana

class SemanaSemVooParadoTestCase(_Base):
    def _voo(self, dias_atras):
        self.conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, ?, ?)",
                          ((TERCA - timedelta(days=dias_atras)).isoformat(), "SSXX", 1.5))
        self.conn.commit()

    def test_voo_parado_ha_mais_de_60_dias_nao_sugere_proximo_voo(self):
        self._voo(100)
        sug = cp.sugestao_semana(self.conn, TERCA, None, [0] * 7, 8, 0)
        self.assertFalse(sug and "próximo voo" in sug, sug)

    def test_voo_recente_ainda_sugere(self):
        self._voo(10)
        sug = cp.sugestao_semana(self.conn, TERCA, None, [0] * 7, 8, 0)
        self.assertIn("próximo voo", sug or "")


if __name__ == "__main__":
    unittest.main()
