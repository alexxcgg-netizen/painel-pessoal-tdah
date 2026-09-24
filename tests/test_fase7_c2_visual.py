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


if __name__ == "__main__":
    unittest.main()
