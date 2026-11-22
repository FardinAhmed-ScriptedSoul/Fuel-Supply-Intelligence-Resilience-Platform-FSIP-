"""Read-only simulator endpoint sampler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def sample_path(name: str | Path, output_dir: str | Path) -> Path:
    path = Path(name)
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    return Path(output_dir) / path.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/sim-samples"))
    args = parser.parse_args()

    endpoints = ("v1/health", "v1/state", "v1/metrics", "v1/events", "v1/faults")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for endpoint in endpoints:
        request = Request(f"{args.base_url.rstrip('/')}/{endpoint}", method="GET")
        try:
            with urlopen(request, timeout=5) as response:
                body = response.read()
                record = {
                    "endpoint": f"/{endpoint}",
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "body": json.loads(body) if body else None,
                }
        except (HTTPError, URLError, TimeoutError) as exc:
            record = {"endpoint": f"/{endpoint}", "error": str(exc)}
        filename = endpoint.rsplit("/", 1)[-1]
        output_path = sample_path(filename, args.output_dir)
        output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
