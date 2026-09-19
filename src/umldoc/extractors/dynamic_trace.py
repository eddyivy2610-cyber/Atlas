"""Dynamic execution tracer using sys.settrace to produce structured Sequence IR."""

import inspect
import os
import sys
import time
from collections import deque
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from umldoc.ir.base import ExceptionSnapshot, ValueSnapshot
from umldoc.ir.dynamic_model import (
    InteractionEventType,
    InteractionIR,
    ParticipantIR,
    TraceSessionIR,
)


def _safe_repr(obj: Any, max_len: int = 60) -> Tuple[str, bool]:
    """Safely format an object representation without invoking dunder methods on uninitialized objects."""
    try:
        t = type(obj)
        if t in (int, float, bool, bytes):
            r = repr(obj)
        elif t is str:
            r = f"'{obj}'" if len(obj) <= max_len else f"'{obj[:max_len]}...'"
            return r, len(obj) > max_len
        elif t is list or t is tuple or t is set or t is dict:
            try:
                r = f"{t.__name__}[{len(obj)}]"
            except Exception:
                r = f"{t.__name__}"
        else:
            r = f"<{t.__name__}>"

        if len(r) > max_len:
            return r[:max_len] + "...", True
        return r, False
    except Exception:
        return f"<{type(obj).__name__}>", False


def _get_type_name(obj: Any) -> str:
    """Get clean type name for an object without invoking getattr."""
    if obj is None:
        return "None"
    return type(obj).__name__


