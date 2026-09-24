# Testes da faixa P7 (sinais do iPhone) - assistente/sinais.py:
# ultimos_sinais, sinal_recente e a reacao embutida (reagir). Banco sempre
# temporario/memoria, com o SQL da migracao aplicado direto (sem depender de
# db.init_db/infra de migracao ainda nao mesclada - mesmo padrao da faixa
# A5, ver tests/test_ia_historico.py). enfileirar/P3 sempre mockados: nenhuma
# chamada real, nenhum dado do Alex sai do ambiente.
import sqlite3
import sys
import types
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from assistente import sinais

MIGRACAO_SQL = (
    Path(__file__).resolve().parent.parent / "migracoes" / "202609241240_p7_sinais.sql"
).read_text(encoding="utf-8")


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRACAO_SQL)
    conn.executescript(
        """
        CREATE TABLE configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );

        CREATE TABLE compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            item_normalizado TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            comprado_em TEXT
        );
        """
    )
    return conn


def _inserir_sinal(conn, tipo, lugar=None, quando=None, recebido_em=None):
    quando = quando or datetime.now().isoformat(timespec="seconds")
    if recebido_em is None:
        conn.execute("INSERT INTO sinais (tipo, lugar, quando) VALUES (?, ?, ?)", (tipo, lugar, quando))
    else:
        conn.execute(
            "INSERT INTO sinais (tipo, lugar, quando, recebido_em) VALUES (?, ?, ?, ?)",
            (tipo, lugar, quando, recebido_em),
        )
    conn.commit()


@contextmanager
def _caixa_mockada(retorno="item-1"):
    """`assistente.caixa` ainda nao existe nesta integracao (faixa P1a) -
    injeta um modulo falso em sys.modules pro `from assistente.caixa import
    enfileirar` (import tardio, dentro da funcao) funcionar no teste, do
    jeito que a P1a vai deixar quando existir de verdade."""
    modulo_falso = types.ModuleType("assistente.caixa")
    mock_enfileirar = MagicMock(return_value=retorno)
    modulo_falso.enfileirar = mock_enfileirar
    anterior = sys.modules.get("assistente.caixa")
    sys.modules["assistente.caixa"] = modulo_falso
    try:
        yield mock_enfileirar
    finally:
        if anterior is None:
            sys.modules.pop("assistente.caixa", None)
        else:
            sys.modules["assistente.caixa"] = anterior


@contextmanager
def _p3_ausente():
    """Garante que `assistente.gatilhos.p3_briefing` nao existe (P3 ainda
    nao chegou nesta integracao) - o cenario padrao destes testes."""
    chaves_removidas = {}
    for chave in list(sys.modules):
        if chave == "assistente.gatilhos.p3_briefing" or chave.startswith("assistente.gatilhos.p3_briefing."):
            chaves_removidas[chave] = sys.modules.pop(chave)
    try:
        yield
    finally:
        sys.modules.update(chaves_removidas)


@contextmanager
def _p3_mockada():
    """Injeta um `assistente.gatilhos.p3_briefing` falso com
    `garantir_briefing` mockado - simula a P3 ja integrada."""
    pacote_gatilhos = sys.modules.get("assistente.gatilhos")
    pacote_criado = False
    if pacote_gatilhos is None:
        pacote_gatilhos = types.ModuleType("assistente.gatilhos")
        pacote_gatilhos.__path__ = []
        sys.modules["assistente.gatilhos"] = pacote_gatilhos
        pacote_criado = True
    modulo_falso = types.ModuleType("assistente.gatilhos.p3_briefing")
    mock_garantir = MagicMock(return_value=None)
    modulo_falso.garantir_briefing = mock_garantir
    anterior = sys.modules.get("assistente.gatilhos.p3_briefing")
    sys.modules["assistente.gatilhos.p3_briefing"] = modulo_falso
    try:
        yield mock_garantir
    finally:
        if anterior is None:
            sys.modules.pop("assistente.gatilhos.p3_briefing", None)
        else:
            sys.modules["assistente.gatilhos.p3_briefing"] = anterior
        if pacote_criado:
            sys.modules.pop("assistente.gatilhos", None)


