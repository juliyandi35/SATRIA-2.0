@echo off
setlocal
cd /d "%~dp0"

if defined SATRIA_PYTHON (
  set "PYTHON_SOURCE=%SATRIA_PYTHON%"
) else (
  set "PYTHON_SOURCE=C:\Users\juliy\anaconda3\python.exe"
)

if not exist "%PYTHON_SOURCE%" (
  echo Python tidak ditemukan di "%PYTHON_SOURCE%".
  echo Atur SATRIA_PYTHON ke lokasi python.exe yang valid lalu jalankan ulang.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Membuat .venv dari "%PYTHON_SOURCE%"...
  "%PYTHON_SOURCE%" -m venv .venv
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

pushd frontend
call npm install
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
popd

echo SATRIA 2.0 siap. Jalankan run_satria.bat.
