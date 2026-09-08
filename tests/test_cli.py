from __future__ import annotations

import subprocess
import sys


def test_version_and_help() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "bergbot.cli", "--version"], capture_output=True, text=True, check=False
    )
    assert out.returncode == 0 and out.stdout.startswith("bergbot 0.")
    out = subprocess.run(
        [sys.executable, "-m", "bergbot.cli", "--help"], capture_output=True, text=True, check=False
    )
    assert out.returncode == 0 and "audit" in out.stdout


def test_suggest_four_languages() -> None:
    for lang in ("en", "fr", "de", "it"):
        out = subprocess.run(
            [sys.executable, "-m", "bergbot.cli", "suggest", "--lang", lang, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert out.returncode == 0 and out.stdout.count('"text"') == 4
