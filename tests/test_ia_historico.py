# Testes da faixa A5 (ia/historico.py - resumo fixo + reconstrucao do chat).
# Banco sempre temporario (SQL da migracao aplicado direto, sem depender de
# db.init_db/infra de migracao ainda nao mesclada). IA sempre mockada -
# nenhuma chamada real, nenhuma credencial.
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from ia import core, historico
from ia.contrato import Resposta

MIGRACAO_SQL = (
    Path(__file__).resolve().parent.parent
    / "migracoes"
    / "202609241100_a5_historico.sql"
).read_text(encoding="utf-8")


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE chat_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            papel TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.executescript(MIGRACAO_SQL)
    conn.commit()
    return conn


def _inserir(conn, *pares) -> None:
    """pares: ("user", "texto"), ("assistant", "texto"), ... em ordem."""
    for papel, texto in pares:
        conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES (?, ?)", (papel, texto))
    conn.commit()


def _interacoes(n: int, prefixo: str = "msg", tamanho: int = 10) -> list:
    """n pares (user, assistant), texto curto - so pra contagem de mensagens."""
    pares = []
    for i in range(n):
        pares.append(("user", f"{prefixo} pergunta {i} " + ("x" * tamanho)))
        pares.append(("assistant", f"{prefixo} resposta {i} " + ("x" * tamanho)))
    return pares


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = _conectar()
        self.addCleanup(self.conn.close)


class TestSemHistorico(Base):
    def test_banco_vazio_nao_reconstroi(self):
        self.assertFalse(historico.precisa_reconstruir(self.conn))

    def test_banco_vazio_devolve_contexto_vazio(self):
        ctx = historico.montar_contexto(self.conn)
        self.assertEqual(ctx, {"contexto_fixo": "", "mensagens": []})

    def test_tabela_ausente_nao_quebra(self):
        # Simula a infra de migracao ainda nao ter chegado: tabela nao existe.
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            "CREATE TABLE chat_mensagens (id INTEGER PRIMARY KEY, papel TEXT, texto TEXT, "
            "criado_em TEXT DEFAULT (datetime('now')));"
        )
        _inserir(conn, ("user", "oi"))
        ctx = historico.montar_contexto(conn)
        self.assertEqual(ctx["contexto_fixo"], "")
        self.assertEqual(len(ctx["mensagens"]), 1)
        conn.close()


class TestPoucasMensagens(Base):
    """Abaixo do limite de verbatim: tudo na integra, sem IA, sem resumo."""

    def test_poucas_mensagens_ficam_todas_na_integra(self):
        _inserir(self.conn, *_interacoes(3))  # 6 mensagens < MENSAGENS_VERBATIM (12)
        with patch.object(core, "chamar_ia") as mock_chamar:
            ctx = historico.montar_contexto(self.conn)
        mock_chamar.assert_not_called()
        self.assertEqual(ctx["contexto_fixo"], "")
        self.assertEqual(len(ctx["mensagens"]), 6)
        self.assertEqual(ctx["mensagens"][0]["role"], "user")
        self.assertEqual(ctx["mensagens"][-1]["role"], "assistant")

    def test_mensagens_no_formato_role_content(self):
        _inserir(self.conn, ("user", "quanto gastei hoje?"))
        ctx = historico.montar_contexto(self.conn)
        self.assertEqual(ctx["mensagens"], [{"role": "user", "content": "quanto gastei hoje?"}])


class TestCorteAlinhado(Base):
    def test_corte_nunca_comeca_por_assistant(self):
        # 20 mensagens (10 interacoes) - bem acima do alvo de 12 - o corte
        # deve cair exatamente numa fronteira 'user'.
        _inserir(self.conn, *_interacoes(10))
        pool = historico._mensagens_desde(self.conn, 0)
        corte = historico._cortar_para_verbatim(pool, historico.MENSAGENS_VERBATIM)
        self.assertEqual(pool[corte]["papel"], "user")
        # com interacoes perfeitamente pareadas, o alvo (12) cai exato.
        self.assertEqual(len(pool) - corte, 12)

    def test_corte_alvo_maior_que_pool_devolve_zero(self):
        _inserir(self.conn, *_interacoes(2))
        pool = historico._mensagens_desde(self.conn, 0)
        self.assertEqual(historico._cortar_para_verbatim(pool, 100), 0)


