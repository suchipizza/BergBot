"""Hatch build hook: copy locales, brand dist/manifest and seed data into the wheel as `bergbot/_data`
so an installed package works without the repo (paths.data_root falls back to it)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "bergbot" / "_data"


class CustomBuildHook(BuildHookInterface):  # type: ignore[misc]
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel" or build_data.get("editable"):
            return
        if DATA.exists():
            shutil.rmtree(DATA)
        (DATA / "brand" / "mascot").mkdir(parents=True)
        shutil.copytree(ROOT / "locales", DATA / "locales")
        shutil.copytree(ROOT / "data", DATA / "data")
        shutil.copy(ROOT / "brand" / "mascot" / "manifest.json", DATA / "brand" / "mascot" / "manifest.json")
        if (ROOT / "brand" / "mascot" / "dist").exists():
            shutil.copytree(ROOT / "brand" / "mascot" / "dist", DATA / "brand" / "mascot" / "dist")
        build_data.setdefault("artifacts", []).append("src/bergbot/_data/**")

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        if DATA.exists():
            shutil.rmtree(DATA)