class ExecutionTracer:
    """Traces Python function execution and captures sequence diagram interactions."""

    def __init__(
        self,
        scenario_name: str = "ExecutionTrace",
        entrypoint_name: str = "main",
        include_prefixes: Optional[Set[str]] = None,
        exclude_prefixes: Optional[Set[str]] = None,
    ):
        self.scenario_name = scenario_name
        self.entrypoint_name = entrypoint_name
        self.include_prefixes = include_prefixes or set()
        self.exclude_prefixes = exclude_prefixes or {
            "builtins", "typing", "pytest", "_pytest", "pluggy", "unittest",
            "importlib", "sys", "os", "asyncio", "anyio", "sniffio", "selectors",
            "concurrent", "contextvars", "socket", "ssl", "threading", "queue",
            "urllib", "email", "encodings", "abc", "posixpath", "genericpath",
        }
        self.participants: Dict[str, ParticipantIR] = {}
        self.interactions: List[InteractionIR] = []
        self.call_stack: deque = deque()  # Stack of (participant_id, method_name, start_time, event_id, depth)
        self.sequence_counter: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self._prev_trace: Optional[Callable] = None

    def __enter__(self) -> "ExecutionTracer":
        self.start_time = time.perf_counter()
        self._prev_trace = sys.gettrace()
        sys.settrace(self._global_trace)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        sys.settrace(self._prev_trace)
        self.end_time = time.perf_counter()

    async def __aenter__(self) -> "ExecutionTracer":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    def trace_function(self, func: Callable, *args, **kwargs) -> Any:
        """Run and trace a sync function synchronously."""
        with self:
            return func(*args, **kwargs)

    async def trace_async_function(self, func: Callable, *args, **kwargs) -> Any:
        """Run and trace an async function or coroutine."""
        with self:
            return await func(*args, **kwargs)

    def get_session_ir(self) -> TraceSessionIR:
        """Compile recorded execution events into TraceSessionIR."""
        duration_ms = (self.end_time - self.start_time) * 1000.0 if self.end_time > 0 else 0.0
        return TraceSessionIR(
            session_id=f"trace_{int(self.start_time * 1000)}",
            scenario_name=self.scenario_name,
            entrypoint=self.entrypoint_name,
            duration_ms=round(duration_ms, 3),
            participants=list(self.participants.values()),
            interactions=self.interactions,
            metadata={"total_events": str(len(self.interactions))},
        )

    def _should_trace_frame(self, frame) -> bool:
        """Determine whether frame module and function belongs to traced domain logic."""
        fn_name = frame.f_code.co_name
        # Skip internal Python dispatch and representation dunders that trigger loops on proxies
        if fn_name in {
            "__getattr__", "__getattribute__", "__setattr__", "__delattr__",
            "__dir__", "__hash__", "__repr__", "__str__", "__len__", "__bool__",
            "__instancecheck__", "__subclasscheck__"
        }:
            return False

        module_name = frame.f_globals.get("__name__", "")
        if not module_name:
            filename = frame.f_globals.get("__file__", "")
            if not filename or "site-packages" in filename or "lib" in filename.lower():
                return False

        # Exclude standard library / internal tooling
        for ex in self.exclude_prefixes:
            if module_name == ex or module_name.startswith(f"{ex}."):
                return False

        # If include prefixes specified, check match
        if self.include_prefixes:
            return any(module_name == inc or module_name.startswith(f"{inc}.") for inc in self.include_prefixes)

        # Skip Python stdlib files if inspectable
        filename = frame.f_code.co_filename
        if "site-packages" in filename:
            return False

        return True

    def _get_or_create_participant(self, frame) -> ParticipantIR:
        """Resolve lifeline participant from frame (object instance or module)."""
        instance = frame.f_locals.get("self")
        if instance is None:
            instance = frame.f_locals.get("cls")
        module_name = frame.f_globals.get("__name__", "")

        if instance is not None:
            if isinstance(instance, type):
                cls_name = instance.__name__
                part_id = f"cls_{cls_name}"
                display_name = f"{cls_name} (class)"
                if part_id not in self.participants:
                    self.participants[part_id] = ParticipantIR(
                        id=part_id,
                        name=display_name,
                        class_name=cls_name,
                        module_name=module_name,
                    )
                return self.participants[part_id]
            else:
                cls_name = type(instance).__name__
                inst_id = id(instance)
                part_id = f"{cls_name}_{inst_id & 0xFFFF}"
                display_name = f"{cls_name.lower()}_{inst_id & 0xFFFF}: {cls_name}"
                if part_id not in self.participants:
                    self.participants[part_id] = ParticipantIR(
                        id=part_id,
                        name=display_name,
                        class_name=cls_name,
                        module_name=module_name,
                        instance_id=inst_id,
                    )
                return self.participants[part_id]
        else:
            part_id = f"mod_{module_name.replace('.', '_')}" if module_name else "Client"
            display_name = f"{module_name}" if module_name else "Client"
            if part_id not in self.participants:
                self.participants[part_id] = ParticipantIR(
                    id=part_id,
                    name=display_name,
                    class_name=None,
                    module_name=module_name,
                )
            return self.participants[part_id]

    def _global_trace(self, frame, event: str, arg: Any):
        """Top-level trace handler for call events."""
        if event == "call" and self._should_trace_frame(frame):
            self._handle_call(frame)
            return self._local_trace
        return None

    def _handle_call(self, frame):
        """Process method/function invocation start."""
        caller_part_id = "Client"
        if self.call_stack:
            caller_part_id = self.call_stack[-1][0]
        else:
            if "Client" not in self.participants:
                self.participants["Client"] = ParticipantIR(
                    id="Client",
                    name="Caller / Client",
                )

        callee_part = self._get_or_create_participant(frame)
        fn_name = frame.f_code.co_name
        depth = len(self.call_stack)

        # Capture arguments
        args_dict: Dict[str, ValueSnapshot] = {}
        for var_name in frame.f_code.co_varnames[: frame.f_code.co_argcount]:
            if var_name in frame.f_locals and var_name not in ("self", "cls"):
                val = frame.f_locals[var_name]
                repr_str, is_trunc = _safe_repr(val)
                args_dict[var_name] = ValueSnapshot(
                    type_name=_get_type_name(val),
                    repr_value=repr_str,
                    is_truncated=is_trunc,
                )

        event_id = f"evt_{self.sequence_counter}"
        self.sequence_counter += 1

        interaction = InteractionIR(
            event_id=event_id,
            event_type=InteractionEventType.CALL,
            caller_id=caller_part_id,
            callee_id=callee_part.id,
            method_name=fn_name,
            arguments=args_dict,
            sequence_order=self.sequence_counter,
            call_depth=depth,
            line_number=frame.f_lineno,
        )
        self.interactions.append(interaction)
        self.call_stack.append((callee_part.id, fn_name, time.perf_counter(), event_id, depth, caller_part_id))

    def _local_trace(self, frame, event: str, arg: Any):
        """Internal frame trace handler for return and exception events."""
        if event == "return":
            if self.call_stack:
                callee_id, fn_name, start_t, call_evt_id, depth, caller_id = self.call_stack.pop()
                duration_ms = (time.perf_counter() - start_t) * 1000.0

                repr_str, is_trunc = _safe_repr(arg)
                ret_snap = ValueSnapshot(
                    type_name=_get_type_name(arg),
                    repr_value=repr_str,
                    is_truncated=is_trunc,
                )

                self.sequence_counter += 1
                interaction = InteractionIR(
                    event_id=f"ret_{self.sequence_counter}",
                    event_type=InteractionEventType.RETURN,
                    caller_id=callee_id,
                    callee_id=caller_id,
                    method_name=f"return {fn_name}",
                    return_value=ret_snap,
                    sequence_order=self.sequence_counter,
                    call_depth=depth,
                    duration_ms=round(duration_ms, 3),
                    line_number=frame.f_lineno,
                )
                self.interactions.append(interaction)

        elif event == "exception":
            exc_type, exc_value, _ = arg
            if self.call_stack:
                callee_id, fn_name, start_t, call_evt_id, depth, caller_id = self.call_stack[-1]
                exc_snap = ExceptionSnapshot(
                    type_name=exc_type.__name__ if hasattr(exc_type, "__name__") else str(exc_type),
                    message=str(exc_value),
                    line_number=frame.f_lineno,
                )
                self.sequence_counter += 1
                interaction = InteractionIR(
                    event_id=f"exc_{self.sequence_counter}",
                    event_type=InteractionEventType.EXCEPTION,
                    caller_id=callee_id,
                    callee_id=caller_id,
                    method_name=f"raise {exc_snap.type_name}",
                    exception=exc_snap,
                    sequence_order=self.sequence_counter,
                    call_depth=depth,
                    line_number=frame.f_lineno,
                )
                self.interactions.append(interaction)

        return self._local_trace


def trace_execution(
    scenario_name: str = "TraceScenario",
    include_prefixes: Optional[Set[str]] = None,
) -> Callable:
    """Decorator to trace any sync or async function or test and return/store TraceSessionIR."""
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = ExecutionTracer(
                    scenario_name=scenario_name,
                    entrypoint_name=func.__name__,
                    include_prefixes=include_prefixes,
                )
                async with tracer:
                    result = await func(*args, **kwargs)
                async_wrapper.trace_session = tracer.get_session_ir()
                return result
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = ExecutionTracer(
                    scenario_name=scenario_name,
                    entrypoint_name=func.__name__,
                    include_prefixes=include_prefixes,
                )
                with tracer:
                    result = func(*args, **kwargs)
                sync_wrapper.trace_session = tracer.get_session_ir()
                return result
            return sync_wrapper
    return decorator
