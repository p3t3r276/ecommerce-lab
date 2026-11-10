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

### D-001 · S0 · SPA reads roles from the ID token
- Kind: architecture
- Decided by: user (from Q-s0-01)
- Decision: Each SPA client (`storefront`, `admin`, `pos`) gets a per-client mapper `oidc-usermodel-realm-role-mapper` with claim `realm_access.roles`, ID token only. `libs/auth` reads roles from the ID token claims, so `roleGuard` stays synchronous.
- Overrides: none
- Resolves: none
- Reason: ID token is for the client, access token is for the API; costs one mapper per client. See design/s0.md §Q-s0-01 (option B).
- Date: 2026-11-10

### D-002 · S0 · SPA keeps tokens in sessionStorage
- Kind: architecture
- Decided by: user (from Q-s0-02)
- Decision: `angular-oauth2-oidc` uses its default `sessionStorage`. The guide shows in-memory storage as an optional experiment only.
- Overrides: none
- Resolves: none
- Reason: library default, fast dev loop, no third-party scripts in the lab. See design/s0.md §Q-s0-02 (option A).
- Date: 2026-11-10

### D-003 · S0 · Repository, tooling and build conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-01..C-s0-08 of design/s0.md: `git init -b main` then first commit on `main` before branching `step/s0-foundation`; session 1 installs `Aspire.ProjectTemplates`; `global.json`, `Directory.Build.props`, Central Package Management; `shoplab.slnx`; project table, paths and namespaces; launch profiles `http` on ports 5000/5101.
- Overrides: Detail session 2 (command order of git init / branch / first commit); Detail session 1 (missing Aspire.ProjectTemplates install)
- Resolves: I-15, I-16
- Reason: remove contradictions in the Detail plan and fix the layout every later step depends on.
- Date: 2026-11-10

### D-004 · S0 · AppHost and infrastructure conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-09..C-s0-12 of design/s0.md: resource names (`pg`, `keycloak`, `catalog`, `gateway`, `storefront`, `admin`), 8 databases declared in S0, volumes `shoplab-pg` / `shoplab-keycloak`, Postgres 17, Keycloak with `admin/admin` via parameter and realm import from `docker/keycloak`, and the WithReference/WaitFor wiring.
- Overrides: none
- Resolves: none
- Reason: completes v3 and Detail with exact names and versions.
- Date: 2026-11-10

### D-005 · S0 · Keycloak realm conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-13..C-s0-16 of design/s0.md: reference ships a curated `docker/keycloak/shoplab-realm.json` with fixed user IDs as a shared file (replaces the user's own export); admin username is `admin@shoplab.local`; audience `gateway` via `gateway-audience` mapper per client; `accessTokenLifespan = 900`, registration disabled.
- Overrides: Detail session 7 (hand-created users and exported realm; admin username `admin`)
- Resolves: I-12, I-14
- Reason: Customer.Id = Keycloak `sub` needs stable IDs across machines; username mismatch between plans.
- Date: 2026-11-10

### D-006 · S0 · .NET auth, gateway and telemetry conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-17..C-s0-22 of design/s0.md: `Auth:Authority` / `Auth:Audience` keys and JwtBearer claim mapping; explicit `RequireAuthorization(AuthPolicies.Authenticated)`, no fallback policy, no gateway CORS; `yarp.json` route and cluster rules; OpenTelemetry sources/meters and resilience; OpenAPI + Scalar (Development only, build-time document in `contracts/openapi`, git-ignored); `http/ping.http` variables.
- Overrides: none
- Resolves: none
- Reason: completes the plans with exact keys, names and behaviours.
- Date: 2026-11-10

