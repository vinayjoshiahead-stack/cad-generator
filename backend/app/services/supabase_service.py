"""Supabase Storage and generation persistence helpers."""

import os
from typing import Any, Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


class SupabaseService:
    """Small synchronous wrapper around the Supabase Python client."""

    bucket_name = "cad-artifacts"

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None) -> None:
        supabase_url = url or os.getenv("SUPABASE_URL")
        supabase_key = key or os.getenv("SUPABASE_KEY")
        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured")
        self.client: Client = create_client(supabase_url, supabase_key)

    def upload_artifact(self, file_bytes: bytes, file_path: str, content_type: str) -> str:
        """Upload an artifact and return its public URL."""

        self.client.storage.from_(self.bucket_name).upload(
            file_path,
            file_bytes,
            {"content-type": content_type, "upsert": "true"},
        )
        return self.client.storage.from_(self.bucket_name).get_public_url(file_path)

    def create_project(self, title: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a project and return the generated project record."""

        response = self.client.table("projects").insert(
            {"title": title, "user_id": user_id}
        ).execute()
        if not response.data:
            raise RuntimeError("Supabase did not return the inserted project")
        return response.data[0]

    def list_projects(self, user_id: Optional[str] = None) -> list[Dict[str, Any]]:
        """Return projects, optionally filtered by owner."""

        query = self.client.table("projects").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        response = query.order("updated_at", desc=True).execute()
        return response.data or []

    def save_generation_record(
        self,
        project_id: str,
        user_prompt: str,
        code: str,
        status: str,
        artifacts_urls: Dict[str, Optional[str]],
        error_log: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a generation and derive its version from the parent generation."""

        version_number = 1
        if parent_id:
            parent = (
                self.client.table("model_generations")
                .select("version_number")
                .eq("id", parent_id)
                .single()
                .execute()
            )
            if parent.data:
                version_number = int(parent.data["version_number"]) + 1

        record = {
            "project_id": project_id,
            "parent_generation_id": parent_id,
            "user_prompt": user_prompt,
            "cad_query_code": code,
            "execution_status": status,
            "error_log": error_log,
            "gltf_url": artifacts_urls.get("gltf_url"),
            "step_url": artifacts_urls.get("step_url"),
            "stl_url": artifacts_urls.get("stl_url"),
            "svg_blueprint_url": artifacts_urls.get("svg_blueprint_url"),
            "version_number": version_number,
        }
        response = self.client.table("model_generations").insert(record).execute()
        if not response.data:
            raise RuntimeError("Supabase did not return the inserted generation")
        return response.data[0]

    def get_project_history(self, project_id: str) -> list[Dict[str, Any]]:
        """Return generations in chronological order for a project."""

        response = (
            self.client.table("model_generations")
            .select("*")
            .eq("project_id", project_id)
            .order("version_number")
            .order("created_at")
            .execute()
        )
        return response.data or []


def artifact_path(project_id: str, generation_id: str, extension: str) -> str:
    """Build a stable, collision-resistant Storage path."""

    return f"projects/{project_id}/{generation_id}/{uuid4().hex}.{extension}"