"""Configuration deployment contracts; no real home, network, or Herdr session."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PortableSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="herdr setup ")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / "config with spaces"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.config))
        for key in ("HERDR_CONFIG_PATH", "HERDR_NVIM_CONFIG", "NVIM_APPNAME"):
            self.env.pop(key, None)
        tools = self.home / "tools"
        tools.mkdir()
        herdr = tools / "herdr"
        herdr.write_text("#!/bin/sh\nprintf '[keys]\\n# settings = \"prefix+s\"\\n[ui]\\n'\n")
        herdr.chmod(0o755)
        self.env["PATH"] = str(tools) + os.pathsep + os.defpath
        self.herdr = self.config / "herdr/config.toml"
        self.herdr.parent.mkdir(parents=True)

    def install(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "setup/install.py"), "--config-only", *args],
            env=self.env, capture_output=True, text=True,
        )

    def test_preserves_unrelated_settings_and_reinstall_is_idempotent(self):
        self.herdr.write_text('[keys]\nprefix = "ctrl+b"\nedit_scrollback = "prefix+e"\n'
                              'cycle_pane_next = ["prefix+o", "prefix+tab"]\n'
                              '[theme]\nname = "catppuccin"\n')
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        contents = self.herdr.read_bytes()
        data = tomllib.loads(contents.decode())
        self.assertEqual(data["keys"]["edit_scrollback"], "prefix+e")
        self.assertEqual(data["keys"]["cycle_pane_next"], ["prefix+o", "prefix+tab"])
        self.assertEqual(data["theme"]["name"], "catppuccin")
        self.assertEqual({a["command"] for a in data["keys"]["command"]},
                         {"chmarax.herdr-nvim.toggle", "chmarax.herdr-nvim.pick-file"})
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.herdr.read_bytes(), contents)

    def test_conflicting_key_leaves_existing_config_untouched(self):
        original = '[keys]\nedit_scrollback = "prefix+ctrl+e"\n'
        self.herdr.write_text(original)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.herdr.read_text(), original)
        self.assertFalse((self.config / "herdr-editor").exists())

    def test_malformed_config_does_not_install_partial_profile(self):
        original = '[keys\nbroken'
        self.herdr.write_text(original)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.herdr.read_text(), original)
        self.assertFalse((self.config / "herdr-editor").exists())

    def test_dry_run_does_not_write_configuration(self):
        self.herdr.write_text('[theme]\nname = "catppuccin"\n')
        before = self.herdr.read_bytes()
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.herdr.read_bytes(), before)
        self.assertFalse((self.config / "herdr-editor").exists())

    def test_commented_herdr_defaults_are_reserved(self):
        result = self.install("--toggle-key", "prefix+s")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Key collision", result.stderr)
        self.assertFalse((self.config / "herdr-editor").exists())

    def test_modified_profile_requires_explicit_replacement_with_backup(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        profile = self.config / "herdr-editor"
        edited = profile / "lua/config/options.lua"
        mine = edited.read_bytes() + b"\n-- my local customization\n"
        edited.write_bytes(mine)
        extra = profile / "personal.txt"
        extra.write_text("keep this")
        refused = self.install()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("User-modified profile file", refused.stderr)
        self.assertEqual(edited.read_bytes(), mine)
        replaced = self.install("--replace-profile")
        self.assertEqual(replaced.returncode, 0, replaced.stdout + replaced.stderr)
        self.assertTrue(any(path.read_bytes() == mine for path in edited.parent.glob("options.lua.bak.*")))
        self.assertEqual(extra.read_text(), "keep this")


    def test_invalid_editor_executable_is_rejected_before_deployment(self):
        plugin = self.config / "herdr-nvim/config.toml"
        plugin.parent.mkdir()
        original = '[sidebar]\nnvim_bin = 42\n'
        plugin.write_text(original)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sidebar.nvim_bin", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(plugin.read_text(), original)
        self.assertFalse((self.config / "herdr-editor").exists())


if __name__ == "__main__":
    unittest.main()
