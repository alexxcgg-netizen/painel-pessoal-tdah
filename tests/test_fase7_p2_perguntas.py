"""Fase 7, faixa P2 (Perguntas de acompanhamento).

Cobre assistente/perguntas.py (logica pura) e
assistente/gatilhos/p2_perguntas.py (executar/ao_resolver).
`assistente.contrato.enfileirar` (implementado na faixa P1a) ainda nao
existe nesta integracao, entao e mockado com `unittest.mock.patch` (o
gatilho importa de forma tardia, dentro da funcao, como
`assistente/gatilhos/__init__.py` manda) - nenhuma chamada real de API,
nenhum credential real. Relogio sempre injetado (`agora`/`hoje` por
parametro), nunca a hora real."""

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import assistente.contrato  # noqa: E402
from assistente import perguntas  # noqa: E402
from assistente.gatilhos import p2_perguntas as gatilho  # noqa: E402

HOJE = date(2026, 9, 24)
AGORA = datetime(2026, 9, 24, 12, 0)


class _FakeContrato:
    """Substitui assistente.contrato.enfileirar: reproduz o unico
    comportamento do contrato que interessa aqui - chave_unica repetida
    nao vira item novo."""

    def __init__(self):
        self.criados = {}
        self.chamadas = []
        self.enfileirar = MagicMock(side_effect=self._enfileirar)

    def _enfileirar(self, *, chave_unica="", **kwargs):
        self.chamadas.append({"chave_unica": chave_unica, **kwargs})
        if chave_unica and chave_unica in self.criados:
            return self.criados[chave_unica]
        item_id = f"item-{len(self.criados) + 1}"
        self.criados[chave_unica or item_id] = item_id
        return item_id


# ---------------------------------------------------------------------------
# Logica pura (assistente/perguntas.py) - sem banco, sem relogio real.
# ---------------------------------------------------------------------------


class EhRelacionamentoTestCase(unittest.TestCase):
    def test_bloqueia_namorada(self):
        self.assertTrue(perguntas.eh_relacionamento("Jantar com a namorada"))

    def test_bloqueia_sem_acento_maiuscula(self):
        self.assertTrue(perguntas.eh_relacionamento("ENCONTRO ROMANTICO no sabado"))

    def test_bloqueia_aniversario_de_namoro(self):
        self.assertTrue(perguntas.eh_relacionamento("Aniversario de namoro"))

    def test_nao_bloqueia_reuniao_normal(self):
        self.assertFalse(perguntas.eh_relacionamento("Reuniao com o fornecedor"))

    def test_nao_bloqueia_aniversario_comum(self):
        self.assertFalse(perguntas.eh_relacionamento("Aniversario da Maria"))

    def test_texto_vazio_ou_none(self):
        self.assertFalse(perguntas.eh_relacionamento(""))
        self.assertFalse(perguntas.eh_relacionamento(None))


class TextosPerguntaTestCase(unittest.TestCase):
    def test_conta(self):
        self.assertEqual(perguntas.texto_pergunta_conta("Internet"), 'Pagou "Internet"?')

    def test_evento(self):
        self.assertEqual(
            perguntas.texto_pergunta_evento("Reuniao com fornecedor"),
            'Como foi "Reuniao com fornecedor"? Algo a anotar?',
        )

    def test_tarefa(self):
        self.assertEqual(perguntas.texto_pergunta_tarefa("Ligar pro banco"), 'Fez "Ligar pro banco"?')

    def test_espera(self):
        self.assertEqual(
            perguntas.texto_pergunta_espera("fornecedor X", "orcamento do telhado"),
            'Ainda esperando fornecedor X sobre "orcamento do telhado"?',
        )


