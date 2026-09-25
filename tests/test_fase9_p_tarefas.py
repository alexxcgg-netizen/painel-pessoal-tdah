# tests/test_fase9_p_tarefas.py - Fase 9 (faixa P-tarefas): seletor segmentado
# Pendentes/Hoje/Concluidas na aba Tarefas + `GET /api/tasks?estado=concluidas`
# (opt-in, sem parametro o comportamento continua identico ao de antes). Banco
# temporario, sem IA/Pluggy real - mesmo padrao de tests/test_fase9_api.py e
# tests/test_fase9_c_abas.py.
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
os.environ.setdefault("OPENAI_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402  (precisa vir depois do patch de db.DB_PATH)

PIN_TESTE = "123456"


class _BaseTestCase(unittest.TestCase):
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

    def _criar_tarefa(self, titulo, due_date=None):
        res = self.client.post("/api/tasks", json={"titulo": titulo, "due_date": due_date})
        assert res.status_code == 201, res.get_json()
        return res.get_json()["id"]

    def _completar(self, task_id):
        res = self.client.post(f"/api/tasks/{task_id}/complete")
        assert res.status_code == 200, res.get_json()


class ApiTasksSemParametroTestCase(_BaseTestCase):
    """Sem `estado` (ou com `estado=pendentes`) o comportamento de sempre
    continua igual - so pendentes, mais recente primeiro."""

    def test_lista_vazia_no_comeco(self):
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_so_pendentes_aparecem_sem_parametro(self):
        id_a = self._criar_tarefa("Lavar o carro")
        id_b = self._criar_tarefa("Pagar a fatura")
        self._completar(id_a)

        tasks = self.client.get("/api/tasks").get_json()
        ids = [t["id"] for t in tasks]
        self.assertIn(id_b, ids)
        self.assertNotIn(id_a, ids)

    def test_estado_pendentes_explicito_e_identico_a_sem_parametro(self):
        self._criar_tarefa("Regar as plantas")
        sem_param = self.client.get("/api/tasks").get_json()
        com_param = self.client.get("/api/tasks?estado=pendentes").get_json()
        self.assertEqual(sem_param, com_param)

    def test_estado_invalido_400(self):
        res = self.client.get("/api/tasks?estado=nao-existe")
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())


class ApiTasksConcluidasTestCase(_BaseTestCase):
    def test_concluidas_vem_com_completed_at_mais_recente_primeiro(self):
        id_a = self._criar_tarefa("Tarefa A")
        id_b = self._criar_tarefa("Tarefa B")
        self._completar(id_a)
        self._completar(id_b)

        concluidas = self.client.get("/api/tasks?estado=concluidas").get_json()
        ids = [t["id"] for t in concluidas]
        # B foi concluida depois de A -> aparece primeiro (mais recente primeiro).
        self.assertEqual(ids[:2], [id_b, id_a])
        for t in concluidas:
            self.assertIsNotNone(t["completed_at"])

    def test_pendentes_nao_aparecem_em_concluidas(self):
        id_pendente = self._criar_tarefa("Ainda pendente")
        id_feita = self._criar_tarefa("Ja feita")
        self._completar(id_feita)

        concluidas = self.client.get("/api/tasks?estado=concluidas").get_json()
        ids = [t["id"] for t in concluidas]
        self.assertIn(id_feita, ids)
        self.assertNotIn(id_pendente, ids)

    def test_limite_respeitado(self):
        ids = [self._criar_tarefa(f"Tarefa {i}") for i in range(5)]
        for i in ids:
            self._completar(i)

        concluidas = self.client.get("/api/tasks?estado=concluidas&limite=2").get_json()
        self.assertEqual(len(concluidas), 2)

    def test_limite_default_e_30(self):
        ids = [self._criar_tarefa(f"Tarefa {i}") for i in range(35)]
        for i in ids:
            self._completar(i)

        concluidas = self.client.get("/api/tasks?estado=concluidas").get_json()
        self.assertEqual(len(concluidas), 30)

    def test_limite_invalido_400(self):
        res = self.client.get("/api/tasks?estado=concluidas&limite=abc")
        self.assertEqual(res.status_code, 400)

    def test_limite_e_limitado_a_100(self):
        res = self.client.get("/api/tasks?estado=concluidas&limite=99999")
        self.assertEqual(res.status_code, 200)  # so confere que nao quebra/estoura


class ReabrirTarefaTestCase(_BaseTestCase):
    """A API de desfazer (reabrir) ja existia (Fase 6, US-E3) - o seletor da
    aba so passa a usa-la pra "desfazer" uma concluida."""

    def test_reabrir_tira_da_lista_de_concluidas_e_devolve_pra_pendentes(self):
        task_id = self._criar_tarefa("Vai e volta")
        self._completar(task_id)
        self.assertIn(task_id, [t["id"] for t in self.client.get("/api/tasks?estado=concluidas").get_json()])

        res = self.client.post(f"/api/tasks/{task_id}/reabrir")
        self.assertEqual(res.status_code, 200)

        concluidas = self.client.get("/api/tasks?estado=concluidas").get_json()
        pendentes = self.client.get("/api/tasks").get_json()
        self.assertNotIn(task_id, [t["id"] for t in concluidas])
        self.assertIn(task_id, [t["id"] for t in pendentes])


class TarefasHtmlTestCase(_BaseTestCase):
    """A aba renderiza o seletor segmentado e o container do grafico -
    contrato pro JS (static/js/secoes/tarefas/tarefas.js)."""

    def test_seletor_e_grafico_na_pagina(self):
        corpo = self.client.get("/").get_data(as_text=True)
        for elemento_id in (
            "tarefas-seletor",
            "tf-frase-resumo",
            "tf-grafico-semana",
            "tarefas-vazio-texto",
            "tf-bloco-energia",
        ):
            self.assertIn(f'id="{elemento_id}"', corpo, msg=f"elemento #{elemento_id} sumiu da pagina")
        # os 3 botoes do seletor, com os data-estado esperados pelo JS.
        for estado in ("pendentes", "hoje", "concluidas"):
            self.assertIn(f'data-estado="{estado}"', corpo)

    def test_ids_antigos_da_aba_continuam_no_lugar(self):
        """Nao pode sumir nada que outras partes do app usam por id
        (cards.js, testes existentes) - so garante que a reforma visual nao
        quebrou contrato de outra faixa."""
        corpo = self.client.get("/").get_data(as_text=True)
        for elemento_id in (
            "tarefa-abrir-btn",
            "nova-tarefa-form",
            "nova-tarefa-titulo",
            "nova-tarefa-prazo",
            "lista-tarefas",
            "tarefas-vazio",
            "energia-botoes",
            "lista-sugestao-energia",
            "sugestao-energia-vazio",
        ):
            self.assertIn(f'id="{elemento_id}"', corpo, msg=f"elemento #{elemento_id} sumiu da pagina")


if __name__ == "__main__":
    unittest.main()
