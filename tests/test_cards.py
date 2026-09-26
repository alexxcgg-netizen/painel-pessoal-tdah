"""Fase 6 (Grupo E3) - contrato de cards (docs/CARDS.md).

Testa o envelope {cards, resumo_texto, passos} de /api/chat e /api/capture,
o mapeamento executor-de-tool -> card (cards.py), a compatibilidade com os
campos legados e o modo visitante (valor nao sai na resposta). Banco sempre
temporario, IA sempre mockada.
"""

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import cards  # noqa: E402

PIN_TESTE = "123456"


def fake_usage(model="claude-haiku-4-5-20251001", cost=0.001):
    return {"model": model, "input_tokens": 100, "output_tokens": 20, "cost_usd": cost}


class ContratoCardsBase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def tearDown(self):
        self.conn.close()

    def _chat(self, fake_chat, mensagem="oi"):
        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    def _capture(self, parsed, texto="algo", **extra):
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            return self.client.post("/api/capture", json={"text": texto, **extra})

    def _assert_envelope(self, corpo):
        self.assertIsInstance(corpo["cards"], list)
        self.assertIsInstance(corpo["resumo_texto"], str)
        self.assertIsInstance(corpo["passos"], list)
        ids = [c["id"] for c in corpo["cards"]]
        self.assertEqual(len(ids), len(set(ids)))
        for c in corpo["cards"]:
            self.assertIn(c["type"], cards.TIPOS_CARD)
            self.assertIsInstance(c["data"], dict)
            self.assertIsInstance(c["actions"], list)
        for p in corpo["passos"]:
            self.assertEqual(set(p) - {"erro"}, {"modulo", "descricao", "ms"})
            self.assertIsInstance(p["ms"], int)


