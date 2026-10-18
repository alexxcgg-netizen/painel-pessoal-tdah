"""scripts/relatorio_painel.py (2026-10-16): relatorio do painel inteiro pro Claude achar bug.
Banco temporario semeado a mao; nada do banco real. Datas ao meio-dia UTC pra cair no mesmo dia em
qualquer fuso."""
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import db  # noqa: E402
import relatorio_painel as rp  # noqa: E402

DIA = date(2030, 3, 11)
HOJE = date(2030, 3, 12)


def _t(min_seg: str) -> str:
    """'3:00' -> 13:03:00 UTC (meio da tarde, mesmo dia no Brasil)."""
    return f"2030-03-11 13:{int(min_seg.split(':')[0]):02d}:00"


class RelatorioTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name)
        antes = db.DB_PATH
        db.DB_PATH = self.pasta / "painel.db"
        self.addCleanup(setattr, db, "DB_PATH", antes)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)

    def ins(self, sql, *params):
        self.conn.execute(sql, params)
        self.conn.commit()

    def chat(self, papel, texto, quando):
        self.ins("INSERT INTO chat_mensagens (papel, texto, criado_em) VALUES (?, ?, ?)", papel, texto, quando)

    def diag(self, tipo, dados, quando="2030-03-11 15:00:00"):
        self.ins("INSERT INTO diagnostico_cliente (tipo, dados_json, criado_em) VALUES (?, ?, ?)",
                 tipo, json.dumps(dados), quando)

    def relatorio(self, log=None):
        self.conn.close()
        ro = rp.abrir_so_leitura(db.DB_PATH)
        try:
            return rp.montar(ro, log or self.pasta / "nao_existe.log", DIA, DIA, hoje=HOJE)
        finally:
            ro.close()

    def test_conversa_acha_correcao_admissao_repeticao_e_horario_solto(self):
        self.chat("assistant", "Criei a tarefa de visitar a sala 12.", _t("0:00"))
        self.chat("user", "18:30 horas", _t("1:00"))
        self.chat("assistant", "Não consegui renomear essa tarefa, o painel não deixou.", _t("2:00"))
        self.chat("user", "isso está errado, não era isso", _t("3:00"))
        self.chat("assistant", "Ajustei.", _t("4:00"))
        self.chat("user", "me lembra de beber agua depois", _t("5:00"))
        self.chat("assistant", "Anotei.", _t("6:00"))
        self.chat("user", "Me lembra de beber água depois!", _t("7:00"))
        texto, achados = self.relatorio()
        self.assertIn("A IA admitiu falha (1)", texto)
        self.assertIn("Ele corrigiu / reclamou (1)", texto)
        self.assertIn("Ele repetiu a mesma mensagem (1)", texto)
        self.assertIn("Só um horário solto depois de resposta (1)", texto)
        pesos = {a.titulo.split(" (")[0]: a.peso for a in achados}
        self.assertEqual(pesos["Conversa: a ia admitiu falha"], 3)
        self.assertEqual(pesos["Conversa: ele repetiu a mesma mensagem"], 2)
        # "O que olhar primeiro" vem antes das secoes e ordena do mais grave
        self.assertLess(texto.index("O que olhar primeiro"), texto.index("## Conversa"))
        self.assertLess(texto.index("[quebrado]"), texto.index("[suspeito]"))

    def test_numero_longo_na_conversa_sai_oculto(self):
        self.chat("assistant", "ok", _t("0:00"))
        self.chat("user", "isso está errado, a conta é 12345678901234", _t("1:00"))
        texto, _ = self.relatorio()
        self.assertNotIn("12345678901234", texto)
        self.assertIn("[número oculto]", texto)

    def test_aparelho_erro_js_barra_fora_da_tela_e_medida_ignorada(self):
        for _ in range(3):
            self.diag("erro_js", {"msg": "x is not a function", "arq": "tarefas.js", "linha": 12, "aba": "hoje"})
        self.diag("tela", {"motivo": "desvio", "innerH": 956, "barraFundo": 1912, "bruto": 1912, "aplicado": 1912})
        self.diag("tela", {"motivo": "abriu", "innerH": 956, "barraFundo": 956, "bruto": 0, "aplicado": 0})
        self.diag("tela", {"motivo": "ignorada", "innerH": 956, "barraFundo": 956})
        # barra desceu junto com a janela visual (vvTopo+vvH = 1004): NAO e fora da tela
        self.diag("tela", {"motivo": "desvio", "innerH": 956, "vvTopo": 48, "vvH": 956, "barraFundo": 1004})
        self.diag("mic", {"evento": "detector_surdo"})
        texto, achados = self.relatorio()
        self.assertIn("3x `x is not a function` em `tarefas.js:12`", texto)
        self.assertIn("Barra de abas fora da tela (1 medidas)", texto)
        self.assertIn("descartadas pela proteção: 1", texto)
        titulos = " | ".join(a.titulo for a in achados)
        self.assertIn("1 tipo(s) de erro de JavaScript", titulos)
        self.assertIn("barra de abas saiu da tela (1x)", titulos)
        self.assertIn("microfone", titulos)

    def test_servidor_agrupa_por_tipo_e_ignora_fora_do_periodo(self):
        log = self.pasta / "erros_servidor.log"
        log.write_text(
            "2030-03-11 09:00:01,100 ERROR app: chat falhou no turno 41\n"
            "Traceback (most recent call last):\n  File x\nValueError: y\n"
            "2030-03-11 10:00:01,100 ERROR app: chat falhou no turno 77\n"
            "2030-03-11 11:00:00,000 WARNING rotas.tasks: lugar nao achado\n"
            "2030-03-01 09:00:00,000 ERROR app: antigo demais\n", encoding="utf-8")
        texto, achados = self.relatorio(log)
        self.assertIn("2x **ERROR** `app`: chat falhou no turno N", texto)
        self.assertNotIn("antigo demais", texto)
        self.assertIn("1x **WARNING** `rotas.tasks`", texto)
        self.assertEqual(max(a.peso for a in achados if a.titulo.startswith("Servidor")), 3)

    def test_sem_log_diz_que_ainda_nao_existe(self):
        texto, _ = self.relatorio()
        self.assertIn("ainda não há `nao_existe.log`", texto)

    def test_dados_atrasadas_duplicadas_desfeitas_e_avisos_ignorados(self):
        self.ins("INSERT INTO tasks (title, due_date) VALUES ('Pagar a conta de luz', '2030-02-01')")
        self.ins("INSERT INTO tasks (title, due_date) VALUES ('Comprar leite', '2030-03-12')")
        self.ins("INSERT INTO tasks (title, due_date) VALUES ('comprar  LEITE!', '2030-03-12')")
        self.ins("INSERT INTO acoes_desfazer (token, itens_json, criado_em, desfeito_em) VALUES ('t1', '[]', ?, ?)",
                 "2030-03-11 14:00:00", "2030-03-11 15:00:00")
        for i in range(4):
            self.ins("INSERT INTO avisos_insistentes (tipo, referencia_id, data, titulo, corpo, tag, enviado_em, tentativas) "
                     "VALUES ('agua', ?, '2030-03-11', 't', 'c', ?, '2030-03-11 12:00:00', 3)", i, f"tag{i}")
        texto, achados = self.relatorio()
        self.assertIn("Tarefas atrasadas (1)", texto)
        self.assertIn("Tarefas duplicadas (1)", texto)
        self.assertIn("Ações que ele desfez: 1", texto)
        self.assertIn("4 enviados, 4 nunca vistos", texto)
        titulos = " | ".join(a.titulo for a in achados)
        self.assertIn("1 tarefa(s) atrasada(s), 1 há 14+ dias", titulos)
        self.assertIn("1 tarefa(s) duplicada(s)", titulos)
        self.assertIn("4/4 avisos insistentes nunca vistos", titulos)

    def test_tabela_faltando_nao_derruba_o_resto(self):
        self.conn.execute("DROP TABLE diagnostico_cliente")
        self.conn.execute("DROP TABLE avisos_insistentes")
        self.conn.commit()
        texto, _ = self.relatorio()
        self.assertIn("sem diagnóstico do aparelho", texto)
        self.assertIn("## Dados", texto)

    def test_main_grava_arquivo_e_o_banco_e_aberto_so_leitura(self):
        self.conn.close()
        saida = self.pasta / "r.md"
        rc = rp.main(["--banco", str(db.DB_PATH), "--log", str(self.pasta / "x.log"), "--saida", str(saida),
                      "--desde", "2030-03-10", "--ate", "2030-03-12"])
        self.assertEqual(rc, 0)
        self.assertTrue(saida.read_text(encoding="utf-8").startswith("# Relatório do painel"))
        ro = rp.abrir_so_leitura(db.DB_PATH)
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("INSERT INTO tasks (title) VALUES ('nao pode')")
        ro.close()
        self.assertEqual(rp.main(["--banco", str(self.pasta / "nao_tem.db")]), 1)
        self.assertEqual(rp.main(["--desde", "2030-03-12", "--ate", "2030-03-10", "--banco", str(db.DB_PATH)]), 2)


if __name__ == "__main__":
    unittest.main()
