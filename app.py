# app.py
from __future__ import annotations

from flask import Flask, jsonify, render_template

from models.db import init_db
from api.auth import bp as auth_bp
from api.strategies import bp as strategies_bp
from api.runs import bp as runs_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )

    init_db()

    app.register_blueprint(auth_bp)
    app.register_blueprint(strategies_bp)
    app.register_blueprint(runs_bp)

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.get("/")
    def home():
        try:
            return render_template("index.html")
        except Exception:
            return "OK: Flask server running"

    @app.get("/brokers")
    def brokers():
        return render_template("brokers.html")

    @app.get("/controls")
    def controls():
        return render_template("controls.html")

    @app.get("/backtests")
    def backtests():
        return render_template("backtests.html")

    @app.get("/stream")
    def stream():
        return render_template("stream.html")
    @app.get("/scripts")
    def scripts_page():
        return render_template("scripts.html")

        
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)