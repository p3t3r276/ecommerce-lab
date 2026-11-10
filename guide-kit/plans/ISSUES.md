# Open issues in the plans

Sources: `plans/source/implement-plan-v3.md` (v3, doc rev 105) and `plans/source/detail-plan.md` (Detail, doc rev 51), exported from claude.ai on 2026-11-03 23:26.

The plans were reviewed in several rounds on 2026-11-03. All 92 issues found (conflicts between the two plans, logic bugs, missing steps, test gaps, wrong numbers, missing specs, tool risks, wording) were fixed in the plans themselves before this export. The user keeps the full review log outside the kit (`plan-issues.xlsx`); agents do not need it.

`step-designer` must still handle every **open** row below whose **Resolve in** matches the step it designs, and must add a new row (next free ID, starting at I-12) for any new conflict it finds between v3, Detail and `decisions.md`. `/decide` marks rows `resolved (D-xxx)`.

Status values: `open` | `resolved (D-xxx)`.

| ID | Resolve in | Kind | Issue | Where | Proposed resolution | Status |
|----|-----------|------|-------|-------|---------------------|--------|
| I-11 | S6, S7 | missing info (by design) | Events marked "dự kiến" (`FlashReservationCreated`, `FlashReservationReleased`, `PosSaleRecorded`, `PosRefundRecorded`) are finalized when their step is designed. v3 says the event table is updated afterwards and `src/Contracts/` in the reference becomes the source of truth. | v3 › Integration event | Designer of S6/S7 fixes payloads and routing keys, keeping the fields v3 already lists. | open |
| I-12 | S0 | conflict | Detail session 7 has the user create users by hand and export the realm, so each person's user IDs (sub) are random, while v3 Domain says Customer.Id = Keycloak sub "ID cố định trong realm" and S2 seed/customers.json, TestUsers depend on them. | Detail S0 w02 session 7; v3 › Domain model › Customer | Reference ships a curated docker/keycloak/shoplab-realm.json with fixed user IDs as a shared file; the user's export is replaced by it. | resolved (D-005) |
| I-13 | S0 | conflict | Detail session 14 asks to pass the gateway URL through an environment variable but names the file apps/*/proxy.conf.json, which cannot read environment variables. | Detail S0 w04 session 14 | Use apps/<name>/proxy.conf.mjs reading services__gateway__http__0, fallback http://localhost:5000. | resolved (D-007) |
| I-14 | S0 | wording | Detail session 7 lists the admin user as "admin"; v3 Data mẫu and Detail session 16 use username admin@shoplab.local. | Detail S0 w02 session 7 | Username is admin@shoplab.local. | resolved (D-005) |
| I-15 | S0 | logic | Detail session 2 runs git checkout -b step/s0-foundation before the first commit but expects "Commit đầu tiên trên master". | Detail S0 w01 session 2 | git init -b master, first commit on master, then create step/s0-foundation. | resolved (D-003) |
| I-16 | S0 | missing step | Detail session 1 does not install Aspire.ProjectTemplates, which session 3 needs for dotnet new aspire-apphost (v3 › Lệnh 1 has it). | Detail S0 w01 session 1 | Session 1 also runs dotnet new install Aspire.ProjectTemplates. | resolved (D-003) |
| I-17 | all | conflict | Detail session 2 now says "Commit đầu tiên trên master", but the step-end merge sessions (20, 48, 104, 156, 184, 212, 272, 324, 352) and the plan-usage intro still use main (git checkout main, "Tag sN-done có trên main", "merge vào main"). | Detail 00-1 Cách dùng plan; Detail merge sessions of every step | Default branch is master; read main as master in every merge session. | resolved (D-010) |

## Things that look like issues but are intended

- Detail S0 week 3 creates Catalog and Gateway with `dotnet new web` and hand-written `ApiMarker` / `launchSettings`; `tools/new-service.py` only exists from session 49. Follow the plan.
- Commit messages in the user's repo follow the plan (`s2: reserve endpoint`, one branch per step). The kit's reference repo uses its own convention (`bNNN:` per session, tags `wNN`), see `CLAUDE.md`.
- `ReservationStatus` tombstones (`Sku = "*"`, `LocationId = Guid.Empty`) are intended; every query of held stock filters `Status = Active`.
