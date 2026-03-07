from __future__ import annotations

from urllib.parse import quote

import httpx

from src.config.settings import get_settings


class SupabaseStorageClient:
    def __init__(self, *, timeout_seconds: float = 30.0):
        settings = get_settings()
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL is not configured.")
        if not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        self.base_url = settings.supabase_url.rstrip("/")
        self.service_role_key = settings.supabase_service_role_key
        self.bucket_name = settings.supabase_storage_bucket_private
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

    def ensure_bucket(self) -> None:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.base_url}/storage/v1/bucket/{self.bucket_name}",
                headers=self._headers,
            )
            if response.status_code == 200:
                return
            response_text = (response.text or "").lower()
            bucket_missing = (
                response.status_code == 404
                or "bucket not found" in response_text
            )
            if not bucket_missing:
                response.raise_for_status()

            create_response = client.post(
                f"{self.base_url}/storage/v1/bucket",
                headers={**self._headers, "Content-Type": "application/json"},
                json={
                    "id": self.bucket_name,
                    "name": self.bucket_name,
                    "public": False,
                },
            )
            if create_response.status_code not in {200, 201, 409}:
                create_response.raise_for_status()

    def upload_bytes(self, *, storage_key: str, content: bytes, content_type: str | None) -> dict:
        object_path = quote(f"{self.bucket_name}/{storage_key}", safe="/")
        headers = {
            **self._headers,
            "x-upsert": "true",
            "Content-Type": content_type or "application/octet-stream",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/storage/v1/object/{object_path}",
                headers=headers,
                content=content,
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    def download_bytes(self, *, storage_key: str) -> bytes:
        object_path = quote(f"{self.bucket_name}/{storage_key}", safe="/")
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.base_url}/storage/v1/object/{object_path}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.content
