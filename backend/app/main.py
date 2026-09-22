"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schema import ExecuteRequest, ExecuteResponse
from app.services.cad_executor import CadExecutionError, execute_cadquery

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
        return execute_cadquery(request.code, request.export_format)
    except CadExecutionError as exc:
        return ExecuteResponse(
            success=False,
            export_format=request.export_format,
            data="",
            media_type="application/json",
            filename="",
            error=exc.to_response(),
        )
