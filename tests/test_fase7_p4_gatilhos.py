# Faixa P4 (Fase 7): motor de avaliacao (assistente/regras.py:avaliar_regra
# e os avaliadores por gatilho) + o gatilho do tick
# (assistente/gatilhos/p4_regras.py:executar). Banco sempre em memoria
# (schema minimo criado a mao, como tests/test_ia_historico.py faz - nao
# depende da infra de migracao automatica ainda nao mesclada). `enfileirar`
# sempre mockado (contrato da Caixa, faixa P1a) - nunca cria dado de
# verdade fora deste teste.
import json
import sqlite3
import unittest
from datetime import datetime
from unittest.mock import patch

from assistente import regras as motor
from assistente.gatilhos import p4_regras as gatilho

MIGRACAO_SQL = None  # carregado em setUpModule, pra achar o caminho 1x


def setUpModule():
    global MIGRACAO_SQL
    from pathlib import Path
    caminho = Path(__file__).resolve().parent.parent / "migracoes" / "202609241230_p4_regras.sql"
    MIGRACAO_SQL = caminho.read_text(encoding="utf-8")


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRACAO_SQL)
    conn.executescript(
        """
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            source_text TEXT,
            tipo TEXT NOT NULL DEFAULT 'real',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_text TEXT,
            due_at TEXT,
            due_date TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE habitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            meta TEXT,
            frequencia_tipo TEXT NOT NULL DEFAULT 'diario',
            dias_semana TEXT,
            vezes_por_semana INTEGER,
            horario TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE habito_marcacoes (
            data TEXT NOT NULL,
            habito_id INTEGER NOT NULL,
            marcado_em TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (data, habito_id)
        );
        """
    )
    conn.commit()
    return conn


def _inserir_regra(conn, regra: dict, texto_original: str = "x", ativa: int = 1,
                    pausada_ate=None, ultima_vez=None) -> int:
    cur = conn.execute(
        "INSERT INTO p4_regras (texto_original, json, ativa, pausada_ate, ultima_vez) "
        "VALUES (?, ?, ?, ?, ?)",
        (texto_original, json.dumps(regra, ensure_ascii=False), ativa, pausada_ate, ultima_vez),
    )
    conn.commit()
    return cur.lastrowid


def _inserir_gasto(conn, categoria: str, valor: float, quando: str, tipo: str = "real"):
    conn.execute(
        "INSERT INTO expenses (amount, category, tipo, created_at) VALUES (?, ?, ?, ?)",
        (valor, categoria, tipo, quando),
    )
    conn.commit()


def _inserir_tarefa(conn, titulo: str, due_at=None, due_date=None, completed_at=None) -> int:
    cur = conn.execute(
        "INSERT INTO tasks (title, due_at, due_date, completed_at) VALUES (?, ?, ?, ?)",
        (titulo, due_at, due_date, completed_at),
    )
    conn.commit()
    return cur.lastrowid


def _inserir_habito(conn, nome: str, frequencia_tipo="diario", horario=None,
                     dias_semana=None, vezes_por_semana=None) -> int:
    cur = conn.execute(
        "INSERT INTO habitos (nome, frequencia_tipo, horario, dias_semana, vezes_por_semana) "
        "VALUES (?, ?, ?, ?, ?)",
        (nome, frequencia_tipo, horario, dias_semana, vezes_por_semana),
    )
    conn.commit()
    return cur.lastrowid


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.addCleanup(self.conn.close)


# ---------------------------------------------------------------------------
# gatilho: horario
# ---------------------------------------------------------------------------

