#!/usr/bin/env python3
"""Status of the guide kit.

  python3 tools/kit-status.py                 table per step + suggested next command
  python3 tools/kit-status.py next-build      next week to build: "wNN SN" (exit 0) or a reason (exit 2)
  python3 tools/kit-status.py pending-guides  built weeks without a guide: one "wNN SN" per line
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference"


def front_matter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("#")[0].strip()
    return out


def ref_tags() -> set[str]:
    if not (REF / ".git").exists():
        return set()
    r = subprocess.run(["git", "-C", str(REF), "tag", "--list"], capture_output=True, text=True)
    return set(r.stdout.split())


def load_steps() -> list[tuple[str, dict]]:
    idx = ROOT / "plans" / "index.json"
    if not idx.exists():
        print("plans/index.json missing: run `python3 tools/split-plans.py` first.", file=sys.stderr)
        sys.exit(1)
    steps = json.loads(idx.read_text(encoding="utf-8"))["detail"]["steps"]
    return sorted(steps.items(), key=lambda kv: int(kv[0][1:]))


def design_status(sid: str) -> str:
    fm = front_matter(ROOT / "design" / f"{sid.lower()}.md")
    return fm.get("status", "missing") if fm or (ROOT / "design" / f"{sid.lower()}.md").exists() else "missing"


def week_state(sid: str, wid: str, tags: set[str]) -> dict:
    log = front_matter(ROOT / "build-log" / f"{wid}.md")
    return {
        "built": wid in tags,
        "log": log.get("status", "missing"),
        "guide": (ROOT / "guides" / sid.lower() / f"{wid}.md").exists(),
        "review": (ROOT / "reviews" / f"{wid}.md").exists(),
    }


def next_build(steps, tags) -> tuple[int, str]:
    for i, (sid, step) in enumerate(steps):
        for j, wid in enumerate(step["weeks"]):
            if wid in tags:
                continue
            log = front_matter(ROOT / "build-log" / f"{wid}.md")
            if log.get("status") == "blocked":
                return 2, f"blocked: {wid} ({sid}) - see build-log/{wid}.md, add the missing decision, then rebuild"
            if design_status(sid) != "approved":
                return 2, f"design {sid} is {design_status(sid)}: run /design-step {sid} then /decide {sid}"
            if j == 0 and i > 0:
                prev = steps[i - 1][0].lower()
                if f"{prev}-done" not in tags:
                    return 2, f"{steps[i-1][0]} gate not passed: tag {prev}-done missing in reference"
            return 0, f"{wid} {sid}"
    return 2, "all weeks built"


def pending_guides(steps, tags) -> list[str]:
    out = []
    for sid, step in steps:
        for wid in step["weeks"]:
            st = week_state(sid, wid, tags)
            if st["built"] and st["log"] == "done" and not st["guide"]:
                out.append(f"{wid} {sid}")
    return out


def main() -> int:
    steps = load_steps()
    tags = ref_tags()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "next-build":
        code, msg = next_build(steps, tags)
        print(msg)
        return code
    if mode == "pending-guides":
        for line in pending_guides(steps, tags):
            print(line)
        return 0

    print(f"{'Step':<5} {'Design':<9} {'Built':>7} {'Guides':>7} {'Reviews':>8}  {'Gate':<5} Weeks")
    for sid, step in steps:
        weeks = list(step["weeks"])
        states = [week_state(sid, w, tags) for w in weeks]
        built = sum(s["built"] for s in states)
        guides = sum(s["guide"] for s in states)
        reviews = sum(s["review"] for s in states)
        gate = "yes" if f"{sid.lower()}-done" in tags else "-"
        print(f"{sid:<5} {design_status(sid):<9} {built:>3}/{len(weeks):<3} {guides:>3}/{len(weeks):<3} "
              f"{reviews:>8}  {gate:<5} {weeks[0]}-{weeks[-1]}")

    drafts = [sid for sid, _ in steps if design_status(sid) == "draft"]
    pend = pending_guides(steps, tags)
    code, msg = next_build(steps, tags)
    if drafts:
        nxt = f"/decide {drafts[0]}"
    elif msg.startswith("blocked"):
        nxt = msg
    elif pend:
        nxt = f"/write-guides  ({len(pend)} built week(s) without a guide)"
    elif code == 0:
        nxt = f"/build-reference  (next: {msg})"
    elif msg.startswith("design"):
        nxt = f"/design-step {msg.split()[1]}"
    else:
        nxt = msg
    print(f"\nNext: {nxt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
