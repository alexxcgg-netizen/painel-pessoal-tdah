"""Fase 9 (C6/P-comp): "cards e blocos sem brilho, checkboxes no estilo novo,
LED removido" - guarda dos arquivos desta faixa:
- static/css/style.css (so os trechos mexidos por esta faixa - o arquivo e
  compartilhado, outras faixas ainda podem ter brilho pendente fora do
  escopo aqui listado)
- static/css/ui/componentes/*.css
- static/css/secoes/hoje/checkin.css
- static/css/secoes/gastos/conversa.css

Regra (dada pelo briefing): sombra de elevacao preta/neutra pode ficar;
qualquer sombra/halo/text-shadow com cor (acento, cor de aba, branco
brilhante) sai - "none" ou sombra preta neutra. Excecoes: o vidro da barra
de navegacao (#tabbar/.tab-btn, faixa a parte) e o anel de foco
(:focus-visible, spread sem blur).
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MEUS_ARQUIVOS = [
    RAIZ / "static" / "css" / "style.css",
    RAIZ / "static" / "css" / "secoes" / "hoje" / "checkin.css",
    RAIZ / "static" / "css" / "secoes" / "gastos" / "conversa.css",
    *sorted((RAIZ / "static" / "css" / "ui" / "componentes").glob("*.css")),
]

# Trechos de style.css que sao de OUTRAS faixas (topo/cabecalho, conversa do
# Hoje, tarefas, viagens, grupos "Vida" especificos - aviacao/painel/
# construtora fora dos componentes de card/badge genericos) e continuam com
# sombra colorida de proposito: nao sao desta faixa, entao o guard-rail so
# roda nos arquivos que sao 100% meus (componentes/checkin/conversa) e, no
# style.css compartilhado, so confere que os trechos que ESTA faixa mexeu
# (por nome de selector) ficaram limpos - ver relatorio final pra lista
# completa do que ficou de fora por pertencer a outra faixa.
SELETORES_STYLE_CSS_CORRIGIDOS = [
    ".stat-tile",
    ".stat-tile-valor",
    ".card-resultado",
    ".linha-do-tempo li.item.proximo",
    ".linha-do-tempo li.item.concluido::before",
    ".linha-do-tempo li.item.perdido::before",
    ".item-badge-proximo",
    ".visao-dia-periodo-dia-hoje",
    ".badge-planejado",
    "#importar-btn:hover",
    ".btn-conectar:hover",
    ".meta-progresso-barra.completa",
    ".meta-guardar button",
    ".badge-sucesso",
    ".card-btn-despertar.ativo",
    "@keyframes itemDestacado",
    ".card-bolinha",
    ".card-valor-grande",
    ".card-hora-grande",
    ".card-meta-valores strong",
    ".card-contrato .meta-progresso-barra",
    ".card-gota.cheia svg",
    ".card-dia-bloco",
    ".card-graf-barra",
    ".card-habito-dia.feito .card-habito-circ",
    ".avatar-usuario",
    "@keyframes itemDestacado",
]

# .item-destacado usa @keyframes itemDestacado (0%, 35% { box-shadow: ... }) -
# checado a parte, direto no texto bruto (o parser simples de _blocos_com_seletor
# nao amarra @keyframes ao seu bloco pai).



def _sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _blocos_com_seletor(css, contem):
    """Retorna (seletor_completo, corpo) de toda regra cujo seletor contenha a
    string `contem` (comparacao simples, nao regex) - inclui @media/@keyframes
    aninhados de forma aproximada (suficiente pra guard-rail de teste)."""
    css = _sem_comentarios(css)
    saida = []
    padrao = re.compile(r"([^{}]+)\{([^{}]*)\}")
    for m in padrao.finditer(css):
        seletor = m.group(1).strip()
        if contem in seletor:
            saida.append((seletor, m.group(2)))
    return saida


COR_TOKENS = (
    "var(--accent",
    "var(--cor-acento",
    "var(--cor-painel",
    "var(--cor-tarefas",
    "var(--cor-financeiro",
    "var(--cor-bancos",
    "var(--cor-construtora",
    "var(--cor-aviacao",
    "var(--cor-hoje",
    "var(--tile-cor",
    "var(--card-cor",
    "var(--glass-glow",
    "var(--bolinha",
    "rgba(66, 187, 145",  # verde solido usado como "glow" antigo
)


def _sombra_tem_cor(valor):
    return any(tok in valor for tok in COR_TOKENS)


def _e_excecao(seletor, valor):
    """#tabbar/.tab-btn (faixa a parte, nao mexemos) e anel de foco
    (:focus-visible com spread e sem blur, ex.: `0 0 0 2px COR`)."""
    if "#tabbar" in seletor or ".tab-btn" in seletor:
        return True
    if ":focus-visible" in seletor or ":focus" in seletor:
        # anel de foco: token --anel-foco (ja e so spread, sem blur, por
        # definicao em tokens.css) ou um "OFFSET-X OFFSET-Y BLUR SPREADpx"
        # escrito na mao com BLUR=0.
        if "var(--anel-foco" in valor:
            return True
        for termo in valor.split(","):
            termo = termo.strip()
            m = re.match(r"0\s+0\s+0\s+\d+(?:\.\d+)?px", termo)
            if not m:
                return False
        return True
    return False


class SemBrilhoNosMeusArquivosTestCase(unittest.TestCase):
    """static/css/ui/componentes/*.css, checkin.css e conversa.css sao 100%
    desta faixa - nenhuma sombra/halo colorido pode sobrar ali."""

    def test_sem_text_shadow_colorido(self):
        problemas = []
        for caminho in MEUS_ARQUIVOS:
            if caminho.name == "style.css":
                continue  # style.css e compartilhado, checado a parte abaixo
            texto = _sem_comentarios(caminho.read_text(encoding="utf-8"))
            for m in re.finditer(r"text-shadow\s*:\s*([^;]+);", texto):
                valor = m.group(1)
                if valor.strip() in ("none", "0"):
                    continue
                if _sombra_tem_cor(valor):
                    problemas.append(f"{caminho.name}: text-shadow: {valor}")
        self.assertEqual(problemas, [], "\n".join(problemas))

    def test_sem_box_shadow_ou_drop_shadow_colorido(self):
        problemas = []
        for caminho in MEUS_ARQUIVOS:
            if caminho.name == "style.css":
                continue
            texto = _sem_comentarios(caminho.read_text(encoding="utf-8"))
            for seletor, corpo in _blocos_com_seletor(texto, ""):
                for m in re.finditer(r"(box-shadow|filter)\s*:\s*([^;]+);", corpo):
                    prop, valor = m.group(1), m.group(2)
                    if prop == "filter" and "drop-shadow" not in valor:
                        continue
                    if valor.strip() == "none":
                        continue
                    if _sombra_tem_cor(valor) and not _e_excecao(seletor, valor):
                        problemas.append(f"{caminho.name} [{seletor.strip()[:60]}]: {prop}: {valor}")
        self.assertEqual(problemas, [], "\n".join(problemas))

    def test_glass_glow_nao_e_redeclarado_com_cor(self):
        for caminho in MEUS_ARQUIVOS:
            if caminho.name == "style.css":
                continue
            texto = _sem_comentarios(caminho.read_text(encoding="utf-8"))
            for m in re.finditer(r"--glass-glow\s*:\s*([^;]+);", texto):
                self.assertEqual(m.group(1).strip(), "none", f"{caminho.name}: --glass-glow nao esta none")


class SemBrilhoNosTrechosCorrigidosDoStyleCssTestCase(unittest.TestCase):
    """style.css e compartilhado entre faixas - so confere os seletores que
    esta faixa (C6/P-comp) mexeu (lista SELETORES_STYLE_CSS_CORRIGIDOS)."""

    def test_seletores_corrigidos_sem_sombra_colorida(self):
        style = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
        style_sem_comentarios = _sem_comentarios(style)
        problemas = []
        for alvo in SELETORES_STYLE_CSS_CORRIGIDOS:
            if alvo.startswith("@keyframes "):
                nome = alvo[len("@keyframes ") :]
                m = re.search(re.escape(alvo) + r"\s*\{(.*?)\}\s*\}", style_sem_comentarios, re.S)
                self.assertIsNotNone(m, f"{alvo} nao encontrado em style.css")
                corpo = m.group(1)
                for mm in re.finditer(r"box-shadow\s*:\s*([^;]+);", corpo):
                    valor = mm.group(1)
                    if valor.strip() != "none" and _sombra_tem_cor(valor):
                        problemas.append(f"style.css [{alvo}]: box-shadow: {valor}")
                continue
            blocos = _blocos_com_seletor(style_sem_comentarios, alvo)
            self.assertTrue(blocos, f"selecor nao encontrado em style.css: {alvo}")
            for seletor, corpo in blocos:
                for m in re.finditer(r"(text-shadow|box-shadow|filter)\s*:\s*([^;]+);", corpo):
                    prop, valor = m.group(1), m.group(2)
                    if prop == "filter" and "drop-shadow" not in valor:
                        continue
                    if valor.strip() == "none":
                        continue
                    if _sombra_tem_cor(valor) and not _e_excecao(seletor, valor):
                        problemas.append(f"style.css [{seletor.strip()[:60]}]: {prop}: {valor}")
        self.assertEqual(problemas, [], "\n".join(problemas))

    def test_glass_glow_local_stat_tile_e_card_resultado_e_none(self):
        style = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
        style_sem_comentarios = _sem_comentarios(style)
        for alvo in (".stat-tile", ".card-resultado"):
            blocos = _blocos_com_seletor(style_sem_comentarios, alvo)
            corpo = "".join(c for _, c in blocos)
            m = re.search(r"--glass-glow\s*:\s*([^;]+);", corpo)
            self.assertIsNotNone(m, f"{alvo}: --glass-glow nao encontrado")
            self.assertEqual(m.group(1).strip(), "none")


class CheckboxEstiloConversaTestCase(unittest.TestCase):
    """static/css/ui/componentes/campo.css - checkbox no estilo "Conversa":
    quadrado raio 6px, borda 1.5px --cor-texto-fraco, marcado = fundo
    --cor-acento, foco visivel (anel --cor-acento 2px sem blur), sem glow,
    area de toque >= 44px."""

    def setUp(self):
        self.css = (RAIZ / "static" / "css" / "ui" / "componentes" / "campo.css").read_text(
            encoding="utf-8"
        )
        self.sem_comentarios = _sem_comentarios(self.css)

    def _bloco(self, seletor):
        blocos = _blocos_com_seletor(self.sem_comentarios, seletor)
        self.assertTrue(blocos, f"selector nao encontrado: {seletor}")
        return blocos[0][1]

    def test_raio_6px(self):
        corpo = self._bloco(':where(input[type="checkbox"])')
        self.assertIn("border-radius: 6px", corpo)

    def test_borda_1_5px_cor_texto_fraco(self):
        corpo = self._bloco(':where(input[type="checkbox"])')
        self.assertRegex(corpo, r"border\s*:\s*1\.5px\s+solid\s+var\(--cor-texto-fraco\)")

    def test_marcado_usa_cor_acento(self):
        corpo = self._bloco(':where(input[type="checkbox"]):checked')
        self.assertIn("var(--cor-acento)", corpo)
        self.assertNotIn("box-shadow", corpo)  # sem glow no estado marcado

    def test_sem_glow_no_estado_repouso(self):
        corpo = self._bloco(':where(input[type="checkbox"])')
        m = re.search(r"box-shadow\s*:\s*([^;]+);", corpo)
        self.assertIsNotNone(m)
        self.assertFalse(_sombra_tem_cor(m.group(1)))

    def test_foco_visivel_anel_2px_sem_blur(self):
        corpo = self._bloco(':where(input[type="checkbox"]):focus-visible')
        m = re.search(r"box-shadow\s*:\s*([^;]+);", corpo)
        self.assertIsNotNone(m)
        valor = m.group(1).strip()
        self.assertRegex(valor, r"^0\s+0\s+0\s+2px\s+var\(--cor-acento\)$")

    def test_area_de_toque_44px_existe(self):
        # checkbox solto (fora de <label>) ganha ::after de 44px via --toque-min.
        self.assertIn('input[type="checkbox"]:not(label *)', self.sem_comentarios)
        self.assertIn("--toque-min", self.sem_comentarios)


class LedRemovidoTestCase(unittest.TestCase):
    """Nenhum indicador "LED" (classe .led/led-*) deve existir - e os pontos
    coloridos que faziam esse papel (linha do tempo, .card-bolinha) ficam
    chapados, sem glow."""

    def test_nenhuma_classe_led_no_css_js_ou_templates(self):
        padrao = re.compile(r"(?<![\w-])led(?![\w-])", re.IGNORECASE)
        problemas = []
        for base in ("static/css", "static/js", "templates"):
            for caminho in (RAIZ / base).rglob("*"):
                if caminho.suffix not in (".css", ".js", ".html"):
                    continue
                texto = caminho.read_text(encoding="utf-8", errors="ignore")
                # comentarios de doc (css/js /* */ e html <!-- -->) podem falar
                # sobre o LED que foi removido - nao contam como violacao.
                texto_sem_comentarios = re.sub(r"/\*.*?\*/|<!--.*?-->|//[^\n]*", "", texto, flags=re.S)
                # ignora "disabled"/"enabled"/"labelled" etc - so match de "led" isolado
                for m in padrao.finditer(texto_sem_comentarios):
                    inicio = max(0, m.start() - 12)
                    vizinhanca = texto_sem_comentarios[inicio : m.end() + 4]
                    if re.search(r"[a-zA-Z]led|led[a-zA-Z]", vizinhanca.replace(" ", "")):
                        continue
                    problemas.append(f"{caminho.relative_to(RAIZ)}: ...{vizinhanca}...")
        self.assertEqual(problemas, [], "\n".join(problemas))

    def test_linha_do_tempo_concluido_sem_glow(self):
        checkin = (RAIZ / "static" / "css" / "secoes" / "hoje" / "checkin.css").read_text(
            encoding="utf-8"
        )
        blocos = _blocos_com_seletor(_sem_comentarios(checkin), "li.item.concluido::before")
        self.assertTrue(blocos)
        corpo = blocos[0][1]
        self.assertIn("box-shadow: none", corpo)

    def test_card_bolinha_sem_glow(self):
        style = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
        blocos = _blocos_com_seletor(_sem_comentarios(style), ".card-bolinha")
        self.assertTrue(blocos)
        for seletor, corpo in blocos:
            if seletor.strip() != ".card-bolinha":
                continue
            self.assertIn("box-shadow: none", corpo)


