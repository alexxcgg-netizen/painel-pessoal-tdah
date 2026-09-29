"""Testes da criptografia de campo (Open Finance + saude) - ver
docs/SEGURANCA.md. Cobre: roundtrip puro do modulo criptografia.py, que o
valor gravado no banco realmente nao e o texto plano (lido via SQL cru),
migracao de dado pre-existente (roda uma vez, idempotente), comportamento
sem ENCRYPTION_KEY configurada, e que as features que leem essas tabelas
continuam devolvendo os valores certos depois da mudanca."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from cryptography.fernet import Fernet

import aprendizado
import criptografia
import db
import notificacoes

# ATENCAO: db.DB_PATH tem que ser desviado do banco de verdade (data/painel.db)
# ANTES de importar app.py - o modulo chama init_db() direto na importacao
# (app.py:198), no caminho que db.DB_PATH apontar naquele instante. Sem isso,
# so importar este arquivo de teste ja migraria/mexeria no banco real (foi
# exatamente esse erro que uma revisao independente cometeu num script solto
# fora da suite - aqui na suite de verdade fica protegido). Mesmo padrao que
# tests/test_app.py ja usa.
_tmp_dir_import = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir_import.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do desvio de db.DB_PATH acima)

CHAVE_TESTE = Fernet.generate_key().decode()
OUTRA_CHAVE = Fernet.generate_key().decode()


class _BancoIsoladoTestCase(unittest.TestCase):
    """Mesmo padrao de test_financeiro.py/test_notificacoes.py - banco
    temporario isolado por teste. NAO chama db.init_db() sozinho no setUp
    (diferente da base usual) porque varios testes aqui precisam controlar
    exatamente quando ENCRYPTION_KEY esta presente na hora da subida do
    banco (pra testar a migracao)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        criptografia._aviso_sem_chave_ja_logado = False
        criptografia._aviso_chave_invalida_ja_logado = False

    def tearDown(self):
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()


# ---- Roundtrip puro do modulo criptografia.py ------------------------------


