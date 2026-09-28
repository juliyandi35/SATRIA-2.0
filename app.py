from __future__ import annotations

import json
import logging
import os
import platform
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException

load_dotenv(Path(__file__).with_name('.env'))

from SATRIA_backend import (
    ask_satria,
    bind_repository,
    clear_session,
    model_status,
)
from satria import readiness_service
from satria.analytics_service import data_diagnostics, hidden_risk, spatial_clusters
from satria.data_service import DataRepository, DataValidationError
from auth_routes import AUTH_EXEMPT_PATHS, build_auth_blueprint
from data_routes import build_data_blueprint
from services.auth_service import AuthError, get_secret_key
from services.email_service import email_configuration_status, send_email_tool


PROJECT_ROOT = Path(__file__).resolve().parent
AUDIT_LOG = PROJECT_ROOT / "system_audit.log"
DATABASE_PATH = PROJECT_ROOT / "checkpoints.db"
BUILTIN_DATASET = PROJECT_ROOT / "data" / "tabel3_readiness.csv"


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("satria.audit")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(AUDIT_LOG, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
    return logger


AUDIT = _configure_logging()


def _payload() -> dict[str, Any]:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _error(message: str, status: int = 400, details: dict[str, Any] | None = None):
    body: dict[str, Any] = {"status": "error", "error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def _frame_from_legacy_data(data: Any) -> pd.DataFrame | None:
    if not isinstance(data, list) or not data:
        return None
    frame = pd.DataFrame(data)
    aliases = {"latitude": "lat", "longitude": "lon", "UNIT_NODE": "unit"}
    frame = frame.rename(columns=aliases)
    return frame


def _numeric(payload: dict[str, Any], key: str, default: float) -> float:
    """Read a numeric payload field, treating an explicit JSON null the same as absent."""
    value = payload.get(key, default)
    return default if value is None else value


def create_app(repository: DataRepository | None = None, database_path: Path | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    auth_db_path = database_path or DATABASE_PATH
    app.secret_key = get_secret_key(auth_db_path)
    app.config.update(
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        JSON_SORT_KEYS=False,
        REPOSITORY=repository or DataRepository(PROJECT_ROOT),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    bind_repository(app.config["REPOSITORY"])
    app.register_blueprint(build_auth_blueprint(auth_db_path))
    app.register_blueprint(build_data_blueprint(auth_db_path))
    readiness_service.seed_if_empty(auth_db_path, PROJECT_ROOT)

    def repo() -> DataRepository:
        return app.config["REPOSITORY"]

    @app.before_request
    def require_login():
        if not request.path.startswith("/api/") or request.path in AUTH_EXEMPT_PATHS:
            return None
        if not session.get("authenticated"):
            return _error("Sesi tidak ditemukan. Silakan masuk kembali.", 401)
        return None

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    @app.errorhandler(413)
    def payload_too_large(_error_value):
        return _error("Ukuran unggahan melebihi batas 25 MB.", 413)

    @app.errorhandler(DataValidationError)
    def validation_error(error: DataValidationError):
        return _error(str(error), 400, error.details)

    @app.errorhandler(AuthError)
    def auth_error(error: AuthError):
        return _error(str(error), error.status)

    @app.errorhandler(404)
    def not_found(_error_value):
        if request.path.startswith("/api/"):
            return _error("Endpoint tidak ditemukan.", 404)
        return render_template("index.html"), 404

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return _error(error.description or "Permintaan tidak dapat diproses.", error.code or 500)
        return error

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        app.logger.exception("Unhandled SATRIA error")
        if request.path.startswith("/api/"):
            return _error("Sistem tidak dapat menyelesaikan permintaan ini.", 500)
        return "SATRIA tidak dapat dimuat.", 500

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/data/status")
    def data_status():
        return jsonify(repo().status())

    @app.post("/api/data/import")
    def import_dataset():
        upload = request.files.get("file")
        if upload is not None:
            filename = Path(upload.filename or "dataset.csv").name
            result = repo().import_bytes(upload.read(), filename, "upload")
        else:
            payload = _payload()
            source = payload.get("source", "builtin")
            if source != "builtin":
                return _error("Sumber impor tidak dikenali.")
            # Readiness is always computed live from the (editable) actual + MEF reference
            # tables, never read as a frozen file - this keeps it consistent with any edits
            # made via Kelola Data.
            csv_bytes = readiness_service.compute_readiness_csv(auth_db_path)
            result = repo().import_bytes(csv_bytes, "computed_readiness.csv", "computed")
        AUDIT.info("DATA IMPORT filename=%s rows=%s", result["metadata"]["filename"], result["metadata"]["rows"])
        return jsonify(result)

    @app.post("/api/data/reset")
    def reset_dataset():
        repo().reset()
        AUDIT.info("DATA STATE RESET")
        return jsonify({"status": "success", "message": "Dataset dilepas dari memori aktif."})

    @app.get("/api/data/summary")
    def data_summary():
        return jsonify({"summary": repo().summary(), "metadata": repo().status().get("metadata")})

    @app.post("/api/data/view")
    @app.post("/api/data/filter")
    def data_view():
        payload = _payload()
        result = repo().view(
            payload.get("filters", {}),
            page=_numeric(payload, "page", 1),
            page_size=_numeric(payload, "page_size", 20),
            search=str(payload.get("search", "")),
            sort_by=str(payload.get("sort_by", "readiness")),
            sort_order=str(payload.get("sort_order", "asc")),
        )
        return jsonify(result)

    @app.get("/api/data/explorer")
    def legacy_data_explorer():
        if not repo().loaded:
            return jsonify([])
        return jsonify(repo().view(page=1, page_size=100)["records"])

    @app.get("/api/data/raw/<int:source_index>")
    def raw_record(source_index: int):
        record = repo().raw_record(source_index)
        if record is None:
            return _error("Baris sumber tidak ditemukan.", 404)
        return jsonify({"source_index": source_index, "raw": record})

    @app.post("/api/data/diagnostics")
    def diagnostics():
        payload = _payload()
        legacy = _frame_from_legacy_data(payload.get("data"))
        frame = legacy if legacy is not None else repo().frame(payload.get("filters", {}))
        source_quality = repo().status().get("quality") if repo().loaded else None
        try:
            return jsonify(data_diagnostics(frame, source_quality))
        except ValueError as error:
            return _error(str(error), 422)

    @app.post("/api/spatial/clusters")
    def clusters():
        payload = _payload()
        legacy = _frame_from_legacy_data(payload.get("data"))
        frame = legacy if legacy is not None else repo().frame(payload.get("filters", {}))
        result = spatial_clusters(
            frame,
            epsilon_km=float(_numeric(payload, "epsilon_km", 150)),
            min_samples=int(_numeric(payload, "min_samples", 3)),
        )
        return jsonify(result)

    @app.post("/api/predictive/forecast")
    def predictive_forecast():
        payload = _payload()
        legacy = _frame_from_legacy_data(payload.get("data"))
        frame = legacy if legacy is not None else repo().frame(payload.get("filters", {}))
        try:
            result = hidden_risk(frame, limit=int(_numeric(payload, "limit", 15)))
        except ValueError as error:
            return _error(str(error), 422)
        return jsonify(result)

    @app.get("/api/models")
    def models():
        return jsonify({"provider": "Ollama Local", "models": model_status()})

    @app.post("/api/chat")
    def chat():
        payload = _payload()
        message = str(payload.get("message", "")).strip()
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        filters = context.get("filters") if isinstance(context.get("filters"), dict) else {}
        context = {
            **context,
            "authoritative_data": repo().ai_context(filters),
        }
        audit_enabled = bool(context.get("audit_log", False))
        if audit_enabled:
            AUDIT.info("QUERY IN session=%s message=%s", payload.get("session_id"), message[:1000])
        try:
            response = ask_satria(
                user_query=message,
                active_unit=str(payload.get("active_unit", "National")),
                selected_region=str(payload.get("selected_region", "All")),
                dashboard_context=context,
                session_id=str(payload.get("session_id", "satria-session")),
                local_exec=bool(context.get("local_exec", True)),
                ai_model=str(context.get("ai_model", "granite4.2:3b")),
            )
        except (ValueError, RuntimeError) as error:
            return _error(str(error), 422)
        if audit_enabled:
            AUDIT.info("RESPONSE OUT session=%s response=%s", payload.get("session_id"), response[:2000])
        return jsonify({"response": response})

    @app.post("/api/chat/session/clear")
    def clear_chat_session():
        session_id = str(_payload().get("session_id", ""))
        if not session_id:
            return _error("Session ID diperlukan.")
        deleted = clear_session(session_id)
        return jsonify({"status": "success", "deleted_messages": deleted})

    @app.post("/api/email/report")
    def email_report():
        if not repo().loaded:
            return _error("Impor dataset sebelum membuat laporan.", 409)
        payload = _payload()
        recipient = str(payload.get("email", "")).strip()
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        summary = repo().summary(filters)
        body = (
            "SATRIA 2.0 — Ringkasan Intelijen Kesiapan\n\n"
            f"Rekaman aktif: {summary['record_count']}\n"
            f"Unit: {summary['unit_count']}\n"
            f"Provinsi: {summary['province_count']}\n"
            f"Rata-rata kesiapan: {summary['average_readiness']}\n"
            f"Median kesiapan: {summary['median_readiness']}\n"
            f"Observasi ditandai: {summary['flagged_count']}\n"
            f"Observasi memerlukan perhatian: {summary['attention_count']}\n"
            f"Sinkronisasi terbaru: {summary['latest_sync']}\n\n"
            "Semua nilai dihitung dari dataset aktif pada saat laporan dibuat."
        )
        try:
            message = send_email_tool(recipient, "SATRIA 2.0 — Ringkasan Intelijen", body)
        except (RuntimeError, ValueError) as error:
            return _error(str(error), 422)
        return jsonify({"status": "success", "message": message})

    @app.post("/api/email/audit-log")
    def email_audit_log():
        if not AUDIT_LOG.exists() or AUDIT_LOG.stat().st_size == 0:
            return _error("Log audit masih kosong.", 409)
        recipient = str(_payload().get("email", "")).strip()
        content = AUDIT_LOG.read_text(encoding="utf-8", errors="replace")
        try:
            message = send_email_tool(
                recipient,
                "SATRIA 2.0 — Audit Log",
                "Log audit sistem SATRIA 2.0 terlampir.",
                attachment=(content.encode("utf-8"), "system_audit.log"),
            )
        except (RuntimeError, ValueError) as error:
            return _error(str(error), 422)
        return jsonify({"status": "success", "message": message})

    @app.get("/api/logs")
    def recent_logs():
        if not AUDIT_LOG.exists():
            return jsonify({"lines": [], "size_bytes": 0})
        lines = AUDIT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]
        return jsonify({"lines": lines, "size_bytes": AUDIT_LOG.stat().st_size})

    @app.post("/api/logs/clear")
    def clear_logs():
        for handler in AUDIT.handlers:
            handler.flush()
        AUDIT_LOG.write_text("", encoding="utf-8")
        return jsonify({"status": "success", "message": "Log aktivitas telah dikosongkan."})

    @app.get("/api/db/test")
    def test_database():
        if not DATABASE_PATH.is_file():
            return _error("Database checkpoints.db tidak ditemukan.", 404)
        connection = sqlite3.connect(DATABASE_PATH, timeout=3)
        try:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            return jsonify(
                {
                    "status": "success",
                    "message": "Koneksi SQLite berhasil.",
                    "tables": tables,
                    "size_bytes": DATABASE_PATH.stat().st_size,
                }
            )
        except sqlite3.Error:
            return _error("Database checkpoint tidak dapat dibuka.", 500)
        finally:
            connection.close()

    @app.get("/api/system/status")
    def system_status():
        db_ok = False
        try:
            connection = sqlite3.connect(DATABASE_PATH, timeout=2)
            try:
                connection.execute("SELECT 1").fetchone()
                db_ok = True
            finally:
                connection.close()
        except sqlite3.Error:
            pass
        models_value = model_status()
        ollama_online = any(item["ollama_online"] for item in models_value)
        return jsonify(
            {
                "backend": {
                    "status": "online",
                    "runtime": "Flask",
                    "python": {
                        "version": platform.python_version(),
                        "executable": sys.executable,
                        "base_prefix": sys.base_prefix,
                    },
                },
                "dataset": repo().status(),
                "ollama": {"status": "online" if ollama_online else "offline", "models": models_value},
                "checkpoint_database": {"status": "online" if db_ok else "error"},
                "mysql": {"status": "configured" if os.getenv("DB_HOST") else "not_configured"},
                "email": email_configuration_status(),
                "external_search": {"configured": bool(os.getenv("SATRIA_EXTERNAL_SEARCH", ""))},
                "builtin_dataset": {"available": BUILTIN_DATASET.is_file()},
            }
        )

    @app.get("/api/geography/provinces")
    def provinces_geojson():
        path = PROJECT_ROOT / "data" / "indonesia-38-provinces.geojson"
        if not path.is_file():
            return _error("Batas provinsi tidak tersedia.", 404)
        return send_file(path, mimetype="application/geo+json", conditional=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False, use_reloader=False, threaded=True)