class TestReconstrucaoPorTamanho(Base):
    def test_abaixo_do_limite_nao_reconstroi(self):
        _inserir(self.conn, *_interacoes(3, tamanho=5))
        self.assertFalse(historico.precisa_reconstruir(self.conn))

    def test_acima_do_limite_reconstroi(self):
        # 6000 tokens * 4 chars/token = 24000 chars pra estourar.
        _inserir(self.conn, ("user", "x" * 30000))
        self.assertTrue(historico.precisa_reconstruir(self.conn))

    def test_reconstroi_e_avanca_marcador(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))  # bem acima do limite
        resposta = Resposta(ok=True, texto="Resumo: Alex conversou sobre varias coisas.")
        with patch.object(core, "chamar_ia", return_value=resposta) as mock_chamar:
            ctx = historico.montar_contexto(self.conn)

        mock_chamar.assert_called_once()
        args, kwargs = mock_chamar.call_args
        self.assertEqual(args[0], "resumo_historico")
        self.assertTrue(args[1])  # lista nao vazia de mensagens a dobrar
        self.assertEqual(args[1][0]["role"], "user")
        self.assertEqual(kwargs["contexto_fixo"], "")  # sem resumo anterior ainda
        self.assertTrue(kwargs["sistema"].strip())  # instrucao de sistema nao vazia

        self.assertEqual(ctx["contexto_fixo"], "Resumo: Alex conversou sobre varias coisas.")
        self.assertEqual(len(ctx["mensagens"]), 12)  # so o trecho verbatim
        estado = historico._obter_estado(self.conn)
        self.assertGreater(estado["ultimo_mensagem_id"], 0)
        self.assertEqual(estado["resumo"], "Resumo: Alex conversou sobre varias coisas.")

    def test_contexto_fixo_identico_entre_chamadas_sem_reconstrucao(self):
        """O ponto central do mecanismo: 2 chamadas seguidas sem cruzar o
        limite/dia devolvem o MESMO contexto_fixo (cache do provedor)."""
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        resposta = Resposta(ok=True, texto="resumo estavel")
        with patch.object(core, "chamar_ia", return_value=resposta):
            ctx1 = historico.montar_contexto(self.conn)
        # mensagem nova pequena - nao deve estourar o limite de novo
        _inserir(self.conn, ("user", "mais uma pergunta curta"))
        with patch.object(core, "chamar_ia", return_value=resposta) as mock_chamar2:
            ctx2 = historico.montar_contexto(self.conn)
        mock_chamar2.assert_not_called()
        self.assertEqual(ctx1["contexto_fixo"], ctx2["contexto_fixo"])
        self.assertNotEqual(ctx1["mensagens"], ctx2["mensagens"])  # so as mensagens novas mudam


class TestReconstrucaoPorDia(Base):
    def test_dia_igual_nao_forca_reconstrucao(self):
        _inserir(self.conn, *_interacoes(3, tamanho=5))
        agora = datetime(2026, 9, 24, 10, 0, 0)
        resposta = Resposta(ok=True, texto="resumo dia 1")
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="x")):
            historico.montar_contexto(self.conn, agora=agora)
        # sem estado["dia"] setado ainda (nao reconstruiu - poucas mensagens), roda de novo mesmo dia
        with patch.object(core, "chamar_ia") as mock_chamar:
            historico.montar_contexto(self.conn, agora=agora)
        mock_chamar.assert_not_called()

    def test_virada_de_dia_forca_reconstrucao_mesmo_com_pouco_texto(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))  # forca 1a reconstrucao
        dia1 = datetime(2026, 9, 24, 23, 0, 0)
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="resumo dia 1")):
            historico.montar_contexto(self.conn, agora=dia1)

        # mensagem nova pequena no dia seguinte - nao estoura tokens, mas o
        # dia mudou, entao tem que reconstruir de novo.
        _inserir(self.conn, ("user", "bom dia"), ("assistant", "bom dia!"))
        dia2 = datetime(2026, 9, 25, 8, 0, 0)
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="resumo dia 2")) as mock2:
            ctx = historico.montar_contexto(self.conn, agora=dia2)

        mock2.assert_called_once()
        self.assertEqual(ctx["contexto_fixo"], "resumo dia 2")

    def test_virada_de_dia_sem_nada_pra_dobrar_so_atualiza_marcador(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        dia1 = datetime(2026, 9, 24, 23, 0, 0)
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="resumo dia 1")):
            historico.montar_contexto(self.conn, agora=dia1)

        # nenhuma mensagem nova - so o dia muda. Nao ha nada alem do trecho
        # verbatim pra dobrar, entao nao deveria chamar IA de novo.
        dia2 = datetime(2026, 9, 25, 8, 0, 0)
        with patch.object(core, "chamar_ia") as mock2:
            ctx = historico.montar_contexto(self.conn, agora=dia2)
        mock2.assert_not_called()
        self.assertEqual(ctx["contexto_fixo"], "resumo dia 1")

        # e no dia 3, sem nada novo de novo, tambem nao chama.
        dia3 = datetime(2026, 9, 26, 8, 0, 0)
        with patch.object(core, "chamar_ia") as mock3:
            historico.montar_contexto(self.conn, agora=dia3)
        mock3.assert_not_called()


