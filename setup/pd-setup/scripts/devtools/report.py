#!/usr/bin/env python3
"""Generate the daily engineering report, the short daily update message, and sprint reports.

  report.py daily  [--date YYYY-MM-DD] [--with-tests] [--no-gh] [--stdout]
  report.py update [--date YYYY-MM-DD]                 # short text for chat/email (statement.md format)
  report.py sprint [--sprint S1] [--with-tests] [--no-gh] [--stdout]
  report.py all    [--date YYYY-MM-DD]                 # daily + update (+ sprint report on the sprint's last day)

Data sources (each optional; gaps are listed at the bottom of the report):
  git history of the hub and the code repo · planning/status.json (features, blockers, notes) ·
  GitHub CLI `gh` (merged/open PRs, CI runs) · local pytest run (--with-tests)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import common as c

SEP = "\x1f"


# ------------------------------------------------------------------------- data collection
def collect_commits(repo: Path, start: dt.date, end: dt.date, limit: int) -> dict | None:
    if not (repo / ".git").exists():
        return None
    base = ["log", "--all", "--no-merges", f"--since={start.isoformat()} 00:00:00", f"--until={end.isoformat()} 23:59:59"]
    out = c.git(repo, *base, "--date=format-local:%Y-%m-%d %H:%M",
                f"--pretty=format:%h{SEP}%an{SEP}%ad{SEP}%s{SEP}%D")
    if out is None:
        return None
    commits = []
    for line in out.splitlines():
        parts = line.split(SEP)
        if len(parts) < 5:
            continue
        h, author, when, subject, refs = parts[:5]
        commits.append({"hash": h, "author": author, "when": when, "subject": subject,
                        "features": c.feature_ids(subject + " " + refs)})
    stat = c.git(repo, *base, "--shortstat", "--pretty=tformat:") or ""
    ins = sum(int(m) for m in re.findall(r"(\d+) insertion", stat))
    dele = sum(int(m) for m in re.findall(r"(\d+) deletion", stat))
    files = sum(int(m) for m in re.findall(r"(\d+) files? changed", stat))
    by_feature: dict[str, list] = {}
    unlinked = []
    for cm in commits:
        if cm["features"]:
            for fid in cm["features"]:
                by_feature.setdefault(fid, []).append(cm)
        else:
            unlinked.append(cm)
    return {"commits": commits, "by_feature": by_feature, "unlinked": unlinked,
            "authors": sorted({cm["author"] for cm in commits}), "insertions": ins, "deletions": dele,
            "files": files, "limit": limit}


def collect_gh(repo: Path, day: dt.date | None, start: dt.date | None = None, end: dt.date | None = None) -> dict | None:
    if not (repo / ".git").exists() or not c.which("gh"):
        return None
    if start and end:
        query = f"merged:{start.isoformat()}..{end.isoformat()}"
    else:
        query = f"merged:{day.isoformat()}" if day else ""
    merged = c.gh_json(["pr", "list", "--state", "merged", "--search", query, "--limit", "100", "--json",
                        "number,title,author,mergedAt,url,headRefName"], repo)
    opened = c.gh_json(["pr", "list", "--state", "open", "--limit", "50", "--json",
                        "number,title,author,url,headRefName,isDraft,reviewDecision,updatedAt"], repo)
    runs = c.gh_json(["run", "list", "--branch", "main", "--limit", "5", "--json",
                      "name,conclusion,status,createdAt,url,displayTitle"], repo)
    if merged is None and opened is None and runs is None:
        return None
    return {"merged": merged or [], "open": opened or [], "runs": runs or []}


def find_python(code: Path) -> str:
    for cand in (code / ".venv" / "bin" / "python", code / ".venv" / "Scripts" / "python.exe"):
        if cand.exists():
            return str(cand)
    return sys.executable


def run_tests(code: Path) -> dict | None:
    if not (code / "tests").exists():
        return None
    import subprocess
    env = dict(os.environ)
    sep = os.pathsep
    env["PYTHONPATH"] = sep.join(["backend", "backend/shared", "intel/predictor"] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    py = find_python(code)
    targets = [t for t in ("tests/unit", "tests/scenarios") if (code / t).exists()] or ["tests"]

    def attempt(extra: list[str]) -> tuple[int, str]:
        try:
            p = subprocess.run([py, "-m", "pytest", *targets, "-q", *extra], cwd=str(code), env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420)
            return p.returncode, (p.stdout or "") + (p.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 127, str(exc)

    code_rc, out = attempt(["--cov=backend", "--cov-report=term"])
    if "unrecognized arguments" in out and "--cov" in out:
        code_rc, out = attempt([])
    passed = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    errors = re.search(r"(\d+) errors?", out)
    cov = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", out, re.M)
    if not (passed or failed or errors) and code_rc != 0:
        return {"ok": False, "summary": "pytest could not run (see tool output)", "passed": 0, "failed": 0, "coverage": None}
    return {"ok": code_rc == 0, "passed": int(passed.group(1)) if passed else 0,
            "failed": int(failed.group(1)) if failed else 0,
            "errors": int(errors.group(1)) if errors else 0,
            "coverage": int(cov.group(1)) if cov else None, "summary": ""}


# ------------------------------------------------------------------------- planning helpers
def day_matches(ts: str, day: dt.date) -> bool:
    return ts.startswith(day.isoformat())


def in_range(ts: str, start: dt.date, end: dt.date) -> bool:
    d = ts[:10]
    return start.isoformat() <= d <= end.isoformat()


def sprint_features(sprint_id: str, backlog: list[dict]) -> list[dict]:
    return [f for f in backlog if f["sprint"] == sprint_id]


def next_candidates(backlog: list[dict], status: dict, sprints: dict, limit: int = 5) -> list[dict]:
    order = {sp["id"]: i for i, sp in enumerate(sprints.get("sprints", []))}
    pri = {"P0": 0, "P1": 1, "P2": 2}
    st = status["features"]
    cands = []
    for f in backlog:
        s = st[f["id"]]["status"]
        if s in ("done", "dropped"):
            continue
        waiting = [d for d in f["depends"] if st.get(d, {}).get("status") != "done"]
        rank = (0 if s in ("in_progress", "review", "blocked") else 1, order.get(f["sprint"], 99),
                pri.get(f["priority"], 9), 1 if waiting else 0, f["id"])
        cands.append((rank, f, s, waiting))
    cands.sort(key=lambda x: x[0])
    return [{"feature": f, "status": s, "waiting": w} for _, f, s, w in cands[:limit]]


def fmt_feature(f: dict) -> str:
    return f"{f['id']} - {f['title']}"


def days_to(label_iso: str, today: dt.date) -> int:
    return (dt.datetime.fromisoformat(label_iso).date() - today).days


# ------------------------------------------------------------------------- daily report
def build_daily(day: dt.date, with_tests: bool, use_gh: bool) -> tuple[str, str]:
    cfg, backlog, sprints, status = c.load_config(), c.load_backlog(), c.load_sprints(), c.load_status()
    ms = sprints.get("milestones", {})
    sp, sday, span = c.sprint_for_date(day, sprints)
    fm = {f["id"]: f for f in backlog}
    st = status["features"]
    limit = cfg.get("report", {}).get("max_commits_listed", 40)
    repos = {r["name"]: r for r in cfg.get("repos", [])}
    code_entry = next((r for r in cfg.get("repos", []) if r.get("primary")), None)
    code_path = c.repo_path(code_entry) if code_entry else None
    gaps: list[str] = []

    code_git = collect_commits(code_path, day, day, limit) if code_path else None
    if code_git is None:
        gaps.append(f"code repo not found at `{code_entry['path'] if code_entry else '?'}` (run `scripts/setup.sh --code`) - commit data omitted")
    hub_git = None
    if cfg.get("report", {}).get("include_hub_commits", True) and "hub" in repos:
        hub_git = collect_commits(c.repo_path(repos["hub"]), day, day, limit)
    gh = collect_gh(code_path, day) if (use_gh and code_path) else None
    if use_gh and gh is None:
        gaps.append("GitHub CLI data unavailable (`gh` missing, not logged in, or no remote) - PR/CI sections omitted")
    tests = run_tests(code_path) if (with_tests and code_path) else None
    if with_tests and tests is None:
        gaps.append("tests not run (no tests directory in the code repo)")

    # features completed / started today (from status history)
    done_today, started_today = [], []
    for fid, rec in st.items():
        for h in rec.get("history", []):
            if day_matches(h["at"], day) and h["to"] == "done" and h["from"] != "done":
                done_today.append((fid, h.get("note", "")))
            if day_matches(h["at"], day) and h["to"] == "in_progress" and h["from"] == "todo":
                started_today.append(fid)
    notes_today = [n for n in status["notes"] if n["date"] == day.isoformat()]
    open_blockers = [b for b in status["blockers"] if not b["resolved"] and b["opened"] <= day.isoformat()]
    resolved_today = [b for b in status["blockers"] if b["resolved"] == day.isoformat()]
    in_progress = [fid for fid, rec in st.items() if rec["status"] in ("in_progress", "review", "blocked")]

    author = c.git_user()
    if sp and sday < 1:
        day_label = f"starts {sp['start']}"
    elif sp and sday > span:
        day_label = f"ended {sp['end']}"
    else:
        day_label = f"day {sday}/{span}"
    sprint_label = f"{sp['id']} - {sp['name']} ({day_label})" if sp else "no sprint"
    sp_feats = sprint_features(sp["id"], backlog) if sp else []
    sp_done = [f for f in sp_feats if st[f["id"]]["status"] == "done"]
    p0 = [f for f in sp_feats if f["priority"] == "P0"]
    p0_done = [f for f in p0 if st[f["id"]]["status"] == "done"]
    total_done = sum(1 for r in st.values() if r["status"] == "done")

    L: list[str] = []
    L.append(f"# Daily Engineering Report - {c.day_name(day)}\n")
    L.append(f"**Project:** {cfg.get('project', '')}  ")
    L.append(f"**Sprint:** {sprint_label}  ")
    L.append(f"**Prepared by:** {author}  |  **Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    L.append("## Snapshot\n")
    L.append("| Metric | Value |\n|---|---|")
    L.append(f"| Sprint features done | {len(sp_done)}/{len(sp_feats)} (P0: {len(p0_done)}/{len(p0)}) |")
    L.append(f"| Overall features done | {total_done}/{len(backlog)} |")
    if ms.get("feature_freeze"):
        L.append(f"| Days to feature freeze ({ms['feature_freeze'].replace('T', ' ')}) | {days_to(ms['feature_freeze'], day)} |")
    if ms.get("deadline"):
        L.append(f"| Days to deadline ({ms['deadline']}) | {days_to(ms['deadline'], day)} |")
    if code_git:
        L.append(f"| Code commits today | {len(code_git['commits'])} by {len(code_git['authors'])} author(s), "
                 f"{code_git['files']} files, +{code_git['insertions']}/-{code_git['deletions']} |")
    if hub_git:
        L.append(f"| Docs/planning commits today | {len(hub_git['commits'])} |")
    if gh:
        L.append(f"| PRs merged today / open now | {len(gh['merged'])} / {len(gh['open'])} |")
    if tests:
        cov = f", coverage {tests['coverage']}% (unit+scenarios only)" if tests.get("coverage") is not None else ""
        L.append(f"| Tests (unit+scenarios) | {tests['passed']} passed, {tests['failed']} failed{cov} |")
    L.append("")

    # 1 completed
    L.append("## 1. Completed today\n")
    any_done = False
    for fid, note in done_today:
        any_done = True
        pr = st[fid].get("pr")
        L.append(f"- **{fmt_feature(fm[fid])}** - DONE" + (f" ([PR]({pr}))" if pr else "") + (f". {note}" if note else ""))
    if gh:
        for pr in gh["merged"]:
            any_done = True
            L.append(f"- PR #{pr['number']} merged: {pr['title']} ({pr.get('author', {}).get('login', '?')}) - {pr['url']}")
    if code_git:
        for fid, cms in sorted(code_git["by_feature"].items()):
            any_done = True
            title = fm[fid]["title"] if fid in fm else ""
            L.append(f"- Work on **{fid}** {title}: {len(cms)} commit(s) - " + "; ".join(cm["subject"] for cm in cms[:3]) + (" ..." if len(cms) > 3 else ""))
        if code_git["unlinked"]:
            any_done = True
            L.append(f"- Other code commits ({len(code_git['unlinked'])}): " + "; ".join(cm["subject"] for cm in code_git["unlinked"][:4]) + (" ..." if len(code_git["unlinked"]) > 4 else ""))
    if hub_git and hub_git["commits"]:
        any_done = True
        L.append(f"- Docs/planning ({len(hub_git['commits'])} commit(s)): " + "; ".join(cm["subject"] for cm in hub_git["commits"][:4]) + (" ..." if len(hub_git["commits"]) > 4 else ""))
    if not any_done:
        L.append("- Nothing recorded as completed today. (Record it with `scripts/plan.sh set F-### done --note \"...\"`.)")
    L.append("")

    # 2 in progress
    L.append("## 2. In progress\n")
    if in_progress or (gh and gh["open"]):
        L.append("| Feature | Status | Owner | Branch | Last update | PR |\n|---|---|---|---|---|---|")
        for fid in sorted(in_progress):
            r = st[fid]
            L.append(f"| {fmt_feature(fm[fid])} | {r['status']} | {r.get('owner') or '-'} | `{r.get('branch') or fm[fid]['branch']}` | {r.get('updated', '')[:16].replace('T', ' ') or '-'} | {r.get('pr') or '-'} |")
        if gh and gh["open"]:
            L.append("\nOpen pull requests:")
            for pr in gh["open"]:
                state = "draft" if pr.get("isDraft") else (pr.get("reviewDecision") or "awaiting review")
                L.append(f"- #{pr['number']} {pr['title']} ({pr.get('author', {}).get('login', '?')}, {state}) - {pr['url']}")
    else:
        L.append("- No feature is marked in progress. (Start one with `scripts/plan.sh set F-### in_progress`.)")
    L.append("")

    # 3 blockers
    L.append("## 3. Challenges and blockers\n")
    any_block = False
    for b in open_blockers:
        any_block = True
        L.append(f"- **OPEN #{b['id']}** (since {b['opened']}" + (f", {b['feature']}" if b.get("feature") else "") + f"): {b['text']}")
    for fid, r in st.items():
        if r["status"] == "blocked":
            any_block = True
            L.append(f"- {fid} is marked **blocked**: see its latest note in `planning/status.json`")
    for b in resolved_today:
        any_block = True
        L.append(f"- Resolved today #{b['id']}: {b['text']}" + (f" -> {b['resolution']}" if b.get("resolution") else ""))
    if gh:
        bad = [r for r in gh["runs"] if r.get("conclusion") in ("failure", "cancelled", "timed_out")]
        for r in bad[:3]:
            any_block = True
            L.append(f"- CI on main: **{r['conclusion']}** - {r['displayTitle']} ({r['url']})")
    if tests and (tests["failed"] or not tests["ok"]):
        any_block = True
        L.append(f"- Local tests failing: {tests['failed']} failed" + (f" ({tests['summary']})" if tests.get("summary") else ""))
    if not any_block:
        L.append("- None recorded.")
    L.append("")

    # 4 next
    L.append("## 4. Next (plan for the next working day)\n")
    manual_next = [n for n in notes_today if n["kind"] == "next"]
    for n in manual_next:
        L.append(f"- {n['text']}")
    for cand in next_candidates(backlog, status, sprints):
        f, s, w = cand["feature"], cand["status"], cand["waiting"]
        verb = "Continue" if s in ("in_progress", "review", "blocked") else "Start"
        extra = f" (waiting on {', '.join(w)})" if w else ""
        L.append(f"- {verb} **{fmt_feature(f)}** [{f['priority']}, planned {f['sprint']}]{extra}")
    L.append("")

    # 5 quality
    if tests or (gh and gh["runs"]):
        L.append("## 5. Quality and health\n")
        if tests:
            cov = f"; coverage {tests['coverage']}%" if tests.get("coverage") is not None else ""
            L.append(f"- Local run (unit + scenarios): **{tests['passed']} passed, {tests['failed']} failed**{cov}.")
        if gh and gh["runs"]:
            L.append("- Recent CI runs on `main`:")
            for r in gh["runs"]:
                L.append(f"  - {r.get('conclusion') or r.get('status')}: {r['name']} - {r['displayTitle']} ({r['createdAt'][:16].replace('T', ' ')})")
        L.append("")

    # 6 notes
    other = [n for n in notes_today if n["kind"] != "next"]
    L.append("## 6. Decisions, risks and notes\n")
    if other:
        for n in other:
            L.append(f"- **{n['kind']}**: {n['text']}")
    else:
        L.append("- None recorded. (Add with `scripts/plan.sh note add \"...\" --kind decision|risk|note`.)")
    L.append("")

    # 7 outlook
    if sp:
        L.append("## 7. Sprint outlook\n")
        L.append(f"**{sp['id']} goal:** {sp['goal']}\n")
        remaining = [f for f in sp_feats if st[f["id"]]["status"] != "done"]
        if sp_feats:
            L.append(f"Remaining in sprint: {len(remaining)} of {len(sp_feats)}" + (": " + ", ".join(f['id'] for f in remaining) if remaining else " - sprint scope complete."))
        if day.isoformat() >= sp["end"] and [f for f in remaining if f["priority"] == "P0"]:
            L.append(f"\n**AT RISK:** last sprint day and {len([f for f in remaining if f['priority'] == 'P0'])} P0 feature(s) are not done.")
        L.append("\nExit criteria (tick when verified):")
        for crit in sp.get("exit_criteria", []):
            L.append(f"- [ ] {crit}")
        L.append("")

    # appendix
    if code_git and code_git["commits"]:
        L.append("## Appendix A - code commits\n")
        L.append("| Time | Hash | Author | Subject | Features |\n|---|---|---|---|---|")
        for cm in code_git["commits"][:limit]:
            L.append(f"| {cm['when']} | `{cm['hash']}` | {cm['author']} | {cm['subject'].replace('|', '/')} | {', '.join(cm['features']) or '-'} |")
        if len(code_git["commits"]) > limit:
            L.append(f"\n(+{len(code_git['commits']) - limit} more not listed)")
        L.append("")
    L.append("## Appendix B - data sources and gaps\n")
    L.append(f"- Sources used: git history ({'code + ' if code_git else ''}{'hub' if hub_git else 'none'}), `planning/status.json`" + (", GitHub CLI" if gh else "") + (", local pytest run" if tests else "") + ".")
    for g in gaps:
        L.append(f"- Gap: {g}")
    L.append("- Everything above is generated; add context with `scripts/plan.sh` (status, blockers, notes) and regenerate.")
    L.append("")
    md = "\n".join(L)

    # short update (statement.md format)
    T: list[str] = [f"Daily update - {c.day_name(day)}" + (f" | Sprint {sp['id']}: {sp['name']} ({day_label})" if sp else ""), ""]
    T.append("Completed:")
    comp = [f"- {fmt_feature(fm[fid])}" + (f" ({n})" if n else "") for fid, n in done_today]
    if gh:
        comp += [f"- PR #{p['number']} merged: {p['title']}" for p in gh["merged"]]
    if code_git and not comp:
        comp += [f"- {fid}: {len(cms)} commit(s)" for fid, cms in sorted(code_git["by_feature"].items())]
    if hub_git and hub_git["commits"] and not comp:
        comp.append(f"- Docs/planning: {len(hub_git['commits'])} commit(s)")
    T += comp or ["- (nothing recorded)"]
    T += ["", "In progress:"]
    T += [f"- {fmt_feature(fm[fid])} [{st[fid]['status']}]" for fid in sorted(in_progress)] or ["- (none marked)"]
    T += ["", "Challenges / blockers:"]
    blk = [f"- #{b['id']} {b['text']}" for b in open_blockers] + [f"- {fid} blocked" for fid, r in st.items() if r["status"] == "blocked"]
    T += blk or ["- None"]
    T += ["", "Next:"]
    nxt = [f"- {n['text']}" for n in manual_next]
    nxt += [f"- {'Continue' if x['status'] != 'todo' else 'Start'} {fmt_feature(x['feature'])}" for x in next_candidates(backlog, status, sprints, 3)]
    T += nxt
    if ms.get("deadline"):
        T += ["", f"Days to freeze: {days_to(ms['feature_freeze'], day)} | to deadline: {days_to(ms['deadline'], day)}"]
    return md, "\n".join(T) + "\n"


# ------------------------------------------------------------------------- sprint report
def build_sprint(sprint_id: str, with_tests: bool, use_gh: bool) -> str:
    cfg, backlog, sprints, status = c.load_config(), c.load_backlog(), c.load_sprints(), c.load_status()
    sp = c.sprint_by_id(sprint_id, sprints)
    if not sp:
        raise SystemExit(f"error: unknown sprint '{sprint_id}'")
    start, end = dt.date.fromisoformat(sp["start"]), dt.date.fromisoformat(sp["end"])
    st = status["features"]
    feats = sprint_features(sp["id"], backlog)
    started_here = [f for f in backlog if f.get("start_sprint") == sp["id"] and f["sprint"] != sp["id"]]
    done = [f for f in feats if st[f["id"]]["status"] == "done"]
    spill = [f for f in feats if st[f["id"]]["status"] != "done"]
    code_entry = next((r for r in cfg.get("repos", []) if r.get("primary")), None)
    code_path = c.repo_path(code_entry) if code_entry else None
    git_data = collect_commits(code_path, start, end, 10**6) if code_path else None
    hub = next((r for r in cfg.get("repos", []) if r["name"] == "hub"), None)
    hub_git = collect_commits(c.repo_path(hub), start, end, 10**6) if hub else None
    gh = collect_gh(code_path, None, start, end) if (use_gh and code_path) else None
    tests = run_tests(code_path) if (with_tests and code_path) else None

    L = [f"# Sprint Report - {sp['id']}: {sp['name']}\n"]
    L.append(f"**Dates:** {sp['start']} to {sp['end']}  |  **Prepared by:** {c.git_user()}  |  **Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    L.append(f"**Goal:** {sp['goal']}\n")
    pct = int(100 * len(done) / len(feats)) if feats else 0
    L.append("## Outcome\n")
    L.append(f"- Planned features: **{len(feats)}**; done: **{len(done)}** ({pct}%); carried over: **{len(spill)}**.")
    if started_here:
        L.append("- Started here, finishing later: " + ", ".join(f"{f['id']} (planned {f['sprint']})" for f in started_here) + ".")
    if git_data:
        L.append(f"- Code activity: {len(git_data['commits'])} commits by {len(git_data['authors'])} author(s), {git_data['files']} files, +{git_data['insertions']}/-{git_data['deletions']}.")
    if hub_git:
        L.append(f"- Docs/planning commits: {len(hub_git['commits'])}.")
    if gh:
        L.append(f"- PRs merged: {len(gh['merged'])}; open now: {len(gh['open'])}.")
    if tests:
        cov = f", coverage {tests['coverage']}%" if tests.get("coverage") is not None else ""
        L.append(f"- Tests now: {tests['passed']} passed, {tests['failed']} failed{cov}.")
    L.append("")

    L.append("## Features\n")
    L.append("| ID | Title | Pri | Status | Owner | PR |\n|---|---|---|---|---|---|")
    for f in feats:
        r = st[f["id"]]
        L.append(f"| {f['id']} | {f['title']} | {f['priority']} | {r['status']} | {r.get('owner') or '-'} | {r.get('pr') or '-'} |")
    L.append("")

    L.append("## Exit criteria (tick manually after verifying)\n")
    for crit in sp.get("exit_criteria", []):
        L.append(f"- [ ] {crit}")
    L.append(f"\n**Demo:** {sp.get('demo', '')}\n")

    L.append("## Carry-over\n")
    if spill:
        order = [s["id"] for s in sprints["sprints"]]
        nxt = order[order.index(sp["id"]) + 1] if sp["id"] in order and order.index(sp["id"]) + 1 < len(order) else "(after the last sprint: decide: cut or finish before freeze)"
        for f in spill:
            L.append(f"- {fmt_feature(f)} [{f['priority']}] - status **{st[f['id']]['status']}** -> move to **{nxt}**" + (" (P2 stretch: candidate to cut)" if f["priority"] == "P2" else ""))
    else:
        L.append("- Nothing carried over.")
    L.append("")

    L.append("## Blockers\n")
    rng = [b for b in status["blockers"] if b["opened"] <= sp["end"] and (not b["resolved"] or b["resolved"] >= sp["start"])]
    if rng:
        for b in rng:
            L.append(f"- #{b['id']} ({b['opened']} -> {b['resolved'] or 'OPEN'}) {b['text']}" + (f" - {b['resolution']}" if b.get("resolution") else ""))
    else:
        L.append("- None recorded.")
    L.append("")

    notes = [n for n in status["notes"] if sp["start"] <= n["date"] <= sp["end"] and n["kind"] in ("decision", "risk")]
    L.append("## Decisions and risks\n")
    for n in notes:
        L.append(f"- {n['date']} **{n['kind']}**: {n['text']}")
    if not notes:
        L.append("- None recorded.")
    L.append("")

    daily = sorted(p.name for p in (c.REPORTS / "daily").glob("*.md") if sp["start"] <= p.stem <= sp["end"])
    L.append("## Daily reports in this sprint\n")
    for name in daily:
        L.append(f"- [{name[:-3]}](../daily/{name})")
    if not daily:
        L.append("- None generated yet (`scripts/report.sh daily`).")
    L.append("")

    L.append("## Retrospective (fill in)\n")
    L.append("- What went well:\n- What slowed us down:\n- What we change next sprint:\n- Risks we now see:\n")
    return "\n".join(L)


# ------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    c.utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("daily", "update", "sprint", "all"):
        s = sub.add_parser(name)
        s.add_argument("--date", help="YYYY-MM-DD | today | yesterday (default today)")
        s.add_argument("--sprint", help="sprint id for 'sprint' (default: sprint of --date)")
        s.add_argument("--with-tests", action="store_true", help="run unit+scenario tests in the code repo and include the numbers")
        s.add_argument("--no-gh", action="store_true", help="skip GitHub CLI lookups")
        s.add_argument("--stdout", action="store_true", help="print instead of writing files")
    args = p.parse_args(argv)
    day = c.parse_date(args.date)
    use_gh = not args.no_gh

    def emit(path: Path, text: str) -> None:
        if args.stdout:
            print(text)
        else:
            c.write_text(path, text)
            print(f"wrote {path.relative_to(c.HUB)}")

    if args.cmd in ("daily", "update", "all"):
        md, short = build_daily(day, args.with_tests, use_gh)
        if args.cmd in ("daily", "all"):
            emit(c.REPORTS / "daily" / f"{day.isoformat()}.md", md)
        if args.cmd in ("update", "all"):
            emit(c.REPORTS / "daily" / f"{day.isoformat()}.update.txt", short)
    if args.cmd in ("sprint", "all"):
        sprints = c.load_sprints()
        if args.cmd == "sprint":
            sp = c.sprint_by_id(args.sprint, sprints) if args.sprint else c.sprint_for_date(day, sprints)[0]
        else:
            sp, _, _ = c.sprint_for_date(day, sprints)
            if not sp or day.isoformat() < sp["end"]:
                return 0  # 'all' only emits the sprint report on the sprint's last day
        if not sp:
            print("error: no sprint found", file=sys.stderr)
            return 2
        emit(c.REPORTS / "sprint" / f"{sp['id']}.md", build_sprint(sp["id"], args.with_tests, use_gh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