class TestAvaliarHorario(Base):
    def test_diario_antes_da_hora_nao_dispara(self):
        cond = {"tipo": "diario", "hora": "18:00"}
        agora = datetime(2026, 9, 24, 17, 59)
        self.assertFalse(motor.avaliar_horario(cond, agora, None))

    def test_diario_na_hora_dispara(self):
        cond = {"tipo": "diario", "hora": "18:00"}
        agora = datetime(2026, 9, 24, 18, 0)
        self.assertTrue(motor.avaliar_horario(cond, agora, None))

    def test_diario_depois_da_hora_dispara(self):
        cond = {"tipo": "diario", "hora": "18:00"}
        agora = datetime(2026, 9, 24, 21, 30)
        self.assertTrue(motor.avaliar_horario(cond, agora, None))

    def test_diario_nao_dispara_2x_no_mesmo_dia(self):
        cond = {"tipo": "diario", "hora": "18:00"}
        ultima_vez = datetime(2026, 9, 24, 18, 1)  # ja disparou hoje
        agora = datetime(2026, 9, 24, 20, 0)
        self.assertFalse(motor.avaliar_horario(cond, agora, ultima_vez))

    def test_diario_dispara_de_novo_no_dia_seguinte(self):
        cond = {"tipo": "diario", "hora": "18:00"}
        ultima_vez = datetime(2026, 9, 24, 18, 1)
        agora = datetime(2026, 9, 25, 18, 5)
        self.assertTrue(motor.avaliar_horario(cond, agora, ultima_vez))

    def test_semanal_so_dispara_no_dia_certo(self):
        cond = {"tipo": "semanal", "dia_semana": 0, "hora": "09:00"}  # segunda
        terca = datetime(2026, 9, 22, 10, 0)  # terca-feira
        segunda = datetime(2026, 9, 21, 10, 0)
        self.assertFalse(motor.avaliar_horario(cond, terca, None))
        self.assertTrue(motor.avaliar_horario(cond, segunda, None))

    def test_data_so_dispara_no_dia_exato(self):
        cond = {"tipo": "data", "data": "2026-12-25", "hora": "10:00"}
        self.assertFalse(motor.avaliar_horario(cond, datetime(2026, 12, 24, 10, 0), None))
        self.assertTrue(motor.avaliar_horario(cond, datetime(2026, 12, 25, 10, 30), None))
        self.assertFalse(motor.avaliar_horario(cond, datetime(2026, 12, 26, 10, 0), None))


# ---------------------------------------------------------------------------
# gatilho: gasto_categoria
# ---------------------------------------------------------------------------

