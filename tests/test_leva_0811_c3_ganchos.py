"""Leva 08/11, frente C rodada 3: ganchos do agente A em app.py/rotas (trajeto de agora nos avisos de
tarefa, titulo fixo pra saida que passou, parada sem endereco nao vai pro Google, manha repete ao abrir o
app), rollback da ferramenta do chat que estoura no meio de uma escrita e textos com "tu"/plural.
Banco temporario, IA e Maps dublados, nomes inventados."""
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from rotas import n3a_widget  # noqa: E402

PIN = "135790"


def _uso():
    return {"model": "claude-haiku-4-5-20251001", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0}


class _Base(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        sem_maps = patch("maps_client.configurado", return_value=False)
        sem_maps.start()
        self.addCleanup(sem_maps.stop)

    def sql(self, query, params=()):
        conn = db.get_db()
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()


# ------------------------------------------------------------------ 1a/1b: trajeto de agora + titulo


class AvisosDeTarefaTestCase(_Base):
    def test_passou_da_hora_saida_tem_titulo_fixo_e_trajeto(self):
        hoje = date.today().isoformat()
        conn = db.get_db()
        try:
            date_id = conn.execute("INSERT INTO tasks (title, due_date, hora, estilo) VALUES "
                                   "('Jantar de teste', ?, '20:00', 'date')", (hoje,)).lastrowid
            comum_id = conn.execute("INSERT INTO tasks (title, due_date, hora) VALUES "
                                    "('Ligar pro banco de teste', ?, '14:00')", (hoje,)).lastrowid
            conn.commit()
            vistos = {}

            def passou(conn_, agora_, caminho_min=None):
                vistos["caminho_min"] = caminho_min
                return [(date_id, "era 20:00"), (comum_id, "era 14:00")]

            with patch("notificacoes.tarefas_horario_passou", side_effect=passou), \
                    patch("onde_vou.caminho_min_tarefa", return_value=17) as caminho:
                avisos = app._avisos_proatividade_e8(conn, datetime.now())
                self.assertEqual(vistos["caminho_min"]({"id": date_id}), 17)
            titulos = {ref: t for tipo, ref, t, _c in avisos if tipo == "tarefa_horario_passou"}
            self.assertEqual(titulos[date_id], app.TITULO_SAIDA_PASSOU)
            self.assertNotIn("tempo", titulos[date_id].lower())  # nada de "ainda da tempo" na saida
            self.assertEqual(titulos[comum_id], "Passou da hora")  # generico: o catalogo varia
            caminho.assert_called_once()
            # titulo da saida fica fora do catalogo: a variacao nao troca
            t, _ = app._texto_variado(conn, "tarefa_horario_passou", date_id, app.TITULO_SAIDA_PASSOU, "x")
            self.assertEqual(t, app.TITULO_SAIDA_PASSOU)
        finally:
            conn.close()

    def test_verificar_passa_o_trajeto_pro_aviso_da_hora(self):
        vistos = {}

        def chegando(conn_, *a, **k):
            vistos.update(k)
            return []

        self.client.post("/api/push/inscrever",
                         json={"endpoint": "https://exemplo.com/push/c3", "keys": {"p256dh": "x", "auth": "y"}})
        with patch("notificacoes.tarefas_com_horario_chegando", side_effect=chegando), \
                patch("push_client.configurado", return_value=True), \
                patch("push_client.enviar", return_value=True):
            self.client.post("/api/notificacoes/verificar-agora")
        self.assertTrue(callable(vistos.get("caminho_min")))


# ------------------------------------------------------------------ 1c: parada sem endereco


class ParadaSemEnderecoTestCase(_Base):
    def test_trajetos_parada_sem_endereco_nao_chama_o_google(self):
        conn = db.get_db()
        try:
            with patch("vida_assistente.resolver_parada", return_value=""), \
                    patch.object(app, "_trajeto_min_aviso") as trajeto:
                self.assertEqual(app._trajetos_parada_aviso(conn, "casa da fulana", "Shopping de teste"), (None, None))
            trajeto.assert_not_called()
        finally:
            conn.close()

    def test_saida_com_parada_sem_endereco_usa_a_folga(self):
        conn = db.get_db()
        try:
            with patch.dict(os.environ, {"ENDERECO_CASA": "Rua dos Testes, 1"}), \
                    patch("vida_assistente.resolver_parada", return_value=""), \
                    patch("maps_client.configurado", return_value=True), \
                    patch("maps_client.tempo_de_viagem") as maps:
                saida, _info = app._saida_com_parada(conn, "2099-01-01", "20:00", "casa da fulana", "Bar de teste")
            maps.assert_not_called()
            self.assertIsNone(saida["trajeto_min"])
        finally:
            conn.close()


# ------------------------------------------------------------------ 1d: manha repete ao abrir o app


class ManhaAoAcordarTestCase(_Base):
    def test_push_visto_chama_depois_do_ao_ver_e_nao_derruba(self):
        ordem = []
        with patch("de_onde_parei.ao_ver", side_effect=lambda *a, **k: ordem.append("ao_ver") or False), \
                patch("conversa_proativa.repetir_manha_ao_acordar",
                      side_effect=lambda conn, agora: ordem.append(("manha", agora.tzinfo)) or []):
            r = self.client.post("/api/push/visto")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ordem, ["ao_ver", ("manha", None)])  # depois do ao_ver, hora local sem fuso
        with patch("conversa_proativa.repetir_manha_ao_acordar", side_effect=RuntimeError("quebrou")):
            self.assertEqual(self.client.post("/api/push/visto").status_code, 200)


