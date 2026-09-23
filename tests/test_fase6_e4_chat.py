"""Fase 6 (faixa E4) - chat produzindo cards dos modulos novos.

US-E7: consulta que vira card resolvida no classificador LOCAL (sem API),
tools dos modulos da E2 (habito, projeto, viagem, agenda, treino, agua)
ligadas ao contrato de cards com Desfazer, card sugestao com horario real e
a caixa "Com a sua rotina em mente" alimentada pela memoria (US-E10).
US-E6: brain dump devolvendo o contrato (8+ cards + resumo_final).

Banco sempre temporario, IA sempre mockada, iCloud sempre mockado.
"""

import os
import random
import string
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import aprendizado  # noqa: E402
import cards  # noqa: E402

PIN_TESTE = "123456"


def fake_usage(model="claude-sonnet-4-5", cost=0.001):
    return {"model": model, "input_tokens": 100, "output_tokens": 20, "cost_usd": cost}


def ia_proibida(*_a, **_k):
    raise AssertionError("a IA nao podia ter sido chamada - era pra resolver local")


class Base(unittest.TestCase):
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
        self.hoje = date.today()

    def tearDown(self):
        self.conn.close()

    def chat_local(self, mensagem):
        with patch("claude_client.chat", side_effect=ia_proibida), patch(
            "claude_client.classify_intent", side_effect=ia_proibida
        ):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    def chat_ia(self, fake_chat, mensagem="oi"):
        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": mensagem})
        self.assertEqual(res.status_code, 200, res.get_json())
        return res.get_json()

    def tipos(self, corpo):
        return [c["type"] for c in corpo["cards"]]

    def desfazer_de(self, card):
        acoes = [a for a in card["actions"] if a["tipo"] == "desfazer"]
        return acoes[0]["token"] if acoes else None

    def assert_contrato(self, corpo):
        self.assertIsInstance(corpo["cards"], list)
        for c in corpo["cards"]:
            self.assertIn(c["type"], cards.TIPOS_CARD)
            self.assertFalse([k for k in c if k.startswith("_")], c)
        for p in corpo["passos"]:
            self.assertEqual(set(p) - {"erro"}, {"modulo", "descricao", "ms"})


# ---------------------------------------------------------------------------
# US-E7 (c): banco "pergunta -> onde buscar" no classificador local
# ---------------------------------------------------------------------------


class BancoConsultaTestCase(unittest.TestCase):
    def test_exemplos_do_nectar(self):
        c = aprendizado.consulta_conhecida("Me mostra o projeto da viagem e a meta")
        self.assertEqual(c["acao"], "consultar")
        self.assertEqual(c["parametros"]["fontes"], [{"fonte": "projeto", "termo": "viagem"}, {"fonte": "meta"}])
        c = aprendizado.consulta_conhecida("como foram meus treinos nos últimos 7 dias?")
        self.assertEqual(c["parametros"]["fontes"], [{"fonte": "treinos", "dias": 7}])
        c = aprendizado.consulta_conhecida("Tomei um copo de água.")
        self.assertEqual(c, {"acao": "registrar_checkin", "parametros": {"campo": "hidratacao"}})
        c = aprendizado.consulta_conhecida("como encaixo meu treino hoje?")
        self.assertEqual(c["parametros"]["fontes"], [{"fonte": "sugestao", "titulo": "treino"}])

    def test_acao_ou_assunto_fora_do_banco_nunca_resolve_local(self):
        for texto in [
            "quero uma meta de 5 mil pra viagem",
            "cria o projeto reforma do quarto",
            "quanto eu gastei esse mes?",
            "tomei um copo de agua e gastei 5 no pao",
            "mostra minhas tarefas de hoje",
            "gastei 50 no mercado",
            "me lembra de beber agua as 15h",
            "como esta o saldo da meta no banco?",
            "",
            "   ",
        ]:
            self.assertIsNone(aprendizado.consulta_conhecida(texto), texto)

    def test_fuzz_nunca_levanta_excecao(self):
        rnd = random.Random(42)
        alfabeto = string.ascii_letters + string.digits + " ?!.,çãéíóú\n\t$%{}[]<>\"'\\"
        entradas = [None, 123, [], {}, "a" * 10000, "?" * 500, "projeto " * 300, "\x00\x01"]
        entradas += ["".join(rnd.choice(alfabeto) for _ in range(rnd.randint(0, 200))) for _ in range(80)]
        for e in entradas:
            resultado = aprendizado.consulta_conhecida(e)
            self.assertTrue(resultado is None or resultado["acao"] in ("consultar", "registrar_checkin"))
            if resultado and resultado["acao"] == "consultar":
                self.assertTrue(aprendizado.fontes_validas(resultado["parametros"]))

    def test_fontes_validas_filtra_lixo(self):
        self.assertEqual(aprendizado.fontes_validas({"pergunta": "x"}), [])
        self.assertEqual(aprendizado.fontes_validas(None), [])
        self.assertEqual(
            aprendizado.fontes_validas({"fontes": [{"fonte": "meta"}, {"fonte": "hackear"}, "x", 3]}),
            [{"fonte": "meta"}],
        )