class ChatContratoTestCase(ContratoCardsBase):
    def test_chat_sem_tool_devolve_envelope_vazio_e_campos_legados(self):
        corpo = self._chat(lambda *a: ("Oi! Beleza?", [], fake_usage()))
        self._assert_envelope(corpo)
        self.assertEqual(corpo["cards"], [])
        self.assertEqual(corpo["passos"], [])
        # legado continua (frontend antigo em cache do PWA)
        self.assertEqual(corpo["resposta"], "Oi! Beleza?")
        self.assertEqual(corpo["resumo_texto"], "Oi! Beleza?")
        self.assertEqual(corpo["acoes"], [])

    def test_efeito_privado_nunca_chega_na_ia(self):
        vistos = []

        def fake_chat(mensagens, contexto, memorias, executores):
            vistos.append(executores["registrar_tarefa"]({"titulo": "x"}))
            vistos.append(executores["registrar_gasto"]({"titulo": "pao", "valor": 5.0}))
            vistos.append(executores["registrar_meta"]({"titulo": "m", "valor": 100.0}))
            vistos.append(executores["registrar_lembrete"]({"titulo": "l", "data": "2026-10-01"}))
            vistos.append(executores["registrar_renda"]({"valor": 10.0, "categoria": "freela"}))
            return "ok", [], fake_usage()

        self._chat(fake_chat)
        for r in vistos:
            self.assertFalse([k for k in r if k.startswith("_")], r)
        self.assertEqual(vistos[0], {"ok": True})

    def test_tarefas_da_mesma_resposta_viram_um_card_so(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "comprar pao", "quando_data": "2026-09-23", "hora": "08:00"})
            executores["registrar_tarefa"]({"titulo": "ligar pro banco"})
            return "Anotei as duas.", ["registrar_tarefa", "registrar_tarefa"], fake_usage()

        corpo = self._chat(fake_chat)
        self._assert_envelope(corpo)
        self.assertEqual([c["type"] for c in corpo["cards"]], ["tarefas_criadas"])
        tarefas = corpo["cards"][0]["data"]["tarefas"]
        self.assertEqual([t["titulo"] for t in tarefas], ["comprar pao", "ligar pro banco"])
        self.assertEqual(tarefas[0]["data"], "2026-09-23")
        self.assertEqual(tarefas[0]["hora"], "08:00")
        self.assertFalse(tarefas[0]["concluida"])
        abrir = [a for a in corpo["cards"][0]["actions"] if a["tipo"] == "abrir_aba"]
        self.assertEqual(abrir[0]["aba"], "tarefas")
        self.assertEqual(abrir[0]["destaque"], {"entidade": "tarefa", "id": tarefas[0]["id"]})
        self.assertEqual([p["modulo"] for p in corpo["passos"]], ["Tarefas", "Tarefas"])

    def test_brain_dump_gera_card_por_efeito_e_resumo_final(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "mercado", "valor": 45.9, "categoria": "mercado"})
            executores["registrar_tarefa"]({"titulo": "pagar boleto"})
            executores["registrar_meta"]({"titulo": "reserva", "valor": 15000.0, "prazo": "2026-12-22"})
            executores["registrar_lembrete"]({"titulo": "renovar CMA", "data": "2026-10-01"})
            executores["registrar_renda"]({"valor": 3000.0, "categoria": "salario", "descricao": "salario"})
            return "Feito.", [], fake_usage()

        corpo = self._chat(fake_chat)
        self._assert_envelope(corpo)
        tipos = [c["type"] for c in corpo["cards"]]
        self.assertEqual(tipos, ["transacao", "tarefas_criadas", "meta", "lembrete", "transacao", "resumo_final"])
        gasto, renda = corpo["cards"][0]["data"], corpo["cards"][4]["data"]
        self.assertEqual((gasto["entidade"], gasto["sentido"], gasto["valor"]), ("gasto", "saida", 45.9))
        self.assertEqual((renda["entidade"], renda["sentido"], renda["valor"]), ("renda", "entrada", 3000.0))
        meta = corpo["cards"][2]["data"]
        self.assertEqual((meta["valor_alvo"], meta["valor_guardado"], meta["percentual"], meta["falta"]), (15000.0, 0.0, 0.0, 15000.0))
        self.assertEqual(meta["prazo"], "2026-12-22")
        resumo = corpo["cards"][-1]["data"]
        self.assertEqual(resumo["passos_total"], 5)
        self.assertEqual(resumo["modulos"], ["Financas", "Tarefas", "Metas", "Lembretes"])
        textos = {linha["modulo"]: linha["texto"] for linha in resumo["linhas"]}
        self.assertEqual(textos["Financas"], "1 gasto registrado, 1 entrada registrada")
        self.assertNotIn("45", json.dumps(resumo))  # resumo_final nunca carrega valor

    def test_gasto_com_banco_mostra_meio_e_saldo(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 1000.0)

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "mercado", "valor": 150.0, "banco": "Nubank"})
            return "Registrado.", ["registrar_gasto"], fake_usage()

        corpo = self._chat(fake_chat)
        data = corpo["cards"][0]["data"]
        self.assertEqual(data["meio"], "Nubank")
        self.assertEqual(data["saldo"], {"conta": "nubank", "antes": 1000.0, "depois": 850.0})
        self.assertEqual(data["data"], date.today().isoformat())

    def test_executor_com_erro_vira_passo_com_erro_e_sem_card(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_medida"]({"tipo": "", "valor": 1})
            return "Nao deu.", [], fake_usage()

        corpo = self._chat(fake_chat)
        self.assertEqual(corpo["cards"], [])
        self.assertTrue(corpo["passos"][0]["erro"])
        self.assertEqual(corpo["passos"][0]["modulo"], "Saude")

    def test_historico_devolve_cards_da_resposta(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "lavar carro"})
            return "Anotado.", ["registrar_tarefa"], fake_usage()

        self._chat(fake_chat)
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertEqual(hist[0]["cards"], [])
        self.assertEqual(hist[1]["cards"][0]["type"], "tarefas_criadas")
        self.assertNotIn("cards_json", hist[1])

    def test_historico_com_card_ilegivel_nao_quebra(self):
        self.conn.execute(
            "INSERT INTO chat_mensagens (papel, texto, cards_json) VALUES ('assistant', 'x', '{nao e json')"
        )
        self.conn.commit()
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertEqual(hist[0]["cards"], [])

    def test_telegram_continua_recebendo_so_texto(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "x"})
            return "Anotei pelo Telegram.", ["registrar_tarefa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.assertEqual(app._telegram_chat_fn("anota x"), "Anotei pelo Telegram.")


class CaptureContratoTestCase(ContratoCardsBase):
    def test_captura_tarefa(self):
        parsed = {"tipo": "tarefa", "titulo": "Levar carro", "quando": "amanha", "quando_data": "2026-09-24", "hora": "14:00"}
        res = self._capture(parsed)
        self.assertEqual(res.status_code, 201)
        corpo = res.get_json()
        self._assert_envelope(corpo)
        # legado intacto
        self.assertEqual((corpo["tipo"], corpo["titulo"], corpo["quando"]), ("tarefa", "Levar carro", "amanha"))
        self.assertEqual(corpo["cards"][0]["type"], "tarefas_criadas")
        self.assertEqual(corpo["cards"][0]["data"]["tarefas"][0]["data"], "2026-09-24")
        self.assertEqual([p["modulo"] for p in corpo["passos"]], ["Captura", "Tarefas"])

    def test_captura_gasto_e_meta(self):
        corpo = self._capture({"tipo": "gasto", "titulo": "Uber", "valor": 23.5, "categoria": "transporte"}).get_json()
        self.assertEqual(corpo["valor"], 23.5)
        self.assertEqual(corpo["cards"][0]["type"], "transacao")
        self.assertEqual(corpo["cards"][0]["data"]["categoria"], "transporte")
        corpo = self._capture({"tipo": "meta", "titulo": "Viagem", "valor": 5000, "prazo": None}).get_json()
        self.assertEqual(corpo["cards"][0]["type"], "meta")
        self.assertEqual(corpo["cards"][0]["data"]["valor_alvo"], 5000.0)

    def test_captura_duvida_sem_card(self):
        res = self._capture({"duvida": "Isso e gasto ou tarefa?"})
        corpo = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(corpo["duvida"], "Isso e gasto ou tarefa?")
        self.assertEqual(corpo["cards"], [])
        self.assertEqual(corpo["resumo_texto"], "Isso e gasto ou tarefa?")

    def test_reenvio_idempotente_devolve_os_mesmos_cards(self):
        parsed = {"tipo": "tarefa", "titulo": "Unica"}
        primeiro = self._capture(parsed, client_id="abc-1").get_json()
        segundo = self._capture(parsed, client_id="abc-1").get_json()
        self.assertEqual(primeiro["cards"], segundo["cards"])
        n = self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(n, 1)

    def test_atalho_capturar_mantem_formato_legado_e_ganha_cards(self):
        parsed = {"tipo": "tarefa", "titulo": "Pelo Siri"}
        with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
            res = self.client.post("/api/atalho/capturar", json={"text": "anota pelo siri"})
        corpo = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(corpo["titulo"], "Pelo Siri")
        self.assertEqual(corpo["cards"][0]["type"], "tarefas_criadas")


class ModoVisitanteCardsTestCase(ContratoCardsBase):
    def _ativar(self):
        self.assertEqual(self.client.post("/api/modo-visitante", json={"ativar": True}).status_code, 200)

    def test_captura_gasto_nao_vaza_valor(self):
        self._ativar()
        res = self._capture({"tipo": "gasto", "titulo": "Presente", "valor": 7777.77, "categoria": "lazer"})
        self.assertNotIn(b"7777", res.data)
        corpo = res.get_json()
        self.assertTrue(corpo["cards"][0]["data"]["oculto"])
        self.assertNotIn("valor", corpo["cards"][0]["data"])
        self.assertNotIn("valor", corpo)

    def test_reenvio_idempotente_tambem_mascara(self):
        parsed = {"tipo": "meta", "titulo": "Carro", "valor": 8888.0}
        self._capture(parsed, client_id="vis-1")
        self._ativar()
        res = self._capture(parsed, client_id="vis-1")
        self.assertNotIn(b"8888", res.data)

    def test_chat_nao_vaza_valor_nem_na_prosa(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 5432.1)
        self._ativar()

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "joia", "valor": 6666.66, "banco": "nubank"})
            executores["registrar_meta"]({"titulo": "casa", "valor": 99999.0})
            return "Registrei R$ 6.666,66 e a meta de R$ 99.999,00.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "gastei"})
        for segredo in (b"6666", b"6.666", b"99999", b"99.999", b"5432", b"5.432"):
            self.assertNotIn(segredo, res.data)
        corpo = res.get_json()
        self.assertIn("R$ •••", corpo["resumo_texto"])
        self.assertEqual(corpo["cards"][1]["data"]["percentual"], 0.0)  # percentual fica

        hist = self.client.get("/api/chat/historico")
        for segredo in (b"6666", b"6.666", b"99999", b"5432"):
            self.assertNotIn(segredo, hist.data)

    def test_sem_modo_visitante_valor_aparece(self):
        res = self._capture({"tipo": "gasto", "titulo": "Presente", "valor": 7777.77, "categoria": "lazer"})
        self.assertIn(b"7777.77", res.data)


