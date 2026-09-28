import os
import random
import numpy as np
import pandas as pd
import geopandas as gpd

from datetime import datetime, timedelta
from shapely.geometry import Point

def generate_satria_mef_dataset(
    num_units=100,
    geojson_path="data/indonesia-38-provinces.geojson",
    output_dir="output_generated",
    seed=42
):
    random.seed(seed)
    np.random.seed(seed)

    if not os.path.exists(geojson_path):
        raise FileNotFoundError(f"GeoJSON tidak ditemukan: {geojson_path}")

    print("🗺️ Membaca batas provinsi Indonesia...")
    provinces = gpd.read_file(geojson_path).to_crs("EPSG:4326")
    provinces = provinces[provinces.geometry.notna() & ~provinces.geometry.is_empty].copy().reset_index(drop=True)

    CATEGORIES = ["Personnel", "Equipment", "Logistics", "Infrastructure", "Training"]
    UNIT_TYPES = ["Yonif", "Yonkav", "Yonarmed", "Yonzipur", "Denpal", "Bekangdam"]

    # Tabel 2: Matriks Acuan MEF Statis
    MEF_STANDARDS = {
        "Yonif": {"Personnel": 1000, "Equipment": 250, "Logistics": 3000, "Infrastructure": 40, "Training": 20},
        "Yonkav": {"Personnel": 500, "Equipment": 350, "Logistics": 4000, "Infrastructure": 50, "Training": 25},
        "Yonarmed": {"Personnel": 550, "Equipment": 300, "Logistics": 3500, "Infrastructure": 45, "Training": 25},
        "Yonzipur": {"Personnel": 650, "Equipment": 250, "Logistics": 3000, "Infrastructure": 60, "Training": 20},
        "Denpal": {"Personnel": 200, "Equipment": 100, "Logistics": 2000, "Infrastructure": 35, "Training": 15},
        "Bekangdam": {"Personnel": 400, "Equipment": 150, "Logistics": 8000, "Infrastructure": 60, "Training": 15}
    }

    df_mef = pd.DataFrame.from_dict(MEF_STANDARDS, orient='index').reset_index()
    df_mef.rename(columns={'index': 'UNIT_TYPE'}, inplace=True)

    base_time = datetime.strptime("2026-08-27 08:00:00", "%Y-%m-%d %H:%M:%S")
    
    def random_point_in_polygon(geometry):
        minx, miny, maxx, maxy = geometry.bounds
        while True:
            lon = np.random.uniform(minx, maxx)
            lat = np.random.uniform(miny, maxy)
            if geometry.contains(Point(lon, lat)):
                return lat, lon

    print(f"⚙️ Menghasilkan {num_units} unit data...")
    
    province_names = provinces["PROVINSI"].tolist()
    selected_provinces = np.random.choice(province_names, size=num_units, replace=True)
    geometry_map = dict(zip(provinces["PROVINSI"], provinces.geometry))

    data_actual, data_readiness = [], []
    record_counter = 10001

    for province_name in selected_provinces:
        geometry = geometry_map[province_name]
        lat, lon = random_point_in_polygon(geometry)
        
        unit_type = random.choice(UNIT_TYPES)
        unit_name = f"{unit_type} {random.randint(10, 999)}"
        mef_vals = MEF_STANDARDS[unit_type]
        
        actual_row = {
            "UNIT_TYPE": unit_type,
            "UNIT_NODE": unit_name, 
            "LOCATION": province_name, 
            "LATITUDE": round(lat, 6), 
            "LONGITUDE": round(lon, 6)
        }
        
        for category in CATEGORIES:
            mef_val = mef_vals[category]
            
            # Kalkulasi independen agar setiap kategori mendapat persentase unik
            readiness_pct = np.clip(np.random.normal(loc=85.0, scale=12.0), 40.0, 110.0) / 100.0
            actual_val = int(mef_val * readiness_pct)
            readiness_idx = round((actual_val / mef_val) * 100, 1)
            
            actual_row[category] = actual_val
            
            status = "FLAGGED" if (readiness_idx < 75.0 or np.random.random() < 0.05) else "VERIFIED"
            last_sync = base_time - timedelta(minutes=random.randint(0, 1440))

            data_readiness.append({
                "RECORD_ID": f"SDP-{record_counter}",
                "CATEGORY": category,
                "UNIT_NODE": unit_name,
                "LOCATION": province_name,
                "LATITUDE": round(lat, 6),
                "LONGITUDE": round(lon, 6),
                "READINESS_IDX": readiness_idx,
                "STATUS": status,
                "LAST_SYNC": last_sync.strftime("%Y-%m-%d %H:%M:%S")
            })
            record_counter += 1
            
        data_actual.append(actual_row)

    df_actual = pd.DataFrame(data_actual)
    df_readiness = pd.DataFrame(data_readiness)

    os.makedirs(output_dir, exist_ok=True)
    
    df_actual.to_csv(os.path.join(output_dir, "tabel1_actual.csv"), index=False)
    df_mef.to_csv(os.path.join(output_dir, "tabel2_mef_reference.csv"), index=False)
    df_readiness.to_csv(os.path.join(output_dir, "tabel3_readiness.csv"), index=False)

    print("=" * 60)
    print("✅ DATASET BERHASIL DIBUAT (3 TABEL - LOKASI & UNIT DIKEMBALIKAN)")
    print("=" * 60)

    return df_actual, df_mef, df_readiness

df_actual, df_mef, df_readiness = generate_satria_mef_dataset(num_units=500)