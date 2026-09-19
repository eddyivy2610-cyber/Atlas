"""Regression tests verifying tracer resilience against __getattr__ loops, metaclasses, and custom proxies."""

import pytest
from umldoc.extractors.dynamic_trace import ExecutionTracer


class DangerousProxy:
    """A proxy class that raises or recurses if __getattr__, __len__, or __bool__ are called naively."""

    def __init__(self):
        # Missing attribute on purpose
        pass

    def __getattr__(self, name):
        if name == "_internal_state":
            # If tracer accesses _internal_state on uninitialized object, it triggers __getattr__
            return getattr(self, "_fallback_target")
        raise AttributeError(f"No attribute {name}")

    def __len__(self):
        # Custom len that accesses a missing attribute
        return len(self._internal_state)

    def __bool__(self):
        # Custom bool that calls __len__
        return len(self) > 0

    def compute(self, x: int) -> int:
        return x * 2


class MetaclassSample(type):
    """Custom metaclass with custom attribute interceptor."""
    def __getattr__(cls, name):
        if name.startswith("meta_"):
            return f"handled_{name}"
        raise AttributeError(name)


class CustomMetaClassInstance(metaclass=MetaclassSample):
    @classmethod
    def execute(cls, val: str) -> str:
        return f"done_{val}"


def test_tracer_resilience_on_dangerous_proxy():
    """Verify tracer executes cleanly on classes with explosive __getattr__ / __len__ hooks."""
    proxy = DangerousProxy()

    tracer = ExecutionTracer(
        scenario_name="DangerousProxyTest",
        entrypoint_name="proxy_flow",
        include_prefixes={"tests"},
    )

    with tracer:
        res = proxy.compute(21)

    assert res == 42
    session = tracer.get_session_ir()
    assert session.scenario_name == "DangerousProxyTest"
    assert len(session.interactions) >= 2


def test_tracer_resilience_on_metaclasses():
    """Verify tracer runs on classes with custom metaclass dispatch."""
    tracer = ExecutionTracer(
        scenario_name="MetaclassTest",
        entrypoint_name="meta_flow",
        include_prefixes={"tests"},
    )

    with tracer:
        res = CustomMetaClassInstance.execute("sample")

    assert res == "done_sample"
    session = tracer.get_session_ir()
    assert len(session.interactions) >= 2
