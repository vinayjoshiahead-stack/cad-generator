### PROMPT FOR FASTAPI BACKEND MIGRATION (CadQuery -> build123d + Geometry Gate)

We are upgrading our FastAPI CAD execution server from `CadQuery` to `build123d` while preserving backward compatibility for legacy `cadquery` scripts stored in our Supabase `generations` history table.

Please update our FastAPI backend (`requirements.txt` and the `POST /execute` endpoint) with the following exact changes:

#### 1. Update `requirements.txt`

Ensure `build123d` is installed alongside `cadquery` (they share `cadquery-ocp`, so there is minimal image size increase):

```txt
build123d>=0.8.0
cadquery>=2.4.0
fastapi
uvicorn
supabase
pydantic
```

#### 2. Upgrade POST /execute Execution Sandbox to Support build123d (Part, Compound, BuildPart)

Update the Python execution runner in POST /execute so it:
Pre-imports build123d (import build123d as bd and from build123d import \*), math, and cadquery as cq into the execution namespace.
Extracts the final shape from the executed script in this priority order:
result variable (can be a build123d.Shape / Part / Compound, a BuildPart context manager where result.part is the shape, or a legacy cq.Workplane / cq.Assembly).
part or assembly or assy variable if result is not defined.
Unwraps BuildPart automatically:

```
import build123d as bd

if isinstance(raw_result, bd.BuildPart):
    shape = raw_result.part
elif isinstance(raw_result, bd.Shape):
    shape = raw_result
```

#### 3. Add the Built-In Deterministic Geometry Inspector (validate_geometry)

Before exporting shape to STL/STEP/SVG/GLB, run a geometric validation check on build123d shapes (unless the script sets allow_multiple_solids = True for multi-part assemblies):

```
def inspect_and_validate_build123d(shape: bd.Shape, allow_multiple_solids: bool = False) -> dict:
    solids = shape.solids()
    solid_count = len(solids)

    if solid_count == 0:
        raise ValueError("GeometryValidationError: The script produced 0 solids (empty geometry). Check extrude/boolean operations.")

    if not allow_multiple_solids and solid_count > 1:
        # Compute bounding boxes of each disconnected solid to help the LLM fix floating parts
        boxes = []
        for idx, s in enumerate(solids):
            bb = s.bounding_box()
            boxes.append(
                f"Solid #{idx+1}: min=({bb.min.X:.2f}, {bb.min.Y:.2f}, {bb.min.Z:.2f}), "
                f"max=({bb.max.X:.2f}, {bb.max.Y:.2f}, {bb.max.Z:.Z if hasattr(bb.max, 'Z') else bb.max.Z:.2f}), "
                f"vol={s.volume:.2f}mm³"
            )
        details = "; ".join(boxes)
        raise ValueError(
            f"TopologicalFloatingPartsError: Expected 1 connected solid body, but generated {solid_count} "
            f"disconnected floating solids! Ensure components touch or overlap before union/addition. "
            f"Detected solids: [{details}]"
        )

    if not shape.is_valid:
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
        }
    }
```

#### 4. Native build123d Exporters (stl, step, svg, gltf/glb)

When shape is a build123d.Shape:
export_format == "stl": Use bd.export_stl(shape, tmp_stl_path, tolerance=1e-3, angular_tolerance=0.1) and return base64-encoded bytes in data.
export_format == "step": Use bd.export_step(shape, tmp_step_path) and return base64-encoded bytes in data.
export_format == "gltf" or "glb": Use bd.export_gltf(shape, tmp_glb_path, binary=True) and return base64-encoded bytes in data.
export_format == "svg": Project the shape isometrically using bd.ExportSVG (with visible and hidden line layers) or shape.to_splines() and return the SVG string in data.

#### 5. Include geometry_telemetry in the JSON Response

In the 200 OK JSON response from POST /execute, include "geometry_telemetry": telemetry_dict alongside "status": "success", "data": ..., "project_id": ..., and "generation_id": ....
