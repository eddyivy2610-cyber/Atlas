"""Dynamic execution trace and sequence diagram IR models."""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field
from umldoc.ir.base import ValueSnapshot, ExceptionSnapshot


class InteractionEventType(str, Enum):
    """Type of interaction event occurring during runtime execution."""
    CALL = "call"
    RETURN = "return"
    EXCEPTION = "exception"
    YIELD = "yield"


class ParticipantIR(BaseModel):
    """A lifeline / actor in a sequence diagram trace."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique participant lifeline identifier")
    name: str = Field(..., description="Display name for the lifeline (e.g. 'client: Client')")
    class_name: Optional[str] = Field(default=None, description="Class name if object instance")
    module_name: Optional[str] = Field(default=None, description="Module where participant is declared")
    instance_id: Optional[int] = Field(default=None, description="Object memory ID / id() to distinguish instances")


class InteractionIR(BaseModel):
    """An interaction message (call, return, or exception propagation) between lifelines."""
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(..., description="Unique interaction ID")
    event_type: InteractionEventType = Field(default=InteractionEventType.CALL, description="Event type")
    caller_id: str = Field(..., description="Participant ID of the caller / sender")
    callee_id: str = Field(..., description="Participant ID of the callee / receiver")
    method_name: str = Field(..., description="Name of the invoked method or function")
    arguments: Dict[str, ValueSnapshot] = Field(default_factory=dict, description="Captured argument snapshots")
    return_value: Optional[ValueSnapshot] = Field(default=None, description="Captured return value snapshot")
    exception: Optional[ExceptionSnapshot] = Field(default=None, description="Exception details if raised")
    sequence_order: int = Field(..., ge=0, description="Global deterministic execution sequence index")
    call_depth: int = Field(default=0, ge=0, description="Stack depth of the call activation")
    duration_ms: Optional[float] = Field(default=None, ge=0.0, description="Elapsed execution time in milliseconds")
    line_number: Optional[int] = Field(default=None, description="Source code line triggering the interaction")


class TraceSessionIR(BaseModel):
    """A single execution trace session corresponding to a test case or scenario."""
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(..., description="Unique trace session identifier")
    scenario_name: str = Field(..., description="Name of the test or executed scenario")
    entrypoint: str = Field(..., description="Entrypoint function or method (e.g. 'test_query_execution')")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Total session duration in ms")
    participants: List[ParticipantIR] = Field(default_factory=list, description="Ordered participant lifelines")
    interactions: List[InteractionIR] = Field(default_factory=list, description="Chronological sequence events")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Session runtime environment info")


class DynamicModelIR(BaseModel):
    """Collection of dynamic trace sessions for a project snapshot."""
    model_config = ConfigDict(frozen=True)

    project_name: str = Field(..., description="Project name")
    commit_hash: Optional[str] = Field(default=None, description="Git commit hash")
    sessions: List[TraceSessionIR] = Field(default_factory=list, description="All recorded trace sessions")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Environment and tracer configuration")