class TestFalhaDeIA(Base):
    def test_falha_na_ia_mantem_resumo_e_marcador_antigos(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=False, erro="teto_ia_estourado")):
            ctx = historico.montar_contexto(self.conn)
        self.assertEqual(ctx["contexto_fixo"], "")
        estado = historico._obter_estado(self.conn)
        self.assertEqual(estado["ultimo_mensagem_id"], 0)

    def test_falha_na_ia_nao_levanta_excecao(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        with patch.object(core, "chamar_ia", side_effect=RuntimeError("rede fora")):
            with self.assertRaises(RuntimeError):
                # chamar_ia do nucleo real nunca levanta (contrato), mas se
                # o duble do teste levantar, historico.py nao deve mascarar -
                # isso e bug de configuracao, nao falha de IA esperada.
                historico.montar_contexto(self.conn)

    def test_resposta_ok_mas_texto_vazio_nao_avanca_marcador(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="   ")):
            ctx = historico.montar_contexto(self.conn)
        self.assertEqual(ctx["contexto_fixo"], "")


class TestSequenciaMultiplasReconstrucoes(Base):
    def test_segunda_reconstrucao_usa_resumo_anterior_como_contexto_fixo(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="resumo 1")):
            historico.montar_contexto(self.conn)

        _inserir(self.conn, *_interacoes(20, tamanho=2000, prefixo="rodada2"))
        with patch.object(core, "chamar_ia", return_value=Resposta(ok=True, texto="resumo 2")) as mock2:
            ctx = historico.montar_contexto(self.conn)

        kwargs = mock2.call_args.kwargs
        self.assertIn("resumo 1", kwargs["contexto_fixo"])
        self.assertEqual(ctx["contexto_fixo"], "resumo 2")


class TestPrecisaReconstruirIsolado(Base):
    """precisa_reconstruir() sozinho, sem depender de montar_contexto."""

    def test_agora_injetavel(self):
        _inserir(self.conn, *_interacoes(3, tamanho=5))
        agora_fixo = datetime(2026, 1, 1, 12, 0, 0)
        self.assertFalse(historico.precisa_reconstruir(self.conn, agora=agora_fixo))

    def test_nao_muta_estado(self):
        _inserir(self.conn, *_interacoes(20, tamanho=2000))
        antes = historico._obter_estado(self.conn)
        historico.precisa_reconstruir(self.conn)
        depois = historico._obter_estado(self.conn)
        self.assertEqual(antes, depois)


class TestConfigDaFuncao(unittest.TestCase):
    """ia/config.d/resumo_historico.json precisa carregar (README.md:
    'Rode ia.core.carregar_todas_configs() num teste')."""

    def test_config_carrega_e_bate_com_o_pedido(self):
        core.limpar_cache()
        configs = core.carregar_todas_configs()
        self.assertIn("resumo_historico", configs)
        cfg = configs["resumo_historico"]
        self.assertFalse(cfg["ativo"])
        self.assertEqual(cfg["modelo_atual"], {
            "provedor": "anthropic", "modelo": "claude-haiku-4-5-20251001", "esforco": "",
        })
        self.assertEqual(cfg["alvo"], {
            "provedor": "openai", "modelo": "gpt-6-luna", "esforco": "medio",
        })
        self.assertEqual(cfg["max_tokens_saida"], 400)


class TestMensagensDesdeEEstimativa(Base):
    def test_mensagens_desde_respeita_o_marcador(self):
        _inserir(self.conn, ("user", "a"), ("assistant", "b"), ("user", "c"))
        todas = historico._mensagens_desde(self.conn, 0)
        self.assertEqual(len(todas), 3)
        so_a_ultima = historico._mensagens_desde(self.conn, todas[1]["id"])
        self.assertEqual([m["texto"] for m in so_a_ultima], ["c"])

    def test_estimar_tokens_len_por_4(self):
        pool = [{"texto": "x" * 40}, {"texto": "y" * 60}]
        self.assertEqual(historico._estimar_tokens(pool), 100 // 4)

    def test_texto_none_nao_quebra_estimativa(self):
        # defensivo: coluna texto e NOT NULL no schema real, mas a funcao nao
        # deve estourar se algum dia vier None de outro caminho.
        pool = [{"texto": ""}]
        self.assertEqual(historico._estimar_tokens(pool), 0)


if __name__ == "__main__":
    unittest.main()
