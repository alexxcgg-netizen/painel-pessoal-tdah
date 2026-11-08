"""Painel puxando assunto (2026-10-13): conversa_proativa.py (fechar o dia 21h e padroes
da semana no domingo), POST /api/tarefas/adiar e mascara de visitante. Banco temporario,
IA nunca chamada, push nunca enviado."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import cards  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import conversa_proativa as cp  # noqa: E402

PIN_TESTE = "123456"
HOJE = date.today()  # ja_notificou_hoje usa date.today()
AMANHA = (HOJE + timedelta(days=1)).isoformat()
ONTEM = (HOJE - timedelta(days=1)).isoformat()


def _banco():
    db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
    if db.DB_PATH.exists():
        db.DB_PATH.unlink()
    db.init_db()
    return db.get_db()


def _tarefa(conn, titulo, due=None, hora=None, feita_em=None, recorrencia=None):
    cur = conn.execute(
        "INSERT INTO tasks (title, due_date, hora, completed_at, recorrencia) VALUES (?, ?, ?, ?, ?)",
        (titulo, due, hora, feita_em, recorrencia),
    )
    conn.commit()
    return cur.lastrowid


def _feita_no_dia(dia: date) -> str:
    # completed_at e UTC: meio-dia de Brasilia = 15:00Z
    return f"{dia.isoformat()} 15:00:00"


class FecharDiaTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _banco()

    def tearDown(self):
        self.conn.close()

    def test_dia_vazio_nao_gera_nada(self):
        self.assertIsNone(cp.fechar_dia(self.conn, HOJE))

    def test_pendentes_em_ordem_de_agenda_com_atrasadas(self):
        _tarefa(self.conn, "feita", due=HOJE.isoformat(), feita_em=_feita_no_dia(HOJE))
        _tarefa(self.conn, "dez", due=HOJE.isoformat(), hora="10:00")
        _tarefa(self.conn, "oito", due=HOJE.isoformat(), hora="08:00")
        _tarefa(self.conn, "velha", due=ONTEM)
        _tarefa(self.conn, "futura", due=AMANHA)
        _tarefa(self.conn, "rotina", due=HOJE.isoformat(), recorrencia="diaria")
        texto, lista = cp.fechar_dia(self.conn, HOJE)
        d = lista[0]["data"]
        self.assertEqual(lista[0]["type"], "fechar_dia")
        self.assertEqual(d["feitas"], 1)
        self.assertEqual([p["titulo"] for p in d["pendentes"]], ["velha", "oito", "dez"])
        self.assertTrue(d["pendentes"][0]["atrasada"])
        self.assertEqual(len(d["ids_adiar"]), 3)
        self.assertIn("1 feita", texto)
        self.assertIn("ficaram 3", texto)
        self.assertIn("1 já vinham de antes", texto)
        self.assertNotIn("futura", texto)
        self.assertNotIn("rotina", texto)

    def test_dia_limpo(self):
        _tarefa(self.conn, "a", due=HOJE.isoformat(), feita_em=_feita_no_dia(HOJE))
        texto, lista = cp.fechar_dia(self.conn, HOJE)
        self.assertIn("Dia fechado limpo", texto)
        self.assertEqual(lista[0]["data"]["pendentes"], [])
        self.assertEqual(cp.resumo_push_fechar_dia(texto, lista[0]), "Dia fechado limpo. Dá uma olhada no resumo.")

    def test_card_limita_lista_mas_adia_todas(self):
        for i in range(cp.LIMITE_PENDENTES_CARD + 3):
            _tarefa(self.conn, f"t{i}", due=HOJE.isoformat())
        _, lista = cp.fechar_dia(self.conn, HOJE)
        d = lista[0]["data"]
        self.assertEqual(len(d["pendentes"]), cp.LIMITE_PENDENTES_CARD)
        self.assertEqual(d["mais"], 3)
        self.assertEqual(len(d["ids_adiar"]), cp.LIMITE_PENDENTES_CARD + 3)


class AdiarTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _banco()

    def tearDown(self):
        self.conn.close()

    def _due(self, i):
        return self.conn.execute("SELECT due_date, hora FROM tasks WHERE id = ?", (i,)).fetchone()

    def test_so_move_aberta_ate_hoje_e_mantem_hora(self):
        hoje = _tarefa(self.conn, "hoje", due=HOJE.isoformat(), hora="09:30")
        velha = _tarefa(self.conn, "velha", due=ONTEM)
        feita = _tarefa(self.conn, "feita", due=HOJE.isoformat(), feita_em=_feita_no_dia(HOJE))
        futura = _tarefa(self.conn, "futura", due=(HOJE + timedelta(days=5)).isoformat())
        rotina = _tarefa(self.conn, "rotina", due=HOJE.isoformat(), recorrencia="diaria")
        sem_data = _tarefa(self.conn, "sem data")
        r = cp.adiar_para_amanha(self.conn, [hoje, velha, feita, futura, rotina, sem_data, 99999], HOJE)
        self.assertEqual(r, {"movidas": 2, "para": AMANHA})
        self.assertEqual(tuple(self._due(hoje)), (AMANHA, "09:30"))
        self.assertEqual(self._due(velha)["due_date"], AMANHA)
        self.assertEqual(self._due(feita)["due_date"], HOJE.isoformat())
        self.assertEqual(self._due(rotina)["due_date"], HOJE.isoformat())
        self.assertIsNone(self._due(sem_data)["due_date"])

    def test_ids_lixo(self):
        for ids in (None, [], ["1"], [True], [-1, 0], [1.5]):
            with self.subTest(ids=ids):
                self.assertEqual(cp.adiar_para_amanha(self.conn, ids, HOJE)["movidas"], 0)


class TrazerParaHojeTestCase(unittest.TestCase):
    """2026-10-14: atrasada tem "pra hoje" - antes so existia "pra amanha" e a tarefa de ontem,
    que o Alex ia fazer hoje, ia parar depois de amanha."""

    def setUp(self):
        self.conn = _banco()

    def tearDown(self):
        self.conn.close()

    def _due(self, i):
        return self.conn.execute("SELECT due_date, hora FROM tasks WHERE id = ?", (i,)).fetchone()

    def test_so_traz_atrasada_aberta_e_hora_que_ja_passou_sai(self):
        cedo = _tarefa(self.conn, "placas", due=ONTEM, hora="09:45")
        tarde = _tarefa(self.conn, "academia", due=ONTEM, hora="18:00")
        sem_hora = _tarefa(self.conn, "pix", due=(HOJE - timedelta(days=3)).isoformat())
        hoje = _tarefa(self.conn, "de hoje", due=HOJE.isoformat(), hora="08:00")
        feita = _tarefa(self.conn, "feita", due=ONTEM, feita_em=_feita_no_dia(HOJE))
        rotina = _tarefa(self.conn, "rotina", due=ONTEM, recorrencia="diaria")
        futura = _tarefa(self.conn, "futura", due=AMANHA)
        r = cp.trazer_para_hoje(self.conn, [cedo, tarde, sem_hora, hoje, feita, rotina, futura, 99999], HOJE, "11:00")
        self.assertEqual(r, {"movidas": 3, "para": HOJE.isoformat()})
        self.assertEqual(tuple(self._due(cedo)), (HOJE.isoformat(), None))  # 09:45 ja passou
        self.assertEqual(tuple(self._due(tarde)), (HOJE.isoformat(), "18:00"))  # ainda vem
        self.assertEqual(tuple(self._due(sem_hora)), (HOJE.isoformat(), None))
        self.assertEqual(tuple(self._due(hoje)), (HOJE.isoformat(), "08:00"))  # nao era atrasada
        self.assertEqual(self._due(feita)["due_date"], ONTEM)
        self.assertEqual(self._due(rotina)["due_date"], ONTEM)
        self.assertEqual(self._due(futura)["due_date"], AMANHA)

    def test_ids_lixo(self):
        for ids in (None, [], ["1"], [True], [-1, 0], [1.5]):
            with self.subTest(ids=ids):
                self.assertEqual(cp.trazer_para_hoje(self.conn, ids, HOJE, "10:00")["movidas"], 0)


class SemanaTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _banco()

    def tearDown(self):
        self.conn.close()

    def test_semana_vazia(self):
        self.assertIsNone(cp.padroes_semana(self.conn, HOJE))

    def test_observacoes_saem_dos_numeros(self):
        melhor = HOJE - timedelta(days=2)
        for _ in range(4):
            _tarefa(self.conn, "x", feita_em=_feita_no_dia(melhor))
        _tarefa(self.conn, "y", feita_em=_feita_no_dia(HOJE))
        _tarefa(self.conn, "antiga", feita_em=_feita_no_dia(HOJE - timedelta(days=9)))
        self.conn.execute("INSERT INTO voos (data, destino, horas) VALUES (?, 'SBFL', 1.5)", (HOJE.isoformat(),))
        self.conn.commit()
        texto, lista = cp.padroes_semana(self.conn, HOJE)
        d = lista[0]["data"]
        self.assertEqual(lista[0]["type"], "semana")
        self.assertEqual(len(d["dias"]), 7)
        self.assertEqual(d["ate"], HOJE.isoformat())
        self.assertEqual((d["tarefas"], d["tarefas_ant"]), (5, 1))
        self.assertEqual(d["melhor_dia"], melhor.isoformat())
        self.assertEqual(d["voo_horas"], 1.5)
        nome = cp.DIAS_LONGOS[melhor.weekday()].capitalize()
        self.assertIn(f"{nome} foi teu dia mais produtivo, 4 tarefas", texto)
        self.assertIn("4 a mais que na semana passada", texto)
        self.assertLessEqual(len(d["observacoes"]), 3)
        # leva 22/10: voou na semana -> a sugestao puxa a categoria do diario de bordo mais atrasada
        self.assertEqual(d["sugestao"], "Navegação é a categoria mais atrasada pro comercial (faltam 20,0 h): "
                                        "vale pedir uma navegação no próximo voo.")
        self.assertIn("Pra semana que vem: Navegação", texto)

    def test_sugestao_da_semana_segue_a_prioridade(self):
        melhor = HOJE - timedelta(days=2)
        for _ in range(3):
            _tarefa(self.conn, "x", feita_em=_feita_no_dia(melhor))
        _, lista = cp.padroes_semana(self.conn, HOJE)
        nome = cp.DIAS_LONGOS[melhor.weekday()]
        self.assertEqual(lista[0]["data"]["sugestao"], f"Põe o que for mais pesado da semana que vem na {nome}, que foi quando tu mais rendeu.")
        for i in range(3):
            self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", (f"atrasada {i}", (HOJE - timedelta(days=3)).isoformat()))
        self.conn.commit()
        _, lista = cp.padroes_semana(self.conn, HOJE)
        self.assertTrue(lista[0]["data"]["sugestao"].startswith("Separa 30 min na segunda pra zerar as 3 atrasadas"))

    def test_card_semana_mascara_pro_visitante(self):
        _tarefa(self.conn, "x", feita_em=_feita_no_dia(HOJE))
        _, lista = cp.padroes_semana(self.conn, HOJE)
        _, lista_dia = cp.fechar_dia(self.conn, HOJE)
        for chave in ("gasto", "gasto_ant", "gastos_dia", "agua_dia"):
            self.assertIn(chave, cards.CAMPOS_SENSIVEIS["semana"])
        for chave in ("gasto", "agua"):
            self.assertIn(chave, cards.CAMPOS_SENSIVEIS["fechar_dia"])
        self.assertIn("semana", cards.TIPOS_CARD)
        self.assertIn("fechar_dia", cards.TIPOS_CARD)
        self.assertTrue(lista and lista_dia)


class VerificarTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _banco()
        _tarefa(self.conn, "pendente", due=HOJE.isoformat())

    def tearDown(self):
        self.conn.close()

    def _mensagens(self):
        return self.conn.execute("SELECT texto FROM chat_mensagens WHERE papel = 'assistant'").fetchall()

    def test_fora_da_janela_nao_faz_nada(self):
        self.assertEqual(cp.verificar(self.conn, datetime.combine(HOJE, datetime.min.time()).replace(hour=20)), [])
        self.assertEqual(self._mensagens(), [])

    def test_publica_uma_vez_so(self):
        # leva 08/11: sem nada feito na semana o padroes_semana nao sai e o teste quebrava todo domingo (esperava
        # o card da semana). Uma tarefa feita ontem garante o card no domingo; nos outros dias ele nao entra.
        _tarefa(self.conn, "feita ontem", feita_em=_feita_no_dia(HOJE - timedelta(days=1)))
        agora = datetime.combine(HOJE, datetime.min.time()).replace(hour=21, minute=3)
        saida = cp.verificar(self.conn, agora)
        self.assertEqual([s[0] for s in saida][:1], ["fechamento_noturno"])
        self.assertIn("pousar o dia: 1 em aberto", saida[0][2])  # lab v4: o fechamento das 21h virou o Pouso do dia
        self.assertEqual(len(self._mensagens()), 1 + (1 if HOJE.weekday() == 6 else 0))
        self.assertTrue(db.ja_notificou_hoje(self.conn, "fechar_dia_chat"))
        self.assertEqual(cp.verificar(self.conn, agora.replace(minute=8)), [])
        self.assertEqual(len(self._mensagens()), 1 + (1 if HOJE.weekday() == 6 else 0))

    def test_card_vai_pro_historico_do_chat(self):
        cp.verificar(self.conn, datetime.combine(HOJE, datetime.min.time()).replace(hour=22))
        hist = db.list_chat_mensagens(self.conn)
        tipos = [c["type"] for m in hist for c in db.cards_de_mensagem_chat(m)]
        # lab v4 (Grupo G): placar primeiro, depois o pouso (domingo a noite tambem sai o card da semana)
        self.assertEqual([t for t in tipos if t != "semana"], ["placar_feito", "pouso_dia"])

    def test_semana_so_no_domingo(self):
        sabado = HOJE + timedelta(days=(5 - HOJE.weekday()) % 7)
        self.assertEqual(sabado.weekday(), 5)
        saida = cp.verificar(self.conn, datetime.combine(sabado, datetime.min.time()).replace(hour=20))
        self.assertNotIn("padroes_semana", [s[0] for s in saida])


class RotaAdiarTestCase(unittest.TestCase):
    def setUp(self):
        conn = _banco()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        self.id = _tarefa(conn, "rota", due=app._agora_brasilia().date().isoformat(), hora="07:00")
        conn.commit()
        conn.close()
        self.client = app.app.test_client()

    def test_exige_login(self):
        self.assertEqual(self.client.post("/api/tarefas/adiar", json={"ids": [self.id]}).status_code, 401)

    def test_valida_e_move(self):
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)
        for corpo in ({}, {"ids": "1"}, {"ids": []}, {"ids": list(range(1, 202))}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post("/api/tarefas/adiar", json=corpo).status_code, 400)
        r = self.client.post("/api/tarefas/adiar", json={"ids": [self.id]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["movidas"], 1)

    def test_pra_hoje_exige_login_valida_e_traz(self):
        self.assertEqual(self.client.post("/api/tarefas/pra-hoje", json={"ids": [self.id]}).status_code, 401)
        self.assertEqual(self.client.post("/login", json={"pin": PIN_TESTE}).status_code, 200)
        for corpo in ({}, {"ids": "1"}, {"ids": []}, {"ids": list(range(1, 202))}):
            with self.subTest(corpo=corpo):
                self.assertEqual(self.client.post("/api/tarefas/pra-hoje", json=corpo).status_code, 400)
        conn = db.get_db()
        ontem = (app._agora_brasilia().date() - timedelta(days=1)).isoformat()
        atrasada = _tarefa(conn, "placas do residencial", due=ontem)
        conn.close()
        r = self.client.post("/api/tarefas/pra-hoje", json={"ids": [atrasada, self.id]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"movidas": 1, "para": app._agora_brasilia().date().isoformat()})


if __name__ == "__main__":
    unittest.main()


class ComoEstaTestCase(unittest.TestCase):
    """Leva 22/10: de manha a IA pergunta "como tu ta hoje?" com o card do check-in."""

    def setUp(self):
        self.conn = _banco()
        self.manha = datetime.combine(HOJE, datetime.min.time()).replace(hour=8, minute=5)

    def tearDown(self):
        self.conn.close()

    def _cards(self):
        return [c for m in db.list_chat_mensagens(self.conn) for c in db.cards_de_mensagem_chat(m)]

    def test_pergunta_uma_vez_de_manha_com_o_card(self):
        # leva 08/11 (A7): sai no primeiro sinal de acordado (aqui: o "bom dia" das 08:00)
        import vida_assistente

        vida_assistente.registrar_acordou(self.conn, self.manha.replace(minute=0))
        saida = cp.perguntar_como_esta(self.conn, self.manha)
        self.assertEqual([s[0] for s in saida], ["como_esta"])
        card = [c for c in self._cards() if c["type"] == "checkin"][0]
        self.assertEqual((card["data"]["energia"], card["data"]["humor"]), (None, None))
        self.assertEqual(cp.perguntar_como_esta(self.conn, self.manha.replace(hour=9)), [])
        self.assertEqual(len(self._cards()), 1)

    def test_fora_da_janela_ou_ja_respondido_nao_pergunta(self):
        self.assertEqual(cp.perguntar_como_esta(self.conn, self.manha.replace(hour=13)), [])  # 08/11: janela ate 12:30
        db.salvar_checkin(self.conn, HOJE.isoformat(), {"sono": 1})
        self.assertEqual(cp.perguntar_como_esta(self.conn, self.manha), [])
        self.assertEqual(self._cards(), [])

    def test_card_mostra_o_que_ja_foi_dito_e_visitante_nao_ve(self):
        db.salvar_checkin(self.conn, HOJE.isoformat(), {"energia": 3, "humor": 2})
        card = cards.card_checkin(self.conn)
        self.assertEqual((card["data"]["energia"], card["data"]["sono"], card["data"]["humor"]), (3, None, 2))
        mascarado = cards.mascarar_cards([card])[0]["data"]
        self.assertTrue(mascarado["oculto"])
        self.assertNotIn("energia", mascarado)


    def test_ferramenta_do_chat_devolve_o_card_sem_desfazer(self):
        db.salvar_checkin(self.conn, HOJE.isoformat(), {"sono": 1})
        lista = cards.cards_dos_efeitos(self.conn, [{"entidade": "checkin", "consulta": True}], criar_token=lambda i: "tok")
        self.assertEqual([c["type"] for c in lista], ["checkin"])
        self.assertEqual(lista[0]["data"]["sono"], 1)
        self.assertFalse([a for a in lista[0]["actions"] if a.get("tipo") == "desfazer"])
