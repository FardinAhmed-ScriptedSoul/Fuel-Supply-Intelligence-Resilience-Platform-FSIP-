"""Unit tests for operator identity, per-operator tokens, and token hardening."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes.recommendations import require_operator_token


def test_single_operator_token_match(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("OPERATOR_TOKEN", "secret-token-123")
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)

    actor = require_operator_token("secret-token-123")
    assert actor == "operator"


def test_multi_operator_tokens_resolves_named_actor(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("OPERATOR_TOKENS", "fardin:tok-fardin-99,lead_ops:tok-ops-77")
    monkeypatch.delenv("OPERATOR_TOKEN", raising=False)

    assert require_operator_token("tok-fardin-99") == "fardin"
    assert require_operator_token("tok-ops-77") == "lead_ops"


def test_invalid_token_raises_401(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("OPERATOR_TOKEN", "correct-token")

    with pytest.raises(HTTPException) as exc:
        require_operator_token("wrong-token")
    assert exc.value.status_code == 401


def test_missing_token_raises_401(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("OPERATOR_TOKEN", "correct-token")

    with pytest.raises(HTTPException) as exc:
        require_operator_token("")
    assert exc.value.status_code == 401


def test_unconfigured_tokens_raises_503(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("OPERATOR_TOKEN", raising=False)
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)

    with pytest.raises(HTTPException) as exc:
        require_operator_token("some-token")
    assert exc.value.status_code == 503


def test_non_local_refuses_default_token(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("OPERATOR_TOKEN", "change-me")
    monkeypatch.delenv("OPERATOR_TOKENS", raising=False)

    with pytest.raises(HTTPException) as exc:
        require_operator_token("change-me")
    assert exc.value.status_code == 503
    assert "Startup refusal" in exc.value.detail

