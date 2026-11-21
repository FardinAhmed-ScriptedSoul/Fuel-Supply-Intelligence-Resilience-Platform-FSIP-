# __ID__ — __NAME__

| | |
|---|---|
| **Branch** | `__BRANCH__` |
| **Owner** | _name / agent session_ |
| **Created** | __DATE__ |
| **Status** | DRAFT → IN PROGRESS → IN REVIEW → MERGED |
| **Backlog entry** | `docs/process/BACKLOG.md#__ID__` |
| **Design refs** | `docs/design/FINAL_SYSTEM_DESIGN.md` §…, `docs/design/ARCHITECTURE.md` §… |

## 1. Goal and non-goals
- **Goal:** _one sentence of operator-visible value_
- **Non-goals:** _what this PR deliberately does not do_

## 2. Acceptance criteria (Given / When / Then) — each maps to a test
| # | Criterion | Test (`level :: path :: name`) |
|---|---|---|
| A1 | Given … When … Then … | unit :: tests/unit/… :: test_… |
| A2 | | integration :: … |
| A3 | | acceptance :: … |

## 3. Design notes
- **Modules touched:** _core / api / worker / predictor / web_ (respect `.importlinter`)
- **Contracts:** _API routes (request/response), DB changes (additive SQL), simulator interactions_
- **Time model:** _wall-clock vs sim ticks used here_
- **Assumptions:** _anything not verified against the live simulator_

## 4. Failure modes and resilience
| Dependency / input | Failure | Behavior | Test |
|---|---|---|---|
| simulator | 503 / latency / stale / malformed | | |
| database | unavailable | | |
| predictor | down / slow | | |

## 5. Observability
- **Metrics added/changed:** _name{labels}_
- **Logs/events:** _event names, fields (no secrets)_
- **Alerts / UI banners affected:**

## 6. Security checklist (see `docs/process/SECURITY_AND_REVIEW_POLICY.md` §3)
- [ ] Input validated at the boundary
- [ ] Authorization on mutations
- [ ] No secrets in code or logs
- [ ] No new dependency (or vetted per policy)
- [ ] Errors don't leak internals
- [ ] LLM input/output constrained (if applicable)

## 7. Test plan and evidence (paste real output)
| Level | Command | Result |
|---|---|---|
| Unit | `make test-unit` | |
| Integration | `make test-int` | |
| E2E | `make test-e2e` | |
| Acceptance | `make test-acc` | |
| Architecture | `make lint-arch` | |
| Security | `make security` | |
| Pre-PR gate | `make pre-pr` | |

## 8. Rollout and rollback
- **Deploy notes:** _migrations, env vars, flags_
- **Rollback:** _revert commit / Render rollback / flag off_

## 9. Deviations and decisions
_Log any deviation from the design docs here and, if it changes a locked decision, open an ADR._
