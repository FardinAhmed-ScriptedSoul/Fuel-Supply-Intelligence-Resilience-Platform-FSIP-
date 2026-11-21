# Feature Spec: F-018 E2E journeys (Playwright)

## Summary
- Backlog ID: F-018
- Title: E2E journeys (Playwright)
- Track: QA / Frontend
- Priority: P1

## Implementation
1. Configured Playwright runner in `web/playwright.config.ts`.
2. Created end-to-end operator journey tests in `web/e2e/operator-journey.spec.ts`:
   - Verification of permanent "SIMULATED DATA" operator banner.
   - Verification of shortage risk navigation and trajectory drawer.
   - Verification of human approval decision controls.
