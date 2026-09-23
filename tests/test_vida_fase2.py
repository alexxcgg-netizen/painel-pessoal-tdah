"""BRIEFING.md Fase 2 + regressoes da revisao da Fase 1."""

import json
import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from test_vida_rotas import VidaBaseTestCase, fake_usage

import app
import claude_client
import db
import vida


class LogicaFase2TestCase(unittest.TestCase):
    def test_slot_agua_pausa(self):
        quarta = datetime(2026, 9, 23, 9, 0)
        self.assertEqual(vida.slot_agua_pausa(quarta), 9)
        self.assertEqual(vida.slot_agua_pausa(quarta.replace(hour=17, minute=4)), 17)
        self.assertIsNone(vida.slot_agua_pausa(quarta.replace(minute=5)))
        self.assertIsNone(vida.slot_agua_pausa(quarta.replace(hour=10)))
        self.assertIsNone(vida.slot_agua_pausa(quarta.replace(hour=19)))
        self.assertIsNone(vida.slot_agua_pausa(datetime(2026, 9, 26, 9, 0)))  # sabado

    def test_noites_ruins_seguidas(self):
        hoje = date(2026, 9, 23)
        sono = {"2026-09-23": 5.0, "2026-09-22": 5.5, "2026-09-21": 7.5, "2026-09-20": 4.0}
        self.assertEqual(vida.noites_ruins_seguidas(sono, {}, hoje), 2)
        self.assertEqual(vida.noites_ruins_seguidas(sono, {"2026-09-21": 1}, hoje), 4)
        # hoje sem dado nenhum: conta a partir de ontem
        self.assertEqual(vida.noites_ruins_seguidas({"2026-09-22": 5.0, "2026-09-21": 5.0}, {}, hoje), 2)
        self.assertEqual(vida.noites_ruins_seguidas({}, {}, hoje), 0)
        self.assertEqual(vida.noites_ruins_seguidas({"2026-09-23": 8.0}, {"2026-09-23": 1}, hoje), 1)

    def test_compromissos_na_chuva(self):
        eventos = [
            {"titulo": "Obra", "inicio": "2026-09-23T15:00:00"},
            {"titulo": "Cafe", "inicio": "2026-09-23T09:00:00"},
            {"titulo": "Feriado", "inicio": "2026-09-23T00:00:00", "dia_inteiro": True},
            {"titulo": "Ruim", "inicio": "lixo"},
        ]
        resumo = {"alerta": True, "hora_inicio": 14, "hora_fim": 17}
        self.assertEqual([e["titulo"] for e in vida.compromissos_na_chuva(eventos, resumo)], ["Obra"])
        self.assertEqual(vida.compromissos_na_chuva(eventos, {"alerta": False}), [])
        self.assertEqual(vida.compromissos_na_chuva(eventos, None), [])

    def test_ficha_para_titulo(self):
        fichas = [{"id": 1, "grupo": "Peito"}, {"id": 2, "grupo": "Costas"}]
        self.assertEqual([f["id"] for f in vida.ficha_para_titulo(fichas, "Treino de PEITO")], [1])
        self.assertEqual([f["id"] for f in vida.ficha_para_titulo(fichas, "Academia")], [1, 2])
        self.assertEqual(vida.ficha_para_titulo(fichas, "Ligar pro banco"), [])
        self.assertEqual(vida.ficha_para_titulo(fichas, None), [])
        self.assertEqual(vida.ficha_para_titulo([], "Treino peito"), [])

    def test_checklist_saida(self):
        sexta_noite = datetime(2026, 9, 25, 20, 0)
        self.assertEqual(vida.checklist_saida(sexta_noite, None, False, False), ["carteira"])
        itens = vida.checklist_saida(sexta_noite, 30, True, True)
        self.assertEqual(len(itens), 4)
        self.assertIn("carregador (bateria em 30%)", itens)
        self.assertNotIn("carregador", " ".join(vida.checklist_saida(sexta_noite, 80, False, False)))
        # bigode so sexta/sabado a partir das 16h
        self.assertEqual(len(vida.checklist_saida(datetime(2026, 9, 25, 10, 0), None, False, True)), 1)
        self.assertEqual(len(vida.checklist_saida(datetime(2026, 9, 23, 20, 0), None, False, True)), 1)
        self.assertEqual(len(vida.checklist_saida(datetime(2026, 9, 26, 21, 0), None, False, True)), 2)

    def test_eh_dia_de_academia(self):
        self.assertTrue(vida.eh_dia_de_academia(["Ligar banco", "Treino costas"]))
        self.assertFalse(vida.eh_dia_de_academia(["Ligar banco"]))

    def test_mensagem_chegou_casa(self):
        agora = datetime(2026, 9, 23, 12, 10)
        msg = vida.mensagem_chegou_casa(agora, {"titulo": "Obra", "inicio": "2026-09-23T14:00:00"}, [])
        self.assertEqual(msg, "Proximo: Obra as 14:00 - sai ate 13:30.")
        msg = vida.mensagem_chegou_casa(agora, {"titulo": "Obra", "inicio": "2026-09-23T12:30:00"}, [])
        self.assertEqual(msg, "Proximo: Obra as 12:30 - sai ja.")
        self.assertIsNone(vida.mensagem_chegou_casa(agora, None, ["x"]))
        noite = datetime(2026, 9, 23, 19, 0)
        self.assertIn("a, b, c e mais 1", vida.mensagem_chegou_casa(noite, None, ["a", "b", "c", "d"]))
        self.assertIn("Nada pendente", vida.mensagem_chegou_casa(noite, None, []))

    def test_proxima_data_manutencao(self):
        hoje = date(2026, 9, 23)
        self.assertEqual(vida.proxima_data_manutencao("2026-03-10", 6, None, hoje), date(2026, 9, 10))
        self.assertEqual(vida.proxima_data_manutencao("2026-01-31", 1, None, hoje), date(2026, 2, 28))
        self.assertEqual(vida.proxima_data_manutencao("2026-11-15", 3, None, hoje), date(2027, 2, 15))
        self.assertEqual(vida.proxima_data_manutencao(None, 12, "2026-09-01 10:00:00", hoje), date(2027, 9, 1))
        self.assertEqual(vida.proxima_data_manutencao("lixo", 1, None, hoje), date(2026, 10, 23))

    def test_itens_de_compra(self):
        self.assertEqual(vida.limpar_item_compra("Acabou o Café."), "Café")
        self.assertEqual(vida.limpar_item_compra("acabaram as pilhas"), "pilhas")
        self.assertEqual(vida.normalizar_item_compra("Acabou o Café"), "cafe")
        self.assertEqual(vida.normalizar_item_compra("  CAFÉ! "), "cafe")

    def test_vencimento_anterior_e_dia_da_rotina(self):
        self.assertEqual(vida.vencimento_anterior(10, date(2026, 9, 23)), date(2026, 9, 10))
        self.assertEqual(vida.vencimento_anterior(25, date(2026, 9, 23)), date(2026, 8, 25))
        self.assertEqual(vida.vencimento_anterior(31, date(2026, 3, 1)), date(2026, 2, 28))
        self.assertEqual(vida.vencimento_anterior(20, date(2026, 1, 5)), date(2025, 12, 20))
        self.assertEqual(vida.dia_da_rotina("noite", datetime(2026, 9, 24, 0, 30)), date(2026, 9, 23))
        self.assertEqual(vida.dia_da_rotina("noite", datetime(2026, 9, 23, 23, 40)), date(2026, 9, 23))
        self.assertEqual(vida.dia_da_rotina("manha", datetime(2026, 9, 24, 0, 30)), date(2026, 9, 24))


