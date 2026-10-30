"""Lab v4, grupo C (avisos e manha): badge, aviso-cara, cartoes-manha, se-entao, bom-dia, carro e o card de cada um.
Sem rede e sem IA de verdade (a IA do cartoes-manha e dublada); banco temporario (nunca o data/painel.db)."""
import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from tests.test_assistente_vida import _Base  # prepara o banco temporario antes de importar o app

import aviso_cara  # noqa: E402
import badge  # noqa: E402
import bom_dia  # noqa: E402
import cards  # noqa: E402
import carro  # noqa: E402
import db  # noqa: E402
import manha  # noqa: E402
import se_entao  # noqa: E402

HOJE = date(2026, 10, 30)
AGORA = datetime(2026, 10, 30, 7, 30)


class _C(_Base):
    def conn(self):
        c = db.get_db()
        self.addCleanup(c.close)
        return c

    def tarefa(self, titulo, dia=None, hora=None, local=None):
        c = self.conn()
        cur = c.execute("INSERT INTO tasks (title, due_date, hora, local) VALUES (?, ?, ?, ?)",
                        (titulo, (dia or HOJE).isoformat(), hora, local))
        c.commit()
        return cur.lastrowid


class BadgeTest(_C):
    def test_conta_abertas_ate_hoje_e_ignora_futuras_e_concluidas(self):
        a = self.tarefa("a")
        self.tarefa("b", HOJE - timedelta(days=2))
        self.tarefa("futura", HOJE + timedelta(days=3))
        self.sql("UPDATE tasks SET completed_at = '2026-10-30 08:00:00' WHERE id = ?", (a,))
        self.assertEqual(badge.contagem(self.conn(), HOJE), 1)

    def test_rota_devolve_numero(self):
        self.tarefa("x")
        self.assertGreaterEqual(self.client.get("/api/badge").get_json()["n"], 0)

    def test_nunca_levanta(self):
        self.assertEqual(badge.contagem(None, HOJE), 0)


class AvisoCaraTest(_C):
    def test_reenvio_troca_de_cara_e_registra(self):
        t = self.tarefa("Academia", hora="18:00")
        c = self.conn()
        titulo, corpo = aviso_cara.variar(c, "tarefa_horario", t, f"tarefa_horario-{t}", "De novo · Academia", "Academia às 18:00", 1, AGORA)
        self.assertEqual(titulo, "De novo · Academia")
        self.assertTrue(corpo)
        n = c.execute("SELECT COUNT(*) n FROM aviso_cara_envios").fetchone()["n"]
        self.assertEqual(n, 1)

    def test_desligado_devolve_o_texto_original(self):
        c = self.conn()
        db.definir_configuracao(c, aviso_cara.CONFIG_LIGADO, "0")
        self.assertEqual(aviso_cara.variar(c, "tarefa_horario", 1, "t-1", "T", "corpo", 1, AGORA), ("T", "corpo"))

    def test_resolver_marca_feito_ou_toque_uma_vez(self):
        c = self.conn()
        aviso_cara.criar_tabela(c)
        aviso_cara.registrar_envio(c, "tag-1", "tarefa_horario", 1, "humor", 1, AGORA)
        self.assertEqual(aviso_cara.resolver(c, "tag-1", "feito", AGORA), 1)
        self.assertEqual(aviso_cara.resolver(c, "tag-1", "toque", AGORA), 0)

    def test_pesos_nunca_zeram_uma_cara(self):
        p = aviso_cara.pesos(self.conn())
        self.assertTrue(all(v >= aviso_cara.PISO_PESO for v in p.values()))
        self.assertEqual(set(p), set(aviso_cara.ROSTOS))


