"""Stress tests verifying dynamic tracing on async / coroutine workflows in httpx."""

import pytest
import httpx
from umldoc.extractors.dynamic_trace import ExecutionTracer, trace_execution
from umldoc.ir.dynamic_model import InteractionEventType


@pytest.mark.asyncio
async def test_httpx_async_client_tracing():
    """Trace asynchronous HTTP request and response lifecycle in httpx."""
    # Mock transport responding to requests
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/data":
            return httpx.Response(200, json={"status": "success", "items": [1, 2, 3]})
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)

    tracer = ExecutionTracer(
        scenario_name="HTTPX_Async_Get",
        entrypoint_name="async_request_flow",
        include_prefixes={"httpx"},
    )

    async with tracer:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/data")
            data = response.json()

    assert response.status_code == 200
    assert data["status"] == "success"

    session = tracer.get_session_ir()
    assert session.scenario_name == "HTTPX_Async_Get"
    assert len(session.participants) >= 2
    assert len(session.interactions) >= 4

    # Verify captured lifelines and interactions
    participant_classes = {p.class_name for p in session.participants if p.class_name}
    assert "AsyncClient" in participant_classes or "Response" in participant_classes

    method_names = [e.method_name for e in session.interactions if e.event_type == InteractionEventType.CALL]
    assert any("get" in m or "request" in m or "json" in m for m in method_names)


@pytest.mark.asyncio
async def test_async_decorator_tracing():
    """Verify trace_execution decorator on native async def coroutines."""
    @trace_execution(scenario_name="AsyncCalculation", include_prefixes={"tests"})
    async def calculate(a: int, b: int) -> int:
        return a + b

    result = await calculate(10, 25)
    assert result == 35

    session = calculate.trace_session
    assert session.scenario_name == "AsyncCalculation"
    assert len(session.interactions) >= 2