class RegressoesRevisaoFase1TestCase(VidaBaseTestCase):
    def test_hiperfoco_guarda_aviso_de_janela_e_solta_depois(self):
        self.client.post("/api/hiperfoco", json={"minutos": 50})
        with patch("notificacoes.hora_de_dormir_devida", return_value=True):
            self.assertFalse([c for c in self._notificar() if c.startswith("22h")])
        self.client.delete("/api/hiperfoco")
        corpos = self._notificar()
        self.assertEqual(len([c for c in corpos if c.startswith("22h")]), 1)
        self.assertFalse([c for c in self._notificar() if c.startswith("22h")])

    def test_agua_pausa_some_no_hiperfoco_sem_acumular(self):
        self.client.post("/api/hiperfoco", json={"minutos": 50})
        with patch("vida.slot_agua_pausa", return_value=11):
            self.assertFalse([c for c in self._notificar() if "copo de agua" in c])
        self.client.delete("/api/hiperfoco")
        self.assertFalse([c for c in self._notificar() if "copo de agua" in c])

    def test_aviso_guardado_de_outro_dia_e_descartado(self):
        conn = self._conn()
        db.definir_configuracao(conn, "avisos_adiados", json.dumps({"data": "2020-01-01", "itens": [["t", "velho"]]}))
        self.assertNotIn("velho", self._notificar())

    def test_pagar_conta_atrasada_marca_o_vencimento_certo(self):
        hoje = date.today()
        atrasado = hoje - timedelta(days=2)
        conn = self._conn()
        conta_id = db.create_conta_pessoal(conn, "Luz", atrasado.day, None)
        conn.execute("UPDATE contas_pessoais SET criado_em = '2020-01-01 00:00:00' WHERE id = ?", (conta_id,))
        conn.commit()
        conta = self.client.get("/api/contas-pessoais").get_json()[0]
        self.assertEqual(conta["proximo_vencimento"], vida.vencimento_anterior(atrasado.day, hoje).isoformat())
        self.assertLess(conta["dias_ate_vencer"], 0)
        r = self.client.post(f"/api/contas-pessoais/{conta_id}/paga").get_json()
        self.assertEqual(r["vencimento"], conta["proximo_vencimento"])
        depois = self.client.get("/api/contas-pessoais").get_json()[0]
        self.assertGreater(depois["dias_ate_vencer"], 0)

    def test_conta_cadastrada_depois_do_vencimento_comeca_no_proximo(self):
        ontem = date.today() - timedelta(days=1)
        self.client.post("/api/contas-pessoais", json={"nome": "Luz", "dia_vencimento": ontem.day})
        conta = self.client.get("/api/contas-pessoais").get_json()[0]
        self.assertGreater(conta["dias_ate_vencer"], 0)

    def test_valor_infinito_rejeitado(self):
        corpo = '{"nome": "Luz", "dia_vencimento": 5, "valor": 1e999}'
        r = self.client.post("/api/contas-pessoais", data=corpo, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/medidas", data='{"tipo": "peso", "valor": 1e999}', content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_rotina_de_dias_passados_nao_disputa_o_essencial(self):
        hoje = date.today()
        conn = self._conn()
        modelo = conn.execute("INSERT INTO tasks (title, recorrencia) VALUES ('Remedio', 'diaria')").lastrowid
        conn.execute(
            "INSERT INTO tasks (title, due_date, recorrente_origem_id) VALUES ('Remedio', ?, ?)",
            ((hoje - timedelta(days=4)).isoformat(), modelo),
        )
        conn.commit()
        a = self._tarefa("Pagar IPVA", due=hoje.isoformat())
        with patch("claude_client.escolher_essencial", side_effect=ValueError):
            titulos = [t["title"] for t in self.client.get("/api/essencial").get_json()["tarefas"]]
        self.assertIn("Pagar IPVA", titulos)
        self.assertEqual(titulos.count("Remedio"), 1)  # so a instancia de hoje

    def test_trocar_nao_devolve_a_que_foi_recusada(self):
        ids = [self._tarefa(f"t{i}") for i in range(5)]
        with patch("claude_client.escolher_essencial", side_effect=ValueError):
            primeira = [t["id"] for t in self.client.get("/api/essencial").get_json()["tarefas"]]
        recusada = primeira[0]
        r = self.client.post("/api/essencial/trocar", json={"task_id": recusada}).get_json()
        nova = [t["id"] for t in r["tarefas"] if t["id"] not in primeira][0]
        r = self.client.post("/api/essencial/trocar", json={"task_id": nova}).get_json()
        self.assertNotIn(recusada, [t["id"] for t in r["tarefas"]])
        self.assertEqual(len(r["tarefas"]), 3)
        self.assertEqual(len(ids), 5)

    def test_rotina_da_noite_nao_zera_depois_da_meia_noite(self):
        item = self.client.get("/api/rotina?momento=noite").get_json()["itens"][0]
        antes = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=40)
        depois = antes + timedelta(minutes=50)
        with patch("app.datetime") as dt:
            dt.now.return_value = antes
            dt.fromisoformat = datetime.fromisoformat
            self.client.post(f"/api/rotina/{item['id']}/alternar")
        with patch("app.datetime") as dt:
            dt.now.return_value = depois
            dt.fromisoformat = datetime.fromisoformat
            self.assertEqual(self.client.get("/api/rotina?momento=noite").get_json()["feitos"], 1)

    def test_hiperfoco_devolve_segundos(self):
        estado = self.client.post("/api/hiperfoco", json={"minutos": 25}).get_json()
        self.assertTrue(1490 <= estado["segundos_restantes"] <= 1500)

    def test_nome_parecido_nao_zera_a_pessoa_errada(self):
        conn = self._conn()
        db.create_pessoa(conn, "Joao", 7)
        self.assertIsNone(vida.achar_pessoa(db.list_pessoas(conn), "jo"))


