"""Faixa P3 (briefing) - testes de assistente/gatilhos/p3_briefing.py:
executar(conn, agora) com relogio sempre injetado (nunca datetime.now()), e
ao_resolver. `assistente.caixa` ainda nao existe neste repo (e da faixa
P1a) - os testes instalam um modulo falso em sys.modules antes de chamar
executar(), exatamente como a faixa P3 vai rodar de verdade contra a P1a
(so que aqui com um duble no lugar do enfileirar real)."""

import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (so pra garantir que o app carrega no ambiente de teste)

from assistente import briefing  # noqa: E402
from assistente.gatilhos import p3_briefing  # noqa: E402

assert app  # usado so pra nao sobrar import "nao usado" pro linter


_SENTINELA = object()
_caixa_original: list = []  # vazio = nada instalado; [modulo ou _SENTINELA] = instalado


def _instalar_caixa_falsa():
    """Sobe um modulo assistente.caixa falso em sys.modules, com enfileirar
    mockado (isola o gatilho da Caixa real da P1a)."""
    if not _caixa_original:
        _caixa_original.append(sys.modules.get("assistente.caixa", _SENTINELA))
    modulo = types.ModuleType("assistente.caixa")
    modulo.enfileirar = MagicMock(return_value="item-fake-id")
    sys.modules["assistente.caixa"] = modulo
    return modulo.enfileirar


def _remover_caixa_falsa():
    """C1: devolve o modulo REAL que estava la (antes so fazia pop - o
    proximo import criava um 2o objeto assistente.caixa, e os patch() de
    tests/test_fase7_p1a_caixa.py passavam a mirar o objeto errado quando
    os dois arquivos rodavam no mesmo processo, nessa ordem). Chamar 2x
    (no meio do teste e no tearDown) e seguro."""
    if not _caixa_original:
        return
    original = _caixa_original.pop()
    if original is _SENTINELA:
        sys.modules.pop("assistente.caixa", None)
    else:
        sys.modules["assistente.caixa"] = original


class JanelaTestCase(unittest.TestCase):
    def test_dentro_da_janela_no_minuto_exato(self):
        agora = datetime(2026, 6, 15, 7, 30, 0)
        self.assertTrue(p3_briefing._dentro_da_janela(agora, "07:30"))

    def test_dentro_da_janela_alguns_minutos_depois(self):
        agora = datetime(2026, 6, 15, 7, 34, 59)
        self.assertTrue(p3_briefing._dentro_da_janela(agora, "07:30"))

    def test_fora_da_janela_depois(self):
        agora = datetime(2026, 6, 15, 7, 35, 0)
        self.assertFalse(p3_briefing._dentro_da_janela(agora, "07:30"))

    def test_fora_da_janela_antes(self):
        agora = datetime(2026, 6, 15, 7, 29, 59)
        self.assertFalse(p3_briefing._dentro_da_janela(agora, "07:30"))

    def test_horario_invalido_nunca_dispara(self):
        agora = datetime(2026, 6, 15, 7, 30, 0)
        self.assertFalse(p3_briefing._dentro_da_janela(agora, "abc"))
        self.assertFalse(p3_briefing._dentro_da_janela(agora, ""))
        self.assertFalse(p3_briefing._dentro_da_janela(agora, None))


class ExecutarTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()
        self.enfileirar = _instalar_caixa_falsa()

    def tearDown(self):
        self.conn.close()
        _remover_caixa_falsa()

    def test_dispara_manha_na_janela_padrao(self):
        agora = datetime(2026, 6, 15, 7, 30, 0)
        p3_briefing.executar(self.conn, agora)

        chamadas = self.enfileirar.call_args_list
        self.assertEqual(len(chamadas), 1)
        kwargs = chamadas[0].kwargs
        self.assertEqual(kwargs["tipo"], "briefing")
        self.assertEqual(kwargs["chave_unica"], "p3_manha:2026-06-15")
        self.assertEqual(kwargs["origem"], "p3_briefing:manha:2026-06-15")
        self.assertEqual(kwargs["titulo"], "Bom dia")

    def test_dispara_noite_na_janela_padrao_com_opcoes(self):
        agora = datetime(2026, 6, 15, 21, 2, 0)
        p3_briefing.executar(self.conn, agora)

        chamadas = self.enfileirar.call_args_list
        self.assertEqual(len(chamadas), 1)
        kwargs = chamadas[0].kwargs
        self.assertEqual(kwargs["chave_unica"], "p3_noite:2026-06-15")
        self.assertEqual(kwargs["origem"], "p3_briefing:noite:2026-06-15")
        self.assertEqual(kwargs["opcoes"], briefing.OPCOES_FECHAMENTO)

    def test_nao_dispara_fora_de_qualquer_janela(self):
        agora = datetime(2026, 6, 15, 12, 0, 0)
        p3_briefing.executar(self.conn, agora)
        self.enfileirar.assert_not_called()

    def test_nao_dispara_2x_mesmo_tick_rodando_duas_vezes(self):
        # A P1a dedup por chave_unica (contrato); aqui a gente garante que o
        # gatilho sempre manda a MESMA chave_unica pro mesmo dia/janela,
        # condicao necessaria pro dedup dela funcionar.
        agora = datetime(2026, 6, 15, 7, 31, 0)
        p3_briefing.executar(self.conn, agora)
        p3_briefing.executar(self.conn, agora)

        self.assertEqual(self.enfileirar.call_count, 2)
        chave1 = self.enfileirar.call_args_list[0].kwargs["chave_unica"]
        chave2 = self.enfileirar.call_args_list[1].kwargs["chave_unica"]
        self.assertEqual(chave1, chave2)

    def test_virada_de_dia_muda_a_chave(self):
        p3_briefing.executar(self.conn, datetime(2026, 6, 15, 7, 30, 0))
        p3_briefing.executar(self.conn, datetime(2026, 6, 16, 7, 30, 0))

        chave1 = self.enfileirar.call_args_list[0].kwargs["chave_unica"]
        chave2 = self.enfileirar.call_args_list[1].kwargs["chave_unica"]
        self.assertNotEqual(chave1, chave2)
        self.assertEqual(chave1, "p3_manha:2026-06-15")
        self.assertEqual(chave2, "p3_manha:2026-06-16")

    def test_horario_editado_muda_a_janela(self):
        briefing.definir_horario_manha(self.conn, "08:15")

        # O horario antigo (padrao) nao dispara mais.
        p3_briefing.executar(self.conn, datetime(2026, 6, 15, 7, 30, 0))
        self.enfileirar.assert_not_called()

        # O novo horario dispara.
        p3_briefing.executar(self.conn, datetime(2026, 6, 15, 8, 15, 0))
        self.enfileirar.assert_called_once()

    def test_flag_desativada_nao_dispara_nem_importa_caixa(self):
        db.definir_configuracao(self.conn, briefing.CHAVE_ATIVO, "0")
        _remover_caixa_falsa()  # se o gatilho tentar importar, vira erro - de proposito

        agora = datetime(2026, 6, 15, 7, 30, 0)
        p3_briefing.executar(self.conn, agora)  # nao pode levantar ModuleNotFoundError


class AoResolverTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def test_resposta_valida_salva_humor(self):
        item = {"origem": "p3_briefing:noite:2026-06-15"}
        p3_briefing.ao_resolver(self.conn, item, "Bom")

        checkin = db.get_checkin(self.conn, "2026-06-15")
        self.assertIsNotNone(checkin)
        self.assertEqual(checkin["humor"], 4)

    def test_resposta_sem_opcao_correspondente_nao_salva(self):
        item = {"origem": "p3_briefing:noite:2026-06-15"}
        p3_briefing.ao_resolver(self.conn, item, "adiar")

        checkin = db.get_checkin(self.conn, "2026-06-15")
        self.assertIsNone(checkin)

    def test_origem_de_outro_gatilho_e_ignorada(self):
        item = {"origem": "p2_conta:123"}
        p3_briefing.ao_resolver(self.conn, item, "Bom")
        self.assertIsNone(db.get_checkin(self.conn, date.today().isoformat()))

    def test_origem_do_briefing_da_manha_e_ignorada(self):
        item = {"origem": "p3_briefing:manha:2026-06-15"}
        p3_briefing.ao_resolver(self.conn, item, "Bom")
        self.assertIsNone(db.get_checkin(self.conn, "2026-06-15"))

    def test_item_sem_origem_nao_quebra(self):
        p3_briefing.ao_resolver(self.conn, {}, "Bom")
        p3_briefing.ao_resolver(self.conn, {"origem": None}, "Bom")
        p3_briefing.ao_resolver(self.conn, {"origem": ""}, "Bom")


if __name__ == "__main__":
    unittest.main()
