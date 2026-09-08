"""M6: benchmark harness runs offline on recorded fixtures with ≥ 90 % pass rate; zero safety regressions."""

from __future__ import annotations

from bergbot.benchmark import format_table, run_benchmark


def test_benchmark_offline() -> None:
    result = run_benchmark(offline=True)
    table = format_table(result)
    assert result["total"] == 10, table
    assert result["pass_rate"] >= 0.9, table
    for r in result["routes"]:
        assert r["checks"].get("fixed_line", True) and r["checks"].get("unverified_stays_unverified", True), r