class TreinoTestCase(VidaBaseTestCase):
    def test_ficha_crud_e_substitui_mesmo_grupo(self):
        r = self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios": "Supino 4x10"})
        self.assertEqual(r.status_code, 201)
        self.client.post("/api/treino/fichas", json={"grupo": "peito", "exercicios": ["Supino 4x12", " ", "Crucifixo"]})
        fichas = self.client.get("/api/treino/fichas").get_json()
        self.assertEqual(len(fichas), 1)
        self.assertEqual(fichas[0]["exercicios"], "Supino 4x12\nCrucifixo")
        self.client.delete(f"/api/treino/fichas/{fichas[0]['id']}")
        self.assertEqual(self.client.get("/api/treino/fichas").get_json(), [])

    def test_tarefa_de_treino_ganha_ficha(self):
        self.client.post("/api/treino/fichas", json={"grupo": "Peito", "exercicios": "Supino"})
        ficha_id = self.client.get("/api/treino/fichas").get_json()[0]["id"]
        self._tarefa("Treino peito", due=date.today().isoformat(), hora="18:00")
        self._tarefa("Pagar luz")
        por_titulo = {t["title"]: t for t in self.client.get("/api/tasks").get_json()}
        self.assertEqual(por_titulo["Treino peito"]["fichas_treino"], [ficha_id])
        self.assertEqual(por_titulo["Pagar luz"]["fichas_treino"], [])

    def test_registro_de_treino_e_validacoes(self):
        self.assertEqual(self.client.post("/api/treino", json={"grupo": "Costas", "duracao_min": 60}).status_code, 201)
        self.assertEqual(self.client.post("/api/treino", json={}).status_code, 201)
        for ruim in [0, 601, "muito", True]:
            self.assertEqual(self.client.post("/api/treino", json={"duracao_min": ruim}).status_code, 400)
        treinos = self.client.get("/api/treino").get_json()
        self.assertEqual(len(treinos), 2)
        for corpo in [{}, {"grupo": "Peito"}, {"grupo": "", "exercicios": "x"}, {"grupo": "x" * 41, "exercicios": "x"}]:
            self.assertEqual(self.client.post("/api/treino/fichas", json=corpo).status_code, 400)

    def test_chat_salva_ficha_e_registra_treino(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertTrue(executores["salvar_ficha_treino"]({"grupo": "Perna", "exercicios": ["Agachamento 4x10"]})["ok"])
            self.assertIn("erro", executores["salvar_ficha_treino"]({"grupo": "Perna"}))
            self.assertTrue(executores["registrar_treino"]({"grupo": "Perna", "duracao_min": 50})["ok"])
            return "Anotado.", ["salvar_ficha_treino"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "perna: agachamento 4x10. treinei hoje 50 min"})
        self.assertEqual(self.client.get("/api/treino/fichas").get_json()[0]["grupo"], "Perna")
        self.assertEqual(self.client.get("/api/treino").get_json()[0]["duracao_min"], 50)


