import os
import random
import numpy as np
import pandas as pd
import geopandas as gpd

from datetime import datetime, timedelta
from shapely.geometry import Point


def generate_satria_dataset(
    num_records=1000,
    geojson_path="data/indonesia-38-provinces.geojson",
    output_path=None,
    seed=42
):
    """
    Generate synthetic SATRIA defense readiness dataset.

    Parameters
    ----------
    num_records : int
        Jumlah record yang akan dibuat.

    geojson_path : str
        Path menuju GeoJSON batas provinsi Indonesia.

    output_path : str or None
        Lokasi file CSV output.
        Jika None, otomatis menggunakan nama berdasarkan jumlah record.

    seed : int
        Random seed agar hasil dapat direproduksi.

    Returns
    -------
    pandas.DataFrame
        Dataset SATRIA yang telah dibuat.
    """

    # ==========================================================
    # 1. RANDOM SEED
    # ==========================================================

    random.seed(seed)
    np.random.seed(seed)

    # ==========================================================
    # 2. VALIDASI INPUT
    # ==========================================================

    if num_records <= 0:
        raise ValueError(
            "num_records harus lebih besar dari 0."
        )

    if not os.path.exists(geojson_path):
        raise FileNotFoundError(
            f"GeoJSON tidak ditemukan:\n{geojson_path}"
        )

    # ==========================================================
    # 3. LOAD GEOJSON PROVINSI
    # ==========================================================

    print("🗺️ Membaca batas provinsi Indonesia...")

    provinces = gpd.read_file(
        geojson_path
    )

    # Pastikan WGS84
    provinces = provinces.to_crs(
        "EPSG:4326"
    )

    # ==========================================================
    # 4. VALIDASI KOLOM
    # ==========================================================

    if "PROVINSI" not in provinces.columns:

        raise ValueError(
            "Kolom 'PROVINSI' tidak ditemukan "
            "di dalam GeoJSON."
        )

    # Hapus geometry kosong
    provinces = provinces[
        provinces.geometry.notna()
        & ~provinces.geometry.is_empty
    ].copy()

    # Reset index
    provinces = provinces.reset_index(
        drop=True
    )

    print(
        f"✅ {len(provinces)} provinsi ditemukan."
    )

    # ==========================================================
    # 5. KONFIGURASI SATRIA
    # ==========================================================

    CATEGORIES = [
        "Personnel",
        "Equipment",
        "Logistics",
        "Infrastructure",
        "Training"
    ]

    UNIT_TYPES = [
        "Yonif",
        "Yonkav",
        "Yonarmed",
        "Yonzipur",
        "Denpal",
        "Bekangdam"
    ]

    # ==========================================================
    # 6. BASE TIME
    # ==========================================================

    base_time = datetime.strptime(
        "2026-08-27 08:00:00",
        "%Y-%m-%d %H:%M:%S"
    )

    # ==========================================================
    # 7. FUNGSI RANDOM POINT DALAM POLYGON
    # ==========================================================

    def random_point_in_polygon(geometry):

        minx, miny, maxx, maxy = geometry.bounds

        while True:

            lon = np.random.uniform(
                minx,
                maxx
            )

            lat = np.random.uniform(
                miny,
                maxy
            )

            point = Point(
                lon,
                lat
            )

            if geometry.contains(point):
                return lat, lon

    # ==========================================================
    # 8. GENERATE DATA
    # ==========================================================

    print(
        f"⚙️ Menghasilkan {num_records:,} record..."
    )

    data = []

    province_names = provinces[
        "PROVINSI"
    ].tolist()

    # ----------------------------------------------------------
    # Sampling provinsi
    # ----------------------------------------------------------

    selected_provinces = np.random.choice(
        province_names,
        size=num_records,
        replace=True
    )

    # ----------------------------------------------------------
    # Cache geometry agar tidak lookup terus
    # ----------------------------------------------------------

    geometry_map = dict(
        zip(
            provinces["PROVINSI"],
            provinces.geometry
        )
    )

    # ==========================================================
    # 9. GENERATE RECORD
    # ==========================================================
    
    record_counter = 10001

    for i, province_name in enumerate(selected_provinces):
        geometry = geometry_map[province_name]
        
        # Tentukan koordinat dan nama unit SATU KALI untuk iterasi ini
        lat, lon = random_point_in_polygon(geometry)
        unit_name = f"{random.choice(UNIT_TYPES)} {random.randint(10, 999)}"
        
        # Loop semua kategori agar unit ini memiliki nilai di setiap aspek
        for category in CATEGORIES:
            
            # Buat nilai readiness yang sedikit bervariasi antar kategori
            readiness = np.random.normal(loc=85.0, scale=8.0)
            readiness = round(float(np.clip(readiness, 40.0, 100.0)), 1)
            
            status = "FLAGGED" if (readiness < 75.0 or np.random.random() < 0.05) else "VERIFIED"
            last_sync = base_time - timedelta(minutes=random.randint(0, 1440))

            data.append({
                "RECORD_ID": f"SDP-{record_counter}",
                "CATEGORY": category,
                "UNIT_NODE": unit_name,
                "LOCATION": province_name,
                "LATITUDE": round(lat, 6),
                "LONGITUDE": round(lon, 6),
                "READINESS_IDX": readiness,
                "STATUS": status,
                "LAST_SYNC": last_sync.strftime("%Y-%m-%d %H:%M:%S")
            })
            record_counter += 1

    # ==========================================================
    # 10. DATAFRAME
    # ==========================================================

    df = pd.DataFrame(data)

    # ==========================================================
    # 11. OUTPUT PATH
    # ==========================================================

    if output_path is None:

        if num_records >= 1_000_000:

            filename = (
                f"satria_dataset_"
                f"{num_records // 1_000_000}m.csv"
            )

        elif num_records >= 1_000:

            filename = (
                f"satria_dataset_"
                f"{num_records // 1_000}k.csv"
            )

        else:

            filename = (
                f"satria_dataset_"
                f"{num_records}.csv"
            )

        output_path = os.path.join(
            "output_generated",
            filename
        )

    # ==========================================================
    # 12. BUAT FOLDER OUTPUT
    # ==========================================================

    output_dir = os.path.dirname(
        output_path
    )

    if output_dir:
        os.makedirs(
            output_dir,
            exist_ok=True
        )

    # ==========================================================
    # 13. SIMPAN CSV
    # ==========================================================

    df.to_csv(
        output_path,
        index=False
    )

    # ==========================================================
    # 14. INFORMASI HASIL
    # ==========================================================

    print()
    print("=" * 60)
    print("✅ SATRIA DATASET BERHASIL DIBUAT")
    print("=" * 60)

    print(
        f"📊 Jumlah record : {len(df):,}"
    )

    print(
        f"🗺️ Provinsi      : "
        f"{df['LOCATION'].nunique()}"
    )

    print(
        f"📁 Output        : {output_path}"
    )

    print(
        f"🚩 Flagged       : "
        f"{(df['STATUS'] == 'FLAGGED').sum():,}"
    )

    print(
        f"✔ Verified       : "
        f"{(df['STATUS'] == 'VERIFIED').sum():,}"
    )

    print("=" * 60)

    return df

df = generate_satria_dataset(
    num_records=100
)