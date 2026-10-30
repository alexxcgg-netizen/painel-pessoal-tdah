"""scripts/ipa_com_endereco.py: grava o endereco na copia local do .ipa."""

import importlib.util
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ipa_com_endereco", Path(__file__).resolve().parent.parent / "scripts" / "ipa_com_endereco.py")
ipa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ipa)


class IpaComEnderecoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.entrada = self.dir / "a.ipa"
        with zipfile.ZipFile(self.entrada, "w") as z:
            exe = zipfile.ZipInfo("Payload/Painel.app/Painel")
            exe.external_attr = (stat.S_IFREG | 0o755) << 16
            z.writestr(exe, b"binario")
            z.writestr("Payload/Painel.app/Info.plist", b"plist")

    def test_grava_e_preserva_o_resto(self):
        saida = self.dir / "b.ipa"
        ipa.gravar_endereco(self.entrada, saida, "https://painel.exemplo.net")
        with zipfile.ZipFile(saida) as z:
            self.assertEqual(z.read(ipa.ARQUIVO).decode().strip(), "https://painel.exemplo.net")
            self.assertEqual(z.read("Payload/Painel.app/Painel"), b"binario")
            modo = z.getinfo("Payload/Painel.app/Painel").external_attr >> 16
            self.assertTrue(modo & 0o100, "o executavel perdeu a permissao")

    def test_trocar_o_endereco_nao_duplica(self):
        b, c = self.dir / "b.ipa", self.dir / "c.ipa"
        ipa.gravar_endereco(self.entrada, b, "https://um.exemplo.net")
        ipa.gravar_endereco(b, c, "https://dois.exemplo.net")
        with zipfile.ZipFile(c) as z:
            self.assertEqual(z.namelist().count(ipa.ARQUIVO), 1)
            self.assertIn("dois", z.read(ipa.ARQUIVO).decode())

    def test_recusa_endereco_ruim_e_sobrescrever_a_entrada(self):
        for ruim in ("", "painel", "ftp://x", "https://"):
            with self.subTest(ruim=ruim), self.assertRaises(ValueError):
                ipa.gravar_endereco(self.entrada, self.dir / "b.ipa", ruim)
        with self.assertRaises(ValueError):
            ipa.gravar_endereco(self.entrada, self.entrada, "https://x.net")

    def test_acha_no_tailscale_a_porta_do_painel(self):
        saida = (
            "https://pc.exemplo.ts.net (tailnet only)\n|-- / proxy https+insecure://127.0.0.1:5000\n\n"
            "https://pc.exemplo.ts.net:8443 (tailnet only)\n|-- / proxy http://127.0.0.1:5001\n"
        )
        self.assertEqual(ipa.endereco_do_serve(saida), "https://pc.exemplo.ts.net:8443")
        self.assertEqual(ipa.endereco_do_serve(saida, 9999), "")
        self.assertEqual(ipa.endereco_do_serve(""), "")

    def test_le_o_endereco_do_env(self):
        env = self.dir / ".env"
        env.write_text('OUTRA=1\nAPP_URL_PUBLICA="https://painel.exemplo.net/"\n', encoding="utf-8")
        self.assertEqual(ipa.endereco_do_env(env), "https://painel.exemplo.net")


if __name__ == "__main__":
    unittest.main()