class TestAvaliarGastoCategoria(Base):
    def test_periodo_intervalo_semana(self):
        # 2026-09-24 e uma quinta-feira -> semana = 21 (segunda) a 27 (domingo)
        inicio, fim = motor.periodo_intervalo(datetime(2026, 9, 24).date(), "semana")
        self.assertEqual(inicio.isoformat(), "2026-09-21")
        self.assertEqual(fim.isoformat(), "2026-09-27")

    def test_periodo_intervalo_mes(self):
        inicio, fim = motor.periodo_intervalo(datetime(2026, 9, 24).date(), "mes")
        self.assertEqual(inicio.isoformat(), "2026-09-01")
        self.assertEqual(fim.isoformat(), "2026-09-30")

    def test_periodo_intervalo_mes_dezembro(self):
        inicio, fim = motor.periodo_intervalo(datetime(2026, 12, 15).date(), "mes")
        self.assertEqual(inicio.isoformat(), "2026-12-01")
        self.assertEqual(fim.isoformat(), "2026-12-31")

    def test_periodo_intervalo_dia(self):
        inicio, fim = motor.periodo_intervalo(datetime(2026, 9, 24).date(), "dia")
        self.assertEqual(inicio, fim)

    def test_periodo_invalido_levanta(self):
        with self.assertRaises(ValueError):
            motor.periodo_intervalo(datetime(2026, 9, 24).date(), "ano")

    def test_nao_dispara_abaixo_do_limite(self):
        _inserir_gasto(self.conn, "mercado", 100.0, "2026-09-22 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)
        self.assertEqual(total, 100.0)

    def test_dispara_acima_do_limite(self):
        _inserir_gasto(self.conn, "mercado", 200.0, "2026-09-22 10:00:00")
        _inserir_gasto(self.conn, "mercado", 150.0, "2026-09-23 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)
        self.assertEqual(total, 350.0)

    def test_categoria_case_insensitive(self):
        _inserir_gasto(self.conn, "Mercado", 400.0, "2026-09-22 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)

    def test_ignora_gasto_planejado(self):
        _inserir_gasto(self.conn, "mercado", 1000.0, "2026-09-22 10:00:00", tipo="planejado")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)
        self.assertEqual(total, 0.0)

    def test_ignora_gasto_fora_do_periodo(self):
        _inserir_gasto(self.conn, "mercado", 400.0, "2026-08-01 10:00:00")  # mes passado
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)

    def test_ignora_outra_categoria(self):
        _inserir_gasto(self.conn, "lazer", 400.0, "2026-09-22 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)

    def test_nao_dispara_2x_no_mesmo_periodo(self):
        _inserir_gasto(self.conn, "mercado", 400.0, "2026-09-22 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        ultima_vez = datetime(2026, 9, 23, 9, 0)  # ja disparou nessa mesma semana
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 24, 12, 0), ultima_vez)
        self.assertFalse(deve)

    def test_dispara_de_novo_na_semana_seguinte(self):
        _inserir_gasto(self.conn, "mercado", 400.0, "2026-09-29 10:00:00")
        cond = {"categoria": "mercado", "periodo": "semana", "valor_limite": 300}
        ultima_vez = datetime(2026, 9, 23, 9, 0)  # disparou na semana anterior
        deve, total = motor.avaliar_gasto_categoria(self.conn, cond, datetime(2026, 9, 29, 12, 0), ultima_vez)
        self.assertTrue(deve)


# ---------------------------------------------------------------------------
# gatilho: habito_nao_feito_ate
# ---------------------------------------------------------------------------

class TestAvaliarHabito(Base):
    def test_habito_inexistente(self):
        cond = {"habito_nome": "Nao existe"}
        deve, habito = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 22, 0), None)
        self.assertFalse(deve)
        self.assertIsNone(habito)

    def test_com_hora_explicita_antes_nao_dispara(self):
        _inserir_habito(self.conn, "Meditar", horario="08:00")
        cond = {"habito_nome": "Meditar", "hora": "20:00"}
        deve, _ = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 19, 0), None)
        self.assertFalse(deve)

    def test_com_hora_explicita_depois_dispara(self):
        _inserir_habito(self.conn, "Meditar")
        cond = {"habito_nome": "Meditar", "hora": "20:00"}
        deve, habito = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 20, 30), None)
        self.assertTrue(deve)
        self.assertEqual(habito["nome"], "Meditar")

    def test_nao_dispara_se_ja_marcado_hoje(self):
        habito_id = _inserir_habito(self.conn, "Meditar")
        self.conn.execute("INSERT INTO habito_marcacoes (data, habito_id) VALUES (?, ?)",
                           ("2026-09-24", habito_id))
        self.conn.commit()
        cond = {"habito_nome": "Meditar", "hora": "20:00"}
        deve, _ = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 21, 0), None)
        self.assertFalse(deve)

    def test_nao_dispara_2x_no_mesmo_dia(self):
        _inserir_habito(self.conn, "Meditar")
        cond = {"habito_nome": "Meditar", "hora": "20:00"}
        ultima_vez = datetime(2026, 9, 24, 20, 1)
        deve, _ = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 21, 0), ultima_vez)
        self.assertFalse(deve)

    def test_sem_hora_usa_horario_do_habito(self):
        # habito com horario proprio (08:00) - so "passa batido" 1h depois.
        _inserir_habito(self.conn, "Agua", horario="08:00")
        cond = {"habito_nome": "Agua"}
        self.assertFalse(motor.avaliar_habito_nao_feito_ate(
            self.conn, cond, datetime(2026, 9, 24, 8, 30), None)[0])
        self.assertTrue(motor.avaliar_habito_nao_feito_ate(
            self.conn, cond, datetime(2026, 9, 24, 9, 1), None)[0])

    def test_sem_hora_e_sem_horario_no_habito_nunca_dispara(self):
        _inserir_habito(self.conn, "Sem horario")
        cond = {"habito_nome": "Sem horario"}
        deve, _ = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 23, 0), None)
        self.assertFalse(deve)

    def test_busca_por_habito_id(self):
        habito_id = _inserir_habito(self.conn, "Correr", horario="06:00")
        cond = {"habito_id": habito_id, "habito_nome": "Correr"}
        deve, habito = motor.avaliar_habito_nao_feito_ate(self.conn, cond, datetime(2026, 9, 24, 7, 30), None)
        self.assertTrue(deve)
        self.assertEqual(habito["id"], habito_id)


# ---------------------------------------------------------------------------
# gatilho: tarefa_vencida
# ---------------------------------------------------------------------------

