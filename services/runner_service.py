# services/runner_service.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from services.storage_service import ensure_workspace, write_user_files, write_manifest_and_data
from services.artifact_service import list_artifacts


WORK_ROOT = Path(os.getenv("WORK_ROOT", "workspaces"))
RUNNER_IMAGE = os.getenv("RUNNER_IMAGE", "trading-runner:latest")

RUN_CPUS = os.getenv("RUN_CPUS", "1.0")
RUN_MEMORY = os.getenv("RUN_MEMORY", "768m")
RUN_PIDS = os.getenv("RUN_PIDS", "256")


def create_workspace(run_id: str) -> Path:
    ws = WORK_ROOT / run_id
    ensure_workspace(ws)
    return ws


def run_in_docker(ws: Path, entry: str = "main.py", timeout_sec: int = 30) -> Tuple[int, str, str]:
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--cpus", RUN_CPUS,
        "--memory", RUN_MEMORY,
        "--pids-limit", RUN_PIDS,
        "--security-opt", "no-new-privileges",
        "-v", f"{ws.resolve()}:/work",
        "-w", "/work",
        RUNNER_IMAGE,
        "python", entry
    ]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT"
