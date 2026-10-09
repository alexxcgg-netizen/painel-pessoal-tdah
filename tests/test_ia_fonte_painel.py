"""Fonte unica do chat: "a IA responde de acordo com o painel, e nao fora dele".

Cobre (sem IA real, banco temporario):
- a regra de fonte unica nos dois prompts (e continuam formataveis);
- as 3 tools novas (consultar_tarefas/gastos/agenda) no array de tools e no dict
  de executores;
- comportamento de cada consulta + mini-fuzz (nunca excecao)."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import caldav_client  # noqa: E402
import chat_consultas  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402
from rotas import f9_financas  # noqa: E402

PIN_TESTE = "123456"
HOJE = date.today()


def _iso(dias: int) -> str:
    return (HOJE + timedelta(days=dias)).isoformat()


class PromptsTestCase(unittest.TestCase):
    def test_regra_nos_dois_prompts(self):
        for prompt in (chat_mod.CHAT_SYSTEM_PROMPT, chat_mod.CHAT_SIMPLES_PROMPT):
            self.assertIn("REGRA DE FONTE UNICA", prompt)
            self.assertIn("UNICA", prompt)
            self.assertIn("Contexto de agora", prompt)
            self.assertIn("NUNCA estime", prompt)
            self.assertIn("invente", prompt)
            self.assertIn("memorias", prompt)
            for tema in ("tarefas", "gastos", "agenda", "voos", "habitos", "notas", "pessoas"):
                self.assertIn(tema, prompt)

    def test_regra_vem_no_comeco(self):
        # logo no comeco: antes das regras de registro de tarefa/gasto
        self.assertLess(chat_mod.CHAT_SYSTEM_PROMPT.index("REGRA DE FONTE UNICA"), 1200)
        self.assertLess(chat_mod.CHAT_SIMPLES_PROMPT.index("REGRA DE FONTE UNICA"), 900)

    def test_prompt_completo_manda_usar_consultar(self):
        self.assertIn("`consultar_*`", chat_mod.CHAT_SYSTEM_PROMPT)
        self.assertIn("Isso nao ta no painel", chat_mod.CHAT_SYSTEM_PROMPT)

    def test_simples_reforca_marcador_para_periodo_nao_coberto(self):
        p = chat_mod.CHAT_SIMPLES_PROMPT
        self.assertIn("periodo passado ou futuro", p)
        self.assertGreaterEqual(p.count("{marcador}"), 2)

    def test_formatam_sem_erro_e_sao_estaveis_entre_chamadas(self):
        hoje = date(2026, 9, 29)
        a = chat_mod.montar_sistema_chat(["gosta de cafe"], hoje=hoje)
        b = chat_mod.montar_sistema_chat(["gosta de cafe"], hoje=hoje)
        self.assertEqual(a, b)
        self.assertIn("REGRA DE FONTE UNICA", a)
        self.assertNotIn("{", a.replace("{}", ""))  # nenhum placeholder sobrando
        simples = chat_mod.CHAT_SIMPLES_PROMPT.format(
            hoje=hoje.isoformat(), marcador=chat_mod.MARCADOR_PRECISA_FERRAMENTA, memorias="- x"
        )
        self.assertIn(chat_mod.MARCADOR_PRECISA_FERRAMENTA, simples)
        self.assertNotIn("{marcador}", simples)


class ToolsTestCase(unittest.TestCase):
    NOVAS = ("consultar_tarefas", "consultar_gastos", "consultar_agenda", "consultar_voos")

    def test_tools_no_array_com_schema_valido(self):
        por_nome = {t["name"]: t for t in chat_mod.CHAT_TOOLS}
        nomes = [t["name"] for t in chat_mod.CHAT_TOOLS]
        self.assertEqual(len(nomes), len(set(nomes)), "nome de tool duplicado")
        for nome in self.NOVAS:
            self.assertIn(nome, por_nome)
            t = por_nome[nome]
            self.assertTrue(t["description"].strip())
            self.assertIn("SEMPRE", t["description"])
            self.assertEqual(t["input_schema"]["type"], "object")
            self.assertIsInstance(t["input_schema"]["properties"], dict)
            self.assertNotIn("required", t["input_schema"])
            for prop in t["input_schema"]["properties"].values():
                self.assertIn(prop["type"], ("string", "integer"))
        st = por_nome["consultar_tarefas"]["input_schema"]["properties"]["status"]
        self.assertEqual(st["enum"], ["pendentes", "concluidas", "todas"])


class _Base(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        self.exec = self._capturar_executores()

    def tearDown(self):
        self.conn.close()

    def _capturar_executores(self) -> dict:
        capturado = {}

        def fake_chat(mensagens, contexto, memorias, executores):
            capturado.update(executores)
            return "ok", [], {"model": "claude-sonnet-4-5", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        # chama o pipeline direto com a conexao do teste (a rota HTTP fecha a
        # conexao no fim e os executores ficariam com uma conexao morta)
        with patch("claude_client.chat", side_effect=fake_chat), patch(
            "app._plano_local_chat", return_value=None
        ):
            resposta, _acoes, erro = app._processar_mensagem_chat(self.conn, "texto qualquer sem atalho local")
        self.assertIsNone(erro)
        self.assertTrue(capturado, "claude_client.chat nao foi chamado")
        return capturado

    def tarefa(self, titulo, due=None, hora=None, concluida=None, recorrencia=None):
        cur = self.conn.execute(
            "INSERT INTO tasks (title, due_date, hora, completed_at, recorrencia) VALUES (?, ?, ?, ?, ?)",
            (titulo, due, hora, concluida, recorrencia),
        )
        self.conn.commit()
        return cur.lastrowid


class ExecutoresRegistradosTestCase(_Base):
    def test_tres_executores_registrados(self):
        for nome in ToolsTestCase.NOVAS:
            self.assertIn(nome, self.exec)
        nomes_tools = {t["name"] for t in chat_mod.CHAT_TOOLS}
        for nome in ToolsTestCase.NOVAS:
            self.assertIn(nome, nomes_tools)

    def test_resultado_sem_chave_interna(self):
        for nome in ToolsTestCase.NOVAS:
            r = self.exec[nome]({})
            self.assertFalse([k for k in r if k.startswith("_")])


class TarefasTestCase(_Base):
    def test_pendentes_padrao_hoje_e_atrasadas_separadas(self):
        self.tarefa("de hoje", _iso(0), "10:00")
        self.tarefa("de amanha", _iso(1))
        self.tarefa("atrasada", _iso(-3))
        self.tarefa("feita hoje", _iso(0), concluida=f"{_iso(0)} 09:00:00")
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual(r["status"], "pendentes")
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["de hoje"])
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["tarefas"][0]["hora"], "10:00")
        self.assertEqual([t["titulo"] for t in r["atrasadas"]], ["atrasada"])
        self.assertEqual(r["atrasadas_total"], 1)

    def test_atrasadas_so_quando_periodo_e_hoje(self):
        self.tarefa("atrasada", _iso(-3))
        self.tarefa("amanha", _iso(1))
        r = self.exec["consultar_tarefas"]({"de": _iso(1), "ate": _iso(1)})
        self.assertNotIn("atrasadas", r)
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["amanha"])
        r = self.exec["consultar_tarefas"]({"de": _iso(0), "ate": _iso(7)})
        self.assertNotIn("atrasadas", r)
        r = self.exec["consultar_tarefas"]({"de": _iso(0), "ate": _iso(0), "status": "concluidas"})
        self.assertNotIn("atrasadas", r)

    def test_periodo_respeita_de_ate(self):
        for i in range(-2, 6):
            self.tarefa(f"t{i}", _iso(i))
        r = self.exec["consultar_tarefas"]({"de": _iso(1), "ate": _iso(3)})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["t1", "t2", "t3"])
        self.assertEqual(r["periodo"], {"de": _iso(1), "ate": _iso(3)})

    def test_concluidas_e_todas(self):
        self.tarefa("aberta", _iso(0))
        self.tarefa("feita", _iso(0), concluida=f"{_iso(0)} 09:30:00")
        r = self.exec["consultar_tarefas"]({"status": "concluidas"})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["feita"])
        self.assertEqual(r["tarefas"][0]["concluida_em"], f"{_iso(0)} 09:30")
        r = self.exec["consultar_tarefas"]({"status": "todas"})
        self.assertEqual(sorted(t["titulo"] for t in r["tarefas"]), ["aberta", "feita"])
        self.assertEqual(r["total"], 2)
        r = self.exec["consultar_tarefas"]({"status": "Concluídas"})  # sem acento/caixa
        self.assertEqual(r["status"], "concluidas")

    def test_concluida_por_data_de_conclusao(self):
        self.tarefa("sem prazo, feita ontem", None, concluida=f"{_iso(-1)} 18:00:00")
        r = self.exec["consultar_tarefas"]({"de": _iso(-1), "ate": _iso(-1), "status": "concluidas"})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["sem prazo, feita ontem"])

    def test_modelo_de_recorrencia_ignorado(self):
        self.tarefa("modelo", None, recorrencia="diaria")
        self.tarefa("modelo concluido", None, concluida="2026-01-01 10:00:00", recorrencia="diaria")
        self.tarefa("normal", _iso(0))
        # pendentes: so a instancia de hoje (materializada) - o modelo (due_date NULL) nunca aparece
        r = self.exec["consultar_tarefas"]({"status": "pendentes"})
        titulos = [t["titulo"] for t in r["tarefas"]]
        self.assertEqual(titulos.count("modelo"), 1)
        self.assertTrue(all(t["data"] == _iso(0) for t in r["tarefas"]))
        # concluidas: o modelo concluido (sem due_date, completed_at antigo) nunca aparece
        r = self.exec["consultar_tarefas"]({"de": "2025-12-31", "ate": "2026-01-02", "status": "todas"})
        self.assertEqual(r["tarefas"], [])
        self.assertEqual(r["total"], 0)

    def test_materializa_recorrente_quando_periodo_inclui_hoje(self):
        self.conn.execute(
            "INSERT INTO tasks (title, hora, recorrencia) VALUES ('remedio', '08:00', 'diaria')"
        )
        self.conn.commit()
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["remedio"])
        r2 = self.exec["consultar_tarefas"]({})  # idempotente
        self.assertEqual(r2["total"], 1)

    def test_limite_30_com_total_real(self):
        for i in range(45):
            self.tarefa(f"t{i:02d}", _iso(0))
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual(len(r["tarefas"]), 30)
        self.assertEqual(r["total"], 45)
        self.assertIn("30 de 45", r["obs"])

    def test_atrasadas_limite_10(self):
        for i in range(15):
            self.tarefa(f"a{i:02d}", _iso(-1 - i))
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual(len(r["atrasadas"]), 10)
        self.assertEqual(r["atrasadas_total"], 15)
        self.assertEqual(r["atrasadas"][0]["titulo"], "a14")  # a mais antiga primeiro

    def test_ordena_por_hora_com_sem_hora_no_fim(self):
        self.tarefa("sem hora", _iso(0))
        self.tarefa("tarde", _iso(0), "15:00")
        self.tarefa("cedo", _iso(0), "07:30")
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["cedo", "tarde", "sem hora"])

    def test_erros(self):
        f = self.exec["consultar_tarefas"]
        self.assertEqual(f({"de": "2026-02-30"}), {"erro": "data invalida, use AAAA-MM-DD"})
        self.assertEqual(f({"ate": "amanha"}), {"erro": "data invalida, use AAAA-MM-DD"})
        self.assertEqual(f({"de": 20260101}), {"erro": "data invalida, use AAAA-MM-DD"})
        self.assertIn("erro", f({"de": "2026-01-01", "ate": "2027-03-01"}))  # > 400 dias
        self.assertNotIn("erro", f({"de": _iso(0), "ate": _iso(399)}))  # exatamente 400 dias
        self.assertIn("erro", f({"de": _iso(0), "ate": _iso(400)}))  # 401 dias
        self.assertIn("erro", f({"de": _iso(2), "ate": _iso(1)}))
        self.assertIn("erro", f({"status": "banana"}))
        self.assertIn("erro", f({"status": 5}))

    def test_so_ate_ou_so_de(self):
        self.tarefa("velha", _iso(-5))
        r = self.exec["consultar_tarefas"]({"ate": _iso(-5)})
        self.assertEqual(r["periodo"], {"de": _iso(-5), "ate": _iso(-5)})
        self.assertEqual([t["titulo"] for t in r["tarefas"]], ["velha"])
        r = self.exec["consultar_tarefas"]({"de": _iso(-10)})
        self.assertEqual(r["periodo"], {"de": _iso(-10), "ate": _iso(0)})


class GastosTestCase(_Base):
    def gasto(self, valor, categoria, descricao, dia=0, tipo="real"):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (?, ?, ?, ?, ?)",
            (valor, categoria, descricao, tipo, f"{_iso(dia)} 12:00:00"),
        )
        self.conn.commit()

    def banco(self, valor, dia, descricao="Compra", tipo_operacao="DEBIT", categoria_pluggy=None, ext="x1"):
        conta = db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        self.conn.execute(
            """INSERT INTO bank_transactions (bank_account_id, data, descricao, valor, external_id, categoria,
               categoria_pluggy, descricao_original, tipo_operacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (conta, _iso(dia), db.criptografia.criptografar(descricao), db._cnum(valor), ext, None,
             categoria_pluggy, descricao, tipo_operacao),
        )
        self.conn.commit()

    def _mes(self):
        return HOJE.replace(day=1), HOJE

    def test_soma_bate_com_a_fonte_da_aba_financas(self):
        self.gasto(100.0, "mercado", "compras da semana")
        self.gasto(50.5, "transporte", "uber")
        self.gasto(999.0, "lazer", "planejado nao conta", tipo="planejado")
        self.banco(30.25, 0, "IFOOD", ext="b1")
        self.banco(500.0, 0, "Pagamento de fatura", categoria_pluggy="Credit card payment", ext="b2")
        self.banco(70.0, 0, "Salario", tipo_operacao="CREDIT", ext="b3")
        r = self.exec["consultar_gastos"]({})
        de, ate = self._mes()
        total_fonte, top_fonte = f9_financas._gasto_periodo(self.conn, de, ate)
        self.assertEqual(r["total"], round(total_fonte, 2))
        self.assertEqual(r["total"], 180.75)
        self.assertEqual(r["quantidade"], 3)
        self.assertEqual(r["por_categoria"], top_fonte)
        self.assertEqual(r["periodo"], {"de": de.isoformat(), "ate": ate.isoformat()})
        self.assertEqual(r["maiores"][0]["valor"], 100.0)
        self.assertEqual([m["valor"] for m in r["maiores"]], [100.0, 50.5, 30.25])
        self.assertEqual(set(r["maiores"][0]), {"data", "descricao", "categoria", "valor"})

    def test_periodo_explicito_bate_com_fonte(self):
        self.gasto(10.0, "mercado", "a", dia=-40)
        self.gasto(20.0, "mercado", "b", dia=-35)
        self.gasto(30.0, "mercado", "c", dia=-1)
        de, ate = HOJE - timedelta(days=45), HOJE - timedelta(days=30)
        r = self.exec["consultar_gastos"]({"de": de.isoformat(), "ate": ate.isoformat()})
        self.assertEqual(r["total"], round(f9_financas._gasto_periodo(self.conn, de, ate)[0], 2))
        self.assertEqual(r["total"], 30.0)

    def test_filtro_categoria_sem_acento_e_caixa(self):
        self.gasto(40.0, "alimentacao", "almoco")
        self.gasto(60.0, "Alimentação", "jantar")
        self.gasto(15.0, "transporte", "onibus")
        for termo in ("ALIMENTACAO", "alimentação", "  Alimentacao "):
            r = self.exec["consultar_gastos"]({"categoria": termo})
            self.assertEqual(r["total"], 100.0, termo)
            self.assertEqual(r["quantidade"], 2, termo)
        r = self.exec["consultar_gastos"]({"categoria": "transporte"})
        self.assertEqual(r["total"], 15.0)

    def test_categoria_sem_resultado_lista_as_do_periodo(self):
        self.gasto(15.0, "transporte", "onibus")
        r = self.exec["consultar_gastos"]({"categoria": "inexistente"})
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["quantidade"], 0)
        self.assertTrue(r["categorias_no_periodo"])

    def test_periodo_vazio_total_zero(self):
        r = self.exec["consultar_gastos"]({"de": "2020-01-01", "ate": "2020-01-31"})
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["quantidade"], 0)
        self.assertEqual(r["por_categoria"], [])
        self.assertEqual(r["maiores"], [])

    def test_top_8_categorias_e_5_maiores(self):
        for i in range(12):
            self.gasto(10.0 + i, f"cat{i:02d}", f"g{i}")
        r = self.exec["consultar_gastos"]({})
        self.assertEqual(len(r["por_categoria"]), 8)
        self.assertEqual(len(r["maiores"]), 5)
        self.assertEqual(r["quantidade"], 12)
        self.assertEqual(r["maiores"][0]["valor"], 21.0)

    def test_erros_de_data(self):
        f = self.exec["consultar_gastos"]
        self.assertEqual(f({"de": "2026-02-30"}), {"erro": "data invalida, use AAAA-MM-DD"})
        self.assertEqual(f({"ate": "31/12/2026"}), {"erro": "data invalida, use AAAA-MM-DD"})
        self.assertIn("erro", f({"de": "2024-01-01", "ate": "2026-01-01"}))
        self.assertIn("erro", f({"de": _iso(0), "ate": _iso(-1)}))

    def test_modo_visitante_recusa(self):
        with app.app.test_request_context("/"):
            with patch("app._modo_visitante_ativo", return_value=True):
                r = self.exec["consultar_gastos"]({})
        self.assertIn("erro", r)