class CriptografiaModuloTestCase(unittest.TestCase):
    def test_configurada_reflete_env(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            self.assertTrue(criptografia.configurada())
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENCRYPTION_KEY", None)
            self.assertFalse(criptografia.configurada())

    def test_chave_malformada_nunca_levanta_e_nao_conta_como_configurada(self):
        # achado de revisao independente: Fernet(chave.encode()) levantava
        # ValueError direto pra quem chamasse _fernet()/criptografar() -
        # sem try/except em volta (ex: dentro do loop de migracao em db.py),
        # isso derrubava o app inteiro. Agora degrada pra "sem criptografia".
        for chave_ruim in ("nao-e-base64-valido!!!", "curta-demais", "a" * 100):
            with patch.dict(os.environ, {"ENCRYPTION_KEY": chave_ruim}):
                self.assertFalse(criptografia.configurada(), msg=repr(chave_ruim))
                self.assertEqual(criptografia.criptografar("saldo 1000"), "saldo 1000", msg=repr(chave_ruim))
                self.assertEqual(criptografia.descriptografar("saldo 1000"), "saldo 1000", msg=repr(chave_ruim))

    def test_roundtrip_texto(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            cifrado = criptografia.criptografar("Nubank - conta corrente")
            self.assertNotEqual(cifrado, "Nubank - conta corrente")
            self.assertEqual(criptografia.descriptografar(cifrado), "Nubank - conta corrente")

    def test_none_passa_direto_dos_dois_lados(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            self.assertIsNone(criptografia.criptografar(None))
            self.assertIsNone(criptografia.descriptografar(None))

    def test_sem_chave_criptografar_devolve_texto_como_veio(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENCRYPTION_KEY", None)
            self.assertEqual(criptografia.criptografar("saldo 1000"), "saldo 1000")
            self.assertEqual(criptografia.descriptografar("saldo 1000"), "saldo 1000")

    def test_mesmo_texto_gera_cifrados_diferentes_cada_vez(self):
        # Fernet usa IV aleatorio - protege contra "descobrir por padrao repetido"
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            a = criptografia.criptografar("Mercado")
            b = criptografia.criptografar("Mercado")
            self.assertNotEqual(a, b)
            self.assertEqual(criptografia.descriptografar(a), "Mercado")
            self.assertEqual(criptografia.descriptografar(b), "Mercado")

    def test_descriptografar_valor_nao_cifrado_devolve_como_esta(self):
        # dado gravado antes da chave existir, ou por um script que bateu
        # direto no banco - nunca derruba a leitura
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            self.assertEqual(criptografia.descriptografar("texto-plano-legado"), "texto-plano-legado")

    def test_descriptografar_com_chave_errada_devolve_cifrado_como_esta(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            cifrado = criptografia.criptografar("segredo")
        with patch.dict(os.environ, {"ENCRYPTION_KEY": OUTRA_CHAVE}):
            # chave errada nao decifra - nunca derruba, devolve o token cifrado como esta
            self.assertEqual(criptografia.descriptografar(cifrado), cifrado)


# ---- Roundtrip numerico via db._cnum/_dnum --------------------------------


class CriptografiaNumericaTestCase(unittest.TestCase):
    def test_int_roundtrip(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            cifrado = db._cnum(8123)
            self.assertEqual(db._dnum(cifrado, int), 8123)

    def test_float_roundtrip_sem_perda(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            cifrado = db._cnum(1234.567)
            self.assertEqual(db._dnum(cifrado, float), 1234.567)

    def test_negativo_roundtrip(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            cifrado = db._cnum(-45.9)
            self.assertEqual(db._dnum(cifrado, float), -45.9)

    def test_none_passa_direto(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            self.assertIsNone(db._cnum(None))
            self.assertIsNone(db._dnum(None, float))


# ---- O valor gravado no banco realmente nao e o texto plano ----------------


class ValorNaoFicaEmTextoPlanoTestCase(_BancoIsoladoTestCase):
    def test_saldo_bancario_cifrado_no_banco(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            conta_id = db.get_or_create_bank_account(conn, "Nubank")
            db.atualizar_saldo_conta(conn, conta_id, 1234.56)

            bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
            self.assertNotEqual(bruto["saldo"], "1234.56")
            self.assertNotEqual(bruto["saldo"], 1234.56)

            conta = db.buscar_conta_por_nome(conn, "Nubank")
            self.assertEqual(conta["saldo"], 1234.56)
            conn.close()

    def test_transacao_bancaria_descricao_e_valor_cifrados_no_banco(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            conta_id = db.get_or_create_bank_account(conn, "Nubank")
            db.insert_bank_transactions(
                conn,
                conta_id,
                [{"data": "2026-09-01", "descricao": "PADARIA CENTRAL", "valor": -45.9, "external_id": "ext1"}],
            )

            bruto = conn.execute(
                "SELECT descricao, valor FROM bank_transactions WHERE external_id = 'ext1'"
            ).fetchone()
            self.assertNotEqual(bruto["descricao"], "PADARIA CENTRAL")
            self.assertNotIn("PADARIA", bruto["descricao"])
            self.assertNotEqual(bruto["valor"], -45.9)

            transacoes = db.list_bank_transactions(conn, conta_id)
            self.assertEqual(transacoes[0]["descricao"], "PADARIA CENTRAL")
            self.assertEqual(transacoes[0]["valor"], -45.9)
            conn.close()

    def test_saude_cifrada_no_banco(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            hoje = date.today().isoformat()
            db.upsert_saude_dia(conn, hoje, {"passos": 8000, "sono_horas": 7.5})

            bruto = conn.execute("SELECT passos, sono_horas FROM saude_dados WHERE data = ?", (hoje,)).fetchone()
            self.assertNotEqual(bruto["passos"], "8000")
            self.assertNotEqual(bruto["sono_horas"], "7.5")

            dia = db.get_saude_dia(conn, hoje)
            self.assertEqual(dia["passos"], 8000)
            self.assertEqual(dia["sono_horas"], 7.5)
            conn.close()

    def test_medida_corporal_valor_cifrado_no_banco(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            medida_id = db.create_medida_corporal(conn, "peso", 78.4, "kg", date.today().isoformat())

            bruto = conn.execute("SELECT valor, tipo FROM medidas_corporais WHERE id = ?", (medida_id,)).fetchone()
            self.assertNotEqual(bruto["valor"], "78.4")
            self.assertEqual(bruto["tipo"], "peso")  # tipo fica em texto plano (usado em WHERE)

            medidas = db.list_medidas_corporais(conn, tipo="peso")
            self.assertEqual(medidas[0]["valor"], 78.4)
            conn.close()

    def test_medicamento_nome_dosagem_horario_cifrados_no_banco(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            cur = conn.execute("INSERT INTO tasks (title) VALUES ('Tomar Losartana')")
            conn.commit()
            med_id = db.create_medicamento(conn, "Losartana", "50mg", "08:00", "diaria", cur.lastrowid)

            bruto = conn.execute(
                "SELECT nome, dosagem, horario FROM medicamentos WHERE id = ?", (med_id,)
            ).fetchone()
            self.assertNotEqual(bruto["nome"], "Losartana")
            self.assertNotEqual(bruto["dosagem"], "50mg")
            self.assertNotEqual(bruto["horario"], "08:00")

            medicamentos = db.list_medicamentos_ativos(conn)
            self.assertEqual(medicamentos[0]["nome"], "Losartana")
            self.assertEqual(medicamentos[0]["dosagem"], "50mg")
            self.assertEqual(medicamentos[0]["horario"], "08:00")
            conn.close()

    def test_ordenacao_medicamentos_por_horario_continua_certa_cifrada(self):
        """horario e cifrado - list_medicamentos_ativos precisa ordenar em
        Python depois de descriptografar, nao no SQL."""
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            for nome, horario in [("C", "20:00"), ("A", "07:00"), ("B", "12:30")]:
                cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (f"Tomar {nome}",))
                conn.commit()
                db.create_medicamento(conn, nome, None, horario, "diaria", cur.lastrowid)

            medicamentos = db.list_medicamentos_ativos(conn)
            self.assertEqual([m["nome"] for m in medicamentos], ["A", "B", "C"])
            conn.close()


# ---- Migracao de dado pre-existente ----------------------------------------


class MigracaoTestCase(_BancoIsoladoTestCase):
    def test_migra_dado_texto_plano_ao_configurar_chave(self):
        # banco criado e populado SEM chave (texto plano, como sempre foi)
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Caixa")
        db.atualizar_saldo_conta(conn, conta_id, 500.0)
        hoje = date.today().isoformat()
        db.upsert_saude_dia(conn, hoje, {"passos": 5000})
        conn.close()

        conn_temp = db.get_db()
        bruto_antes = conn_temp.execute(
            "SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)
        ).fetchone()
        conn_temp.close()
        self.assertEqual(bruto_antes["saldo"], 500.0)

        # agora liga a chave e sobe o app de novo - migracao deve rodar
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            bruto_depois = conn.execute(
                "SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)
            ).fetchone()
            self.assertNotEqual(bruto_depois["saldo"], 500.0)

            # mas continua legivel normalmente pelas funcoes do db.py
            conta = db.buscar_conta_por_nome(conn, "Caixa")
            self.assertEqual(conta["saldo"], 500.0)
            dia = db.get_saude_dia(conn, hoje)
            self.assertEqual(dia["passos"], 5000)
            self.assertEqual(db.obter_configuracao(conn, "criptografia_migrada"), "1")
            conn.close()

    def test_migracao_nao_roda_duas_vezes(self):
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Caixa")
        db.atualizar_saldo_conta(conn, conta_id, 500.0)
        conn.close()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()  # 1a vez: migra (texto plano -> cifrado)
            conn = db.get_db()
            cifrado_1a_vez = conn.execute(
                "SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)
            ).fetchone()["saldo"]
            conn.close()

            db.init_db()  # 2a vez: flag ja setada, nao deve tocar de novo
            conn = db.get_db()
            cifrado_2a_vez = conn.execute(
                "SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)
            ).fetchone()["saldo"]
            # se tivesse rodado de novo, cifraria o texto ja cifrado e o
            # valor mudaria (e ficaria ilegivel) - tem que ser IDENTICO
            self.assertEqual(cifrado_1a_vez, cifrado_2a_vez)
            conta = db.buscar_conta_por_nome(conn, "Caixa")
            self.assertEqual(conta["saldo"], 500.0)
            conn.close()

    def test_migracao_nao_roda_sem_chave(self):
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Caixa")
        db.atualizar_saldo_conta(conn, conta_id, 500.0)
        conn.close()

        db.init_db()  # sem ENCRYPTION_KEY - migracao nem deve tentar rodar
        conn = db.get_db()
        self.assertIsNone(db.obter_configuracao(conn, "criptografia_migrada"))
        bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(bruto["saldo"], 500.0)
        conn.close()

    def test_chave_malformada_nao_derruba_a_subida_com_dado_sensivel(self):
        # achado de revisao independente: com dado sensivel ja gravado em
        # texto plano, uma ENCRYPTION_KEY presente mas invalida (colada
        # errada no .env) derrubava o app inteiro na subida - a migracao
        # chamava criptografar() dentro de um loop sem try/except em volta,
        # e Fernet(chave.encode()) levantava ValueError direto de init_db().
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Caixa")
        db.atualizar_saldo_conta(conn, conta_id, 500.0)
        db.upsert_saude_dia(conn, date.today().isoformat(), {"passos": 5000})
        conn.close()

        for chave_ruim in ("chave-obviamente-invalida", "curta-demais", ""):
            with patch.dict(os.environ, {"ENCRYPTION_KEY": chave_ruim}):
                if not chave_ruim:
                    os.environ.pop("ENCRYPTION_KEY", None)
                try:
                    db.init_db()  # nao pode levantar
                except Exception as e:  # pragma: no cover - o teste falha e mostra o motivo
                    self.fail(f"init_db() nao deveria propagar excecao com chave invalida: {e}")

        conn = db.get_db()
        # migracao nao rodou (chave nunca ficou "valida") - dado continua
        # exatamente como estava, legivel, nada virou lixo cifrado com chave
        # que nao existe de verdade
        self.assertIsNone(db.obter_configuracao(conn, "criptografia_migrada"))
        bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(bruto["saldo"], 500.0)
        conn.close()

    def test_migra_de_verdade_depois_de_corrigir_chave_invalida_pra_valida(self):
        # a chave invalida nao pode ter marcado "ja migrei" por engano -
        # senao, quando o Alex corrigir o .env com a chave certa, a migracao
        # de verdade nunca rodaria e o dado ficaria em texto plano pra sempre
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Caixa")
        db.atualizar_saldo_conta(conn, conta_id, 500.0)
        conn.close()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": "chave-invalida"}):
            db.init_db()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            self.assertEqual(db.obter_configuracao(conn, "criptografia_migrada"), "1")
            bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
            self.assertNotEqual(bruto["saldo"], 500.0)
            conta = db.buscar_conta_por_nome(conn, "Caixa")
            self.assertEqual(conta["saldo"], 500.0)
            conn.close()


# ---- Comportamento sem ENCRYPTION_KEY configurada --------------------------


class SemChaveTestCase(_BancoIsoladoTestCase):
    def test_app_funciona_normalmente_sem_chave_dado_fica_plano(self):
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Nubank")
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)

        bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(bruto["saldo"], 1000.0)  # continua em texto plano, sem quebrar nada

        conta = db.buscar_conta_por_nome(conn, "Nubank")
        self.assertEqual(conta["saldo"], 1000.0)
        conn.close()


# ---- Features existentes continuam corretas depois da mudanca -------------


class FeaturesExistentesComCriptografiaTestCase(_BancoIsoladoTestCase):
    def test_resumo_bancario_total_gasto_e_saldo_com_criptografia_ativa(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            conta_id = db.get_or_create_bank_account(conn, "Nubank")
            db.atualizar_saldo_conta(conn, conta_id, 2000.0)
            db.insert_bank_transactions(
                conn,
                conta_id,
                [
                    {"data": "2026-09-01", "descricao": "Mercado", "valor": -300.0, "external_id": "e1"},
                    {"data": "2026-09-02", "descricao": "Salario", "valor": 3000.0, "external_id": "e2"},
                ],
            )
            stats = db.estatisticas_conta(conn, conta_id)
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["total_gasto"], 300.0)
            self.assertEqual(stats["ultima"], "2026-09-02")

            total_mes = db.total_gastos_bancarios_mes(conn, "2026-09")
            self.assertEqual(total_mes, 300.0)
            conn.close()

    def test_media_passos_com_criptografia_ativa(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            hoje = date.today()
            for i, passos in enumerate([1000, 2000, 3000], start=1):
                dia = (hoje - timedelta(days=i)).isoformat()
                db.upsert_saude_dia(conn, dia, {"passos": passos})
            media = db.media_passos_ultimos_dias(conn, hoje.isoformat(), dias=7)
            self.assertEqual(media, 2000.0)
            conn.close()

    def test_correlacao_sono_produtividade_com_criptografia_ativa(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            dias_bom_sono = []
            for i in range(4):
                dia = date(2026, 1, 1) + timedelta(days=i)
                db.upsert_saude_dia(conn, dia.isoformat(), {"sono_horas": 8.0})
                dias_bom_sono.append(dia)
                for _ in range(2):
                    conn.execute(
                        "INSERT INTO tasks (title, due_date, completed_at) VALUES (?, ?, ?)",
                        ("Tarefa", dia.isoformat(), f"{dia.isoformat()}T10:00:00"),
                    )
            conn.commit()
            correlacao = aprendizado.correlacao_sono_produtividade(conn, minimo_amostras=3)
            self.assertIn("8h+", correlacao)
            self.assertEqual(correlacao["8h+"], 1.0)
            conn.close()

    def test_media_checkin_por_faixa_sono_com_criptografia_ativa(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            for i in range(4):
                dia = date(2026, 1, 1) + timedelta(days=i)
                db.upsert_saude_dia(conn, dia.isoformat(), {"sono_horas": 8.0})
                db.salvar_checkin(conn, dia.isoformat(), {"humor": 3, "energia": 3, "sono": 3})
            medias = aprendizado.media_checkin_por_faixa_sono(conn, "humor", minimo_amostras=3)
            self.assertIn("8h+", medias)
            self.assertEqual(medias["8h+"], 3.0)
            conn.close()

    def test_cobrancas_genericas_sem_rotulo_com_criptografia_ativa(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            conta_id = db.get_or_create_bank_account(conn, "Nubank")
            db.insert_bank_transactions(
                conn,
                conta_id,
                [{"data": "2026-09-01", "descricao": "APPLE.COM/BILL", "valor": -14.9, "external_id": "e1"}],
            )
            avisos = notificacoes.cobrancas_genericas_sem_rotulo(conn)
            self.assertEqual(len(avisos), 1)
            self.assertEqual(avisos[0][0], "apple.com/bill")
            self.assertAlmostEqual(avisos[0][1], 14.9)
            conn.close()

    def test_export_completo_sai_legivel_com_criptografia_ativa(self):
        # achado de revisao independente: o export JSON/CSV completo
        # (docs/BACKUP.md promete "legivel"/"pra abrir em planilha") fazia
        # SELECT * cru via introspeccao de schema, sem descriptografar - com
        # a chave ligada, saldo/sono/etc saiam como token Fernet ilegivel.
        # O backup .db bruto (sqlite3.backup) continua cifrado de proposito
        # (esse SIM e o formato pensado pra restaurar sem passar pela app) -
        # esse teste e so do export JSON/CSV completo.
        with patch.dict(os.environ, {"ENCRYPTION_KEY": CHAVE_TESTE}):
            db.init_db()
            conn = db.get_db()
            conta_id = db.get_or_create_bank_account(conn, "Nubank")
            db.atualizar_saldo_conta(conn, conta_id, 1234.5)
            db.insert_bank_transactions(
                conn, conta_id, [{"data": "2026-09-01", "descricao": "Mercado", "valor": -50.0, "external_id": "e1"}]
            )
            db.upsert_saude_dia(conn, "2026-09-01", {"passos": 8000, "sono_horas": 7.5})

            tabelas = app._exportar_tabelas_dict(conn)

            conta_exportada = next(t for t in tabelas["bank_accounts"] if t["id"] == conta_id)
            self.assertEqual(conta_exportada["saldo"], 1234.5)
            transacao_exportada = tabelas["bank_transactions"][0]
            self.assertEqual(transacao_exportada["descricao"], "Mercado")
            self.assertEqual(transacao_exportada["valor"], -50.0)
            saude_exportada = next(s for s in tabelas["saude_dados"] if s["data"] == "2026-09-01")
            self.assertEqual(saude_exportada["passos"], 8000)
            self.assertEqual(saude_exportada["sono_horas"], 7.5)

            # confirma que ESTAVA cifrado no banco (senao o teste nao provaria
            # nada - o export teria que descriptografar de fato, nao so ler
            # um valor que ja estava em texto plano por acidente)
            bruto = conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
            self.assertNotEqual(bruto["saldo"], 1234.5)
            conn.close()

    def test_export_completo_fica_cifrado_sem_chave(self):
        # sem ENCRYPTION_KEY, nao ha chave nenhuma pra descriptografar -
        # exporta exatamente o que esta gravado (que ja e o proprio dado
        # legivel, ja que sem chave o banco fica em texto plano mesmo)
        db.init_db()
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "Nubank")
        db.atualizar_saldo_conta(conn, conta_id, 700.0)
        tabelas = app._exportar_tabelas_dict(conn)
        conta_exportada = next(t for t in tabelas["bank_accounts"] if t["id"] == conta_id)
        self.assertEqual(conta_exportada["saldo"], 700.0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
