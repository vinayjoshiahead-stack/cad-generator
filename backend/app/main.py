"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schema import ArtifactUrls, ExecuteRequest, ExecuteResponse
from app.services.cad_executor import (
    CadExecutionError,
    execute_cadquery_with_target,
    export_all_formats,
)
from app.services.supabase_service import SupabaseService, artifact_path
from uuid import uuid4

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight service and engine health response."""

    return {"status": "ok", "engine": "CadQuery"}


@app.post("/execute", response_model=ExecuteResponse)
def execute(request: ExecuteRequest) -> ExecuteResponse:
    """Execute a CadQuery program and return its encoded export."""

    if len(request.code) > settings.max_code_length:
        raise HTTPException(
            status_code=413,
            detail=f"code exceeds the {settings.max_code_length} character limit",
        )

    try:
        execution = execute_cadquery_with_target(request.code, request.export_format)
        response = execution.response
        if request.project_id:
            service = SupabaseService()
            generation_id = str(uuid4())
            artifact_urls = {}
            extensions = {"gltf": "glb", "step": "step", "stl": "stl", "svg": "svg"}
            url_keys = {
                "gltf": "gltf_url",
                "step": "step_url",
                "stl": "stl_url",
                "svg": "svg_blueprint_url",
            }
            for export_format, (file_bytes, content_type, _) in export_all_formats(execution.target).items():
                artifact_urls[url_keys[export_format]] = service.upload_artifact(
                    file_bytes,
                    artifact_path(request.project_id, generation_id, extensions[export_format]),
                    content_type,
                )
            record = service.save_generation_record(
                project_id=request.project_id,
                user_prompt=request.user_prompt,
                code=request.code,
                status="completed",
                artifacts_urls=artifact_urls,
                parent_id=request.parent_generation_id,
            )
            response.generation_id = str(record["id"])
            response.artifact_urls = ArtifactUrls(**artifact_urls)
        return response
    except CadExecutionError as exc:
        return ExecuteResponse(
            success=False,
            export_format=request.export_format,
            data="",
            media_type="application/json",
            filename="",
            error=exc.to_response(),
        )


@app.get("/projects/{project_id}/history")
def project_history(project_id: str) -> list[dict]:
    """Return all saved generations for a project in version order."""

    return SupabaseService().get_project_history(project_id)
