---
description: Build the next week(s) of the reference implementation with reference-builder (Sonnet), one week per subagent, sequentially
argument-hint: [wNN | number of weeks, default 1]
model: sonnet
---

You are the orchestrator. Do not write code yourself; delegate to the `reference-builder` subagent.

1. Run `python3 tools/kit-status.py next-build`. It prints the next week to build (`wNN SN`) or a reason why nothing can be built (design not approved, step gate not passed, blocked log).
2. Decide which weeks to build:
   - `$ARGUMENTS` is `wNN`: build only that week, and only if it is the one `next-build` printed; otherwise explain and stop.
   - `$ARGUMENTS` is a number k (1–4): build up to k weeks.
   - Empty: build 1 week.
3. For each week, **one at a time** (each week depends on the previous one):
   - Call `reference-builder` with: "Build week wNN (step SN). Follow the procedure in your definition."
   - After it returns, check `build-log/wNN.md` front matter. If `status: blocked`, stop the loop and go to step 4.
   - Run `python3 tools/kit-status.py next-build` again for the next week. Stop if the step's last week is done (the next step needs `/design-step`).
4. Report to the user in Vietnamese, at most 8 lines: weeks built, tags created, sessions marked `unverified`, deviations, blockers and what decision is needed. Suggest `/write-guides` next.

Do not read the code or the full build logs yourself; rely on the builder's report and the front matter, so this session's context stays small.
