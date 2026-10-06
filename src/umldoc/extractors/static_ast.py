"""AST-based static architecture extractor for Python codebases."""

import ast
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from umldoc.ir.base import (
    ElementKind,
    MemberVisibility,
    RelationType,
    SourceLocation,
)
from umldoc.ir.static_model import (
    AttributeIR,
    ClassIR,
    FunctionIR,
    MethodIR,
    ModuleIR,
    ParameterIR,
    RelationIR,
    StaticModelIR,
)


def _compute_hash(content: str) -> str:
    """Compute SHA-256 hash for content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_visibility(name: str) -> MemberVisibility:
    """Determine visibility from Python naming convention."""
    if name.startswith("__") and not name.endswith("__"):
        return MemberVisibility.PRIVATE
    elif name.startswith("_") and not name.endswith("__"):
        return MemberVisibility.PROTECTED
    return MemberVisibility.PUBLIC


def _unparse_ast_node(node: Optional[ast.AST]) -> Optional[str]:
    """Safely convert an AST node to source string."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


DEFAULT_EXCLUDES: Set[str] = {
    # Virtual environments & package managers
    "venv", ".venv", "env", ".env", "virtualenv", ".virtualenv",
    "site-packages", "node_modules", "bower_components",
    "lib", "lib64", "include", "scripts",
    # Build & distribution
    "build", "dist", "target", "out", "bin", "obj",
    "egg-info", ".eggs",
    # Version control & IDE
    ".git", ".svn", ".hg", ".github", ".gitlab", ".vscode", ".idea",
    # Caches & temporary data
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".tox", "htmlcov", ".coverage", "cache", ".cache", "tmp", "temp",
    # Non-system assets & documentation
    "static", "templates", "public", "assets", "media", "uploads", "data",
    "docs", "doc", "documentation", "guide", "manual",
    # Tests & fixtures (should not be included in production system architecture)
    "tests", "test", "testing", "fixtures", "mocks", "spec", "specs",
    # Database migrations boilerplate
    "migrations",
}


