@echo off
rem ------------------------------------------------------------
rem  Probador de Audios (Windows)
rem  Lo abre el acceso directo "Probador de Audios" (menu Inicio / Escritorio).
rem  La primera vez instala todo lo necesario de forma automatica.
rem ------------------------------------------------------------
setlocal
chcp 65001 >nul
title Probador de Audios
cd /d "%~dp0"

echo.
echo   Probador de Audios
echo   ------------------
echo.

rem Todo lo que la app instala (motor, Python, librerias y modelo de voz) vive en
rem esta carpeta. Para desinstalar: Configuracion > Aplicaciones > Probador de Audios.
set "DATOS_APP=%LOCALAPPDATA%\ProbadorAudios"
if not exist "%DATOS_APP%" mkdir "%DATOS_APP%"
set "PROBADOR_DATOS=%DATOS_APP%"
set "UV_CACHE_DIR=%DATOS_APP%\uv-cache"
set "UV_PYTHON_INSTALL_DIR=%DATOS_APP%\python"
set "UV_PYTHON_BIN_DIR=%DATOS_APP%\python-bin"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_NO_CONFIG=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "UV=%DATOS_APP%\bin\uv.exe"

rem 1) Componente de Microsoft que necesita el motor de voz (Visual C++ 2015-2022, version 14.40 o mas nueva).
set "VCMINOR=0"
for /f "tokens=3" %%v in ('reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Minor 2^>nul ^| find "Minor"') do set /a VCMINOR=%%v
if %VCMINOR% LSS 40 for /f "tokens=3" %%v in ('reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" /v Minor 2^>nul ^| find "Minor"') do set /a VCMINOR=%%v
if %VCMINOR% GEQ 40 goto :vc_listo
echo   Instalando un componente de Microsoft que necesita la app.
echo   Si Windows pide permiso, acepta.
echo.
curl -L -s -f -o "%TEMP%\vc_redist.x64.exe" https://aka.ms/vs/17/release/vc_redist.x64.exe
if exist "%TEMP%\vc_redist.x64.exe" "%TEMP%\vc_redist.x64.exe" /install /passive /norestart
del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
:vc_listo

rem 2) Motor de instalacion (uv). Se instala una sola vez.
if exist "%UV%" goto :uv_listo
echo   Primera vez: instalando el motor de la app, 1 o 2 minutos...
echo.
if not exist "%DATOS_APP%\bin" mkdir "%DATOS_APP%\bin"
set "UV_ZIP=%TEMP%\probador-uv.zip"
curl -L -s -f -o "%UV_ZIP%" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
if exist "%UV_ZIP%" tar -xf "%UV_ZIP%" -C "%DATOS_APP%\bin"
del "%UV_ZIP%" >nul 2>&1
if exist "%UV%" goto :uv_listo
rem Alternativa: instalador oficial con PowerShell (sin modulos heredados de otra consola)
set "PSModulePath="
set "UV_UNMANAGED_INSTALL=%DATOS_APP%\bin"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "UV_UNMANAGED_INSTALL="
if exist "%UV%" goto :uv_listo
echo.
echo   No se pudo instalar. Revisa tu conexion a internet y vuelve a intentarlo.
echo.
if not "%PROBADOR_SIN_PAUSA%"=="1" pause
exit /b 1
:uv_listo

rem 3) Python y librerias: se descargan solo si faltan.
echo   Preparando la app...
echo   La primera vez descarga componentes; puede tardar varios minutos.
echo.
set "PY=3.12"
rem En PCs con procesador ARM se usa la version Intel/AMD (emulada), que es la compatible.
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PY=cpython-3.12-windows-x86_64-none"
"%UV%" run --python %PY% "%~dp0app\app.py"
if errorlevel 1 goto :error
endlocal
exit /b 0

:error
echo.
echo   La app se cerro. Si fue por un error y es la primera vez,
echo   revisa tu conexion a internet y vuelve a abrirla.
echo.
if not "%PROBADOR_SIN_PAUSA%"=="1" pause
endlocal
exit /b 1
