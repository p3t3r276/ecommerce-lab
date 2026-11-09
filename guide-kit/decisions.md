# Decisions

The single source of truth for every choice that changes or completes the plans. Agents read this file before anything else and follow it over the plans.

**Precedence:** `decisions.md` > `plans/source/implement-plan-v3.md` (what to build and why) > `plans/source/detail-plan.md` (order, commands, done criteria).

**Format.** Append only. To change a decision, add a new entry that says `Supersedes D-xxx`; never edit or delete an old one.

```
### D-012 · S3 · Outbox is called explicitly through IOutbox
- Kind: convention | contract | architecture
- Decided by: agent (convention) | user (from Q-s3-02)
- Decision: <one or two sentences, precise enough to implement>
- Overrides: <plan reference, e.g. "Detail session 110 OutboxInterceptor"> | none
- Resolves: <I-xx> | none
- Reason: <why>
- Date: YYYY-MM-DD
```

---

### D-000 · all · How plans are used
- Kind: convention
- Decided by: user
- Decision: v3 defines architecture, domain, contracts and gates. Detail defines the order of work (week, session), commands and "done" criteria. When they conflict, follow the latest decision here; if none exists, stop and raise a question in the step design instead of guessing.
- Overrides: none
- Resolves: none
- Reason: two plans written at different times; one explicit rule avoids silent drift.
- Date: 2026-11-03