class ClassificarIntentLocalTestCase(Base):
    def test_intent_classificar_resolve_consulta_sem_api(self):
        with patch("claude_client.classify_intent", side_effect=ia_proibida):
            res = self.client.post("/api/intent/classificar", json={"texto": "me mostra meus habitos"})
        corpo = res.get_json()
        self.assertEqual(corpo["acao"], "consultar")
        self.assertEqual(corpo["parametros"]["fontes"], [{"fonte": "habitos"}])
        self.assertFalse(corpo["precisa_confirmacao"])
        self.assertEqual(corpo["confianca"], aprendizado.CONFIANCA_PADRAO_INTENT)

    def test_intent_fora_do_banco_continua_chamando_a_ia(self):
        chamado = []

        def fake(texto, contexto_correcao=None):
            chamado.append(texto)
            return {"acao": "consultar", "confianca": 0.9, "parametros": {}, "precisa_confirmacao": False}, fake_usage()

        with patch("claude_client.classify_intent", side_effect=fake):
            self.client.post("/api/intent/classificar", json={"texto": "quanto eu gastei esse mes?"})
        self.assertEqual(chamado, ["quanto eu gastei esse mes?"])

    def test_padrao_aprendido_de_outra_acao_vence_a_regra(self):
        # correcao manual do Alex (US-B3) vale mais que o banco de regras
        aprendizado.confirmar_padrao_intent(self.conn, "mostra minhas metas", "navegar_tela", {"tela": "gastos"},
                                            forcar_confianca_alta=True)
        resultado, _ = app._classificar_intent(self.conn, "mostra minhas metas", somente_local=True)
        self.assertEqual(resultado["acao"], "navegar_tela")

    def test_padrao_consultar_sem_fontes_ganha_as_fontes_da_regra(self):
        aprendizado.confirmar_padrao_intent(self.conn, "mostra minhas metas", "consultar", {"pergunta": "metas"},
                                            forcar_confianca_alta=True)
        resultado, _ = app._classificar_intent(self.conn, "mostra minhas metas", somente_local=True)
        self.assertEqual(resultado["acao"], "consultar")
        self.assertEqual(resultado["parametros"]["fontes"], [{"fonte": "meta"}])

    def test_somente_local_nunca_chama_api(self):
        with patch("claude_client.classify_intent", side_effect=ia_proibida):
            self.assertEqual(app._classificar_intent(self.conn, "bom dia, tudo bem?", somente_local=True), (None, None))


# ---------------------------------------------------------------------------
# US-E7 (b): consultas no chat -> cards, sem API
# ---------------------------------------------------------------------------


