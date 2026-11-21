#!/usr/bin/env python3
"""Track feature status, blockers and notes. These records feed the daily/sprint reports.

Examples
  plan.py list --sprint S1
  plan.py set F-001 in_progress --owner "Name" --branch chore/F-001-postgres-18-migration
  plan.py set F-001 review --pr https://github.com/ORG/REPO/pull/12
  plan.py set F-001 done --note "compose boots PG18; CI db-integration green"
  plan.py blocker add "Need write access to the trunk repo" --feature F-002
  plan.py blocker resolve 1 --note "access granted"
  plan.py note add "Decided to keep asyncpg + plain SQL" --kind decision
  plan.py note add "Start F-005 first thing" --kind next
  plan.py where            # today's sprint, day, days to freeze/deadline
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import common as c


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def feature_map() -> dict:
    return {f["id"]: f for f in c.load_backlog()}


def cmd_list(args) -> int:
    fm, status = feature_map(), c.load_status()
    rows = []
    for fid, f in fm.items():
        st = status["features"][fid]
        if args.sprint and f["sprint"].lower() != args.sprint.lower():
            continue
        if args.status and st["status"] != args.status:
            continue
        rows.append((f["sprint"], f["priority"], fid, st["status"], st.get("owner", ""), f["title"]))
    rows.sort()
    if not rows:
        print("(no matching features)")
        return 0
    print(f"{'SPR':<4} {'PRI':<4} {'ID':<6} {'STATUS':<12} {'OWNER':<14} TITLE")
    for sprint, pri, fid, st, owner, title in rows:
        print(f"{sprint:<4} {pri:<4} {fid:<6} {st:<12} {owner[:14]:<14} {title}")
    done = sum(1 for r in rows if r[3] == "done")
    print(f"\n{done}/{len(rows)} done")
    return 0


def cmd_show(args) -> int:
    fm, status = feature_map(), c.load_status()
    fid = args.id.upper()
    if fid not in fm:
        print(f"error: unknown feature {fid}", file=sys.stderr)
        return 2
    f, st = fm[fid], status["features"][fid]
    print(f"{fid}  {f['title']}")
    print(f"  branch:   {f['branch']}")
    print(f"  priority: {f['priority']}   track: {f['track']}   sprint: {f['sprint']}"
          + (f" (starts {f['start_sprint']})" if f.get("start_sprint") else ""))
    print(f"  depends:  {', '.join(f['depends']) or '-'}")
    print(f"  levels:   {', '.join(f['levels']) or '-'}")
    print(f"  status:   {st['status']}   owner: {st.get('owner') or '-'}   pr: {st.get('pr') or '-'}")
    for h in st.get("history", []):
        print(f"    {h['at']}  {h['from']} -> {h['to']}" + (f"  ({h['note']})" if h.get("note") else ""))
    return 0


def cmd_set(args) -> int:
    fm, status = feature_map(), c.load_status()
    fid = args.id.upper()
    if fid not in fm:
        print(f"error: unknown feature {fid}", file=sys.stderr)
        return 2
    if args.status not in c.STATUSES:
        print(f"error: status must be one of {', '.join(c.STATUSES)}", file=sys.stderr)
        return 2
    st = status["features"][fid]
    when = f"{c.parse_date(args.date).isoformat()}T{dt.datetime.now().strftime('%H:%M:%S')}" if args.date else now_iso()
    if st["status"] != args.status:
        st.setdefault("history", []).append(
            {"at": when, "from": st["status"], "to": args.status, "note": args.note or ""}
        )
        st["status"] = args.status
    elif args.note:
        st.setdefault("history", []).append({"at": when, "from": st["status"], "to": st["status"], "note": args.note})
    for key in ("owner", "branch", "pr"):
        val = getattr(args, key)
        if val:
            st[key] = val
    if args.status == "in_progress" and not st.get("branch"):
        st["branch"] = fm[fid]["branch"]
    st["updated"] = when
    c.save_status(status)
    print(f"{fid}: {st['status']}")
    return 0


def cmd_blocker(args) -> int:
    status = c.load_status()
    blockers = status["blockers"]
    if args.action == "add":
        if not args.text:
            print("error: blocker text required", file=sys.stderr)
            return 2
        nid = max([b["id"] for b in blockers], default=0) + 1
        blockers.append({
            "id": nid, "text": args.text, "feature": (args.feature or "").upper(),
            "opened": c.parse_date(args.date).isoformat(), "resolved": "", "resolution": "",
        })
        print(f"blocker #{nid} added")
    elif args.action == "resolve":
        target = next((b for b in blockers if str(b["id"]) == str(args.text)), None)
        if not target:
            print(f"error: no blocker #{args.text}", file=sys.stderr)
            return 2
        target["resolved"] = c.parse_date(args.date).isoformat()
        target["resolution"] = args.note or ""
        print(f"blocker #{target['id']} resolved")
    else:  # list
        for b in blockers:
            mark = "OPEN " if not b["resolved"] else "DONE "
            print(f"#{b['id']:<3} {mark} {b['opened']}  {b.get('feature') or '-':<6} {b['text']}"
                  + (f"  -> {b['resolution']}" if b.get("resolution") else ""))
        if not blockers:
            print("(no blockers recorded)")
        return 0
    c.save_status(status)
    return 0


def cmd_note(args) -> int:
    status = c.load_status()
    if args.action == "list":
        for n in status["notes"]:
            print(f"{n['date']}  [{n['kind']}]  {n['text']}")
        if not status["notes"]:
            print("(no notes)")
        return 0
    if not args.text:
        print("error: note text required", file=sys.stderr)
        return 2
    status["notes"].append({"date": c.parse_date(args.date).isoformat(), "kind": args.kind, "text": args.text})
    c.save_status(status)
    print("note added")
    return 0


def cmd_where(_args) -> int:
    today = dt.date.today()
    sp, day, span = c.sprint_for_date(today)
    ms = c.load_sprints().get("milestones", {})
    print(f"Today: {c.day_name(today)}")
    if sp:
        print(f"Sprint {sp['id']} - {sp['name']} (day {day}/{span}, {sp['start']} to {sp['end']})")
        print(f"Goal: {sp['goal']}")
    for key, label in (("feature_freeze", "Feature freeze"), ("deadline", "Deadline")):
        if ms.get(key):
            target = dt.datetime.fromisoformat(ms[key])
            days = (target.date() - today).days
            print(f"{label}: {ms[key].replace('T', ' ')}  ({days} day(s) away)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list"); s.add_argument("--sprint"); s.add_argument("--status", choices=c.STATUSES); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=cmd_show)

    s = sub.add_parser("set"); s.add_argument("id"); s.add_argument("status")
    s.add_argument("--owner"); s.add_argument("--branch"); s.add_argument("--pr")
    s.add_argument("--note"); s.add_argument("--date"); s.set_defaults(fn=cmd_set)

    s = sub.add_parser("blocker"); s.add_argument("action", choices=["add", "resolve", "list"])
    s.add_argument("text", nargs="?", help="text for add, id for resolve")
    s.add_argument("--feature"); s.add_argument("--note"); s.add_argument("--date"); s.set_defaults(fn=cmd_blocker)

    s = sub.add_parser("note"); s.add_argument("action", choices=["add", "list"])
    s.add_argument("text", nargs="?")
    s.add_argument("--kind", choices=["note", "next", "risk", "decision"], default="note")
    s.add_argument("--date"); s.set_defaults(fn=cmd_note)

    s = sub.add_parser("where"); s.set_defaults(fn=cmd_where)
    return p


def main(argv=None) -> int:
    c.utf8_stdout()
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
