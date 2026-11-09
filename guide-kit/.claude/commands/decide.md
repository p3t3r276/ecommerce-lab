---
description: Record the user's answers for a step design, append decisions, write the shared-file list, approve the design
argument-hint: S0..S8
model: sonnet
---

You record decisions. You may edit `design/sN.md`, `decisions.md`, `plans/ISSUES.md` and `shared/sN.txt`. Nothing else.

1. Read `design/sN.md` for the step in `$ARGUMENTS`. It must exist with `status: draft`; otherwise report and stop.
2. For each `### Q-sN-xx` question:
   - If exactly one option is ticked (`- [x]`), use it, together with the "Reason (user):" line if filled.
   - Otherwise ask the user in Vietnamese, one question at a time: a short context (2–3 lines), the options, and the recommendation. Record their choice by ticking the option and filling "Reason (user):" in `design/sN.md`. If they say "theo đề xuất", use the recommendation.
3. Append to `decisions.md` (append only, never edit existing entries), with the next free IDs `D-xxx` and today's date:
   - one entry per answered question (Kind: architecture, Decided by: user),
   - one entry per convention group in the design's "Conventions" section that overrides or completes the plans (Kind: convention, Decided by: agent). Group related conventions; do not create one entry per line.
   - one entry for the contracts of the step: "Contracts of SN are defined in design/sN.md §Contracts" (Kind: contract).
   Fill "Overrides" and "Resolves" from the design.
4. In `plans/ISSUES.md`, set Status to `resolved (D-xxx)` for every issue the design resolves. Add new issue rows proposed by the design, with the next free `I-xx` IDs.
5. Write `shared/sN.txt` from the "Shared files" section: one glob per line, relative to the reference root, `#` comments allowed.
6. Set `status: approved` in the front matter of `design/sN.md`.
7. Report in Vietnamese, at most 8 lines: decisions added (IDs and titles), issues resolved, and the next step: `/build-reference`.