class ConsultaChatLocalTestCase(Base):
    def _viagem_e_meta(self):
        ida = (self.hoje + timedelta(days=40)).isoformat()
        volta = (self.hoje + timedelta(days=45)).isoformat()
        viagem_id = db.create_viagem(self.conn, "Gramado", ida, volta, "ferias")
        db.substituir_itens_viagem(self.conn, viagem_id, ["Casaco", "Carregador", "Documento"])
        self.conn.execute("UPDATE viagem_itens SET feito = 1 WHERE texto = 'Casaco'")
        self.conn.commit()
        meta_id = db.create_goal(self.conn, "Reserva de emergencia", 15000.0, "2026-12-22")
        self.conn.execute("UPDATE goals SET valor_guardado = 9000 WHERE id = ?", (meta_id,))
        self.conn.commit()
        return viagem_id, meta_id

    def test_projeto_da_viagem_e_a_meta_viram_dois_cards_sem_api(self):
        viagem_id, meta_id = self._viagem_e_meta()
        corpo = self.chat_local("Me mostra o projeto da viagem e a meta")
        self.assert_contrato(corpo)
        self.assertEqual(self.tipos(corpo), ["projeto_viagem", "meta"])  # consulta nao gera resumo_final
        viagem = corpo["cards"][0]["data"]
        self.assertEqual((viagem["origem"], viagem["id"], viagem["titulo"]), ("viagem", viagem_id, "Viagem pra Gramado"))
        self.assertEqual((viagem["feitas"], viagem["total"]), (1, 3))
        self.assertEqual(viagem["etapas"][0], {"titulo": "Casaco", "feito": True, "data": None})
        meta = corpo["cards"][1]["data"]
        self.assertEqual((meta["id"], meta["percentual"], meta["valor_guardado"]), (meta_id, 60.0, 9000.0))
        self.assertTrue(meta["consulta"] and viagem["consulta"])  # aditivo: o front nao diz "Meta criada"
        for c in corpo["cards"]:
            self.assertFalse([a for a in c["actions"] if a["tipo"] == "desfazer"], "consulta nao tem Desfazer")
            self.assertTrue([a for a in c["actions"] if a["tipo"] == "abrir_aba"])
        self.assertEqual([p["modulo"] for p in corpo["passos"]], ["Projetos", "Metas"])
        self.assertEqual(corpo["resposta"], corpo["resumo_texto"])
        self.assertNotIn("9000", corpo["resumo_texto"])
        self.assertNotIn("R$", corpo["resumo_texto"])

    def test_consulta_local_fica_no_historico_com_cards(self):
        self._viagem_e_meta()
        self.chat_local("mostra minhas metas")
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertEqual(hist[-1]["cards"][0]["type"], "meta")

    def test_meta_em_modo_visitante_sai_sem_valor(self):
        self._viagem_e_meta()
        with patch("app._modo_visitante_ativo", return_value=True):
            corpo = self.chat_local("mostra minhas metas")
        meta = corpo["cards"][0]["data"]
        self.assertTrue(meta["oculto"])
        self.assertNotIn("valor_guardado", meta)
        self.assertNotIn("valor_alvo", meta)
        self.assertEqual(meta["percentual"], 60.0)

    def test_projeto_generico_com_termo_aproximado(self):
        pid = db.create_projeto(self.conn, "Reformar o quarto", (self.hoje + timedelta(days=30)).isoformat())
        db.adicionar_etapa_projeto(self.conn, pid, "Comprar tinta", None)
        e2 = db.adicionar_etapa_projeto(self.conn, pid, "Pintar", (self.hoje + timedelta(days=10)).isoformat())
        db.concluir_etapa_projeto(self.conn, db.list_etapas_projeto(self.conn, pid)[0]["id"])
        db.create_projeto(self.conn, "Lancar o curso", None)
        corpo = self.chat_local("como vai o projeto reforma do quarto?")
        self.assertEqual(self.tipos(corpo), ["projeto_viagem"])
        d = corpo["cards"][0]["data"]
        self.assertEqual((d["origem"], d["id"], d["titulo"], d["percentual"]), ("projeto", pid, "Reformar o quarto", 50))
        self.assertEqual(d["proximo_marco"]["titulo"], "Pintar")
        self.assertEqual(d["proximo_marco"]["data"], (self.hoje + timedelta(days=10)).isoformat())
        self.assertEqual(d["status"], "no_rumo")
        self.assertTrue(0 <= d["hoje_fracao"] <= 1)
        self.assertIsNotNone(e2)

    def test_sem_projeto_responde_local_sem_card(self):
        corpo = self.chat_local("me mostra o projeto")
        self.assertEqual(corpo["cards"], [])
        self.assertIn("projeto", corpo["resumo_texto"].lower())

    def test_treinos_dos_ultimos_7_dias(self):
        for dias_atras, grupo, minutos in [(0, "Peito", 60), (2, "corrida", 40), (5, "Peito", 50), (9, "Perna", 30)]:
            db.registrar_treino(self.conn, (self.hoje - timedelta(days=dias_atras)).isoformat(), grupo, minutos, None)
        corpo = self.chat_local("como foram meus treinos nos últimos 7 dias?")
        self.assertEqual(self.tipos(corpo), ["saude_treino"])
        d = corpo["cards"][0]["data"]
        self.assertEqual(d["periodo"], "últimos 7 dias")
        self.assertEqual(len(d["sessoes"]), 3)  # o de 9 dias atras fica fora
        self.assertEqual(sum(s["minutos"] for s in d["sessoes"]), 150)
        self.assertEqual(d["sessoes"][1]["atividade"], "Corrida")
        self.assertFalse(d["registrado"])

    def test_tomei_um_copo_de_agua_incrementa_e_mostra_saude_do_dia(self):
        db.registrar_hidratacao(self.conn, self.hoje.isoformat())
        corpo = self.chat_local("tomei um copo de agua")
        self.assertEqual(self.tipos(corpo), ["saude_dia"])
        d = corpo["cards"][0]["data"]
        self.assertEqual((d["agua_copos"], d["registrado"], d["data"]), (2, "agua", self.hoje.isoformat()))
        self.assertEqual(db.contar_hidratacao_dia(self.conn, self.hoje.isoformat()), 2)
        self.assertIn("2 hoje", corpo["resumo_texto"])
        token = self.desfazer_de(corpo["cards"][0])
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual(db.contar_hidratacao_dia(self.conn, self.hoje.isoformat()), 1)

    def test_habitos_consulta_semana_seg_dom(self):
        hid = db.create_habito(self.conn, "Meditar", "15 min", "n_vezes_semana", None, 3, "08:00")
        db.alternar_habito_dia(self.conn, self.hoje.isoformat(), hid)
        corpo = self.chat_local("como estão meus hábitos?")
        self.assertEqual(self.tipos(corpo), ["habito"])
        d = corpo["cards"][0]["data"]
        self.assertEqual(len(d["semana"]), 7)
        self.assertEqual(date.fromisoformat(d["semana"][0]["data"]).weekday(), 0)
        self.assertTrue(next(s for s in d["semana"] if s["data"] == self.hoje.isoformat())["feito"])
        self.assertEqual(d["frequencia"], "3x por semana · qualquer dia conta")
        self.assertEqual(d["contexto"], "1 de 3 vezes nesta semana.")


