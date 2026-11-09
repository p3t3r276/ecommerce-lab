---
description: Review the user's own code for one week against contracts and the reference, with code-reviewer (Opus)
argument-hint: wNN [path to user repo]
model: sonnet
---

You are the orchestrator. Do not review yourself; delegate to the `code-reviewer` subagent.

1. Parse the week `wNN` from `$ARGUMENTS`. If missing, ask the user which week (in Vietnamese) and stop.
2. Find the user's repo path: the second argument if given, otherwise `SHOPLAB_PATH` in `kit.env`. Check that the path exists and is a git repo (`git -C <path> rev-parse`). If not, ask the user for the path and stop. If Claude Code cannot read that directory, tell the user to add it (for example with `/add-dir <path>`) and stop.
3. Check that `guides/sN/wNN.md` exists (the week has a guide). If not, explain and stop.
4. Call `code-reviewer` with: "Review wNN (step SN), user repo: <path>. Follow the procedure in your definition."
5. Read only the "Tóm tắt" section of `reviews/wNN.md` and report it to the user in Vietnamese, at most 8 lines, plus the path of the full review.
