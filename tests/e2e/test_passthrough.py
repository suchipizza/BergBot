"""Channel passthrough fixture: a generic bridge delivers text (+ file); Bergbot returns plain text + files."""

from __future__ import annotations

import json
from pathlib import Path

from bergbot.agent.session import Session
from bergbot.sources.http import FixtureFetcher

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _bridge_message(text: str, file: Path | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "channel": "whatsapp-bridge",
        "from": "+41790000000",
        "text": text,
        "file": str(file) if file else None,
    }


def test_bridge_roundtrip(tmp_path: Path) -> None:
    f = FixtureFetcher.from_files(
        FIX / "workflows" / "session.json.gz",
        *sorted((FIX / "workflows").glob("*-*.json.gz")),
        *sorted((FIX / "sources").glob("*.json")),
    )
    f.strict = False
    s = Session(workdir=tmp_path, fetcher=f, with_map=False)
    inbound = _bridge_message("Check if this hike is good on 2026-09-12", FIX / "gpx" / "rigi-stage.gpx")
    reply = s.handle(inbound["text"], attachment=Path(inbound["file"]))
    outbound = {
        "channel": inbound["channel"],
        "to": inbound["from"],
        "text": reply.message.text,
        "files": [str(p) for p in reply.files],
    }
    assert outbound["files"] and Path(outbound["files"][0]).suffix == ".html"
    assert "\n" in outbound["text"] and len(outbound["text"].splitlines()) <= 12
    assert "**" not in outbound["text"] and "<" not in outbound["text"]  # plain text, channel-agnostic
    json.dumps(outbound)  # serialisable for any bridge


def test_telegram_module_imports_without_token(tmp_path: Path) -> None:
    from bergbot.adapters.telegram import bot

    assert bot.stored_token() in (None, "") or isinstance(bot.stored_token(), str)
    d = bot.smoke_offline()
    assert d.exists()
