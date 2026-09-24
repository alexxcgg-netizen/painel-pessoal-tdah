"""Fase 7 / C1 - historia 3: `fechamento_noturno` (push antigo das 21h) x
briefing da noite da P3. So um dos dois sai: com a flag assistente.p3.ativo
ligada e o tick configurado, fica so o briefing da P3 (item da Caixa, push
pelo tick); sem isso, o fechamento antigo continua. Push sempre mockado."""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from assistente import briefing, caixa  # noqa: E402
from assistente.gatilhos import p3_briefing  # noqa: E402

PIN_TESTE = "123456"
TITULO_ANTIGO = "Fechando o dia"


class FechamentoXBriefingTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200
        sub = {"endpoint": "https://exemplo.com/push/c1", "keys": {"p256dh": "x", "auth": "y"}}
        self.client.post("/api/push/inscrever", json=sub)

    def _flag_p3(self, valor):
        conn = db.get_db()
        db.definir_configuracao(conn, briefing.CHAVE_ATIVO, valor)
        conn.commit()
        conn.close()

    def _titulos_do_verificar(self, env):
        with patch.dict(os.environ, env, clear=False), \
                patch("notificacoes.fechamento_noturno_devido", return_value=True), \
                patch("notificacoes.dentro_do_horario_silencioso", return_value=False), \
                patch("push_client.configurado", return_value=True), \
                patch("push_client.enviar", return_value=True) as enviar:
            if "PAINEL_TICK_TOKEN" not in env:
                os.environ.pop("PAINEL_TICK_TOKEN", None)
            self.client.post("/api/notificacoes/verificar-agora")
        return [c.args[1] for c in enviar.call_args_list]

    def test_p3_ligada_com_tick_suprime_o_fechamento_antigo(self):
        titulos = self._titulos_do_verificar({"PAINEL_TICK_TOKEN": "tick-teste"})
        self.assertNotIn(TITULO_ANTIGO, titulos)

    def test_p3_desligada_mantem_o_fechamento_antigo(self):
        self._flag_p3("0")
        titulos = self._titulos_do_verificar({"PAINEL_TICK_TOKEN": "tick-teste"})
        self.assertIn(TITULO_ANTIGO, titulos)

    def test_sem_tick_configurado_o_briefing_nao_sai_entao_o_antigo_continua(self):
        titulos = self._titulos_do_verificar({})
        self.assertIn(TITULO_ANTIGO, titulos)

    def test_erro_na_flag_mantem_o_antigo(self):
        with patch.object(briefing, "ativo", side_effect=RuntimeError("sem tabela")):
            titulos = self._titulos_do_verificar({"PAINEL_TICK_TOKEN": "tick-teste"})
        self.assertIn(TITULO_ANTIGO, titulos)

    def test_as_21h_sai_um_push_so_o_briefing_da_p3(self):
        """Ponta a ponta: verificar-agora (push antigo) + gatilho da P3 e a
        repeticao da Caixa (o que o /api/tick faz) no mesmo minuto."""
        titulos_antigos = self._titulos_do_verificar({"PAINEL_TICK_TOKEN": "tick-teste"})
        agora = datetime.combine(datetime.now().date(), datetime.strptime(
            briefing.horario_noite(db.get_db()), "%H:%M").time())
        conn = db.get_db()
        try:
            with patch("push_client.configurado", return_value=True), \
                    patch("push_client.enviar", return_value=True) as enviar, \
                    patch.object(caixa, "_aviso_permitido", return_value=True), \
                    patch.object(caixa, "_agora", return_value=agora):
                p3_briefing.executar(conn, agora)
                caixa.processar_repeticoes(conn, agora)
            titulos_tick = [c.args[1] for c in enviar.call_args_list]
        finally:
            conn.close()
        # o push antigo (verificar-agora) nao saiu; o do tick e o briefing da P3
        self.assertNotIn(TITULO_ANTIGO, titulos_antigos)
        itens = [i for i in caixa.listar(db.get_db()) if i["tipo"] == "briefing"]
        self.assertEqual(len(itens), 1)
        self.assertTrue(itens[0]["origem"].startswith("p3_briefing:noite:"))
        self.assertEqual(titulos_tick, [itens[0]["titulo"]])


if __name__ == "__main__":
    unittest.main()
