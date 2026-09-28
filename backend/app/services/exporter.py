"""build123d shape exporters and base64 response encoding."""

import base64
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple

import build123d as bd

from app.models.schema import ExportFormat


class ExportError(Exception):
    """Raised when a CAD object cannot be converted to the requested format."""

    def __init__(self, message: str, original: BaseException) -> None:
        super().__init__(message)
        self.original = original
        self.traceback = traceback.format_exc()


def _normalize_target(target: Any) -> Any:
    if isinstance(target, bd.BuildPart):
        return target.part
    return target


def _is_build123d_shape(target: Any) -> bool:
    return isinstance(target, (bd.Shape, bd.Part, bd.Compound, bd.Solid))


def _export_build123d_shape(target: Any, path: str, export_format: str) -> None:
    shape = _normalize_target(target)
    if export_format == "stl":
        bd.export_stl(shape, path, tolerance=1e-3, angular_tolerance=0.1)
        return
    if export_format == "step":
        bd.export_step(shape, path)
        return
    if export_format in {"gltf", "glb"}:
        bd.export_gltf(shape, path, binary=True)
        return
    if export_format == "svg":
        try:
            svg_text = bd.ExportSVG(shape, with_hidden=True).to_svg()
        except Exception:
            svg_text = str(shape.to_splines())
        Path(path).write_text(svg_text, encoding="utf-8")
        return
    raise ValueError(f"unsupported export format: {export_format}")


def _write_export(target: Any, export_format: ExportFormat, path: str) -> None:
    if _is_build123d_shape(target):
        _export_build123d_shape(target, path, export_format)
        return
    raise ValueError(f"unsupported target type for build123d export: {type(target)!r}")


def export_target(target: Any, export_format: ExportFormat) -> Tuple[str, str, str, Dict[str, Any]]:
    """Export a target and return base64 data, media type, filename, metadata."""

    suffixes = {"gltf": ".glb", "step": ".step", "stl": ".stl", "svg": ".svg"}
    media_types = {
        "gltf": "model/gltf-binary",
        "step": "application/step",
        "stl": "model/stl",
        "svg": "image/svg+xml",
    }

    try:
        with tempfile.TemporaryDirectory(prefix="cad-generator-") as directory:
            output_path = str(Path(directory) / f"model{suffixes[export_format]}")
            _write_export(target, export_format, output_path)
            encoded = base64.b64encode(Path(output_path).read_bytes()).decode("ascii")
            return (
                encoded,
                media_types[export_format],
                f"model{suffixes[export_format]}",
                {"bytes": Path(output_path).stat().st_size},
            )
    except Exception as exc:
        raise ExportError(f"failed to export as {export_format}: {exc}", exc) from exc


def export_target_bytes(target: Any, export_format: ExportFormat) -> Tuple[bytes, str, str]:
    """Export a target and return raw bytes, media type, and filename."""

    suffixes = {"gltf": ".glb", "step": ".step", "stl": ".stl", "svg": ".svg"}
    media_types = {
        "gltf": "model/gltf-binary",
        "step": "application/step",
        "stl": "model/stl",
        "svg": "image/svg+xml",
    }

    try:
        with tempfile.TemporaryDirectory(prefix="cad-generator-") as directory:
            output_path = str(Path(directory) / f"model{suffixes[export_format]}")
            _write_export(target, export_format, output_path)
            return Path(output_path).read_bytes(), media_types[export_format], f"model{suffixes[export_format]}"
    except Exception as exc:
        raise ExportError(f"failed to export as {export_format}: {exc}", exc) from exc
