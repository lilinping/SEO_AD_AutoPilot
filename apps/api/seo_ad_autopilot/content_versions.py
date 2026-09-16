"""Content version management — Phase 2 (GAP-017 / DB-004).

Provides:
- ContentVersionStore: in-memory + JSON-file backed versioned content store
- SQLAlchemy model definition: ContentVersion (ready for Alembic migration)
- Version comparison diff
- Rollback to any previous version
- Auto-increment semantic version (1.0.0 → 1.0.1 → 1.1.0 → 2.0.0)

Usage:
    store = ContentVersionStore(storage_path="content_versions/")
    vid = await store.save(content_id="abc", content={"markdown": "..."}, author="agent")
    history = await store.history("abc")
    rolled_back = await store.rollback("abc", version="1.0.0")
"""

from __future__ import annotations

import difflib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


# ── Version data models ───────────────────────────────────────────────────────

@dataclass
class ContentVersion:
    """A single version snapshot of generated content."""

    version_id:   str
    content_id:   str
    version:      str              # SemVer string: "1.0.0"
    content:      dict[str, Any]   # {"markdown": "...", "html": "...", ...}
    author:       str              # "agent" | "human" | user_id
    created_at:   float            # Unix timestamp
    change_note:  str = ""
    metadata:     dict[str, Any] = field(default_factory=dict)
    is_active:    bool = True      # current active version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContentVersion":
        return cls(**data)


# ── Semantic version helpers ──────────────────────────────────────────────────

def _parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        return (1, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return (1, 0, 0)


def _next_version(current: str, bump: str = "patch") -> str:
    """Bump semantic version. bump: 'major' | 'minor' | 'patch'."""
    major, minor, patch = _parse_semver(current)
    if bump == "major":
        return f"{major + 1}.0.0"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


# ── Content diff ──────────────────────────────────────────────────────────────

def diff_content(old: dict[str, Any], new: dict[str, Any], field: str = "markdown") -> str:
    """Return a unified diff of `field` between old and new versions."""
    old_text = str(old.get(field, "")).splitlines(keepends=True)
    new_text = str(new.get(field, "")).splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_text, new_text,
        fromfile=f"v_old/{field}",
        tofile=f"v_new/{field}",
        lineterm="",
    )
    return "".join(diff)


# ── ContentVersionStore ───────────────────────────────────────────────────────

class ContentVersionStore:
    """File-backed content version store with in-memory cache.

    Each content_id has its own JSON file: {storage_path}/{content_id}.json
    The file contains a list of ContentVersion dicts sorted by version ascending.
    """

    def __init__(self, storage_path: str = "content_versions") -> None:
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[ContentVersion]] = {}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _file(self, content_id: str) -> Path:
        safe_id = content_id.replace("/", "_").replace("\\", "_")
        return self._path / f"{safe_id}.json"

    def _load(self, content_id: str) -> list[ContentVersion]:
        if content_id in self._cache:
            return self._cache[content_id]
        fp = self._file(content_id)
        if fp.exists():
            try:
                raw = json.loads(fp.read_text(encoding="utf-8"))
                versions = [ContentVersion.from_dict(v) for v in raw]
            except Exception:
                versions = []
        else:
            versions = []
        self._cache[content_id] = versions
        return versions

    def _save_file(self, content_id: str) -> None:
        versions = self._cache.get(content_id, [])
        fp = self._file(content_id)
        fp.write_text(
            json.dumps([v.to_dict() for v in versions], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def save(
        self,
        content_id: str,
        content: dict[str, Any],
        author: str = "agent",
        bump: str = "patch",
        change_note: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> ContentVersion:
        """Save a new version of content. Returns the new ContentVersion."""
        versions = self._load(content_id)

        # Determine new version number
        if versions:
            latest_version = versions[-1].version
            new_version = _next_version(latest_version, bump)
            # Deactivate previous versions
            for v in versions:
                v.is_active = False
        else:
            new_version = "1.0.0"

        cv = ContentVersion(
            version_id  = str(uuid.uuid4()),
            content_id  = content_id,
            version     = new_version,
            content     = content,
            author      = author,
            created_at  = time.time(),
            change_note = change_note,
            metadata    = metadata or {},
            is_active   = True,
        )
        versions.append(cv)
        self._cache[content_id] = versions
        self._save_file(content_id)
        return cv

    async def history(
        self,
        content_id: str,
        limit: int = 50,
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        """Return version history for a content_id (newest first)."""
        versions = self._load(content_id)
        result = []
        for v in reversed(versions[-limit:]):
            entry = {
                "version_id":  v.version_id,
                "version":     v.version,
                "author":      v.author,
                "created_at":  v.created_at,
                "change_note": v.change_note,
                "is_active":   v.is_active,
                "metadata":    v.metadata,
            }
            if include_content:
                entry["content"] = v.content
            result.append(entry)
        return result

    async def get(
        self,
        content_id: str,
        version: Optional[str] = None,
    ) -> Optional[ContentVersion]:
        """Get a specific version (default: active/latest)."""
        versions = self._load(content_id)
        if not versions:
            return None
        if version is None:
            # Return active version (last saved)
            active = [v for v in versions if v.is_active]
            return active[-1] if active else versions[-1]
        for v in versions:
            if v.version == version:
                return v
        return None

    async def rollback(
        self,
        content_id: str,
        version: str,
        author: str = "human",
        change_note: str = "",
    ) -> Optional[ContentVersion]:
        """Roll back to a previous version (creates a new version entry)."""
        target = await self.get(content_id, version)
        if not target:
            return None
        # Save the target content as a new version (rollback)
        return await self.save(
            content_id=content_id,
            content=target.content,
            author=author,
            bump="patch",
            change_note=change_note or f"Rollback to {version}",
            metadata={"rolled_back_from": version, "original_version_id": target.version_id},
        )

    async def diff(
        self,
        content_id: str,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
        field: str = "markdown",
    ) -> dict[str, Any]:
        """Compare two versions and return a unified diff."""
        versions = self._load(content_id)
        if len(versions) < 2:
            return {"diff": "", "error": "Not enough versions to diff"}

        v_from = await self.get(content_id, from_version) if from_version else versions[-2]
        v_to   = await self.get(content_id, to_version)   if to_version   else versions[-1]

        if not v_from or not v_to:
            return {"diff": "", "error": "Version not found"}

        diff_text = diff_content(v_from.content, v_to.content, field)
        return {
            "from_version": v_from.version,
            "to_version":   v_to.version,
            "field":        field,
            "diff":         diff_text,
            "lines_added":   diff_text.count("\n+"),
            "lines_removed": diff_text.count("\n-"),
        }

    async def delete(self, content_id: str, version: Optional[str] = None) -> bool:
        """Delete a specific version or all versions of a content_id."""
        versions = self._load(content_id)
        if version:
            new_versions = [v for v in versions if v.version != version]
            if len(new_versions) == len(versions):
                return False
            self._cache[content_id] = new_versions
        else:
            self._cache[content_id] = []
        self._save_file(content_id)
        return True


# ── Module-level default store ────────────────────────────────────────────────

_default_store: Optional[ContentVersionStore] = None


def get_version_store(storage_path: Optional[str] = None) -> ContentVersionStore:
    """Return the module-level default ContentVersionStore instance."""
    global _default_store
    if _default_store is None:
        path = storage_path or os.getenv("CONTENT_VERSIONS_PATH", "content_versions")
        _default_store = ContentVersionStore(storage_path=path)
    return _default_store