class AgendaTestCase(_Base):
    def test_ordena_por_hora_misturando_icloud_e_tarefas(self):
        self.tarefa("tarefa 15h", _iso(0), "15:00")
        self.tarefa("tarefa 08h", _iso(0), "08:00")
        self.tarefa("sem hora", _iso(0))
        eventos = [
            {"titulo": "Reuniao", "inicio": f"{_iso(0)}T11:00:00", "fim": f"{_iso(0)}T12:00:00", "dia_inteiro": False},
            {"titulo": "Feriado", "inicio": _iso(0), "fim": _iso(1), "dia_inteiro": True},
        ]
        with patch.object(caldav_client, "configurado", return_value=True), patch.object(
            caldav_client, "eventos_do_dia", return_value=eventos
        ) as ev:
            r = self.exec["consultar_agenda"]({})
        ev.assert_called_once_with(HOJE)
        self.assertEqual(r["dia"], HOJE.isoformat())
        self.assertEqual(r["eventos_icloud"], "ok")
        self.assertEqual([c["titulo"] for c in r["compromissos"]], ["Feriado", "tarefa 08h", "Reuniao", "tarefa 15h"])
        self.assertEqual(r["compromissos"][2]["hora"], "11:00")
        self.assertEqual(r["compromissos"][2]["ate"], "12:00")
        self.assertTrue(r["compromissos"][0]["dia_inteiro"])
        self.assertEqual(r["tarefas_pendentes_sem_hora"], 1)
        self.assertEqual(r["total"], 4)

    def test_outro_dia_usa_o_dia_pedido(self):
        self.tarefa("amanha 10h", _iso(1), "10:00")
        self.tarefa("hoje 10h", _iso(0), "10:00")
        with patch.object(caldav_client, "configurado", return_value=True), patch.object(
            caldav_client, "eventos_do_dia", return_value=[]
        ) as ev:
            r = self.exec["consultar_agenda"]({"dia": _iso(1)})
        ev.assert_called_once_with(HOJE + timedelta(days=1))
        self.assertEqual([c["titulo"] for c in r["compromissos"]], ["amanha 10h"])

    def test_dia_sem_nada_lista_vazia(self):
        with patch.object(caldav_client, "configurado", return_value=False):
            r = self.exec["consultar_agenda"]({"dia": _iso(30)})
        self.assertEqual(r["compromissos"], [])
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["eventos_icloud"], "nao configurado")

    def test_icloud_falhando_nao_quebra(self):
        self.tarefa("tarefa 09h", _iso(0), "09:00")
        with patch.object(caldav_client, "configurado", return_value=True), patch.object(
            caldav_client, "eventos_do_dia", side_effect=RuntimeError("caldav fora do ar")
        ):
            r = self.exec["consultar_agenda"]({})
        self.assertNotIn("erro", r)
        self.assertEqual(r["eventos_icloud"], "indisponivel agora")
        self.assertEqual([c["titulo"] for c in r["compromissos"]], ["tarefa 09h"])

    def test_tarefa_concluida_aparece_marcada(self):
        self.tarefa("feita", _iso(0), "07:00", concluida=f"{_iso(0)} 07:30:00")
        with patch.object(caldav_client, "configurado", return_value=False):
            r = self.exec["consultar_agenda"]({})
        self.assertTrue(r["compromissos"][0]["concluida"])

    def test_data_invalida(self):
        for dia in ("2026-02-30", "hoje", 5, ["2026-01-01"], "2026-1-1"):
            self.assertEqual(self.exec["consultar_agenda"]({"dia": dia}), {"erro": "data invalida, use AAAA-MM-DD"}, dia)

    def test_evento_malformado_do_icloud_e_ignorado(self):
        eventos = ["lixo", None, {"titulo": "ok", "inicio": f"{_iso(0)}T09:00:00", "fim": None, "dia_inteiro": False}, {}]
        with patch.object(caldav_client, "configurado", return_value=True), patch.object(
            caldav_client, "eventos_do_dia", return_value=eventos
        ):
            r = self.exec["consultar_agenda"]({})
        self.assertNotIn("erro", r)
        self.assertIn("ok", [c["titulo"] for c in r["compromissos"]])


