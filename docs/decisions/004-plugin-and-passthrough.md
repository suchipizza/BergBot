# 004 — Plugin mode contract and channel passthrough

The Claude plugin (`plugins/bergbot`) contains no Python. Its skills tell the host agent exactly which
`bergbot … --json` commands to run and what to do with the JSON: present `bergbot message` verbatim, obey
`register`, verify statuses only through pages actually read (WebVerification shape), deliver files.
Sub-agents split the research (route-investigator, conditions-analyst, logistics-researcher,
restriction-researcher, media-scout) and a final evidence-reviewer gate re-checks the safety rules.

Channel passthrough is a documented pattern, not code: any bridge that reaches the host agent gets plain text
and files back. Bergbot does not ship or recommend a WhatsApp bridge (terms of service).

Claude.ai marketplace install: to be verified from a fresh account before launch (PRD open decision 4); the
website tab reads "coming soon" until verified.
