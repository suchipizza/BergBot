"""Regenerate docs/screenshots/*.png with headless Chrome: the report on a phone, a chat reply, and the install /
connect step images. Chat and step images are HTML renders of real command output; Telegram step images are
placeholders until the founder replaces them with real phone screenshots (FOUNDER INPUT)."""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
CHROME = next(
    (
        p
        for p in [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            shutil.which("google-chrome") or "",
            shutil.which("chromium") or "",
        ]
        if p and Path(p).exists()
    ),
    None,
)

CSS = "body{margin:0;background:#e8ecf1;font:15px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:18px}"
CHAT = """<div style="max-width:440px;margin:0 auto;background:#fff;border-radius:18px;padding:14px;box-shadow:0 2px 12px rgba(0,0,0,.08)">
<div style="display:flex;align-items:center;gap:10px;border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:10px"><img src="{avatar}" style="width:36px;height:36px;border-radius:50%;object-fit:cover"><div><b>Bergbot</b><br><span style="color:#888;font-size:.8rem">bot</span></div></div>
<div style="display:flex;justify-content:flex-end"><div style="background:#dcf8c6;border-radius:14px 14px 2px 14px;padding:8px 12px;max-width:85%">{prompt}</div></div>
<div style="display:flex;margin-top:8px"><div style="background:#f1f3f5;border-radius:14px 14px 14px 2px;padding:10px 12px;max-width:92%;white-space:pre-wrap;font-size:.92rem">{reply}</div></div>
<div style="display:flex;margin-top:8px"><div style="border:1px solid #ddd;border-radius:12px;padding:8px 12px;font-size:.85rem">📎 {file}</div></div>
<div style="display:flex;gap:8px;margin-top:10px">{buttons}</div></div>"""
TERM = """<div style="max-width:720px;margin:0 auto;background:#0f172a;color:#e5eaf0;border-radius:12px;padding:16px 18px;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap"><span style="color:#94a3b8">{title}</span>\n\n{body}</div>"""
PLACEHOLDER = """<div style="max-width:360px;margin:0 auto;background:#fff;border-radius:18px;padding:18px;text-align:center;color:#556"><div style="font-size:2rem">📱</div><b>{title}</b><p style="font-size:.9rem">{body}</p><p style="font-size:.75rem;color:#999">placeholder — replace with a real screenshot</p></div>"""


def shot(html_body: str, name: str, width: int, height: int) -> None:
    if CHROME is None:
        print("no Chrome found; skipping", name)
        return
    tmp = OUT / f"_{name}.html"
    tmp.write_text(f"<!doctype html><meta charset=utf-8><style>{CSS}</style>{html_body}", encoding="utf-8")
    subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={OUT / name}",
            f"file://{tmp}",
        ],
        check=False,
        capture_output=True,
    )
    tmp.unlink(missing_ok=True)
    print("wrote", OUT / name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    avatar = (
        (ROOT / "brand" / "mascot" / "dist" / "default.datauri.txt").read_text().strip()
        if (ROOT / "brand" / "mascot" / "dist" / "default.datauri.txt").exists()
        else ""
    )
    # 1) report on a phone (500 px is Chrome's minimum headless width; crop to 390 visually via zoom)
    report = ROOT / "examples" / "gpx-audit" / "report.html"
    if CHROME and report.exists():
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=500,1400",
                "--force-device-scale-factor=1",
                f"--screenshot={OUT / 'report-phone.png'}",
                f"file://{report}",
            ],
            check=False,
            capture_output=True,
        )
        print("wrote", OUT / "report-phone.png")
    # 2) chat bubble from the brunnen-around example (EN)
    msg = (ROOT / "examples" / "brunnen-around" / "message.txt").read_text(encoding="utf-8")
    turns = [t for t in msg.split("\n> ") if t.strip()]
    sel = next((t for t in turns if t.startswith("1\n")), turns[0])
    prompt, reply = "1", sel.split("\n", 1)[1].strip()
    first = turns[0].lstrip("> ").split("\n", 1)
    body = CHAT.format(
        avatar=avatar,
        prompt=html.escape(first[0]),
        reply=html.escape(first[1].strip()),
        file="",
        buttons="".join(
            f'<span style="border:1px solid #cbd5e1;border-radius:8px;padding:4px 10px;font-size:.85rem">{b}</span>'
            for b in ("1", "2", "3")
        ),
    )
    body += CHAT.format(
        avatar=avatar,
        prompt=html.escape(prompt),
        reply=html.escape(reply),
        file=next(
            (
                ln.split(": ", 1)[1]
                for ln in reply.splitlines()
                if ln.startswith(("Report:", "Rapport", "Bericht", "Rapporto"))
            ),
            "bergbot-report.html",
        ),
        buttons="".join(
            f'<span style="border:1px solid #cbd5e1;border-radius:8px;padding:4px 10px;font-size:.85rem">{b}</span>'
            for b in ("GPX", "➕")
        ),
    )
    shot(body, "chat.png", 520, 1180)
    # 3) install steps (terminal renders of real output)
    shot(
        TERM.format(
            title="Claude Code",
            body=html.escape(
                "> /plugin marketplace add suchipizza/BergBot\n\nCloning repository: https://github.com/suchipizza/BergBot.git\nClone complete, validating marketplace…\n✔ Successfully added marketplace: bergbot"
            ),
        ),
        "install-cc-1.png",
        760,
        260,
    )
    shot(
        TERM.format(
            title="Claude Code",
            body=html.escape(
                '> /plugin install bergbot\n\nInstalling plugin "bergbot@bergbot"...\n✔ Successfully installed plugin: bergbot@bergbot (scope: user)\n  Skills: audit · find · around · check · export · media · help'
            ),
        ),
        "install-cc-2.png",
        760,
        260,
    )
    shot(
        TERM.format(
            title="Terminal",
            body=html.escape(
                "$ pipx install bergbot\n  installed package bergbot 0.1.0, installed using Python 3.12\n  These apps are now globally available\n    - bergbot\n$ bergbot doctor\nBergbot doctor v0.1.0\n  [  ok] ch.geoadmin            [  ok] ch.closures          [  ok] ch.meteoswiss\n  [  ok] ch.bafu.quiet_zones    [  ok] ch.army              [  ok] ch.transport …"
            ),
        ),
        "install-cc-3.png",
        760,
        300,
    )
    shot(
        PLACEHOLDER.format(
            title="@BotFather → /newbot", body="Choose a name and a username, copy the token."
        ),
        "connect-tg-1.png",
        420,
        300,
    )
    shot(
        TERM.format(
            title="Terminal",
            body=html.escape(
                '$ pipx install "bergbot[all]"\n$ bergbot connect telegram\nPaste the token from @BotFather (it looks like 123456:ABC-DEF…). It is stored locally in ~/.bergbot.\ntoken> ••••••••••••\nBergbot Telegram bot starting (long polling). Files go to ~/.bergbot/telegram. Ctrl-C to stop.'
            ),
        ),
        "connect-tg-2.png",
        760,
        260,
    )
    shot(
        PLACEHOLDER.format(
            title="Your bot in Telegram",
            body="Write a place, a wish, or send a GPX. Tap a suggestion to start.",
        ),
        "connect-tg-3.png",
        420,
        300,
    )


if __name__ == "__main__":
    sys.exit(main())
