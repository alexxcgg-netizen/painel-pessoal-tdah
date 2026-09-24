"""Testes de `classificador_local/regras/a10_agua.py` (Fase 7, faixa A10).

Cobre: 30+ variacoes de frase que DEVEM casar (com a quantidade certa
extraida), frases que NAO devem casar (inclusive as duas citadas no
prompt da faixa: "conta de agua", "agua sanitaria"), fuzzing de entrada
invalida/extrema, registro de verdade (mesma funcao `db.registrar_hidratacao`
do botao "+1 copo"), Desfazer, e o caminho completo via /api/chat com a IA
mockada garantindo que ela nao foi chamada."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import classificador_local  # noqa: E402
from classificador_local.regras import a10_agua  # noqa: E402

PIN_TESTE = "123456"
USO = {"model": "claude-sonnet", "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.001}

# (frase, quantidade esperada) - >= 30 variacoes positivas, cobrindo os 5
# exemplos do prompt da faixa ("tomei um copo de agua", "bebi agua", "mais
# um copo", "+1 agua", "tomei 2 copos") mais variacoes de verbo/numero/
# acento/maiuscula/pontuacao/espacamento.
FRASES_QUE_CASAM = [
    ("tomei um copo de agua", 1),
    ("tomei um copo de água", 1),
    ("Tomei um copo de água", 1),
    ("TOMEI UM COPO DE ÁGUA", 1),
    ("tomei um copo de água.", 1),
    ("tomei um copo de água!", 1),
    ("  tomei   um   copo   de   água  ", 1),
    ("tomei um copo d'água", 1),
    ("tomei um copo dágua", 1),
    ("tomei 1 copo de água", 1),
    ("tomei uma copo de água", 1),  # concordancia errada, mas ainda claro
    ("bebi água", 1),
    ("bebi agua", 1),
    ("Bebi Água", 1),
    ("bebi água.", 1),
    ("tomei água", 1),
    ("tomei agua", 1),
    ("bebi mais água", 1),
    ("tomei mais água", 1),
    ("mais água", 1),
    ("mais agua", 1),
    ("mais um copo", 1),
    ("mais um copo.", 1),
    ("mais 1 copo", 1),
    ("mais um copo de água", 1),
    ("mais uma copo de agua", 1),
    ("+1 água", 1),
    ("+1 agua", 1),
    ("+ 1 água", 1),
    ("+1 copo", 1),
    ("+1 copo de água", 1),
    ("tomei 2 copos", 2),
    ("tomei 2 copos.", 2),
    ("bebi 2 copos", 2),
    ("tomei dois copos", 2),
    ("tomei dois copos de água", 2),
    ("bebi 3 copos de água", 3),
    ("tomei três copos", 3),
    ("tomei tres copos de agua", 3),
    ("tomei mais 2 copos", 2),
    ("bebi mais um copo de água", 1),
    ("tomei mais um copo", 1),
    ("mais 2 copos", 2),
    ("mais 2 copos de água", 2),
    ("+2 água", 2),
    ("+3 copos", 3),
    ("+5 copos de água", 5),
    ("tomei dez copos de água", 10),
    ("tomei 10 copos", 10),
]

# frases que NAO devem casar - inclui as duas citadas explicitamente no
# prompt da faixa mais outras parecidas de proposito (pra provar que o
# regex e estrito, nao so "contem a palavra agua").
FRASES_QUE_NAO_CASAM = [
    "conta de água",
    "conta de agua",
    "paguei a conta de água",
    "a conta de água venceu",
    "água sanitária",
    "agua sanitaria",
    "comprei água sanitária",
    "água mineral",
    "comprei uma água mineral",
    "tomei um copo de suco",
    "tomei um copo de café",
    "tomei um copo de vinho",
    "bebi cerveja",
    "bebi refrigerante",
    "tomei banho",
    "tomei um remédio",
    "vou tomar água daqui a pouco",  # intencao futura, nao acao ja feita
    "preciso beber mais água",  # conselho/lembrete, nao registro
    "água",
    "agua",
    "copo",
    "um copo",
    "tomei",
    "bebi",
    "mais",
    "+1 tarefa",
    "+1",
    "gastei 20 com água",
    "tomei 2 copos de suco",
    "tomei um copo",  # ambiguo de proposito (ver nota no modulo) - ver teste dedicado abaixo
]


class CasarTestCase(unittest.TestCase):
    def test_frases_que_devem_casar(self):
        for frase, quantidade_esperada in FRASES_QUE_CASAM:
            with self.subTest(frase=frase):
                resultado = a10_agua.casar(frase)
                self.assertIsNotNone(resultado, f"deveria casar: {frase!r}")
                self.assertEqual(resultado["acao"], "registrar_hidratacao_a10")
                self.assertEqual(resultado["confianca"], 1.0)
                self.assertEqual(resultado["parametros"]["quantidade"], quantidade_esperada)

    def test_frases_que_nao_devem_casar(self):
        # "tomei um copo" (sem mencao a agua) e uma decisao de design
        # documentada no modulo - trato em separado, nao entra no bloco
        # generico de negativos.
        negativos = [f for f in FRASES_QUE_NAO_CASAM if f != "tomei um copo"]
        for frase in negativos:
            with self.subTest(frase=frase):
                self.assertIsNone(a10_agua.casar(frase), f"NAO deveria casar: {frase!r}")

    def test_tomei_um_copo_sozinho_conta_como_agua_por_design(self):
        """Mesma decisao do exemplo da faixa ("tomei 2 copos", sem "de
        agua", tambem conta) - "copo" sozinho no contexto de hidratacao e
        tratado como agua. Documentado no docstring do modulo."""
        resultado = a10_agua.casar("tomei um copo")
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["parametros"]["quantidade"], 1)

    def test_entrada_invalida_nunca_quebra(self):
        for bruto in (None, 123, 1.5, True, False, [], {}, ["tomei água"], object()):
            with self.subTest(bruto=bruto):
                self.assertIsNone(a10_agua.casar(bruto))

    def test_string_vazia_ou_so_espaco(self):
        for bruto in ("", "   ", "\n", "\t\t", "   \n  "):
            with self.subTest(bruto=repr(bruto)):
                self.assertIsNone(a10_agua.casar(bruto))

    def test_string_gigante_nao_quebra_nem_casa(self):
        gigante = "tomei água " * 20_000
        self.assertIsNone(a10_agua.casar(gigante))

    def test_unicode_estranho_nao_quebra(self):
        for bruto in ("\x00\ud800", "água" + "́" * 500, "🚰💧 água", "TOMEI ÁGUA"):
            with self.subTest(bruto=repr(bruto)):
                a10_agua.casar(bruto)  # so garante que nao levanta excecao

    def test_zero_copos_nao_e_acao(self):
        for frase in ("tomei 0 copos", "tomei 0 copo de água", "mais 0 copos", "+0 água"):
            with self.subTest(frase=frase):
                self.assertIsNone(a10_agua.casar(frase))

    def test_numero_negativo_nao_casa(self):
        for frase in ("tomei -1 copo", "tomei -2 copos de água"):
            with self.subTest(frase=frase):
                self.assertIsNone(a10_agua.casar(frase))

    def test_quantidade_absurda_e_clampada(self):
        resultado = a10_agua.casar("tomei 9999 copos")
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["parametros"]["quantidade"], a10_agua._QUANTIDADE_MAXIMA)

    def test_registrado_no_classificador_local_real(self):
        """`a10_agua.py` e um arquivo de verdade em classificador_local/regras/
        - `classificador_local.casar` (a fachada que o app usa) tem que achar
        ele sozinho, sem injecao de teste."""
        self.assertIn("a10_agua", classificador_local.nomes_regras())
        resultado = classificador_local.casar("tomei um copo de água")
        self.assertEqual(resultado["regra"], "a10_agua")
        self.assertEqual(resultado["acao"], "registrar_hidratacao_a10")


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)

    def contar_registros_hoje(self):
        from datetime import date

        conn = db.get_db()
        try:
            return db.contar_hidratacao_dia(conn, date.today().isoformat())
        finally:
            conn.close()


class ExecutarTestCase(_Base):
    def test_executar_registra_um_copo_com_a_mesma_funcao_do_botao(self):
        conn = db.get_db()
        try:
            resultado = a10_agua.casar("tomei um copo de água")
            saida = a10_agua.executar(conn, resultado["parametros"])
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(len(saida["efeitos"]), 1)
        self.assertEqual(saida["efeitos"][0]["entidade"], "hidratacao")
        self.assertIsInstance(saida["efeitos"][0]["id"], int)
        self.assertEqual(saida["resumo_texto"], "+1 copo de água. 1 hoje.")
        self.assertEqual(self.contar_registros_hoje(), 1)

    def test_executar_registra_n_copos(self):
        conn = db.get_db()
        try:
            resultado = a10_agua.casar("tomei 3 copos")
            saida = a10_agua.executar(conn, resultado["parametros"])
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(len(saida["efeitos"]), 3)
        ids = [ef["id"] for ef in saida["efeitos"]]
        self.assertEqual(len(set(ids)), 3)  # 3 linhas distintas, nao a mesma repetida
        self.assertEqual(saida["resumo_texto"], "+3 copos de água. 3 hoje.")
        self.assertEqual(self.contar_registros_hoje(), 3)

    def test_executar_acumula_com_registros_anteriores_do_dia(self):
        conn = db.get_db()
        try:
            db.registrar_hidratacao(conn, __import__("datetime").date.today().isoformat())
            conn.commit()
            resultado = a10_agua.casar("bebi água")
            saida = a10_agua.executar(conn, resultado["parametros"])
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(saida["resumo_texto"], "+1 copo de água. 2 hoje.")
        self.assertEqual(self.contar_registros_hoje(), 2)

    def test_executar_com_parametros_malformados_registra_1_por_seguranca(self):
        conn = db.get_db()
        try:
            for parametros in ({}, {"quantidade": "tres"}, {"quantidade": -5}, {"quantidade": None},
                                {"quantidade": True}, "nao e dict", None):
                with self.subTest(parametros=parametros):
                    antes = self.contar_registros_hoje()
                    saida = a10_agua.executar(conn, parametros)
                    conn.commit()
                    self.assertEqual(len(saida["efeitos"]), 1)
                    self.assertEqual(self.contar_registros_hoje(), antes + 1)
        finally:
            conn.close()

    def test_executar_clampa_quantidade_excessiva(self):
        conn = db.get_db()
        try:
            saida = a10_agua.executar(conn, {"quantidade": 500})
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(len(saida["efeitos"]), a10_agua._QUANTIDADE_MAXIMA)
        self.assertEqual(self.contar_registros_hoje(), a10_agua._QUANTIDADE_MAXIMA)


class DesfazerTestCase(_Base):
    def test_desfazer_remove_o_copo_registrado(self):
        conn = db.get_db()
        resultado = classificador_local.casar("tomei um copo de água")
        env = classificador_local.executar(conn, resultado, app._criar_token_desfazer(conn))
        conn.commit()
        conn.close()

        self.assertEqual(self.contar_registros_hoje(), 1)
        token = next(a["token"] for c in env["cards"] for a in c["actions"] if a.get("tipo") == "desfazer")

        res = self.client.post(f"/api/desfazer/{token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"ok": True, "desfeitos": 1})
        self.assertEqual(self.contar_registros_hoje(), 0)

    def test_desfazer_duas_vezes_da_409(self):
        conn = db.get_db()
        resultado = classificador_local.casar("bebi água")
        env = classificador_local.executar(conn, resultado, app._criar_token_desfazer(conn))
        conn.commit()
        conn.close()
        token = next(a["token"] for c in env["cards"] for a in c["actions"] if a.get("tipo") == "desfazer")

        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 409)

    def test_dois_copos_geram_dois_cards_com_desfazer_independente(self):
        """"tomei 2 copos" vira 2 efeitos `hidratacao` - cards.py monta 1
        card por efeito (nao agrupa hidratacao como agrupa tarefa), entao
        cada copo tem o proprio Desfazer, igual um brain dump normal
        (docs/CARDS.md: "cards diferentes da mesma resposta tem tokens
        independentes")."""
        conn = db.get_db()
        resultado = classificador_local.casar("tomei 2 copos")
        env = classificador_local.executar(conn, resultado, app._criar_token_desfazer(conn))
        conn.commit()
        conn.close()

        self.assertEqual(self.contar_registros_hoje(), 2)
        cards_saude = [c for c in env["cards"] if c["type"] == "saude_dia"]
        self.assertEqual(len(cards_saude), 2)
        tokens = [a["token"] for c in cards_saude for a in c["actions"] if a.get("tipo") == "desfazer"]
        self.assertEqual(len(tokens), 2)
        self.assertEqual(len(set(tokens)), 2)  # tokens distintos

        # desfaz so o primeiro - o segundo continua registrado
        self.assertEqual(self.client.post(f"/api/desfazer/{tokens[0]}").status_code, 200)
        self.assertEqual(self.contar_registros_hoje(), 1)


class IntegracaoChatTestCase(_Base):
    def test_chat_resolve_local_sem_chamar_ia(self):
        with patch("claude_client.chat") as ia:
            res = self.client.post("/api/chat", json={"mensagem": "tomei um copo de água"})
        ia.assert_not_called()
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertEqual(corpo["resposta"], "+1 copo de água. 1 hoje.")
        self.assertEqual(corpo["acoes"], ["registrar_hidratacao_a10"])
        self.assertEqual(corpo["cards"][0]["type"], "saude_dia")
        self.assertTrue(any(a.get("tipo") == "desfazer" for a in corpo["cards"][0]["actions"]))
        self.assertEqual(self.contar_registros_hoje(), 1)

    def test_chat_bebi_agua_tambem_resolve_local(self):
        with patch("claude_client.chat") as ia:
            res = self.client.post("/api/chat", json={"mensagem": "bebi água"})
        ia.assert_not_called()
        self.assertEqual(res.get_json()["resposta"], "+1 copo de água. 1 hoje.")

    def test_chat_mais_um_copo_tambem_resolve_local(self):
        with patch("claude_client.chat") as ia:
            res = self.client.post("/api/chat", json={"mensagem": "mais um copo"})
        ia.assert_not_called()
        self.assertEqual(res.get_json()["resposta"], "+1 copo de água. 1 hoje.")

    def test_chat_mais_1_agua_tambem_resolve_local(self):
        with patch("claude_client.chat") as ia:
            res = self.client.post("/api/chat", json={"mensagem": "+1 água"})
        ia.assert_not_called()
        self.assertEqual(res.get_json()["resposta"], "+1 copo de água. 1 hoje.")

    def test_chat_tomei_2_copos_registra_2(self):
        with patch("claude_client.chat") as ia:
            res = self.client.post("/api/chat", json={"mensagem": "tomei 2 copos"})
        ia.assert_not_called()
        self.assertEqual(res.get_json()["resposta"], "+2 copos de água. 2 hoje.")
        self.assertEqual(self.contar_registros_hoje(), 2)

    def test_chat_conta_de_agua_nao_resolve_local_vai_pra_ia(self):
        with patch("claude_client.chat", return_value=("Anotado.", [], USO)) as ia:
            res = self.client.post("/api/chat", json={"mensagem": "paguei a conta de água hoje"})
        ia.assert_called_once()
        self.assertEqual(res.get_json()["resposta"], "Anotado.")
        self.assertEqual(self.contar_registros_hoje(), 0)

    def test_chat_agua_sanitaria_nao_resolve_local_vai_pra_ia(self):
        with patch("claude_client.chat", return_value=("Ok.", [], USO)) as ia:
            res = self.client.post("/api/chat", json={"mensagem": "comprei água sanitária"})
        ia.assert_called_once()
        self.assertEqual(self.contar_registros_hoje(), 0)

    def test_telegram_usa_o_mesmo_caminho_local(self):
        with patch("claude_client.chat") as ia:
            self.assertEqual(app._telegram_chat_fn("tomei um copo de água"), "+1 copo de água. 1 hoje.")
        ia.assert_not_called()
        self.assertEqual(self.contar_registros_hoje(), 1)

    def test_captura_resolve_local_sem_chamar_ia(self):
        with patch("claude_client.classify_capture") as ia:
            res = self.client.post("/api/capture", json={"text": "tomei um copo de água"})
        ia.assert_not_called()
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self.assertEqual(corpo["regra_local"], "a10_agua")
        self.assertEqual(corpo["acao"], "registrar_hidratacao_a10")
        self.assertEqual(self.contar_registros_hoje(), 1)

    def test_intent_primeira_camada_so_classifica_nao_registra(self):
        with patch("claude_client.classify_intent") as ia:
            res = self.client.post("/api/intent/classificar", json={"texto": "tomei um copo de água"})
        ia.assert_not_called()
        corpo = res.get_json()
        self.assertEqual(corpo["acao"], "registrar_hidratacao_a10")
        self.assertEqual(corpo["regra_local"], "a10_agua")
        self.assertEqual(self.contar_registros_hoje(), 0)  # intent nunca executa


if __name__ == "__main__":
    unittest.main()
