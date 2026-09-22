"""Controlled CadQuery script execution and error shaping."""

import builtins
import traceback
from typing import Any, Dict, Optional

import cadquery as cq

from app.models.schema import ExecuteResponse, ExportFormat, ExecutionErrorResponse
from app.services.exporter import ExportError, export_target


SAMPLE_CODE = """import cadquery as cq

result = cq.Workplane(\"XY\").box(20, 20, 5).edges(\"|Z\").fillet(2)
"""


class CadExecutionError(Exception):
    """An execution or export failure formatted for an API response."""

    def __init__(self, error_type: str, message: str, trace: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.trace = trace

    def to_response(self) -> ExecutionErrorResponse:
        return ExecutionErrorResponse(
            type=self.error_type,
            message=self.message,
            traceback=self.trace,
        )


def _safe_import(name: str, globals_dict: Optional[Dict[str, Any]] = None, locals_dict: Optional[Dict[str, Any]] = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    allowed_roots = {"cadquery", "math"}
    root = name.split(".", 1)[0]
    if level != 0 or root not in allowed_roots:
        raise ImportError(f"imports are restricted; cannot import {name!r}")
    return builtins.__import__(name, globals_dict, locals_dict, fromlist, level)


_SAFE_BUILTINS: Dict[str, Any] = {
    "__import__": _safe_import,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}
_SAFE_BUILTINS["range"] = range


def _execute_source(source: str) -> Dict[str, Any]:
    namespace: Dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "cq": cq,
        "cadquery": cq,
    }
    exec(compile(source, "<cadquery-script>", "exec"), namespace, namespace)
    return namespace


def _find_target(namespace: Dict[str, Any]) -> Any:
    if "result" in namespace:
        return namespace["result"]
    if "assy" in namespace:
        return namespace["assy"]
    raise NameError("script must define either 'result' (Workplane/Solid) or 'assy' (Assembly)")


def _validate_target(target: Any) -> None:
    supported = (cq.Workplane, cq.Shape, cq.Assembly)
    if not isinstance(target, supported):
        raise TypeError(
            "target must be a cadquery.Workplane, cadquery.Shape/Solid, or cadquery.Assembly"
        )


def execute_cadquery(source: str, export_format: ExportFormat) -> ExecuteResponse:
    """Run source, locate its target, export it, and convert failures to API data."""

    source_to_run = source.strip() or SAMPLE_CODE
    try:
        namespace = _execute_source(source_to_run)
        target = _find_target(namespace)
        _validate_target(target)
        data, media_type, filename, metadata = export_target(target, export_format)
        return ExecuteResponse(
            export_format=export_format,
            data=data,
            media_type=media_type,
            filename=filename,
            metadata=metadata,
        )
    except ExportError as exc:
        raise CadExecutionError(
            "ExportError",
            str(exc),
            exc.traceback,
        ) from exc
    except Exception as exc:
        raise CadExecutionError(
            type(exc).__name__,
            str(exc),
            traceback.format_exc(),
        ) from exc
