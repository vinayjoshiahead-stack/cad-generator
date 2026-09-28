"""CadQuery/build123d shape exporters and base64 response encoding."""

import base64
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Tuple

import cadquery as cq
import trimesh

try:
    import build123d as bd
except Exception:  # pragma: no cover - dependency may be missing in some envs
    bd = None

from app.models.schema import ExportFormat


class ExportError(Exception):
    """Raised when a CAD object cannot be converted to the requested format."""

    def __init__(self, message: str, original: BaseException) -> None:
        super().__init__(message)
        self.original = original
        self.traceback = traceback.format_exc()


def _is_assembly(target: Any) -> bool:
    return isinstance(target, cq.Assembly)


def _is_build123d_shape(target: Any) -> bool:
    return bd is not None and hasattr(target, "wrapped") and hasattr(target, "solids")


def _normalize_build123d_target(target: Any) -> Any:
    if bd is not None and isinstance(target, bd.BuildPart):
        return target.part
    if bd is not None and isinstance(target, (bd.Shape, bd.Compound, bd.Part, bd.Solid)):
        return target
    return target


def _shape_for_export(target: Any) -> Any:
    """Convert an assembly to a compound for mesh and projection exporters."""

    if _is_assembly(target):
        return target.toCompound()
    return target


def _export_cadquery(target: Any, path: str, export_type: str) -> None:
    cq.exporters.export(_shape_for_export(target), path, exportType=export_type)


def _export_build123d_shape(target: Any, path: str, export_format: str) -> None:
    shape = _normalize_build123d_target(target)
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
            render = bd.ExportSVG(shape, projection_dir=(1, -1, 1), with_hidden=True)
            svg_text = render.to_svg()
        except Exception:
            svg_text = shape.to_splines()
            if hasattr(svg_text, "to_svg"):
                svg_text = svg_text.to_svg()
            elif not isinstance(svg_text, str):
                svg_text = str(svg_text)
        Path(path).write_text(svg_text, encoding="utf-8")
        return
    raise ValueError(f"unsupported export format: {export_format}")


def _export_gltf(target: Any, path: str) -> None:
    """Export through STL and let trimesh produce a binary glTF file."""

    if _is_build123d_shape(target):
        _export_build123d_shape(target, path, "gltf")
        return

    with tempfile.TemporaryDirectory(prefix="cadquery-stl-") as directory:
        stl_path = os.path.join(directory, "model.stl")
        _export_cadquery(target, stl_path, "STL")
        mesh = trimesh.load(stl_path, file_type="stl", force="mesh", process=False)
        if isinstance(mesh, trimesh.Scene):
            scene = mesh
        else:
            scene = trimesh.Scene(mesh)
        scene.export(path, file_type="glb")


def _write_export(target: Any, export_format: ExportFormat, path: str) -> None:
    if export_format == "gltf":
        _export_gltf(target, path)
    elif export_format == "step":
        if _is_assembly(target):
            target.save(path, exportType="STEP")
        elif _is_build123d_shape(target):
            _export_build123d_shape(target, path, "step")
        else:
            _export_cadquery(target, path, "STEP")
    elif export_format == "stl":
        if _is_build123d_shape(target):
            _export_build123d_shape(target, path, "stl")
        else:
            _export_cadquery(target, path, "STL")
    elif export_format == "svg":
        if _is_build123d_shape(target):
            _export_build123d_shape(target, path, "svg")
        else:
            _export_cadquery(target, path, "SVG")
    else:
        raise ValueError(f"unsupported export format: {export_format}")


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
