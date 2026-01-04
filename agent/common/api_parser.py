"""
API Parsing and Routing utilities for website API modules.
"""

import ast
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from pydantic import BaseModel, Field

# API routing and parsing utilities
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_DIR = REPO_ROOT / "api"
API_INDEX_FILE = API_DIR / "index.json"


class ParameterDescription(BaseModel):
    """Metadata describing a single endpoint parameter."""
    name: str
    kind: str = Field(description="Parameter kind")
    annotation: Optional[str] = None
    default: Optional[str] = None


class EndpointDescription(BaseModel):
    """Metadata describing an API endpoint."""
    name: str
    section: Optional[str] = None
    summary: str = ""
    docstring: str = ""
    parameters: List[ParameterDescription] = Field(default_factory=list)
    return_annotation: Optional[str] = None


class TypeDescription(BaseModel):
    """Metadata describing a Pydantic BaseModel subclass."""
    name: str
    bases: List[str] = Field(default_factory=list)
    docstring: str = ""
    fields: List[Dict[str, Any]] = Field(default_factory=list)


class APISpecification(BaseModel):
    """Structured description of the API surface for prompting."""
    path: Path
    endpoints: List[EndpointDescription] = Field(default_factory=list)
    types: List[TypeDescription] = Field(default_factory=list)

    @classmethod
    def from_file(cls, api_file: Path) -> "APISpecification":
        endpoints, types = _parse_api_file(api_file)
        return cls(path=api_file, endpoints=endpoints, types=types)

    def as_prompt_block(self, prefix: Optional[str] = None) -> str:
        """Render the specification as a markdown-friendly prompt block."""
        display_prefix = f"{prefix}." if prefix else ""
        lines: List[str] = ["Endpoints:"]
        for endpoint in self.endpoints:
            header = f"- {display_prefix}{endpoint.name}("
            params = []
            for param in endpoint.parameters:
                param_repr = param.name
                if param.annotation:
                    param_repr += f": {param.annotation}"
                if param.default is not None:
                    param_repr += f" = {param.default}"
                params.append(param_repr)
            header += ", ".join(params) + ")"
            header += f" -> {endpoint.return_annotation or 'None'}"
            if endpoint.section:
                header += f"  [{endpoint.section}]"
            lines.append(header)
            if endpoint.summary:
                lines.append(f"  Summary: {endpoint.summary}")
            for param in endpoint.parameters:
                details = f"    - {param.kind}: {param.name}"
                if param.annotation:
                    details += f" ({param.annotation})"
                if param.default is not None:
                    details += f", default={param.default}"
                lines.append(details)
        if self.types:
            lines.append("")
            lines.append("Type Definitions:")
            for type_desc in self.types:
                bases = f"({', '.join(type_desc.bases)})" if type_desc.bases else ""
                lines.append(f"- class {display_prefix}{type_desc.name}{bases}")
                if type_desc.docstring:
                    lines.append("  Docstring:")
                    for doc_line in type_desc.docstring.strip().splitlines():
                        lines.append(f"    {doc_line}")
                if type_desc.fields:
                    lines.append("  Fields:")
                    for field in type_desc.fields:
                        field_line = f"    - {field.get('name', '')}"
                        if field.get('annotation'):
                            field_line += f": {field.get('annotation')}"
                        if field.get('default'):
                            field_line += f" = {field.get('default')}"
                        lines.append(field_line)
        return "\n".join(lines)


@dataclass
class WebsiteAPI:
    """Metadata and helpers for a website-specific API module."""
    name: str
    file_name: str
    description: str
    base_dir: Path = field(repr=False)
    _spec: Optional[APISpecification] = field(default=None, init=False, repr=False)

    @property
    def path(self) -> Path:
        return self.base_dir / self.file_name

    def load_spec(self) -> APISpecification:
        if self._spec is None:
            self._spec = APISpecification.from_file(self.path)
        return self._spec


