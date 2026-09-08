# Install Bergbot

One command per surface. Every guide has one screenshot per step; commands have a copy button on the website.

## Claude Code

**Step 1 — Add the marketplace**
```
/plugin marketplace add suchipizza/BergBot
```
![](../screenshots/install-cc-1.png)

**Step 2 — Install the plugin**
```
/plugin install bergbot
```
![](../screenshots/install-cc-2.png)

**Step 3 — Install the CLI the plugin calls, then type a sentence or /find …**
```
pipx install bergbot
```
![](../screenshots/install-cc-3.png)

## Claude.ai

Coming soon — the Customize → Plugins → Add marketplace path is being verified from a fresh account. Until then use Claude Code, Telegram or the CLI.

## CLI

**Step 1 — Install**
```
pipx install "bergbot[all]"
bergbot doctor
```
**Step 2 — Optional: your Anthropic key enables web verification and free chat**
```
export ANTHROPIC_API_KEY=sk-ant-…
```
**Step 3 — Chat, or run one check**
```
bergbot chat
bergbot audit route.gpx --date 2026-09-12 --lang en --out audit.json && bergbot render audit.json
```
![](../screenshots/chat.png)

## Bring your own channel (WhatsApp, Signal, iMessage…)

If your agent is already connected to a messaging app through an MCP server or bridge, install the Claude Code plugin and message your agent from that app. Bergbot ships no bridge and does not recommend unofficial WhatsApp bridges (they breach WhatsApp's terms).
