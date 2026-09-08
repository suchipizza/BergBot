"""`bergbot chat`: a REPL over `agent.Session`. Slash commands map to intents; files land in the workdir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from bergbot.agent.llm import LLM
from bergbot.agent.session import Session
from bergbot.conversation.suggestions import suggest
from bergbot.i18n import load, normalise_lang

SLASH = {
    "/find": "find",
    "/around": "around",
    "/audit": "audit",
    "/check": "check",
    "/gpx": "gpx",
    "/help": "help",
}


def run_repl(lang: str | None = None, workdir: Path = Path(".")) -> None:
    workdir = workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    llm = LLM()
    session = Session(
        workdir=workdir,
        lang=normalise_lang(lang) if lang else None,
        llm=llm,
        offline=bool(os.environ.get("BERGBOT_OFFLINE") not in (None, "", "0")),
    )
    L = load(normalise_lang(lang or "en"))
    print(L.list("playful.greetings")[0])
    if not llm.available:
        print("(no ANTHROPIC_API_KEY — deterministic mode: no web verification, no free chat)")
    for i, s in enumerate(suggest(normalise_lang(lang or "en")), 1):
        print(f"{i}. {s.text}")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text in ("/quit", "/exit", "quit", "exit"):
            return
        attachment: Path | None = None
        for cmd, intent in SLASH.items():
            if text.startswith(cmd):
                rest = text[len(cmd) :].strip()
                if intent == "audit" and rest:
                    attachment = Path(rest)
                    text = rest
                elif intent == "gpx":
                    text = "send me the gpx " + rest
                elif intent == "help":
                    text = "help"
                else:
                    text = rest or text
                break
        reply = session.handle(
            text, attachment=attachment, progress=lambda s: print(f"  … {s}", file=sys.stderr)
        )
        print(reply.message.text)
        if reply.files:
            print(
                load(reply.message.lang).t(
                    "ui.message.files_line", paths=", ".join(str(p) for p in reply.files)
                )
            )