class TestAvaliarTarefaVencida(Base):
    def test_sem_tarefas_nao_dispara(self):
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)
        self.assertEqual(tarefas, [])

    def test_tarefa_vencida_por_due_date_dispara(self):
        _inserir_tarefa(self.conn, "Pagar conta", due_date="2026-09-20")
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)
        self.assertEqual(len(tarefas), 1)

    def test_tarefa_vencida_por_due_at_dispara(self):
        _inserir_tarefa(self.conn, "Ligar pro dentista", due_at="2026-09-24 08:00:00")
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)

    def test_tarefa_no_futuro_nao_dispara(self):
        _inserir_tarefa(self.conn, "Viajar", due_date="2026-12-25")
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)

    def test_tarefa_ja_completada_nao_conta(self):
        _inserir_tarefa(self.conn, "Feita", due_date="2026-09-01", completed_at="2026-09-02 10:00:00")
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)

    def test_varias_tarefas_vencidas(self):
        _inserir_tarefa(self.conn, "A", due_date="2026-09-01")
        _inserir_tarefa(self.conn, "B", due_date="2026-09-10")
        deve, tarefas = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)
        self.assertEqual(len(tarefas), 2)

    def test_nao_dispara_2x_no_mesmo_dia(self):
        _inserir_tarefa(self.conn, "A", due_date="2026-09-01")
        ultima_vez = datetime(2026, 9, 24, 9, 0)
        deve, _ = motor.avaliar_tarefa_vencida(self.conn, {}, datetime(2026, 9, 24, 15, 0), ultima_vez)
        self.assertFalse(deve)


# ---------------------------------------------------------------------------
# gatilho: sinal_iphone
# ---------------------------------------------------------------------------

def _criar_tabela_sinais(conn):
    # Mesmo schema de migracoes/202609241240_p7_sinais.sql (faixa P7).
    conn.executescript(
        "CREATE TABLE sinais (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tipo TEXT NOT NULL, lugar TEXT, quando TEXT NOT NULL, "
        "recebido_em TEXT NOT NULL DEFAULT (datetime('now')));"
    )


def _inserir_sinal(conn, tipo: str, lugar, quando: str):
    conn.execute("INSERT INTO sinais (tipo, lugar, quando) VALUES (?, ?, ?)", (tipo, lugar, quando))
    conn.commit()


class TestAvaliarSinalIphone(Base):
    def test_tabela_ausente_nao_quebra(self):
        # A faixa P7 (que grava os sinais) pode nao ter rodado ainda -
        # `sinais` nem existe, e assistente.sinais pode nao estar instalado.
        # Nunca deve levantar.
        cond = {"tipo": "cheguei", "lugar": "casa"}
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 18, 0), None)
        self.assertFalse(deve)
        self.assertIsNone(sinal)

    def test_com_tabela_e_sinal_novo_dispara(self):
        _criar_tabela_sinais(self.conn)
        _inserir_sinal(self.conn, "cheguei", "trabalho", "2026-09-24T08:05:00")
        cond = {"tipo": "cheguei", "lugar": "trabalho"}
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 8, 10), None)
        self.assertTrue(deve)
        self.assertEqual(sinal["lugar"], "trabalho")

    def test_sinal_antigo_nao_dispara_de_novo(self):
        _criar_tabela_sinais(self.conn)
        _inserir_sinal(self.conn, "cheguei", "trabalho", "2026-09-24T08:05:00")
        cond = {"tipo": "cheguei", "lugar": "trabalho"}
        ultima_vez = datetime(2026, 9, 24, 8, 6)  # depois do sinal
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 9, 0), ultima_vez)
        self.assertFalse(deve)

    def test_tipo_diferente_nao_bate(self):
        _criar_tabela_sinais(self.conn)
        _inserir_sinal(self.conn, "sai", "trabalho", "2026-09-24T08:05:00")
        cond = {"tipo": "cheguei"}
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 9, 0), None)
        self.assertFalse(deve)

    def test_sem_lugar_na_condicao_aceita_qualquer_lugar(self):
        _criar_tabela_sinais(self.conn)
        _inserir_sinal(self.conn, "acordei", None, "2026-09-24T07:00:00")
        cond = {"tipo": "acordei"}
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 7, 5), None)
        self.assertTrue(deve)

    def test_usa_assistente_sinais_quando_disponivel(self):
        # assistente.sinais (faixa P7) ja esta na integracao - confirma que
        # o caminho "feliz" (import funciona) tambem bate.
        import assistente.sinais  # so garante que o modulo existe/importa

        _criar_tabela_sinais(self.conn)
        _inserir_sinal(self.conn, "carregando", None, "2026-09-24T23:00:00")
        cond = {"tipo": "carregando"}
        deve, sinal = motor.avaliar_sinal_iphone(self.conn, cond, datetime(2026, 9, 24, 23, 1), None)
        self.assertTrue(deve)
        self.assertEqual(sinal["tipo"], "carregando")


