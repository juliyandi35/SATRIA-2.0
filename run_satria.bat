@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo SATRIA environment belum tersedia.
  echo Jalankan setup_satria.bat terlebih dahulu.
  exit /b 1
)

if not exist "static\dist\assets\satria.js" (
  echo Frontend SATRIA belum dibangun.
  echo Jalankan setup_satria.bat terlebih dahulu.
  exit /b 1
)

echo SATRIA 2.0 tersedia di http://127.0.0.1:5002
start "" "http://127.0.0.1:5002"
".venv\Scripts\python.exe" app.py
