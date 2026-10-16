import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "install-launch-agent.sh"


@unittest.skipUnless((ROOT / ".venv" / "bin" / "python").exists(), "スクリプトは .venv の Python で引数を確かめる")
class InstallScriptTest(unittest.TestCase):
    """自動起動の登録スクリプト。DRY_RUN=1 で動かす（作った plist を出して終わり、登録しない）。"""

    def install(self, *options):
        return subprocess.run([str(SCRIPT), *options], cwd=ROOT, env={**os.environ, "DRY_RUN": "1"},
                              capture_output=True, text=True, timeout=60)

    def test_help_only_prints_the_usage_and_does_not_register(self):
        # 2026-10-16 に --help が常駐として登録され、利用枠の画面が一晩止まった
        for options in (["--help"], ["-h"], ["--he"], ["--monitor", "--help"], ["--local", "-h"]):
            with self.subTest(options=options):
                result = self.install(*options)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertNotIn("<plist", result.stdout)
                self.assertIn("登録は変えていません", result.stderr)

    def test_wrong_options_stop_before_registering(self):
        result = self.install("--brightness", "200")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("<plist", result.stdout)

    def test_options_are_written_into_the_plist(self):
        result = self.install("--device", "5.2", "--brightness", "40")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<string>run</string>\n    <string>--device</string>\n    <string>5.2</string>\n"
                      "    <string>--brightness</string>\n    <string>40</string>", result.stdout)


if __name__ == "__main__":
    unittest.main()