class SugestaoTestCase(Base):
    def _agora(self, hh, mm=0):
        return patch("app._agora", return_value=datetime.combine(self.hoje, time(hh, mm)))

    def test_como_encaixo_meu_treino_hoje_horario_real_e_memoria_da_rotina(self):
        hoje = self.hoje.isoformat()
        eventos = [
            {"titulo": "Trabalho", "inicio": f"{hoje}T08:00:00", "fim": f"{hoje}T12:00:00", "dia_inteiro": False},
            {"titulo": "Obra", "inicio": f"{hoje}T13:00:00", "fim": f"{hoje}T17:30:00", "dia_inteiro": False},
        ]
        db.registrar_treino(self.conn, hoje, "Peito", 50, None)
        db.registrar_treino(self.conn, hoje, "Perna", 40, None)
        with self._agora(7, 10), patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.eventos_do_dia", return_value=eventos
        ):
            corpo = self.chat_local("como encaixo meu treino hoje?")
        self.assertEqual(self.tipos(corpo), ["sugestao"])
        d = corpo["cards"][0]["data"]
        self.assertEqual(d["inicio"], f"{hoje}T17:30")  # 17:30-22:00 e o maior espaco
        self.assertEqual(d["duracao_min"], 45)  # media dos treinos registrados
        self.assertEqual(d["titulo"], "Treino")
        self.assertIn("17:30 às 22:00", d["porque"])
        self.assertIn("Treino sem horario fixo", d["porque"])  # memoria sua_rotina (US-E10)
        self.assertIn("17:30", corpo["resumo_texto"])

    def test_sugestao_nunca_no_passado(self):
        with self._agora(20, 5):
            corpo = self.chat_local("como encaixo meu treino hoje?")
        self.assertEqual(corpo["cards"][0]["data"]["inicio"], f"{self.hoje.isoformat()}T20:15")

    def test_dia_acabando_sem_espaco_nao_inventa_horario(self):
        with self._agora(21, 40):
            corpo = self.chat_local("como encaixo meu treino hoje?")
        self.assertEqual(corpo["cards"], [])
        self.assertIn("não sobrou", corpo["resumo_texto"])

    def test_memoria_editada_pelo_alex_aparece_na_caixa(self):
        self.conn.execute("UPDATE memorias SET texto = 'Prefere treinar depois das 18h' WHERE texto LIKE 'Treino sem%'")
        self.conn.commit()
        with self._agora(7):
            corpo = self.chat_local("que horas eu vou pra academia hoje?")
        self.assertIn("Prefere treinar depois das 18h", corpo["cards"][0]["data"]["porque"])

    def test_tool_da_ia_tambem_gera_card(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            r = executores["sugerir_horario_livre"]({"duracao_minutos": 45, "titulo": "estudar meteorologia"})
            self.assertTrue(r["encontrado"])
            self.assertNotIn("_efeito", r)
            return "Sugeri um horario.", ["sugerir_horario_livre"], fake_usage()

        with self._agora(7):
            corpo = self.chat_ia(fake_chat, "acha um horario pra eu estudar meteo")
        self.assertEqual(self.tipos(corpo), ["sugestao"])
        self.assertEqual(corpo["cards"][0]["data"]["titulo"], "Estudar meteorologia")


class BancoCresceTestCase(Base):
    def test_resposta_da_ia_so_com_consulta_vira_padrao_local(self):
        db.create_habito(self.conn, "Ler", None, "diario", None, None, None)
        frase = "e ai, como to indo nos meus rituais"
        self.assertIsNone(aprendizado.consulta_conhecida(frase))
        chamadas = []

        def fake_chat(mensagens, contexto, memorias, executores):
            chamadas.append(1)
            executores["consultar_habitos"]({})
            return "Olha ai.", ["consultar_habitos"], fake_usage()

        for _ in range(aprendizado.LIMIAR_CONFIRMACOES_PADRAO_INTENT):
            corpo = self.chat_ia(fake_chat, frase)
            self.assertEqual(self.tipos(corpo), ["habito"])
        self.assertEqual(len(chamadas), 3)
        corpo = self.chat_local(frase)  # 4a vez: local, sem IA
        self.assertEqual(self.tipos(corpo), ["habito"])
        padrao = db.buscar_padrao_intent(self.conn, aprendizado.normalizar_texto_intent(frase))
        self.assertEqual(padrao["parametros"], {"fontes": [{"fonte": "habitos"}]})

    def test_ia_que_cria_algo_nao_ensina_padrao(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["consultar_habitos"]({})
            executores["registrar_tarefa"]({"titulo": "x"})
            return "ok", [], fake_usage()

        self.chat_ia(fake_chat, "frase mista qualquer")
        self.assertIsNone(db.buscar_padrao_intent(self.conn, "frase mista qualquer"))

    def test_ia_sem_ferramenta_nao_ensina(self):
        self.chat_ia(lambda *a: ("Oi!", [], fake_usage()), "bom dia")
        self.assertIsNone(db.buscar_padrao_intent(self.conn, "bom dia"))


# ---------------------------------------------------------------------------
# US-E7 (a): tools dos modulos -> cards com Desfazer
# ---------------------------------------------------------------------------


class ToolsModulosTestCase(Base):
    def test_registrar_habito_card_e_desfazer(self):
        db.create_habito(self.conn, "Ler", None, "diario", None, None, None)

        def fake_chat(mensagens, contexto, memorias, executores):
            r = executores["registrar_habito"]({"nome": "Meditar", "meta": "15 min", "frequencia_tipo": "dias_semana",
                                                "dias_semana": [0, 2, 4], "horario": "08:00"})
            self.assertEqual(set(r), {"ok", "habito_id"})
            return "Criei.", ["registrar_habito"], fake_usage()

        corpo = self.chat_ia(fake_chat, "quero meditar 15 min seg qua sex as 8h")
        self.assert_contrato(corpo)
        d = corpo["cards"][0]["data"]
        self.assertEqual((d["nome"], d["meta"], d["frequencia"], d["horario"]), ("Meditar", "15 min", "seg, qua, sex", "08:00"))
        self.assertEqual((d["ativos_antes"], d["ativos_depois"]), (1, 2))
        self.assertEqual([s["feito"] for s in d["semana"]], [False] * 7)
        abrir = [a for a in corpo["cards"][0]["actions"] if a["tipo"] == "abrir_aba"][0]
        self.assertEqual((abrir["aba"], abrir["destaque"]["entidade"]), ("vida", "habito"))
        token = self.desfazer_de(corpo["cards"][0])
        self.assertEqual(self.client.post(f"/api/desfazer/{token}").status_code, 200)
        self.assertEqual([h["nome"] for h in db.list_habitos(self.conn)], ["Ler"])

    def test_marcar_habito_desfazer_volta_o_dia(self):
        hid = db.create_habito(self.conn, "Meditar", None, "diario", None, None, None)

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["marcar_habito"]({"nome": "medit"})
            return "Marquei.", ["marcar_habito"], fake_usage()

        corpo = self.chat_ia(fake_chat, "meditei")
        d = corpo["cards"][0]["data"]
        self.assertEqual(d["contexto"], "Marcado como feito hoje.")
        self.assertTrue(next(s for s in d["semana"] if s["data"] == self.hoje.isoformat())["feito"])
        token = self.desfazer_de(corpo["cards"][0])
        self.client.post(f"/api/desfazer/{token}")
        self.assertFalse(db.habito_marcado(self.conn, self.hoje.isoformat(), hid))
        # desmarcar pelo chat e desfazer marca de novo
        corpo = self.chat_ia(fake_chat, "meditei")
        corpo = self.chat_ia(fake_chat, "desmarca meditar")
        self.assertEqual(corpo["cards"][0]["data"]["contexto"], "Desmarcado hoje.")
        self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][0])}")
        self.assertTrue(db.habito_marcado(self.conn, self.hoje.isoformat(), hid))

    def test_projeto_etapa_concluir_cards_e_desfazer(self):
        prazo = (self.hoje + timedelta(days=60)).isoformat()

        def criar(mensagens, contexto, memorias, executores):
            executores["criar_projeto"]({"nome": "Lancamento do curso", "prazo_final": prazo})
            executores["adicionar_etapa"]({"nome_projeto": "lancamento", "texto": "Gravar aulas"})
            executores["adicionar_etapa"]({"nome_projeto": "lancamento", "texto": "Editar"})
            return "Feito.", [], fake_usage()

        corpo = self.chat_ia(criar, "projeto novo")
        self.assertEqual(self.tipos(corpo), ["projeto_viagem"] * 3 + ["resumo_final"])
        ultimo = corpo["cards"][2]["data"]
        self.assertEqual((ultimo["total"], ultimo["feitas"], ultimo["percentual"], ultimo["prazo"]), (2, 0, 0, prazo))
        self.assertEqual(ultimo["proximo_marco"]["titulo"], "Gravar aulas")
        # desfaz so a etapa "Editar"
        self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][2])}")
        pid = db.list_projetos(self.conn)[0]["id"]
        self.assertEqual([e["texto"] for e in db.list_etapas_projeto(self.conn, pid)], ["Gravar aulas"])

        def concluir(mensagens, contexto, memorias, executores):
            executores["concluir_etapa"]({"nome_projeto": "lancamento"})
            return "Concluida.", [], fake_usage()

        corpo = self.chat_ia(concluir, "gravei as aulas")
        self.assertEqual(corpo["cards"][0]["data"]["percentual"], 100)
        self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][0])}")
        self.assertEqual(db.list_etapas_projeto(self.conn, pid)[0]["feita"], 0)

    def test_registrar_viagem_vira_card_de_viagem(self):
        ida = (self.hoje + timedelta(days=80)).isoformat()

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_viagem"]({"destino": "Gramado", "data_ida": ida})
            return "Anotei.", [], fake_usage()

        corpo = self.chat_ia(fake_chat, "vou pra gramado")
        d = corpo["cards"][0]["data"]
        self.assertEqual((d["origem"], d["titulo"], d["prazo"]), ("viagem", "Viagem pra Gramado", ida))
        self.assertEqual(d["proximo_marco"], {"titulo": "Ida", "data": ida})
        self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][0])}")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM viagens").fetchone()[0], 0)

    def test_agendar_evento_card_agenda_e_desfazer_so_do_painel(self):
        def fake_criar(titulo, inicio, fim, lembrar=None):
            return {"uid": "uid-e4", "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}

        def fake_chat(mensagens, contexto, memorias, executores):
            executores["agendar_evento"]({"titulo": "Reuniao com o contador", "data": "2026-09-29",
                                          "hora_inicio": "14:00", "hora_fim": "15:00", "lembrar_min_antes": 30})
            return "Agendei.", [], fake_usage()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.criar_evento", side_effect=fake_criar
        ):
            corpo = self.chat_ia(fake_chat, "reuniao terca 14h")
        d = corpo["cards"][0]["data"]
        self.assertEqual(corpo["cards"][0]["type"], "agenda")
        self.assertEqual(
            (d["titulo"], d["inicio"], d["fim"], d["lembrar_min_antes"], d["uid"], d["confirmado"]),
            ("Reuniao com o contador", "2026-09-29T14:00", "2026-09-29T15:00", 30, "uid-e4", True),
        )
        desfazer = [a for a in corpo["cards"][0]["actions"] if a["tipo"] == "desfazer"][0]
        self.assertEqual(desfazer["alvo"], [{"entidade": "evento", "uid": "uid-e4"}])
        with patch("caldav_client.configurado", return_value=True), patch("caldav_client.apagar_evento") as apagar:
            res = self.client.post(f"/api/desfazer/{desfazer['token']}")
        self.assertEqual(res.status_code, 200)
        apagar.assert_called_once_with("uid-e4")
        self.assertIsNone(db.evento_criado_pelo_painel(self.conn, "uid-e4"))

    def test_agenda_nao_configurada_nao_gera_card(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            r = executores["agendar_evento"]({"titulo": "x", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00"})
            self.assertIn("erro", r)
            return "Nao deu.", [], fake_usage()

        with patch("caldav_client.configurado", return_value=False):
            corpo = self.chat_ia(fake_chat)
        self.assertEqual(corpo["cards"], [])
        self.assertTrue(corpo["passos"][0].get("erro"))

    def test_registrar_treino_card_registrado_e_desfazer(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            executores["registrar_treino"]({"grupo": "costas", "duracao_min": 55})
            return "Boa.", [], fake_usage()

        corpo = self.chat_ia(fake_chat, "treinei costas 55 min")
        d = corpo["cards"][0]["data"]
        self.assertTrue(d["registrado"])
        self.assertEqual(d["sessoes"][0], {"atividade": "Costas", "fonte": "Painel", "minutos": 55,
                                           "data": self.hoje.isoformat()})
        self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][0])}")
        self.assertEqual(db.list_treinos(self.conn), [])

    def test_desfazer_habito_marcacao_com_dado_forjado_e_ignorado(self):
        self.assertIsNone(db.criar_acao_desfazer(self.conn, [{"entidade": "habito_marcacao", "id": 1, "data": "x", "feito": True}]))
        self.assertIsNone(db.criar_acao_desfazer(self.conn, [{"entidade": "habito_marcacao", "id": 1, "data": "2026-09-23", "feito": "sim"}]))


class AdaptadoresTestCase(unittest.TestCase):
    def test_semana_seg_dom(self):
        quarta = date(2026, 9, 23)
        semana = cards.semana_seg_dom({"2026-09-21", "2026-09-23", "2026-09-20"}, quarta)
        self.assertEqual([s["data"] for s in semana][0], "2026-09-21")
        self.assertEqual([s["data"] for s in semana][-1], "2026-09-27")
        self.assertEqual([s["feito"] for s in semana], [True, False, True, False, False, False, False])
        domingo = cards.semana_seg_dom(set(), date(2026, 9, 27))
        self.assertEqual(domingo[0]["data"], "2026-09-21")

    def test_projeto_para_card_escala_hoje_fracao(self):
        detalhe = {"id": 3, "nome": "X", "criado_em": "2026-09-01 10:00:00", "prazo_final": "2026-10-01",
                   "status": "atrasado", "etapas": [{"texto": "a", "feita": 1, "data_prevista": None, "feita_em": "2026-09-05 1"}],
                   "percentual": 100, "etapas_feitas": 1, "total_etapas": 1, "proxima_etapa": None, "posicao_hoje": 73}
        d = cards.projeto_para_card(detalhe)
        self.assertEqual(d["hoje_fracao"], 0.73)
        self.assertEqual(d["inicio"], "2026-09-01")
        self.assertEqual(d["etapas"], [{"titulo": "a", "feito": True, "data": "2026-09-05"}])
        self.assertIsNone(d["proximo_marco"])
        self.assertIsNone(cards.projeto_para_card({**detalhe, "posicao_hoje": None})["hoje_fracao"])

    def test_frequencia_habito(self):
        self.assertEqual(cards.texto_frequencia_habito({"frequencia_tipo": "diario"}), "todo dia")
        self.assertEqual(cards.texto_frequencia_habito({"frequencia_tipo": "dias_semana", "dias_semana": "6,0"}), "seg, dom")


# ---------------------------------------------------------------------------
# US-E6: brain dump produzindo cards
# ---------------------------------------------------------------------------

TEXTO_NECTAR = (
    "Semana que vem vou pra Gramado de 10 a 15 de dezembro. Gastei 45,90 no mercado e 32 de uber. "
    "Caiu o salario, 5 mil. Quero comecar a meditar 10 minutos todo dia de manha e ja fiz academia hoje. "
    "Me lembra de renovar o CMA dia 1 de outubro. Reuniao com o contador terca as 14h, lembra 30 min antes."
)


class BrainDumpCardsTestCase(Base):
    def _fake_nectar(self, mensagens, contexto, memorias, executores):
        self.assertEqual(mensagens[-1]["content"], TEXTO_NECTAR)
        executores["registrar_viagem"]({"destino": "Gramado", "data_ida": "2026-12-10", "data_volta": "2026-12-15"})
        executores["registrar_gasto"]({"titulo": "Mercado", "valor": 45.9, "categoria": "mercado"})
        executores["registrar_gasto"]({"titulo": "Uber", "valor": 32.0, "categoria": "transporte"})
        executores["registrar_renda"]({"valor": 5000.0, "categoria": "cliente", "descricao": "salario"})
        executores["registrar_habito"]({"nome": "Meditar", "meta": "10 min", "frequencia_tipo": "diario", "horario": "07:00"})
        executores["marcar_habito"]({"nome": "Academia"})
        executores["registrar_lembrete"]({"titulo": "Renovar o CMA", "data": "2026-10-01"})
        executores["agendar_evento"]({"titulo": "Reuniao com o contador", "data": "2026-09-29",
                                      "hora_inicio": "14:00", "hora_fim": "15:00", "lembrar_min_antes": 30})
        executores["registrar_treino"]({"grupo": "academia", "duracao_min": 60})
        return "-> Viagem: Gramado\n-> Gasto: mercado e uber\n...", [], fake_usage()

    def _processar(self, item_id, fake=None):
        def fake_criar(titulo, inicio, fim, lembrar=None):
            return {"uid": "uid-reuniao", "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}

        with patch("claude_client.chat", side_effect=fake or self._fake_nectar), patch(
            "caldav_client.configurado", return_value=True
        ), patch("caldav_client.criar_evento", side_effect=fake_criar):
            return self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "assistente"})

    def test_texto_nectar_vira_8_ou_mais_cards_e_resumo_final(self):
        db.create_habito(self.conn, "Academia", None, "diario", None, None, None)
        item_id = self.client.post("/api/brain-dump", json={"texto": TEXTO_NECTAR}).get_json()["id"]
        res = self._processar(item_id)
        self.assertEqual(res.status_code, 200, res.get_json())
        corpo = res.get_json()
        self.assert_contrato(corpo)
        tipos = self.tipos(corpo)
        self.assertEqual(tipos, [
            "projeto_viagem", "transacao", "transacao", "transacao", "habito", "habito",
            "lembrete", "agenda", "saude_treino", "resumo_final",
        ])
        self.assertGreaterEqual(len(tipos) - 1, 8)
        resumo = corpo["cards"][-1]["data"]
        self.assertEqual(resumo["passos_total"], 9)
        for modulo in ("Viagens", "Finanças", "Hábitos", "Lembretes", "Agenda", "Saúde"):
            self.assertIn(modulo, resumo["modulos"])
        textos = {linha["modulo"]: linha["texto"] for linha in resumo["linhas"]}
        self.assertEqual(textos["Finanças"], "2 gastos registrados, 1 entrada registrada")
        self.assertEqual(textos["Viagens"], "1 viagem registrada")
        self.assertEqual(textos["Hábitos"], "2 hábitos atualizados")
        self.assertNotIn("45", str(resumo))
        # cada card tem o proprio Desfazer (tokens independentes)
        tokens = [self.desfazer_de(c) for c in corpo["cards"][:-1]]
        self.assertTrue(all(tokens))
        self.assertEqual(len(set(tokens)), len(tokens))
        # legado + item marcado + chat com os cards
        self.assertEqual((corpo["ok"], corpo["tipo"]), (True, "assistente"))
        self.assertEqual(corpo["resposta"], corpo["resumo_texto"])
        self.assertEqual(self.client.get("/api/brain-dump").get_json(), [])
        hist = self.client.get("/api/chat/historico").get_json()
        self.assertEqual(hist[-2]["texto"], TEXTO_NECTAR)
        self.assertEqual(len(hist[-1]["cards"]), 10)
        # desfazer um card (uber) nao mexe nos outros
        self.assertEqual(self.client.post(f"/api/desfazer/{tokens[2]}").status_code, 200)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM incomes").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM viagens").fetchone()[0], 1)

    def test_brain_dump_visitante_nao_converte(self):
        # Revisao da Fase 6 (achado 12): converter cria gasto/tarefa/evento de
        # uma vez - no modo visitante e 403 (antes convertia e so mascarava o
        # valor). O item continua pendente pro Alex converter depois.
        item_id = self.client.post("/api/brain-dump", json={"texto": TEXTO_NECTAR}).get_json()["id"]
        with patch("app._modo_visitante_ativo", return_value=True):
            res = self._processar(item_id, fake=ia_proibida)
        self.assertEqual(res.status_code, 403)
        self.assertEqual([i["id"] for i in self.client.get("/api/brain-dump").get_json()], [item_id])

    def test_ia_falhou_item_continua_pendente(self):
        import anthropic

        item_id = self.client.post("/api/brain-dump", json={"texto": "coisa solta"}).get_json()["id"]

        def quebra(*_a):
            raise anthropic.APIConnectionError(request=None)

        res = self._processar(item_id, fake=quebra)
        self.assertEqual(res.status_code, 502)
        self.assertEqual([i["id"] for i in self.client.get("/api/brain-dump").get_json()], [item_id])

    def test_processar_duas_vezes_recusa(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "coisa solta"}).get_json()["id"]
        self.assertEqual(self._processar(item_id, fake=lambda *a: ("ok", [], fake_usage())).status_code, 200)
        self.assertEqual(self._processar(item_id, fake=ia_proibida).status_code, 400)

    def test_consulta_no_brain_dump_resolve_local(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "tomei um copo de agua"}).get_json()["id"]
        res = self._processar(item_id, fake=ia_proibida)
        self.assertEqual(self.tipos(res.get_json()), ["saude_dia"])

    def test_converter_tarefa_e_gasto_devolvem_contrato(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "levar carro na revisao"}).get_json()["id"]
        corpo = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "tarefa"}).get_json()
        self.assertEqual((corpo["ok"], corpo["tipo"]), (True, "tarefa"))
        self.assertEqual(self.tipos(corpo), ["tarefas_criadas"])
        self.assertEqual(corpo["cards"][0]["data"]["tarefas"][0]["id"], corpo["id"])
        self.assertEqual(self.client.post(f"/api/desfazer/{self.desfazer_de(corpo['cards'][0])}").status_code, 200)

        item_id = self.client.post("/api/brain-dump", json={"texto": "mercado 30"}).get_json()["id"]
        corpo = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "gasto", "valor": 30.0}).get_json()
        self.assertEqual(self.tipos(corpo), ["transacao"])
        self.assertEqual(corpo["cards"][0]["data"]["valor"], 30.0)

        item_id = self.client.post("/api/brain-dump", json={"texto": "ideia"}).get_json()["id"]
        corpo = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "nota"}).get_json()
        self.assertEqual(corpo["cards"], [])
        self.assertEqual(corpo["resumo_texto"], "Virou nota.")

    def test_converter_gasto_valor_invalido(self):
        item_id = self.client.post("/api/brain-dump", json={"texto": "x"}).get_json()["id"]
        for valor in [True, float("nan"), float("inf"), -1, "30", None]:
            res = self.client.post(f"/api/brain-dump/{item_id}/converter", json={"tipo": "gasto", "valor": valor})
            self.assertEqual(res.status_code, 400, valor)


if __name__ == "__main__":
    unittest.main()
