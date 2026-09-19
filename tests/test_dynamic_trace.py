"""Unit tests for dynamic sys.settrace execution tracer."""

import pytest
from tests.sample_codebase.models import InMemoryStorage, UserRole
from tests.sample_codebase.service import UserService
from umldoc.extractors.dynamic_trace import ExecutionTracer, trace_execution
from umldoc.ir.dynamic_model import InteractionEventType


def test_dynamic_tracer_workflow():
    """Test tracing a real multi-object execution workflow."""
    storage = InMemoryStorage()
    service = UserService(storage=storage)

    tracer = ExecutionTracer(
        scenario_name="TestRegisterAndFetch",
        entrypoint_name="user_workflow",
        include_prefixes={"tests.sample_codebase"},
    )

    with tracer:
        user = service.register_user("u1", "alice", "alice@example.com", UserRole.ADMIN)
        fetched = service.get_user("u1")

    assert user.username == "alice"
    assert fetched.email == "alice@example.com"

    session = tracer.get_session_ir()
    assert session.scenario_name == "TestRegisterAndFetch"
    assert len(session.participants) >= 2
    assert len(session.interactions) >= 4

    # Verify interaction event sequence
    call_events = [e for e in session.interactions if e.event_type == InteractionEventType.CALL]
    method_names = [e.method_name for e in call_events]

    assert "register_user" in method_names
    assert "save" in method_names
    assert "get_user" in method_names
    assert "fetch" in method_names


def test_dynamic_tracer_exception_handling():
    """Test capturing exceptions and failure paths in sequence traces."""
    storage = InMemoryStorage()
    service = UserService(storage=storage)

    tracer = ExecutionTracer(
        scenario_name="TestExceptionWorkflow",
        entrypoint_name="error_workflow",
        include_prefixes={"tests.sample_codebase"},
    )

    with tracer:
        try:
            service.register_user("u2", "", "bad@example.com")
        except ValueError:
            pass

    session = tracer.get_session_ir()
    exc_events = [e for e in session.interactions if e.event_type == InteractionEventType.EXCEPTION]
    assert len(exc_events) >= 1
    assert exc_events[0].exception.type_name == "ValueError"
    assert "Username cannot be empty" in exc_events[0].exception.message