class CardsPurosTestCase(unittest.TestCase):
    def test_ocultar_valores_texto(self):
        self.assertEqual(cards.ocultar_valores_texto("gastei R$ 1.234,56 hoje"), "gastei R$ ••• hoje")
        self.assertEqual(cards.ocultar_valores_texto("R$-50"), "R$ •••")
        self.assertEqual(cards.ocultar_valores_texto("sem valor"), "sem valor")
        self.assertIsNone(cards.ocultar_valores_texto(None))

    def test_envelope_numera_ids(self):
        env = cards.envelope([cards.novo_card("meta", {}), cards.novo_card("meta", {})], "x", [])
        self.assertEqual([c["id"] for c in env["cards"]], ["c1", "c2"])

    def test_registro_so_tira_chaves_privadas_de_dict(self):
        reg = cards.RegistroExecucao()
        envolvidos = reg.envolver({"a": lambda e: "texto", "b": lambda e: {"ok": 1, "_x": 2}})
        self.assertEqual(envolvidos["a"]({}), "texto")
        self.assertEqual(envolvidos["b"]({}), {"ok": 1})
        self.assertEqual(len(reg.passos()), 2)
        self.assertEqual(reg.efeitos(), [])

    def test_mascarar_nao_altera_original(self):
        original = {"cards": [cards.novo_card("transacao", {"valor": 10.0, "saldo": {"antes": 1}})], "valor": 10.0}
        mascarado = cards.mascarar_visitante(original)
        self.assertIn("valor", original["cards"][0]["data"])
        self.assertNotIn("valor", mascarado["cards"][0]["data"])
        self.assertNotIn("saldo", mascarado["cards"][0]["data"])