class CartoesManhaTest(_C):
    CTX = "Alex: preciso comprar o presente da minha mae, aniversario dela e dia 12 de novembro"

    def ia(self, evidencia):
        return lambda ctx, esq: {"cartoes": [{
            "titulo": "Presente da mãe", "texto": "Tu falou do presente.", "evidencia": evidencia, "rotulo": "Ver ideias",
            "tarefa": {"titulo": "Escolher presente da mãe", "quando": "hoje", "hora": "19:00"}}]}

    def test_sem_evidencia_literal_nao_vira_cartao(self):
        r = manha.validar(self.ia("isso nunca foi dito por ele")(None, None), self.CTX, [], [])
        self.assertEqual(r, [])

    def test_evidencia_literal_passa(self):
        r = manha.validar(self.ia("presente da minha mae")(None, None), self.CTX, [], [])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["tarefa_hora"], "19:00")

    def test_assunto_esquecido_ou_ja_em_tarefa_nao_volta(self):
        bruto = self.ia("presente da minha mae")(None, None)
        self.assertEqual(manha.validar(bruto, self.CTX, [{"chave": manha.chave_do_assunto("Presente da mãe"), "titulo": "x"}], []), [])
        self.assertEqual(manha.validar(bruto, self.CTX, [], ["Presente da mãe"]), [])

    def test_maximo_de_tres(self):
        bruto = {"cartoes": [{"titulo": f"Assunto {chr(65 + i)}{i}z", "texto": "t", "evidencia": "presente da minha mae", "rotulo": "ok"} for i in range(6)]}
        self.assertLessEqual(len(manha.validar(bruto, self.CTX, [], [])), 3)

    def test_preparar_grava_uma_vez_por_dia_e_ia_que_falha_nao_inventa(self):
        c = self.conn()
        with patch.object(manha, "contexto", return_value=self.CTX):
            self.assertIsNone(manha.preparar(c, HOJE, AGORA, pedir_ia=lambda *_: None))
            linhas = manha.preparar(c, HOJE, AGORA, pedir_ia=self.ia("presente da minha mae"))
            self.assertEqual(len(linhas), 1)
            self.assertIsNone(manha.preparar(c, HOJE, AGORA, pedir_ia=self.ia("presente da minha mae")))

    def test_resolver_cria_tarefa_depois_volta_amanha_esquecer_nao_puxa_mais(self):
        c = self.conn()
        with patch.object(manha, "contexto", return_value=self.CTX):
            l = manha.preparar(c, HOJE, AGORA, pedir_ia=self.ia("presente da minha mae"))
        cid = l[0]["id"]
        self.assertTrue(manha.resolver(c, cid, HOJE)["tarefa_id"])
        self.assertEqual(manha.estado_de(c, [cid])[cid], "feito")
        with patch.object(manha, "contexto", return_value=self.CTX):
            l2 = manha.preparar(c, HOJE + timedelta(days=1), AGORA + timedelta(days=1), pedir_ia=self.ia("presente da minha mae"))
        self.assertEqual(l2, [])  # ja virou tarefa: nao puxa de novo

    def test_card_e_chat(self):
        c = self.conn()
        with patch.object(manha, "contexto", return_value=self.CTX):
            l = manha.preparar(c, HOJE, AGORA, pedir_ia=self.ia("presente da minha mae"))
        k = manha.card(l, AGORA)
        self.assertEqual(k["type"], "cartoes_manha")
        self.assertEqual(k["data"]["cartoes"][0]["status"], "novo")
        self.assertIn("cartoes_manha", cards.TIPOS_CARD)

    def test_rotas_exigem_login_e_respondem(self):
        r = self.client.get("/api/manha/estado?ids=1,2")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/api/manha/9999/resolver").status_code, 404)