# ------------------------------------------------------------------ 2: rollback da ferramenta


class RollbackDaFerramentaTestCase(_Base):
    def test_escrita_pela_metade_nao_fica_no_banco(self):
        self.sql("INSERT INTO tasks (title, hora) VALUES ('Tarefa travada de teste', '15:00')")
        erros = []

        def fake(mensagens, contexto, memorias, executores):
            # mesmo tratamento do loop do chat: a ferramenta que estoura vira erro e a proxima roda
            for tool, entrada in [("travar_tarefa", {"titulo": "Tarefa travada de teste"}),
                                  ("registrar_lembrete", {"titulo": "Lembrete de teste", "data": "2099-01-02"})]:
                try:
                    executores[tool](entrada)
                except RuntimeError as exc:
                    erros.append(str(exc))
            return "Feito.", ["registrar_lembrete"], _uso()

        with patch("dia_ruim.travar", side_effect=RuntimeError("estourou no meio")), \
                patch("claude_client.chat", side_effect=fake):
            res = self.client.post("/api/chat", json={"mensagem": "trava e anota"})
        self.assertEqual(res.status_code, 200, res.get_json())
        self.assertEqual(erros, ["estourou no meio"])  # a excecao segue pro loop
        # o UPDATE do due_date (antes do travar estourar) nao foi junto com o commit do lembrete
        self.assertEqual(self.sql("SELECT due_date FROM tasks")[0][0], None)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lembretes")[0][0], 1)


# ------------------------------------------------------------------ 3: textos


class TextosTestCase(unittest.TestCase):
    def test_plural_e_acento(self):
        self.assertEqual(app._qtd(1, "dia", "dias"), "1 dia")
        self.assertEqual(app._qtd(9, "dia", "dias"), "9 dias")
        self.assertEqual(app._prazo_em_dias(-2), "já passou do prazo")
        self.assertEqual(app._prazo_em_dias(1), "vence amanhã")
        self.assertEqual(app._prazo_em_dias(4), "vence em 4 dias")
        texto = app._texto_revisao("fevereiro", {"tarefas_feitas": 1, "treinos": 2, "rotina_manha_dias": 1,
                                                 "sono_medio": None, "humor_medio": None, "gasto_total": 0})
        self.assertEqual(texto, "Fevereiro fechou: 1 tarefa feita, 2 treinos, rotina da manhã em 1 dia.")

    def test_widget(self):
        self.assertEqual(n3a_widget._linha_conta({"nome": "Luz", "em_dias": -1}), "Conta: Luz vencida há 1 dia")
        self.assertEqual(n3a_widget._linha_conta({"nome": "Luz", "em_dias": 1}), "Conta: Luz vence amanhã")
        self.assertEqual(n3a_widget._linha_habitos({"feitos": 1, "total": 2}), "Hábitos: 1/2")


if __name__ == "__main__":
    unittest.main()
