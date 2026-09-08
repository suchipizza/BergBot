"""Telegram adapter (FR-I2, M7): local long-polling bot over `agent.Session`, one session per chat.

- `bergbot connect telegram` prompts for the BotFather token, stores it in ~/.bergbot/telegram.token, sends a
  test message to the bot owner on first /start and starts polling. Nothing is hosted.
- Suggestions → reply keyboard; after an audit → inline buttons GPX / another / photos (photos only when the
  register allows it); GPX and HTML are sent as documents; a shared location runs `around`.
- Progress edits every ≤ 20 s on a status message while a workflow runs.
- Register rules are the renderer's: no mascot sticker, no extra emoji in serious messages.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from bergbot.agent.llm import LLM
from bergbot.agent.session import Reply, Session
from bergbot.conversation.suggestions import suggest
from bergbot.core.domain import Intent, Register
from bergbot.i18n import load, normalise_lang
from bergbot.paths import brand_dir, user_config_dir

TOKEN_FILE = user_config_dir() / "telegram.token"


def stored_token() -> str | None:
    env = os.environ.get("BERGBOT_TELEGRAM_TOKEN")
    if env:
        return env
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip() or None
    return None


def store_token(token: str) -> Path:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip() + "\n", encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return TOKEN_FILE


def connect_and_run(token: str | None = None, workdir: Path | None = None) -> None:
    """Entry point of `bergbot connect telegram`."""
    token = token or stored_token()
    if not token:
        print(
            "Paste the token from @BotFather (it looks like 123456:ABC-DEF…). It is stored locally in ~/.bergbot."
        )
        token = input("token> ").strip()
    if not token:
        raise SystemExit("no token")
    store_token(token)
    try:
        from telegram.ext import Application  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise SystemExit("python-telegram-bot is not installed: pip install 'bergbot[telegram]'") from e
    work = (workdir or user_config_dir() / "telegram").resolve()
    work.mkdir(parents=True, exist_ok=True)
    print(f"Bergbot Telegram bot starting (long polling). Files go to {work}. Ctrl-C to stop.")
    asyncio.run(_run(token, work))


async def _run(token: str, work: Path) -> None:
    from telegram import Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

    app = Application.builder().token(token).build()
    bot = BergbotTelegram(work)
    app.add_handler(CommandHandler(["start", "help"], bot.on_help))
    app.add_handler(CommandHandler(["find", "around", "audit", "check", "gpx"], bot.on_command))
    app.add_handler(CallbackQueryHandler(bot.on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.on_document))
    app.add_handler(MessageHandler(filters.LOCATION, bot.on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.on_text))
    await _set_avatar_hint()
    async with app:
        await app.start()
        assert app.updater is not None
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await app.updater.stop()
            await app.stop()


async def _set_avatar_hint() -> None:
    avatar = brand_dir() / "dist" / "avatar.png"
    if avatar.exists():
        print(f"Tip: set the bot avatar in @BotFather → /setuserpic with {avatar}")


class BergbotTelegram:
    def __init__(self, work: Path) -> None:
        self.work = work
        self.llm = LLM()
        self.sessions: dict[int, Session] = {}

    def session(self, chat_id: int, lang_code: str | None) -> Session:
        s = self.sessions.get(chat_id)
        if s is None:
            d = self.work / str(chat_id)
            d.mkdir(parents=True, exist_ok=True)
            s = Session(workdir=d, llm=self.llm)
            s.last_lang = normalise_lang(lang_code)
            self.sessions[chat_id] = s
        return s

    # ----- handlers -----
    async def on_help(self, update: Any, context: Any) -> None:
        chat = update.effective_chat
        lang = normalise_lang(getattr(update.effective_user, "language_code", None))
        s = self.session(chat.id, lang)
        reply = s.handle("help")
        await self._send(update, reply, keyboard=[x.text for x in suggest(reply.message.lang)])

    async def on_command(self, update: Any, context: Any) -> None:
        text = (update.message.text or "").strip()
        cmd, _, rest = text.partition(" ")
        mapping = {
            "/gpx": "send me the gpx",
            "/audit": rest or "audit",
            "/check": rest,
            "/find": rest,
            "/around": rest,
        }
        await self._handle_text(update, mapping.get(cmd.split("@")[0], rest) or "help")

    async def on_text(self, update: Any, context: Any) -> None:
        await self._handle_text(update, update.message.text or "")

    async def on_button(self, update: Any, context: Any) -> None:
        q = update.callback_query
        await q.answer()
        data = q.data or ""
        text = {
            "gpx": "send me the gpx",
            "another": "another suggestion",
            "photos": "photos of this route",
        }.get(data, data)
        await self._handle_text(update, text)

    async def on_document(self, update: Any, context: Any) -> None:
        doc = update.message.document
        name = (doc.file_name or "route.gpx").lower()
        if not name.endswith((".gpx", ".kml", ".geojson")):
            await self._handle_text(update, update.message.caption or "")
            return
        chat = update.effective_chat
        s = self.session(chat.id, getattr(update.effective_user, "language_code", None))
        target = s.workdir / Path(name).name
        f = await doc.get_file()
        await f.download_to_drive(custom_path=str(target))
        await self._handle_text(update, update.message.caption or name, attachment=target)

    async def on_location(self, update: Any, context: Any) -> None:
        loc = update.message.location
        await self._handle_text(update, f"{loc.latitude:.5f}, {loc.longitude:.5f}")

    # ----- core -----
    async def _handle_text(self, update: Any, text: str, attachment: Path | None = None) -> None:
        chat = update.effective_chat
        lang_code = getattr(update.effective_user, "language_code", None)
        s = self.session(chat.id, lang_code)
        L = load(s.last_lang)
        status = await chat.send_message(L.t("ui.progress.resolving"))
        loop = asyncio.get_running_loop()
        last: dict[str, float] = {"t": loop.time()}

        def progress(msg: str) -> None:
            now = loop.time()
            if now - last["t"] >= 2.0:
                last["t"] = now
                asyncio.run_coroutine_threadsafe(_edit(status, msg), loop)

        try:
            reply = await loop.run_in_executor(
                None, lambda: s.handle(text, attachment=attachment, progress=progress)
            )
        except Exception as e:  # noqa: BLE001
            reply = Reply(
                s._plain(
                    f"{load(s.last_lang).list('playful.error_generic')[0]} ({type(e).__name__})", s.last_lang
                )
            )
        try:
            await status.delete()
        except Exception:  # noqa: BLE001
            pass
        await self._send(update, reply)

    async def _send(self, update: Any, reply: Reply, keyboard: list[str] | None = None) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

        chat = update.effective_chat
        markup: Any = None
        if keyboard:
            markup = ReplyKeyboardMarkup(
                [[k] for k in keyboard], resize_keyboard=True, one_time_keyboard=True
            )
        elif reply.message.intent in (Intent.find, Intent.around) and reply.message.buttons:
            markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(b, callback_data=b) for b in reply.message.buttons]]
            )
        elif reply.audit is not None and reply.message.intent is Intent.audit:
            row = [
                InlineKeyboardButton("GPX", callback_data="gpx"),
                InlineKeyboardButton("➕", callback_data="another"),
            ]
            if reply.message.mode is Register.playful and reply.audit.route.identity.famous:
                row.append(InlineKeyboardButton("📷", callback_data="photos"))
            markup = InlineKeyboardMarkup([row])
        await chat.send_message(reply.message.text, reply_markup=markup, disable_web_page_preview=True)
        for f in reply.files:
            with f.open("rb") as fh:
                await chat.send_document(fh, filename=f.name)


async def _edit(status: Any, text: str) -> None:
    try:
        await status.edit_text(text)
    except Exception:  # noqa: BLE001
        pass


def smoke_offline() -> Path:
    """Used by tests: build a session in a temp dir without network or Telegram."""
    d = Path(tempfile.mkdtemp(prefix="bergbot-tg-"))
    Session(workdir=d, offline=True)
    return d
