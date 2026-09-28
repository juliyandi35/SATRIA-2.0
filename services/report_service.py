"""SATRIA's full intelligence report: descriptive readiness analysis, data quality
inspection, spatial cluster analysis, and hidden-risk (Isolation Forest) findings - every
section backed by both a table and a chart, built with the shared pdf_kit toolkit."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from satria.analytics_service import data_diagnostics, hidden_risk, spatial_clusters
from services.pdf_kit import (
    INK,
    MUTED,
    OKSIDA,
    PERUNGGU,
    SELAT,
    _fmt,
    _hbar_chart,
    _kv_table,
    _note,
    _section_title,
    _severity_color,
    _subheading,
    _table,
    _text,
    _vbar_chart,
)

if TYPE_CHECKING:
    from fpdf import FPDF

    from satria.data_service import DataRepository


def _readiness_summary_section(pdf: "FPDF", view_data: dict[str, Any], metadata: dict[str, Any] | None) -> None:
    summary = view_data["summary"]
    _section_title(pdf, "1. Ringkasan dan Analisis Deskriptif Kesiapan")
    if metadata:
        _note(pdf, f"Dataset aktif: {metadata.get('filename', '-')} ({metadata.get('rows', '-')} baris sumber).")
    _kv_table(
        pdf,
        [
            ("Rekaman aktif", summary["record_count"]),
            ("Unit", summary["unit_count"]),
            ("Provinsi", summary["province_count"]),
            ("Rata-rata kesiapan", _fmt(summary["average_readiness"], 2)),
            ("Median kesiapan", _fmt(summary["median_readiness"], 2)),
            ("Kesiapan minimum", _fmt(summary["minimum_readiness"], 2)),
            ("Kesiapan maksimum", _fmt(summary["maximum_readiness"], 2)),
            ("Observasi ditandai (FLAGGED)", summary["flagged_count"]),
            ("Observasi memerlukan perhatian", summary["attention_count"]),
            ("Sinkronisasi terbaru", _text(summary["latest_sync"])),
        ],
    )

    distributions = view_data["distributions"]
    _subheading(pdf, "Distribusi indeks kesiapan")
    readiness_bins = distributions.get("readiness", [])
    _vbar_chart(pdf, [(row["name"], row["count"]) for row in readiness_bins], color=SELAT)
    _table(pdf, ["Rentang", "Jumlah observasi"], [[row["name"], row["count"]] for row in readiness_bins], [90, 90])

    _subheading(pdf, "Distribusi berdasarkan kategori")
    categories = distributions.get("category", [])
    _vbar_chart(pdf, [(row["name"], row["count"]) for row in categories[:10]], color=PERUNGGU)
    _table(
        pdf,
        ["Kategori", "Jumlah", "Rata-rata kesiapan"],
        [[row["name"], row["count"], _fmt(row["average_readiness"], 2)] for row in categories],
        [90, 45, 45],
    )

    _subheading(pdf, "Distribusi berdasarkan status")
    statuses = distributions.get("status", [])
    _vbar_chart(pdf, [(row["name"], row["count"]) for row in statuses[:10]], color=MUTED)
    _table(
        pdf,
        ["Status", "Jumlah", "Rata-rata kesiapan"],
        [[row["name"], row["count"], _fmt(row["average_readiness"], 2)] for row in statuses],
        [90, 45, 45],
    )

    rankings = view_data["rankings"]
    _subheading(pdf, "10 unit dengan kesiapan terendah")
    lowest = rankings.get("lowest_units", [])[:10]
    _table(
        pdf,
        ["Unit", "Lokasi", "Kesiapan", "Rekaman", "Ditandai"],
        [[row["unit"], row["location"], _fmt(row["readiness"], 1), row["records"], row["flagged"]] for row in lowest],
        [55, 55, 25, 25, 25],
    )

    _subheading(pdf, "10 unit dengan kesiapan tertinggi")
    highest = rankings.get("highest_units", [])[:10]
    _table(
        pdf,
        ["Unit", "Lokasi", "Kesiapan", "Rekaman", "Ditandai"],
        [[row["unit"], row["location"], _fmt(row["readiness"], 1), row["records"], row["flagged"]] for row in highest],
        [55, 55, 25, 25, 25],
    )

    _subheading(pdf, "Peringkat provinsi (kesiapan terendah ke tertinggi)")
    provinces = rankings.get("provinces", [])
    _hbar_chart(
        pdf,
        [(row["location"], row["readiness"] or 0, SELAT) for row in provinces[:15]],
        value_fmt=lambda value: _fmt(value, 1),
    )
    _table(
        pdf,
        ["Provinsi", "Kesiapan rata-rata", "Rekaman"],
        [[row["location"], _fmt(row["readiness"], 2), row["records"]] for row in provinces],
        [110, 45, 35],
    )


def _quality_section(pdf: "FPDF", diagnostics: dict[str, Any]) -> None:
    _section_title(pdf, "2. Inspeksi Kualitas Data")
    quality = diagnostics["quality"]
    _kv_table(
        pdf,
        [
            ("Skor kualitas", f"{_fmt(quality['score'], 2)} / 100"),
            ("Metode skor", quality["score_method"]),
            ("Baris duplikat", f"{_fmt(quality['duplicate_pct'], 3)}%"),
            ("Jumlah baris dianalisis", diagnostics["row_count"]),
            ("Jumlah kolom dianalisis", diagnostics["column_count"]),
            ("Dibuat", diagnostics["generated_at"]),
        ],
    )

    _subheading(pdf, "Nilai kosong per kolom")
    missing_pct = quality["missing_pct"]
    missing_counts = quality["missing_counts"]
    columns = sorted(missing_pct, key=lambda column: missing_pct[column], reverse=True)
    _hbar_chart(
        pdf,
        [(column, missing_pct[column], OKSIDA if missing_pct[column] > 5 else MUTED) for column in columns[:10]],
        value_fmt=lambda value: f"{_fmt(value, 2)}%",
    )
    _table(
        pdf,
        ["Kolom", "Nilai kosong", "Persentase"],
        [[column, missing_counts[column], f"{_fmt(missing_pct[column], 3)}%"] for column in columns],
        [90, 45, 45],
    )

    numeric = diagnostics.get("numeric") or {}
    if numeric:
        _subheading(pdf, "Statistik numerik - indeks kesiapan")
        _kv_table(
            pdf,
            [
                ("Rata-rata", _fmt(numeric.get("mean"), 3)),
                ("Median", _fmt(numeric.get("median"), 3)),
                ("Standar deviasi", _fmt(numeric.get("std_dev"), 3)),
                ("Varians", _fmt(numeric.get("variance"), 3)),
                ("Skewness", _fmt(numeric.get("skewness"), 4)),
                ("Kurtosis", _fmt(numeric.get("kurtosis"), 4)),
                ("Kardinalitas", numeric.get("cardinality")),
                ("Kuartil 1 / Kuartil 3", f"{_fmt(numeric.get('q1'), 2)} / {_fmt(numeric.get('q3'), 2)}"),
                ("Potensi outlier (IQR)", numeric.get("potential_outliers")),
                ("Di luar rentang wajar (0-100)", numeric.get("out_of_expected_range")),
            ],
        )

    categorical = diagnostics.get("categorical") or {}
    if categorical:
        _subheading(pdf, "Inspeksi kolom kategorikal")
        _table(
            pdf,
            ["Kolom", "Kategori unik", "Kategori jarang", "Inkonsistensi huruf"],
            [
                [
                    column,
                    stats["unique_categories"],
                    len(stats["rare_categories"]),
                    stats["case_inconsistency"],
                ]
                for column, stats in categorical.items()
            ],
            [55, 45, 45, 45],
        )

    geo = diagnostics.get("geospatial") or {}
    if geo:
        _subheading(pdf, "Inspeksi koordinat geospasial")
        _kv_table(
            pdf,
            [
                ("Rentang lintang", f"{_fmt(geo['lat_range'][0], 3)} s.d. {_fmt(geo['lat_range'][1], 3)}"),
                ("Rentang bujur", f"{_fmt(geo['lon_range'][0], 3)} s.d. {_fmt(geo['lon_range'][1], 3)}"),
                ("Koordinat nol (0,0)", geo["zero_coordinates"]),
                ("Lokasi tidak valid", geo["impossible_locations"]),
                ("Koordinat duplikat", geo["duplicate_coords"]),
                ("Koordinat kosong", geo["missing_coordinates"]),
            ],
        )


def _spatial_section(pdf: "FPDF", spatial: dict[str, Any]) -> None:
    _section_title(pdf, "3. Analisis Spasial - Klaster Risiko (DBSCAN)")
    _kv_table(
        pdf,
        [
            ("Metode", spatial["method"]),
            ("Radius klaster (epsilon)", f"{spatial['parameters']['epsilon_km']} km"),
            ("Minimum sampel per klaster", spatial["parameters"]["min_samples"]),
            ("Titik berisiko dianalisis", spatial["risk_point_count"]),
            ("Titik noise (di luar klaster)", spatial["noise_count"]),
            ("Jumlah klaster ditemukan", len(spatial["clusters"])),
        ],
    )

    clusters = spatial["clusters"]
    if not clusters:
        _note(pdf, "Tidak ada klaster risiko yang terbentuk dari parameter dan dataset aktif saat ini.")
        return

    _subheading(pdf, "Perbandingan kesiapan rata-rata antar klaster")
    _hbar_chart(
        pdf,
        [
            (f"{cluster['cluster_id']} ({cluster['severity']})", cluster["average_readiness"] or 0, _severity_color(cluster["severity"]))
            for cluster in clusters
        ],
        value_fmt=lambda value: _fmt(value, 1),
    )
    _table(
        pdf,
        ["Klaster", "Tingkat", "Anggota", "Unit", "Kesiapan rata-rata", "Ditandai"],
        [
            [
                cluster["cluster_id"],
                cluster["severity"],
                cluster["member_count"],
                cluster["unit_count"],
                _fmt(cluster["average_readiness"], 2),
                cluster["flagged_count"],
            ]
            for cluster in clusters
        ],
        [30, 28, 25, 25, 40, 25],
    )

    for cluster in clusters:
        _subheading(pdf, f"Karakteristik klaster {cluster['cluster_id']} - tingkat {cluster['severity']}")
        _kv_table(
            pdf,
            [
                ("Jumlah anggota", cluster["member_count"]),
                ("Jumlah unit unik", cluster["unit_count"]),
                ("Kesiapan rata-rata", _fmt(cluster["average_readiness"], 2)),
                ("Observasi ditandai", cluster["flagged_count"]),
                ("Titik pusat (centroid)", f"{cluster['centroid']['lat']}, {cluster['centroid']['lon']}"),
                ("Lokasi tercakup", ", ".join(cluster["locations"]) or "-"),
            ],
        )
        members = cluster["members"][:10]
        _table(
            pdf,
            ["Unit", "Lokasi", "Kesiapan", "Status"],
            [[member["unit"], member["location"], _fmt(member["readiness"], 1), member["status"]] for member in members],
            [60, 60, 30, 40],
        )
        if cluster["member_count"] > len(members):
            _note(pdf, f"Menampilkan {len(members)} dari {cluster['member_count']} anggota klaster ini.")


def _hidden_risk_section(pdf: "FPDF", frame) -> None:
    _section_title(pdf, "4. Analisis Risiko Tersembunyi (Isolation Forest)")
    try:
        risk = hidden_risk(frame, limit=15)
    except ValueError as error:
        _note(pdf, str(error))
        return

    _kv_table(
        pdf,
        [
            ("Metode", risk["method"]),
            ("Fitur dianalisis", ", ".join(risk["features_analyzed"])),
            ("Jumlah fitur ter-encode", risk["encoded_feature_count"]),
            ("Observasi dikecualikan (data tidak lengkap)", risk["excluded_count"]),
            ("Observasi dianggap anomali", risk["anomaly_count"]),
            ("Skor risiko puncak", _fmt(risk["peak_risk"], 2)),
            ("Tingkat keyakinan pemisahan", f"{_fmt(risk['confidence'], 1)} ({risk['confidence_method']})"),
        ],
    )

    _subheading(pdf, "Skor risiko tersembunyi - 15 unit teratas")
    _hbar_chart(
        pdf,
        [
            (item["unit"], item["hidden_risk"] or 0, OKSIDA if item["is_anomaly"] else PERUNGGU)
            for item in risk["top_risks"]
        ],
        value_fmt=lambda value: _fmt(value, 1),
    )
    _table(
        pdf,
        ["Unit", "Lokasi", "Kategori", "Skor risiko", "Kesiapan", "Status", "Anomali"],
        [
            [
                item["unit"],
                item["location"],
                item["category"],
                _fmt(item["hidden_risk"], 2),
                _fmt(item["readiness"], 1),
                item["status"],
                "Ya" if item["is_anomaly"] else "Tidak",
            ]
            for item in risk["top_risks"]
        ],
        [40, 35, 30, 25, 22, 20, 18],
    )


def build_full_report_pdf(repository: "DataRepository", filters: dict | None = None) -> bytes:
    """Compose a complete SATRIA intelligence report: descriptive readiness analysis, data
    quality inspection, spatial cluster analysis, and hidden-risk (Isolation Forest) findings -
    every section backed by both a table and a chart drawn from the active dataset."""
    from fpdf import FPDF

    filters = filters or {}
    frame = repository.frame(filters)
    view_data = repository.view(filters, page=1, page_size=1)
    metadata = repository.status().get("metadata")
    source_quality = repository.status().get("quality")
    diagnostics = data_diagnostics(frame, source_quality)
    spatial = spatial_clusters(frame)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*INK)
    pdf.cell(0, 11, "SATRIA 2.0 - Laporan Intelijen Kesiapan Lengkap", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, f"Dibuat: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(2)

    _readiness_summary_section(pdf, view_data, metadata)
    _quality_section(pdf, diagnostics)
    _spatial_section(pdf, spatial)
    _hidden_risk_section(pdf, frame)

    raw = pdf.output()
    return bytes(raw) if isinstance(raw, (bytes, bytearray)) else raw.encode("latin1")
