"""Faixa P1a (Fase 7) - testes de rotas/p1a_caixa.py: o Blueprint e testado
isolado (Flask app minimo, so com `bp` registrado, sem passar por
rotas.registrar_todas/app.py) pra nao depender do resto do app (PIN,
demais blueprints) so pra testar a logica DESTE blueprint - sessao/PIN em
volta de /api/assistente/caixa* e coberta pelo `@app.before_request`
global de app.py (rotas/_base.py, Etapa 0/X1), nao por este blueprint.
Isso testa JSON, status code e a checagem de token do /api/tick."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from flask import Flask

import db
from assistente import caixa
import rotas.p1a_caixa as rotas_p1a


class RotasP1aTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()
        caixa._garantir_tabela(self.conn)

        self.AGORA_TESTE = datetime(2026, 9, 24, 10, 0, 0)
        self._agora_original = caixa._agora
        caixa._agora = lambda: self.AGORA_TESTE

        self._token_original = os.environ.get("PAINEL_TICK_TOKEN")
        os.environ["PAINEL_TICK_TOKEN"] = "token-de-teste-123"

        app = Flask(__name__)
        app.register_blueprint(rotas_p1a.bp)
        app.testing = True
        self.app = app
        self.client = app.test_client()

    def tearDown(self):
        caixa._agora = self._agora_original
        if self._token_original is None:
            os.environ.pop("PAINEL_TICK_TOKEN", None)
        else:
            os.environ["PAINEL_TICK_TOKEN"] = self._token_original
        self.conn.close()
        db.DB_PATH = self._db_path_original
        self._tmp.cleanup()

    def _datetime_travado(self, momento: datetime):
        """A rota usa datetime.now() direto (nao caixa._agora) pro `agora`
        do tick/saude - trava aqui pra nao depender da hora real da
        maquina (silencio 22h-7h, "atrasado" etc)."""
        patcher = patch.object(rotas_p1a, "datetime")
        datetime_mock = patcher.start()
        datetime_mock.now.return_value = momento
        datetime_mock.strptime = datetime.strptime
        self.addCleanup(patcher.stop)
        return datetime_mock

    # ---- GET /api/assistente/caixa -----------------------------------

    def test_listar_caixa_vazia(self):
        resp = self.client.get("/api/assistente/caixa")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertEqual(corpo["itens"], [])
        self.assertEqual(corpo["pendentes"], 0)

    def test_listar_caixa_com_itens_e_contagem(self):
        caixa.enfileirar("pergunta", "Pagou o cartao?")
        caixa.enfileirar("aviso", "Conta vencendo")
        resp = self.client.get("/api/assistente/caixa")
        corpo = resp.get_json()
        self.assertEqual(len(corpo["itens"]), 2)
        self.assertEqual(corpo["pendentes"], 2)
        # ordenado por urgencia: pergunta antes de aviso
        self.assertEqual(corpo["itens"][0]["tipo"], "pergunta")

    def test_listar_caixa_filtra_por_estado(self):
        item_id = caixa.enfileirar("aviso", "Vai resolver")
        caixa.resolver(item_id, "sim")
        resp = self.client.get("/api/assistente/caixa?estado=resolvido")
        corpo = resp.get_json()
        self.assertEqual(len(corpo["itens"]), 1)
        self.assertEqual(corpo["itens"][0]["id"], int(item_id))

    def test_listar_caixa_estado_invalido_devolve_400(self):
        resp = self.client.get("/api/assistente/caixa?estado=lixo")
        self.assertEqual(resp.status_code, 400)

    def test_listar_caixa_respeita_limite(self):
        for i in range(5):
            caixa.enfileirar("sugestao", f"Sugestao {i}")
        resp = self.client.get("/api/assistente/caixa?limite=2")
        self.assertEqual(len(resp.get_json()["itens"]), 2)

    def test_listar_caixa_limite_invalido_cai_no_padrao(self):
        caixa.enfileirar("sugestao", "Uma sugestao")
        resp = self.client.get("/api/assistente/caixa?limite=abc")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["itens"]), 1)

    # ---- POST /api/assistente/caixa/<id>/responder --------------------

    def test_responder_com_sucesso(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        resp = self.client.post(
            f"/api/assistente/caixa/{item_id}/responder",
            json={"resposta": "sim", "texto": "paguei ontem"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True})
        linha = self.conn.execute(
            "SELECT * FROM assistente_itens WHERE id = ?", (int(item_id),)
        ).fetchone()
        self.assertEqual(linha["estado"], "resolvido")

    def test_responder_sem_resposta_no_corpo_devolve_400(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        resp = self.client.post(f"/api/assistente/caixa/{item_id}/responder", json={})
        self.assertEqual(resp.status_code, 400)

    def test_responder_sem_corpo_nenhum_devolve_400(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        resp = self.client.post(f"/api/assistente/caixa/{item_id}/responder")
        self.assertEqual(resp.status_code, 400)

    def test_responder_item_inexistente_devolve_404(self):
        resp = self.client.post("/api/assistente/caixa/999999/responder", json={"resposta": "sim"})
        self.assertEqual(resp.status_code, 404)

    def test_responder_resposta_invalida_devolve_400(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        resp = self.client.post(
            f"/api/assistente/caixa/{item_id}/responder", json={"resposta": "talvez"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_responder_id_nao_numerico_devolve_400(self):
        resp = self.client.post("/api/assistente/caixa/abc/responder", json={"resposta": "sim"})
        self.assertEqual(resp.status_code, 400)

    def test_responder_adiar(self):
        item_id = caixa.enfileirar("pergunta", "Confirma a viagem?")
        resp = self.client.post(
            f"/api/assistente/caixa/{item_id}/responder", json={"resposta": "adiar"}
        )
        self.assertEqual(resp.status_code, 200)
        linha = self.conn.execute(
            "SELECT * FROM assistente_itens WHERE id = ?", (int(item_id),)
        ).fetchone()
        self.assertEqual(linha["estado"], "adiado")

    # ---- POST /api/tick -------------------------------------------------

    def test_tick_sem_header_devolve_401(self):
        resp = self.client.post("/api/tick")
        self.assertEqual(resp.status_code, 401)

    def test_tick_com_token_errado_devolve_401(self):
        resp = self.client.post("/api/tick", headers={"Authorization": "Bearer token-errado"})
        self.assertEqual(resp.status_code, 401)

    def test_tick_sem_prefixo_bearer_devolve_401(self):
        resp = self.client.post("/api/tick", headers={"Authorization": "token-de-teste-123"})
        self.assertEqual(resp.status_code, 401)

    def test_tick_sem_token_configurado_no_servidor_devolve_401(self):
        os.environ.pop("PAINEL_TICK_TOKEN", None)
        resp = self.client.post("/api/tick", headers={"Authorization": "Bearer qualquer-coisa"})
        self.assertEqual(resp.status_code, 401)

    def test_tick_com_token_certo_devolve_200_e_processa(self):
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?")
        self._datetime_travado(self.AGORA_TESTE)
        with patch("assistente.caixa.enviar_push", return_value=True):
            resp = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertTrue(corpo["ok"])
        self.assertIn("pushes_enviados", corpo)
        self.assertIn("expirados", corpo)
        self.assertIn("reativados", corpo)
        linha = self.conn.execute(
            "SELECT pushes_hoje FROM assistente_itens WHERE id = ?", (int(item_id),)
        ).fetchone()
        self.assertEqual(linha["pushes_hoje"], 1)

    def test_tick_registra_horario_em_configuracoes(self):
        self._datetime_travado(self.AGORA_TESTE)
        with patch("assistente.caixa.enviar_push", return_value=True):
            self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        valor = db.obter_configuracao(self.conn, caixa.CHAVE_ULTIMO_TICK)
        self.assertEqual(valor, "2026-09-24 10:00:00")

    def test_tick_duas_vezes_seguidas_e_idempotente(self):
        caixa.enfileirar("pergunta", "Pagou o cartao?", chave_unica="teste_idempotencia")
        self._datetime_travado(self.AGORA_TESTE)
        with patch("assistente.caixa.enviar_push", return_value=True):
            resp1 = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
            resp2 = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp1.get_json()["pushes_enviados"], 1)
        self.assertEqual(resp2.get_json()["pushes_enviados"], 0)
        total = self.conn.execute(
            "SELECT COUNT(*) AS n FROM assistente_itens WHERE chave_unica = 'teste_idempotencia'"
        ).fetchone()["n"]
        self.assertEqual(total, 1)

    def test_tick_chama_executar_todos_de_verdade(self):
        # assistente.gatilhos.executar_todos (Etapa 0/X1) roda de verdade -
        # sem gatilho nenhum registrado (nenhum arquivo meu em
        # assistente/gatilhos/), devolve {} (relatorio vazio), nao None.
        self._datetime_travado(self.AGORA_TESTE)
        resp = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["gatilhos"], {})

    def test_tick_repassa_relatorio_de_executar_todos(self):
        with patch("rotas.p1a_caixa.executar_todos", return_value={"p2_perguntas": {"ok": True}}) as mock_exec:
            self._datetime_travado(self.AGORA_TESTE)
            resp = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["gatilhos"], {"p2_perguntas": {"ok": True}})
        mock_exec.assert_called_once()
        self.assertEqual(mock_exec.call_args.args[1], self.AGORA_TESTE)

    def test_tick_erro_inesperado_no_agregador_nao_derruba_a_rota(self):
        # executar_todos ja isola erro de CADA gatilho sozinha; isto cobre um
        # bug inesperado na propria agregadora (ex.: pkgutil falhando).
        with patch("rotas.p1a_caixa.executar_todos", side_effect=RuntimeError("bug inesperado")):
            resp = self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        self.assertIn("erro", resp.get_json()["gatilhos"])

    # ---- GET /api/assistente/saude ---------------------------------------

    def test_saude_sem_tick_nenhum(self):
        resp = self.client.get("/api/assistente/saude")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertIsNone(corpo["ultimo_tick_em"])
        self.assertTrue(corpo["atrasado"])

    def test_saude_logo_apos_tick_nao_fica_atrasado(self):
        self._datetime_travado(self.AGORA_TESTE)
        with patch("assistente.caixa.enviar_push", return_value=True):
            self.client.post("/api/tick", headers={"Authorization": "Bearer token-de-teste-123"})

        self._datetime_travado(self.AGORA_TESTE + timedelta(minutes=5))
        resp = self.client.get("/api/assistente/saude")
        corpo = resp.get_json()
        self.assertFalse(corpo["atrasado"])
        self.assertEqual(corpo["minutos_desde_ultimo_tick"], 5.0)

    def test_saude_fica_atrasado_depois_de_15_minutos(self):
        db.definir_configuracao(self.conn, caixa.CHAVE_ULTIMO_TICK, "2026-09-24 09:00:00")
        self._datetime_travado(datetime(2026, 9, 24, 9, 16, 0))
        resp = self.client.get("/api/assistente/saude")
        corpo = resp.get_json()
        self.assertTrue(corpo["atrasado"])
        self.assertEqual(corpo["minutos_desde_ultimo_tick"], 16.0)

    def test_saude_valor_corrompido_em_configuracoes_nao_quebra(self):
        db.definir_configuracao(self.conn, caixa.CHAVE_ULTIMO_TICK, "isso-nao-e-uma-data")
        resp = self.client.get("/api/assistente/saude")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["atrasado"])


if __name__ == "__main__":
    unittest.main()
