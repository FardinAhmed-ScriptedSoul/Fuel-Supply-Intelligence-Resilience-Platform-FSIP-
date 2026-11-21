"""Shared helpers for the hub's planning and reporting tools (standard library only)."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
PLANNING = HUB / "planning"
REPORTS = HUB / "reports"
STATUSES = ("todo", "in_progress", "review", "blocked", "done", "dropped")
FEATURE_RE = re.compile(r"F-\d{3}")


def utf8_stdout() -> None:
    """Windows Git Bash consoles often default to a legacy code page; force UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def load_config() -> dict:
    return read_json(PLANNING / "config.json", {})


def load_backlog() -> list[dict]:
    return read_json(PLANNING / "backlog.json", {"features": []})["features"]


def load_sprints() -> dict:
    return read_json(PLANNING / "sprints.json", {"sprints": [], "milestones": {}})


def load_status() -> dict:
    data = read_json(PLANNING / "status.json", None)
    if data is None:
        data = {"features": {}, "blockers": [], "notes": []}
    data.setdefault("features", {})
    data.setdefault("blockers", [])
    data.setdefault("notes", [])
    for feat in load_backlog():
        data["features"].setdefault(
            feat["id"],
            {"status": "todo", "owner": "", "branch": "", "pr": "", "updated": "", "history": []},
        )
    return data


def save_status(data: dict) -> None:
    write_json(PLANNING / "status.json", data)


def parse_date(text: str | None) -> dt.date:
    if not text:
        return dt.date.today()
    if text.lower() == "today":
        return dt.date.today()
    if text.lower() == "yesterday":
        return dt.date.today() - dt.timedelta(days=1)
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise SystemExit(f"error: bad date '{text}' (use YYYY-MM-DD, 'today' or 'yesterday')")


def day_name(d: dt.date) -> str:
    return d.strftime("%a %d %b %Y")


def sprint_for_date(d: dt.date, sprints: dict | None = None) -> tuple[dict | None, int, int]:
    """Return (sprint, day_index, days_in_sprint). Falls back to the nearest sprint."""
    sprints = sprints or load_sprints()
    items = sprints.get("sprints", [])
    if not items:
        return None, 0, 0
    for sp in items:
        s, e = dt.date.fromisoformat(sp["start"]), dt.date.fromisoformat(sp["end"])
        if s <= d <= e:
            return sp, (d - s).days + 1, (e - s).days + 1
    first, last = items[0], items[-1]
    if d < dt.date.fromisoformat(first["start"]):
        return first, 0, (dt.date.fromisoformat(first["end"]) - dt.date.fromisoformat(first["start"])).days + 1
    span = (dt.date.fromisoformat(last["end"]) - dt.date.fromisoformat(last["start"])).days + 1
    return last, span + 1, span


def sprint_by_id(sprint_id: str, sprints: dict | None = None) -> dict | None:
    sprints = sprints or load_sprints()
    for sp in sprints.get("sprints", []):
        if sp["id"].lower() == sprint_id.lower():
            return sp
    return None


# ----------------------------------------------------------------------------- git / gh helpers
def run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr if proc.returncode else "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def git(repo: Path, *args: str, timeout: int = 60) -> str | None:
    if not (repo / ".git").exists():
        return None
    code, out = run(["git", "-C", str(repo), *args], timeout=timeout)
    return out if code == 0 else None


def repo_path(entry: dict) -> Path:
    p = Path(entry["path"])
    return p if p.is_absolute() else (HUB / p).resolve()


def git_user() -> str:
    out = git(HUB, "config", "user.name")
    return (out or "").strip() or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


def which(name: str) -> str | None:
    return shutil.which(name)


def gh_json(args: list[str], repo_dir: Path, timeout: int = 40):
    """Run `gh ... --json` inside repo_dir. Returns parsed JSON or None when gh is unavailable."""
    if not which("gh"):
        return None
    code, out = run(["gh", *args], cwd=repo_dir, timeout=timeout)
    if code != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def feature_ids(text: str) -> list[str]:
    return sorted(set(FEATURE_RE.findall(text or "")))
