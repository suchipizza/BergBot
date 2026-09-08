"""Anthropic API calls used by the standalone session. Every call is optional: when no API key is configured,
`LLM.available` is False and the session works deterministically (rules, no web verification, no free chat).

Model: `BERGBOT_MODEL` (default claude-opus-5). Web verification uses the server-side web_search tool and must
return the `WebVerification` shape from sources/shared/web — the status stays `unverified` unless the model
returns a verified result with a URL and a quote."""

from __future__ import annotations

import json
import os
from typing import Any

from bergbot.conversation.intent import LLM_PROMPT, LLM_SCHEMA
from bergbot.i18n import load, normalise_lang
from bergbot.sources.shared.web import WebVerification

DEFAULT_MODEL = "claude-opus-5"

SYSTEM = """You are Bergbot, an open-source mountain-planning assistant for Switzerland (hiking first). You reply in the
language given. Facts about routes, distances, weather, transport, closures and hazards come from the tool results
you are given — never compute or invent them. Never call a route, day or condition "safe" or any equivalent
("should be fine", "go for it", "sans danger", "sicher", "sicuro"); describe what is known, what is unknown, and
that the decision is the user's. Follow the register you are given: serious = precise, no humour, no emoji except
🔴🟠🟡; playful = warm, short, a little mountain humour. Keep answers short (≤ 8 lines)."""


class LLM:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("BERGBOT_MODEL", DEFAULT_MODEL)
        self._client: Any = None
        self.available = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    # ----- intent refinement (structured output) -----
    def classify(self, text: str, lang_hint: str | None, today: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        resp = self.client().messages.create(
            model=self.model,
            max_tokens=2000,
            system=f"{LLM_PROMPT} Today is {today}. Reply language hint: {lang_hint or 'detect'}.",
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": LLM_SCHEMA}},
        )
        for block in resp.content:
            if block.type == "text":
                try:
                    return dict(json.loads(block.text))
                except ValueError:
                    return None
        return None

    # ----- web verification -----
    def verify(self, spec: dict[str, Any], lang: str = "en") -> WebVerification | None:
        if not self.available:
            return None
        prompt = (
            "Verify this status with web search and answer ONLY with a JSON object matching the schema.\n"
            f"Status type: {spec['status_type']}. Queries to try: {spec['queries']}. Preferred sources: {spec['prefer']}.\n"
            f"Verified only if: {spec['verified_if']}. Value vocabulary: {spec['value_vocab']}. Rules: {spec['rules']}.\n"
            "Fill retrieved_ts with the current UTC time in ISO format. quoted_span ≤ 15 words verbatim."
        )
        resp = self.client().messages.create(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
            messages=[
                {
                    "role": "user",
                    "content": prompt + "\nSchema: " + json.dumps(WebVerification.model_json_schema()),
                }
            ],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        obj = _extract_json(text)
        if not obj:
            return None
        try:
            wv = WebVerification.model_validate(obj)
        except Exception:  # noqa: BLE001
            return None
        if wv.result == "verified" and not (wv.url and wv.quoted_span):
            wv.result = "unverified"  # SR-3: a verdict without evidence is not a verdict
        return wv

    # ----- media -----
    def media(self, spec: dict[str, Any], lang: str = "en") -> list[dict[str, Any]]:
        if not self.available:
            return []
        prompt = (
            f"Find 3–5 links (official page, gallery, recent dated trip report, video) for the route '{spec.get('subject', '')}'. "
            f"Queries: {spec['queries']}. Prefer: {spec['prefer']}. Rules: {spec['rules']}. "
            'Answer ONLY with a JSON list of objects {"title","url","type","date","description"} where type ∈ official|gallery|trip_report|video|article.'
        )
        resp = self.client().messages.create(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        obj = _extract_json(text, want_list=True)
        return [x for x in (obj or []) if isinstance(x, dict) and x.get("url") and x.get("title")][:5]

    # ----- free chat -----
    def chat(
        self, text: str, lang: str, register: str, facts: list[str], history: list[dict[str, str]]
    ) -> str | None:
        if not self.available:
            return None
        L = load(normalise_lang(lang))
        forbidden = ", ".join(L.list("safety.forbidden"))
        system = (
            f"{SYSTEM}\nReply language: {L.t('ui.language_name')} ({lang}). Register: {register}. "
            f"Forbidden phrases in this language: {forbidden}. If the user asks whether something is safe, answer with what is "
            f"known, what is unknown, and end with: {L.t('safety.fixed_line')}\n"
            + (
                "Facts from the current audit (use them, do not contradict them):\n- " + "\n- ".join(facts)
                if facts
                else ""
            )
        )
        messages = [*history[-8:], {"role": "user", "content": text}]
        resp = self.client().messages.create(
            model=self.model, max_tokens=1500, system=system, messages=messages
        )
        if resp.stop_reason == "refusal":
            return None
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None


def _extract_json(text: str, want_list: bool = False) -> Any:
    text = text.strip()
    start = text.find("[" if want_list else "{")
    end = text.rfind("]" if want_list else "}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None
