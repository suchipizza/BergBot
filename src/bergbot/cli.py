"""`bergbot` command-line entry point.

Boundary: argument parsing and output only. Every `--json` command prints exactly one JSON document to
stdout and exits 0; errors go to stderr as `{"error": ..., "unverified": [...]}` with exit code 2.
Deterministic work is delegated to `bergbot.core`; conversation to `bergbot.conversation`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from bergbot import __version__

app = typer.Typer(
    name="bergbot",
    help="Check everything before you go to the mountains. Local-first, warnings first, never a verdict.",
    no_args_is_help=True,
    add_completion=False,
)


def emit(doc: Any) -> None:
    """Print a single JSON document (stable key order, UTF-8) — the contract for every --json command."""
    sys.stdout.write(json.dumps(doc, ensure_ascii=False, indent=2, default=str) + "\n")


def fail(error: str, unverified: list[str] | None = None, code: int = 2) -> None:
    sys.stderr.write(json.dumps({"error": error, "unverified": unverified or []}, ensure_ascii=False) + "\n")
    raise typer.Exit(code)


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", "-V", help="Print version and exit.", is_eager=True),
) -> None:
    if version:
        typer.echo(f"bergbot {__version__}")
        raise typer.Exit()


@app.command()
def doctor(json_out: bool = typer.Option(False, "--json", help="Machine-readable output.")) -> None:
    """Check keys, tokens, data caches and adapter health."""
    from bergbot.doctor import run_doctor

    report = run_doctor()
    if json_out:
        emit(report)
        return
    from bergbot.doctor import format_doctor

    typer.echo(format_doctor(report))


schema_app = typer.Typer(help="Domain model schemas.")
app.add_typer(schema_app, name="schema")


@schema_app.command("export")
def schema_export(out: Path = typer.Option(Path("docs/schema"), "--out", help="Output directory.")) -> None:
    """Write JSON schemas for every domain model to docs/schema/."""
    from bergbot.core.domain import export_schemas

    written = export_schemas(out)
    typer.echo(f"wrote {len(written)} schemas to {out}")


brand_app = typer.Typer(help="Mascot asset pipeline.")
app.add_typer(brand_app, name="brand")


@brand_app.command("build")
def brand_build() -> None:
    """Optimise brand/mascot/src/*.png|svg into dist/ (WebP ≤ 40 KB, data URIs, avatar)."""
    from bergbot.brand import build_assets

    for line in build_assets():
        typer.echo(line)


@app.command()
def resolve(
    place: str = typer.Argument(..., help="Address, village, stop, hut, summit or 'lat,lon'."),
    json_out: bool = typer.Option(True, "--json/--no-json"),
    lang: str = typer.Option("en", "--lang"),
) -> None:
    """Resolve a place name to a canonical Place with bbox, canton and elevation."""
    from bergbot.core.geospatial.places import resolve_place

    try:
        p = resolve_place(place, lang=lang)
    except LookupError as e:
        fail(str(e))
        return
    emit(p.model_dump(mode="json"))


@app.command()
def audit(
    route: Path = typer.Argument(..., help="GPX, KML or GeoJSON file."),
    date: str = typer.Option(None, "--date", help="YYYY-MM-DD (default: tomorrow)."),
    start_time: str = typer.Option("09:00", "--start", help="Planned start HH:MM."),
    lang: str = typer.Option("en", "--lang"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
    out: Path = typer.Option(None, "--out", help="Write audit JSON to this file instead of stdout."),
    offline: bool = typer.Option(
        False, "--offline", help="Use only cached static layers; skip live sources."
    ),
    name: str = typer.Option(None, "--name", help="Route name override."),
) -> None:
    """Run the full audit on a route file and print the Audit JSON."""
    from bergbot.core.workflows import run_audit

    try:
        result = run_audit(route, date=date, start_time=start_time, lang=lang, offline=offline, name=name)
    except FileNotFoundError:
        fail(f"file not found: {route}")
        return
    doc = result.model_dump(mode="json")
    if out:
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        typer.echo(str(out))
    else:
        emit(doc)


@app.command()
def find(
    constraints: str = typer.Option(
        ..., "--constraints", help="Constraint JSON (see docs/schema/Constraint.json)."
    ),
    lang: str = typer.Option("en", "--lang"),
    limit: int = typer.Option(3, "--limit"),
    offline: bool = typer.Option(False, "--offline"),
) -> None:
    """Find 2–3 candidate routes matching constraints, ranked by conditions."""
    from bergbot.core.domain import Constraint
    from bergbot.core.workflows import run_find

    try:
        c = Constraint.model_validate_json(constraints)
    except Exception as e:  # noqa: BLE001
        fail(f"invalid constraints: {e}")
        return
    result = run_find(c, lang=lang, limit=limit, offline=offline)
    emit(result.model_dump(mode="json"))


@app.command()
def around(
    place: str = typer.Argument(..., help="Place text, 'lat,lon' or path to a GPX."),
    constraints: str = typer.Option("{}", "--constraints", help="Optional constraint JSON."),
    lang: str = typer.Option("en", "--lang"),
    limit: int = typer.Option(3, "--limit"),
    offline: bool = typer.Option(False, "--offline"),
) -> None:
    """Find suitable routes around a place."""
    from bergbot.core.domain import Constraint
    from bergbot.core.workflows import run_around

    try:
        c = Constraint.model_validate_json(constraints)
    except Exception as e:  # noqa: BLE001
        fail(f"invalid constraints: {e}")
        return
    try:
        result = run_around(place, c, lang=lang, limit=limit, offline=offline)
    except LookupError as e:
        fail(str(e))
        return
    emit(result.model_dump(mode="json"))


@app.command()
def check(
    kind: str = typer.Option(..., "--kind", help="lift | hut | pass | fire_ban | road"),
    name: str = typer.Option(..., "--name", help="Name of the lift/hut/pass or canton."),
    date: str = typer.Option(None, "--date"),
    lang: str = typer.Option("en", "--lang"),
) -> None:
    """Single-status check. Returns verified/unverified with source and timestamp plus the web-verification spec."""
    from bergbot.core.workflows import run_check

    result = run_check(kind, name, date=date, lang=lang)
    emit(result.model_dump(mode="json"))


@app.command()
def render(
    audit_json: Path = typer.Argument(..., help="Audit JSON produced by `bergbot audit`."),
    lang: str = typer.Option(None, "--lang", help="Override report language."),
    out: Path = typer.Option(Path("bergbot-report.html"), "--out"),
    no_map: bool = typer.Option(False, "--no-map", help="Skip tile fetch (blank map background)."),
) -> None:
    """Render the single-file HTML report from an audit JSON."""
    from bergbot.core.domain import Audit
    from bergbot.core.reporting.render import render_report

    audit_obj = Audit.model_validate_json(audit_json.read_text(encoding="utf-8"))
    html, size_warning = render_report(audit_obj, lang=lang, with_map=not no_map)
    out.write_text(html, encoding="utf-8")
    typer.echo(str(out))
    if size_warning:
        typer.echo(size_warning, err=True)


@app.command()
def export(
    audit_json: Path = typer.Argument(..., help="Audit JSON produced by `bergbot audit`."),
    fmt: str = typer.Option("gpx", "--format", help="gpx | kml | geojson"),
    out: Path = typer.Option(None, "--out"),
) -> None:
    """Export the audited route as GPX (default), KML or GeoJSON."""
    from bergbot.core.domain import Audit
    from bergbot.core.geospatial.export import export_route

    audit_obj = Audit.model_validate_json(audit_json.read_text(encoding="utf-8"))
    target = out or Path(f"bergbot-route.{fmt}")
    export_route(audit_obj.route, fmt, target)
    typer.echo(str(target))


@app.command()
def message(
    audit_json: Path = typer.Argument(..., help="Audit JSON."),
    lang: str = typer.Option(None, "--lang"),
    report_filename: str = typer.Option("bergbot-report.html", "--report-filename"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Render the ≤12-line chat message (register decided by rule) from an audit JSON."""
    from bergbot.conversation.message import render_audit_message
    from bergbot.conversation.register import decide
    from bergbot.core.domain import Audit, Intent, QuestionKind

    audit_obj = Audit.model_validate_json(audit_json.read_text(encoding="utf-8"))
    reg = decide(audit_obj, Intent.audit, QuestionKind.none)
    msg = render_audit_message(audit_obj, reg, lang=lang or audit_obj.lang, report_filename=report_filename)
    if json_out:
        emit({"message": msg.model_dump(mode="json"), "register": reg.model_dump(mode="json")})
    else:
        typer.echo(msg.text)


@app.command()
def suggest(
    lang: str = typer.Option("en", "--lang"),
    region: str = typer.Option(None, "--region", help="Canton code, e.g. gl, vs, ti."),
    month: int = typer.Option(None, "--month"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Four localised, seasonal, region-aware prompt suggestions."""
    from bergbot.conversation.suggestions import suggest as _suggest

    s = _suggest(lang=lang, region=region, month=month)
    if json_out:
        emit([x.model_dump(mode="json") for x in s])
    else:
        for i, x in enumerate(s, 1):
            typer.echo(f"{i}. {x.text}")


@app.command()
def chat(
    lang: str = typer.Option(None, "--lang", help="Force reply language (default: detect)."),
    workdir: Path = typer.Option(Path("."), "--workdir", help="Where report/GPX files are written."),
) -> None:
    """Interactive chat (standalone mode; needs ANTHROPIC_API_KEY)."""
    from bergbot.adapters.cli.repl import run_repl

    run_repl(lang=lang, workdir=workdir)


connect_app = typer.Typer(help="Connect a messaging channel.")
app.add_typer(connect_app, name="connect")


@connect_app.command("telegram")
def connect_telegram(
    token: str = typer.Option(None, "--token", help="BotFather token (prompted if omitted)."),
    workdir: Path = typer.Option(None, "--workdir"),
) -> None:
    """Store a Telegram bot token and start the local long-polling bot."""
    from bergbot.adapters.telegram.bot import connect_and_run

    connect_and_run(token=token, workdir=workdir)


@app.command()
def benchmark(
    json_out: bool = typer.Option(False, "--json"),
    offline: bool = typer.Option(True, "--offline/--online"),
) -> None:
    """Run the benchmark harness in docs/benchmark and print the pass rate."""
    from bergbot.benchmark import run_benchmark

    result = run_benchmark(offline=offline)
    if json_out:
        emit(result)
    else:
        from bergbot.benchmark import format_table

        typer.echo(format_table(result))


if __name__ == "__main__":
    app()