class ParseDataLivreTestCase(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(perguntas.parse_data_livre("2026-10-05", HOJE), date(2026, 10, 5))

    def test_br_barra(self):
        self.assertEqual(perguntas.parse_data_livre("05/10/2026", HOJE), date(2026, 10, 5))

    def test_br_traco(self):
        self.assertEqual(perguntas.parse_data_livre("05-10-2026", HOJE), date(2026, 10, 5))

    def test_dia_mes_sem_ano_futuro(self):
        self.assertEqual(perguntas.parse_data_livre("05/10", HOJE), date(2026, 10, 5))

    def test_dia_mes_sem_ano_ja_passou_pula_pro_ano_seguinte(self):
        self.assertEqual(perguntas.parse_data_livre("01/01", HOJE), date(2027, 1, 1))

    def test_invalida(self):
        self.assertIsNone(perguntas.parse_data_livre("nao sei", HOJE))

    def test_vazia(self):
        self.assertIsNone(perguntas.parse_data_livre("", HOJE))
        self.assertIsNone(perguntas.parse_data_livre(None, HOJE))


class DataAdiarTarefaTestCase(unittest.TestCase):
    def test_amanha(self):
        self.assertEqual(perguntas.data_adiar_tarefa("amanha", HOJE), date(2026, 9, 25))

    def test_proxima_semana(self):
        self.assertEqual(perguntas.data_adiar_tarefa("proxima_semana", HOJE), date(2026, 10, 1))

    def test_escolher_data_valida(self):
        self.assertEqual(
            perguntas.data_adiar_tarefa("escolher_data", HOJE, "10/10/2026"), date(2026, 10, 10)
        )

    def test_escolher_data_invalida(self):
        self.assertIsNone(perguntas.data_adiar_tarefa("escolher_data", HOJE, "quinta-feira"))

    def test_adiar_generico(self):
        self.assertEqual(perguntas.data_adiar_tarefa("adiar", HOJE), date(2026, 9, 25))

    def test_opcao_desconhecida(self):
        self.assertIsNone(perguntas.data_adiar_tarefa("sei_la", HOJE))


class LimiarEsperaDiasTestCase(unittest.TestCase):
    def test_none_usa_padrao(self):
        self.assertEqual(perguntas.limiar_espera_dias(None), 3)

    def test_valor_valido(self):
        self.assertEqual(perguntas.limiar_espera_dias("5"), 5)

    def test_valor_invalido_usa_padrao(self):
        self.assertEqual(perguntas.limiar_espera_dias("abc"), 3)

    def test_valor_zero_ou_negativo_usa_padrao(self):
        self.assertEqual(perguntas.limiar_espera_dias("0"), 3)
        self.assertEqual(perguntas.limiar_espera_dias("-2"), 3)

    def test_padrao_customizado(self):
        self.assertEqual(perguntas.limiar_espera_dias(None, padrao=7), 7)


class FlagAtivaTestCase(unittest.TestCase):
    def test_none_e_ativo(self):
        self.assertTrue(perguntas.flag_ativa(None))

    def test_zero_desliga(self):
        self.assertFalse(perguntas.flag_ativa("0"))

    def test_false_desliga(self):
        self.assertFalse(perguntas.flag_ativa("false"))

    def test_qualquer_outra_coisa_liga(self):
        self.assertTrue(perguntas.flag_ativa("1"))
        self.assertTrue(perguntas.flag_ativa("ligado"))


# ---------------------------------------------------------------------------
# Gatilho (banco real em arquivo temporario, enfileirar mockado).
# ---------------------------------------------------------------------------


class GatilhoTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.fake_contrato = _FakeContrato()
        self._patch_enfileirar = patch.object(
            assistente.contrato, "enfileirar", self.fake_contrato.enfileirar
        )
        self._patch_enfileirar.start()
        self._patch_caldav = patch("caldav_client.configurado", return_value=False)
        self._patch_caldav.start()

    def tearDown(self):
        self._patch_caldav.stop()
        self._patch_enfileirar.stop()
        self.conn.close()

    # -- conta pessoal --------------------------------------------------

    def test_conta_pessoal_pergunta_no_dia_do_vencimento(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()
        chamada = self.fake_contrato.chamadas[0]
        self.assertEqual(chamada["titulo"], 'Pagou "Internet"?')
        self.assertEqual(chamada["opcoes"], ["sim", "ainda_nao", "adiar"])
        self.assertEqual(chamada["chave_unica"], f"p2_perguntas:conta:{conta_id}:{HOJE.isoformat()}")
        self.assertTrue(chamada["origem"].startswith("p2_perguntas:"))

    def test_conta_pessoal_nao_pergunta_fora_do_dia(self):
        outro_dia = 5 if HOJE.day != 5 else 6
        db.create_conta_pessoal(self.conn, "Internet", outro_dia)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_conta_pessoal_nao_pergunta_se_ja_paga(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        db.marcar_conta_paga(self.conn, conta_id, HOJE.isoformat())
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_conta_pessoal_nao_duplica_em_dois_ticks(self):
        db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        gatilho.executar(self.conn, AGORA)
        gatilho.executar(self.conn, AGORA)
        self.assertEqual(self.fake_contrato.enfileirar.call_count, 2)
        self.assertEqual(len(self.fake_contrato.criados), 1)

    def test_conta_pessoal_relacionamento_nao_pergunta(self):
        db.create_conta_pessoal(self.conn, "Presente pra namorada", HOJE.day)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_resolver_conta_sim_marca_paga(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        item = {"origem": f"p2_perguntas:conta:{conta_id}:{HOJE.isoformat()}"}
        gatilho.ao_resolver(self.conn, item, "sim", "", agora=AGORA)
        self.assertTrue(db.conta_paga(self.conn, conta_id, HOJE.isoformat()))

    def test_resolver_conta_ainda_nao_nao_marca(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        item = {"origem": f"p2_perguntas:conta:{conta_id}:{HOJE.isoformat()}"}
        gatilho.ao_resolver(self.conn, item, "ainda_nao", "", agora=AGORA)
        self.assertFalse(db.conta_paga(self.conn, conta_id, HOJE.isoformat()))

    def test_resolver_conta_adiar_nao_marca(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        item = {"origem": f"p2_perguntas:conta:{conta_id}:{HOJE.isoformat()}"}
        gatilho.ao_resolver(self.conn, item, "adiar", "", agora=AGORA)
        self.assertFalse(db.conta_paga(self.conn, conta_id, HOJE.isoformat()))

    # -- evento/reuniao ---------------------------------------------------

    def _evento(self, titulo, inicio, fim, dia_inteiro=False):
        return {"titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat(), "dia_inteiro": dia_inteiro}

    def test_evento_terminado_pergunta(self):
        evento = self._evento(
            "Reuniao com fornecedor", datetime(2026, 9, 24, 9, 0), datetime(2026, 9, 24, 10, 0)
        )
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=[evento]
        ):
            gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()
        chamada = self.fake_contrato.chamadas[0]
        self.assertEqual(chamada["titulo"], 'Como foi "Reuniao com fornecedor"? Algo a anotar?')
        self.assertEqual(chamada["opcoes"], ["anotar", "nada"])
        self.assertEqual(chamada["corpo"], "Reuniao com fornecedor")

    def test_evento_ainda_nao_terminou_nao_pergunta(self):
        evento = self._evento(
            "Reuniao com fornecedor", datetime(2026, 9, 24, 11, 30), datetime(2026, 9, 24, 13, 0)
        )
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=[evento]
        ):
            gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_evento_dia_inteiro_nao_pergunta(self):
        evento = self._evento(
            "Feriado", datetime(2026, 9, 24, 0, 0), datetime(2026, 9, 24, 23, 59), dia_inteiro=True
        )
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=[evento]
        ):
            gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_evento_relacionamento_nao_pergunta(self):
        evento = self._evento(
            "Jantar romantico", datetime(2026, 9, 24, 9, 0), datetime(2026, 9, 24, 10, 0)
        )
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=[evento]
        ):
            gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_caldav_nao_configurado_nao_quebra(self):
        gatilho.executar(self.conn, AGORA)  # caldav_client.configurado() mockado False no setUp
        self.fake_contrato.enfileirar.assert_not_called()

    def test_caldav_com_erro_nao_quebra_o_tick(self):
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", side_effect=RuntimeError("iCloud fora do ar")
        ):
            gatilho.executar(self.conn, AGORA)  # nao deve levantar
        self.fake_contrato.enfileirar.assert_not_called()

    def test_resolver_evento_anotar_cria_nota(self):
        item = {"origem": f"p2_perguntas:evento:{123}:{HOJE.isoformat()}", "corpo": "Reuniao com fornecedor"}
        gatilho.ao_resolver(self.conn, item, "anotar", "Fechou o preco do telhado", agora=AGORA)
        notas = db.buscar_notas(self.conn, "telhado")
        self.assertEqual(len(notas), 1)
        self.assertIn("Reuniao com fornecedor", notas[0]["titulo"])

    def test_resolver_evento_nada_nao_cria_nota(self):
        item = {"origem": f"p2_perguntas:evento:{123}:{HOJE.isoformat()}", "corpo": "Reuniao com fornecedor"}
        gatilho.ao_resolver(self.conn, item, "nada", "", agora=AGORA)
        self.assertEqual(db.list_notas(self.conn), [])

    def test_resolver_evento_anotar_sem_texto_nao_cria_nota(self):
        item = {"origem": f"p2_perguntas:evento:{123}:{HOJE.isoformat()}", "corpo": "Reuniao com fornecedor"}
        gatilho.ao_resolver(self.conn, item, "anotar", "   ", agora=AGORA)
        self.assertEqual(db.list_notas(self.conn), [])

    def test_resolver_evento_anotar_relacionamento_nao_cria_nota(self):
        item = {"origem": f"p2_perguntas:evento:{123}:{HOJE.isoformat()}", "corpo": "Jantar romantico"}
        gatilho.ao_resolver(self.conn, item, "anotar", "foi otimo", agora=AGORA)
        self.assertEqual(db.list_notas(self.conn), [])

    # -- tarefa com prazo vencido -------------------------------------------

    def _criar_tarefa(self, titulo, due_date):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date) VALUES (?, ?)", (titulo, due_date.isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def test_tarefa_vencida_pergunta(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()
        chamada = self.fake_contrato.chamadas[0]
        self.assertEqual(chamada["titulo"], 'Fez "Ligar pro banco"?')
        self.assertEqual(chamada["opcoes"], ["sim", "amanha", "proxima_semana", "escolher_data"])
        self.assertEqual(chamada["chave_unica"], f"p2_perguntas:tarefa:{task_id}:2026-09-20")

    def test_tarefa_com_prazo_hoje_nao_e_vencida(self):
        self._criar_tarefa("Ligar pro banco", HOJE)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_tarefa_concluida_nao_pergunta(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        db.complete_task(self.conn, task_id)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_tarefa_relacionamento_nao_pergunta(self):
        self._criar_tarefa("Comprar presente pra namorada", date(2026, 9, 20))
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_resolver_tarefa_sim_conclui(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        item = {"origem": f"p2_perguntas:tarefa:{task_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "sim", "", agora=AGORA)
        row = self.conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertIsNotNone(row["completed_at"])

    def test_resolver_tarefa_amanha_adia(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        item = {"origem": f"p2_perguntas:tarefa:{task_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "amanha", "", agora=AGORA)
        row = self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertEqual(row["due_date"], "2026-09-25")

    def test_resolver_tarefa_proxima_semana_adia(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        item = {"origem": f"p2_perguntas:tarefa:{task_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "proxima_semana", "", agora=AGORA)
        row = self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertEqual(row["due_date"], "2026-10-01")

    def test_resolver_tarefa_escolher_data_valida(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        item = {"origem": f"p2_perguntas:tarefa:{task_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "escolher_data", "10/10/2026", agora=AGORA)
        row = self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertEqual(row["due_date"], "2026-10-10")

    def test_resolver_tarefa_escolher_data_invalida_nao_altera(self):
        task_id = self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        item = {"origem": f"p2_perguntas:tarefa:{task_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "escolher_data", "sei la quando", agora=AGORA)
        row = self.conn.execute("SELECT due_date FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self.assertEqual(row["due_date"], "2026-09-20")

    # -- lembrete -------------------------------------------------------

    def test_lembrete_unico_vencido_pergunta(self):
        lembrete_id = db.create_lembrete(self.conn, "Renovar seguro do carro", "2026-09-20")
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()
        chamada = self.fake_contrato.chamadas[0]
        self.assertEqual(chamada["opcoes"], ["feito", "adiar"])
        self.assertEqual(chamada["chave_unica"], f"p2_perguntas:lembrete:{lembrete_id}:2026-09-20")

    def test_lembrete_futuro_nao_pergunta(self):
        db.create_lembrete(self.conn, "Renovar seguro do carro", "2026-10-20")
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_lembrete_recorrente_pergunta_so_no_dia(self):
        db.create_lembrete(self.conn, "Renovar CRLV", "2020-09-24", recorrente=True)
        gatilho.executar(self.conn, AGORA)  # AGORA = 2026-09-24
        self.fake_contrato.enfileirar.assert_called_once()

    def test_lembrete_recorrente_nao_pergunta_no_dia_seguinte(self):
        db.create_lembrete(self.conn, "Renovar CRLV", "2020-09-24", recorrente=True)
        gatilho.executar(self.conn, datetime(2026, 9, 25, 12, 0))
        self.fake_contrato.enfileirar.assert_not_called()

    def test_lembrete_relacionamento_nao_pergunta(self):
        db.create_lembrete(self.conn, "Aniversario de namoro", "2026-09-20")
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_resolver_lembrete_feito_nao_recorrente_apaga(self):
        lembrete_id = db.create_lembrete(self.conn, "Renovar seguro", "2026-09-20")
        item = {"origem": f"p2_perguntas:lembrete:{lembrete_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "feito", "", agora=AGORA)
        self.assertEqual(
            self.conn.execute("SELECT 1 FROM lembretes WHERE id = ?", (lembrete_id,)).fetchone(), None
        )

    def test_resolver_lembrete_feito_recorrente_mantem(self):
        lembrete_id = db.create_lembrete(self.conn, "Renovar CRLV", "2020-09-24", recorrente=True)
        item = {"origem": f"p2_perguntas:lembrete:{lembrete_id}:2026-09-24"}
        gatilho.ao_resolver(self.conn, item, "feito", "", agora=AGORA)
        self.assertIsNotNone(
            self.conn.execute("SELECT 1 FROM lembretes WHERE id = ?", (lembrete_id,)).fetchone()
        )

    def test_resolver_lembrete_adiar_empurra_um_dia(self):
        lembrete_id = db.create_lembrete(self.conn, "Renovar seguro", "2026-09-20")
        item = {"origem": f"p2_perguntas:lembrete:{lembrete_id}:2026-09-20"}
        gatilho.ao_resolver(self.conn, item, "adiar", "", agora=AGORA)
        row = self.conn.execute("SELECT data FROM lembretes WHERE id = ?", (lembrete_id,)).fetchone()
        self.assertEqual(row["data"], "2026-09-25")

    # -- espera (esperando resposta de X) --------------------------------

    def test_espera_parada_ha_3_dias_pergunta(self):
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        self.conn.execute(
            "UPDATE esperas SET criado_em = ? WHERE id = ?", ("2026-09-21 10:00:00", espera_id)
        )
        self.conn.commit()
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()
        chamada = self.fake_contrato.chamadas[0]
        self.assertEqual(
            chamada["titulo"], 'Ainda esperando Fornecedor X sobre "orcamento do telhado"?'
        )
        self.assertEqual(chamada["opcoes"], ["cobrar", "ja_respondeu", "adiar"])

    def test_espera_recente_nao_pergunta(self):
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        self.conn.execute(
            "UPDATE esperas SET criado_em = ? WHERE id = ?", ("2026-09-23 10:00:00", espera_id)
        )
        self.conn.commit()
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_espera_limiar_configuravel(self):
        db.definir_configuracao(self.conn, gatilho.CONFIG_ESPERA_DIAS, "5")
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        self.conn.execute(
            "UPDATE esperas SET criado_em = ? WHERE id = ?", ("2026-09-21 10:00:00", espera_id)
        )
        self.conn.commit()
        gatilho.executar(self.conn, AGORA)  # 3 dias corridos, limiar 5 -> nao pergunta ainda
        self.fake_contrato.enfileirar.assert_not_called()

    def test_espera_resolvida_nao_pergunta(self):
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        self.conn.execute(
            "UPDATE esperas SET criado_em = ? WHERE id = ?", ("2026-09-21 10:00:00", espera_id)
        )
        db.resolver_espera(self.conn, espera_id)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_espera_relacionamento_nao_pergunta(self):
        db.create_espera(self.conn, "Namorada", "confirmar o jantar")
        self.conn.execute("UPDATE esperas SET criado_em = ?", ("2026-09-21 10:00:00",))
        self.conn.commit()
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_resolver_espera_ja_respondeu_resolve(self):
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        item = {"origem": f"p2_perguntas:espera:{espera_id}:2026-09-21"}
        gatilho.ao_resolver(self.conn, item, "ja_respondeu", "", agora=AGORA)
        pendentes = [e["id"] for e in db.list_esperas_pendentes(self.conn)]
        self.assertNotIn(espera_id, pendentes)

    def test_resolver_espera_cobrar_continua_pendente(self):
        espera_id = db.create_espera(self.conn, "Fornecedor X", "orcamento do telhado")
        item = {"origem": f"p2_perguntas:espera:{espera_id}:2026-09-21"}
        gatilho.ao_resolver(self.conn, item, "cobrar", "", agora=AGORA)
        pendentes = [e["id"] for e in db.list_esperas_pendentes(self.conn)]
        self.assertIn(espera_id, pendentes)

    # -- flag geral -------------------------------------------------------

    def test_flag_desligada_nao_pergunta_nada(self):
        db.definir_configuracao(self.conn, gatilho.FLAG_ATIVO, "0")
        db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        self._criar_tarefa("Ligar pro banco", date(2026, 9, 20))
        db.create_lembrete(self.conn, "Renovar seguro", "2026-09-20")
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_not_called()

    def test_flag_none_e_ativa_por_padrao(self):
        db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        gatilho.executar(self.conn, AGORA)
        self.fake_contrato.enfileirar.assert_called_once()

    # -- ao_resolver com origem invalida nao derruba nada ------------------

    def test_ao_resolver_origem_vazia_nao_quebra(self):
        gatilho.ao_resolver(self.conn, {"origem": ""}, "sim", "", agora=AGORA)

    def test_ao_resolver_id_nao_numerico_nao_quebra(self):
        gatilho.ao_resolver(self.conn, {"origem": "p2_perguntas:conta:abc:2026-09-24"}, "sim", "", agora=AGORA)

    def test_ao_resolver_item_como_row_sqlite(self):
        conta_id = db.create_conta_pessoal(self.conn, "Internet", HOJE.day)
        row = self.conn.execute(
            "SELECT id AS origem_fake FROM contas_pessoais WHERE id = ?", (conta_id,)
        ).fetchone()
        # sqlite3.Row se comporta como mapping (dict(row) funciona) - simula
        # o formato real que a P1a deve passar.
        item_dict = {"origem": f"p2_perguntas:conta:{conta_id}:{HOJE.isoformat()}"}
        gatilho.ao_resolver(self.conn, item_dict, "sim", "", agora=AGORA)
        self.assertTrue(db.conta_paga(self.conn, conta_id, HOJE.isoformat()))
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
