import pytest
from pathlib import Path


def test_schema_sql_is_idempotent():
    """Verify that backend/api/db.sql uses IF NOT EXISTS for all statements to guarantee idempotency on PostgreSQL 18."""
    sql_path = Path(__file__).resolve().parents[2] / "backend" / "api" / "db.sql"
    assert sql_path.exists(), f"Schema file not found at {sql_path}"
    content = sql_path.read_text(encoding="utf-8")
    
    # Assert every CREATE TABLE has IF NOT EXISTS
    table_lines = [line.strip() for line in content.splitlines() if line.strip().upper().startswith("CREATE TABLE")]
    assert len(table_lines) > 0
    for line in table_lines:
        assert "IF NOT EXISTS" in line.upper(), f"Table creation missing IF NOT EXISTS: {line}"
        
    # Assert every CREATE INDEX has IF NOT EXISTS
    index_lines = [line.strip() for line in content.splitlines() if line.strip().upper().startswith("CREATE INDEX") or line.strip().upper().startswith("CREATE UNIQUE INDEX")]
    assert len(index_lines) > 0
    for line in index_lines:
        assert "IF NOT EXISTS" in line.upper(), f"Index creation missing IF NOT EXISTS: {line}"


def test_docker_compose_uses_postgres_18():
    """Verify docker-compose.yml uses PostgreSQL 18 image and proper volume path."""
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    assert compose_path.exists()
    content = compose_path.read_text(encoding="utf-8")
    assert "postgres:18" in content
    assert "postgres_data:/var/lib/postgresql" in content
