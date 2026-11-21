## Feature
**ID / branch:** `F-___` / `type/F-___-name`  ·  **Spec:** `docs/features/F-___-name.md`
**One-line value to the operator:**

## What changed and why
-

## Acceptance criteria (copy from the spec; tick when a test proves it)
- [ ] A1 —
- [ ] A2 —
- [ ] A3 —

## Test evidence (paste real output, not "passes locally")
| Level | Command | Result |
|---|---|---|
| Unit | `make test-unit` | |
| Integration | `make test-int` | |
| E2E | `make test-e2e` (or "n/a: no UI/flow change") | |
| Acceptance | `make test-acc` (or "n/a: reason") | |
| Architecture | `make lint-arch` | |
| Pre-PR gate | `make pre-pr` summary | |

## Resilience and observability
- [ ] Every new external call has timeout + retry policy + defined degraded behavior (and a test)
- [ ] New metrics/logs added (names: ) and no secrets/PII in logs
- [ ] UI shows the degraded state where relevant (STALE / FALLBACK / APPROVALS DISABLED)

## Security (policy §3)
- [ ] Input validated at the boundary · [ ] authz on mutating routes · [ ] no secrets in diff or logs
- [ ] No new dependency — or it was vetted (source, license, `pip-audit`/`npm audit`) and is justified here:
- [ ] Errors do not leak internals · [ ] LLM inputs/outputs constrained (if touched)

## Safety invariants (tick or write n/a)
- [ ] No path from compute to dispatch without a persisted human decision
- [ ] In-transit / scheduled supply never counted as inventory
- [ ] Changed request body ⇒ new idempotency key (never mutate a stored body)

## Docs
- [ ] Spec updated (evidence, deviations) · [ ] `docs/PROGRESS.md` entry · [ ] ADR opened if a locked decision changed

## Screenshots / recordings (UI changes)

## Risk and rollback
**Risk:** low / medium / high — **Rollback:** revert this PR / flag / Render rollback

## Reviewer guide
**Start with:** _file or test_ · **Hardest part:** _..._ · **Not in scope:** _..._
