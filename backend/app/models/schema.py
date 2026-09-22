"""Pydantic models for the CAD Generator API."""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


ExportFormat = Literal["gltf", "step", "stl", "svg"]


class ExecuteRequest(BaseModel):
    """User-supplied CadQuery program and requested output format."""

    code: str = Field(default="", description="CadQuery Python source code.")
    export_format: ExportFormat = Field(default="gltf")
    user_prompt: str = Field(default="")
    user_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)
    parent_generation_id: Optional[str] = Field(default=None)


class ProjectCreateRequest(BaseModel):
    """Payload for creating a project."""

    title: str = Field(min_length=1, max_length=200)
    user_id: Optional[str] = None


class ProjectResponse(BaseModel):
    """Project metadata returned by the API."""

    id: str
    user_id: Optional[str] = None
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ArtifactUrls(BaseModel):
    """Public URLs for generated CAD artifacts."""

    gltf_url: Optional[str] = None
    step_url: Optional[str] = None
    stl_url: Optional[str] = None
    svg_blueprint_url: Optional[str] = None


class ExecutionErrorResponse(BaseModel):
    """Structured error details suitable for an LLM correction loop."""

    type: str
    message: str
    traceback: str


class ExecuteResponse(BaseModel):
    """Successful execution response containing encoded file data."""

    success: bool = True
    export_format: ExportFormat
    data: str
    media_type: str
    filename: str
    error: Optional[ExecutionErrorResponse] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    generation_id: Optional[str] = None
    project_id: Optional[str] = None
    artifact_urls: Optional[ArtifactUrls] = None
