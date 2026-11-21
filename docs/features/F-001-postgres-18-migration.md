# Feature Spec: F-001 PostgreSQL 18 migration

## Summary
- Backlog ID: F-001
- Title: PostgreSQL 18 migration
- Track: DevOps / Database
- Priority: P0

## Changes
1. Updated `docker-compose.yml` PostgreSQL image from `postgres:16.8-alpine` to `postgres:18-alpine`.
2. Updated volume mount path to `/var/lib/postgresql` as required by PostgreSQL 18 container layout.
3. Verified `backend/api/db.sql` schema idempotency (all `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`).
4. Added integration tests in `tests/integration/test_db_migration.py`.