LIXO = [
    None, 0, 1, -1, 3.14, float("nan"), float("inf"), True, False, [], [1, 2], {}, {"a": 1},
    "", " ", "x" * 100_000, "2026-02-30", "2026-13-01", "0000-00-00", "9999-12-31", "0001-01-01",
    "20260929", "2026-W01", "2026-09-29T10:00:00", "'; DROP TABLE tasks;--", "%", "\x00", "‮2026-09-29",
    "ação ção ñ 日本語 🙂", "\n\n", b"bytes", object(), ("2026-01-01",), {"de": "2026-01-01"},
]


class FuzzTestCase(_Base):
    def setUp(self):
        super().setUp()
        self.tarefa("t", _iso(0), "10:00")
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo, created_at) VALUES (5, 'x', 'y', 'real', ?)",
            (f"{_iso(0)} 10:00:00",),
        )
        self.conn.commit()

    def _rodar(self, nome, entrada):
        with patch.object(caldav_client, "configurado", return_value=True), patch.object(
            caldav_client, "eventos_do_dia", return_value=[]
        ):
            try:
                r = self.exec[nome](entrada)
            except Exception as e:  # noqa: BLE001
                self.fail(f"{nome}({entrada!r:.60}) levantou {type(e).__name__}: {e}")
        self.assertIsInstance(r, dict, nome)
        return r

    def test_entrada_inteira_maluca(self):
        for nome in ToolsTestCase.NOVAS:
            for entrada in LIXO:
                self._rodar(nome, entrada)

    def test_cada_campo_maluco(self):
        campos = {
            "consultar_tarefas": ("de", "ate", "status"),
            "consultar_gastos": ("de", "ate", "categoria"),
            "consultar_agenda": ("dia",),
        }
        for nome, chaves in campos.items():
            for chave in chaves:
                for valor in LIXO:
                    self._rodar(nome, {chave: valor})

    def test_combinacoes(self):
        for de in ("2026-02-30", "2026-01-01", None, 5):
            for ate in ("2026-12-31", "2027-12-31", None, "x"):
                r = self._rodar("consultar_tarefas", {"de": de, "ate": ate, "status": "todas"})
                self._rodar("consultar_gastos", {"de": de, "ate": ate, "categoria": "x" * 5000})
                self.assertTrue("erro" in r or "tarefas" in r)

    def test_erro_interno_vira_dict_de_erro(self):
        with patch("chat_consultas.aprendizado.normalizar_consulta", side_effect=RuntimeError("boom")):
            self.assertIn("erro", chat_consultas.consultar_gastos(self.conn, {"categoria": "x"}))
            self.assertIn("erro", chat_consultas.consultar_tarefas(self.conn, {"status": "todas"}))
        self.assertIn("erro", chat_consultas.consultar_agenda(None, {}))  # conn invalida