class ViagensLugaresTestCase(VidaBaseTestCase):
    def test_viagem_crud_mala_e_lugares(self):
        ida = (date.today() + timedelta(days=5)).isoformat()
        volta = (date.today() + timedelta(days=7)).isoformat()
        self.client.post("/api/lugares", json={"nome": "Ostradamus", "cidade": "Florianópolis", "tipo": "restaurante"})
        r = self.client.post("/api/viagens", json={"destino": "Florianopolis", "data_ida": ida, "data_volta": volta})
        self.assertEqual(r.status_code, 201)
        vid = r.get_json()["viagem_id"]
        with patch("claude_client.gerar_mala", return_value=(["Documento", " ", 5, "Carregador"], fake_usage())) as ia, \
                patch("app._clima_texto_para", return_value="20-28C"):
            mala = self.client.post(f"/api/viagens/{vid}/mala").get_json()
        self.assertEqual(ia.call_args.args, ("Florianopolis", 3, None, "20-28C"))
        self.assertEqual([i["texto"] for i in mala["itens"]], ["Documento", "Carregador"])
        self.assertEqual(mala["lugares"][0]["nome"], "Ostradamus")
        item_id = mala["itens"][0]["id"]
        self.assertTrue(self.client.post(f"/api/viagens/itens/{item_id}/alternar").get_json()["feito"])
        self.assertFalse(self.client.post(f"/api/viagens/itens/{item_id}/alternar").get_json()["feito"])
        self.assertEqual(self.client.post("/api/viagens/itens/99999/alternar").status_code, 404)
        self.client.delete(f"/api/viagens/{vid}")
        self.assertEqual(self.client.get("/api/viagens").get_json(), [])

    def test_validacoes_e_erros(self):
        hoje = date.today().isoformat()
        for corpo in [{}, {"destino": "X"}, {"destino": "X", "data_ida": "amanha"},
                      {"destino": "X", "data_ida": hoje, "data_volta": "2000-01-01"},
                      {"destino": "", "data_ida": hoje}, {"destino": 3, "data_ida": hoje}]:
            self.assertEqual(self.client.post("/api/viagens", json=corpo).status_code, 400, msg=repr(corpo))
        self.assertEqual(self.client.post("/api/viagens/999/mala").status_code, 404)
        vid = self.client.post("/api/viagens", json={"destino": "X", "data_ida": hoje}).get_json()["viagem_id"]
        with patch("claude_client.gerar_mala", return_value=({"x": 1}, fake_usage())), patch("app._clima_texto_para", return_value=None):
            self.assertEqual(self.client.post(f"/api/viagens/{vid}/mala").status_code, 502)
        self.assertEqual(self.client.post("/api/lugares", json={"nome": " "}).status_code, 400)

    def test_viagem_passada_some_da_lista(self):
        conn = self._conn()
        db.create_viagem(conn, "Antiga", "2020-01-01", "2020-01-05", None)
        self.assertEqual(self.client.get("/api/viagens").get_json(), [])

    def test_chat_registra_viagem_e_lugar(self):
        ida = (date.today() + timedelta(days=10)).isoformat()

        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertTrue(executores["registrar_viagem"]({"destino": "Gramado", "data_ida": ida})["ok"])
            self.assertIn("erro", executores["registrar_viagem"]({"destino": "Gramado", "data_ida": "semana que vem"}))
            self.assertTrue(executores["registrar_lugar"]({"nome": "Casa da Montanha", "cidade": "Gramado"})["ok"])
            return "Anotado.", ["registrar_viagem"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "vou pra Gramado"})
        viagem = self.client.get("/api/viagens").get_json()[0]
        self.assertEqual(viagem["lugares"][0]["nome"], "Casa da Montanha")


