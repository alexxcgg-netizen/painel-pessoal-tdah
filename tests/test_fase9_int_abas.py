"""Fase 9 (integracao das 4 abas): nenhum CSS/JS/template pode continuar preso a
uma aba que deixou de existir - o conteudo migrou e perdia o estilo (bug real:
icone de banco gigante em Financas porque bancos.css era escopado em #tab-bancos)."""
import glob
import re

ABAS_REMOVIDAS = re.compile(r"#tab-(bancos|painel|construtora|aviacao|assistente)\b")


def test_nada_aponta_para_aba_removida():
    arquivos = (
        glob.glob("static/css/**/*.css", recursive=True)
        + glob.glob("static/js/**/*.js", recursive=True)
        + glob.glob("templates/**/*.html", recursive=True)
    )
    achados = []
    for a in arquivos:
        texto = open(a, encoding="utf-8").read()
        texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
        texto = re.sub(r"(^|\s)//[^\n]*", "", texto)
        texto = re.sub(r"\{#.*?#\}|<!--.*?-->", "", texto, flags=re.S)
        if ABAS_REMOVIDAS.search(texto):
            achados.append(a)
    assert achados == []


def test_icone_de_titulo_de_secao_tem_tamanho():
    css = open("static/css/style.css", encoding="utf-8").read()
    bloco = re.search(r"\.secao-secundaria > svg \{([^}]*)\}", css)
    assert bloco and "width: 18px" in bloco.group(1) and "height: 18px" in bloco.group(1)