class ListaUltimosDiasFinancasTestCase(unittest.TestCase):
    """static/css/secoes/gastos/conversa.css: lista leve, sem cartao por
    item (o cartao e so #fc-card-ultimos-dias), divisoria fina, valor com
    saida/entrada diferenciados por cor."""

    def setUp(self):
        self.css = (RAIZ / "static" / "css" / "secoes" / "gastos" / "conversa.css").read_text(
            encoding="utf-8"
        )
        self.sem_comentarios = _sem_comentarios(self.css)

    def test_item_sem_cartao_proprio(self):
        blocos = _blocos_com_seletor(self.sem_comentarios, "#lista-extrato-financas li.item")
        alvo = [c for s, c in blocos if s.strip() == "#fc-card-ultimos-dias #lista-extrato-financas li.item"]
        self.assertTrue(alvo, "regra da linha do item nao encontrada")
        corpo = alvo[0]
        self.assertIn("background: none", corpo)
        self.assertIn("border: none", corpo)
        self.assertIn("box-shadow: none", corpo)
        self.assertRegex(corpo, r"border-bottom\s*:\s*1px solid var\(--cor-borda\)")

    def test_descricao_15px_peso_500(self):
        blocos = _blocos_com_seletor(self.sem_comentarios, "#lista-extrato-financas .item-titulo")
        alvo = [c for s, c in blocos if "chip" not in s]
        self.assertTrue(alvo)
        corpo = alvo[0]
        self.assertIn("font-size: 15px", corpo)
        self.assertIn("font-weight: 500", corpo)

    def test_subtitulo_13px_fraco(self):
        blocos = _blocos_com_seletor(self.sem_comentarios, "#lista-extrato-financas .item-quando")
        self.assertTrue(blocos)
        corpo = blocos[0][1]
        self.assertIn("font-size: 13px", corpo)
        self.assertIn("var(--cor-texto-fraco)", corpo)

    def test_valor_tabular_nums_entrada_acento_saida_texto(self):
        blocos = _blocos_com_seletor(self.sem_comentarios, "#lista-extrato-financas .valor-mono")
        base = [c for s, c in blocos if s.strip().endswith(".valor-mono")]
        negativo = [c for s, c in blocos if "banco-saldo-negativo" in s]
        self.assertTrue(base and negativo)
        self.assertIn("tabular-nums", base[0])
        self.assertIn("var(--cor-acento)", base[0])
        self.assertIn("var(--cor-texto)", negativo[0])


if __name__ == "__main__":
    unittest.main()