class ManutencaoComprasResponderTestCase(VidaBaseTestCase):
    def test_manutencao_crud_e_feita(self):
        ultima = (date.today() - timedelta(days=170)).isoformat()
        r = self.client.post("/api/manutencoes", json={"item": "Troca de oleo", "intervalo_meses": 6, "ultima_vez": ultima})
        self.assertEqual(r.status_code, 201)
        m = self.client.get("/api/manutencoes").get_json()[0]
        self.assertLess(m["dias_ate"], 20)
        self.client.post(f"/api/manutencoes/{m['id']}/feita")
        self.assertGreater(self.client.get("/api/manutencoes").get_json()[0]["dias_ate"], 170)
        self.assertEqual(self.client.post("/api/manutencoes/999/feita").status_code, 404)
        amanha = (date.today() + timedelta(days=1)).isoformat()
        for corpo in [{"item": "x"}, {"item": "x", "intervalo_meses": 0}, {"item": "x", "intervalo_meses": 121},
                      {"item": "", "intervalo_meses": 6}, {"item": "x", "intervalo_meses": 6, "ultima_vez": amanha},
                      {"item": "x", "intervalo_meses": 6, "ultima_vez": "ontem"}]:
            self.assertEqual(self.client.post("/api/manutencoes", json=corpo).status_code, 400, msg=repr(corpo))

    def test_manutencao_veiculo_crud(self):
        hoje = date.today().isoformat()
        r = self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Troca de oleo", "data": hoje, "km": 50000, "proxima_em_km": 55000},
        )
        self.assertEqual(r.status_code, 201)
        m_id = r.get_json()["id"]

        itens = self.client.get("/api/manutencoes-veiculo").get_json()
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["tipo"], "Troca de oleo")
        self.assertEqual(itens[0]["km"], 50000)
        self.assertEqual(itens[0]["proxima_em_km"], 55000)
        self.assertIsNone(itens[0]["proxima_em_data"])

        r_upd = self.client.put(
            f"/api/manutencoes-veiculo/{m_id}",
            json={"tipo": "Troca de oleo", "data": hoje, "km": 50000, "proxima_em_km": 60000},
        )
        self.assertEqual(r_upd.status_code, 200)
        self.assertEqual(self.client.get("/api/manutencoes-veiculo").get_json()[0]["proxima_em_km"], 60000)

        self.assertEqual(self.client.put("/api/manutencoes-veiculo/9999", json={"tipo": "x", "data": hoje}).status_code, 404)

        del_res = self.client.delete(f"/api/manutencoes-veiculo/{m_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(self.client.get("/api/manutencoes-veiculo").get_json(), [])

    def test_manutencao_veiculo_validacao(self):
        hoje = date.today().isoformat()
        for corpo in [
            {},
            {"tipo": "x"},
            {"tipo": "", "data": hoje},
            {"tipo": "x", "data": "31/12/2026"},
            {"tipo": "x", "data": hoje, "km": -5},
            {"tipo": "x", "data": hoje, "km": "lixo"},
            {"tipo": "x", "data": hoje, "proxima_em_km": -1},
            {"tipo": "x", "data": hoje, "proxima_em_data": "lixo"},
        ]:
            self.assertEqual(
                self.client.post("/api/manutencoes-veiculo", json=corpo).status_code, 400, msg=repr(corpo)
            )

    def test_manutencao_veiculo_apagar_inexistente_nao_quebra(self):
        res = self.client.delete("/api/manutencoes-veiculo/9999")
        self.assertEqual(res.status_code, 200)

    def test_compras_dedup_e_comprado(self):
        r = self.client.post("/api/compras", json={"itens": ["acabou o cafe", "Café", "arroz", " "]})
        self.assertEqual(r.get_json()["adicionados"], ["cafe", "arroz"])
        itens = self.client.get("/api/compras").get_json()
        self.assertEqual([i["item"] for i in itens], ["cafe", "arroz"])
        self.client.post(f"/api/compras/{itens[0]['id']}/comprado")
        self.assertEqual([i["item"] for i in self.client.get("/api/compras").get_json()], ["arroz"])
        self.client.post("/api/compras", json={"item": "cafe"})
        self.assertEqual(len(self.client.get("/api/compras").get_json()), 2)
        for corpo in [{}, {"itens": []}, {"itens": [" "]}, {"itens": 5}]:
            self.assertEqual(self.client.post("/api/compras", json=corpo).status_code, 400, msg=repr(corpo))

    def test_chat_adiciona_compra(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertEqual(executores["adicionar_compras"]({"itens": ["leite"]})["adicionados"], ["leite"])
            return "Anotado.", ["adicionar_compras"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "acabou o leite"})
        self.assertEqual(self.client.get("/api/compras").get_json()[0]["item"], "leite")

    def test_responder_crud(self):
        self.assertEqual(self.client.post("/api/responder", json={"quem": " "}).status_code, 400)
        rid = self.client.post("/api/responder", json={"quem": "Joao", "sobre": "orcamento"}).get_json()["id"]
        self.assertEqual(self.client.get("/api/responder").get_json()[0]["dias"], 0)
        self.client.post(f"/api/responder/{rid}/feito")
        self.assertEqual(self.client.get("/api/responder").get_json(), [])

    def test_chat_registra_responder_e_saida(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            self.assertTrue(executores["registrar_responder"]({"quem": "Maria"})["ok"])
            self.assertTrue(executores["marcar_saida_noite"]({})["ok"])
            return "Anotado.", ["registrar_responder"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "tenho que responder a Maria; hoje vou sair a noite"})
        self.assertEqual(self.client.get("/api/responder").get_json()[0]["quem"], "Maria")
        conn = self._conn()
        self.assertEqual(db.obter_configuracao(conn, "saida_noite_data"), date.today().isoformat())


class MensagemDificilTestCase(VidaBaseTestCase):
    def test_redige_duas_versoes(self):
        with patch("claude_client.redigir_mensagem_dificil", return_value=({"direta": "a", "gentil": "b"}, fake_usage())):
            r = self.client.post("/api/mensagem-dificil", json={"situacao": "cobrar o Joao", "para_quem": "Joao"})
        self.assertEqual(r.get_json(), {"direta": "a", "gentil": "b"})

    def test_erros(self):
        for corpo in [{}, {"situacao": " "}, {"situacao": "x" * 1501}]:
            self.assertEqual(self.client.post("/api/mensagem-dificil", json=corpo).status_code, 400)
        with patch("claude_client.redigir_mensagem_dificil", return_value=({"direta": "a"}, fake_usage())):
            self.assertEqual(self.client.post("/api/mensagem-dificil", json={"situacao": "x"}).status_code, 502)


class AtalhoLocalTestCase(VidaBaseTestCase):
    def _local(self, **corpo):
        return self.client.post("/api/atalho/local", json=corpo)

    def test_chegou_em_casa_com_compromisso_depois(self):
        hoje = date.today().isoformat()
        with patch("app.datetime") as dt:
            dt.now.return_value = datetime.combine(date.today(), datetime.min.time()).replace(hour=12)
            dt.fromisoformat = datetime.fromisoformat
            self._tarefa("Obra do Jorge", due=hoje, hora="14:00")
            r = self._local(evento="chegou", lugar="Casa")
        self.assertEqual(r.get_json()["mensagem"], "Proximo: Obra do Jorge as 14:00 - sai ate 13:30.")

    def test_saiu_de_casa_checklist_e_dedup(self):
        with patch("app.datetime") as dt:
            dt.now.return_value = datetime(2026, 9, 25, 20, 0)  # sexta a noite
            dt.fromisoformat = datetime.fromisoformat
            conn = self._conn()
            db.definir_configuracao(conn, "saida_noite_data", "2026-09-25")
            r = self._local(evento="saiu", lugar="casa", bateria=30).get_json()
            self.assertIn("carteira", r["mensagem"])
            self.assertIn("carregador (bateria em 30%)", r["mensagem"])
            self.assertIn("bigode", r["mensagem"])
            self.assertEqual(self._local(evento="saiu", lugar="casa", bateria=30).get_json()["mensagem"], "")

    def test_mercado_so_com_lista(self):
        self.assertEqual(self._local(evento="chegou", lugar="mercado").get_json()["mensagem"], "")
        self.client.post("/api/compras", json={"itens": ["cafe", "arroz"]})
        self.assertEqual(self._local(evento="chegou", lugar="mercado").get_json()["mensagem"], "Lista de compras: cafe, arroz.")
        self.assertEqual(self._local(evento="chegou", lugar="farmacia").get_json()["mensagem"], "")

    def test_validacao_e_token(self):
        for corpo in [{}, {"evento": "entrou", "lugar": "casa"}, {"evento": "chegou"}, {"evento": "chegou", "lugar": 5}]:
            self.assertEqual(self.client.post("/api/atalho/local", json=corpo).status_code, 400, msg=repr(corpo))
        anonimo = app.app.test_client()
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "segredo"}):
            self.assertEqual(anonimo.post("/api/atalho/local", json={"evento": "chegou", "lugar": "casa"}).status_code, 401)
            ok = anonimo.post(
                "/api/atalho/local", json={"evento": "chegou", "lugar": "casa"}, headers={"X-Webhook-Token": "segredo"}
            )
            self.assertEqual(ok.status_code, 200)


