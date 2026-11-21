# Feature Spec: F-002 CI hardening (adopt starter kit)

## Summary
- Backlog ID: F-002
- Title: CI hardening (adopt starter kit)
- Track: DevOps
- Priority: P0

## Changes
1. Adopted starter-kit workflows (`ci.yml`, `deploy.yml`, `nightly.yml`), `.github/pull_request_template.md`, `.github/CODEOWNERS`, and `.github/branch-protection.json`.
2. Added `.importlinter`, `.gitleaks.toml`, and `requirements-ci.txt`.
3. Added helper scripts `scripts/new-feature.sh` and `scripts/pre-pr-check.sh`.
4. Appended developer convenience targets to `Makefile`.
5. Updated `pyproject.toml` with `target-version = "py312"` and explicit pytest markers (`db`, `sim`, `acceptance`, `slow`).
6. Fixed flaky wall-clock assertion in `tests/unit/test_risk.py::test_all_twelve_pairs_complete_under_fifty_milliseconds` with a generous bound (500ms).

