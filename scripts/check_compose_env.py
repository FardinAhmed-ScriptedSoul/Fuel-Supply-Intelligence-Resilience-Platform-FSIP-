"""Check resolved Compose credentials and internal service ports without printing secrets."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit
from typing import Any


def load_compose_config(env_file: str | Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "config",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(result.stdout)
    if not isinstance(config, dict):
        raise ValueError("Resolved Compose configuration must be a JSON object")
    return config


def _environment(service: dict[str, Any]) -> dict[str, str]:
    raw = service.get("environment", {})
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        return {
            entry.split("=", 1)[0]: entry.split("=", 1)[1]
            for entry in raw
            if isinstance(entry, str) and "=" in entry
        }
    return {}


def _internal_ports(service: dict[str, Any]) -> set[int]:
    ports: set[int] = set()
    for entry in service.get("ports", []):
        target: Any
        if isinstance(entry, dict):
            target = entry.get("target")
        elif isinstance(entry, str):
            target = entry.split(":")[-1].split("/")[0]
        else:
            continue
        try:
            ports.add(int(target))
        except (TypeError, ValueError):
            continue
    return ports


def configuration_errors(config: dict[str, Any]) -> list[str]:
    services = config.get("services")
    if not isinstance(services, dict):
        return ["Compose services are missing"]

    errors: list[str] = []
    postgres_environment = _environment(services.get("postgres", {}))
    postgres = postgres_environment.get("POSTGRES_PASSWORD")
    if postgres is None:
        errors.append("postgres.POSTGRES_PASSWORD is missing")

    for name in ("api", "worker"):
        database_url = _environment(services.get(name, {})).get("DATABASE_URL")
        if not database_url:
            errors.append(f"{name}.DATABASE_URL is missing")
        elif postgres is not None:
            try:
                configured_password = unquote(urlsplit(database_url).password or "")
            except ValueError:
                configured_password = None
            if configured_password is None or configured_password != postgres:
                errors.append(f"{name}.DATABASE_URL credentials do not match postgres")

    worker_predictor_url = _environment(services.get("worker", {})).get("PREDICTOR_URL")
    predictor_ports = _internal_ports(services.get("predictor", {}))
    if not worker_predictor_url:
        errors.append("worker.PREDICTOR_URL is missing")
    elif not predictor_ports:
        errors.append("predictor service internal port is missing")
    else:
        try:
            configured_port = urlsplit(worker_predictor_url).port
        except ValueError:
            configured_port = None
        if configured_port not in predictor_ports:
            errors.append("worker.PREDICTOR_URL port does not match predictor service")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()

    errors = configuration_errors(load_compose_config(args.env_file))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: database credentials and predictor URL match Compose services")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
