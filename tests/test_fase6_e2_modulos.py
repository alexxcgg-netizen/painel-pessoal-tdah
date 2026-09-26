"""Fase 6, Grupo E2 (modulos): Habitos (US-E12), Projetos (US-E13), agenda no
iCloud (US-E14) e limite do cartao (US-E15).

Segue o padrao de tests/test_pin_inicial.py: db.DB_PATH pra um arquivo
temporario + db.garantir_banco_nao_producao() ANTES de importar app. CalDAV
e SEMPRE mockado aqui - nenhum teste chama iCloud de verdade (nem tenta:
caldav_client.configurado() ja devolve False sem ICLOUD_USERNAME/
ICLOUD_APP_PASSWORD no ambiente de teste, e os testes de "com CalDAV" mockam
caldav_client.configurado/criar_evento/apagar_evento explicitamente)."""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import caldav_client
import db
import vida

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402


def fake_usage():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001}


PIN_TESTE = "123456"


class Fase6E2TestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    # ---- US-E12: Habitos --------------------------------------------------

    def test_criar_habito_diario_e_listar(self):
        res = self.client.post(
            "/api/habitos", json={"nome": "Meditar", "meta": "15 min", "frequencia_tipo": "diario", "horario": "08:00"}
        )
        self.assertEqual(res.status_code, 201)
        habito_id = res.get_json()["habito_id"]

        res = self.client.get("/api/habitos")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["ativos_total"], 1)
        h = body["habitos"][0]
        self.assertEqual(h["id"], habito_id)
        self.assertEqual(h["nome"], "Meditar")
        self.assertEqual(len(h["ultimos_7"]), 7)
        # ultimos_7 termina hoje, cada dia com letra de dia da semana valida
        self.assertTrue(h["ultimos_7"][-1]["hoje"])
        self.assertEqual(h["ultimos_7"][-1]["data"], date.today().isoformat())
        for dia in h["ultimos_7"]:
            self.assertIn(dia["letra"], vida.DIAS_SEMANA_LETRAS)
        self.assertFalse(h["feito_hoje"])
        self.assertTrue(h["devido_hoje"])

    def test_criar_habito_sem_nome_da_erro(self):
        res = self.client.post("/api/habitos", json={"frequencia_tipo": "diario"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("nome", res.get_json()["error"])

    def test_criar_habito_dias_semana_exige_dias_validos(self):
        res = self.client.post("/api/habitos", json={"nome": "Academia", "frequencia_tipo": "dias_semana"})
        self.assertEqual(res.status_code, 400)

        res = self.client.post(
            "/api/habitos", json={"nome": "Academia", "frequencia_tipo": "dias_semana", "dias_semana": [0, 2, 4]}
        )
        self.assertEqual(res.status_code, 201)
        habito = self.client.get("/api/habitos").get_json()["habitos"][0]
        self.assertEqual(habito["dias_semana"], [0, 2, 4])

    def test_criar_habito_dias_semana_ignora_valores_invalidos_do_fuzzing(self):
        # lixo (string, fora de faixa, negativo, float) nunca deve quebrar a rota -
        # so filtra o que for 0..6 valido; se nada sobrar, erro claro (nao 500).
        res = self.client.post(
            "/api/habitos",
            json={"nome": "Academia", "frequencia_tipo": "dias_semana", "dias_semana": ["abc", 99, -1, 3.5, None, 2]},
        )
        self.assertEqual(res.status_code, 201)
        habito = self.client.get("/api/habitos").get_json()["habitos"][0]
        self.assertEqual(habito["dias_semana"], [2])

    def test_criar_habito_n_vezes_semana_exige_1_a_7(self):
        for invalido in (0, 8, -1, "abc", None):
            res = self.client.post(
                "/api/habitos",
                json={"nome": "Ler", "frequencia_tipo": "n_vezes_semana", "vezes_por_semana": invalido},
            )
            self.assertEqual(res.status_code, 400, invalido)

        res = self.client.post(
            "/api/habitos", json={"nome": "Ler", "frequencia_tipo": "n_vezes_semana", "vezes_por_semana": 3}
        )
        self.assertEqual(res.status_code, 201)

    def test_marcar_e_desmarcar_habito_alterna(self):
        habito_id = self.client.post("/api/habitos", json={"nome": "Agua", "frequencia_tipo": "diario"}).get_json()[
            "habito_id"
        ]
        r1 = self.client.post(f"/api/habitos/{habito_id}/marcar")
        self.assertEqual(r1.get_json(), {"feito": True})
        habito = self.client.get("/api/habitos").get_json()["habitos"][0]
        self.assertTrue(habito["feito_hoje"])
        self.assertTrue(habito["ultimos_7"][-1]["feito"])

        r2 = self.client.post(f"/api/habitos/{habito_id}/marcar")
        self.assertEqual(r2.get_json(), {"feito": False})

    def test_marcar_habito_inexistente_404(self):
        res = self.client.post("/api/habitos/999/marcar")
        self.assertEqual(res.status_code, 404)

    def test_apagar_habito_remove_da_lista_e_marcacoes(self):
        habito_id = self.client.post("/api/habitos", json={"nome": "Correr", "frequencia_tipo": "diario"}).get_json()[
            "habito_id"
        ]
        self.client.post(f"/api/habitos/{habito_id}/marcar")
        res = self.client.delete(f"/api/habitos/{habito_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/habitos").get_json()["ativos_total"], 0)
        conn = db.get_db()
        restante = conn.execute("SELECT * FROM habito_marcacoes WHERE habito_id = ?", (habito_id,)).fetchone()
        conn.close()
        self.assertIsNone(restante)

    def test_habito_nome_muito_grande_e_recusado(self):
        res = self.client.post("/api/habitos", json={"nome": "x" * 500, "frequencia_tipo": "diario"})
        self.assertEqual(res.status_code, 400)

    def test_chat_registrar_habito_e_marcar_habito(self):
        def fake_chat_registrar(mensagens, contexto, memorias, executores):
            resultado = executores["registrar_habito"](
                {"nome": "Meditar", "frequencia_tipo": "diario", "horario": "08:00"}
            )
            self.assertEqual(resultado["ok"], True)
            return "Beleza, criei o habito.", ["registrar_habito"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat_registrar):
            res = self.client.post("/api/chat", json={"mensagem": "meditar 15 min todo dia as 8h"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(self.client.get("/api/habitos").get_json()["habitos"]), 1)

        def fake_chat_marcar(mensagens, contexto, memorias, executores):
            resultado = executores["marcar_habito"]({"nome": "medit"})
            self.assertEqual(resultado["ok"], True)
            self.assertTrue(resultado["feito"])
            return "Marquei.", ["marcar_habito"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat_marcar):
            res = self.client.post("/api/chat", json={"mensagem": "marquei que meditei hoje"})
        self.assertEqual(res.status_code, 200)

    def test_chat_marcar_habito_inexistente_devolve_erro_sem_quebrar(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["marcar_habito"]({"nome": "nao existe isso"})
            self.assertIn("erro", resultado)
            return "Nao achei esse habito.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            res = self.client.post("/api/chat", json={"mensagem": "marquei nao existe isso"})
        self.assertEqual(res.status_code, 200)

    # ---- US-E12: funcoes puras (vida.py) -----------------------------------

    def test_letra_dia_semana_bate_com_segunda_a_domingo(self):
        segunda = date(2026, 9, 21)  # 21/09/2026 e uma segunda-feira
        letras = [vida.letra_dia_semana(segunda + timedelta(days=i)) for i in range(7)]
        self.assertEqual(letras, ["S", "T", "Q", "Q", "S", "S", "D"])

    def test_ultimos_n_dias_termina_hoje_em_ordem_crescente(self):
        hoje = date(2026, 9, 23)
        dias = vida.ultimos_n_dias(hoje, 7)
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[-1], hoje)
        self.assertEqual(dias[0], hoje - timedelta(days=6))
        self.assertEqual(dias, sorted(dias))

    def test_parse_dias_semana_ignora_lixo(self):
        self.assertEqual(vida.parse_dias_semana(None), set())
        self.assertEqual(vida.parse_dias_semana(""), set())
        self.assertEqual(vida.parse_dias_semana("0,2,4"), {0, 2, 4})
        self.assertEqual(vida.parse_dias_semana("abc,99,-1, 3 ,3"), {3})

    def test_habito_devido_em_dias_semana(self):
        habito = {"frequencia_tipo": "dias_semana", "dias_semana": "0,2,4"}
        segunda = date(2026, 9, 21)
        terca = date(2026, 9, 22)
        self.assertTrue(vida.habito_devido_em(habito, segunda))
        self.assertFalse(vida.habito_devido_em(habito, terca))

    def test_habito_devido_em_n_vezes_semana_para_quando_bate_meta(self):
        habito = {"frequencia_tipo": "n_vezes_semana", "vezes_por_semana": 2}
        hoje = date(2026, 9, 23)
        self.assertTrue(vida.habito_devido_em(habito, hoje, vezes_feitas_semana=0))
        self.assertTrue(vida.habito_devido_em(habito, hoje, vezes_feitas_semana=1))
        self.assertFalse(vida.habito_devido_em(habito, hoje, vezes_feitas_semana=2))

    def test_habito_passou_batido_so_com_horario_devido_e_1h_depois(self):
        habito = {"frequencia_tipo": "diario", "horario": "08:00"}
        antes = datetime(2026, 9, 23, 8, 30)
        depois = datetime(2026, 9, 23, 9, 1)
        self.assertFalse(vida.habito_passou_batido(habito, antes, marcado_hoje=False))
        self.assertTrue(vida.habito_passou_batido(habito, depois, marcado_hoje=False))
        self.assertFalse(vida.habito_passou_batido(habito, depois, marcado_hoje=True))

    def test_habito_passou_batido_sem_horario_nunca_acusa(self):
        habito = {"frequencia_tipo": "diario", "horario": None}
        self.assertFalse(vida.habito_passou_batido(habito, datetime(2026, 9, 23, 23, 0), marcado_hoje=False))

    def test_habito_passou_batido_dia_nao_devido_nunca_acusa(self):
        habito = {"frequencia_tipo": "dias_semana", "dias_semana": "0", "horario": "08:00"}
        terca_tarde = datetime(2026, 9, 22, 20, 0)  # terca - habito e so segunda
        self.assertFalse(vida.habito_passou_batido(habito, terca_tarde, marcado_hoje=False))

    # ---- US-E13: Projetos ---------------------------------------------------

    def test_criar_projeto_e_etapas_calcula_percentual_e_proxima(self):
        projeto_id = self.client.post("/api/projetos", json={"nome": "Reforma"}).get_json()["projeto_id"]
        e1 = self.client.post(f"/api/projetos/{projeto_id}/etapas", json={"texto": "Comprar tinta"}).get_json()[
            "etapa_id"
        ]
        self.client.post(f"/api/projetos/{projeto_id}/etapas", json={"texto": "Pintar"})

        projetos = self.client.get("/api/projetos").get_json()
        self.assertEqual(len(projetos), 1)
        p = projetos[0]
        self.assertEqual(p["total_etapas"], 2)
        self.assertEqual(p["etapas_feitas"], 0)
        self.assertEqual(p["percentual"], 0)
        self.assertEqual(p["proxima_etapa"]["texto"], "Comprar tinta")

        self.client.post(f"/api/projetos/etapas/{e1}/concluir")
        p = self.client.get("/api/projetos").get_json()[0]
        self.assertEqual(p["etapas_feitas"], 1)
        self.assertEqual(p["percentual"], 50)
        self.assertEqual(p["proxima_etapa"]["texto"], "Pintar")
        self.assertEqual(p["dias_sem_toque"], 0)

    def test_projeto_sem_etapas_nao_quebra(self):
        self.client.post("/api/projetos", json={"nome": "Vazio"})
        p = self.client.get("/api/projetos").get_json()[0]
        self.assertEqual(p["total_etapas"], 0)
        self.assertEqual(p["percentual"], 0)
        self.assertIsNone(p["proxima_etapa"])
        self.assertIsNone(p["dias_sem_toque"])

    def test_projeto_sem_prazo_nao_calcula_posicao_hoje(self):
        self.client.post("/api/projetos", json={"nome": "Sem prazo"})
        p = self.client.get("/api/projetos").get_json()[0]
        self.assertIsNone(p["posicao_hoje"])

    def test_projeto_status_atrasado_quando_passa_do_prazo_com_pendencia(self):
        projeto_id = self.client.post(
            "/api/projetos", json={"nome": "Atrasado", "prazo_final": "2020-01-01"}
        ).get_json()["projeto_id"]
        self.client.post(f"/api/projetos/{projeto_id}/etapas", json={"texto": "Alguma coisa"})
        p = self.client.get("/api/projetos").get_json()[0]
        self.assertEqual(p["status"], "atrasado")

    def test_projeto_status_pausado_e_manual_e_nunca_e_sobrescrito(self):
        projeto_id = self.client.post(
            "/api/projetos", json={"nome": "Pausado", "prazo_final": "2020-01-01"}
        ).get_json()["projeto_id"]
        res = self.client.post(f"/api/projetos/{projeto_id}/status", json={"status": "pausado"})
        self.assertEqual(res.status_code, 200)
        p = self.client.get("/api/projetos").get_json()[0]
        self.assertEqual(p["status"], "pausado")
        self.assertTrue(p["status_manual"])

    def test_definir_status_invalido_400(self):
        projeto_id = self.client.post("/api/projetos", json={"nome": "X"}).get_json()["projeto_id"]
        res = self.client.post(f"/api/projetos/{projeto_id}/status", json={"status": "lixo"})
        self.assertEqual(res.status_code, 400)

    def test_adicionar_etapa_em_projeto_inexistente_400(self):
        res = self.client.post("/api/projetos/9999/etapas", json={"texto": "Algo"})
        self.assertEqual(res.status_code, 400)

    def test_concluir_e_apagar_etapa_inexistente_404(self):
        self.assertEqual(self.client.post("/api/projetos/etapas/9999/concluir").status_code, 404)
        self.assertEqual(self.client.delete("/api/projetos/etapas/9999").status_code, 404)

    def test_apagar_projeto_remove_etapas(self):
        projeto_id = self.client.post("/api/projetos", json={"nome": "Apagar"}).get_json()["projeto_id"]
        self.client.post(f"/api/projetos/{projeto_id}/etapas", json={"texto": "Etapa"})
        self.client.delete(f"/api/projetos/{projeto_id}")
        self.assertEqual(self.client.get("/api/projetos").get_json(), [])
        conn = db.get_db()
        restante = conn.execute("SELECT * FROM projeto_etapas WHERE projeto_id = ?", (projeto_id,)).fetchone()
        conn.close()
        self.assertIsNone(restante)

    def test_viagem_nao_migra_pra_projetos_mas_expoe_formato_convertido(self):
        viagem_id = self.client.post(
            "/api/viagens", json={"destino": "Floripa", "data_ida": "2026-10-01", "data_volta": "2026-10-05"}
        ).get_json()["viagem_id"]
        conn = db.get_db()
        db.substituir_itens_viagem(conn, viagem_id, ["Protetor solar", "Passaporte"])
        conn.close()

        # nunca aparece em /api/projetos (nao migrou, nao duplicou dado)
        self.assertEqual(self.client.get("/api/projetos").get_json(), [])

        res = self.client.get(f"/api/viagens/{viagem_id}/como-projeto")
        self.assertEqual(res.status_code, 200)
        convertido = res.get_json()
        self.assertEqual(convertido["nome"], "Viagem: Floripa")
        self.assertEqual(convertido["total_etapas"], 2)
        self.assertEqual(convertido["prazo_final"], "2026-10-05")
        self.assertIn("percentual", convertido)

        # continua existindo em viagens/viagem_itens, intocado
        viagens = self.client.get("/api/viagens").get_json()
        self.assertEqual(len(viagens), 1)

    def test_viagem_como_projeto_inexistente_404(self):
        res = self.client.get("/api/viagens/9999/como-projeto")
        self.assertEqual(res.status_code, 404)

    def test_chat_criar_projeto_adicionar_etapa_concluir_etapa(self):
        def fake_chat_criar(mensagens, contexto, memorias, executores):
            resultado = executores["criar_projeto"]({"nome": "Lancamento do curso"})
            self.assertTrue(resultado["ok"])
            return "Criei o projeto.", ["criar_projeto"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat_criar):
            self.client.post("/api/chat", json={"mensagem": "novo projeto: lancamento do curso"})

        def fake_chat_etapa(mensagens, contexto, memorias, executores):
            resultado = executores["adicionar_etapa"]({"nome_projeto": "lancamento", "texto": "Gravar aulas"})
            self.assertTrue(resultado["ok"])
            return "Adicionei a etapa.", ["adicionar_etapa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat_etapa):
            self.client.post("/api/chat", json={"mensagem": "etapa do lancamento: gravar aulas"})

        def fake_chat_concluir(mensagens, contexto, memorias, executores):
            resultado = executores["concluir_etapa"]({"nome_projeto": "lancamento"})
            self.assertTrue(resultado["ok"])
            self.assertEqual(resultado["etapa"], "Gravar aulas")
            return "Concluida.", ["concluir_etapa"], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat_concluir):
            self.client.post("/api/chat", json={"mensagem": "terminei de gravar as aulas do lancamento"})

        p = self.client.get("/api/projetos").get_json()[0]
        self.assertEqual(p["percentual"], 100)

    def test_chat_concluir_etapa_sem_pendencia_devolve_erro(self):
        self.client.post("/api/projetos", json={"nome": "Projeto sem etapa"})

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["concluir_etapa"]({"nome_projeto": "sem etapa"})
            self.assertIn("erro", resultado)
            return "Nao tem etapa pendente.", [], fake_usage()

        with patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "termina a proxima etapa do projeto sem etapa"})

    # ---- US-E13: funcoes puras (vida.py) -------------------------------------

    def test_calcular_projeto_posicao_hoje_na_metade(self):
        etapas = []
        calculo = vida.calcular_projeto(etapas, "2026-10-11", "2026-09-21 10:00:00", date(2026, 10, 1))
        # 20 dias no total (21/09 a 11/10), hoje = 01/10 => 10 dias decorridos = 50%
        self.assertEqual(calculo["posicao_hoje"], 50)

    def test_calcular_projeto_posicao_hoje_prazo_no_passado(self):
        calculo = vida.calcular_projeto([], "2020-01-01", "2019-01-01", date(2026, 1, 1))
        self.assertEqual(calculo["posicao_hoje"], 100)

    def test_status_projeto_calculado(self):
        hoje = date(2026, 9, 23)
        self.assertEqual(vida.status_projeto_calculado("no_rumo", None, 0, hoje), "no_rumo")
        self.assertEqual(vida.status_projeto_calculado("no_rumo", "2020-01-01", 50, hoje), "atrasado")
        self.assertEqual(vida.status_projeto_calculado("no_rumo", "2020-01-01", 100, hoje), "no_rumo")
        self.assertEqual(vida.status_projeto_calculado("pausado", "2020-01-01", 0, hoje), "pausado")

    # ---- US-E14: agenda no calendario "Painel" (CalDAV mockado) -------------

    def test_criar_evento_sem_caldav_configurado_devolve_erro_claro(self):
        # ambiente de teste nunca tem ICLOUD_USERNAME/ICLOUD_APP_PASSWORD - a
        # rota tem que responder com erro claro, nunca 500.
        res = self.client.post(
            "/api/agenda/eventos",
            json={"titulo": "Reuniao", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("não configurada", res.get_json()["error"])

    def test_criar_evento_com_caldav_mockado_registra_localmente(self):
        def fake_criar(titulo, inicio, fim, lembrar=None):
            self.assertEqual(titulo, "Reuniao")
            self.assertEqual(lembrar, 30)
            return {"uid": "uid-123", "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.criar_evento", side_effect=fake_criar
        ) as mock_criar:
            res = self.client.post(
                "/api/agenda/eventos",
                json={
                    "titulo": "Reuniao",
                    "data": "2026-09-29",
                    "hora_inicio": "14:00",
                    "hora_fim": "15:00",
                    "lembrar_min_antes": 30,
                },
            )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["uid"], "uid-123")
        mock_criar.assert_called_once()

        criados = self.client.get("/api/agenda/eventos-criados").get_json()
        self.assertEqual(len(criados), 1)
        self.assertEqual(criados[0]["uid"], "uid-123")

    def test_criar_evento_hora_fim_antes_do_inicio_400(self):
        with patch("caldav_client.configurado", return_value=True):
            res = self.client.post(
                "/api/agenda/eventos",
                json={"titulo": "X", "data": "2026-09-29", "hora_inicio": "15:00", "hora_fim": "14:00"},
            )
        self.assertEqual(res.status_code, 400)

    def test_criar_evento_campos_invalidos_400_sem_quebrar(self):
        casos = [
            {},
            {"titulo": "", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00"},
            {"titulo": "X", "data": "data invalida", "hora_inicio": "14:00", "hora_fim": "15:00"},
            {"titulo": "X", "data": "2026-09-29", "hora_inicio": "25:99", "hora_fim": "15:00"},
            {"titulo": "X", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00", "lembrar_min_antes": -5},
            {"titulo": "X", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00", "lembrar_min_antes": "abc"},
        ]
        with patch("caldav_client.configurado", return_value=True):
            for corpo in casos:
                res = self.client.post("/api/agenda/eventos", json=corpo)
                self.assertEqual(res.status_code, 400, corpo)

    def test_apagar_evento_nao_registrado_e_recusado_e_nunca_chama_caldav(self):
        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.apagar_evento"
        ) as mock_apagar:
            res = self.client.delete("/api/agenda/eventos/uid-que-o-painel-nunca-criou")
        self.assertEqual(res.status_code, 400)
        self.assertIn("não foi criado pelo painel", res.get_json()["error"])
        mock_apagar.assert_not_called()

    def test_apagar_evento_registrado_funciona_e_esquece_localmente(self):
        conn = db.get_db()
        db.registrar_evento_criado(conn, "uid-registrado", "Reuniao", "2026-09-29T14:00:00", "2026-09-29T15:00:00")
        conn.close()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.apagar_evento", return_value=True
        ) as mock_apagar:
            res = self.client.delete("/api/agenda/eventos/uid-registrado")
        self.assertEqual(res.status_code, 200)
        mock_apagar.assert_called_once_with("uid-registrado")
        self.assertEqual(self.client.get("/api/agenda/eventos-criados").get_json(), [])

    def test_apagar_evento_registrado_sem_caldav_configurado_da_erro_e_nao_esquece(self):
        conn = db.get_db()
        db.registrar_evento_criado(conn, "uid-x", "T", "2026-09-29T14:00:00", "2026-09-29T15:00:00")
        conn.close()
        res = self.client.delete("/api/agenda/eventos/uid-x")
        self.assertEqual(res.status_code, 400)
        # continua registrado - a tentativa falhou antes de apagar de verdade
        self.assertEqual(len(self.client.get("/api/agenda/eventos-criados").get_json()), 1)

    def test_chat_agendar_evento(self):
        def fake_criar(titulo, inicio, fim, lembrar=None):
            return {"uid": "uid-chat", "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}

        def fake_chat(mensagens, contexto, memorias, executores):
            resultado = executores["agendar_evento"](
                {"titulo": "Reuniao", "data": "2026-09-29", "hora_inicio": "14:00", "hora_fim": "15:00", "lembrar_min_antes": 30}
            )
            self.assertTrue(resultado["ok"])
            return "Agendei.", ["agendar_evento"], fake_usage()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client.criar_evento", side_effect=fake_criar
        ):
            with patch("claude_client.chat", side_effect=fake_chat):
                res = self.client.post(
                    "/api/chat", json={"mensagem": "reuniao terca dia 29 das 14h as 15h, lembrar 30 min antes"}
                )
        self.assertEqual(res.status_code, 200)

    # ---- US-E14: caldav_client.py isolado (sempre mockado, nunca iCloud real)

    def test_caldav_criar_evento_sem_configuracao_levanta_erro_claro(self):
        with patch("caldav_client.configurado", return_value=False):
            with self.assertRaises(caldav_client.NaoConfiguradoError):
                caldav_client.criar_evento("X", datetime(2026, 9, 29, 14, 0), datetime(2026, 9, 29, 15, 0))

    def test_caldav_apagar_evento_sem_configuracao_levanta_erro_claro(self):
        with patch("caldav_client.configurado", return_value=False):
            with self.assertRaises(caldav_client.NaoConfiguradoError):
                caldav_client.apagar_evento("qualquer-uid")

    def test_caldav_criar_evento_usa_calendario_painel_mockado(self):
        eventos_salvos = []

        class FakeCalendar:
            def get_display_name(self):
                return "Painel"

            def add_event(self, **kwargs):
                eventos_salvos.append(kwargs)

        class FakePrincipal:
            def calendars(self):
                return [FakeCalendar()]

            def make_calendar(self, name=None):
                raise AssertionError("nao deveria criar - o calendario 'Painel' ja existe")

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def principal(self):
                return FakePrincipal()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client._client", return_value=FakeClient()
        ):
            resultado = caldav_client.criar_evento(
                "Reuniao", datetime(2026, 9, 29, 14, 0), datetime(2026, 9, 29, 15, 0), lembrar_min_antes=30
            )
        self.assertEqual(resultado["titulo"], "Reuniao")
        self.assertTrue(resultado["uid"])
        self.assertEqual(len(eventos_salvos), 1)
        self.assertEqual(eventos_salvos[0]["summary"], "Reuniao")
        self.assertEqual(eventos_salvos[0]["alarm_trigger"], timedelta(minutes=-30))

    def test_caldav_criar_evento_cria_calendario_painel_se_nao_existir(self):
        criado = {}

        class FakeCalendarNova:
            def add_event(self, **kwargs):
                criado["kwargs"] = kwargs

        class FakePrincipal:
            def calendars(self):
                return []

            def make_calendar(self, name=None):
                self.nome_pedido = name
                return FakeCalendarNova()

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def principal(self):
                return FakePrincipal()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client._client", return_value=FakeClient()
        ):
            caldav_client.criar_evento("X", datetime(2026, 9, 29, 14, 0), datetime(2026, 9, 29, 15, 0))
        self.assertIn("kwargs", criado)

    def test_caldav_apagar_evento_uid_nao_encontrado_devolve_false(self):
        class FakeCalendar:
            def get_display_name(self):
                return "Painel"

            def event_by_uid(self, uid):
                raise Exception("nao encontrado")

        class FakePrincipal:
            def calendars(self):
                return [FakeCalendar()]

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def principal(self):
                return FakePrincipal()

        with patch("caldav_client.configurado", return_value=True), patch(
            "caldav_client._client", return_value=FakeClient()
        ):
            self.assertFalse(caldav_client.apagar_evento("uid-inexistente"))

    # ---- US-E15: limite do cartao -------------------------------------------

    def test_bancos_sem_limite_nao_tem_aviso(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        conn.close()
        contas = self.client.get("/api/bancos").get_json()
        self.assertEqual(contas[0]["limite"], None)
        self.assertIsNone(contas[0]["limite_info"])

    def test_definir_limite_e_calcular_fracao(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        hoje = date.today().isoformat()
        db.insert_bank_transactions(
            conn, conta_id, [{"data": hoje, "descricao": "compra", "valor": -900.0, "external_id": "t1"}]
        )
        conn.close()

        res = self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": 1000})
        self.assertEqual(res.status_code, 200)

        contas = self.client.get("/api/bancos").get_json()
        conta = contas[0]
        self.assertEqual(conta["limite"], 1000.0)
        self.assertEqual(conta["gasto_ciclo"], 900.0)
        self.assertAlmostEqual(conta["limite_info"]["fracao"], 0.9)
        self.assertAlmostEqual(conta["limite_info"]["sobra"], 100.0)

    def test_definir_limite_invalido_400(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        conn.close()
        for invalido in (-10, 0, "abc", float("nan")):
            res = self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": invalido})
            self.assertEqual(res.status_code, 400, invalido)

    def test_definir_limite_vazio_apaga_limite(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        conn.close()
        self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": 1000})
        self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": None})
        contas = self.client.get("/api/bancos").get_json()
        self.assertIsNone(contas[0]["limite"])
        self.assertIsNone(contas[0]["limite_info"])

    def test_definir_limite_conta_inexistente_400(self):
        res = self.client.post("/api/bancos/9999/limite", json={"limite": 1000})
        self.assertEqual(res.status_code, 400)

    def test_modo_visitante_oculta_limite_do_cartao(self):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, "nubank", "cartao")
        conn.close()
        self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": 1000})

        self.client.post("/api/modo-visitante", json={"ativar": True})
        self.assertEqual(self.client.get("/api/bancos").get_json(), [])
        res = self.client.post(f"/api/bancos/{conta_id}/limite", json={"limite": 500})
        self.assertEqual(res.status_code, 403)
        self.client.post("/api/modo-visitante", json={"pin": PIN_TESTE})

    def test_fracao_limite_cartao_pura(self):
        self.assertIsNone(vida.fracao_limite_cartao(500, None))
        self.assertIsNone(vida.fracao_limite_cartao(500, 0))
        self.assertIsNone(vida.fracao_limite_cartao(500, -100))
        resultado = vida.fracao_limite_cartao(500, 1000)
        self.assertEqual(resultado, {"fracao": 0.5, "sobra": 500.0})
        # gasto negativo (dado sujo) nunca vira fracao negativa
        self.assertEqual(vida.fracao_limite_cartao(-50, 1000)["fracao"], 0.0)
        # gasto muito acima do limite trava num teto sao (1.5) em vez de estourar
        estourado = vida.fracao_limite_cartao(50000, 1000)
        self.assertEqual(estourado["fracao"], 1.5)
        self.assertLess(estourado["sobra"], 0)

    def test_gasto_mes_conta_soma_so_saidas_do_mes_da_conta(self):
        conn = db.get_db()
        conta_a = db.get_or_create_bank_account(conn, "nubank", "cartao")
        conta_b = db.get_or_create_bank_account(conn, "caixa", "cartao")
        hoje = date.today()
        mes_passado = (hoje.replace(day=1) - timedelta(days=1)).isoformat()
        db.insert_bank_transactions(
            conn,
            conta_a,
            [
                {"data": hoje.isoformat(), "descricao": "a", "valor": -100.0, "external_id": "a1"},
                {"data": hoje.isoformat(), "descricao": "b", "valor": 500.0, "external_id": "a2"},  # entrada, nao conta
                {"data": mes_passado, "descricao": "c", "valor": -300.0, "external_id": "a3"},  # mes errado
            ],
        )
        db.insert_bank_transactions(
            conn, conta_b, [{"data": hoje.isoformat(), "descricao": "d", "valor": -999.0, "external_id": "b1"}]
        )
        conn.close()
        ano_mes = hoje.strftime("%Y-%m")
        conn = db.get_db()
        total_a = db.gasto_mes_conta(conn, conta_a, ano_mes)
        conn.close()
        self.assertEqual(total_a, 100.0)


if __name__ == "__main__":
    unittest.main()
