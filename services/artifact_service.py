# services/artifact_service.py
from __future__ import annotations

from pathlib import Path
from typing import List

from services.storage_service import safe_join


def list_artifacts(workspace: Path) -> List[str]:
    art_dir = workspace / "artifacts"
    if not art_dir.exists():
        return []
    return sorted([p.name for p in art_dir.iterdir() if p.is_file()])


def artifact_path(workspace: Path, name: str) -> Path:
    """
    Prevent path traversal: only allow artifacts within workspace/artifacts.
    """
    return safe_join(workspace / "artifacts", name)
