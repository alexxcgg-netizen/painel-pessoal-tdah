"""Prova de qualidade do chat (scripts/eval_chat): validacao do casos.json e o runner de ponta a
ponta com a IA MOCKADA - prova que ele (1) roda contra uma COPIA do banco (o de origem nunca e
escrito), (2) desliga agenda/Uber/push/Telegram/HTTP de escrita e (3) aplica as checagens.
Nenhuma chamada real de API, nenhum banco real."""

import hashlib
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import caldav_client  # noqa: E402
import push_client  # noqa: E402
import requests  # noqa: E402
import telegram_bot  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
_NOME_MODULO = "eval_chat_rodar_sob_teste"


def _carregar_rodar():
    spec = importlib.util.spec_from_file_location(_NOME_MODULO, RAIZ / "scripts" / "eval_chat" / "rodar.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[_NOME_MODULO] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _sha(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


class CasosJsonTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rodar = _carregar_rodar()
        cls.addClassCleanup(sys.modules.pop, _NOME_MODULO, None)
        cls.dados = cls.rodar.carregar_casos()

    def test_casos_json_e_valido_e_usa_so_ferramentas_reais(self):
        erros, _avisos = self.rodar.validar_casos(self.dados, self.rodar.nomes_das_ferramentas())
        self.assertEqual(erros, [])
        self.assertGreaterEqual(len(self.dados["casos"]), 30)

    def test_cobre_registro_dump_de_audio_e_conversa(self):
        grupos = {c.get("grupo") for c in self.dados["casos"]}
        self.assertTrue({"registro", "dump de audio", "conversa"} <= grupos)
        modelos = {c.get("modelo_esperado") for c in self.dados["casos"]}
        self.assertTrue({"haiku", "sonnet", "local"} <= modelos)

    def test_validador_pega_ferramenta_inexistente_regex_ruim_e_id_repetido(self):
        base = {"global": {"max_emojis": 1, "frases_proibidas": ["Claro!"]},
                "casos": [
                    {"id": "a", "mensagem": "oi", "ferramentas_obrigatorias": ["ferramenta_que_nao_existe"],
                     "resposta": {"min_chars": 1, "max_chars": 10}},
                    {"id": "a", "mensagem": "oi", "contem": ["("], "resposta": {"min_chars": 5, "max_chars": 1}},
                ]}
        erros, _ = self.rodar.validar_casos(base, {"registrar_gasto"}, checar_roteador=False)
        texto = " | ".join(erros)
        self.assertIn("ferramenta_que_nao_existe", texto)
        self.assertIn("id repetido", texto)
        self.assertIn("regex invalido", texto)
        self.assertIn("min_chars <= max_chars", texto)

    def test_estimativa_de_custo_fica_em_ordem_de_grandeza_razoavel(self):
        est = self.rodar.estimar_custo(self.dados, tokens_fixos=15000)
        self.assertGreater(est["total_usd"], 0.05)
        self.assertLess(est["total_usd"], 2.0)
        sem_juiz = est["total_usd"]
        com_juiz = self.rodar.estimar_custo(self.dados, tokens_fixos=15000, juiz=True)["total_usd"]
        self.assertGreater(com_juiz, sem_juiz)
        local = [c for c in est["por_caso"] if c["modelo"] == "local"]
        self.assertTrue(local and all(c["usd"] == 0 for c in local))


class ChecagensTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rodar = _carregar_rodar()
        cls.addClassCleanup(sys.modules.pop, _NOME_MODULO, None)
        cls.glob = {"max_emojis": 1, "frases_proibidas": ["Claro!", "Ótima pergunta", "Se precisar de mais alguma coisa"]}

    def _caso(self, **extra):
        return {"id": "x", "mensagem": "m", "resposta": {"min_chars": 5, "max_chars": 100}, **extra}

    def avaliar(self, caso, resposta, acoes=(), erro=None, deltas=None, modelos=None):
        return self.rodar.avaliar_resposta(caso, self.glob, resposta, list(acoes), erro, deltas, modelos)

    def test_passa_quando_tudo_certo(self):
        caso = self._caso(ferramentas_obrigatorias=["registrar_gasto"], contem=["45"], cria={"expenses": 1})
        self.assertEqual(self.avaliar(caso, "Anotado: R$ 45 no mercado.", ["registrar_gasto"], deltas={"expenses": 1}), [])

    def test_ferramentas_obrigatoria_grupo_e_proibida(self):
        caso = self._caso(ferramentas_obrigatorias=["registrar_gasto"], ferramentas_alguma_de=[["a", "b"]],
                          ferramentas_proibidas=["apagar_tarefa"])
        falhas = " | ".join(self.avaliar(caso, "Anotado, beleza.", ["apagar_tarefa"]))
        self.assertIn("obrigatoria 'registrar_gasto'", falhas)
        self.assertIn("nenhuma de ['a', 'b']", falhas)
        self.assertIn("proibida 'apagar_tarefa'", falhas)

    def test_tamanho_fora_da_faixa(self):
        self.assertTrue(any("curta demais" in f for f in self.avaliar(self._caso(), "ok")))
        self.assertTrue(any("longa demais" in f for f in self.avaliar(self._caso(), "x" * 101)))

    def test_frases_de_robo_sem_olhar_acento_nem_caixa(self):
        for frase in ("Claro! Anotei aqui.", "otima pergunta, vamos la", "Anotei. Se precisar de mais alguma coisa, e so falar"):
            self.assertTrue(any("cara de robo" in f for f in self.avaliar(self._caso(), frase)), frase)
        self.assertEqual(self.avaliar(self._caso(), "Anotei, claro que sim."), [])  # "claro" sem exclamacao nao e a formula

    def test_excesso_de_emoji(self):
        self.assertEqual(self.avaliar(self._caso(), "Feito, valeu \U0001F44D"), [])
        self.assertTrue(any("emoji demais" in f for f in self.avaliar(self._caso(), "Feito \U0001F44D\U0001F389\U0001F680")))
        self.assertEqual(self.avaliar(self._caso(), "Feito ✓ anotado"), [])  # check mark nao conta

    def test_contem_nao_contem_e_cria(self):
        caso = self._caso(contem=["pressao"], nao_contem=["lorem"], cria={"voos": 1})
        falhas = " | ".join(self.avaliar(caso, "A Pressão muda lorem ipsum", deltas={"voos": 0}))
        self.assertNotIn("faltou na resposta", falhas)  # 'Pressão' casa com /pressao/ (sem acento)
        self.assertIn("nao devia aparecer", falhas)
        self.assertIn("'voos'", falhas)

    def test_modelo_esperado(self):
        sonnet = self._caso(modelo_esperado="sonnet")
        self.assertEqual(self.avaliar(sonnet, "resposta normal", modelos=["claude-sonnet-5"]), [])
        self.assertTrue(any("esperava o modelo sonnet" in f for f in self.avaliar(sonnet, "resposta normal", modelos=["claude-haiku-5-5"])))
        local = self._caso(modelo_esperado="local")
        self.assertEqual(self.avaliar(local, "pronto, +1 copo", modelos=[]), [])
        self.assertTrue(any("resolver local" in f for f in self.avaliar(local, "pronto, +1 copo", modelos=["claude-haiku-5-5"])))

    def test_erro_do_pipeline_falha_o_caso(self):
        self.assertEqual(len(self.avaliar(self._caso(), None, erro="teto estourado")), 1)


class BloqueioDeEfeitosTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rodar = _carregar_rodar()
        cls.addClassCleanup(sys.modules.pop, _NOME_MODULO, None)

    def test_host_da_anthropic(self):
        self.assertTrue(self.rodar._host_da_anthropic("https://api.anthropic.com/v1/messages"))
        self.assertFalse(self.rodar._host_da_anthropic("https://api.telegram.org/bot1/sendMessage"))
        self.assertFalse(self.rodar._host_da_anthropic("https://anthropic.com.evil.example/x"))

    def test_desliga_efeitos_e_restaura_ao_sair(self):
        originais = (caldav_client.criar_evento, telegram_bot.enviar_mensagem, push_client.enviar, requests.sessions.Session.request)
        bloqueios = []
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token-que-nao-pode-sair", "ICLOUD_USERNAME": "x"}):
            with self.rodar.efeitos_externos_desligados(bloqueios):
                self.assertNotIn("TELEGRAM_BOT_TOKEN", os.environ)
                self.assertFalse(telegram_bot.configurado())
                self.assertFalse(push_client.configurado())
                evento = caldav_client.criar_evento("Reuniao", datetime(2026, 10, 14, 14), datetime(2026, 10, 14, 15))
                self.assertEqual(evento["titulo"], "Reuniao")
                self.assertTrue(telegram_bot.enviar_mensagem("oi"))
                self.assertTrue(push_client.enviar({}, "t", "c"))
                resposta = requests.post("https://api.telegram.org/botX/sendMessage", json={"text": "oi"})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(requests.delete("https://exemplo.invalido/recurso").status_code, 200)
            self.assertEqual(os.environ.get("TELEGRAM_BOT_TOKEN"), "token-que-nao-pode-sair")  # ambiente restaurado
        alvos = [b["alvo"] for b in bloqueios]
        for esperado in ("caldav.criar_evento", "telegram.enviar_mensagem", "push.enviar", "http POST", "http DELETE"):
            self.assertIn(esperado, alvos)
        self.assertEqual(originais, (caldav_client.criar_evento, telegram_bot.enviar_mensagem, push_client.enviar, requests.sessions.Session.request))


class RunnerComIaMockadaTestCase(unittest.TestCase):
    """Roda `executar` de ponta a ponta: banco de origem temporario (com um dado sentinela), IA falsa."""

    @classmethod
    def setUpClass(cls):
        cls.rodar = _carregar_rodar()
        cls.addClassCleanup(sys.modules.pop, _NOME_MODULO, None)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.origem = Path(self.tmp.name) / "origem.db"
        p = patch.object(db, "DB_PATH", self.origem)
        p.start()
        self.addCleanup(p.stop)
        db.init_db()
        conn = db.get_db()
        conn.execute("INSERT INTO tasks (title) VALUES ('SENTINELA-REAL')")
        conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES ('user', 'historico real que nao pode vazar')")
        conn.commit()
        conn.close()
        self.hash_antes = _sha(self.origem)
        self.contextos_vistos = []

    def _ia_falsa(self):
        usos = {"haiku": {"model": "claude-haiku-5-5", "input_tokens": 5000, "output_tokens": 60, "cost_usd": 0.00056},
                "sonnet": {"model": "claude-sonnet-5", "input_tokens": 5000, "output_tokens": 700, "cost_usd": 0.017}}

        def falsa(historico, contexto, memorias, executores, **kwargs):
            self.contextos_vistos.append([m["content"] for m in historico if m["role"] == "user"])
            mensagem = historico[-1]["content"]
            if "mercado" in mensagem:
                executores["registrar_gasto"]({"valor": 45, "titulo": "mercado", "categoria": "mercado"})
                # tenta mandar coisa pra fora - tudo isso precisa ser engolido pelo runner
                caldav_client.criar_evento("Evento fantasma", datetime(2026, 10, 14, 9), datetime(2026, 10, 14, 10))
                telegram_bot.enviar_mensagem("vazou?")
                requests.post("https://api.telegram.org/botX/sendMessage", json={"text": "vazou?"})
                return "Anotei: R$ 45 no mercado.", ["registrar_gasto"], dict(usos["haiku"])
            if "estol" in mensagem:
                return "Claro! " + "O estol acontece quando o angulo de ataque passa do critico. " * 12, [], dict(usos["sonnet"])
            return "Beleza.", [], dict(usos["haiku"])
        return falsa

    def _dados(self):
        glob = {"max_emojis": 1, "frases_proibidas": ["Claro!"]}
        casos = [
            {"id": "gasto", "mensagem": "gastei 45 no mercado", "ferramentas_obrigatorias": ["registrar_gasto"],
             "resposta": {"min_chars": 3, "max_chars": 100}, "contem": ["45"], "cria": {"expenses": 1}, "modelo_esperado": "haiku"},
            {"id": "estol-robotico", "mensagem": "me explica o estol", "resposta": {"min_chars": 100, "max_chars": 2000},
             "modelo_esperado": "sonnet"},
            {"id": "faltou-ferramenta", "mensagem": "marca o dentista amanha", "ferramentas_obrigatorias": ["registrar_tarefa"],
             "resposta": {"min_chars": 3, "max_chars": 100}},
        ]
        return {"global": glob, "casos": casos}

    def test_fluxo_completo(self):
        saidas = []
        with patch("claude_client.chat", side_effect=self._ia_falsa()), \
                patch.object(db, "DB_PATH", db.DB_PATH):  # garante restauracao mesmo se o runner falhar
            caminho_antes = db.DB_PATH
            relatorio = self.rodar.executar(self._dados(), self.origem, pasta_resultados=Path(self.tmp.name) / "res",
                                            imprimir=saidas.append)
            # DB_PATH volta ao que era antes do runner
            self.assertEqual(db.DB_PATH, caminho_antes)

        # 1) banco de origem intocado, byte a byte (nada de gasto/evento/mensagem nova)
        self.assertEqual(_sha(self.origem), self.hash_antes)
        conn = sqlite3.connect(self.origem)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0], 0)
        conn.close()

        # 2) o historico real da origem nao vazou pra IA (cada caso comeca com o chat limpo)
        for vistos in self.contextos_vistos:
            self.assertEqual(len(vistos), 1)
            self.assertNotIn("historico real que nao pode vazar", vistos[0])

        # 3) efeitos externos engolidos e registrados
        alvos = [b["alvo"] for c in relatorio["casos"] for b in c["bloqueios"]]
        for esperado in ("caldav.criar_evento", "telegram.enviar_mensagem", "http POST"):
            self.assertIn(esperado, alvos)
        self.assertEqual(relatorio["totais"]["bloqueios_externos"], len(alvos))

        # 4) checagens aplicadas: o gasto passa (gravou na COPIA), o estol falha por "Claro!", o 3o por falta de tool
        por_id = {c["id"]: c for c in relatorio["casos"]}
        self.assertTrue(por_id["gasto"]["ok"], por_id["gasto"]["falhas"])
        self.assertEqual(por_id["gasto"]["deltas"], {"expenses": 1})
        self.assertEqual(por_id["gasto"]["via"], "haiku")
        self.assertFalse(por_id["estol-robotico"]["ok"])
        self.assertTrue(any("Claro!" in f for f in por_id["estol-robotico"]["falhas"]))
        self.assertEqual(por_id["estol-robotico"]["via"], "sonnet")
        self.assertFalse(por_id["faltou-ferramenta"]["ok"])
        self.assertTrue(any("registrar_tarefa" in f for f in por_id["faltou-ferramenta"]["falhas"]))

        # 5) custo somado a partir do que o pipeline gravou, e arquivo de resultados gravado
        self.assertAlmostEqual(relatorio["totais"]["custo_chat_usd"], 0.00056 * 2 + 0.017, places=5)
        self.assertEqual(relatorio["totais"]["passaram"], 1)
        self.assertTrue(Path(relatorio["arquivo"]).is_file())
        self.assertRegex(Path(relatorio["arquivo"]).name, r"^\d{4}-\d{2}-\d{2}-\d{4}\.json$")

        # 6) tabela do terminal
        tabela = []
        self.rodar.imprimir_tabela(relatorio, imprimir=tabela.append)
        texto = "\n".join(tabela)
        self.assertIn("gasto", texto)
        self.assertIn("Passaram 1/3", texto)

    def test_cada_caso_comeca_do_snapshot_limpo(self):
        # o caso 1 grava um gasto; o caso 2 nao pode enxergar a linha do caso 1
        contagens = []

        def falsa(historico, contexto, memorias, executores, **kwargs):
            c = db.get_db()
            contagens.append(c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0])
            c.close()
            executores["registrar_gasto"]({"valor": 10, "titulo": "x"})
            return "Anotei.", ["registrar_gasto"], {"model": "claude-haiku-5-5", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        dados = {"global": {"max_emojis": 1, "frases_proibidas": ["Claro!"]},
                 "casos": [{"id": "um", "mensagem": "gastei 10", "resposta": {"min_chars": 1, "max_chars": 50}},
                           {"id": "dois", "mensagem": "gastei 10 de novo", "resposta": {"min_chars": 1, "max_chars": 50}}]}
        with patch("claude_client.chat", side_effect=falsa):
            self.rodar.executar(dados, self.origem, pasta_resultados=None, imprimir=lambda *_: None)
        self.assertEqual(contagens, [0, 0])
        self.assertEqual(_sha(self.origem), self.hash_antes)

    def test_teto_da_rodada_para_de_chamar_a_ia(self):
        chamadas = []

        def falsa(historico, contexto, memorias, executores, **kwargs):
            chamadas.append(1)
            return "ok ok", [], {"model": "claude-sonnet-5", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.6}

        dados = {"global": {"max_emojis": 1, "frases_proibidas": ["Claro!"]},
                 "casos": [{"id": f"c{i}", "mensagem": f"conta {i} por que", "resposta": {"min_chars": 1, "max_chars": 50}} for i in range(4)]}
        with patch("claude_client.chat", side_effect=falsa):
            relatorio = self.rodar.executar(dados, self.origem, teto_usd=1.0, pasta_resultados=None, imprimir=lambda *_: None)
        self.assertEqual(len(chamadas), 2)  # 0.6 + 0.6 passa de 1.0 -> os outros 2 nem chamam
        self.assertTrue(all("teto da rodada" in " ".join(c["falhas"]) for c in relatorio["casos"][2:]))

    def test_origem_inexistente_nao_cria_banco(self):
        inexistente = Path(self.tmp.name) / "nao-existe.db"
        with self.assertRaises(FileNotFoundError):
            self.rodar.executar(self._dados(), inexistente, pasta_resultados=None, imprimir=lambda *_: None)
        self.assertFalse(inexistente.exists())

    def test_modo_validacao_nao_abre_banco_nem_chama_ia(self):
        with patch("claude_client.chat") as chat, patch.object(self.rodar, "executar") as exec_, \
                patch("builtins.print"):
            self.assertEqual(self.rodar.main([]), 0)
        chat.assert_not_called()
        exec_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
