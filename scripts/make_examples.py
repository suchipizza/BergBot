"""Regenerate examples/*: real, regenerable outputs (message.txt, report.html, route.gpx, audit.json).
Run: make examples  (network; ~2 min). Each example folder has a prompt.txt describing what was asked."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bergbot.agent.session import Session  # noqa: E402
from bergbot.core.workflows import default_date  # noqa: E402

EXAMPLES = {
    "glarus-easy-hike": {
        "lang": "de",
        "steps": [
            "Leichte Wanderung im Kanton Glarus am {date}, max. 500 m Aufstieg, mit dem Zug zurück",
            "1",
            "Schick mir das GPX",
        ],
    },
    "brunnen-around": {
        "lang": "en",
        "steps": ["Can you find a hike near Brunnen SZ on {date}?", "1", "send me the gpx"],
    },
    "gpx-audit": {
        "lang": "fr",
        "steps": [
            ("Vérifie si cette rando est bien le {date}", ROOT / "examples" / "gpx-audit" / "route.gpx"),
            "Envoie-moi le GPX",
        ],
    },
    "dog-day": {
        "lang": "it",
        "steps": [
            "Escursione con il mio cane vicino a Urnerboden il {date}, max 600 m di dislivello",
            "1",
            "Inviami il GPX",
        ],
    },
}


def main() -> None:
    date = default_date()
    for name, spec in EXAMPLES.items():
        folder = ROOT / "examples" / name
        keep = folder / "route.gpx" if name == "gpx-audit" else None
        for p in folder.glob("*"):
            if p != keep and p.name != "README.md":
                p.unlink() if p.is_file() else shutil.rmtree(p)
        work = folder / "_work"
        work.mkdir(exist_ok=True)
        s = Session(workdir=work, lang=spec["lang"])  # type: ignore[arg-type]
        transcript: list[str] = []
        for step in spec["steps"]:
            text, att = step if isinstance(step, tuple) else (step, None)
            text = text.format(date=date)
            r = s.handle(text, attachment=att)
            transcript.append(f"> {text}\n\n{r.message.text}\n")
            for f in r.files:
                shutil.copy(
                    f,
                    folder
                    / (
                        "report.html"
                        if f.suffix == ".html"
                        else "route.gpx"
                        if f.suffix == ".gpx"
                        else f.name
                    ),
                )
        if s.audit is not None:
            (folder / "audit.json").write_text(
                s.audit.model_dump_json(by_alias=True, indent=1), encoding="utf-8"
            )
        (folder / "message.txt").write_text("\n".join(transcript), encoding="utf-8")
        (folder / "prompt.txt").write_text(
            "\n".join(t if isinstance(t, str) else t[0] for t in spec["steps"]).format(date=date) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(work, ignore_errors=True)
        print(name, "→", sorted(p.name for p in folder.iterdir()))


if __name__ == "__main__":
    main()
