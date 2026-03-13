"""Build a summary report from Locust CSV output.

Usage: python scripts/build_report.py reports/<timestamp>
"""

import csv
import sys
from pathlib import Path


PASS_CRITERIA = {
    "p99_ms": 100,           # p99 < 100ms
    "error_rate_pct": 5,     # < 5% error rate (excluding startup)
}


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def fmt_ms(val):
    return f"{float(val):.0f}ms" if val else "N/A"


def build_report(report_dir: Path):
    stats_file = report_dir / "locust_stats.csv"
    history_file = report_dir / "locust_stats_history.csv"
    failures_file = report_dir / "locust_failures.csv"

    if not stats_file.exists():
        print(f"No stats file found in {report_dir}")
        sys.exit(1)

    stats = load_csv(stats_file)
    failures = load_csv(failures_file) if failures_file.exists() else []
    history = load_csv(history_file) if history_file.exists() else []

    # Find the Aggregated row
    agg = next((r for r in stats if r["Name"] == "Aggregated"), None)
    if not agg:
        print("No aggregated stats found")
        sys.exit(1)

    total_reqs = int(agg["Request Count"])
    total_fails = int(agg["Failure Count"])
    error_rate = (total_fails / total_reqs * 100) if total_reqs > 0 else 0

    # Per-endpoint stats
    endpoints = [r for r in stats if r["Name"] != "Aggregated"]

    # Peak RPS from history (exclude first 60s of warmup)
    peak_rps = 0
    if history:
        for row in history:
            ts = float(row.get("Timestamp", 0))
            rps = float(row.get("Total Requests/s", 0) or 0)
            if rps > peak_rps:
                peak_rps = rps

    # Build report
    lines = []
    lines.append("=" * 70)
    lines.append("LEDGER LOAD TEST REPORT")
    lines.append("=" * 70)
    lines.append("")

    lines.append("## Success Criteria")
    lines.append("")
    p99 = float(agg.get("99%", 0))
    p99_pass = p99 < PASS_CRITERIA["p99_ms"]
    err_pass = error_rate < PASS_CRITERIA["error_rate_pct"]

    lines.append(f"  p99 latency:  {fmt_ms(agg.get('99%'))}  (target: <{PASS_CRITERIA['p99_ms']}ms)  {'PASS' if p99_pass else 'FAIL'}")
    lines.append(f"  Error rate:   {error_rate:.2f}%  (target: <{PASS_CRITERIA['error_rate_pct']}%)  {'PASS' if err_pass else 'FAIL'}")
    lines.append(f"  Peak RPS:     {peak_rps:.1f}")
    lines.append(f"  Overall:      {'PASS' if (p99_pass and err_pass) else 'FAIL'}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"  Total requests:   {total_reqs}")
    lines.append(f"  Total failures:   {total_fails}")
    lines.append(f"  Error rate:       {error_rate:.2f}%")
    lines.append(f"  Avg response:     {fmt_ms(agg.get('Average Response Time'))}")
    lines.append(f"  Median response:  {fmt_ms(agg.get('Median Response Time'))}")
    lines.append(f"  p95 response:     {fmt_ms(agg.get('95%'))}")
    lines.append(f"  p99 response:     {fmt_ms(agg.get('99%'))}")
    lines.append(f"  Max response:     {fmt_ms(agg.get('Max Response Time'))}")
    lines.append(f"  Avg RPS:          {float(agg.get('Requests/s', 0)):.1f}")
    lines.append("")

    lines.append("## Per-Endpoint Breakdown")
    lines.append("")
    lines.append(f"  {'Endpoint':<30} {'Reqs':>7} {'Fails':>7} {'Avg':>8} {'p95':>8} {'p99':>8} {'Max':>8}")
    lines.append(f"  {'-'*30} {'-'*7} {'-'*7} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for ep in endpoints:
        name = ep["Name"]
        reqs = ep["Request Count"]
        fails = ep["Failure Count"]
        avg = fmt_ms(ep.get("Average Response Time"))
        p95 = fmt_ms(ep.get("95%"))
        p99 = fmt_ms(ep.get("99%"))
        mx = fmt_ms(ep.get("Max Response Time"))
        lines.append(f"  {name:<30} {reqs:>7} {fails:>7} {avg:>8} {p95:>8} {p99:>8} {mx:>8}")
    lines.append("")

    if failures:
        lines.append("## Failure Details")
        lines.append("")
        for f in failures:
            name = f.get("Name", "")
            count = f.get("Occurrences", "")
            msg = f.get("Error", "")[:120]
            lines.append(f"  [{count}x] {name}: {msg}")
        lines.append("")

    lines.append("=" * 70)

    report = "\n".join(lines)
    print(report)

    # Save to file
    report_file = report_dir / "summary.txt"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\nSaved to {report_file}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <report-dir>")
        print(f"  e.g.: {sys.argv[0]} reports/20260313_121500")
        sys.exit(1)
    build_report(Path(sys.argv[1]))
