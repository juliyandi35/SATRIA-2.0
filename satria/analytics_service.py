from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull
from scipy.stats import kurtosis, skew
from sklearn.cluster import DBSCAN
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

_LOGGER = logging.getLogger("satria.audit")


def _number(value: Any, digits: int = 4) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return round(number, digits) if math.isfinite(number) else None


def data_diagnostics(frame: pd.DataFrame, source_quality: dict[str, Any] | None = None) -> dict[str, Any]:
    total_rows = len(frame)
    if total_rows == 0:
        raise ValueError("Dataset aktif tidak memiliki baris untuk didiagnosis.")

    data_columns = [column for column in frame.columns if column != "source_index"]
    missing_counts: dict[str, int] = {}
    for column in data_columns:
        series = frame[column]
        missing_counts[column] = int(series.isna().sum() + (series.eq("").sum() if series.dtype == "object" else 0))
    missing_pct = {column: round(count / total_rows * 100, 3) for column, count in missing_counts.items()}

    duplicate_mask = frame.duplicated(subset=data_columns, keep=False)
    duplicate_pct = round(int(frame.duplicated(subset=data_columns).sum()) / total_rows * 100, 3)

    readiness = frame["readiness"].dropna()
    numeric: dict[str, Any] = {}
    outlier_mask = pd.Series(False, index=frame.index)
    if not readiness.empty:
        q1, q3 = readiness.quantile([0.25, 0.75])
        iqr = q3 - q1
        outlier_mask = frame["readiness"].notna() & (
            (frame["readiness"] < q1 - 1.5 * iqr) | (frame["readiness"] > q3 + 1.5 * iqr)
        )
        numeric = {
            "mean": _number(readiness.mean()),
            "median": _number(readiness.median()),
            "std_dev": _number(readiness.std()),
            "variance": _number(readiness.var()),
            "skewness": _number(skew(readiness), 5) if len(readiness) > 2 else None,
            "kurtosis": _number(kurtosis(readiness), 5) if len(readiness) > 3 else None,
            "cardinality": int(readiness.nunique()),
            "q1": _number(q1),
            "q3": _number(q3),
            "potential_outliers": int(outlier_mask.sum()),
            "out_of_expected_range": int((~readiness.between(0, 100)).sum()),
        }

    categorical: dict[str, Any] = {}
    for column in ("category", "location", "status", "unit"):
        values = frame[column].dropna().astype(str)
        values = values[values.ne("")]
        counts = values.value_counts()
        lower_unique = values.str.casefold().nunique()
        categorical[column] = {
            "unique_categories": int(values.nunique()),
            "rare_categories": counts[counts < max(2, total_rows * 0.01)].index.tolist()[:25],
            "case_inconsistency": int(values.nunique() - lower_unique),
        }

    lat, lon = frame["lat"], frame["lon"]
    impossible = lat.notna() & lon.notna() & (~lat.between(-90, 90) | ~lon.between(-180, 180))
    geo = {
        "lat_range": [_number(lat.min()), _number(lat.max())],
        "lon_range": [_number(lon.min()), _number(lon.max())],
        "zero_coordinates": int(((lat == 0) & (lon == 0)).sum()),
        "impossible_locations": int(impossible.sum()),
        "duplicate_coords": int(frame.duplicated(subset=["lat", "lon"]).sum()),
        "missing_coordinates": int((lat.isna() | lon.isna()).sum()),
    }

    missing_rows = frame[list(missing_counts)].isna().any(axis=1)
    for column in ("id", "category", "unit", "location", "status"):
        missing_rows |= frame[column].eq("")

    quality_issue_count = (
        sum(missing_counts.values())
        + int(frame.duplicated(subset=data_columns).sum())
        + int(impossible.sum())
        + int((~readiness.between(0, 100)).sum())
    )
    denominator = max(1, total_rows * len(data_columns))
    quality_score = round(max(0.0, 100.0 * (1.0 - quality_issue_count / denominator)), 2)

    def ids(mask: pd.Series) -> list[str]:
        return frame.loc[mask, "id"].astype(str).tolist()

    return {
        "schema": {column: str(frame[column].dtype) for column in data_columns},
        "quality": {
            "score": quality_score,
            "score_method": "100 × (1 − counted quality issues ÷ all normalized cells)",
            "missing_pct": missing_pct,
            "missing_counts": missing_counts,
            "duplicate_pct": duplicate_pct,
            "source_validation": source_quality or {},
        },
        "numeric": numeric,
        "categorical": categorical,
        "geospatial": geo,
        "details_ids": {
            "duplicates": ids(duplicate_mask),
            "missing": ids(missing_rows),
            "outliers": ids(outlier_mask),
            "invalid_coordinates": ids(impossible),
            "out_of_range": ids(frame["readiness"].notna() & ~frame["readiness"].between(0, 100)),
        },
        "row_count": total_rows,
        "column_count": len(data_columns),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def spatial_clusters(
    frame: pd.DataFrame,
    *,
    epsilon_km: float = 150.0,
    min_samples: int = 3,
) -> dict[str, Any]:
    if epsilon_km <= 0 or epsilon_km > 2000:
        raise ValueError("Radius klaster harus berada antara 0 dan 2.000 km.")
    if min_samples < 2 or min_samples > 100:
        raise ValueError("Minimum sampel klaster harus berada antara 2 dan 100.")

    risk = frame[
        ((frame["readiness"] < 80) | frame["status"].eq("FLAGGED"))
        & frame["lat"].between(-90, 90)
        & frame["lon"].between(-180, 180)
        & frame["lat"].notna()
        & frame["lon"].notna()
    ].copy()
    if len(risk) < min_samples:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": "Haversine DBSCAN",
            "parameters": {"epsilon_km": epsilon_km, "min_samples": min_samples},
            "risk_point_count": int(len(risk)),
            "noise_count": int(len(risk)),
            "clusters": [],
        }

    coords = risk[["lat", "lon"]].to_numpy(dtype=float)
    labels = DBSCAN(
        eps=epsilon_km / 6371.0088,
        min_samples=min_samples,
        metric="haversine",
    ).fit_predict(np.radians(coords))
    risk["cluster"] = labels

    clusters: list[dict[str, Any]] = []
    for label in sorted(set(labels)):
        if label == -1:
            continue
        members = risk[risk["cluster"] == label]
        member_coords = members[["lat", "lon"]].to_numpy(dtype=float)
        unique_coords = np.unique(member_coords, axis=0)
        polygon = unique_coords.tolist()
        if len(unique_coords) >= 3:
            try:
                hull = ConvexHull(unique_coords[:, [1, 0]], qhull_options="QJ")
                polygon = unique_coords[hull.vertices].tolist()
            except Exception:
                _LOGGER.warning(
                    "ConvexHull failed for cluster label=%s (%d points) - falling back to unordered polygon",
                    label,
                    len(unique_coords),
                )
                polygon = unique_coords.tolist()

        mean_readiness = members["readiness"].dropna().mean()
        average_readiness = float(mean_readiness) if pd.notna(mean_readiness) else None
        flagged_ratio = float(members["status"].eq("FLAGGED").mean())
        if (average_readiness is not None and average_readiness < 60) or flagged_ratio >= 0.6:
            severity = "CRITICAL"
        elif (average_readiness is not None and average_readiness < 75) or flagged_ratio >= 0.3:
            severity = "HIGH"
        else:
            severity = "WATCH"

        clusters.append(
            {
                "cluster_id": f"C-{int(label) + 1:02d}",
                "type": "Vulnerability Zone",
                "severity": severity,
                "coordinates": [[round(float(lat), 6), round(float(lon), 6)] for lat, lon in polygon],
                "centroid": {
                    "lat": round(float(members["lat"].mean()), 6),
                    "lon": round(float(members["lon"].mean()), 6),
                },
                "member_count": int(len(members)),
                "unit_count": int(members["unit"].nunique()),
                "average_readiness": round(average_readiness, 2) if average_readiness is not None else None,
                "flagged_count": int(members["status"].eq("FLAGGED").sum()),
                "locations": sorted(members["location"].dropna().astype(str).unique().tolist()),
                "members": [
                    {
                        "id": str(row["id"]),
                        "unit": str(row["unit"]),
                        "location": str(row["location"]),
                        "readiness": _number(row["readiness"], 2),
                        "status": str(row["status"]),
                        "lat": _number(row["lat"], 6),
                        "lon": _number(row["lon"], 6),
                    }
                    for _, row in members.sort_values("readiness").head(30).iterrows()
                ],
            }
        )

    clusters.sort(
        key=lambda cluster: (
            cluster["average_readiness"] is None,
            cluster["average_readiness"] or 0.0,
            -cluster["member_count"],
        )
    )
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "Haversine DBSCAN",
        "parameters": {"epsilon_km": epsilon_km, "min_samples": min_samples},
        "risk_point_count": int(len(risk)),
        "noise_count": int((labels == -1).sum()),
        "clusters": clusters,
    }


