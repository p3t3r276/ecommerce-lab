---
description: Design one step (contracts, conventions, questions, session kinds) with step-designer (Opus)
argument-hint: S0..S8
model: sonnet
---

You are the orchestrator. Do not design anything yourself; delegate to the `step-designer` subagent.

1. Parse the step from `$ARGUMENTS` (S0..S8). If missing or invalid, run `python3 tools/kit-status.py` and ask the user (in Vietnamese) which step to design. Stop.
2. Preconditions:
   - `plans/index.json` exists; otherwise run `python3 tools/split-plans.py` first.
   - For S1..S8: `git -C reference tag --list "s<N-1>-done"` must print the tag. If not, tell the user (in Vietnamese) that the previous step is not finished in the reference, and stop.
   - If `design/sN.md` already exists with `status: approved`, ask the user whether to redesign. Stop until they confirm.
   - If `notes/s<N-1>.md` does not exist (S1+), mention that the design will not include their feedback on the previous step, and continue.
3. Call `step-designer` with: "Design step SN. Follow the procedure in your definition."
4. When it returns, read only the front matter and the "Questions for the user" and "Plan issues" sections of `design/sN.md`.
5. Report to the user in Vietnamese, at most 12 lines: number of conventions and contracts, the list of questions (one line each with the recommendation), new plan issues. Tell them to read `design/sN.md`, tick their choices (or answer in chat), then run `/decide SN`.
