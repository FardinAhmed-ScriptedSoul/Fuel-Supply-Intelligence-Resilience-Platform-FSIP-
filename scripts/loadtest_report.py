"""Render a concise Markdown report from a k6 summary JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _value(summary: dict[str, Any], metric: str, key: str) -> str:
    values = summary.get(metric)
    if not isinstance(values, dict) or key not in values:
        return "unavailable"
    value = values[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "unavailable"
    return f"{value:g}"


def render(summary_file: str | Path) -> str:
    data = json.loads(Path(summary_file).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("k6 summary must be a JSON object")
    workload = data.get("workload", "unavailable")
    stages = data.get("stages", "unavailable")
    rows = (
        ("p50 latency (ms)", _value(data, "http_req_duration", "med")),
        ("p90 latency (ms)", _value(data, "http_req_duration", "p(90)")),
        ("p95 latency (ms)", _value(data, "http_req_duration", "p(95)")),
        ("p99 latency (ms)", _value(data, "http_req_duration", "p(99)")),
        ("Requests per second", _value(data, "http_reqs", "rate")),
        ("Request count", _value(data, "http_reqs", "count")),
        ("Error rate", _value(data, "request_errors", "rate")),
    )
    lines = [
        f"# Load test: {workload}",
        "",
        f"**Stages:** {stages}",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *(f"| {name} | {value} |" for name, value in rows),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    report = render(args.summary)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