class AvisosFase2TestCase(VidaBaseTestCase):
    def _avisos(self, agora):
        conn = self._conn()
        with patch("app.clima.resumo_chuva_hoje_para_cidade", return_value=None):
            return {(t, c) for t, _, _, c in app._avisos_fase2(conn, agora)}

    def _tipos(self, agora):
        return {t for t, _ in self._avisos(agora)}

    def test_agua_pausa_so_se_nao_bebeu_agora(self):
        quarta = datetime(2026, 9, 23, 11, 1)
        self.assertIn("agua_pausa", self._tipos(quarta))
        self.client.post("/api/hidratacao")
        self.assertNotIn("agua_pausa", self._tipos(quarta))

    def test_sono_ruim_3_noites(self):
        conn = self._conn()
        hoje = date.today()
        for d in range(3):
            conn.execute("INSERT INTO saude_dados (data, sono_horas) VALUES (?, 5.0)", ((hoje - timedelta(days=d)).isoformat(),))
        conn.commit()
        agora = datetime.combine(hoje, datetime.min.time()).replace(hour=9)
        self.assertIn("sono_ruim", self._tipos(agora))
        self.assertNotIn("sono_ruim", self._tipos(agora.replace(hour=7)))

    def test_pre_voo_vespera_e_dia(self):
        conn = self._conn()
        amanha = date.today() + timedelta(days=1)
        conn.execute("INSERT INTO voos (data, destino, hora) VALUES (?, 'SBFL', '10:00')", (amanha.isoformat(),))
        conn.commit()
        vespera = datetime.combine(date.today(), datetime.min.time()).replace(hour=20)
        avisos = self._avisos(vespera)
        self.assertTrue([c for t, c in avisos if t == "pre_voo" and "carta wac" in c])
        dia = datetime.combine(amanha, datetime.min.time()).replace(hour=7)
        with patch("app.date") as d:
            d.today.return_value = amanha
            d.fromisoformat = date.fromisoformat
            self.assertIn("pre_voo", {t for t, _, _, _ in app._avisos_fase2(conn, dia)})
        self.assertNotIn("pre_voo", {t for t, _, _, _ in app._avisos_fase2(conn, dia.replace(hour=11))})

    def test_viagem_documento_3_dias_antes(self):
        ida = date.today() + timedelta(days=3)
        self.client.post("/api/viagens", json={"destino": "Gramado", "data_ida": ida.isoformat()})
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertTrue([c for t, c in self._avisos(agora) if t == "viagem_documento" and "em 3 dia(s)" in c])

    def test_manutencao_perto(self):
        ultima = (date.today() - timedelta(days=178)).isoformat()
        self.client.post("/api/manutencoes", json={"item": "Oleo", "intervalo_meses": 6, "ultima_vez": ultima})
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertIn("manutencao", self._tipos(agora))

    def test_manutencao_veiculo_perto_por_data(self):
        hoje = date.today().isoformat()
        proxima = (date.today() + timedelta(days=5)).isoformat()
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Revisao", "data": hoje, "proxima_em_data": proxima},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertTrue(
            [c for t, c in self._avisos(agora) if t == "manutencao_veiculo" and "Revisao" in c]
        )

    def test_manutencao_veiculo_longe_por_data_nao_avisa(self):
        hoje = date.today().isoformat()
        proxima = (date.today() + timedelta(days=60)).isoformat()
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Revisao", "data": hoje, "proxima_em_data": proxima},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertNotIn("manutencao_veiculo", self._tipos(agora))

    def test_manutencao_veiculo_perto_por_km(self):
        hoje = date.today().isoformat()
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Troca de oleo", "data": hoje, "km": 49800, "proxima_em_km": 50000},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertTrue(
            [c for t, c in self._avisos(agora) if t == "manutencao_veiculo" and "faltam" in c]
        )

    def test_manutencao_veiculo_longe_por_km_nao_avisa(self):
        hoje = date.today().isoformat()
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Troca de oleo", "data": hoje, "km": 40000, "proxima_em_km": 50000},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertNotIn("manutencao_veiculo", self._tipos(agora))

    def test_manutencao_veiculo_ja_passou_do_km_avisa(self):
        hoje = date.today().isoformat()
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Troca de oleo", "data": hoje, "km": 50500, "proxima_em_km": 50000},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertTrue(
            [c for t, c in self._avisos(agora) if t == "manutencao_veiculo" and "passou" in c]
        )

    def test_manutencao_veiculo_so_considera_registro_mais_recente_por_tipo(self):
        hoje = date.today().isoformat()
        antiga = (date.today() - timedelta(days=200)).isoformat()
        # registro antigo do mesmo tipo, ja vencido - deveria ser substituido
        # pelo mais recente (que ainda esta longe), nao empilhar os dois
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Pneu", "data": antiga, "proxima_em_data": antiga},
        )
        self.client.post(
            "/api/manutencoes-veiculo",
            json={"tipo": "Pneu", "data": hoje, "proxima_em_data": (date.today() + timedelta(days=90)).isoformat()},
        )
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertNotIn("manutencao_veiculo", self._tipos(agora))

    def test_manutencao_veiculo_sem_proxima_definida_nunca_avisa(self):
        hoje = date.today().isoformat()
        self.client.post("/api/manutencoes-veiculo", json={"tipo": "Lavagem", "data": hoje})
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=9)
        self.assertNotIn("manutencao_veiculo", self._tipos(agora))

    def test_responder_so_do_dia_anterior_e_depois_das_10h(self):
        conn = self._conn()
        conn.execute("INSERT INTO responder (quem, criado_em) VALUES ('Joao', datetime('now', '-1 day'))")
        conn.execute("INSERT INTO responder (quem) VALUES ('Novo')")
        conn.commit()
        agora = datetime.combine(date.today(), datetime.min.time()).replace(hour=10, minute=30)
        textos = [c for t, c in self._avisos(agora) if t == "responder"]
        self.assertEqual(textos, ["Ainda falta responder: Joao."])
        self.assertNotIn("responder", self._tipos(agora.replace(hour=9)))

    def test_chuva_em_cima_de_compromisso(self):
        hoje = date.today()
        self._tarefa("Obra", due=hoje.isoformat(), hora="15:00")
        conn = self._conn()
        resumo = {"alerta": True, "hora_inicio": 14, "hora_fim": 17, "texto": "Risco de chuva entre 14h e 17h."}
        agora = datetime.combine(hoje, datetime.min.time()).replace(hour=7, minute=31)
        with patch.dict(os.environ, {"CIDADE_PADRAO": "Blumenau"}), \
                patch("app.clima.resumo_chuva_hoje_para_cidade", return_value=resumo):
            avisos = app._avisos_fase2(conn, agora)
        textos = [c for t, _, _, c in avisos if t == "clima_compromisso"]
        self.assertEqual(len(textos), 1)
        self.assertIn("Obra as 15:00", textos[0])

    def test_dica_sono_humor(self):
        conn = self._conn()
        hoje = date.today()
        for d in range(6):
            dia = (hoje - timedelta(days=d)).isoformat()
            horas, humor = (8.5, 3) if d % 2 else (5.0, 1)
            conn.execute("INSERT INTO saude_dados (data, sono_horas) VALUES (?, ?)", (dia, horas))
            conn.execute("INSERT INTO checkins (data, humor) VALUES (?, ?)", (dia, humor))
        conn.commit()
        dica = self.client.get("/api/saude/hoje").get_json()["dica_humor"]
        self.assertIn("humor", dica)
        self.assertIn("8h+", dica)


if __name__ == "__main__":
    unittest.main()
