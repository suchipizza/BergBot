"""Benchmark harness (work order M6): audit 10 real routes and compare with `docs/benchmark/reference.yaml`.

Checks per route: distance ±3 % and ascent ±10 % of the reference, every `expected_warning_types` present,
no amenity open/closed without verified evidence, fixed line present in the message, register rule respected.
`--offline` replays `docs/benchmark/fixtures/<slug>.json.gz`; `record=True` (re)writes them from a live run."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import yaml

from bergbot.conversation.message import render_audit_message
from bergbot.conversation.register import decide
from bergbot.core.domain import AmenityStatus, Intent, QuestionKind
from bergbot.core.workflows import run_audit
from bergbot.i18n import load
from bergbot.paths import repo_root
from bergbot.sources.http import FixtureFetcher, HttpFetcher

BENCH = (repo_root() or Path(".")) / "docs" / "benchmark"
DATE = "2026-09-12"


def run_benchmark(offline: bool = True, record: bool = False) -> dict[str, Any]:
    ref = yaml.safe_load((BENCH / "reference.yaml").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in ref["routes"]:
        slug = item["slug"]
        gpx = BENCH / "routes" / f"{slug}.gpx"
        fx = BENCH / "fixtures" / f"{slug}.json.gz"
        if record:
            tmp = BENCH / "fixtures" / f"{slug}.json"
            fetcher: Any = HttpFetcher(record_to=tmp)
        elif offline and fx.exists():
            fetcher = FixtureFetcher.from_file(fx)
            fetcher.strict = False
        else:
            fetcher = HttpFetcher()
        checks: dict[str, bool] = {}
        try:
            a = run_audit(
                gpx, date=item.get("date", DATE), lang="en", fetcher=fetcher, origin=item.get("origin")
            )
        except Exception as e:  # noqa: BLE001
            rows.append({"slug": slug, "ok": False, "error": f"{type(e).__name__}: {e}", "checks": {}})
            continue
        if record:
            with gzip.open(fx, "wt", encoding="utf-8") as fh:
                fh.write(tmp.read_text(encoding="utf-8"))
            tmp.unlink()
        s = a.route.stats
        assert s is not None
        exp = item.get("expect", {})
        if "distance_km" in exp:
            checks["distance"] = abs(s.distance_km - exp["distance_km"]) / exp["distance_km"] <= 0.03
        if "ascent_m" in exp:
            checks["ascent"] = abs(s.ascent_m - exp["ascent_m"]) / max(exp["ascent_m"], 50) <= 0.10
        types = {w.type.value for w in a.warnings}
        for t in exp.get("warning_types", []):
            checks[f"warn:{t}"] = t in types
        for t in exp.get("absent_warning_types", []):
            checks[f"no:{t}"] = t not in types
        checks["unverified_stays_unverified"] = all(
            x.status is AmenityStatus.unverified or x.verification == "verified" for x in a.amenities
        )
        reg = decide(a, Intent.audit, QuestionKind.none)
        msg = render_audit_message(a, reg, lang="en")
        checks["fixed_line"] = load("en").t("safety.fixed_line") in msg.text
        checks["message_le_12"] = len(msg.lines) <= 12
        if exp.get("register"):
            checks["register"] = reg.mode.value == exp["register"]
        checks["network_member"] = a.route.network_member or item.get("allow_off_network", False)
        rows.append(
            {
                "slug": slug,
                "ok": all(checks.values()),
                "checks": checks,
                "stats": {
                    "distance_km": s.distance_km,
                    "ascent_m": s.ascent_m,
                    "descent_m": s.descent_m,
                    "duration_min": s.duration_min,
                },
                "warnings": sorted(types),
                "register": reg.mode.value,
            }
        )
    passed = sum(1 for r in rows if r["ok"])
    return {
        "date": DATE,
        "routes": rows,
        "passed": passed,
        "total": len(rows),
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
    }


def format_table(result: dict[str, Any]) -> str:
    lines = [
        f"# Bergbot benchmark — {result['passed']}/{result['total']} routes pass ({result['pass_rate'] * 100:.0f} %)",
        "",
        "| route | ok | km | ↑ m | register | warnings | failed checks |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in result["routes"]:
        st = r.get("stats") or {}
        failed = ", ".join(k for k, v in r.get("checks", {}).items() if not v) or (
            "error: " + r["error"] if r.get("error") else "—"
        )
        lines.append(
            f"| {r['slug']} | {'✅' if r['ok'] else '❌'} | {st.get('distance_km', '—')} | {st.get('ascent_m', '—')} | {r.get('register', '—')} | {', '.join(r.get('warnings', []))} | {failed} |"
        )
    return "\n".join(lines)


def write_results(result: dict[str, Any]) -> Path:
    out = BENCH / "results.md"
    out.write_text(format_table(result) + "\n", encoding="utf-8")
    (BENCH / "results.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return out
