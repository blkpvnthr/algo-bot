# api/auth.py
from __future__ import annotations

import os
from flask import Blueprint, jsonify, request

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def current_user_id() -> str:
    """
    MVP:
      - if X-User-Id header exists, use it
      - else fall back to DEMO_USER_ID env
    Replace with real auth later.
    """
    hdr = (request.headers.get("X-User-Id") or "").strip()
    if hdr:
        return hdr
    return os.getenv("DEMO_USER_ID", "demo-user")


@bp.get("/whoami")
def whoami():
    return jsonify({"user_id": current_user_id()})
