# SATRIA 2.0

Strategic Artificial Intelligence for Readiness, Intelligence & Analytics. SATRIA 2.0 adalah lingkungan komando 3D lokal yang menghubungkan data kesiapan nyata, analitik geospasial, deteksi anomali, diagnostik data, dan model Ollama.

## Arsitektur

- React + TypeScript + React Three Fiber untuk antarmuka dan lingkungan 3D.
- Flask sebagai API analitik otoritatif dan host build frontend.
- Pandas, scikit-learn, dan SciPy untuk normalisasi, Isolation Forest, Haversine DBSCAN, convex hull, serta diagnostik.
- Ollama untuk SATRIA AI. Riwayat sesi disimpan di `checkpoints.db`.
- `data/tabel3_readiness.csv` adalah sumber utama, tetapi tidak dimuat otomatis.

## Runtime Python

Proyek ini memakai **Python 3.12.13 (conda-forge)** dari Anaconda:

```text
C:\Users\juliy\anaconda3\python.exe
```

`setup_satria.bat` memakai interpreter tersebut untuk membuat `.venv`, sehingga dependency proyek tetap terisolasi. VS Code diarahkan ke `.venv\Scripts\python.exe`.

## Instalasi Windows

Prasyarat: instalasi Anaconda di atas, Node.js 20+, npm, dan Ollama.

1. Jalankan `setup_satria.bat`.
2. Pastikan model Ollama tersedia:

   ```powershell
   ollama list
   ```

   Model yang dikenali: `granite4.2:3b`, `ornith-1.5:9b`, `gemma4:12b`, dan `muse-glimmer` (alias `muse-glimmer:latest` didukung).

3. Jalankan `run_satria.bat` atau:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

4. Buka `http://127.0.0.1:5002` dan pilih **Impor tabel3_readiness.csv**.

Untuk memakai lokasi Python lain sementara, berikan override sebelum setup:

```powershell
$env:SATRIA_PYTHON = 'C:\path\to\python.exe'
.\setup_satria.bat
```

## Pengembangan frontend

```powershell
cd frontend
npm install
npm run typecheck
npm run build
```

Flask menyajikan hasil build dari `static/dist`. Aplikasi inti tidak membutuhkan CDN.

## Konfigurasi opsional

- Email: `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_HOST`, `SMTP_PORT`.
- MySQL: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
- Ollama alternatif: `OLLAMA_BASE_URL`.

Tanpa konfigurasi tersebut, panel sistem menampilkan status sebenarnya sebagai belum dikonfigurasi. Kredensial tidak boleh ditulis ke source code.

## Preset grafis

AUTO, LOW, MEDIUM, HIGH, dan ULTRA tersedia di Kendali Sistem. AUTO mengukur FPS nyata, menyesuaikan DPR serta kompleksitas, dan memakai hysteresis/cooldown agar kualitas tidak berosilasi.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Pengujian mencakup empty state, impor schema `LAT`/`LON`, cross-filter, nilai di luar 0–100, DBSCAN, Isolation Forest, dan perimeter alat AI.

## Pemecahan masalah

- **Model tidak tersedia:** jalankan `ollama list`, lalu tarik model yang hilang dengan `ollama pull <model>`.
- **Halaman tanpa 3D:** perbarui driver GPU dan aktifkan WebGL; analitik tetap tersedia dalam fallback mode.
- **Dataset ditolak:** periksa kolom wajib, delimiter, encoding, dan batas unggahan 25 MB. Detail kolom yang hilang ditampilkan oleh API.
- **Email belum dikonfigurasi:** isi environment variable SMTP; SATRIA tidak memakai kredensial bawaan.
