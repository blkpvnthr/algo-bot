# api/strategies.py
from __future__ import annotations

from flask import Blueprint, jsonify, request

from api.schemas import parse_strategy_upsert
from models.strategy_repo import (
    create_strategy,
    delete_strategy,
    get_strategy,
    list_strategies,
    update_strategy,
)

bp = Blueprint("strategies", __name__, url_prefix="/api/strategies")


def _user_id() -> str:
    # MVP until auth is wired
    return "demo-user"


@bp.get("")
def http_list_strategies():
    uid = _user_id()
    return jsonify(list_strategies(user_id=uid))


@bp.post("")
def http_create_strategy():
    uid = _user_id()
    body = request.get_json(force=True) or {}

    req = parse_strategy_upsert(body)  # <-- body defined here, inside the handler

    strategy_id = create_strategy(
        user_id=uid,
        name=req.name,
        description=req.description,
        entry=req.entry,
        files=req.files,
    )
    return jsonify({"id": strategy_id}), 201


@bp.get("/<strategy_id>")
def http_get_strategy(strategy_id: str):
    uid = _user_id()
    s = get_strategy(user_id=uid, strategy_id=strategy_id)
    if not s:
        return jsonify({"error": "not found"}), 404
    return jsonify(s)


@bp.put("/<strategy_id>")
def http_update_strategy(strategy_id: str):
    uid = _user_id()
    body = request.get_json(force=True) or {}

    req = parse_strategy_upsert(body)

    ok = update_strategy(
        user_id=uid,
        strategy_id=strategy_id,
        name=req.name,
        description=req.description,
        entry=req.entry,
        files=req.files,
    )
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@bp.delete("/<strategy_id>")
def http_delete_strategy(strategy_id: str):
    uid = _user_id()
    ok = delete_strategy(user_id=uid, strategy_id=strategy_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})
