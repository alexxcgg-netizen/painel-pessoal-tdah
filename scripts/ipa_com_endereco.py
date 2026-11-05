"""Deixa o .ipa pronto pra este iPhone: grava o endereco do painel dentro dele (2026-10-30).

O build do GitHub nao tem endereco nenhum (o repositorio nao guarda isso). Aqui, no PC, o endereco
(APP_URL_PUBLICA do .env ou, sem ele, o `tailscale serve` que aponta pra porta do painel) vai pra um
arquivinho dentro do .app e o app abre direto no painel
(`Ajustes.aplicarEnderecoDeFabrica`). So o endereco: o token o app busca sozinho depois do PIN.
2026-11-05: o mesmo arquivinho vai tambem dentro da extensao dos widgets (`PainelConfig.enderecoDeFabrica`),
porque a assinatura gratis corta o App Group e o widget nao enxerga o que o app guardou. O token do widget
chega pelo pareamento por codigo (rotas/widget_ios.py) - nunca vai dentro do .ipa.
O Sideloadly re-assina tudo na instalacao, entao mexer no pacote aqui nao quebra a assinatura.

Uso: .venv/Scripts/python.exe scripts/ipa_com_endereco.py [entrada.ipa] [saida.ipa]
"""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = "Payload/Painel.app/Painel-endereco.txt"
EXTENSAO = "Payload/Painel.app/PlugIns/PainelWidgetExtension.appex/"
ARQUIVO_WIDGET = EXTENSAO + "Painel-endereco.txt"
PORTA_DO_PAINEL = 5001


def endereco_do_env(caminho: Path) -> str:
    for linha in caminho.read_text(encoding="utf-8", errors="ignore").splitlines():
        if linha.startswith("APP_URL_PUBLICA="):
            return linha.split("=", 1)[1].strip().strip("\"'").rstrip("/")
    return ""


def endereco_do_serve(saida_serve: str, porta: int = PORTA_DO_PAINEL) -> str:
    """Do texto de `tailscale serve status`, o https que faz proxy pra porta do painel."""
    atual = ""
    for linha in saida_serve.splitlines():
        achou = re.match(r"\s*(https://\S+)", linha)
        if achou:
            atual = achou.group(1).rstrip("/")
        elif atual and re.search(rf"proxy \S+:{porta}\b", linha):
            return atual
    return ""


def endereco_do_tailscale() -> str:
    for exe in ("tailscale", r"C:\Program Files\Tailscale\tailscale.exe"):
        try:
            r = subprocess.run([exe, "serve", "status"], capture_output=True, text=True, timeout=15)
        except OSError:
            continue
        if r.stdout:
            return endereco_do_serve(r.stdout)
    return ""


def gravar_endereco(entrada: Path, saida: Path, endereco: str) -> None:
    partes = urlparse(endereco)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ValueError("endereco invalido")
    if entrada.resolve() == saida.resolve():
        raise ValueError("entrada e saida iguais")
    with zipfile.ZipFile(entrada) as ori, zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
        tem_widget = False
        for item in ori.infolist():
            tem_widget = tem_widget or item.filename.startswith(EXTENSAO)
            if item.filename not in (ARQUIVO, ARQUIVO_WIDGET):
                novo.writestr(item, ori.read(item.filename))  # item leva junto as permissoes (executavel)
        novo.writestr(ARQUIVO, endereco + "\n")
        if tem_widget:
            novo.writestr(ARQUIVO_WIDGET, endereco + "\n")


if __name__ == "__main__":
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "app-ios" / "Painel.ipa"
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "Downloads" / "Painel.ipa"
    gravar_endereco(entrada, saida, endereco_do_env(RAIZ / ".env") or endereco_do_tailscale())
    print(f"pronto: {saida}")
