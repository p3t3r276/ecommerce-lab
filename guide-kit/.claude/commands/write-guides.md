---
description: Write Vietnamese guides for built weeks that have none yet, with guide-writer (Sonnet), up to 3 in parallel
argument-hint: [wNN ...]
model: sonnet
---

You are the orchestrator. Do not write guides yourself; delegate to the `guide-writer` subagent.

1. Run `python3 tools/kit-status.py pending-guides`. It lists weeks that are built (tag `wNN` exists and `build-log/wNN.md` has `status: done`) but have no guide yet.
2. If `$ARGUMENTS` lists weeks, keep only those that appear in the pending list; report the others with the reason.
3. Take at most 3 weeks. Call `guide-writer` for each in the same turn so they run in parallel (guides only read the reference, so they do not conflict). Prompt: "Write the guide for wNN (step SN). Follow the procedure in your definition."
4. Report in Vietnamese, at most 8 lines: guides written (path, word count), experiments ran vs predicted, anything the writer found missing in the logs. If more weeks are pending, suggest running `/write-guides` again.