class CardsSimplesBackendTestCase(ContratoCardsBase):
    """US-E3: endpoints que os botoes dos cards simples usam."""

    def test_despertar_liga_desliga_e_aparece_no_card(self):
        lembrete_id = db.create_lembrete(self.conn, "Renovar CMA", "2026-10-01")
        res = self.client.post(f"/api/lembretes/{lembrete_id}/despertar", json={"ativo": True})
        self.assertEqual(res.get_json(), {"ok": True, "ativo": True})
        card = cards.card_lembrete(self.conn, lembrete_id)
        self.assertTrue(card["data"]["despertar"])
        despertar = [a for a in card["actions"] if a["tipo"] == "despertar"][0]
        self.assertEqual((despertar["lembrete_id"], despertar["ativo"]), (lembrete_id, True))
        self.client.post(f"/api/lembretes/{lembrete_id}/despertar", json={"ativo": False})
        self.assertFalse(cards.card_lembrete(self.conn, lembrete_id)["data"]["despertar"])

    def test_despertar_valida_entrada(self):
        lembrete_id = db.create_lembrete(self.conn, "x", "2026-10-01")
        self.assertEqual(self.client.post(f"/api/lembretes/{lembrete_id}/despertar", json={"ativo": "sim"}).status_code, 400)
        self.assertEqual(self.client.post("/api/lembretes/9999/despertar", json={"ativo": True}).status_code, 404)

    def test_lembretes_para_despertar_so_no_dia_e_depois_do_horario(self):
        from datetime import datetime

        import notificacoes

        hoje = date(2026, 9, 23)
        a = db.create_lembrete(self.conn, "hoje ligado", hoje.isoformat())
        db.create_lembrete(self.conn, "hoje desligado", hoje.isoformat())
        c = db.create_lembrete(self.conn, "amanha ligado", "2026-09-24")
        d = db.create_lembrete(self.conn, "aniversario", "2001-09-23", recorrente=True)
        for i in (a, c, d):
            db.definir_despertar_lembrete(self.conn, i, True)
        cedo = notificacoes.lembretes_para_despertar(self.conn, datetime(2026, 9, 23, 8, 59))
        self.assertEqual(cedo, [])
        depois = notificacoes.lembretes_para_despertar(self.conn, datetime(2026, 9, 23, 9, 0))
        self.assertEqual(sorted(i for i, _ in depois), sorted([a, d]))
        self.assertIn('"hoje ligado"', dict(depois)[a])

    def test_reabrir_tarefa(self):
        cur = self.conn.execute("INSERT INTO tasks (title) VALUES ('x')")
        self.conn.commit()
        tid = cur.lastrowid
        self.client.post(f"/api/tasks/{tid}/complete")
        self.assertTrue(cards.card_tarefas_criadas(self.conn, [tid])["data"]["tarefas"][0]["concluida"])
        self.assertEqual(self.client.post(f"/api/tasks/{tid}/reabrir").status_code, 200)
        self.assertFalse(cards.card_tarefas_criadas(self.conn, [tid])["data"]["tarefas"][0]["concluida"])
        self.assertEqual(self.client.post("/api/tasks/9999/reabrir").status_code, 404)

    def test_card_meta_calcula_percentual_e_falta(self):
        goal_id = db.create_goal(self.conn, "Reserva", 15000.0, "2026-12-22")
        db.add_to_goal(self.conn, goal_id, 9000.0)
        data = cards.card_meta(self.conn, goal_id)["data"]
        self.assertEqual((data["percentual"], data["falta"]), (60.0, 6000.0))

    def test_card_de_id_inexistente_some_sem_erro(self):
        self.assertIsNone(cards.card_meta(self.conn, 999))
        self.assertIsNone(cards.card_lembrete(self.conn, 999))
        self.assertIsNone(cards.card_transacao(self.conn, "gasto", 999))
        self.assertIsNone(cards.card_transacao(self.conn, "outra", 1))
        self.assertIsNone(cards.card_tarefas_criadas(self.conn, [999]))
        self.assertEqual(cards.cards_dos_efeitos(self.conn, [{"entidade": "meta", "id": 999}, {"lixo": 1}]), [])


