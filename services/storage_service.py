# services/storage_service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def safe_join(base: Path, name: str) -> Path:
    """
    Prevent path traversal. Only allow paths inside `base`.
    """
    base = base.resolve()
    p = (base / name).resolve()
    if base not in p.parents and p != base:
        raise ValueError("invalid path")
    return p


def ensure_workspace(ws: Path) -> None:
    (ws / "data").mkdir(parents=True, exist_ok=True)
    (ws / "artifacts").mkdir(parents=True, exist_ok=True)


def write_user_files(ws: Path, files: Dict[str, str]) -> None:
    """
    Supports nested paths like 'src/utils.py', but stays inside ws.
    """
    for rel, content in (files or {}).items():
        rel = rel.strip().lstrip("/").replace("\\", "/")
        p = safe_join(ws, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")


def write_manifest_and_data(ws: Path, meta: dict, frames: Dict[str, pd.DataFrame]) -> None:
    """
    Writes parquet files to ws/data and a ws/data/manifest.json
    """
    ensure_workspace(ws)

    symbols = []
    for sym, df in (frames or {}).items():
        outp = ws / "data" / f"{sym}.parquet"
        df.to_parquet(outp, index=False)
        symbols.append({"symbol": sym, "path": f"data/{sym}.parquet"})

    manifest = {"meta": meta, "symbols": symbols}
    (ws / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def read_manifest(ws: Path) -> dict:
    p = ws / "data" / "manifest.json"
    if not p.exists():
        return {"meta": {}, "symbols": []}
    return json.loads(p.read_text(encoding="utf-8"))
