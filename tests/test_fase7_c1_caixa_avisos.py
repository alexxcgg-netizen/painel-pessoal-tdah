"""Fase 7 / C1 - historia 6: tipos da Caixa x catalogo de avisos da P8.

- toda origem que as faixas P mandam pra Caixa tem uma chave em
  assistente/avisos.py TIPOS (assistente.avisos.tipo_de_origem);
- tipo desligado na P8: o gatilho nao cria o item (esta_ligado) nem manda push;
- push proativo usa aviso_permitido completo (liga/desliga + silencio);
  a Caixa usa so esta_ligado (silencio nao impede o item de nascer);
- canal "caixa" na P8: item sem push.
Push sempre mockado; banco temporario."""
import os
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402
from assistente import avisos, caixa  # noqa: E402
from assistente.gatilhos import p3_briefing  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

# Uma origem de exemplo por formato que cada gatilho gera hoje.
ORIGENS_DOS_GATILHOS = {
    "p2_perguntas:conta:12:2026-09-30": "pergunta_conta",
    "p2_perguntas:evento:abc:2026-09-24": "reuniao",
    "p2_perguntas:tarefa:7:2026-09-20": "tarefa_vencida",
    "p2_perguntas:lembrete:3:2026-09-25": "lembrete",
    "p2_perguntas:espera:9:2026-09-10": "espera",
    "p3_briefing:manha:2026-09-24": "briefing_manha",
    "p3_briefing:noite:2026-09-24": "briefing_noite",
    "p3_briefing_noite:2026-09-24": "briefing_noite",  # formato antigo
    "p4_regras:5": "regra",
    "p5_replanejar": "replanejar",
    "p7_sinais": "sinal",
    "p9_memoria:semana-39:abc": "memoria_viva",
}


class CatalogoCobreAsOrigensTestCase(unittest.TestCase):
    def test_toda_origem_de_gatilho_tem_tipo_no_catalogo(self):
        for origem, esperado in ORIGENS_DOS_GATILHOS.items():
            with self.subTest(origem=origem):
                tipo = avisos.tipo_de_origem(origem)
                self.assertEqual(tipo, esperado)
                self.assertIn(tipo, avisos.TIPOS)

    def test_todo_valor_do_mapa_existe_em_tipos(self):
        for chave, tipo in avisos.TIPO_POR_ORIGEM.items():
            self.assertIn(tipo, avisos.TIPOS, chave)

    def test_todo_arquivo_que_enfileira_tem_prefixo_mapeado(self):
        """Varre o codigo: todo gatilho/modulo que chama enfileirar(...)
        precisa ter o prefixo da sua origem no mapa (pega faixa nova que
        esquecer de cadastrar o tipo)."""
        prefixos_mapeados = {p for p, _ in avisos.TIPO_POR_ORIGEM}
        arquivos = list((RAIZ / "assistente" / "gatilhos").glob("p*.py")) + [RAIZ / "assistente" / "sinais.py"]
        for arq in arquivos:
            fonte = arq.read_text(encoding="utf-8")
            if "enfileirar(" not in fonte:
                continue
            with self.subTest(arquivo=arq.name):
                achados = set(re.findall(r'origem=f?"([a-z0-9_]+)', fonte))
                achados |= set(re.findall(r'(?:PREFIXO|CAIXA_ORIGEM) = "([a-z0-9_]+)"', fonte))
                achados |= set(re.findall(r'origem = f"([a-z0-9_]+):', fonte))
                self.assertTrue(achados, f"{arq.name}: nao achei a origem")
                for prefixo in achados:
                    self.assertIn(prefixo, prefixos_mapeados)

    def test_origem_estranha_nao_quebra(self):
        for origem in (None, "", "   ", ":::", "desconhecido:x", 123, "p2_perguntas:nova_coisa:1", "x" * 5000):
            with self.subTest(origem=origem):
                self.assertIsNone(avisos.tipo_de_origem(origem))


