"""Resilience contract tests: validates behavior across every row of the fault-handling matrix."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from core.models import FuelType, Snapshot
from core.sim_client import SimulatorClient, SimulatorError
from worker.forecaster import RemoteForecastError, RemoteForecaster


@pytest.mark.asyncio
async def test_fault_matrix_predictor_5xx_opens_circuit_breaker():
    """Predictor 500 triggers circuit breaker and raises breaker_open on subsequent calls."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": "internal"})
    )
    forecaster = RemoteForecaster(
        "http://predictor:8103",
        failure_threshold=2,
        reset_after_s=10.0,
        transport=mock_transport,
    )
    snap = MagicMock(spec=Snapshot)
    station = MagicMock()
    station.id = "station-mirpur"
    fuel = FuelType.DIESEL

    with pytest.raises(RemoteForecastError) as exc1:
        await forecaster.forecast(snap, station, fuel, seed=1)
    assert exc1.value.reason == "predictor_5xx"

    with pytest.raises(RemoteForecastError) as exc2:
        await forecaster.forecast(snap, station, fuel, seed=1)
    assert exc2.value.reason == "predictor_5xx"

    # Circuit breaker is now open
    with pytest.raises(RemoteForecastError) as exc3:
        await forecaster.forecast(snap, station, fuel, seed=1)
    assert exc3.value.reason == "breaker_open"


@pytest.mark.asyncio
async def test_fault_matrix_simulator_503_raises_transient_error():
    """Simulator 503 error is classified as transient by sim client."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"error": "temporarily unavailable"})
    )
    client = SimulatorClient("http://sim:8000", transport=mock_transport)
    with pytest.raises(SimulatorError) as exc:
        await client.get_instance()
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_fault_matrix_malformed_payload_rejected_cleanly():
    """Malformed simulator JSON does not crash the client and raises an informative error."""
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"invalid json { {")
    )
    client = SimulatorClient("http://sim:8000", transport=mock_transport)
    with pytest.raises(SimulatorError):
        await client.get_instance()


@pytest.mark.asyncio
async def test_fault_matrix_timeout_classified_as_unavailable():
    """Simulator network timeout is caught and cleanly handled."""
    def timeout_handler(request):
        raise httpx.ReadTimeout("timed out")

    mock_transport = httpx.MockTransport(timeout_handler)
    client = SimulatorClient("http://sim:8000", transport=mock_transport)
    with pytest.raises(SimulatorError) as exc:
        await client.get_instance()
    assert exc.value.status_code == 504

