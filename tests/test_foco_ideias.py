"""Grupo A (Foco) do Laboratorio v4, 30/10/2026: E agora?, Por que travou?, Pacote, Um segundo antes e Recomeco.
IA sempre com mock - nada gasta cota."""
import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.test_assistente_vida import _Base

import app
import conversa_proativa
import db
import dia_ruim
import foco_ideias
import recomeco

HOJE = date(2026, 10, 30)  # sexta
AGORA = datetime(2026, 10, 30, 14, 20)


class _Dados(_Base):
    def setUp(self):
        super().setUp()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()

    def tarefa(self, titulo, due=None, **campos):
        cur = self.conn.execute("INSERT INTO tasks (title, due_date) VALUES (?, ?)", (titulo, due))
        for k, v in campos.items():
            self.conn.execute(f"UPDATE tasks SET {k} = ? WHERE id = ?", (v, cur.lastrowid))
        self.conn.commit()
        return cur.lastrowid

    def empurrar(self, tid, n=3):
        for _ in range(n):
            dia_ruim.registrar_adiamento(self.conn, [tid], "2026-10-20", "2026-10-21")
        self.conn.commit()


class EAgoraTest(_Dados):
    def test_escolhe_uma_com_porque_e_cabe_no_tempo(self):
        venc = self.tarefa("Pagar a fatura", "2026-10-30", esforco="baixa")
        self.tarefa("Estudar meteorologia", "2026-11-20", esforco="alta")
        self.tarefa("Sem data qualquer")
        eventos = [{"titulo": "Academia", "inicio": "2026-10-30T15:00:00", "dia_inteiro": False}]
        d = foco_ideias.e_agora(self.conn, AGORA, eventos)
        self.assertEqual((d["quando"], d["livre_min"], d["livre_ate"]), ("14:20", 40, "Academia"))
        s = d["sugestoes"][0]
        self.assertEqual(s["id"], venc)
        self.assertEqual(s["porque"], "Vence hoje. Cabe nos 40 min até Academia.")
        self.assertLessEqual(len(d["sugestoes"]), 3)

    def test_atrasada_vence_e_empurrada_pesa_mais(self):
        a = self.tarefa("Atrasada faz tempo", "2026-10-25")
        b = self.tarefa("Futura empurrada", "2026-11-02")
        self.empurrar(b, 4)
        d = foco_ideias.e_agora(self.conn, AGORA, [])
        self.assertEqual(d["sugestoes"][0]["id"], a)
        self.assertIn("atrasada há 5 dias", d["sugestoes"][0]["porque"])
        self.assertIn("empurrada 4 vezes", [x for x in d["sugestoes"] if x["id"] == b][0]["porque"])

    def test_energia_baixa_afasta_tarefa_pesada_e_arquivada_nao_entra(self):
        pesada = self.tarefa("Planejar a obra inteira", "2026-10-30", esforco="alta")
        leve = self.tarefa("Responder um e-mail", "2026-10-30", esforco="baixa")
        arq = self.tarefa("Velha arquivada", "2026-10-01")
        self.conn.execute("UPDATE tasks SET arquivada_em = 'x' WHERE id = ?", (arq,))
        self.conn.commit()
        db.salvar_checkin(self.conn, "2026-10-30", {"energia": 1})
        ids = [s["id"] for s in foco_ideias.e_agora(self.conn, AGORA, [])["sugestoes"]]
        self.assertEqual(ids[0], leve)
        self.assertNotIn(arq, ids)
        self.assertTrue(pesada in ids)  # continua uma opcao, so desce

    def test_sem_tarefa_devolve_lista_vazia_e_com_hora_na_agenda_nao_entra(self):
        self.assertEqual(foco_ideias.e_agora(self.conn, AGORA, [])["sugestoes"], [])
        self.tarefa("Dentista", "2026-10-30", hora="16:00")
        self.assertEqual(foco_ideias.e_agora(self.conn, AGORA, [])["sugestoes"], [])

    def test_bora_abre_o_foco_com_relogio_correndo(self):
        tid = self.tarefa("Pagar a fatura", "2026-10-30")
        e = foco_ideias.bora(self.conn, AGORA, tid)
        self.assertEqual((e["fase"], e["task_id"]), ("rodando", tid))
        self.assertIsNone(foco_ideias.bora(self.conn, AGORA, 9999))

    def test_rotas(self):
        tid = self.tarefa("Pagar a fatura", "2026-10-30")
        d = self.client.get("/api/e-agora").get_json()
        self.assertEqual(d["sugestoes"][0]["id"], tid)
        self.assertEqual(self.client.post("/api/e-agora/bora", json={"task_id": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/e-agora/bora", json={"task_id": 999}).status_code, 404)
        r = self.client.post("/api/e-agora/bora", json={"task_id": tid}).get_json()
        self.assertEqual(r["sessao"]["fase"], "rodando")
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertTrue(self.client.get("/api/e-agora").get_json()["oculto"])
            self.assertEqual(self.client.post("/api/e-agora/bora", json={"task_id": tid}).status_code, 403)


class PacoteTest(_Dados):
    def test_juntar_guardar_e_liberar_ao_concluir(self):
        tid = self.tarefa("Faxina do quarto")
        r = self.client.post("/api/pacote", json={"task_id": tid, "premio": "  Podcast   de aviação "}).get_json()
        self.assertEqual(r["premio"], "Podcast de aviação")
        p = self.client.get("/api/pacote").get_json()
        self.assertEqual(p["ativos"][0]["premio"], "Podcast de aviação")
        self.assertEqual(p["chatas"], [])
        r = self.client.post(f"/api/tasks/{tid}/complete").get_json()
        self.assertEqual(r["premio"], "Podcast de aviação")
        outra = self.tarefa("Sem pacote")
        self.assertNotIn("premio", self.client.post(f"/api/tasks/{outra}/complete").get_json())

    def test_validacoes_e_desfazer(self):
        tid = self.tarefa("Esteira 30 min")
        self.assertEqual(self.client.post("/api/pacote", json={"task_id": tid, "premio": ""}).status_code, 400)
        self.assertEqual(self.client.post("/api/pacote", json={"task_id": 999, "premio": "x"}).status_code, 404)
        foco_ideias.juntar(self.conn, tid, "Série")
        self.assertEqual(self.client.post("/api/pacote/desfazer", json={"task_id": tid}).status_code, 200)
        self.assertEqual(self.client.post("/api/pacote/desfazer", json={"task_id": tid}).status_code, 404)
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertEqual(self.client.post("/api/pacote", json={"task_id": tid, "premio": "x"}).status_code, 403)

    def test_chat_junta_pelo_titulo(self):
        tid = self.tarefa("Lançar os gastos")
        corpo, res = self.chat([("juntar_pacote", {"tarefa": "lançar os gastos", "premio": "Playlist nova"})])
        self.assertEqual(res[0]["premio"], "Playlist nova")
        self.assertEqual(foco_ideias.premio_da_tarefa(self.conn, tid), "Playlist nova")
        self.assertEqual([c["type"] for c in corpo["cards"]], ["pacote"])

    def test_e_agora_mostra_o_premio(self):
        tid = self.tarefa("Faxina", "2026-10-30")
        foco_ideias.juntar(self.conn, tid, "Série")
        self.assertEqual(foco_ideias.e_agora(self.conn, AGORA, [])["sugestoes"][0]["premio"], "Série")


class TravouTest(_Dados):
    def test_pergunta_so_quem_foi_empurrada_3_vezes_e_so_uma_vez(self):
        a = self.tarefa("Ligar pro cartório")
        b = self.tarefa("Outra", "2026-10-30")
        self.empurrar(a, 3)
        self.empurrar(b, 2)
        self.assertEqual([p["id"] for p in foco_ideias.pendentes_travou(self.conn)], [a])
        foco_ideias.marcar_perguntada(self.conn, a)
        self.assertEqual(foco_ideias.pendentes_travou(self.conn), [])

    def test_chato_vira_pacote(self):
        a = self.tarefa("Ligar pro cartório")
        self.empurrar(a)
        r = foco_ideias.responder_travou(self.conn, a, "chato", AGORA)
        self.assertEqual((r["acao"], r["premios"][0]), ("juntar", "Podcast de aviação"))
        self.assertEqual(foco_ideias.aplicar_remedio(self.conn, AGORA, a, "juntar", "Podcast de aviação")["premio"], "Podcast de aviação")
        self.assertEqual(foco_ideias.premio_da_tarefa(self.conn, a), "Podcast de aviação")

    def test_dificil_usa_ia_cacheia_e_abre_foco(self):
        a = self.tarefa("Ligar pro cartório")
        with patch("ia.funcoes.planejamento.remedio_travou",
                   return_value=({"texto": "Acha o telefone do cartório e salva no contato.", "lista": []}, {})) as m:
            r = foco_ideias.responder_travou(self.conn, a, "dificil", AGORA)
            foco_ideias.responder_travou(self.conn, a, "dificil", AGORA)
        self.assertEqual(m.call_count, 1)  # tocar de novo nao gasta IA
        self.assertEqual((r["acao"], r["texto"]), ("comecar", "Acha o telefone do cartório e salva no contato."))
        s = foco_ideias.aplicar_remedio(self.conn, AGORA, a, "comecar")["sessao"]
        self.assertEqual((s["fase"], s["passo"]), ("rodando", "Acha o telefone do cartório e salva no contato."))

    def test_medo_roteiro_e_sem_rumo_vira_subtarefas(self):
        a = self.tarefa("Ligar pro cartório")
        with patch("ia.funcoes.planejamento.remedio_travou", return_value=({"texto": "", "lista": ["Oi, bom dia.", "Qual o prazo?"]}, {})):
            r = foco_ideias.responder_travou(self.conn, a, "medo", AGORA)
        self.assertEqual(r["roteiro"], ["Oi, bom dia.", "Qual o prazo?"])
        with patch("ia.funcoes.planejamento.remedio_travou",
                   return_value=({"texto": "Descobrir se dá pra pedir online.", "lista": ["Abrir o site", "Achar o pedido"]}, {})):
            r = foco_ideias.responder_travou(self.conn, a, "sem_rumo", AGORA)
        self.assertEqual(r["passos"], ["Abrir o site", "Achar o pedido"])
        self.assertEqual(foco_ideias.aplicar_remedio(self.conn, AGORA, a, "passos")["passos"], 2)
        self.assertEqual(foco_ideias.aplicar_remedio(self.conn, AGORA, a, "passos")["passos"], 0)  # nao duplica
        subs = self.conn.execute("SELECT title, position FROM subtasks WHERE task_id = ? ORDER BY position", (a,)).fetchall()
        self.assertEqual([s["title"] for s in subs], ["Abrir o site", "Achar o pedido"])

    def test_ia_fora_do_ar_cai_no_texto_padrao(self):
        a = self.tarefa("Ligar pro cartório")
        with patch("ia.funcoes.planejamento.remedio_travou", side_effect=ValueError("sem rede")):
            r = foco_ideias.responder_travou(self.conn, a, "medo", AGORA)
        self.assertEqual(len(r["roteiro"]), 3)
        self.assertEqual(self.client.post("/api/travou/responder", json={"task_id": a, "motivo": "xis"}).status_code, 400)

    def test_rotas_e_acao_fora_de_ordem(self):
        a = self.tarefa("Ligar pro cartório")
        self.assertEqual(self.client.post("/api/travou/aplicar", json={"task_id": a, "acao": "comecar"}).status_code, 409)
        r = self.client.post("/api/travou/responder", json={"task_id": a, "motivo": "chato"}).get_json()
        self.assertEqual(r["remedio"]["motivo"], "chato")
        ok = self.client.post("/api/travou/aplicar", json={"task_id": a, "acao": "juntar", "premio": "Série"})
        self.assertEqual(ok.get_json()["premio"], "Série")
        self.assertEqual(self.client.post("/api/travou/aplicar", json={"task_id": a, "acao": "x"}).status_code, 400)

    def test_chat_abre_o_card_e_proativo_publica_uma_vez(self):
        a = self.tarefa("Ligar pro cartório")
        self.empurrar(a)
        corpo, _ = self.chat([("abrir_card_foco", {"card": "travou", "tarefa": "cartório"})])
        card = corpo["cards"][0]
        self.assertEqual((card["type"], card["data"]["task_id"], card["data"]["adiadas"]), ("travou", a, 3))
        # ja foi perguntada: o proativo nao repete
        self.assertEqual(conversa_proativa.perguntar_por_que_travou(self.conn, datetime(2026, 10, 30, 10, 0)), [])

    def test_proativo_pergunta_uma_vez_por_dia_na_janela(self):
        a = self.tarefa("Ligar pro cartório")
        b = self.tarefa("Organizar fotos")
        self.empurrar(a, 4)
        self.empurrar(b, 3)
        # 07/11 (cobranca.py): tarefa comum adiada 3+ fica com o card tarefa_adiada; o "travou" pega a recorrente
        self.assertEqual(conversa_proativa.perguntar_por_que_travou(self.conn, datetime(2026, 10, 30, 10, 0)), [])
        self.conn.execute("UPDATE tasks SET recorrencia = 'diaria'")
        self.conn.commit()
        self.assertEqual(conversa_proativa.perguntar_por_que_travou(self.conn, datetime(2026, 10, 30, 7, 0)), [])  # cedo
        r = conversa_proativa.perguntar_por_que_travou(self.conn, datetime(2026, 10, 30, 10, 0))
        self.assertEqual(r[0][0], "travou")
        self.assertIn("Ligar pro cartório", r[0][2])
        self.assertEqual(conversa_proativa.perguntar_por_que_travou(self.conn, datetime(2026, 10, 30, 11, 0)), [])  # 1x/dia
        msg = self.sql("SELECT cards_json FROM chat_mensagens ORDER BY id DESC LIMIT 1")[0]["cards_json"]
        self.assertEqual(json.loads(msg)[0]["type"], "travou")


class SegundoAntesTest(_Dados):
    def test_tela_conta_so_o_que_voltou_na_semana(self):
        self.tarefa("Separar a CIV pro voo", "2026-10-30")
        t = foco_ideias.tela_segundo_antes(self.conn, AGORA, "Instagram")
        self.assertEqual((t["pergunta"], t["tarefa"], t["app"], t["voltou_semana"]), ("Ia fazer o quê?", "Separar a CIV pro voo", "Instagram", 0))
        r = foco_ideias.registrar_escolha(self.conn, AGORA, "voltou", "Instagram")
        self.assertEqual(r["voltou_semana"], 1)
        foco_ideias.registrar_escolha(self.conn, AGORA, "seguiu", "Instagram")
        foco_ideias.registrar_escolha(self.conn, AGORA - timedelta(days=9), "voltou")
        self.assertEqual(foco_ideias.voltou_na_semana(self.conn, AGORA), 1)
        self.assertIsNone(foco_ideias.registrar_escolha(self.conn, AGORA, "talvez"))

    def test_tarefa_do_momento_prefere_o_foco_em_andamento(self):
        self.tarefa("Outra coisa", "2026-10-30")
        tid = self.tarefa("Lavar a louça")
        foco_ideias.bora(self.conn, AGORA, tid)
        self.assertEqual(foco_ideias.tarefa_do_momento(self.conn, AGORA), "Lavar a louça")

    def test_atalho_exige_token_e_conta(self):
        with patch.dict("os.environ", {"PAINEL_ATALHOS_TOKEN": "segredo-teste"}):
            anon = app.app.test_client()
            self.assertEqual(anon.get("/api/atalho/segundo-antes").status_code, 401)
            h = {"X-Webhook-Token": "segredo-teste"}
            self.assertEqual(anon.get("/api/atalho/segundo-antes?app=Instagram", headers=h).get_json()["voltou_semana"], 0)
            r = anon.post("/api/atalho/segundo-antes", json={"escolha": "voltou", "app": "Instagram"}, headers=h).get_json()
            self.assertEqual(r["voltou_semana"], 1)
            self.assertEqual(anon.post("/api/atalho/segundo-antes", json={"escolha": "x"}, headers=h).status_code, 400)

    def test_rotas_da_sessao(self):
        self.assertIn("voltou_semana", self.client.get("/api/segundo-antes").get_json())
        self.assertEqual(self.client.post("/api/segundo-antes", json={"escolha": "voltou"}).get_json()["voltou_semana"], 1)


class RecomecoTest(_Dados):
    def setUp(self):
        super().setUp()
        self.velha = self.tarefa("Ligar pro dentista", "2026-10-09")
        self.velha2 = self.tarefa("Organizar fotos", "2026-10-12")
        self.conta = self.tarefa("Pagar a Enel", "2026-10-02")
        self.cadeado = self.tarefa("Coisa travada", "2026-10-01", inegociavel=1)
        self.recente = self.tarefa("Devolver o livro", "2026-10-27")
        self.hoje = self.tarefa("Hoje mesmo", "2026-10-30")

    def test_so_arquiva_o_velho_que_nao_e_conta_nem_cadeado(self):
        e = recomeco.estado(self.conn, HOJE)
        self.assertEqual((e["total"], e["velhas"]), (5, 2))
        por_id = {i["id"]: i for i in e["itens"]}
        self.assertTrue(por_id[self.conta]["protegido"] and por_id[self.cadeado]["protegido"])
        r = recomeco.arquivar(self.conn, HOJE, AGORA)
        self.assertEqual((r["arquivadas"], r["total"], r["arquivadas_n"]), (2, 3, 2))
        self.assertEqual(recomeco.arquivar(self.conn, HOJE, AGORA)["arquivadas"], 0)  # idempotente
        ab = self.client.get("/api/tasks").get_json()
        self.assertNotIn(self.velha, [t["id"] for t in ab])
        self.assertIn(self.conta, [t["id"] for t in ab])

    def test_desfazer_devolve_o_prazo_antigo_e_devolver_uma_so(self):
        recomeco.arquivar(self.conn, HOJE, AGORA)
        d = recomeco.devolver(self.conn, HOJE, self.velha)
        self.assertEqual(d["arquivadas_n"], 1)
        self.assertEqual(self.sql("SELECT due_date FROM tasks WHERE id = ?", (self.velha,))[0]["due_date"], "2026-10-09")
        self.assertIsNone(recomeco.devolver(self.conn, HOJE, self.velha))
        r = recomeco.desfazer(self.conn, HOJE)
        self.assertEqual((r["voltaram"], r["arquivadas_n"]), (1, 0))
        self.assertEqual(r["velhas"], 2)

    def test_manter_ate_3_vao_pra_hoje(self):
        r = recomeco.manter(self.conn, HOJE, [self.recente, self.conta])
        self.assertEqual(r["mantidas"], 2)
        self.assertEqual(self.sql("SELECT due_date FROM tasks WHERE id = ?", (self.recente,))[0]["due_date"], "2026-10-30")
        self.assertIsNone(recomeco.manter(self.conn, HOJE, [self.hoje]))  # hoje nao e atrasada
        self.assertIsNone(recomeco.manter(self.conn, HOJE, [self.velha, self.velha2, self.conta, self.recente]))  # > 3
        self.assertEqual(self.client.post("/api/recomeco/manter", json={"ids": []}).status_code, 400)

    @patch("rotas.foco_ideias._agora", return_value=AGORA)  # as datas das tarefas sao fixas; o relogio real faz "recente" virar velha
    def test_rotas(self, _agora):
        self.assertEqual(self.client.get("/api/recomeco").get_json()["velhas"], 2)
        self.assertEqual(self.client.post("/api/recomeco/arquivar").get_json()["arquivadas"], 2)
        self.assertEqual(self.client.post("/api/recomeco/desfazer").get_json()["voltaram"], 2)
        self.assertEqual(self.client.post("/api/recomeco/devolver", json={"id": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/recomeco/devolver", json={"id": 999}).status_code, 404)
        with patch.object(app, "_modo_visitante_ativo", return_value=True):
            self.assertTrue(self.client.get("/api/recomeco").get_json()["oculto"])
            self.assertEqual(self.client.post("/api/recomeco/arquivar").status_code, 403)

    def test_quando_aparece(self):
        self.assertTrue(recomeco.deve_aparecer(self.conn, date(2026, 11, 2)))  # segunda
        self.assertTrue(recomeco.deve_aparecer(self.conn, date(2026, 11, 1)))  # dia 1
        self.assertFalse(recomeco.deve_aparecer(self.conn, date(2026, 11, 4)))  # quarta, so 6
        for i in range(6):
            self.tarefa(f"Atrasada {i}", "2026-10-20")
        self.assertTrue(recomeco.deve_aparecer(self.conn, date(2026, 11, 4)))  # passou de 10

    def test_proativo_uma_vez_e_so_se_ha_o_que_arquivar(self):
        seg = datetime(2026, 11, 2, 8, 0)
        r = conversa_proativa.recomeco_do_dia(self.conn, seg)
        self.assertEqual(r[0][0], "recomeco")
        self.assertEqual(conversa_proativa.recomeco_do_dia(self.conn, seg + timedelta(hours=1)), [])
        self.assertEqual(conversa_proativa.recomeco_do_dia(self.conn, seg + timedelta(days=1, hours=0)), [])  # < 6 dias
        recomeco.arquivar(self.conn, date(2026, 11, 2), seg)
        self.assertEqual(conversa_proativa.recomeco_do_dia(self.conn, seg + timedelta(days=7)), [])  # nada velho sobrou

    def test_chat_abre_cards(self):
        corpo, _ = self.chat([("abrir_card_foco", {"card": "recomeco"}), ("abrir_card_foco", {"card": "e_agora"}),
                              ("abrir_card_foco", {"card": "pacote"}), ("abrir_card_foco", {"card": "segundo_antes"})])
        self.assertEqual(sorted(c["type"] for c in corpo["cards"]), ["e_agora", "pacote", "recomeco", "segundo_antes"])

    def test_card_mascarado_no_visitante(self):
        import cards

        c = cards.mascarar_cards([recomeco.card(self.conn, HOJE)])[0]
        self.assertTrue(c["data"]["oculto"])
        self.assertNotIn("itens", c["data"])


if __name__ == "__main__":
    unittest.main()
