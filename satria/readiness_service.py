"""Readiness = actual capability vs the MEF (Minimum Essential Force) standard, as a percentage.

Two small editable source tables live here: the actual figures per unit (tabel1) and the MEF
reference per unit type (tabel2). Tabel3 (readiness) is never stored - it is always recomputed
from whatever tabel1/tabel2 currently hold, so it can never drift out of sync with an edit.
"""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from satria.data_service import DataValidationError

CATEGORIES = ("Personnel", "Equipment", "Logistics", "Infrastructure", "Training")
FLAGGED_BELOW = 75.0  # matches the deterministic floor observed in the original reference dataset
STATUS_VALUES = ("FLAGGED", "VERIFIED")


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=5)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS actual_data (
            unit_node TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            location TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            personnel REAL NOT NULL,
            equipment REAL NOT NULL,
            logistics REAL NOT NULL,
            infrastructure REAL NOT NULL,
            training REAL NOT NULL,
            PRIMARY KEY (unit_node, location)
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS mef_reference (
            unit_type TEXT PRIMARY KEY,
            personnel REAL NOT NULL,
            equipment REAL NOT NULL,
            logistics REAL NOT NULL,
            infrastructure REAL NOT NULL,
            training REAL NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS status_override (
            unit_node TEXT NOT NULL,
            location TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (unit_node, location, category)
        )"""
    )
    _migrate_legacy_actual_schema(connection)
    return connection


def _migrate_legacy_actual_schema(connection: sqlite3.Connection) -> None:
    """An early build keyed actual_data on unit_node alone, which silently collapsed unit
    designations that are reused at more than one location. Rebuild on the composite key -
    the table only ever holds data reseeded from the bundled CSV or re-imported by an admin,
    so a clean rebuild (not a row-preserving copy) is the correct, simplest fix."""
    row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'actual_data'").fetchone()
    if row is None or "PRIMARY KEY (unit_node, location)" in (row[0] or ""):
        return
    connection.execute("DROP TABLE actual_data")
    connection.execute(
        """CREATE TABLE actual_data (
            unit_node TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            location TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            personnel REAL NOT NULL,
            equipment REAL NOT NULL,
            logistics REAL NOT NULL,
            infrastructure REAL NOT NULL,
            training REAL NOT NULL,
            PRIMARY KEY (unit_node, location)
        )"""
    )
    connection.commit()


def _category_columns() -> list[str]:
    return [category.lower() for category in CATEGORIES]


def seed_if_empty(db_path: Path, project_root: Path) -> None:
    """First run only: load the bundled tabel1/tabel2 CSVs as the starting editable data."""
    connection = _connect(db_path)
    try:
        has_actual = connection.execute("SELECT 1 FROM actual_data LIMIT 1").fetchone()
        has_reference = connection.execute("SELECT 1 FROM mef_reference LIMIT 1").fetchone()
        if not has_actual:
            actual_path = project_root / "data" / "tabel1_actual.csv"
            if actual_path.is_file():
                _replace_actual(connection, pd.read_csv(actual_path))
        if not has_reference:
            reference_path = project_root / "data" / "tabel2_mef_reference.csv"
            if reference_path.is_file():
                _replace_reference(connection, pd.read_csv(reference_path))
        connection.commit()
    finally:
        connection.close()


def _read_actual_frame(payload: bytes, filename: str = "") -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        try:
            frame = pd.read_excel(io.BytesIO(payload), engine="openpyxl")
        except Exception as error:  # openpyxl/xlrd raise several distinct types on bad files
            raise DataValidationError("Berkas Excel tidak dapat dibaca.") from error
    else:
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                frame = pd.read_csv(io.BytesIO(payload), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise DataValidationError("Encoding CSV tidak dapat dibaca.")
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    required = {"UNIT_TYPE", "UNIT_NODE", "LOCATION", "LATITUDE", "LONGITUDE", *[c.upper() for c in CATEGORIES]}
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError("CSV data aktual tidak memiliki kolom wajib.", {"missing_fields": sorted(missing)})
    return frame


def _replace_actual(connection: sqlite3.Connection, frame: pd.DataFrame) -> int:
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    connection.execute("DELETE FROM actual_data")
    rows = []
    for _, row in frame.iterrows():
        try:
            values = [float(row[category.upper()]) for category in CATEGORIES]
        except (TypeError, ValueError):
            raise DataValidationError(f"Nilai numerik tidak valid pada unit {row.get('UNIT_NODE')}.") from None
        if any(value < 0 for value in values):
            raise DataValidationError(f"Nilai aktual tidak boleh negatif (unit {row.get('UNIT_NODE')}).")
        rows.append(
            (
                str(row["UNIT_NODE"]).strip(),
                str(row["UNIT_TYPE"]).strip(),
                str(row["LOCATION"]).strip(),
                float(row["LATITUDE"]),
                float(row["LONGITUDE"]),
                *values,
            )
        )
    connection.executemany(
        "INSERT OR REPLACE INTO actual_data "
        "(unit_node, unit_type, location, lat, lon, personnel, equipment, logistics, infrastructure, training) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _replace_reference(connection: sqlite3.Connection, frame: pd.DataFrame) -> int:
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    connection.execute("DELETE FROM mef_reference")
    rows = []
    for _, row in frame.iterrows():
        try:
            values = [float(row[category.upper()]) for category in CATEGORIES]
        except (TypeError, ValueError):
            raise DataValidationError(f"Nilai numerik tidak valid pada tipe unit {row.get('UNIT_TYPE')}.") from None
        if any(value <= 0 for value in values):
            raise DataValidationError(f"Nilai referensi MEF harus lebih besar dari nol ({row.get('UNIT_TYPE')}).")
        rows.append((str(row["UNIT_TYPE"]).strip(), *values))
    connection.executemany(
        "INSERT OR REPLACE INTO mef_reference (unit_type, personnel, equipment, logistics, infrastructure, training) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def import_actual_csv(db_path: Path, payload: bytes, filename: str = "") -> dict[str, Any]:
    frame = _read_actual_frame(payload, filename)
    connection = _connect(db_path)
    try:
        count = _replace_actual(connection, frame)
        connection.commit()
    finally:
        connection.close()
    return {"rows": count}


def list_actual(db_path: Path, page: int = 1, page_size: int = 25) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        total = connection.execute("SELECT COUNT(*) FROM actual_data").fetchone()[0]
        page_size = max(10, min(int(page_size), 100))
        total_pages = max(1, -(-total // page_size))
        page = max(1, min(int(page), total_pages))
        offset = (page - 1) * page_size
        rows = connection.execute(
            "SELECT unit_node, unit_type, location, lat, lon, personnel, equipment, logistics, infrastructure, training "
            "FROM actual_data ORDER BY unit_node LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
    finally:
        connection.close()
    columns = ["unit_node", "unit_type", "location", "lat", "lon", *_category_columns()]
    return {
        "records": [dict(zip(columns, row)) for row in rows],
        "pagination": {"page": page, "page_size": page_size, "total_records": total, "total_pages": total_pages},
    }


def update_actual(db_path: Path, unit_node: str, location: str, fields: dict[str, Any]) -> dict[str, Any]:
    """unit_node alone is not a unique key - the same designation can appear at more than one
    location (two different physical detachments) - so (unit_node, location) together identify
    the row, matching how the rest of the app already groups units for rankings."""
    updates = _validate_category_fields(fields, allow_zero=True)
    if not updates:
        raise DataValidationError("Tidak ada nilai yang diperbarui.")
    connection = _connect(db_path)
    try:
        if not connection.execute(
            "SELECT 1 FROM actual_data WHERE unit_node = ? AND location = ?", (unit_node, location)
        ).fetchone():
            raise DataValidationError("Unit tidak ditemukan.", {"unit_node": unit_node, "location": location})
        assignments = ", ".join(f"{column} = ?" for column in updates)
        connection.execute(
            f"UPDATE actual_data SET {assignments} WHERE unit_node = ? AND location = ?",
            (*updates.values(), unit_node, location),
        )
        connection.commit()
        row = connection.execute(
            "SELECT unit_node, unit_type, location, lat, lon, personnel, equipment, logistics, infrastructure, training "
            "FROM actual_data WHERE unit_node = ? AND location = ?",
            (unit_node, location),
        ).fetchone()
    finally:
        connection.close()
    columns = ["unit_node", "unit_type", "location", "lat", "lon", *_category_columns()]
    return dict(zip(columns, row))


def list_reference(db_path: Path) -> list[dict[str, Any]]:
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            "SELECT unit_type, personnel, equipment, logistics, infrastructure, training FROM mef_reference ORDER BY unit_type"
        ).fetchall()
    finally:
        connection.close()
    columns = ["unit_type", *_category_columns()]
    return [dict(zip(columns, row)) for row in rows]


def update_reference(db_path: Path, unit_type: str, fields: dict[str, Any]) -> dict[str, Any]:
    updates = _validate_category_fields(fields, allow_zero=False)
    if not updates:
        raise DataValidationError("Tidak ada nilai yang diperbarui.")
    connection = _connect(db_path)
    try:
        if not connection.execute("SELECT 1 FROM mef_reference WHERE unit_type = ?", (unit_type,)).fetchone():
            raise DataValidationError("Tipe unit tidak ditemukan.", {"unit_type": unit_type})
        assignments = ", ".join(f"{column} = ?" for column in updates)
        connection.execute(
            f"UPDATE mef_reference SET {assignments} WHERE unit_type = ?",
            (*updates.values(), unit_type),
        )
        connection.commit()
        row = connection.execute(
            "SELECT unit_type, personnel, equipment, logistics, infrastructure, training FROM mef_reference WHERE unit_type = ?",
            (unit_type,),
        ).fetchone()
    finally:
        connection.close()
    columns = ["unit_type", *_category_columns()]
    return dict(zip(columns, row))


def _validate_category_fields(fields: dict[str, Any], *, allow_zero: bool) -> dict[str, float]:
    valid_columns = set(_category_columns())
    updates: dict[str, float] = {}
    for key, value in fields.items():
        column = str(key).strip().lower()
        if column not in valid_columns:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise DataValidationError(f"Nilai {key} harus berupa angka.") from None
        if number < 0 or (not allow_zero and number <= 0):
            raise DataValidationError(f"Nilai {key} harus {'lebih besar dari nol' if not allow_zero else 'tidak boleh negatif'}.")
        updates[column] = number
    return updates


READINESS_HEADER = ["RECORD_ID", "CATEGORY", "UNIT_NODE", "LOCATION", "LATITUDE", "LONGITUDE", "READINESS_IDX", "STATUS", "LAST_SYNC"]


def _fetch_actual_and_reference(connection: sqlite3.Connection) -> tuple[list[Any], list[Any]]:
    actual_rows = connection.execute(
        "SELECT unit_node, unit_type, location, lat, lon, personnel, equipment, logistics, infrastructure, training FROM actual_data"
    ).fetchall()
    reference_rows = connection.execute(
        "SELECT unit_type, personnel, equipment, logistics, infrastructure, training FROM mef_reference"
    ).fetchall()
    if not actual_rows:
        raise DataValidationError("Belum ada data aktual untuk dihitung.")
    if not reference_rows:
        raise DataValidationError("Belum ada referensi MEF untuk dihitung.")
    return actual_rows, reference_rows


def _fetch_status_overrides(connection: sqlite3.Connection) -> dict[tuple[str, str, str], str]:
    rows = connection.execute("SELECT unit_node, location, category, status FROM status_override").fetchall()
    return {(unit_node, location, category): status for unit_node, location, category, status in rows}


def set_status_override(db_path: Path, unit_node: str, location: str, category: str, status: str) -> dict[str, Any]:
    """Manually pin a unit x category's readiness STATUS to FLAGGED or VERIFIED, overriding the
    75% threshold used by default. The override survives until toggled again or the underlying
    actual/reference values are edited enough to trigger a fresh look - it is not cleared
    automatically, matching how an analyst's manual verification call should persist."""
    status = status.strip().upper()
    if status not in STATUS_VALUES:
        raise DataValidationError("Status harus FLAGGED atau VERIFIED.")
    if category not in CATEGORIES:
        raise DataValidationError("Kategori tidak dikenali.", {"category": category})
    connection = _connect(db_path)
    try:
        if not connection.execute(
            "SELECT 1 FROM actual_data WHERE unit_node = ? AND location = ?", (unit_node, location)
        ).fetchone():
            raise DataValidationError("Unit tidak ditemukan.", {"unit_node": unit_node, "location": location})
        connection.execute(
            "INSERT OR REPLACE INTO status_override (unit_node, location, category, status) VALUES (?, ?, ?, ?)",
            (unit_node, location, category, status),
        )
        connection.commit()
    finally:
        connection.close()
    return {"unit_node": unit_node, "location": location, "category": category, "status": status}


def _build_readiness_rows(
    actual_rows: list[Any], reference_rows: list[Any], overrides: dict[tuple[str, str, str], str] | None = None
) -> list[list[Any]]:
    """readiness = actual / MEF reference x 100, one row per unit x category (long format).
    A manual status_override, if present for that unit x location x category, wins over the
    computed FLAGGED_BELOW threshold."""
    overrides = overrides or {}
    reference = {row[0]: dict(zip(_category_columns(), row[1:])) for row in reference_rows}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows: list[list[Any]] = []
    record_index = 10001
    for unit_node, unit_type, location, lat, lon, *values in actual_rows:
        mef = reference.get(unit_type)
        if mef is None:
            raise DataValidationError(f"Tidak ada referensi MEF untuk tipe unit {unit_type}.")
        for category, actual_value in zip(CATEGORIES, values):
            mef_value = mef[category.lower()]
            readiness = round(actual_value / mef_value * 100, 1) if mef_value else 0.0
            status = overrides.get((unit_node, location, category)) or (
                "FLAGGED" if readiness < FLAGGED_BELOW else "VERIFIED"
            )
            rows.append([f"SDP-{record_index}", category, unit_node, location, lat, lon, readiness, status, now])
            record_index += 1
    return rows


def compute_readiness_csv(db_path: Path) -> bytes:
    """Recompute tabel3 (long format: one row per unit x category) from current tabel1/tabel2.
    Returns CSV bytes shaped exactly like the hand-uploadable tabel3_readiness.csv, so it can go
    straight through the existing importer and its already-tested normalization and quality checks."""
    connection = _connect(db_path)
    try:
        actual_rows, reference_rows = _fetch_actual_and_reference(connection)
        overrides = _fetch_status_overrides(connection)
    finally:
        connection.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(READINESS_HEADER)
    writer.writerows(_build_readiness_rows(actual_rows, reference_rows, overrides))
    return buffer.getvalue().encode("utf-8")


def export_workbook_bytes(db_path: Path) -> bytes:
    """Single-file snapshot of all three tables as one .xlsx workbook: Aktual, Referensi, then
    Kesiapan, in that sheet order. Aktual/Referensi use the same headers the CSV/xlsx importers
    expect, so the export can be edited and re-imported directly."""
    connection = _connect(db_path)
    try:
        actual_rows, reference_rows = _fetch_actual_and_reference(connection)
        overrides = _fetch_status_overrides(connection)
    finally:
        connection.close()

    actual_columns = ["UNIT_TYPE", "UNIT_NODE", "LOCATION", "LATITUDE", "LONGITUDE", *CATEGORIES]
    actual_frame = pd.DataFrame(
        [[unit_type, unit_node, location, lat, lon, *values] for unit_node, unit_type, location, lat, lon, *values in actual_rows],
        columns=actual_columns,
    )
    reference_frame = pd.DataFrame(reference_rows, columns=["UNIT_TYPE", *CATEGORIES])
    readiness_frame = pd.DataFrame(_build_readiness_rows(actual_rows, reference_rows, overrides), columns=READINESS_HEADER)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        actual_frame.to_excel(writer, sheet_name="Aktual", index=False)
        reference_frame.to_excel(writer, sheet_name="Referensi", index=False)
        readiness_frame.to_excel(writer, sheet_name="Kesiapan", index=False)
    return buffer.getvalue()
