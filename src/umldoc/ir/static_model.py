"""Static architecture models for classes, methods, attributes, and relationships."""

from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field
from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    SourceLocation,
)


class ParameterIR(BaseModel):
    """Method/Function parameter specification."""
    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Parameter name")
    type_annotation: Optional[str] = Field(default=None, description="Stringified type annotation")
    default_value: Optional[str] = Field(default=None, description="Default argument value if any")
    is_variadic: bool = Field(default=False, description="True for *args")
    is_keyword: bool = Field(default=False, description="True for **kwargs")
    is_keyword_only: bool = Field(default=False, description="True for keyword-only parameters")


class AttributeIR(BaseModel):
    """Class or instance attribute."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique attribute identifier (e.g. module.Class.attr)")
    name: str = Field(..., description="Attribute variable name")
    type_annotation: Optional[str] = Field(default=None, description="Type annotation string")
    default_value: Optional[str] = Field(default=None, description="Default initializer value expression")
    visibility: MemberVisibility = Field(default=MemberVisibility.PUBLIC, description="Public/protected/private")
    is_class_variable: bool = Field(default=False, description="True if defined at class level")
    is_property: bool = Field(default=False, description="True if managed via @property")
    docstring: Optional[str] = Field(default=None, description="Attribute docstring or inline comment")
    source_location: Optional[SourceLocation] = Field(default=None, description="Source code coordinates")


class MethodIR(BaseModel):
    """Class method declaration."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique method identifier (e.g. module.Class.method)")
    name: str = Field(..., description="Method name")
    parameters: List[ParameterIR] = Field(default_factory=list, description="Method parameter list")
    return_type: Optional[str] = Field(default=None, description="Return type annotation")
    decorators: List[str] = Field(default_factory=list, description="List of applied decorator names")
    visibility: MemberVisibility = Field(default=MemberVisibility.PUBLIC, description="Member visibility")
    is_async: bool = Field(default=False, description="Whether method is an async coroutine")
    is_static: bool = Field(default=False, description="True if decorated with @staticmethod")
    is_classmethod: bool = Field(default=False, description="True if decorated with @classmethod")
    is_abstract: bool = Field(default=False, description="True if marked with @abstractmethod")
    is_property: bool = Field(default=False, description="True if getter/setter property")
    docstring: Optional[str] = Field(default=None, description="Method docstring")
    source_location: Optional[SourceLocation] = Field(default=None, description="Source code location")


class FunctionIR(BaseModel):
    """Module-level standalone function."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique function identifier (e.g. module.function)")
    name: str = Field(..., description="Function name")
    parameters: List[ParameterIR] = Field(default_factory=list, description="Parameter list")
    return_type: Optional[str] = Field(default=None, description="Return type annotation")
    decorators: List[str] = Field(default_factory=list, description="Decorators")
    is_async: bool = Field(default=False, description="True if async def")
    docstring: Optional[str] = Field(default=None, description="Function docstring")
    source_location: Optional[SourceLocation] = Field(default=None, description="Source code location")


class ClassIR(BaseModel):
    """Class / Interface / Protocol architecture element."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique qualified class identifier (e.g. pkg.module.ClassName)")
    name: str = Field(..., description="Class name")
    qualified_name: str = Field(..., description="Fully qualified name within project")
    kind: ElementKind = Field(default=ElementKind.CLASS, description="CLASS, PROTOCOL, DATACLASS, ENUM, etc.")
    bases: List[str] = Field(default_factory=list, description="Names or IDs of base classes / interfaces")
    decorators: List[str] = Field(default_factory=list, description="List of decorators on class")
    is_abstract: bool = Field(default=False, description="True if inherits from ABC or contains abstract methods")
    is_protocol: bool = Field(default=False, description="True if inherits from typing.Protocol")
    is_dataclass: bool = Field(default=False, description="True if decorated with @dataclass")
    is_enum: bool = Field(default=False, description="True if inherits from Enum")
    docstring: Optional[str] = Field(default=None, description="Class docstring")
    attributes: List[AttributeIR] = Field(default_factory=list, description="Attributes and fields")
    methods: List[MethodIR] = Field(default_factory=list, description="Declared methods")
    source_location: Optional[SourceLocation] = Field(default=None, description="Source code location")


class RelationIR(BaseModel):
    """Typed relationship between classes or modules."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique relationship identifier")
    source_id: str = Field(..., description="Source element ID (e.g. subclass or container)")
    target_id: str = Field(..., description="Target element ID (e.g. superclass or component)")
    relation_type: RelationType = Field(..., description="INHERITANCE, COMPOSITION, AGGREGATION, etc.")
    label: Optional[str] = Field(default=None, description="Optional label describing the relationship")
    multiplicity_source: Optional[str] = Field(default=None, description="Multiplicity at source end (e.g. '1')")
    multiplicity_target: Optional[str] = Field(default=None, description="Multiplicity at target end (e.g. '0..*')")
    source_location: Optional[SourceLocation] = Field(default=None, description="Where relation is established")


class ModuleIR(BaseModel):
    """Python module representation."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique module identifier (e.g. pkg.submodule)")
    name: str = Field(..., description="Short module name")
    qualified_name: str = Field(..., description="Full dotted module path")
    file_path: str = Field(..., description="Path to file")
    docstring: Optional[str] = Field(default=None, description="Module docstring")
    classes: List[ClassIR] = Field(default_factory=list, description="Classes declared in this module")
    functions: List[FunctionIR] = Field(default_factory=list, description="Module-level functions")
    imports: List[str] = Field(default_factory=list, description="List of imported module/symbol names")
    source_location: Optional[SourceLocation] = Field(default=None, description="Module source location")


class StaticModelIR(BaseModel):
    """Root static architecture model for a codebase snapshot."""
    model_config = ConfigDict(frozen=True)

    project_name: str = Field(..., description="Project name")
    root_path: str = Field(default=".", description="Root directory path")
    commit_hash: Optional[str] = Field(default=None, description="Git commit hash")
    modules: List[ModuleIR] = Field(default_factory=list, description="Extracted modules")
    classes: List[ClassIR] = Field(default_factory=list, description="All flattened classes for quick lookup")
    relations: List[RelationIR] = Field(default_factory=list, description="All static relationships")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional extractor metadata")
