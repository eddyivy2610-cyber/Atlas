"""Root DocumentIR combining static, dynamic, verification, and drift models."""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from umldoc.ir.static_model import StaticModelIR
from umldoc.ir.dynamic_model import DynamicModelIR
from umldoc.ir.verification import VerificationSummaryIR, DriftReportIR


class DocumentIR(BaseModel):
    """The canonical top-level Document IR container for UMLdoc."""
    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default="1.0.0", description="IR Schema SemVer specification version")
    project_name: str = Field(..., description="Target project name")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of document creation"
    )
    static_model: Optional[StaticModelIR] = Field(default=None, description="Static class and relationship model")
    dynamic_model: Optional[DynamicModelIR] = Field(default=None, description="Dynamic execution trace sessions")
    verification: Optional[VerificationSummaryIR] = Field(default=None, description="Diagram element verification")
    drift_report: Optional[DriftReportIR] = Field(default=None, description="Commit drift evolution report")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Custom generator and environment metadata")

    def to_json_dict(self) -> Dict[str, Any]:
        """Serialize DocumentIR to standard Python dict matching JSON Schema."""
        return self.model_dump(mode="json", exclude_none=False)

    def to_json_str(self, indent: int = 2) -> str:
        """Serialize DocumentIR to formatted JSON string."""
        return json.dumps(self.to_json_dict(), indent=indent)

    @classmethod
    def from_json_str(cls, json_str: str) -> "DocumentIR":
        """Deserialize DocumentIR from JSON string."""
        return cls.model_validate_json(json_str)

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Export the complete JSON Schema definition for DocumentIR."""
        return cls.model_json_schema()
