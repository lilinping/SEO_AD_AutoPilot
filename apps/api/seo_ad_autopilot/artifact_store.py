from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from .config import get_settings


@dataclass
class ArtifactReference:
    artifact_ref: str
    path: str


class ArtifactStoreProtocol(Protocol):
    def write_bytes(self, relative_path: str, content: bytes) -> ArtifactReference: ...
    def write_text(self, relative_path: str, content: str) -> ArtifactReference: ...
    def read_bytes(self, relative_path: str) -> bytes: ...
    def read_text(self, relative_path: str) -> str: ...


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_bytes(self, relative_path: str, content: bytes) -> ArtifactReference:
        path = self.resolve(relative_path)
        path.write_bytes(content)
        return ArtifactReference(artifact_ref=f"artifact://{relative_path}", path=str(path))

    def write_text(self, relative_path: str, content: str) -> ArtifactReference:
        path = self.resolve(relative_path)
        path.write_text(content, encoding="utf-8")
        return ArtifactReference(artifact_ref=f"artifact://{relative_path}", path=str(path))

    def read_bytes(self, relative_path: str) -> bytes:
        return self.resolve(relative_path).read_bytes()

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8")


class HttpArtifactStore:
    def __init__(self, base_url: str, token: str = "", timeout_ms: int = 4000) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token.strip()
        self.timeout_seconds = max(0.2, timeout_ms / 1000)

    def _target_url(self, relative_path: str) -> str:
        safe_path = "/".join(quote(part, safe="._-") for part in relative_path.split("/") if part)
        return urljoin(self.base_url, safe_path)

    def _write(self, relative_path: str, payload: bytes, content_type: str) -> ArtifactReference:
        target_url = self._target_url(relative_path)
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url=target_url, data=payload, method="PUT", headers=headers)
        with urlopen(request, timeout=self.timeout_seconds):
            pass
        return ArtifactReference(artifact_ref=f"artifact+http://{relative_path}", path=target_url)

    def write_bytes(self, relative_path: str, content: bytes) -> ArtifactReference:
        return self._write(relative_path, content, "application/octet-stream")

    def write_text(self, relative_path: str, content: str) -> ArtifactReference:
        return self._write(relative_path, content.encode("utf-8"), "application/json; charset=utf-8")

    def read_bytes(self, relative_path: str) -> bytes:
        target_url = self._target_url(relative_path)
        headers = {"Accept": "application/octet-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url=target_url, method="GET", headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return bytes(response.read() or b"")

    def read_text(self, relative_path: str) -> str:
        raw = self.read_bytes(relative_path)
        return raw.decode("utf-8")


def get_artifact_store() -> ArtifactStoreProtocol:
    settings = get_settings()
    backend = settings.artifact_store_backend.strip().lower()
    if backend == "http" and settings.artifact_store_http_base_url.strip():
        return HttpArtifactStore(
            base_url=settings.artifact_store_http_base_url.strip(),
            token=settings.artifact_store_http_token,
            timeout_ms=settings.artifact_store_http_timeout_ms,
        )
    return ArtifactStore(settings.state_dir / "artifacts")
