# Bring your own channel (WhatsApp, Signal, iMessage…)

Bergbot ships no messaging bridge. If your agent (Claude Code or a personal agent gateway) is already connected
to a messaging app through an MCP server or a bridge, install the Bergbot plugin and message your agent from
that app: the plugin skills run the `bergbot` CLI locally and return the message, the report and the GPX as files
through the same channel.

What Bergbot guarantees: the ≤12-line message is plain text with minimal markdown, so it renders in any client;
files are ordinary `.html` and `.gpx` attachments; nothing depends on the channel.

What Bergbot does not do: recommend, ship or maintain any bridge. Unofficial WhatsApp Web bridges breach
WhatsApp's terms and can get a number banned. A Bergbot-owned WhatsApp bot (Business API, hosted) is Phase 3.

Fixture: `tests/e2e/test_passthrough.py` simulates a message arriving from a generic bridge (text + optional file),
runs the same session the plugin skills use, and checks that text and files come back channel-agnostic.
