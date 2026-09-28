import pandas as pd
import numpy as np
import random

# 1. Konfigurasi Dasar Dataset
num_records = 500
categories = ['Personnel', 'Equipment', 'Logistics', 'Infrastructure', 'Training']
regions = ['West Java', 'East Java', 'Jakarta', 'Sumatra', 'Kalimantan', 'Papua', 'Sulawesi']
statuses = ['VERIFIED', 'FLAGGED']

data = []

# 2. Generate Data Bersih (Baseline)
for i in range(1, num_records + 1):
    record_id = f"ROW-{i:04d}"
    cat = random.choice(categories)
    unit = f"Unit {random.choice(['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'])} - {random.randint(1, 99)}"
    loc = random.choice(regions)
    lat = round(random.uniform(-10.0, 5.0), 4)
    lon = round(random.uniform(95.0, 140.0), 4)
    readiness = round(random.uniform(50.0, 100.0), 1)
    status = random.choice(statuses)
    
    data.append([record_id, cat, unit, loc, lat, lon, readiness, status])

df = pd.DataFrame(data, columns=['RECORD_ID', 'CATEGORY', 'UNIT_NODE', 'LOCATION', 'LAT', 'LON', 'READINESS_IDX', 'STATUS'])

# 3. Injeksi Kecacatan Data (Dirtying the Data)

# A. Missing Values (NA, NULL, -, atau kosong)
missing_formats = [np.nan, 'NA', 'NULL', '-', '']
for col in ['CATEGORY', 'UNIT_NODE', 'LOCATION', 'STATUS']:
    # Ambil 5% indeks acak untuk setiap kolom
    idx_to_mess = df.sample(frac=0.05).index
    df.loc[idx_to_mess, col] = [random.choice(missing_formats) for _ in range(len(idx_to_mess))]

# B. Outliers pada Readiness Index
df.loc[df.sample(frac=0.02).index, 'READINESS_IDX'] = 999.9  # Mustahil besar
df.loc[df.sample(frac=0.02).index, 'READINESS_IDX'] = -25.5  # Mustahil minus
df.loc[df.sample(frac=0.02).index, 'READINESS_IDX'] = np.nan # Kosong numerik

# C. Anomali Geospasial (Koordinat 0,0 atau tidak valid)
df.loc[df.sample(frac=0.03).index, ['LAT', 'LON']] = [0.0, 0.0]
df.loc[df.sample(frac=0.02).index, 'LAT'] = 999.99

# D. Inkonsistensi Kapitalisasi
df.loc[df.sample(frac=0.05).index, 'CATEGORY'] = df['CATEGORY'].astype(str).str.lower()
df.loc[df.sample(frac=0.05).index, 'LOCATION'] = df['LOCATION'].astype(str).str.upper()

# E. Injeksi Baris Duplikat
duplicates = df.sample(n=20, random_state=42)
df = pd.concat([df, duplicates], ignore_index=True)

# 4. Ekspor ke CSV
output_filename = 'satria_dirty_dataset.csv'
df.to_csv(output_filename, index=False)

print(f"Dataset kotor berhasil di-generate: {output_filename}")
print(f"Total baris: {len(df)}")