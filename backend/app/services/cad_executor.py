"""Controlled build123d script execution and validation."""

import builtins
import math
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import build123d as bd

from app.models.schema import ExecuteResponse, ExportFormat, ExecutionErrorResponse
from app.services.exporter import ExportError, export_target, export_target_bytes


SAMPLE_CODE = """import build123d as bd

result = bd.Box(20, 20, 5)
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


@dataclass
class CadExecutionResult:
    response: ExecuteResponse
    target: Any
    geometry_telemetry: Dict[str, Any] | None = None


def _safe_import(name: str, globals_dict: Optional[Dict[str, Any]] = None, locals_dict: Optional[Dict[str, Any]] = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    allowed_roots = {"build123d", "math"}
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
        "bd": bd,
        "build123d": bd,
        "math": math,
    }
    for name in dir(bd):
        if not name.startswith("_"):
            namespace[name] = getattr(bd, name)
    exec(compile(source, "<build123d-script>", "exec"), namespace, namespace)
    return namespace


def _unwrap_target(target: Any) -> Any:
    if isinstance(target, bd.BuildPart):
        return target.part
    return target


def _find_target(namespace: Dict[str, Any]) -> Any:
    for key in ("result", "part", "assembly", "assy"):
        if key in namespace and namespace[key] is not None:
            return _unwrap_target(namespace[key])
    raise NameError("script must define either 'result', 'part', or 'assy' / 'assembly' payload")


def _validate_target(target: Any) -> None:
    supported = (
        bd.Shape,
        bd.Part,
        bd.Compound,
        bd.Solid,
        bd.BuildPart,
    )
    if not isinstance(target, supported):
        raise TypeError("target must be a build123d Shape/Part/Compound/Solid or BuildPart")


def inspect_and_validate_build123d(shape: Any, allow_multiple_solids: bool = False) -> dict:
    """Apply the deterministic geometry checks required by the migration plan."""
    if not hasattr(shape, "solids"):
        return {}

    solids = shape.solids()
    solid_count = len(solids)
    if solid_count == 0:
        raise ValueError("GeometryValidationError: The script produced 0 solids (empty geometry). Check extrude/boolean operations.")

    if not allow_multiple_solids and solid_count > 1:
        boxes = []
        for idx, solid in enumerate(solids):
            bb = solid.bounding_box()
            boxes.append(
                f"Solid #{idx + 1}: min=({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f}), "
                f"max=({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.2f}), vol={solid.volume:.2f}mm³"
            )
        details = "; ".join(boxes)
        raise ValueError(
            f"TopologicalFloatingPartsError: Expected 1 connected solid body, but generated {solid_count} "
            f"disconnected floating solids! Ensure components touch or overlap before union/addition. "
            f"Detected solids: [{details}]"
        )

    if not getattr(shape, "is_valid", True):
        raise ValueError("TopologyError: OpenCASCADE BRepCheck reported invalid non-manifold topology (check fillets/chamfers or self-intersecting sketches).")

    total_volume = sum(s.volume for s in solids)
    if total_volume <= 1e-3:
        raise ValueError(f"ZeroVolumeError: Generated solid has near-zero or negative volume ({total_volume:.4f} mm³).")

    bb = shape.bounding_box()
    return {
        "engine": "build123d",
        "solid_count": solid_count,
        "face_count": len(shape.faces()),
        "edge_count": len(shape.edges()),
        "volume_mm3": round(total_volume, 2),
        "bounding_box": {
            "xlen": round(bb.size.X, 2),
            "ylen": round(bb.size.Y, 2),
            "zlen": round(bb.size.Z, 2),
            "xmin": round(bb.min.X, 2),
            "ymin": round(bb.min.Y, 2),
            "zmin": round(bb.min.Z, 2),
            "xmax": round(bb.max.X, 2),
            "ymax": round(bb.max.Y, 2),
            "zmax": round(bb.max.Z, 2),
        },
    }


def execute_build123d(source: str, export_format: ExportFormat) -> ExecuteResponse:
    """Run source, locate its target, export it, and convert failures to API data."""

    source_to_run = source.strip() or SAMPLE_CODE
    try:
        namespace = _execute_source(source_to_run)
        target = _find_target(namespace)
        _validate_target(target)
        allow_multiple_solids = bool(namespace.get("allow_multiple_solids", False))
        telemetry = inspect_and_validate_build123d(target, allow_multiple_solids=allow_multiple_solids)
        data, media_type, filename, metadata = export_target(target, export_format)
        metadata = dict(metadata)
        if telemetry:
            metadata["geometry_telemetry"] = telemetry
        return ExecuteResponse(
            export_format=export_format,
            data=data,
            media_type=media_type,
            filename=filename,
            metadata=metadata,
            geometry_telemetry=telemetry,
        )
    except ExportError as exc:
        raise CadExecutionError("ExportError", str(exc), exc.traceback) from exc
    except Exception as exc:
        raise CadExecutionError(type(exc).__name__, str(exc), traceback.format_exc()) from exc


def execute_build123d_with_target(source: str, export_format: ExportFormat) -> CadExecutionResult:
    """Run source, export the requested format, and retain the target for persistence."""

    source_to_run = source.strip() or SAMPLE_CODE
    try:
        namespace = _execute_source(source_to_run)
        target = _find_target(namespace)
        _validate_target(target)
        allow_multiple_solids = bool(namespace.get("allow_multiple_solids", False))
        telemetry = inspect_and_validate_build123d(target, allow_multiple_solids=allow_multiple_solids)
        data, media_type, filename, metadata = export_target(target, export_format)
        metadata = dict(metadata)
        if telemetry:
            metadata["geometry_telemetry"] = telemetry
        response = ExecuteResponse(
            export_format=export_format,
            data=data,
            media_type=media_type,
            filename=filename,
            metadata=metadata,
            geometry_telemetry=telemetry,
        )
        return CadExecutionResult(
            response=response,
            target=target,
            geometry_telemetry=telemetry,
        )
    except ExportError as exc:
        raise CadExecutionError("ExportError", str(exc), exc.traceback) from exc
    except Exception as exc:
        raise CadExecutionError(type(exc).__name__, str(exc), traceback.format_exc()) from exc


def export_all_formats(target: Any) -> Dict[str, tuple[bytes, str, str]]:
    """Create all artifacts needed by the Supabase-backed generation record."""

    return {
        export_format: export_target_bytes(target, export_format)
        for export_format in ("gltf", "step", "stl", "svg")
    }
