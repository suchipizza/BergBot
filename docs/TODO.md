# Founder todo (Phase 1 follow-ups)

- [ ] **Design pass first**, then replace placeholder screenshots in `docs/screenshots/`: `connect-tg-1.png`,
      `connect-tg-3.png`, and take real `chat.png` / `report-phone.png` on a phone (steps in the session notes and
      `docs/connect/en.md`). `scripts/screenshots.py` overwrites all eight images — make it skip existing files
      before rerunning.
- [ ] Telegram: create the bot in @BotFather, `bergbot connect telegram`, run the three canonical prompts end to end.
- [ ] Decide how the bot stays up: terminal, `nohup`, a launchd service (`--install-service` to be added), or an
      always-on box. Hosted bridge is Phase 3.
- [ ] Real Tally form URL in `pyproject.toml` → `tool.bergbot.waitlist_url`.
- [ ] Claude.ai marketplace path check from a browser (website tab says "coming soon").
- [ ] 3–5 routes you know well → `docs/benchmark/reference.yaml` `founder_notes`.
- [ ] Native read of `locales/{fr,de,it}/playful.yaml`.
- [ ] Set repo variable `PYPI_PUBLISH=true` and configure PyPI trusted publishing when ready to publish.