class TokenValidoTestCase(unittest.TestCase):
    def test_token_certo(self):
        self.assertTrue(sinais.token_valido("Bearer segredo-123", "segredo-123"))

    def test_token_errado(self):
        self.assertFalse(sinais.token_valido("Bearer errado", "segredo-123"))

    def test_token_ausente_no_cabecalho(self):
        self.assertFalse(sinais.token_valido(None, "segredo-123"))
        self.assertFalse(sinais.token_valido("", "segredo-123"))

    def test_sem_bearer_no_cabecalho(self):
        self.assertFalse(sinais.token_valido("segredo-123", "segredo-123"))

    def test_sem_token_configurado_fica_sempre_fechado(self):
        # rota maquina-a-maquina (ROTAS_COM_TOKEN): sem PAINEL_SINAL_TOKEN
        # configurado ela NUNCA fica aberta, mesmo que o cabeçalho mande algo.
        self.assertFalse(sinais.token_valido("Bearer qualquer-coisa", None))
        self.assertFalse(sinais.token_valido("Bearer qualquer-coisa", ""))
        self.assertFalse(sinais.token_valido(None, None))

    def test_case_sensitive_e_prefixo_exato(self):
        self.assertFalse(sinais.token_valido("bearer segredo-123", "segredo-123"))  # 'Bearer' com B maiusculo
        self.assertFalse(sinais.token_valido("Bearersegredo-123", "segredo-123"))  # sem espaco

    def test_token_configurado_vazio_apos_espacos_ainda_fecha(self):
        self.assertFalse(sinais.token_valido("Bearer ", "segredo-123"))


class QuandoValidoTestCase(unittest.TestCase):
    def test_datetime_iso_valido(self):
        self.assertEqual(sinais.quando_valido("2026-09-24T08:00:00"), "2026-09-24T08:00:00")

    def test_data_pura_tambem_vale(self):
        self.assertEqual(sinais.quando_valido("2026-09-24"), "2026-09-24T00:00:00")

    def test_com_espacos_em_volta(self):
        self.assertEqual(sinais.quando_valido("  2026-09-24T08:00:00  "), "2026-09-24T08:00:00")

    def test_string_vazia_ou_so_espaco(self):
        self.assertIsNone(sinais.quando_valido(""))
        self.assertIsNone(sinais.quando_valido("   "))

    def test_none(self):
        self.assertIsNone(sinais.quando_valido(None))

    def test_tipo_errado_nao_quebra(self):
        for valor in (123, 123.4, True, False, [], {}, ["2026-09-24"]):
            with self.subTest(valor=valor):
                self.assertIsNone(sinais.quando_valido(valor))

    def test_texto_invalido(self):
        for valor in ("nao-e-data", "32/13/2026", "2026-13-40", "amanha"):
            with self.subTest(valor=valor):
                self.assertIsNone(sinais.quando_valido(valor))


class GravarTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()

    def tearDown(self):
        self.conn.close()

    def test_grava_e_devolve_id(self):
        sinal_id = sinais.gravar(self.conn, "acordei", None, "2026-09-24T07:00:00")
        self.assertIsInstance(sinal_id, int)
        linha = self.conn.execute("SELECT * FROM sinais WHERE id = ?", (sinal_id,)).fetchone()
        self.assertEqual(linha["tipo"], "acordei")
        self.assertIsNone(linha["lugar"])
        self.assertEqual(linha["quando"], "2026-09-24T07:00:00")
        self.assertIsNotNone(linha["recebido_em"])

    def test_grava_com_lugar(self):
        sinal_id = sinais.gravar(self.conn, "cheguei", "mercado", "2026-09-24T10:00:00")
        linha = self.conn.execute("SELECT lugar FROM sinais WHERE id = ?", (sinal_id,)).fetchone()
        self.assertEqual(linha["lugar"], "mercado")

    def test_tipo_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            sinais.gravar(self.conn, "voando", None, "2026-09-24T10:00:00")

    def test_ids_sao_sequenciais(self):
        primeiro = sinais.gravar(self.conn, "dormir", None, "2026-09-24T22:00:00")
        segundo = sinais.gravar(self.conn, "acordei", None, "2026-09-25T07:00:00")
        self.assertLess(primeiro, segundo)

    def test_ja_fica_commitado_visivel_em_outra_leitura(self):
        sinal_id = sinais.gravar(self.conn, "carregando", None, "2026-09-24T23:00:00")
        total = self.conn.execute("SELECT COUNT(*) AS n FROM sinais").fetchone()["n"]
        self.assertEqual(total, 1)
        self.assertGreater(sinal_id, 0)


class UltimosSinaisTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()

    def tearDown(self):
        self.conn.close()

    def test_vazio_sem_sinal_nenhum(self):
        self.assertEqual(sinais.ultimos_sinais(self.conn), [])

    def test_mais_recente_primeiro(self):
        _inserir_sinal(self.conn, "dormir", quando="2026-09-23T22:00:00")
        _inserir_sinal(self.conn, "acordei", quando="2026-09-24T07:00:00")
        resultado = sinais.ultimos_sinais(self.conn)
        self.assertEqual([r["tipo"] for r in resultado], ["acordei", "dormir"])

    def test_filtra_por_tipo(self):
        _inserir_sinal(self.conn, "cheguei", lugar="mercado", quando="2026-09-24T10:00:00")
        _inserir_sinal(self.conn, "sai", lugar="mercado", quando="2026-09-24T10:30:00")
        resultado = sinais.ultimos_sinais(self.conn, tipo="cheguei")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["tipo"], "cheguei")

    def test_filtra_por_desde_string_ou_datetime(self):
        _inserir_sinal(self.conn, "carregando", quando="2026-09-20T09:00:00")
        _inserir_sinal(self.conn, "carregando", quando="2026-09-24T09:00:00")
        self.assertEqual(len(sinais.ultimos_sinais(self.conn, desde="2026-09-23T00:00:00")), 1)
        self.assertEqual(len(sinais.ultimos_sinais(self.conn, desde=datetime(2026, 9, 23))), 1)
        self.assertEqual(len(sinais.ultimos_sinais(self.conn, desde="2026-01-01T00:00:00")), 2)

    def test_limite_de_50(self):
        for i in range(60):
            _inserir_sinal(self.conn, "dormir", quando=f"2026-09-24T00:{i % 60:02d}:00")
        self.assertEqual(len(sinais.ultimos_sinais(self.conn)), 50)

    def test_nao_quebra_com_tipo_inexistente(self):
        self.assertEqual(sinais.ultimos_sinais(self.conn, tipo="nao-existe"), [])


class SinalRecenteTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.agora = datetime(2026, 9, 24, 12, 0, 0)

    def tearDown(self):
        self.conn.close()

    def test_none_sem_sinal_nenhum(self):
        self.assertIsNone(sinais.sinal_recente(self.conn, "acordei", agora=self.agora))

    def test_dentro_da_janela(self):
        _inserir_sinal(self.conn, "acordei", quando=(self.agora - timedelta(minutes=5)).isoformat())
        resultado = sinais.sinal_recente(self.conn, "acordei", janela_min=10, agora=self.agora)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["tipo"], "acordei")

    def test_fora_da_janela_devolve_none(self):
        _inserir_sinal(self.conn, "acordei", quando=(self.agora - timedelta(minutes=11)).isoformat())
        self.assertIsNone(sinais.sinal_recente(self.conn, "acordei", janela_min=10, agora=self.agora))

    def test_no_limite_exato_da_janela_conta(self):
        _inserir_sinal(self.conn, "acordei", quando=(self.agora - timedelta(minutes=10)).isoformat())
        self.assertIsNotNone(sinais.sinal_recente(self.conn, "acordei", janela_min=10, agora=self.agora))

    def test_sinal_no_futuro_devolve_none(self):
        # relogio do iPhone adiantado, ou 'quando' mandado errado - nunca deve
        # contar como "recente" um sinal que ainda nao aconteceu.
        _inserir_sinal(self.conn, "acordei", quando=(self.agora + timedelta(minutes=1)).isoformat())
        self.assertIsNone(sinais.sinal_recente(self.conn, "acordei", agora=self.agora))

    def test_filtra_por_lugar(self):
        _inserir_sinal(self.conn, "cheguei", lugar="trabalho", quando=(self.agora - timedelta(minutes=1)).isoformat())
        self.assertIsNotNone(sinais.sinal_recente(self.conn, "cheguei", lugar="trabalho", agora=self.agora))
        self.assertIsNone(sinais.sinal_recente(self.conn, "cheguei", lugar="mercado", agora=self.agora))

    def test_quando_invalido_devolve_none_sem_quebrar(self):
        self.conn.execute(
            "INSERT INTO sinais (tipo, lugar, quando) VALUES ('acordei', NULL, 'nao-e-data')"
        )
        self.conn.commit()
        self.assertIsNone(sinais.sinal_recente(self.conn, "acordei", agora=self.agora))

    def test_pega_o_mais_recente_entre_varios(self):
        _inserir_sinal(self.conn, "dormir", quando=(self.agora - timedelta(minutes=9)).isoformat())
        _inserir_sinal(self.conn, "dormir", quando=(self.agora - timedelta(minutes=2)).isoformat())
        resultado = sinais.sinal_recente(self.conn, "dormir", agora=self.agora)
        self.assertEqual(resultado["quando"], (self.agora - timedelta(minutes=2)).isoformat())


class ReagirTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.agora = datetime(2026, 9, 24, 8, 0, 0)

    def tearDown(self):
        self.conn.close()

    def _add_compra(self, item):
        self.conn.execute(
            "INSERT INTO compras (item, item_normalizado) VALUES (?, ?)", (item, item.lower())
        )
        self.conn.commit()

    def test_flag_desligada_nao_reage_a_nada(self):
        self.conn.execute(
            "INSERT INTO configuracoes (chave, valor) VALUES (?, ?)", (sinais.FLAG_REACOES, "0")
        )
        self.conn.commit()
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_not_called()

    def test_flag_ligada_por_padrao_sem_configuracao(self):
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_called_once()

    def test_cheguei_mercado_enfileira_lista_de_compras(self):
        self._add_compra("arroz")
        self._add_compra("feijao")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_called_once()
        args, kwargs = mock_enfileirar.call_args
        self.assertEqual(args[0], "aviso")
        self.assertIn("arroz", args[2])
        self.assertIn("feijao", args[2])
        self.assertEqual(kwargs["origem"], "p7_sinais")
        self.assertTrue(kwargs["chave_unica"].startswith("p7_mercado_"))

    def test_cheguei_mercado_sem_lista_nao_enfileira(self):
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_not_called()

    def test_cheguei_em_outro_lugar_nao_mexe_com_compras(self):
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "trabalho", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_not_called()

    def test_cheguei_mercado_com_lugar_maiusculo_ou_com_espaco(self):
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "cheguei", "  Mercado  ", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_called_once()

    def test_sai_nao_enfileira_nada(self):
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            sinais.reagir(self.conn, "sai", "mercado", self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_not_called()

    def test_p1a_ausente_nao_quebra_reagir(self):
        # sem _caixa_mockada nenhuma: assistente.caixa nao existe de verdade
        self._add_compra("arroz")
        sys.modules.pop("assistente.caixa", None)
        sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)  # nao levanta

    def test_acordei_chama_p3_quando_existe(self):
        with _p3_mockada() as mock_garantir:
            sinais.reagir(self.conn, "acordei", None, self.agora.isoformat(), agora=self.agora)
        mock_garantir.assert_called_once_with(self.conn, self.agora)

    def test_acordei_sem_p3_nao_quebra(self):
        with _p3_ausente():
            sinais.reagir(self.conn, "acordei", None, self.agora.isoformat(), agora=self.agora)  # nao levanta

    def test_acordei_com_p3_levantando_excecao_nao_quebra(self):
        with _p3_mockada() as mock_garantir:
            mock_garantir.side_effect = RuntimeError("boom")
            sinais.reagir(self.conn, "acordei", None, self.agora.isoformat(), agora=self.agora)  # nao levanta

    def test_dormir_e_carregando_nao_disparam_reacao(self):
        with _caixa_mockada() as mock_enfileirar, _p3_ausente():
            sinais.reagir(self.conn, "dormir", None, self.agora.isoformat(), agora=self.agora)
            sinais.reagir(self.conn, "carregando", None, self.agora.isoformat(), agora=self.agora)
        mock_enfileirar.assert_not_called()

    def test_enfileirar_levantando_excecao_nao_quebra_reagir(self):
        self._add_compra("arroz")
        with _caixa_mockada() as mock_enfileirar:
            mock_enfileirar.side_effect = RuntimeError("boom")
            sinais.reagir(self.conn, "cheguei", "mercado", self.agora.isoformat(), agora=self.agora)  # nao levanta


if __name__ == "__main__":
    unittest.main()