# ---------------------------------------------------------------------------
# avaliar_regra (dispatcher) - so garante que cada gatilho devolve
# (deve_disparar, mensagem nao vazia, detalhe com titulo/janela) quando bate.
# ---------------------------------------------------------------------------

class TestAvaliarRegraDispatcher(Base):
    def test_gatilho_desconhecido_levanta(self):
        with self.assertRaises(ValueError):
            motor.avaliar_regra(self.conn, {"gatilho": "chute", "condicao": {}, "acao": {}},
                                 datetime(2026, 9, 24, 12, 0), None)

    def test_horario_dispara_com_mensagem_e_detalhe(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "08:00"},
                 "acao": {"mensagem": "tomar remedio"}, "texto": "x"}
        deve, mensagem, detalhe = motor.avaliar_regra(self.conn, regra, datetime(2026, 9, 24, 8, 5), None)
        self.assertTrue(deve)
        self.assertEqual(mensagem, "tomar remedio")
        self.assertEqual(detalhe["janela"], "2026-09-24")

    def test_gasto_categoria_mensagem_cita_valores(self):
        _inserir_gasto(self.conn, "mercado", 400.0, "2026-09-22 10:00:00")
        regra = {"gatilho": "gasto_categoria",
                 "condicao": {"categoria": "mercado", "periodo": "semana", "valor_limite": 300.0},
                 "acao": {}, "texto": "x"}
        deve, mensagem, detalhe = motor.avaliar_regra(self.conn, regra, datetime(2026, 9, 24, 12, 0), None)
        self.assertTrue(deve)
        self.assertIn("400.00", mensagem)
        self.assertIn("300.00", mensagem)

    def test_nao_dispara_devolve_vazio(self):
        regra = {"gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "x"}
        deve, mensagem, detalhe = motor.avaliar_regra(self.conn, regra, datetime(2026, 9, 24, 12, 0), None)
        self.assertFalse(deve)
        self.assertEqual(mensagem, "")
        self.assertEqual(detalhe, {})


# ---------------------------------------------------------------------------
# assistente/gatilhos/p4_regras.py:executar - integracao com a tabela
# p4_regras + enfileirar (mockado) + idempotencia + pausa.
# ---------------------------------------------------------------------------

class TestGatilhoExecutar(Base):
    def _mock_enfileirar(self):
        return patch("assistente.gatilhos.p4_regras._enfileirar")

    def test_tabela_ausente_nao_quebra(self):
        conn_sem_tabela = sqlite3.connect(":memory:")
        conn_sem_tabela.row_factory = sqlite3.Row
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(conn_sem_tabela, datetime(2026, 9, 24, 18, 0))
        mock_enf.assert_not_called()
        conn_sem_tabela.close()

    def test_regra_diaria_dispara_e_enfileira(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "tomar o remedio"}, "texto": "todo dia as 18h tomar o remedio"}
        regra_id = _inserir_regra(self.conn, regra)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 5))
        mock_enf.assert_called_once()
        args, kwargs = mock_enf.call_args
        self.assertEqual(args[0], "aviso")
        self.assertEqual(kwargs["origem"], f"p4_regras:{regra_id}")
        self.assertIn(f"p4_regras:{regra_id}:", kwargs["chave_unica"])

        linha = self.conn.execute("SELECT ultima_vez FROM p4_regras WHERE id = ?", (regra_id,)).fetchone()
        self.assertIsNotNone(linha["ultima_vez"])

    def test_regra_inativa_e_ignorada(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra, ativa=0)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 5))
        mock_enf.assert_not_called()

    def test_regra_pausada_e_ignorada(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra, pausada_ate="2026-10-01 00:00:00")
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 5))
        mock_enf.assert_not_called()

    def test_regra_pausada_no_passado_dispara_normal(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra, pausada_ate="2026-09-01 00:00:00")  # ja passou
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 5))
        mock_enf.assert_called_once()

    def test_idempotente_2_ticks_no_mesmo_dia_so_dispara_1x(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 0))
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 1))
            gatilho.executar(self.conn, datetime(2026, 9, 24, 20, 0))
        self.assertEqual(mock_enf.call_count, 1)

    def test_dispara_de_novo_no_dia_seguinte(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 0))
            gatilho.executar(self.conn, datetime(2026, 9, 25, 18, 0))
        self.assertEqual(mock_enf.call_count, 2)

    def test_regra_de_data_unica_e_desativada_apos_disparar(self):
        regra = {"gatilho": "horario", "condicao": {"tipo": "data", "data": "2026-12-25", "hora": "09:00"},
                 "acao": {"mensagem": "feliz natal"}, "texto": "x"}
        regra_id = _inserir_regra(self.conn, regra)
        with self._mock_enfileirar():
            gatilho.executar(self.conn, datetime(2026, 12, 25, 9, 30))
        linha = self.conn.execute("SELECT ativa FROM p4_regras WHERE id = ?", (regra_id,)).fetchone()
        self.assertEqual(linha["ativa"], 0)

    def test_json_invalido_e_ignorado_sem_quebrar(self):
        self.conn.execute(
            "INSERT INTO p4_regras (texto_original, json, ativa) VALUES (?, ?, 1)",
            ("x", "isso nao e json"),
        )
        self.conn.commit()
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 0))  # nao deve levantar
        mock_enf.assert_not_called()

    def test_uma_regra_com_erro_nao_impede_as_outras(self):
        regra_ok = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "08:00"},
                    "acao": {"mensagem": "ok"}, "texto": "x"}
        _inserir_regra(self.conn, {"gatilho_sem_sentido": True}, ativa=1)  # vira json valido, gatilho invalido
        _inserir_regra(self.conn, regra_ok)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 24, 8, 5))
        mock_enf.assert_called_once()  # a regra ok disparou apesar da quebrada

    def test_gasto_categoria_idempotente_por_semana(self):
        _inserir_gasto(self.conn, "mercado", 400.0, "2026-09-22 10:00:00")
        regra = {"gatilho": "gasto_categoria",
                 "condicao": {"categoria": "mercado", "periodo": "semana", "valor_limite": 300.0},
                 "acao": {}, "texto": "x"}
        _inserir_regra(self.conn, regra)
        with self._mock_enfileirar() as mock_enf:
            gatilho.executar(self.conn, datetime(2026, 9, 23, 9, 0))
            gatilho.executar(self.conn, datetime(2026, 9, 24, 9, 0))  # mesma semana
        self.assertEqual(mock_enf.call_count, 1)

        with self._mock_enfileirar() as mock_enf2:
            _inserir_gasto(self.conn, "mercado", 400.0, "2026-09-29 10:00:00")
            gatilho.executar(self.conn, datetime(2026, 9, 29, 9, 0))  # semana seguinte
        self.assertEqual(mock_enf2.call_count, 1)

    def test_usa_stub_do_contrato_quando_caixa_nao_existe(self):
        # assistente.caixa (faixa P1a) ainda nao existe neste branch -
        # _enfileirar precisa cair no stub de assistente/contrato.py, que
        # levanta NotImplementedError (nunca falha silenciosamente).
        regra = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
                 "acao": {"mensagem": "x"}, "texto": "x"}
        _inserir_regra(self.conn, regra)
        # sem mock nenhum - exercita o import tardio de verdade
        gatilho.executar(self.conn, datetime(2026, 9, 24, 18, 0))
        # NotImplementedError e engolido pelo try/except de _processar_regra
        # (uma regra com problema nao derruba o tick) - so confirmamos que
        # nao propagou e que ultima_vez NAO foi gravado (o disparo falhou).
        linha = self.conn.execute("SELECT ultima_vez FROM p4_regras WHERE ativa = 1").fetchone()
        self.assertIsNone(linha["ultima_vez"])


if __name__ == "__main__":
    unittest.main()
