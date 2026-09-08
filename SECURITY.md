# Security

Bergbot runs locally: your route files, tokens and API keys stay on your machine. The Telegram token is stored in
`~/.bergbot/telegram.token` (mode 600); the Anthropic key is read from the environment. No telemetry, no
Bergbot server in Phase 1 (only the static website and a third-party waitlist form).

Report a vulnerability privately via GitHub Security Advisories on this repository (Security → Report a
vulnerability). Please do not open a public issue. We aim to acknowledge within 72 hours.

Scope notes: web verification is performed by your own LLM's web tool; pages it reads are untrusted input and
are only ever quoted (≤ 15 words) with a URL — never executed. Reports are single-file HTML without scripts.
