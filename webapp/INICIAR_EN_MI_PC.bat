@echo off
title Gestion de Riesgo - ISO Calidad Antisoborno (OLG)
cd /d "%~dp0"
echo ================================================================
echo   Gestion de Riesgo - ISO Calidad Antisoborno (OLG)
echo   Arrancando en esta PC (sin nube, sin costo)
echo ================================================================
echo.

REM ---- 1. Python ----
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python en esta PC.
  echo         Instalalo desde https://www.python.org/downloads/
  echo         IMPORTANTE: marcar "Add python.exe to PATH" al instalar.
  echo.
  pause & exit /b 1
)

REM ---- 2. Entorno e instalacion (solo la primera vez tarda) ----
if not exist ".venv" (
  echo Preparando el entorno por primera vez. Esto tarda unos minutos...
  python -m venv .venv || (echo [ERROR] No se pudo crear el entorno. & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
echo Instalando/actualizando componentes...
python -m pip install --quiet -r requirements-local.txt || (echo [ERROR] Fallo la instalacion. & pause & exit /b 1)

REM ---- 3. Tesseract (el lector de PDF escaneados) ----
set "TESS=C:\Program Files\Tesseract-OCR\tesseract.exe"
if not exist "%TESS%" set "TESS=C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
if not exist "%TESS%" set "TESS=%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"
if exist "%TESS%" (
  set "TESSERACT_CMD=%TESS%"
) else (
  where tesseract >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [FALTA] No esta instalado Tesseract, que es el que lee los PDF escaneados.
    echo         Descargalo de: https://github.com/UB-Mannheim/tesseract/wiki
    echo         Al instalarlo, en "Additional language data" MARCA "Spanish".
    echo         Luego vuelve a ejecutar este archivo.
    echo.
    pause & exit /b 1
  )
)

REM ---- 4. Configuracion ----
if not exist "clave_maestra.txt" (
  echo.
  echo Primera vez: escribe la CONTRASENA MAESTRA de administrador.
  echo (minimo 12 caracteres; la vas a necesitar cada vez que entres)
  set /p MAESTRA=Contrasena maestra:
  echo %MAESTRA%> clave_maestra.txt
  echo Guardada en clave_maestra.txt (no compartas ese archivo).
)
set /p ADMIN_MASTER_CODE=<clave_maestra.txt
if not exist "clave_sesion.txt" (
  python -c "import secrets;open('clave_sesion.txt','w').write(secrets.token_hex(32))"
)
set /p SECRET_KEY=<clave_sesion.txt
set OCR_PROVIDER=local
set DATA_DIR=%~dp0data
set PORT=8080

echo.
echo ================================================================
echo   LISTO. Abre en el navegador:   http://localhost:8080
echo   Para apagar la aplicacion: cierra esta ventana.
echo ================================================================
echo.
start "" http://localhost:8080
python app.py
pause