class SeEntaoTest(_C):
    def test_proposta_limpa_e_exige_acao(self):
        self.assertIsNone(se_entao.proposta("beber agua", ["acordar"], []))
        p = se_entao.proposta("beber agua", ["acordar", "lixo"], ["bebo um copo"])
        self.assertEqual([g["id"] for g in p["gatilhos"]], ["acordar"])

    def test_ativar_dispara_uma_vez_por_dia(self):
        c = self.conn()
        r, erro = se_entao.ativar(c, "agua", "acordar", None, "bebo um copo")
        self.assertIsNone(erro)
        avisos = []
        self.assertEqual(len(se_entao.disparar(c, "acordar", AGORA, avisar=lambda *a: avisos.append(a) or True)), 1)
        self.assertEqual(se_entao.disparar(c, "acordar", AGORA, avisar=lambda *a: True), [])
        self.assertEqual(len(avisos), 1)
        self.assertEqual(r["frase"], "Quando acordar, eu bebo um copo")

    def test_hora_exige_hhmm_e_limite_de_ativos(self):
        c = self.conn()
        self.assertIsNotNone(se_entao.ativar(c, "m", "hora", "25:99", "x")[1])
        for i in range(se_entao.MAX_ATIVOS):
            self.assertIsNone(se_entao.ativar(c, "m", "acordar", None, f"acao {i}")[1])
        self.assertIsNotNone(se_entao.ativar(c, "m", "acordar", None, "mais uma")[1])

    def test_mesmo_combinado_reativa_em_vez_de_duplicar(self):
        c = self.conn()
        a = se_entao.ativar(c, "m", "chegar_casa", None, "x")[0]
        se_entao.desativar(c, a["id"])
        b = se_entao.ativar(c, "m", "chegar_casa", None, "x")[0]
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(b["ativo"])

    def test_hora_dispara_no_tick_dentro_da_tolerancia(self):
        c = self.conn()
        se_entao.ativar(c, "m", "hora", "07:00", "tomo remedio")
        chamadas = []
        se_entao.verificar(c, AGORA, avisar=lambda *a: chamadas.append(a) or True)
        se_entao.verificar(c, AGORA, avisar=lambda *a: chamadas.append(a) or True)  # 2o tick no mesmo dia: nao repete
        self.assertEqual(len(chamadas), 1)
        se_entao.ativar(c, "m", "hora", "03:00", "x")
        se_entao.verificar(c, AGORA, avisar=lambda *a: chamadas.append(a) or True)  # passou das 3 h de tolerancia
        self.assertEqual(len(chamadas), 1)

    def test_rotas_ativar_listar_testar_desativar(self):
        r = self.client.post("/api/se-entao", json={"meta": "agua", "gatilho": "acordar", "acao": "bebo um copo"})
        self.assertEqual(r.status_code, 201)
        rid = r.get_json()["id"]
        self.assertEqual(len(self.client.get("/api/se-entao").get_json()["combinados"]), 1)
        self.assertEqual(self.client.post("/api/se-entao", json={"gatilho": "acordar"}).status_code, 400)
        with patch.object(se_entao, "_avisar", return_value=True):
            self.assertTrue(self.client.post(f"/api/se-entao/{rid}/testar").get_json()["enviado"])
        self.assertEqual(self.client.post(f"/api/se-entao/{rid}/desativar").status_code, 200)
        self.assertEqual(self.client.get("/api/se-entao").get_json()["combinados"], [])

    def test_push_acao_feito_responde_com_mensagem(self):
        rid = self.client.post("/api/se-entao", json={"meta": "agua", "gatilho": "acordar", "acao": "bebo"}).get_json()["id"]
        r = self.client.post("/api/push/acao", json={"tag": f"se_entao-{rid}", "acao": "feito"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["mensagem"], "Boa. +1 no teu dia.")

    def test_card_propor(self):
        k = cards.card_se_entao({"meta": "beber agua", "gatilhos": ["acordar"], "acoes": ["bebo um copo"]})
        self.assertEqual(k["type"], "se_entao")
        self.assertIsNone(cards.card_se_entao({"meta": "", "acoes": []}))


class BomDiaTest(_C):
    def test_ler_sono_formatos(self):
        self.assertEqual(bom_dia.ler_sono({"sono_horas": "6,5"})[0], 6.5)
        self.assertAlmostEqual(bom_dia.ler_sono({"sono_horas": "6h40"})[0], 6.67, places=2)
        h, d = bom_dia.ler_sono({"dormiu": "23:30", "acordou": "06:00"})
        self.assertEqual((h, d), (6.5, "23:30"))
        self.assertIsNone(bom_dia.ler_sono({"sono_horas": 40})[0])
        self.assertIsNone(bom_dia.ler_sono({"sono_horas": "abc"})[0])
        self.assertIsNone(bom_dia.ler_sono({})[0])

    def test_montar_fala_curta_com_horas_faladas(self):
        r = bom_dia.montar(agora=AGORA, corpo={"sono_horas": 6.67}, eventos=[], voos=[{"hora": "09:00"}], sem_hora=0,
                           tempo="SBJD: vento 8 kt", primeiro={"sair": "08:05"}, tarefa_primeira=None)
        self.assertEqual([l["rot"] for l in r["linhas"]], ["Sono", "Agenda", "Tempo", "Primeiro passo"])
        self.assertIn("6 horas e 40 minutos", r["fala"])
        self.assertIn("às 9h", r["fala"])
        self.assertIn("8h05", r["fala"])
        self.assertLessEqual(len(r["fala"]), bom_dia.MAX_FALA)
        self.assertEqual(r["linhas"][0]["trilho"], round(6.67 / 8, 3))

    def test_sem_sono_a_linha_some(self):
        r = bom_dia.montar(agora=AGORA, corpo={}, eventos=[], voos=[], sem_hora=2, tempo=None, primeiro=None, tarefa_primeira="Estudar")
        self.assertNotIn("Sono", [l["rot"] for l in r["linhas"]])
        self.assertIn("2 tarefas", r["linhas"][0]["valor"])

    def test_tempo_cai_pro_clima_se_metar_falha(self):
        def quebra(_):
            raise RuntimeError("rede")
        self.assertEqual(bom_dia.tempo_da_manha("X", "SBJD", buscar_metar=quebra, buscar_clima=lambda c: {"condicao": "céu limpo", "temperatura": 23.4}), "Céu limpo, 23°")
        self.assertIsNone(bom_dia.tempo_da_manha("X", None))

    def test_rota_salva_sono_publica_card_uma_vez(self):
        with patch("rotas.avisos_manha._clima_da_cidade", return_value=None):
            r = self.client.post("/api/atalho/bom-dia", json={"sono_horas": 7})
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            j = r.get_json()
            self.assertIn("fala", j)
            self.assertEqual(j["sono_horas"], 7)
            self.client.post("/api/atalho/bom-dia", json={"sono_horas": 7})
        self.assertEqual(self.sql("SELECT COUNT(*) n FROM chat_mensagens WHERE papel = 'assistant'")[0]["n"], 1)  # 1x por dia

    def test_rota_com_token_errado_recusa(self):
        with patch.dict(os.environ, {"PAINEL_ATALHOS_TOKEN": "segredo-c"}):
            self.assertEqual(self.client.post("/api/atalho/bom-dia", json={}, headers={"X-Webhook-Token": "x"}).status_code, 401)
            self.assertEqual(self.client.post("/api/atalho/carro", json={}, headers={"X-Webhook-Token": "x"}).status_code, 401)
            self.assertEqual(self.client.post("/api/atalho/gatilho", json={"evento": "acordar"}, headers={"X-Webhook-Token": "x"}).status_code, 401)

    def test_card(self):
        k = cards.card_bom_dia({"hora": "07:30", "linhas": [{"rot": "Sono", "valor": "7h"}]})
        self.assertEqual(k["type"], "bom_dia")
        self.assertIn("bom_dia", cards.CAMPOS_SENSIVEIS)


class _Maps:
    def __init__(self, tempos):
        self.tempos = tempos  # (origem, destino) -> minutos

    def tempo_de_viagem(self, o, d, partida=None):
        if (o, d) not in self.tempos:
            raise RuntimeError("sem rota")
        return {"duracao_minutos": self.tempos[(o, d)]}

    def posto_no_meio_do_caminho(self, o, d):
        return None

    def coordenada(self, x):
        return (-23.0, -46.0)

    def link_waze(self, coord, nome):
        return f"https://waze.com/ul?ll={coord[0]},{coord[1]}&q={nome}"


class CarroTest(_C):
    def test_sem_compromisso_com_lugar_nao_fala(self):
        self.tarefa("sem lugar", hora="18:30")
        self.assertFalse(carro.montar(self.conn(), HOJE, AGORA, "casa", _Maps({}))["tem"])

    def test_fala_hora_de_chegar_e_parada_ate_10_min(self):
        self.tarefa("Academia", hora="18:30", local="Rua A")
        self.tarefa("Pegar encomenda", local="Rua B")
        m = _Maps({("casa", "Rua A"): 20, ("casa", "Rua B"): 8, ("Rua B", "Rua A"): 17})
        r = carro.montar(self.conn(), HOJE, datetime(2026, 10, 30, 18, 0), "casa", m)
        self.assertTrue(r["tem"])
        self.assertEqual(r["parada"]["extra_min"], 5)
        self.assertEqual(r["chega_as"], "18:25")
        self.assertIn("No caminho", r["fala"])
        self.assertIn("encomenda", r["fala"].lower())
        self.assertIn("waze", r["waze"])

    def test_parada_que_atrasa_mais_de_10_min_nao_entra(self):
        self.tarefa("Academia", hora="18:30", local="Rua A")
        self.tarefa("Pegar encomenda", local="Rua B")
        m = _Maps({("casa", "Rua A"): 20, ("casa", "Rua B"): 15, ("Rua B", "Rua A"): 20})
        r = carro.montar(self.conn(), HOJE, datetime(2026, 10, 30, 18, 0), "casa", m)
        self.assertIsNone(r["parada"])
        self.assertNotIn("No caminho", r["fala"])

    def test_sem_maps_so_diz_compromisso_e_quanto_falta(self):
        self.tarefa("Academia", hora="18:30", local="Rua A")
        r = carro.montar(self.conn(), HOJE, datetime(2026, 10, 30, 18, 0), None, None)
        self.assertIn("faltam 30 minutos", r["fala"])
        self.assertIsNone(r["parada"])

    def test_parse_origem(self):
        self.assertEqual(carro.parse_origem({"lat": "-23,5", "lon": "-46.6"}), "-23.50000,-46.60000")
        self.assertEqual(carro.parse_origem({"localizacao": "-23.5, -46.6"}), "-23.50000,-46.60000")
        with patch.dict(os.environ, {"ENDERECO_CASA": "Rua Z"}):
            self.assertEqual(carro.parse_origem({"lat": "999", "lon": "1"}), "Rua Z")

    def test_card_tem_acao_waze(self):
        self.tarefa("Academia", hora="18:30", local="Rua A")
        r = carro.montar(self.conn(), HOJE, datetime(2026, 10, 30, 18, 0), "casa", _Maps({("casa", "Rua A"): 20}))
        k = carro.card(r, datetime(2026, 10, 30, 18, 0))
        self.assertEqual(k["type"], "carro")
        self.assertTrue(any(a["tipo"] == "abrir_link" for a in k["actions"]))


class ChatToolTest(_C):
    def test_ferramenta_propor_se_entao_gera_card(self):
        j, _ = self.chat([("propor_se_entao", {"meta": "beber agua", "gatilhos": ["acordar"], "acoes": ["bebo um copo"]})])
        tipos = [c["type"] for m in [j] for c in (m.get("cards") or [])]
        self.assertIn("se_entao", tipos)


if __name__ == "__main__":
    unittest.main()
