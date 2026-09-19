"""Unit tests for AST static architecture extractor."""

from pathlib import Path
from umldoc.extractors.static_ast import ASTStaticExtractor
from umldoc.ir.base import ElementKind, RelationType


def test_ast_extractor_sample_codebase():
    """Test static extraction on embedded sample codebase."""
    sample_dir = Path(__file__).parent / "sample_codebase"
    extractor = ASTStaticExtractor(project_name="SampleTest", root_path=str(sample_dir))

    static_model = extractor.extract_directory(target_dir=str(sample_dir))

    assert static_model.project_name == "SampleTest"
    assert len(static_model.modules) >= 2

    # Map extracted classes by name
    class_map = {c.name: c for c in static_model.classes}
    assert "UserRole" in class_map
    assert "StorageBackend" in class_map
    assert "UserProfile" in class_map
    assert "InMemoryStorage" in class_map
    assert "UserService" in class_map

    # Validate UserRole enum
    role_cls = class_map["UserRole"]
    assert role_cls.kind == ElementKind.ENUM
    assert role_cls.is_enum is True

    # Validate StorageBackend abstract interface
    storage_interface = class_map["StorageBackend"]
    assert storage_interface.is_abstract is True
    method_names = {m.name for m in storage_interface.methods}
    assert "save" in method_names
    assert "fetch" in method_names

    # Validate UserProfile dataclass
    profile_cls = class_map["UserProfile"]
    assert profile_cls.kind == ElementKind.DATACLASS
    attr_names = {a.name for a in profile_cls.attributes}
    assert "user_id" in attr_names
    assert "username" in attr_names
    assert "email" in attr_names

    # Validate InMemoryStorage implementation
    mem_storage = class_map["InMemoryStorage"]
    assert "StorageBackend" in mem_storage.bases

    # Validate UserService dependencies
    user_svc = class_map["UserService"]
    svc_methods = {m.name: m for m in user_svc.methods}
    assert "register_user" in svc_methods
    reg_m = svc_methods["register_user"]
    param_names = [p.name for p in reg_m.parameters]
    assert param_names == ["user_id", "username", "email", "role"]

    # Validate inferred relationships
    rel_types = [r.relation_type for r in static_model.relations]
    assert RelationType.REALIZATION in rel_types or RelationType.INHERITANCE in rel_types
