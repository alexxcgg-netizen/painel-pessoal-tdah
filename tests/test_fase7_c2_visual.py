"""Fase 7 (C2): guardas estaticas do polimento visual.

So le CSS/HTML do repo (sem app, sem banco): pega de volta os bugs que a C2 achou.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSS = RAIZ / "static" / "css"


def _sem_comentarios(texto):
    return re.sub(r"/\*.*?\*/", "", texto, flags=re.S)


def _regras(texto):
    """[(seletor, corpo)] de um CSS simples (sem aninhamento alem de @media)."""
    texto = _sem_comentarios(texto)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", texto)]


def _css_fase7():
    """Todos os CSS importados por fase7.css (camadas da Fase 7), na ordem."""
    indice = (CSS / "fase7.css").read_text(encoding="utf-8")
    return [CSS / p for p in re.findall(r'@import url\("([^"]+)"\)', indice)]


class AbaEscondidaTestCase(unittest.TestCase):
    """Bug real (C2): `#tab-painel { display: flex }` vence o `[hidden]` do navegador (id >
    atributo) e a aba aparecia embaixo de todas as outras. Todo `display` num container de
    aba precisa vir com `:not([hidden])`."""

    def test_nenhum_display_em_aba_sem_not_hidden(self):
        ruins = []
        for arq in _css_fase7():
            if not arq.exists():
                continue
            for seletor, corpo in _regras(arq.read_text(encoding="utf-8")):
                if not re.search(r"(^|[;\s])display\s*:", corpo):
                    continue
                for parte in seletor.split(","):
                    parte = parte.strip()
                    # o proprio container da aba (sem descendente depois)
                    if re.fullmatch(r"#tab-[a-z]+(\.[\w-]+)*", parte):
                        ruins.append(f"{arq.relative_to(RAIZ)}: {parte}")
        self.assertEqual(ruins, [], "use #tab-x:not([hidden]) ao definir display")


class ComponenteRespeitaHiddenTestCase(unittest.TestCase):
    """Bug real (C2, tambem achado pela V4/V6): `.card { display: flex }` vence o `[hidden]` do
    navegador, entao `el.hidden = true` nao escondia mais nada. Todo componente que define
    display numa classe simples precisa de uma guarda `.classe[hidden] { display: none }`."""

    def test_guarda_hidden_em_todo_display_de_componente(self):
        faltando = []
        for arq in sorted((CSS / "ui" / "componentes").glob("*.css")):
            regras = _regras(arq.read_text(encoding="utf-8"))
            guardas = set()
            for seletor, corpo in regras:
                if re.search(r"display\s*:\s*none", corpo):
                    for parte in seletor.split(","):
                        m = re.fullmatch(r"\s*(\.[\w-]+)\[hidden\]\s*", parte)
                        if m:
                            guardas.add(m.group(1))
            for seletor, corpo in regras:
                m = re.search(r"(^|;)\s*display\s*:\s*([\w-]+)", corpo)
                if not m or m.group(2) == "none":
                    continue
                for parte in seletor.split(","):
                    parte = parte.strip()
                    if re.fullmatch(r"\.[\w-]+", parte) and parte not in guardas:
                        faltando.append(f"{arq.name}: {parte}")
        self.assertEqual(faltando, [], "acrescente .classe[hidden] { display: none; }")


if __name__ == "__main__":
    unittest.main()