### D-007 · S0 · Frontend conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-23..C-s0-28 of design/s0.md: Nx workspace at `src/Web` with pinned versions, libs `@shoplab/auth` and `@shoplab/api-client`; `scaffold-angular-app.sh` run from repo root; dev proxy file `proxy.conf.mjs` reading `services__gateway__http__0` with fallback; AppHost runs the apps on fixed ports 4200/4300; fixed Keycloak issuer constant; admin routing with `roleGuard('admin')` and public `forbidden` page.
- Overrides: Detail session 14 (proxy file name `proxy.conf.json`); Detail session 13 (script directory)
- Resolves: I-13
- Reason: a JSON file cannot read an environment variable; Keycloak redirect URIs require fixed ports.
- Date: 2026-11-10

### D-008 · S0 · Tests and tools conventions
- Kind: convention
- Decided by: agent
- Decision: Conventions C-s0-29..C-s0-30 of design/s0.md: `tests/Directory.Build.props`, `PostgresFixture` and `SmokeTests` in `Catalog.Tests` (moved to TestKit in S1); `tools/*.sh` use bash, `set -euo pipefail` and python3, no jq.
- Overrides: none
- Resolves: none
- Reason: completes the testing plan with concrete locations and tool rules.
- Date: 2026-11-10

### D-009 · S0 · Contracts of S0
- Kind: contract
- Decided by: agent
- Decision: Contracts of S0 are defined in design/s0.md §Contracts (BuildingBlocks C#, configuration keys, HTTP API, Keycloak realm `shoplab`, frontend libraries, test fixture, tool scripts).
- Overrides: none
- Resolves: none
- Reason: single reference for builder, guide writer and reviewer.
- Date: 2026-11-10

### D-010 · all · Default branch is master
- Kind: convention
- Decided by: user
- Decision: The default branch of the user's repo and the reference is `master`, not `main`. S0 starts with `git init -b master` and the first commit on `master` before branching `step/s0-foundation`; every step-end merge is `git checkout master && git merge --no-ff step/sN-<name>`. Guides and reviews write `master` wherever the plans write `main`.
- Overrides: Detail session 2 ("Commit đầu tiên trên master"), Detail merge sessions 20, 48, 104, 156, 184, 212, 272, 324, 352 and plans/detail/00-1-cach-dung-plan.md (`merge vào main`); supersedes the branch name in D-003
- Resolves: none
- Reason: the user's repositories use `master` as the default branch.
- Date: 2026-11-10

### D-011 · S0 · Postgres 18 instead of 17
- Kind: architecture
- Decided by: user
- Decision: Postgres major version is 18 everywhere. AppHost uses Aspire's default Postgres image (`postgres:18.3` in Aspire 13.6.4) without `.WithImageTag`; Testcontainers use `postgres:18-alpine`; the S0 smoke test asserts `server_version` starts with `18` (`Connect_FreshContainer_ReturnsPostgres18`). The volume `shoplab-pg` created with 17 is deleted and recreated.
- Overrides: v3 stack row 5 (Postgres 17); Detail testing §2 (`postgres:17-alpine`); supersedes the Postgres version in D-004 (C-s0-10)
- Resolves: none
- Reason: Aspire 13.6 ships Postgres 18 by default; following the default avoids pinning an older major. Note: the official 18 image changed the data directory layout, so a 17 volume cannot be reused.
- Date: 2026-11-10

### D-012 · all · Reference branches and step-end merge
- Kind: convention
- Decided by: user
- Decision: The reference repo uses the same branch flow as the plan. Each step is built on `step/sN-<name>` (branch names from Detail). In the gate session, only if the gate in `design/sN.md` passes, the builder runs `git checkout master && git merge --no-ff step/sN-<name>`, tags `sN-done` on the merge commit, then creates `step/s(N+1)-<name>` from `master`. If the gate fails: no merge, no `sN-done` tag. Tags `wNN` stay on the step branch commits.
- Overrides: none (completes CLAUDE.md "Reference repo conventions", which only defined tags)
- Resolves: none
- Reason: `master` of the reference always mirrors the user's repo at the same point and only holds steps that passed their gate.
- Date: 2026-11-10
