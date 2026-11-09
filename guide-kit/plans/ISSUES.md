# Open issues in the plans

Sources: `plans/source/implement-plan-v3.md` (v3, doc rev 105) and `plans/source/detail-plan.md` (Detail, doc rev 51), exported from claude.ai on 2026-11-03 23:26.

The plans were reviewed in several rounds on 2026-11-03. All 92 issues found (conflicts between the two plans, logic bugs, missing steps, test gaps, wrong numbers, missing specs, tool risks, wording) were fixed in the plans themselves before this export. The user keeps the full review log outside the kit (`plan-issues.xlsx`); agents do not need it.

`step-designer` must still handle every **open** row below whose **Resolve in** matches the step it designs, and must add a new row (next free ID, starting at I-12) for any new conflict it finds between v3, Detail and `decisions.md`. `/decide` marks rows `resolved (D-xxx)`.

Status values: `open` | `resolved (D-xxx)`.

| ID | Resolve in | Kind | Issue | Where | Proposed resolution | Status |
|----|-----------|------|-------|-------|---------------------|--------|
| I-11 | S6, S7 | missing info (by design) | Events marked "dự kiến" (`FlashReservationCreated`, `FlashReservationReleased`, `PosSaleRecorded`, `PosRefundRecorded`) are finalized when their step is designed. v3 says the event table is updated afterwards and `src/Contracts/` in the reference becomes the source of truth. | v3 › Integration event | Designer of S6/S7 fixes payloads and routing keys, keeping the fields v3 already lists. | open |

## Things that look like issues but are intended

- Detail S0 week 3 creates Catalog and Gateway with `dotnet new web` and hand-written `ApiMarker` / `launchSettings`; `tools/new-service.py` only exists from session 49. Follow the plan.
- Commit messages in the user's repo follow the plan (`s2: reserve endpoint`, one branch per step). The kit's reference repo uses its own convention (`bNNN:` per session, tags `wNN`), see `CLAUDE.md`.
- `ReservationStatus` tombstones (`Sku = "*"`, `LocationId = Guid.Empty`) are intended; every query of held stock filters `Status = Active`.