def _load_api_index(index_path: Path = API_INDEX_FILE) -> Dict[str, str]:
    """Load the API index mapping filenames to descriptions."""
    if not index_path.exists():
        raise FileNotFoundError(f"API index missing at {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("API index must be a JSON object mapping file names to descriptions.")
    return data


def load_api_registry(index_path: Path = API_INDEX_FILE) -> List[WebsiteAPI]:
    """Load all website APIs described in the JSON index."""
    entries = _load_api_index(index_path)
    registry: List[WebsiteAPI] = []
    for file_name, description in entries.items():
        path = index_path.parent / file_name
        if not path.exists():
            raise FileNotFoundError(f"API file {file_name} referenced in index but missing at {path}")
        registry.append(
            WebsiteAPI(
                name=Path(file_name).stem,
                file_name=file_name,
                description=description,
                base_dir=index_path.parent,
            )
        )
    return registry


def _unparse(node: Optional[ast.AST]) -> Optional[str]:
    """Convert an AST node to source if possible."""
    if node is None:
        return None
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    return ast.dump(node)


def _is_tool_decorated(node: Union[ast.AsyncFunctionDef, ast.FunctionDef]) -> bool:
    """Check if a function node uses the @mcp.tool decorator."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == "tool":
                return True
    return False


def _is_public_api_function(node: Union[ast.AsyncFunctionDef, ast.FunctionDef]) -> bool:
    """Treat top-level async functions without a leading underscore as API endpoints."""
    return isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_")


def _infer_section(lines: List[str], lineno: int) -> Optional[str]:
    """Infer the section heading from preceding comment blocks."""
    for index in range(lineno - 2, -1, -1):
        text = lines[index].strip()
        if text.startswith("# ========================================================================="):
            continue
        if text.startswith("# ==="):
            return text.lstrip("# ").strip()
    return None


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    """Determine whether a class definition derives from pydantic BaseModel."""
    for base in node.bases:
        base_text = _unparse(base)
        if "BaseModel" in base_text:
            return True
    return False


def _build_type_description(node: ast.ClassDef) -> TypeDescription:
    """Create a TypeDescription from a class definition."""
    docstring = textwrap.dedent(ast.get_docstring(node) or "")
    fields: List[Dict[str, Any]] = []

    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            name = statement.target.id
            annotation = _unparse(statement.annotation)
            default_text: Optional[str] = None
            description_text: Optional[str] = None

            value = statement.value
            if isinstance(value, ast.Call) and _is_field_call(value):
                if value.args:
                    default_text = _unparse(value.args[0])
                description_text = _extract_field_description(value)
            elif value is not None:
                default_text = _unparse(value)

            fields.append({
                "name": name,
                "annotation": annotation,
                "default": default_text,
                "description": description_text,
            })

    bases = [_unparse(base) for base in node.bases]
    return TypeDescription(name=node.name, bases=bases, docstring=docstring, fields=fields)


def _is_field_call(call: ast.Call) -> bool:
    """Check whether the call is to pydantic Field."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "Field"
    if isinstance(func, ast.Attribute):
        return func.attr == "Field"
    return False


def _extract_field_description(call: ast.Call) -> Optional[str]:
    """Attempt to extract the description argument from a Field call."""
    for keyword in call.keywords:
        if keyword.arg == "description":
            literal = _literal_eval(keyword.value)
            if isinstance(literal, str):
                return literal
            return _unparse(keyword.value)
    return None


def _literal_eval(node: ast.AST) -> Optional[object]:
    """Safely evaluate an AST literal node."""
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _build_endpoint_description(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    lines: List[str],
) -> EndpointDescription:
    """Create an EndpointDescription from a function definition."""
    docstring = ast.get_docstring(node) or ""
    summary = docstring.strip().splitlines()[0] if docstring else ""
    parameters: List[ParameterDescription] = []

    positional_nodes = list(getattr(node.args, "posonlyargs", [])) + list(node.args.args)
    defaults = list(node.args.defaults)
    default_offset = len(positional_nodes) - len(defaults)

    for index, arg in enumerate(positional_nodes):
        default_node = defaults[index - default_offset] if index >= default_offset else None
        kind = "positional-only" if index < len(getattr(node.args, "posonlyargs", [])) else "positional-or-keyword"
        parameters.append(
            ParameterDescription(
                name=arg.arg,
                kind=kind,
                annotation=_unparse(arg.annotation),
                default=_unparse(default_node),
            )
        )

    if node.args.vararg:
        parameters.append(
            ParameterDescription(
                name=node.args.vararg.arg,
                kind="var-positional",
                annotation=_unparse(node.args.vararg.annotation),
            )
        )

    for kw_arg, default_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
        parameters.append(
            ParameterDescription(
                name=kw_arg.arg,
                kind="keyword-only",
                annotation=_unparse(kw_arg.annotation),
                default=_unparse(default_node),
            )
        )

    if node.args.kwarg:
        parameters.append(
            ParameterDescription(
                name=node.args.kwarg.arg,
                kind="var-keyword",
                annotation=_unparse(node.args.kwarg.annotation),
            )
        )

    return EndpointDescription(
        name=node.name,
        section=_infer_section(lines, node.lineno),
        summary=summary,
        docstring=textwrap.dedent(docstring),
        parameters=parameters,
        return_annotation=_unparse(node.returns),
    )


def _parse_api_file(api_file: Path) -> Tuple[List[EndpointDescription], List[TypeDescription]]:
    """Parse an API module file and return structured descriptions."""
    source = api_file.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    lines = source.splitlines()
    endpoints: List[EndpointDescription] = []
    types: List[TypeDescription] = []

    for node in module_ast.body:
        if isinstance(node, ast.ClassDef) and _is_pydantic_model(node):
            types.append(_build_type_description(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            _is_tool_decorated(node) or _is_public_api_function(node)
        ):
            endpoints.append(_build_endpoint_description(node, lines))

    endpoints.sort(key=lambda endpoint: (endpoint.section or "", endpoint.name))
    types.sort(key=lambda type_desc: type_desc.name)
    return endpoints, types