class DesfazerTestCase(ContratoCardsBase):
    """US-E5: Desfazer por token = ids exatos, um teste por tipo."""

    def _token(self, card):
        return [a for a in card["actions"] if a["tipo"] == "desfazer"][0]["token"]

    def _desfazer(self, token):
        return self.client.post(f"/api/desfazer/{token}")

    def _conta(self, tabela):
        return self.conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]

    def test_tarefa_desfaz_so_as_do_card(self):
        self.conn.execute("INSERT INTO tasks (title) VALUES ('antiga, nao pode sumir')")
        self.conn.commit()

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "a"})
            executores["registrar_tarefa"]({"titulo": "b"})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        card = corpo["cards"][0]
        alvo = [a for a in card["actions"] if a["tipo"] == "desfazer"][0]["alvo"]
        self.assertEqual([x["entidade"] for x in alvo], ["tarefa", "tarefa"])
        # depois do card ainda cria outra tarefa - desfazer NAO e "o ultimo"
        self.conn.execute("INSERT INTO tasks (title) VALUES ('depois')")
        self.conn.commit()
        res = self._desfazer(self._token(card))
        self.assertEqual(res.get_json(), {"ok": True, "desfeitos": 2})
        titulos = sorted(r[0] for r in self.conn.execute("SELECT title FROM tasks").fetchall())
        self.assertEqual(titulos, ["antiga, nao pode sumir", "depois"])

    def test_tarefa_recorrente_desfaz_modelo_e_instancias(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "academia", "recorrencia": "diaria", "hora": "07:00"})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        self.assertGreaterEqual(self._conta("tasks"), 1)
        self._desfazer(self._token(corpo["cards"][0]))
        self.assertEqual(self._conta("tasks"), 0)

    def test_gasto_desfaz_e_devolve_saldo(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 1000.0)

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "mercado", "valor": 150.0, "banco": "nubank"})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        self._desfazer(self._token(corpo["cards"][0]))
        self.assertEqual(self._conta("expenses"), 0)
        saldo = db.buscar_conta_por_nome(self.conn, "nubank")["saldo"]
        self.assertAlmostEqual(saldo, 1000.0)

    def test_renda_desfaz_e_devolve_saldo(self):
        conta_id = db.get_or_create_bank_account(self.conn, "inter", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 200.0)

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_renda"]({"valor": 50.0, "categoria": "freela", "banco": "inter"})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        self._desfazer(self._token(corpo["cards"][0]))
        self.assertEqual(self._conta("incomes"), 0)
        self.assertAlmostEqual(db.buscar_conta_por_nome(self.conn, "inter")["saldo"], 200.0)

    def test_lembrete_e_meta(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_lembrete"]({"titulo": "cma", "data": "2026-10-01"})
            executores["registrar_meta"]({"titulo": "carro", "valor": 1000.0})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        tipos = {c["type"]: c for c in corpo["cards"]}
        db.add_to_goal(self.conn, tipos["meta"]["data"]["id"], 100.0)
        self._desfazer(self._token(tipos["lembrete"]))
        self.assertEqual(self._conta("lembretes"), 0)
        self.assertEqual(self._conta("goals"), 1)  # outro card, independente
        self._desfazer(self._token(tipos["meta"]))
        self.assertEqual((self._conta("goals"), self._conta("goal_deposits")), (0, 0))

    def test_captura_tambem_tem_desfazer(self):
        corpo = self._capture({"tipo": "gasto", "titulo": "Uber", "valor": 23.5, "categoria": "transporte"}).get_json()
        self.assertEqual(self._desfazer(self._token(corpo["cards"][0])).status_code, 200)
        self.assertEqual(self._conta("expenses"), 0)

    def test_brain_dump_cada_card_independente(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_gasto"]({"titulo": "pao", "valor": 5.0})
            executores["registrar_tarefa"]({"titulo": "x"})
            executores["registrar_meta"]({"titulo": "m", "valor": 10.0})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        tokens = [self._token(c) for c in corpo["cards"] if c["type"] != "resumo_final"]
        self.assertEqual(len(set(tokens)), 3)
        self.assertFalse([a for a in corpo["cards"][-1]["actions"] if a["tipo"] == "desfazer"])  # resumo nao desfaz
        self._desfazer(tokens[1])
        self.assertEqual((self._conta("expenses"), self._conta("tasks"), self._conta("goals")), (1, 0, 1))

    def test_duas_vezes_e_token_desconhecido(self):
        corpo = self._capture({"tipo": "tarefa", "titulo": "x"}).get_json()
        token = self._token(corpo["cards"][0])
        self.assertEqual(self._desfazer(token).status_code, 200)
        self.assertEqual(self._desfazer(token).status_code, 409)
        self.assertEqual(self._desfazer("nao-existe").status_code, 404)
        self.assertEqual(self._desfazer("x" * 500).status_code, 404)

    def test_item_ja_apagado_a_mao_e_pulado(self):
        corpo = self._capture({"tipo": "tarefa", "titulo": "x"}).get_json()
        self.conn.execute("DELETE FROM tasks")
        self.conn.commit()
        res = self._desfazer(self._token(corpo["cards"][0]))
        self.assertEqual(res.get_json(), {"ok": True, "desfeitos": 0})

    def test_historico_marca_card_desfeito(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_tarefa"]({"titulo": "x"})
            return "ok", [], fake_usage()

        corpo = self._chat(fake_chat)
        self._desfazer(self._token(corpo["cards"][0]))
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertTrue(hist[1]["cards"][0]["desfeito"])

    def test_evento_nao_criado_pelo_painel_e_recusado_sem_apagar_nada(self):
        tid = self.conn.execute("INSERT INTO tasks (title) VALUES ('junto')").lastrowid
        self.conn.commit()
        token = db.criar_acao_desfazer(
            self.conn, [{"entidade": "tarefa", "id": tid}, {"entidade": "evento", "uid": "de-fora@icloud"}]
        )
        res = self._desfazer(token)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self._conta("tasks"), 1)  # tudo ou nada
        self.assertIsNone(db.obter_acao_desfazer(self.conn, token)["desfeito_em"])

    def _evento_do_painel(self):
        self.conn.execute(
            "INSERT INTO eventos_criados (uid, titulo, inicio, fim) "
            "VALUES ('meu@painel', 'x', '2026-09-29T14:00', '2026-09-29T15:00')"
        )
        self.conn.commit()
        return db.criar_acao_desfazer(self.conn, [{"entidade": "evento", "uid": "meu@painel"}])

    def test_evento_criado_pelo_painel_sem_caldav_configurado_nao_apaga(self):
        token = self._evento_do_painel()
        with patch("caldav_client.configurado", return_value=False), patch("caldav_client.apagar_evento") as apagar:
            self.assertEqual(self._desfazer(token).status_code, 503)
        apagar.assert_not_called()
        self.assertEqual(self._conta("eventos_criados"), 1)

    def test_evento_criado_pelo_painel_com_caldav_apaga(self):
        token = self._evento_do_painel()
        with patch("caldav_client.configurado", return_value=True), patch("caldav_client.apagar_evento") as apagar:
            res = self._desfazer(token)
        self.assertEqual(res.status_code, 200)
        apagar.assert_called_once_with("meu@painel")
        self.assertEqual(self._conta("eventos_criados"), 0)

    def test_falha_no_icloud_desfaz_nada(self):
        token = self._evento_do_painel()
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.apagar_evento", side_effect=ConnectionError("sem rede")
        ):
            self.assertEqual(self._desfazer(token).status_code, 502)
        self.assertEqual(self._conta("eventos_criados"), 1)
        self.assertIsNone(db.obter_acao_desfazer(self.conn, token)["desfeito_em"])

    def test_criar_acao_desfazer_ignora_lixo(self):
        self.assertIsNone(db.criar_acao_desfazer(self.conn, [{"entidade": "usuario", "id": 1}, "x", {"entidade": "tarefa"}]))


if __name__ == "__main__":
    unittest.main()
