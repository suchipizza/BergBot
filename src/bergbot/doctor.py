"""`bergbot doctor`: keys, tokens, caches and adapter health, as JSON and as text."""

from __future__ import annotations

import os
from typing import Any

from bergbot import __version__
from bergbot.i18n import load
from bergbot.paths import cache_dir, user_config_dir


def run_doctor() -> dict[str, Any]:
    from bergbot.sources.registry import all_adapters

    adapters = []
    for adapter in all_adapters():
        try:
            h = adapter.health()
            fr = adapter.freshness()
            lic = adapter.licence()
            adapters.append(
                {
                    "id": adapter.id,
                    "ok": h.ok,
                    "latency_ms": h.latency_ms,
                    "note": h.note,
                    "cache_age_s": h.cache_age_s,
                    "ttl_s": fr.ttl_s,
                    "licence": lic.name,
                    "redistribution": lic.redistribution,
                }
            )
        except Exception as e:  # noqa: BLE001
            adapters.append(
                {"id": getattr(adapter, "id", "?"), "ok": False, "note": f"{type(e).__name__}: {e}"}
            )
    cfg = user_config_dir()
    telegram_token = bool(os.environ.get("BERGBOT_TELEGRAM_TOKEN")) or (cfg / "telegram.token").exists()
    return {
        "version": __version__,
        "config_dir": str(cfg),
        "cache_dir": str(cache_dir()),
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "telegram_token": telegram_token,
        "adapters": adapters,
    }


def format_doctor(report: dict[str, Any], lang: str = "en") -> str:
    L = load(lang)
    lines = [f"{L.t('ui.doctor.title')} v{report['version']}"]
    yes, no = L.t("ui.doctor.set"), L.t("ui.doctor.not_set")
    lines.append(f"  {L.t('ui.doctor.anthropic_key')}: {yes if report['anthropic_key'] else no}")
    lines.append(f"  {L.t('ui.doctor.telegram_token')}: {yes if report['telegram_token'] else no}")
    lines.append(f"  cache: {report['cache_dir']}")
    for a in report["adapters"]:
        status = L.t("ui.doctor.ok") if a.get("ok") else L.t("ui.doctor.fail")
        age = a.get("cache_age_s")
        age_s = (
            f"{L.t('ui.doctor.cache_age')} {age // 3600}h" if age is not None else L.t("ui.doctor.no_cache")
        )
        note = f" — {a['note']}" if a.get("note") else ""
        lines.append(f"  [{status:>4}] {a['id']:<24} {age_s}{note}")
    return "\n".join(lines)
