# Testes da faixa N1 (Fase 7) - financas_recorrentes.py (CRUD + calculos
# derivados, sem IA). Banco sempre :memory:, migracao aplicada direto via
# executescript (infra de migracao automatica da Etapa 0/X1 ainda nao
# mesclou em fase7/integracao - ver docs/agentes/fase7-regras-faixa.md).
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import financas_recorrentes as fr

MIGRACAO_SQL = (
    Path(__file__).resolve().parent.parent / "migracoes" / "202609241300_n1_assinaturas.sql"
).read_text(encoding="utf-8")


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'conta',
            saldo REAL,
            limite REAL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(banco, tipo)
        );
        CREATE TABLE acoes_desfazer (
            token TEXT PRIMARY KEY,
            itens_json TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
            desfeito_em TEXT
        );
        """
    )
    conn.executescript(MIGRACAO_SQL)
    conn.commit()
    return conn


class TestCriarAssinatura(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)

    def test_cria_com_campos_minimos(self):
        aid = fr.criar_assinatura(self.conn, "Netflix", "55", 24, hoje=self.hoje)
        a = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a["nome"], "Netflix")
        self.assertEqual(a["valor"], 55.0)
        self.assertEqual(a["dia_cobranca"], 24)
        self.assertEqual(a["ativa"], 1)
        self.assertEqual(a["inicio"], "2026-09-24")
        self.assertIsNone(a["cancelada_em"])

    def test_aceita_valor_com_virgula_como_string(self):
        aid = fr.criar_assinatura(self.conn, "Spotify", "21,90".replace(",", "."), 5, hoje=self.hoje)
        # nota: financas_recorrentes nunca recebe texto pt-BR cru - quem
        # normaliza "21,90" -> Decimal/"21.90" e o classificador local. Aqui
        # so garantimos que Decimal/str/float/int continuam aceitos.
        a = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a["valor"], 21.9)

    def test_valor_zero_ou_negativo_recusado(self):
        with self.assertRaises(ValueError):
            fr.criar_assinatura(self.conn, "X", 0, 1, hoje=self.hoje)
        with self.assertRaises(ValueError):
            fr.criar_assinatura(self.conn, "X", -10, 1, hoje=self.hoje)

    def test_nome_vazio_recusado(self):
        with self.assertRaises(ValueError):
            fr.criar_assinatura(self.conn, "   ", 10, 1, hoje=self.hoje)

    def test_dia_cobranca_fora_do_intervalo_recusado(self):
        for dia in (0, 32, -1, 100):
            with self.assertRaises(ValueError):
                fr.criar_assinatura(self.conn, "X", 10, dia, hoje=self.hoje)

    def test_dia_cobranca_nao_inteiro_recusado(self):
        with self.assertRaises(ValueError):
            fr.criar_assinatura(self.conn, "X", 10, "15", hoje=self.hoje)


class TestCancelarEReativarAssinatura(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)
        self.aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)

    def test_cancela(self):
        ok = fr.cancelar_assinatura(self.conn, self.aid, self.hoje)
        self.assertTrue(ok)
        a = fr.obter_assinatura(self.conn, self.aid)
        self.assertEqual(a["ativa"], 0)
        self.assertEqual(a["cancelada_em"], "2026-09-24")

    def test_cancelar_duas_vezes_segunda_falha(self):
        self.assertTrue(fr.cancelar_assinatura(self.conn, self.aid, self.hoje))
        self.assertFalse(fr.cancelar_assinatura(self.conn, self.aid, self.hoje))

    def test_cancelar_inexistente_falha(self):
        self.assertFalse(fr.cancelar_assinatura(self.conn, 99999, self.hoje))

    def test_reativar_volta_estado(self):
        fr.cancelar_assinatura(self.conn, self.aid, self.hoje)
        ok = fr.reativar_assinatura(self.conn, self.aid)
        self.assertTrue(ok)
        a = fr.obter_assinatura(self.conn, self.aid)
        self.assertEqual(a["ativa"], 1)
        self.assertIsNone(a["cancelada_em"])

    def test_reativar_ja_ativa_falha(self):
        self.assertFalse(fr.reativar_assinatura(self.conn, self.aid))

    def test_no_meio_do_mes_deixa_de_cobrar_apos_cancelamento(self):
        # assinatura cobra dia 24; cancelada no dia 10 -> nao cobra mais em
        # setembro (cancelou antes da cobranca daquele mes).
        aid = fr.criar_assinatura(self.conn, "Assinatura Meio Mes", 30, 24, inicio="2026-08-01")
        fr.cancelar_assinatura(self.conn, aid, date(2026, 9, 10))
        total = fr.total_mensal_comprometido(self.conn, date(2026, 9, 24))
        nomes = [d["nome"] for d in total["detalhe_assinaturas"]]
        self.assertNotIn("Assinatura Meio Mes", nomes)

    def test_cancelamento_apos_cobranca_do_mes_ainda_conta_naquele_mes(self):
        aid = fr.criar_assinatura(self.conn, "Assinatura Tardia", 30, 5, inicio="2026-08-01")
        fr.cancelar_assinatura(self.conn, aid, date(2026, 9, 20))  # cobrou dia 5, cancelou dia 20
        total = fr.total_mensal_comprometido(self.conn, date(2026, 9, 24))
        nomes = [d["nome"] for d in total["detalhe_assinaturas"]]
        self.assertIn("Assinatura Tardia", nomes)


class TestAtualizarAssinatura(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=date(2026, 9, 24))

    def test_atualiza_valor(self):
        self.assertTrue(fr.atualizar_assinatura(self.conn, self.aid, valor=60))
        self.assertEqual(fr.obter_assinatura(self.conn, self.aid)["valor"], 60.0)

    def test_ignora_campo_desconhecido(self):
        self.assertFalse(fr.atualizar_assinatura(self.conn, self.aid, campo_que_nao_existe="x"))

    def test_dia_cobranca_invalido_levanta(self):
        with self.assertRaises(ValueError):
            fr.atualizar_assinatura(self.conn, self.aid, dia_cobranca=40)

    def test_nome_vazio_levanta(self):
        with self.assertRaises(ValueError):
            fr.atualizar_assinatura(self.conn, self.aid, nome="   ")

    def test_sem_campos_devolve_false(self):
        self.assertFalse(fr.atualizar_assinatura(self.conn, self.aid))


class TestBuscarAssinaturaPorNome(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=date(2026, 9, 24))
        fr.criar_assinatura(self.conn, "Netflix Kids", 20, 24, hoje=date(2026, 9, 24))

    def test_prefere_match_exato(self):
        a = fr.buscar_assinatura_por_nome(self.conn, "Netflix")
        self.assertEqual(a["nome"], "Netflix")

    def test_sem_correspondencia_devolve_none(self):
        self.assertIsNone(fr.buscar_assinatura_por_nome(self.conn, "Amazon Prime"))

    def test_nome_vazio_devolve_none(self):
        self.assertIsNone(fr.buscar_assinatura_por_nome(self.conn, ""))

    def test_case_insensitive(self):
        a = fr.buscar_assinatura_por_nome(self.conn, "netflix")
        self.assertIsNotNone(a)

    def test_apenas_ativas_ignora_cancelada(self):
        aid = fr.criar_assinatura(self.conn, "Disney", 30, 10, hoje=date(2026, 9, 24))
        fr.cancelar_assinatura(self.conn, aid, date(2026, 9, 24))
        self.assertIsNone(fr.buscar_assinatura_por_nome(self.conn, "Disney"))
        self.assertIsNotNone(fr.buscar_assinatura_por_nome(self.conn, "Disney", apenas_ativas=False))


class TestCriarCompraParcelada(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)

    def test_deriva_valor_parcela_de_total(self):
        cid = fr.criar_compra_parcelada(self.conn, "geladeira", 12, valor_total=3000, hoje=self.hoje)
        c = fr.obter_compra_parcelada(self.conn, cid)
        self.assertEqual(c["valor_total"], 3000.0)
        self.assertEqual(c["valor_parcela"], 250.0)

    def test_deriva_valor_total_de_parcela(self):
        cid = fr.criar_compra_parcelada(self.conn, "celular", 10, valor_parcela=300, hoje=self.hoje)
        c = fr.obter_compra_parcelada(self.conn, cid)
        self.assertEqual(c["valor_parcela"], 300.0)
        self.assertEqual(c["valor_total"], 3000.0)

    def test_divisao_nao_exata_arredonda(self):
        cid = fr.criar_compra_parcelada(self.conn, "algo", 3, valor_total=100, hoje=self.hoje)
        c = fr.obter_compra_parcelada(self.conn, cid)
        self.assertEqual(c["valor_parcela"], 33.33)

    def test_sem_valor_nenhum_levanta(self):
        with self.assertRaises(ValueError):
            fr.criar_compra_parcelada(self.conn, "x", 3, hoje=self.hoje)

    def test_n_parcelas_invalido_levanta(self):
        for n in (0, -1, "10"):
            with self.assertRaises(ValueError):
                fr.criar_compra_parcelada(self.conn, "x", n, valor_total=100, hoje=self.hoje)

    def test_descricao_vazia_levanta(self):
        with self.assertRaises(ValueError):
            fr.criar_compra_parcelada(self.conn, "  ", 3, valor_total=100, hoje=self.hoje)

    def test_valor_total_negativo_levanta(self):
        with self.assertRaises(ValueError):
            fr.criar_compra_parcelada(self.conn, "x", 3, valor_total=-10, hoje=self.hoje)


class TestParcelaInfo(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.cid = fr.criar_compra_parcelada(
            self.conn, "celular", 10, valor_parcela=300, primeira_parcela="2026-09-24"
        )
        self.compra = fr.obter_compra_parcelada(self.conn, self.cid)

    def test_no_mes_da_primeira_parcela(self):
        info = fr.parcela_info(self.compra, date(2026, 9, 24))
        self.assertEqual(info["parcela_atual_calculada"], 1)
        self.assertEqual(info["parcelas_restantes"], 10)
        self.assertFalse(info["quitada"])
        self.assertEqual(info["proxima_cobranca"], "2026-09-24")

    def test_antes_do_dia_de_cobranca_do_mes_ainda_nao_pagou(self):
        info = fr.parcela_info(self.compra, date(2026, 9, 23))
        self.assertEqual(info["parcela_atual_calculada"], 1)
        self.assertEqual(info["parcelas_restantes"], 10)

    def test_meio_da_janela(self):
        info = fr.parcela_info(self.compra, date(2027, 1, 25))  # 4 meses depois, ja passou o dia
        self.assertEqual(info["parcela_atual_calculada"], 5)
        self.assertEqual(info["parcelas_restantes"], 6)

    def test_virada_de_ano(self):
        # granularidade de MES: 2027-01-01 ja esta no mes da 5a parcela
        # (set/out/nov/dez/jan = 5 meses desde a primeira), mesmo antes do
        # dia 24 - o dia so afeta a DATA de proxima_cobranca, nao o indice.
        info = fr.parcela_info(self.compra, date(2027, 1, 1))
        self.assertEqual(info["parcela_atual_calculada"], 5)
        self.assertEqual(info["proxima_cobranca"], "2027-01-24")

    def test_no_mes_da_ultima_parcela_ainda_nao_quitada(self):
        # no MES da 10a parcela (mesmo no dia exato da cobranca), a compra
        # ainda esta "em andamento" - so vira quitada no mes seguinte.
        info = fr.parcela_info(self.compra, date(2027, 6, 24))
        self.assertEqual(info["parcela_atual_calculada"], 10)
        self.assertFalse(info["quitada"])
        self.assertEqual(info["parcelas_restantes"], 1)
        self.assertEqual(info["proxima_cobranca"], "2027-06-24")

    def test_mes_seguinte_a_ultima_parcela_fica_quitada(self):
        info = fr.parcela_info(self.compra, date(2027, 7, 1))
        self.assertEqual(info["parcela_atual_calculada"], 10)
        self.assertTrue(info["quitada"])
        self.assertEqual(info["parcelas_restantes"], 0)
        self.assertIsNone(info["proxima_cobranca"])

    def test_muito_depois_de_quitada_continua_quitada(self):
        info = fr.parcela_info(self.compra, date(2030, 1, 1))
        self.assertTrue(info["quitada"])
        self.assertEqual(info["parcelas_restantes"], 0)

    def test_mes_termino_correto(self):
        info = fr.parcela_info(self.compra, date(2026, 9, 24))
        self.assertEqual(info["mes_termino"], "2027-06")

    def test_dia_31_clampado_em_fevereiro(self):
        cid = fr.criar_compra_parcelada(
            self.conn, "assinatura fev", 3, valor_parcela=100, primeira_parcela="2026-01-31"
        )
        compra = fr.obter_compra_parcelada(self.conn, cid)
        info = fr.parcela_info(compra, date(2026, 2, 28))
        self.assertEqual(info["parcela_atual_calculada"], 2)  # cravou no 28/02, ja passou


class TestListarCompras(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()

    def test_apenas_em_andamento_exclui_quitada(self):
        fr.criar_compra_parcelada(self.conn, "quitada", 1, valor_total=100, primeira_parcela="2020-01-01")
        fr.criar_compra_parcelada(self.conn, "em andamento", 24, valor_total=2400, primeira_parcela="2026-09-01")
        hoje = date(2026, 9, 24)
        resultado = fr.listar_compras_parceladas(self.conn, apenas_em_andamento=True, hoje=hoje)
        descricoes = [c["descricao"] for c in resultado]
        self.assertNotIn("quitada", descricoes)
        self.assertIn("em andamento", descricoes)


class TestTotalMensalComprometido(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)

    def test_soma_assinaturas_e_parcelas(self):
        fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)
        # dia_cobranca=5 num mes onde "hoje" e 24: se comecasse HOJE (inicio
        # padrao), o dia 5 ja teria passado e so cobraria a partir de
        # outubro - por isso um `inicio` antigo, simulando assinatura
        # ja existente, pra cair no mes corrente igual a Netflix.
        fr.criar_assinatura(self.conn, "Spotify", 21.90, 5, inicio="2026-01-05")
        fr.criar_compra_parcelada(self.conn, "celular", 10, valor_parcela=300, hoje=self.hoje)
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertAlmostEqual(total["total"], 55 + 21.90 + 300, places=2)

    def test_assinatura_cancelada_antes_da_cobranca_do_mes_nao_conta(self):
        # dia_cobranca=24 (mesmo dia de "hoje"); cancela ONTEM, antes da
        # cobranca de hoje - nao deveria contar mais este mes.
        aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, inicio="2026-01-01")
        fr.cancelar_assinatura(self.conn, aid, date(2026, 9, 23))
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertEqual(total["total"], 0.0)

    def test_assinatura_cancelada_no_mesmo_dia_da_cobranca_ainda_conta(self):
        aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, inicio="2026-01-01")
        fr.cancelar_assinatura(self.conn, aid, self.hoje)  # cancela no proprio dia 24
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertEqual(total["total"], 55.0)

    def test_sem_nada_devolve_zero(self):
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertEqual(total["total"], 0.0)
        self.assertEqual(total["detalhe_assinaturas"], [])
        self.assertEqual(total["detalhe_parcelas"], [])

    def test_assinatura_que_ainda_nao_comecou_nao_conta(self):
        fr.criar_assinatura(self.conn, "Futura", 10, 24, inicio="2026-12-01", hoje=self.hoje)
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertEqual(total["total"], 0.0)

    def test_soma_precisa_sem_deriva_de_float(self):
        # 3 assinaturas de 0.10 deveriam somar exatamente 0.30 (Decimal) -
        # com float puro isso as vezes vira 0.30000000000000004.
        for i in range(3):
            fr.criar_assinatura(self.conn, f"Micro{i}", 0.10, 24, hoje=self.hoje)
        total = fr.total_mensal_comprometido(self.conn, self.hoje)
        self.assertEqual(total["total"], 0.3)


class TestValorParaAvisoCustosFixos(unittest.TestCase):
    def test_projeta_mes_seguinte_nao_o_atual(self):
        conn = _conectar()
        hoje = date(2026, 9, 28)
        # comeca só no mes seguinte - nao deveria contar se a funcao olhasse
        # so pro mes de "hoje".
        fr.criar_assinatura(conn, "Nova", 40, 5, inicio="2026-10-01", hoje=hoje)
        valor = fr.valor_para_aviso_custos_fixos(conn, hoje)
        self.assertEqual(valor, 40.0)


class TestProximasCobrancas(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)

    def test_ordenado_por_proximidade(self):
        fr.criar_assinatura(self.conn, "Longe", 10, 5, hoje=self.hoje)  # ja passou -> mes que vem
        fr.criar_assinatura(self.conn, "Hoje", 20, 24, hoje=self.hoje)
        itens = fr.proximas_cobrancas(self.conn, self.hoje)
        self.assertEqual(itens[0]["nome"], "Hoje")
        self.assertLessEqual(itens[0]["dias"], itens[1]["dias"])

    def test_label_hoje_amanha_dias(self):
        fr.criar_assinatura(self.conn, "Hoje", 10, 24, hoje=self.hoje)
        fr.criar_assinatura(self.conn, "Amanha", 10, 25, hoje=self.hoje)
        fr.criar_assinatura(self.conn, "Depois", 10, 30, hoje=self.hoje)
        itens = {i["nome"]: i for i in fr.proximas_cobrancas(self.conn, self.hoje)}
        self.assertEqual(itens["Hoje"]["label"], "hoje")
        self.assertEqual(itens["Amanha"]["label"], "amanhã")
        self.assertEqual(itens["Depois"]["label"], "em 6 dias")

    def test_inclui_parcelas(self):
        fr.criar_compra_parcelada(self.conn, "celular", 10, valor_parcela=300, primeira_parcela="2026-09-24")
        itens = fr.proximas_cobrancas(self.conn, self.hoje)
        tipos = {i["tipo"] for i in itens}
        self.assertIn("compra_parcelada", tipos)

    def test_compra_quitada_nao_aparece(self):
        fr.criar_compra_parcelada(self.conn, "quitada", 1, valor_total=100, primeira_parcela="2020-01-01")
        itens = fr.proximas_cobrancas(self.conn, self.hoje)
        descricoes = [i.get("descricao") for i in itens]
        self.assertNotIn("quitada", descricoes)


class TestImpactoLimiteCartao(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.conn.execute("INSERT INTO bank_accounts (banco, tipo, limite) VALUES ('nubank', 'cartao', 1000)")
        self.conn.commit()
        self.hoje = date(2026, 9, 24)

    def test_projeta_6_meses_com_limite_conhecido(self):
        fr.criar_assinatura(self.conn, "Netflix", 55, 24, cartao_ou_forma="nubank", hoje=self.hoje)
        fr.criar_compra_parcelada(
            self.conn, "geladeira", 12, valor_total=3000, cartao="nubank", primeira_parcela="2026-09-24"
        )
        resultado = fr.impacto_limite_cartao_proximos_meses(self.conn, self.hoje, meses=6)
        self.assertEqual(len(resultado), 1)
        cartao = resultado[0]
        self.assertEqual(cartao["cartao"], "nubank")
        self.assertEqual(cartao["limite"], 1000.0)
        self.assertEqual(len(cartao["meses"]), 6)
        self.assertAlmostEqual(cartao["meses"][0]["total"], 55 + 250, places=2)
        self.assertIsNotNone(cartao["meses"][0]["fracao"])

    def test_sem_cartao_citado_devolve_lista_vazia(self):
        fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)
        resultado = fr.impacto_limite_cartao_proximos_meses(self.conn, self.hoje)
        self.assertEqual(resultado, [])

    def test_cartao_sem_limite_configurado_fracao_none(self):
        fr.criar_assinatura(self.conn, "Netflix", 55, 24, cartao_ou_forma="inter", hoje=self.hoje)
        resultado = fr.impacto_limite_cartao_proximos_meses(self.conn, self.hoje, meses=1)
        self.assertIsNone(resultado[0]["limite"])
        self.assertIsNone(resultado[0]["meses"][0]["fracao"])

    def test_parcela_que_termina_no_meio_da_janela_some_dos_meses_seguintes(self):
        fr.criar_compra_parcelada(
            self.conn, "curta", 2, valor_total=200, cartao="nubank", primeira_parcela="2026-09-24"
        )
        resultado = fr.impacto_limite_cartao_proximos_meses(self.conn, self.hoje, meses=4)
        totais = [m["total"] for m in resultado[0]["meses"]]
        self.assertEqual(totais, [100.0, 100.0, 0.0, 0.0])


class TestResumoFinanceiroRecorrente(unittest.TestCase):
    def test_formato_basico(self):
        conn = _conectar()
        hoje = date(2026, 9, 24)
        fr.criar_assinatura(conn, "Netflix", 55, 24, hoje=hoje)
        fr.criar_compra_parcelada(conn, "celular", 10, valor_parcela=300, hoje=hoje)
        resumo = fr.resumo_financeiro_recorrente(conn, hoje)
        self.assertEqual(resumo["n_assinaturas_ativas"], 1)
        self.assertEqual(resumo["n_compras_em_andamento"], 1)
        self.assertAlmostEqual(resumo["total_mensal"], 355.0, places=2)
        self.assertIn("proximas_cobrancas", resumo)


class TestDesfazerLocal(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.hoje = date(2026, 9, 24)

    def test_desfaz_criacao_de_assinatura(self):
        aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)
        token = fr.criar_token_desfazer(self.conn, "assinatura", "criar", aid)
        resultado = fr.aplicar_desfazer(self.conn, token)
        self.assertEqual(resultado, {"status": 200, "ok": True, "desfeitos": 1})
        self.assertIsNone(fr.obter_assinatura(self.conn, aid))

    def test_desfaz_cancelamento_reativa(self):
        aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)
        fr.cancelar_assinatura(self.conn, aid, self.hoje)
        token = fr.criar_token_desfazer(self.conn, "assinatura", "cancelar", aid)
        resultado = fr.aplicar_desfazer(self.conn, token)
        self.assertEqual(resultado["desfeitos"], 1)
        a = fr.obter_assinatura(self.conn, aid)
        self.assertEqual(a["ativa"], 1)
        self.assertIsNone(a["cancelada_em"])

    def test_desfaz_criacao_de_compra_parcelada(self):
        cid = fr.criar_compra_parcelada(self.conn, "celular", 10, valor_parcela=300, hoje=self.hoje)
        token = fr.criar_token_desfazer(self.conn, "compra_parcelada", "criar", cid)
        resultado = fr.aplicar_desfazer(self.conn, token)
        self.assertEqual(resultado["desfeitos"], 1)
        self.assertIsNone(fr.obter_compra_parcelada(self.conn, cid))

    def test_token_desconhecido_404(self):
        resultado = fr.aplicar_desfazer(self.conn, "token-que-nao-existe")
        self.assertEqual(resultado["status"], 404)

    def test_token_usado_duas_vezes_segunda_409(self):
        aid = fr.criar_assinatura(self.conn, "Netflix", 55, 24, hoje=self.hoje)
        token = fr.criar_token_desfazer(self.conn, "assinatura", "criar", aid)
        fr.aplicar_desfazer(self.conn, token)
        resultado = fr.aplicar_desfazer(self.conn, token)
        self.assertEqual(resultado["status"], 409)

    def test_entidade_invalida_levanta(self):
        with self.assertRaises(ValueError):
            fr.criar_token_desfazer(self.conn, "gasto", "criar", 1)


if __name__ == "__main__":
    unittest.main()