if __name__ == "__main__":
    unittest.main()


class GastoPorNomeEVoosTestCase(_Base):
    def _gasto(self, valor, cat, desc):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, created_at) VALUES (?, ?, ?, ?)",
            (valor, cat, desc, f"{HOJE.replace(day=1).isoformat()} 12:00:00"),
        )
        self.conn.commit()

    def test_gasto_filtra_pelo_nome_alem_da_categoria(self):
        self._gasto(55.90, "lazer", "Netflix")
        self._gasto(187.45, "alimentação", "Mercado")
        r = self.exec["consultar_gastos"]({"categoria": "netflix"})
        self.assertEqual(r["total"], 55.9)
        r = self.exec["consultar_gastos"]({"categoria": "mercado"})
        self.assertEqual(r["total"], 187.45)
        r = self.exec["consultar_gastos"]({"categoria": "lazer"})
        self.assertEqual(r["total"], 55.9)

    def test_gasto_sem_resultado_lista_categorias(self):
        self._gasto(10, "lazer", "Cinema")
        r = self.exec["consultar_gastos"]({"categoria": "padaria"})
        self.assertEqual(r["total"], 0)
        self.assertIn("Lazer", r["categorias_no_periodo"])

    def test_voos_total_ultimo_e_futuro(self):
        for dias, o, d, h in [(-10, "SBGR", "SBRJ", 1.2), (-30, "SBRJ", "SBGR", 2.0), (7, "SBGR", "SBBR", 1.5)]:
            self.conn.execute("INSERT INTO voos (data, origem, destino, horas) VALUES (?, ?, ?, ?)", (_iso(dias), o, d, h))
        self.conn.commit()
        r = self.exec["consultar_voos"]({})
        self.assertEqual(r["total_voos"], 2)
        self.assertEqual(r["total_horas"], 3.2)
        self.assertEqual(r["ultimos_voos"][0]["destino"], "SBRJ")
        self.assertEqual(r["proximos_voos"][0]["destino"], "SBBR")

    def test_voos_da_civ_somam_por_funcao_e_simulador_fica_fora(self):
        linhas = [
            (-40, "SSBL", "SSBL", 1.0, "PTXXW", "Piloto em Instrução", None),
            (-35, "SSBL", "SSPG", 1.2, "PRLOM", "Piloto em Instrução Solo", None),
            (-30, None, "Simulador", 1.0, None, "Piloto em Instrução", "simulador"),
        ]
        for dias, o, d, h, anv, f, tipo in linhas:
            self.conn.execute(
                "INSERT INTO voos (data, origem, destino, horas, aeronave, funcao, tipo, fonte) VALUES (?, ?, ?, ?, ?, ?, ?, 'civ')",
                (_iso(dias), o, d, h, anv, f, tipo),
            )
        self.conn.commit()
        r = self.exec["consultar_voos"]({})
        self.assertEqual(r["total_voos"], 2)
        self.assertEqual(r["total_horas"], 2.2)
        self.assertEqual(r["total_horas_hhmm"], "2:12")
        self.assertEqual(r["horas_por_funcao"], {"Piloto em Instrução Solo": 1.2, "Piloto em Instrução": 1.0})
        self.assertEqual(r["horas_por_aeronave"]["PRLOM"], 1.2)
        self.assertEqual(r["simulador"], {"sessoes": 1, "horas": 1.0})

    def test_voos_vazio_e_entrada_maluca_nunca_levanta(self):
        r = self.exec["consultar_voos"]({})
        self.assertEqual((r["total_voos"], r["total_horas"], r["proximos_voos"]), (0, 0, []))
        for lixo in (None, "x", 5, [], {"a": 1}):
            self.assertIsInstance(self.exec["consultar_voos"](lixo), dict)

    def test_agenda_traz_titulos_das_tarefas_sem_hora(self):
        self.tarefa("Comprar presente da Ana", _iso(1))
        r = self.exec["consultar_agenda"]({"dia": _iso(1)})
        self.assertEqual(r["tarefas_pendentes_sem_hora"], 1)
        self.assertEqual(r["tarefas_sem_hora"], ["Comprar presente da Ana"])

    def test_pendentes_total_geral_conta_todas_as_datas(self):
        self.tarefa("hoje", _iso(0))
        self.tarefa("atrasada", _iso(-3))
        self.tarefa("semana que vem", _iso(9))
        self.tarefa("sem data")
        self.tarefa("feita", _iso(0), concluida=f"{_iso(0)} 09:00:00")
        r = self.exec["consultar_tarefas"]({})
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["pendentes_total_geral"], 4)
        self.assertNotIn("pendentes_total_geral", self.exec["consultar_tarefas"]({"status": "concluidas"}))