class _BaseBanco(unittest.TestCase):
    AGORA = datetime(2026, 9, 24, 10, 0, 0)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        db.init_db()
        self.conn = db.get_db()
        caixa._garantir_tabela(self.conn)
        self._agora_original = caixa._agora
        caixa._agora = lambda: self.AGORA

    def tearDown(self):
        caixa._agora = self._agora_original
        self.conn.close()
        db.DB_PATH = self._db_original
        self._tmp.cleanup()

    def _desligar(self, tipo, **extra):
        avisos.definir_tipo(tipo, ligado=False, **extra)

    def _itens(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM assistente_itens").fetchall()]


class TipoDesligadoNaoCriaNemAvisaTestCase(_BaseBanco):
    def test_desligado_nao_cria_item(self):
        self._desligar("pergunta_conta")
        item_id = caixa.enfileirar("pergunta", "Pagou o cartao?", origem="p2_perguntas:conta:1:2026-09-30",
                                   chave_unica="p2_perguntas:conta:1:2026-09-30")
        self.assertEqual(item_id, "")
        self.assertEqual(self._itens(), [])

    def test_so_o_tipo_desligado_some(self):
        self._desligar("pergunta_conta")
        self.assertEqual(caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x"), "")
        self.assertTrue(caixa.enfileirar("pergunta", "E a reuniao?", origem="p2_perguntas:evento:2:x"))
        self.assertTrue(caixa.enfileirar("aviso", "Sem origem", origem=""))
        self.assertEqual(len(self._itens()), 2)

    def test_gatilho_p3_com_briefing_noite_desligado_nao_cria(self):
        self._desligar("briefing_noite")
        noite = datetime.combine(self.AGORA.date(), datetime.strptime(
            p3_briefing.briefing.horario_noite(self.conn), "%H:%M").time())
        with patch("push_client.configurado", return_value=True), patch("push_client.enviar") as enviar:
            p3_briefing.executar(self.conn, noite)
            caixa.processar_repeticoes(self.conn, noite)
        self.assertEqual(self._itens(), [])
        enviar.assert_not_called()

    def test_silencio_nao_impede_o_item_de_nascer(self):
        avisos.definir_silencio_global("00:00", "23:59")
        self.assertTrue(caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x"))

    def test_erro_na_config_da_p8_nao_some_com_item(self):
        with patch("assistente.avisos.esta_ligado", side_effect=RuntimeError("config quebrada")):
            self.assertTrue(caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x"))


class PushUsaAvisoPermitidoFinoTestCase(_BaseBanco):
    def _push(self, agora=None):
        with patch.object(caixa, "enviar_push", return_value=True) as enviar:
            resultado = caixa.processar_repeticoes(self.conn, agora or self.AGORA)
        return enviar, resultado

    def test_ligado_fora_do_silencio_manda(self):
        caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x")
        enviar, resultado = self._push()
        enviar.assert_called_once()
        self.assertEqual(resultado["pushes_enviados"], 1)

    def test_desligado_depois_de_criado_nao_manda_push(self):
        caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x")
        self._desligar("pergunta_conta")
        enviar, _ = self._push()
        enviar.assert_not_called()

    def test_silencio_proprio_do_tipo_segura_o_push(self):
        caixa.enfileirar("pergunta", "Reuniao?", origem="p2_perguntas:evento:1:x")
        avisos.definir_tipo("reuniao", silencio_inicio="09:00", silencio_fim="11:00")
        enviar, _ = self._push()
        enviar.assert_not_called()
        # outro tipo, mesmo horario: sai
        caixa.enfileirar("pergunta", "Pagou?", origem="p2_perguntas:conta:1:x")
        enviar, _ = self._push()
        enviar.assert_called_once()

    def test_canal_so_caixa_nao_manda_push(self):
        caixa.enfileirar("sugestao", "Replanejar?", origem="p5_replanejar")
        avisos.definir_tipo("replanejar", canal="caixa")
        enviar, _ = self._push()
        enviar.assert_not_called()
        self.assertEqual(len(caixa.listar(self.conn)), 1)  # continua na Caixa

    def test_item_sem_origem_conhecida_segue_a_categoria(self):
        caixa.enfileirar("aviso", "Algo manual")
        enviar, _ = self._push()
        enviar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