def hidden_risk(frame: pd.DataFrame, limit: int = 15) -> dict[str, Any]:
    required = ["readiness", "category", "location", "unit"]
    usable = frame.dropna(subset=required).copy()
    for column in ("category", "location", "unit"):
        usable = usable[usable[column].astype(str).ne("")]
    if len(usable) < 20:
        raise ValueError("Minimal 20 observasi valid diperlukan untuk analisis risiko tersembunyi.")

    transformer = ColumnTransformer(
        transformers=[
            ("readiness", StandardScaler(), ["readiness"]),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["category", "location"]),
        ],
        remainder="drop",
    )
    detector = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    pipeline = Pipeline([("features", transformer), ("detector", detector)])
    pipeline.fit(usable)
    raw_scores = -pipeline.decision_function(usable)
    minimum, maximum = float(raw_scores.min()), float(raw_scores.max())
    if math.isclose(minimum, maximum):
        normalized = np.zeros_like(raw_scores)
    else:
        normalized = (raw_scores - minimum) / (maximum - minimum) * 100
    usable["hidden_risk"] = normalized
    usable["is_anomaly"] = pipeline.predict(usable) == -1

    anomaly_scores = usable.loc[usable["is_anomaly"], "hidden_risk"]
    normal_scores = usable.loc[~usable["is_anomaly"], "hidden_risk"]
    if anomaly_scores.empty or normal_scores.empty or math.isclose(maximum, minimum):
        confidence = 0.0
    else:
        separation = float(anomaly_scores.median() - normal_scores.median())
        confidence = max(0.0, min(100.0, separation))

    top = usable.sort_values(["hidden_risk", "readiness"], ascending=[False, True]).head(max(1, min(limit, 100)))
    top_risks = [
        {
            "id": str(row["id"]),
            "unit": str(row["unit"]),
            "location": str(row["location"]),
            "category": str(row["category"]),
            "hidden_risk": _number(row["hidden_risk"], 2),
            "readiness": _number(row["readiness"], 2),
            "status": str(row["status"]),
            "is_anomaly": bool(row["is_anomaly"]),
            "lat": _number(row["lat"], 6),
            "lon": _number(row["lon"], 6),
        }
        for _, row in top.iterrows()
    ]
    transformed_feature_count = int(transformer.transform(usable.head(1)).shape[1])
    return {
        "labels": [item["unit"] for item in top_risks],
        "hidden_risk": [item["hidden_risk"] for item in top_risks],
        "readiness": [item["readiness"] for item in top_risks],
        "top_risks": top_risks,
        "confidence": round(confidence, 1),
        "confidence_method": "Median anomaly-to-normal score separation",
        "peak_risk": max((item["hidden_risk"] or 0 for item in top_risks), default=0),
        "anomaly_count": int(usable["is_anomaly"].sum()),
        "excluded_count": int(len(frame) - len(usable)),
        "features_analyzed": ["readiness", "category", "location"],
        "encoded_feature_count": transformed_feature_count,
        "method": "Isolation Forest",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
