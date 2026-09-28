from __future__ import annotations

import csv
import hashlib
import io
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    """A dataset error that is safe to show in the interface."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("RECORD_ID", "ID", "RECORDID"),
    "category": ("CATEGORY", "KATEGORI"),
    "unit": ("UNIT_NODE", "UNIT", "UNIT_NAME"),
    "location": ("LOCATION", "PROVINCE", "PROVINSI", "REGION"),
    "lat": ("LAT", "LATITUDE", "Y"),
    "lon": ("LON", "LONGITUDE", "LNG", "X"),
    "readiness": ("READINESS_IDX", "READINESS", "READINESS_INDEX"),
    "status": ("STATUS",),
    "last_sync": ("LAST_SYNC", "UPDATED_AT", "TIMESTAMP"),
}

REQUIRED_FIELDS = tuple(SOURCE_ALIASES)
SORTABLE_FIELDS = {
    "id",
    "category",
    "unit",
    "location",
    "readiness",
    "status",
    "last_sync",
}

SATUAN_PREFIXES = ("Bekangdam", "Denpal", "Yonif", "Yonkav", "Yonarmed", "Yonzipur")


def _json_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else round(number, 4)


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _json_number(value)
    return value


def _is_no_filter(value: Any) -> bool:
    """True when a filter value means "no restriction" - absent, empty, "all", or an empty list."""
    if value in (None, "", "all", "ALL"):
        return True
    return isinstance(value, list) and not value


class DataRepository:
    """Thread-safe, authoritative in-memory state for one imported dataset."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self._lock = threading.RLock()
        self._frame: pd.DataFrame | None = None
        self._raw_records: list[dict[str, str]] = []
        self._metadata: dict[str, Any] | None = None
        self._quality: dict[str, Any] | None = None

    @property
    def loaded(self) -> bool:
        with self._lock:
            return self._frame is not None

    def reset(self) -> None:
        with self._lock:
            self._frame = None
            self._raw_records = []
            self._metadata = None
            self._quality = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._frame is None:
                return {
                    "loaded": False,
                    "message": "Belum ada dataset yang dimuat.",
                    "metadata": None,
                }
            return {
                "loaded": True,
                "message": "Dataset siap dianalisis.",
                "metadata": self._metadata,
                "quality": self._quality,
            }

    def import_builtin(self) -> dict[str, Any]:
        source_path = (self.project_root / "data" / "tabel3_readiness.csv").resolve()
        if not source_path.is_file() or self.project_root not in source_path.parents:
            raise DataValidationError("Dataset utama data/tabel3_readiness.csv tidak ditemukan.")
        return self.import_bytes(source_path.read_bytes(), source_path.name, "builtin")

    def import_bytes(self, payload: bytes, filename: str, source: str = "upload") -> dict[str, Any]:
        if not payload:
            raise DataValidationError("Dataset kosong dan tidak dapat diimpor.")
        if len(payload) > 25 * 1024 * 1024:
            raise DataValidationError("Ukuran dataset melebihi batas 25 MB.")
        if not filename.lower().endswith(".csv"):
            raise DataValidationError("Format belum didukung. Gunakan berkas CSV.")

        decoded: str | None = None
        encoding_used = ""
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                decoded = payload.decode(encoding)
                encoding_used = encoding
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise DataValidationError("Encoding CSV tidak dapat dibaca.")

        first_line = next((line for line in decoded.splitlines() if line.strip()), "")
        try:
            delimiter = csv.Sniffer().sniff(first_line, delimiters=",;\t|").delimiter
        except csv.Error:
            raise DataValidationError("Pemisah kolom CSV tidak dapat dikenali.") from None

        try:
            raw_frame = pd.read_csv(
                io.StringIO(decoded),
                sep=delimiter,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )
        except Exception as exc:
            raise DataValidationError("CSV rusak atau tidak dapat diparsing.") from exc

        raw_frame.columns = [str(column).strip() for column in raw_frame.columns]
        if raw_frame.empty:
            raise DataValidationError("Dataset tidak memiliki baris data.")
        if len(raw_frame.columns) < 2:
            raise DataValidationError("CSV hanya menghasilkan satu kolom. Periksa delimiter berkas.")

        column_lookup = {column.upper(): column for column in raw_frame.columns}
        source_map: dict[str, str] = {}
        missing: list[str] = []
        for normalized, aliases in SOURCE_ALIASES.items():
            matched = next((column_lookup[alias] for alias in aliases if alias in column_lookup), None)
            if matched:
                source_map[normalized] = matched
            else:
                missing.append(normalized)
        if missing:
            raise DataValidationError(
                "Dataset tidak memiliki kolom wajib yang diperlukan.",
                {"missing_fields": missing, "detected_columns": list(raw_frame.columns)},
            )

        normalized = pd.DataFrame(index=raw_frame.index)
        normalized["source_index"] = raw_frame.index + 2
        for target, source_column in source_map.items():
            normalized[target] = raw_frame[source_column].astype(str).str.strip()

        for column in ("lat", "lon", "readiness"):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized["last_sync"] = pd.to_datetime(normalized["last_sync"], errors="coerce")

        string_columns = ("id", "category", "unit", "location", "status")
        missing_by_field = {
            column: int(normalized[column].eq("").sum()) for column in string_columns
        }
        missing_by_field.update(
            {
                "lat": int(normalized["lat"].isna().sum()),
                "lon": int(normalized["lon"].isna().sum()),
                "readiness": int(normalized["readiness"].isna().sum()),
                "last_sync": int(normalized["last_sync"].isna().sum()),
            }
        )

        impossible_coordinates = (
            normalized["lat"].notna()
            & normalized["lon"].notna()
            & (
                ~normalized["lat"].between(-90, 90)
                | ~normalized["lon"].between(-180, 180)
            )
        )
        suspicious_readiness = normalized["readiness"].notna() & ~normalized["readiness"].between(0, 100)
        duplicate_ids = normalized["id"].ne("") & normalized["id"].duplicated(keep=False)

        quality = {
            "missing_by_field": missing_by_field,
            "missing_total": int(sum(missing_by_field.values())),
            "duplicate_rows": int(raw_frame.duplicated().sum()),
            "duplicate_ids": int(duplicate_ids.sum()),
            "invalid_coordinates": int(impossible_coordinates.sum()),
            "out_of_range_readiness": int(suspicious_readiness.sum()),
            "unparseable_timestamps": int(normalized["last_sync"].isna().sum()),
            "analysis_exclusions": {
                "readiness": int(normalized["readiness"].isna().sum()),
                "map": int((normalized["lat"].isna() | normalized["lon"].isna() | impossible_coordinates).sum()),
            },
        }

        metadata = {
            "filename": filename,
            "source": source,
            "rows": int(len(normalized)),
            "columns": int(len(raw_frame.columns)),
            "source_columns": list(raw_frame.columns),
            "schema_map": source_map,
            "encoding": encoding_used,
            "delimiter": "tab" if delimiter == "\t" else delimiter,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._frame = normalized
            self._raw_records = raw_frame.to_dict(orient="records")
            self._metadata = metadata
            self._quality = quality

        return {
            "status": "success",
            "message": f"{len(normalized):,} baris berhasil diimpor.",
            "metadata": metadata,
            "quality": quality,
            "pipeline": [
                "file_read",
                "schema_detected",
                "schema_normalized",
                "types_validated",
                "quality_checked",
                "state_updated",
            ],
        }

    def frame(self, filters: dict[str, Any] | None = None) -> pd.DataFrame:
        with self._lock:
            if self._frame is None:
                raise DataValidationError("Belum ada dataset yang dimuat.")
            frame = self._frame.copy()
        return self._apply_filters(frame, filters or {})

    def _apply_filters(self, frame: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
        selected_satuan = filters.get("satuan")
        if not _is_no_filter(selected_satuan):
            values = selected_satuan if isinstance(selected_satuan, list) else [selected_satuan]
            selected_prefixes = {str(value).strip().casefold() for value in values}
            unit_prefixes = frame["unit"].fillna("").astype(str).str.strip().str.split().str[0].str.casefold()
            frame = frame[unit_prefixes.isin(selected_prefixes)]

        for key in ("location", "unit", "category", "status"):
            selected = filters.get(key)
            if _is_no_filter(selected):
                continue
            values = selected if isinstance(selected, list) else [selected]
            frame = frame[frame[key].isin([str(value) for value in values])]

        lower = filters.get("readiness_min")
        upper = filters.get("readiness_max")
        if lower not in (None, ""):
            frame = frame[frame["readiness"] >= float(lower)]
        if upper not in (None, ""):
            frame = frame[frame["readiness"] <= float(upper)]

        risk = filters.get("risk")
        if risk == "good":
            frame = frame[frame["readiness"] >= 80]
        elif risk == "attention":
            frame = frame[(frame["readiness"] >= 60) & (frame["readiness"] < 80)]
        elif risk == "critical":
            frame = frame[frame["readiness"] < 60]
        return frame

    def filter_options(
        self, filters: dict[str, Any] | None = None, *, base: pd.DataFrame | None = None
    ) -> dict[str, list[str]]:
        frame = self.frame() if base is None else base
        filters = filters or {}
        contextual_filters = {key: value for key, value in filters.items() if key != "unit"}
        contextual_units = self._apply_filters(frame, contextual_filters)
        present_prefixes = {
            value.casefold()
            for value in frame["unit"].fillna("").astype(str).str.strip().str.split().str[0].tolist()
            if value
        }
        options = {
            key: sorted(value for value in frame[key].dropna().astype(str).unique().tolist() if value)
            for key in ("location", "unit", "category", "status")
        }
        options["satuan"] = [value for value in SATUAN_PREFIXES if value.casefold() in present_prefixes]
        options["unit"] = sorted(
            value for value in contextual_units["unit"].dropna().astype(str).unique().tolist() if value
        )
        return options

    def summary(
        self, filters: dict[str, Any] | None = None, *, frame: pd.DataFrame | None = None
    ) -> dict[str, Any]:
        frame = self.frame(filters) if frame is None else frame
        valid_readiness = frame["readiness"].dropna()
        if frame.empty:
            return {
                "record_count": 0,
                "unit_count": 0,
                "province_count": 0,
                "average_readiness": None,
                "median_readiness": None,
                "flagged_count": 0,
                "attention_count": 0,
                "minimum_readiness": None,
                "maximum_readiness": None,
                "latest_sync": None,
            }
        return {
            "record_count": int(len(frame)),
            "unit_count": int(frame["unit"].replace("", np.nan).nunique()),
            "province_count": int(frame["location"].replace("", np.nan).nunique()),
            "average_readiness": _json_number(valid_readiness.mean()) if not valid_readiness.empty else None,
            "median_readiness": _json_number(valid_readiness.median()) if not valid_readiness.empty else None,
            "flagged_count": int(frame["status"].eq("FLAGGED").sum()),
            "attention_count": int(((frame["readiness"] < 80) | frame["status"].eq("FLAGGED")).sum()),
            "minimum_readiness": _json_number(valid_readiness.min()) if not valid_readiness.empty else None,
            "maximum_readiness": _json_number(valid_readiness.max()) if not valid_readiness.empty else None,
            "latest_sync": _json_value(frame["last_sync"].max()),
        }

    def view(
        self,
        filters: dict[str, Any] | None = None,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str = "",
        sort_by: str = "readiness",
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        filters = filters or {}
        filtered = self.frame(filters)
        unfiltered_base = self.frame()
        frame = filtered
        if search.strip():
            query = search.strip().lower()
            mask = pd.Series(False, index=frame.index)
            for column in ("id", "unit", "location", "category", "status"):
                mask |= frame[column].astype(str).str.lower().str.contains(query, regex=False, na=False)
            frame = frame[mask]

        sort_by = sort_by if sort_by in SORTABLE_FIELDS else "readiness"
        frame = frame.sort_values(
            by=sort_by,
            ascending=sort_order.lower() != "desc",
            na_position="last",
            kind="stable",
        )
        page_size = max(10, min(int(page_size), 100))
        total_pages = max(1, math.ceil(len(frame) / page_size))
        page = max(1, min(int(page), total_pages))
        page_frame = frame.iloc[(page - 1) * page_size : page * page_size]

        distributions = self._distributions(filtered)
        rankings = self._rankings(filtered)
        return {
            "summary": self.summary(filters, frame=filtered),
            "distributions": distributions,
            "rankings": rankings,
            "map_points": self._map_points(filtered),
            "records": self._records(page_frame),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": int(len(frame)),
                "total_pages": total_pages,
            },
            "filter_options": self.filter_options(filters, base=unfiltered_base),
            "quality": self._quality,
            "active_filters": filters,
        }

    def _records(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        fields = ("id", "category", "unit", "location", "lat", "lon", "readiness", "status", "last_sync", "source_index")
        return [
            {field: _json_value(row[field]) for field in fields}
            for _, row in frame.iterrows()
        ]

    def _map_points(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        valid = frame[
            frame["lat"].between(-90, 90)
            & frame["lon"].between(-180, 180)
            & frame["lat"].notna()
            & frame["lon"].notna()
        ]
        if valid.empty:
            return []
        grouped = (
            valid.groupby(["unit", "location", "lat", "lon"], dropna=False)
            .agg(
                readiness=("readiness", "mean"),
                record_count=("id", "size"),
                flagged_count=("status", lambda values: int((values == "FLAGGED").sum())),
                categories=("category", lambda values: sorted(set(str(value) for value in values if value))),
            )
            .reset_index()
        )
        return [
            {
                "unit": row["unit"],
                "location": row["location"],
                "lat": _json_number(row["lat"]),
                "lon": _json_number(row["lon"]),
                "readiness": _json_number(row["readiness"]),
                "record_count": int(row["record_count"]),
                "flagged_count": int(row["flagged_count"]),
                "categories": row["categories"],
            }
            for _, row in grouped.iterrows()
        ]

    def _distributions(self, frame: pd.DataFrame) -> dict[str, Any]:
        def grouped(column: str) -> list[dict[str, Any]]:
            if frame.empty:
                return []
            result = (
                frame.groupby(column, dropna=False)
                .agg(count=("id", "size"), average_readiness=("readiness", "mean"))
                .reset_index()
                .sort_values("count", ascending=False)
            )
            return [
                {
                    "name": str(row[column]) if row[column] else "Tidak diketahui",
                    "count": int(row["count"]),
                    "average_readiness": _json_number(row["average_readiness"]),
                }
                for _, row in result.iterrows()
            ]

        readiness = frame["readiness"].dropna()
        bins = [-np.inf, 60, 75, 85, 95, np.inf]
        labels = ["< 60", "60–74.9", "75–84.9", "85–94.9", "≥ 95"]
        if readiness.empty:
            readiness_distribution: list[dict[str, Any]] = []
        else:
            bucketed = pd.cut(readiness, bins=bins, labels=labels, right=False)
            counts = bucketed.value_counts(sort=False)
            readiness_distribution = [
                {"name": label, "count": int(counts.get(label, 0))} for label in labels
            ]
        return {
            "category": grouped("category"),
            "status": grouped("status"),
            "province": grouped("location"),
            "readiness": readiness_distribution,
        }

    def _rankings(self, frame: pd.DataFrame) -> dict[str, Any]:
        if frame.empty:
            return {"lowest_units": [], "highest_units": [], "provinces": []}
        units = (
            frame.groupby(["unit", "location"], dropna=False)
            .agg(
                readiness=("readiness", "mean"),
                records=("id", "size"),
                flagged=("status", lambda values: int((values == "FLAGGED").sum())),
            )
            .reset_index()
        )
        provinces = (
            frame.groupby("location", dropna=False)
            .agg(readiness=("readiness", "mean"), records=("id", "size"))
            .reset_index()
            .sort_values("readiness")
        )

        def unit_rows(source: pd.DataFrame) -> list[dict[str, Any]]:
            return [
                {
                    "unit": row["unit"],
                    "location": row["location"],
                    "readiness": _json_number(row["readiness"]),
                    "records": int(row["records"]),
                    "flagged": int(row["flagged"]),
                }
                for _, row in source.iterrows()
            ]

        return {
            "lowest_units": unit_rows(units.sort_values("readiness").head(12)),
            "highest_units": unit_rows(units.sort_values("readiness", ascending=False).head(12)),
            "provinces": [
                {
                    "location": row["location"],
                    "readiness": _json_number(row["readiness"]),
                    "records": int(row["records"]),
                }
                for _, row in provinces.iterrows()
            ],
        }

    def ai_context(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.loaded:
            return {"dataset_loaded": False}
        frame = self.frame(filters)
        summary = self.summary(filters)
        rankings = self._rankings(frame)
        return {
            "dataset_loaded": True,
            "dataset": self._metadata,
            "filters": filters or {},
            "summary": summary,
            "lowest_readiness_units": rankings["lowest_units"][:5],
            "quality": self._quality,
        }

    def raw_record(self, source_index: int) -> dict[str, str] | None:
        with self._lock:
            offset = source_index - 2
            if offset < 0 or offset >= len(self._raw_records):
                return None
            return dict(self._raw_records[offset])