class ASTStaticExtractor:
    """Extracts static UML architectural models directly from Python source code AST."""

    def __init__(self, project_name: str, root_path: str = "."):
        self.project_name = project_name
        self.root_path = Path(root_path).resolve()
        self.modules: List[ModuleIR] = []
        self.classes: List[ClassIR] = []
        self.relations: List[RelationIR] = []
        self._class_lookup: Dict[str, ClassIR] = {}
        self._class_calls: List[Dict[str, Any]] = []

    @staticmethod
    def is_test_file(filename: str) -> bool:
        """Check whether a python file is a test/mock file rather than production system code."""
        name_lower = filename.lower()
        if not name_lower.endswith(".py"):
            return True
        stem = name_lower[:-3]
        if stem.startswith("test_") or stem.endswith("_test") or stem == "test":
            return True
        if stem.startswith("tests_") or stem.endswith("_tests") or stem == "tests":
            return True
        if stem.startswith("mock_") or stem.startswith("fixture_"):
            return True
        if stem in ("conftest", "generate_test_data", "test_backend", "setup"):
            return True
        return False

    def extract_directory(
        self,
        target_dir: Optional[str] = None,
        exclude_dirs: Optional[Set[str]] = None,
        filter_tests: bool = True,
    ) -> StaticModelIR:
        """Extract static architecture across all system Python files in directory tree."""
        search_path = Path(target_dir).resolve() if target_dir else self.root_path
        excludes = {d.lower() for d in (exclude_dirs or DEFAULT_EXCLUDES)}

        py_files: List[Path] = []
        for root, dirs, files in os.walk(search_path):
            # Exclude non-system directories case-insensitively and hidden folders
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d.lower() not in excludes
                and not d.lower().endswith(".egg-info")
                and not d.lower().endswith("-dist-info")
            ]
            for file in files:
                if not file.endswith(".py") or file.startswith("."):
                    continue
                if filter_tests and self.is_test_file(file):
                    continue
                py_files.append(Path(root) / file)

        for py_file in sorted(py_files):
            self.extract_file(py_file)

        # Resolve inter-class and inter-module structural relations
        self._infer_relationships()

        return StaticModelIR(
            project_name=self.project_name,
            root_path=str(self.root_path),
            modules=self.modules,
            classes=self.classes,
            relations=self.relations,
            metadata={"extractor": "ASTStaticExtractor", "file_count": str(len(py_files))},
        )

    def extract_file(self, file_path: Path) -> Optional[ModuleIR]:
        """Parse a single Python source file into ModuleIR."""
        try:
            rel_path = file_path.relative_to(self.root_path).as_posix()
        except ValueError:
            rel_path = file_path.as_posix()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except Exception:
            return None

        try:
            tree = ast.parse(source_code, filename=str(file_path))
        except SyntaxError:
            return None

        module_name = file_path.stem
        # Compute dotted path relative to root
        parts = list(file_path.relative_to(self.root_path).parts) if file_path.is_relative_to(self.root_path) else [module_name]
        if parts and parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if parts and parts[-1] == "__init__":
            parts.pop()
        qualified_module = ".".join(parts) if parts else module_name

        module_docstring = ast.get_docstring(tree)
        module_imports = self._extract_imports(tree)
        module_classes: List[ClassIR] = []
        module_functions: List[FunctionIR] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_ir = self._extract_class(node, qualified_module, rel_path, source_code)
                module_classes.append(cls_ir)
                self.classes.append(cls_ir)
                self._class_lookup[cls_ir.qualified_name] = cls_ir
                self._class_lookup[cls_ir.name] = cls_ir
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_ir = self._extract_function(node, qualified_module, rel_path, source_code)
                module_functions.append(fn_ir)

        end_line = len(source_code.splitlines()) or 1

        # If this module has no classes, but defines functions or constants, synthesize an architectural Module entity
        if not module_classes and (module_functions or module_name != "__init__"):
            mod_attrs = self._extract_module_attributes(tree, qualified_module, rel_path)
            mod_methods = [
                MethodIR(
                    id=f"{qualified_module}.{fn.name}",
                    name=fn.name,
                    parameters=fn.parameters,
                    return_type=fn.return_type,
                    decorators=fn.decorators,
                    visibility=MemberVisibility.PUBLIC if not fn.name.startswith("_") else MemberVisibility.PRIVATE,
                    is_async=fn.is_async,
                    is_static=True,
                    docstring=fn.docstring,
                    source_location=fn.source_location,
                )
                for fn in module_functions
            ]
            display_name = qualified_module if "." in qualified_module else module_name
            mod_class_ir = ClassIR(
                id=qualified_module,
                name=display_name,
                qualified_name=qualified_module,
                kind=ElementKind.MODULE,
                docstring=module_docstring,
                attributes=mod_attrs,
                methods=mod_methods,
                source_location=SourceLocation(
                    file_path=rel_path,
                    start_line=1,
                    end_line=end_line,
                    start_col=0,
                    end_col=0,
                    content_hash=_compute_hash(source_code),
                ),
            )
            module_classes.append(mod_class_ir)
            self.classes.append(mod_class_ir)
            self._class_lookup[qualified_module] = mod_class_ir
            self._class_lookup[module_name] = mod_class_ir
            self._class_lookup[display_name] = mod_class_ir

        mod_ir = ModuleIR(
            id=qualified_module,
            name=module_name,
            qualified_name=qualified_module,
            file_path=rel_path,
            docstring=module_docstring,
            classes=module_classes,
            functions=module_functions,
            imports=module_imports,
            source_location=SourceLocation(
                file_path=rel_path,
                start_line=1,
                end_line=end_line,
                start_col=0,
                end_col=0,
                content_hash=_compute_hash(source_code),
            ),
        )
        self.modules.append(mod_ir)
        return mod_ir

    def _extract_module_attributes(self, tree: ast.AST, module_qual: str, file_path: str) -> List[AttributeIR]:
        """Extract top-level module constants and variables as architectural attributes."""
        attrs: List[AttributeIR] = []
        for node in getattr(tree, "body", []):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if not (name.startswith("__") and name.endswith("__")):
                            val_str = _unparse_ast_node(node.value) if hasattr(node, "value") else None
                            if val_str and len(val_str) > 40:
                                val_str = val_str[:37] + "..."
                            attrs.append(
                                AttributeIR(
                                    id=f"{module_qual}.{name}",
                                    name=name,
                                    type_annotation=val_str,
                                    visibility=MemberVisibility.PUBLIC if not name.startswith("_") else MemberVisibility.PRIVATE,
                                    is_class_variable=True,
                                    source_location=SourceLocation(
                                        file_path=file_path,
                                        start_line=node.lineno,
                                        end_line=getattr(node, "end_lineno", node.lineno),
                                        start_col=node.col_offset,
                                    ),
                                )
                            )
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    name = node.target.id
                    if not (name.startswith("__") and name.endswith("__")):
                        attrs.append(
                            AttributeIR(
                                id=f"{module_qual}.{name}",
                                name=name,
                                type_annotation=_unparse_ast_node(node.annotation),
                                default_value=_unparse_ast_node(node.value) if node.value else None,
                                visibility=MemberVisibility.PUBLIC if not name.startswith("_") else MemberVisibility.PRIVATE,
                                is_class_variable=True,
                                source_location=SourceLocation(
                                    file_path=file_path,
                                    start_line=node.lineno,
                                    end_line=getattr(node, "end_lineno", node.lineno),
                                    start_col=node.col_offset,
                                ),
                            )
                        )
        return attrs[:15]

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements from module AST."""
        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        return imports

    def _extract_class(
        self, node: ast.ClassDef, module_qual: str, file_path: str, source_code: str
    ) -> ClassIR:
        """Extract ClassIR details from ast.ClassDef node."""
        class_name = node.name
        qualified_name = f"{module_qual}.{class_name}"
        docstring = ast.get_docstring(node)
        raw_bases = [_unparse_ast_node(b) for b in node.bases]
        bases: List[str] = [b for b in raw_bases if b is not None]

        raw_decs = [_unparse_ast_node(d) for d in node.decorator_list]
        decorators: List[str] = [d for d in raw_decs if d is not None]

        is_abstract = "ABC" in bases or any("abstractmethod" in d for d in decorators)
        is_protocol = any("Protocol" in b for b in bases)
        is_dataclass = any("dataclass" in d for d in decorators)
        is_enum = any(b in ("Enum", "IntEnum", "StrEnum") for b in bases)

        kind = ElementKind.CLASS
        if is_protocol:
            kind = ElementKind.PROTOCOL
        elif is_dataclass:
            kind = ElementKind.DATACLASS
        elif is_enum:
            kind = ElementKind.ENUM
        elif is_abstract:
            kind = ElementKind.INTERFACE

        attributes: List[AttributeIR] = []
        methods: List[MethodIR] = []
        seen_attr_names: Set[str] = set()

        # 1. Class-level attributes & annotations
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attr_name = item.target.id
                type_ann = _unparse_ast_node(item.annotation)
                def_val = _unparse_ast_node(item.value) if item.value else None
                seen_attr_names.add(attr_name)
                attributes.append(
                    AttributeIR(
                        id=f"{qualified_name}.{attr_name}",
                        name=attr_name,
                        type_annotation=type_ann,
                        default_value=def_val,
                        visibility=_get_visibility(attr_name),
                        is_class_variable=True,
                        source_location=SourceLocation(
                            file_path=file_path,
                            start_line=item.lineno,
                            end_line=getattr(item, "end_lineno", item.lineno),
                            start_col=item.col_offset,
                        ),
                    )
                )
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        if attr_name not in seen_attr_names:
                            seen_attr_names.add(attr_name)
                            def_val = _unparse_ast_node(item.value)
                            attributes.append(
                                AttributeIR(
                                    id=f"{qualified_name}.{attr_name}",
                                    name=attr_name,
                                    type_annotation=None,
                                    default_value=def_val,
                                    visibility=_get_visibility(attr_name),
                                    is_class_variable=True,
                                    source_location=SourceLocation(
                                        file_path=file_path,
                                        start_line=item.lineno,
                                        end_line=getattr(item, "end_lineno", item.lineno),
                                        start_col=item.col_offset,
                                    ),
                                )
                            )

            # 2. Methods
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_ir = self._extract_method(item, qualified_name, file_path)
                methods.append(method_ir)
                if is_abstract is False and method_ir.is_abstract:
                    is_abstract = True

                # Walk method body for calls, instantiations, and instance attributes
                for sub in ast.walk(item):
                    if isinstance(sub, ast.Call):
                        called_name = None
                        if isinstance(sub.func, ast.Name):
                            called_name = sub.func.id
                        elif isinstance(sub.func, ast.Attribute):
                            called_name = sub.func.attr
                        if called_name and len(called_name) > 1 and called_name[0].isupper() and not called_name.isupper():
                            self._class_calls.append({
                                "caller_id": qualified_name,
                                "called_name": called_name,
                                "method_name": item.name,
                                "is_init": (item.name == "__init__"),
                                "file_path": file_path,
                                "lineno": getattr(sub, "lineno", item.lineno),
                            })

                    # Inspect __init__ for instance attributes: self.x = ...
                    if item.name == "__init__" and isinstance(sub, ast.Assign):
                        for target in sub.targets:
                            if (
                                isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"
                            ):
                                inst_attr = target.attr
                                if inst_attr not in seen_attr_names:
                                    seen_attr_names.add(inst_attr)
                                    def_val = _unparse_ast_node(sub.value)
                                    attributes.append(
                                        AttributeIR(
                                            id=f"{qualified_name}.{inst_attr}",
                                            name=inst_attr,
                                            type_annotation=None,
                                            default_value=def_val,
                                            visibility=_get_visibility(inst_attr),
                                            is_class_variable=False,
                                            source_location=SourceLocation(
                                                file_path=file_path,
                                                start_line=sub.lineno,
                                                end_line=getattr(sub, "end_lineno", sub.lineno),
                                                start_col=sub.col_offset,
                                            ),
                                        )
                                    )

        node_source = _unparse_ast_node(node) or ""
        return ClassIR(
            id=qualified_name,
            name=class_name,
            qualified_name=qualified_name,
            kind=kind,
            bases=bases,
            decorators=decorators,
            is_abstract=is_abstract,
            is_protocol=is_protocol,
            is_dataclass=is_dataclass,
            is_enum=is_enum,
            docstring=docstring,
            attributes=attributes,
            methods=methods,
            source_location=SourceLocation(
                file_path=file_path,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                start_col=node.col_offset,
                end_col=getattr(node, "end_col_offset", None),
                content_hash=_compute_hash(node_source),
            ),
        )

    def _extract_method(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_qual: str,
        file_path: str,
    ) -> MethodIR:
        """Extract MethodIR details from a method node inside a class."""
        method_name = node.name
        raw_decs = [_unparse_ast_node(d) for d in node.decorator_list]
        decorators: List[str] = [d for d in raw_decs if d is not None]
        is_async = isinstance(node, ast.AsyncFunctionDef)
        is_static = any("staticmethod" in d for d in decorators)
        is_classmethod = any("classmethod" in d for d in decorators)
        is_abstract = any("abstractmethod" in d for d in decorators)
        is_property = any(d in ("property", "cached_property") for d in decorators)

        params = self._extract_parameters(node.args)
        return_type = _unparse_ast_node(node.returns)
        node_source = _unparse_ast_node(node) or ""

        return MethodIR(
            id=f"{class_qual}.{method_name}",
            name=method_name,
            parameters=params,
            return_type=return_type,
            decorators=decorators,
            visibility=_get_visibility(method_name),
            is_async=is_async,
            is_static=is_static,
            is_classmethod=is_classmethod,
            is_abstract=is_abstract,
            is_property=is_property,
            docstring=ast.get_docstring(node),
            source_location=SourceLocation(
                file_path=file_path,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                start_col=node.col_offset,
                end_col=getattr(node, "end_col_offset", None),
                content_hash=_compute_hash(node_source),
            ),
        )

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        module_qual: str,
        file_path: str,
        source_code: str,
    ) -> FunctionIR:
        """Extract standalone module function."""
        fn_name = node.name
        raw_decs = [_unparse_ast_node(d) for d in node.decorator_list]
        decorators: List[str] = [d for d in raw_decs if d is not None]
        params = self._extract_parameters(node.args)
        return_type = _unparse_ast_node(node.returns)
        node_source = _unparse_ast_node(node) or ""

        return FunctionIR(
            id=f"{module_qual}.{fn_name}",
            name=fn_name,
            parameters=params,
            return_type=return_type,
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=ast.get_docstring(node),
            source_location=SourceLocation(
                file_path=file_path,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                start_col=node.col_offset,
                content_hash=_compute_hash(node_source),
            ),
        )

    def _extract_parameters(self, args_node: ast.arguments) -> List[ParameterIR]:
        """Extract parameter names, annotations, defaults from ast.arguments."""
        params: List[ParameterIR] = []
        pos_args = args_node.posonlyargs + args_node.args
        defaults = args_node.defaults

        # Align positional defaults (right-aligned)
        default_offset = len(pos_args) - len(defaults)

        for i, arg in enumerate(pos_args):
            # Skip 'self' / 'cls' as implicit receiver
            if i == 0 and arg.arg in ("self", "cls"):
                continue
            def_val = None
            if i >= default_offset:
                def_val = _unparse_ast_node(defaults[i - default_offset])
            params.append(
                ParameterIR(
                    name=arg.arg,
                    type_annotation=_unparse_ast_node(arg.annotation),
                    default_value=def_val,
                )
            )

        if args_node.vararg:
            params.append(
                ParameterIR(
                    name=args_node.vararg.arg,
                    type_annotation=_unparse_ast_node(args_node.vararg.annotation),
                    is_variadic=True,
                )
            )

        for i, kwarg in enumerate(args_node.kwonlyargs):
            kw_def = _unparse_ast_node(args_node.kw_defaults[i]) if i < len(args_node.kw_defaults) else None
            params.append(
                ParameterIR(
                    name=kwarg.arg,
                    type_annotation=_unparse_ast_node(kwarg.annotation),
                    default_value=kw_def,
                    is_keyword_only=True,
                )
            )

        if args_node.kwarg:
            params.append(
                ParameterIR(
                    name=args_node.kwarg.arg,
                    type_annotation=_unparse_ast_node(args_node.kwarg.annotation),
                    is_keyword=True,
                )
            )

        return params

    def _infer_relationships(self) -> None:
        """Infer inheritance, realization, composition, and associations between classes."""
        rel_counter = 0

        for cls_ir in self.classes:
            # 1. Inheritance / Realization
            for base in cls_ir.bases:
                target_cls = self._find_class(base)
                rel_type = RelationType.INHERITANCE
                target_id = target_cls.id if target_cls else base

                if target_cls and (target_cls.is_protocol or target_cls.is_abstract):
                    rel_type = RelationType.REALIZATION

                rel_counter += 1
                self.relations.append(
                    RelationIR(
                        id=f"rel_{rel_counter}",
                        source_id=cls_ir.id,
                        target_id=target_id,
                        relation_type=rel_type,
                        label="extends" if rel_type == RelationType.INHERITANCE else "implements",
                        source_location=cls_ir.source_location,
                    )
                )

            # 2. Composition & Aggregation from attribute types
            for attr in cls_ir.attributes:
                if attr.type_annotation:
                    target_cls = self._find_class(attr.type_annotation)
                    if target_cls and target_cls.id != cls_ir.id:
                        rel_counter += 1
                        self.relations.append(
                            RelationIR(
                                id=f"rel_{rel_counter}",
                                source_id=cls_ir.id,
                                target_id=target_cls.id,
                                relation_type=RelationType.COMPOSITION if attr.is_class_variable else RelationType.AGGREGATION,
                                label=attr.name,
                                multiplicity_target="1",
                                source_location=attr.source_location,
                            )
                        )

            # 3. Association / Dependency from method parameter & return types
            for method in cls_ir.methods:
                if method.return_type:
                    target_cls = self._find_class(method.return_type)
                    if target_cls and target_cls.id != cls_ir.id:
                        rel_counter += 1
                        self.relations.append(
                            RelationIR(
                                id=f"rel_{rel_counter}",
                                source_id=cls_ir.id,
                                target_id=target_cls.id,
                                relation_type=RelationType.DEPENDENCY,
                                label=f"returns {method.name}()",
                                source_location=method.source_location,
                            )
                        )

        # 4. Composition & Dependency from method body calls and instantiations
        existing_pairs = {(r.source_id, r.target_id) for r in self.relations}
        for call in self._class_calls:
            caller_id = call["caller_id"]
            called_name = call["called_name"]
            target_cls = self._find_class(called_name)
            if target_cls and target_cls.id != caller_id:
                pair = (caller_id, target_cls.id)
                if pair not in existing_pairs:
                    existing_pairs.add(pair)
                    rel_counter += 1
                    rel_type = RelationType.COMPOSITION if call["is_init"] else RelationType.DEPENDENCY
                    label_text = f"instantiates {called_name}" if call["is_init"] else f"calls {called_name}()"
                    self.relations.append(
                        RelationIR(
                            id=f"rel_{rel_counter}",
                            source_id=caller_id,
                            target_id=target_cls.id,
                            relation_type=rel_type,
                            label=label_text,
                            source_location=SourceLocation(
                                file_path=call["file_path"],
                                start_line=call["lineno"],
                                end_line=call["lineno"],
                                start_col=0,
                            ),
                        )
                    )

        # 5. Dependency relations between modules/classes from import statements
        for mod in self.modules:
            src_cls = self._find_class(mod.qualified_name) or self._find_class(mod.name)
            if not src_cls:
                continue
            for imp in mod.imports:
                tgt_cls = self._find_class(imp)
                if not tgt_cls and "." in imp:
                    prefix, suffix = imp.rsplit(".", 1)
                    tgt_cls = self._find_class(prefix) or self._find_class(suffix)
                if tgt_cls and tgt_cls.id != src_cls.id:
                    pair = (src_cls.id, tgt_cls.id)
                    if pair not in existing_pairs:
                        existing_pairs.add(pair)
                        rel_counter += 1
                        self.relations.append(
                            RelationIR(
                                id=f"rel_{rel_counter}",
                                source_id=src_cls.id,
                                target_id=tgt_cls.id,
                                relation_type=RelationType.DEPENDENCY,
                                label="imports",
                                source_location=mod.source_location,
                            )
                        )

    def _find_class(self, type_str: str) -> Optional[ClassIR]:
        """Look up known ClassIR by simple or qualified name."""
        clean_name = type_str.strip().strip("'\"")
        # Handle Optional[X] or List[X]
        if "[" in clean_name and clean_name.endswith("]"):
            clean_name = clean_name.split("[", 1)[1].rstrip("]")

        if clean_name in self._class_lookup:
            return self._class_lookup[clean_name]

        # Check suffixes
        for qual_name, cls_obj in self._class_lookup.items():
            if qual_name.endswith(f".{clean_name}") or qual_name == clean_name:
                return cls_obj
        return None
