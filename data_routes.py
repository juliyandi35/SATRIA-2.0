"""The /api/data/actual and /api/data/reference routes, as a Flask Blueprint - the editable
source tables behind the computed readiness index. Split out for the same reason as
auth_routes.py: keeps app.py from growing past a sane line count."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from satria import readiness_service
from satria.data_service import DataRepository


def _payload() -> dict[str, Any]:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def _repo() -> DataRepository:
    return current_app.config["REPOSITORY"]


def build_data_blueprint(auth_db_path: Path) -> Blueprint:
    audit = logging.getLogger("satria.audit")
    bp = Blueprint("readiness_data", __name__, url_prefix="/api/data")

    def _recompute_active_dataset() -> dict[str, Any]:
        """Push the freshly computed tabel3 through the same import path a hand-uploaded
        readiness CSV would take, so quality checks and every downstream view stay consistent."""
        csv_bytes = readiness_service.compute_readiness_csv(auth_db_path)
        result = _repo().import_bytes(csv_bytes, "computed_readiness.csv", "computed")
        audit.info("READINESS RECOMPUTED rows=%s", result["metadata"]["rows"])
        return result

    @bp.get("/actual")
    def data_actual():
        payload = request.args
        return jsonify(readiness_service.list_actual(auth_db_path, int(payload.get("page", 1)), int(payload.get("page_size", 25))))

    @bp.post("/actual/update")
    def data_actual_update():
        payload = _payload()
        unit_node = str(payload.get("unit_node", ""))
        location = str(payload.get("location", ""))
        if not unit_node or not location:
            return jsonify({"status": "error", "error": "unit_node dan location diperlukan."}), 400
        fields = {key: value for key, value in payload.items() if key not in ("unit_node", "location")}
        row = readiness_service.update_actual(auth_db_path, unit_node, location, fields)
        _recompute_active_dataset()
        audit.info("ACTUAL DATA UPDATED unit_node=%s location=%s", unit_node, location)
        return jsonify({"status": "success", "record": row})

    @bp.post("/actual/import")
    def data_actual_import():
        upload = request.files.get("file")
        if upload is None:
            return jsonify({"status": "error", "error": "Berkas CSV/XLSX diperlukan."}), 400
        filename = Path(upload.filename or "").name
        result = readiness_service.import_actual_csv(auth_db_path, upload.read(), filename)
        active = _recompute_active_dataset()
        audit.info("ACTUAL DATA IMPORTED filename=%s rows=%s", filename, result["rows"])
        return jsonify({"status": "success", **result, "metadata": active["metadata"]})

    @bp.post("/status/override")
    def data_status_override():
        payload = _payload()
        unit_node = str(payload.get("unit_node", ""))
        location = str(payload.get("location", ""))
        category = str(payload.get("category", ""))
        status = str(payload.get("status", ""))
        if not unit_node or not location or not category:
            return jsonify({"status": "error", "error": "unit_node, location, dan category diperlukan."}), 400
        override = readiness_service.set_status_override(auth_db_path, unit_node, location, category, status)
        _recompute_active_dataset()
        audit.info(
            "READINESS STATUS OVERRIDDEN unit_node=%s location=%s category=%s status=%s",
            unit_node, location, category, override["status"],
        )
        return jsonify({"status": "success", "record": override})

    @bp.get("/export")
    def data_export():
        workbook = readiness_service.export_workbook_bytes(auth_db_path)
        audit.info("DATASET EXPORTED bytes=%s", len(workbook))
        return Response(
            workbook,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=\"Dataset SATRIA.xlsx\""},
        )

    @bp.get("/reference")
    def data_reference():
        return jsonify({"records": readiness_service.list_reference(auth_db_path)})

    @bp.post("/reference/update")
    def data_reference_update():
        payload = _payload()
        unit_type = str(payload.get("unit_type", ""))
        if not unit_type:
            return jsonify({"status": "error", "error": "unit_type diperlukan."}), 400
        fields = {key: value for key, value in payload.items() if key != "unit_type"}
        row = readiness_service.update_reference(auth_db_path, unit_type, fields)
        _recompute_active_dataset()
        audit.info("MEF REFERENCE UPDATED unit_type=%s", unit_type)
        return jsonify({"status": "success", "record": row})

    return bp
