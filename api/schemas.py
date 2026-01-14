# api/schemas.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.limits import (
    MAX_ENTRYPOINT_LEN,
    MAX_FILE_BYTES,
    MAX_STRATEGY_DESC_LEN,
    MAX_STRATEGY_NAME_LEN,
    MAX_TOTAL_BYTES,
    MAX_TOTAL_FILES,
)


@dataclass
class StrategyUpsertRequest:
    name: str
    description: str
    entry: str
    files: dict[str, str]


def _require_str(obj: Any, key: str, default: str = "") -> str:
    v = obj.get(key, default)
    if v is None:
        return default
    if not isinstance(v, str):
        raise ValueError(f"{key} must be a string")
    return v


def _require_dict(obj: Any, key: str) -> dict[str, Any]:
    v = obj.get(key)
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"{key} must be an object")
    return v


def _validate_files(files: dict[str, Any]) -> dict[str, str]:
    if len(files) > MAX_TOTAL_FILES:
        raise ValueError(f"Too many files (max {MAX_TOTAL_FILES})")

    total = 0
    out: dict[str, str] = {}

    for name, content in files.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("File names must be non-empty strings")
        if not isinstance(content, str):
            raise ValueError(f"File '{name}' content must be a string")

        b = content.encode("utf-8")
        if len(b) > MAX_FILE_BYTES:
            raise ValueError(f"File '{name}' too large (max {MAX_FILE_BYTES} bytes)")

        total += len(b)
        out[name] = content

    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"Total files too large (max {MAX_TOTAL_BYTES} bytes)")

    return out


def parse_strategy_upsert(body: dict[str, Any]) -> StrategyUpsertRequest:
    name = _require_str(body, "name").strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > MAX_STRATEGY_NAME_LEN:
        raise ValueError(f"name too long (max {MAX_STRATEGY_NAME_LEN})")

    description = _require_str(body, "description", "")
    if len(description) > MAX_STRATEGY_DESC_LEN:
        raise ValueError(f"description too long (max {MAX_STRATEGY_DESC_LEN})")

    entry = _require_str(body, "entry", "main.py").strip() or "main.py"
    if len(entry) > MAX_ENTRYPOINT_LEN:
        raise ValueError(f"entry too long (max {MAX_ENTRYPOINT_LEN})")

    files = body.get("files")
    if not isinstance(files, dict) or not files:
        # accept single-file "code" fallback
        code = _require_str(body, "code", "")
        files = {"main.py": code if code else "print('hello')\n"}

    safe_files = _validate_files(files)
    return StrategyUpsertRequest(name=name, description=description, entry=entry, files=safe_files)
