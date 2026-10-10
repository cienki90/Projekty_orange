@echo off
chcp 65001 >nul
REM ============================================================
REM  sprawdz.bat - walidacja wygenerowanego pliku DXF
REM
REM  Uzycie:
REM    sprawdz.bat              (sprawdza wynik.dxf)
REM    sprawdz.bat plik.dxf
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- wykryj Python: najpierw launcher "py", potem "python" ---
set "PY="
py -3 --version >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3"
    goto :have_py
)
python --version >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    goto :have_py
)
echo [BLAD] Nie znaleziono Pythona. Najpierw uruchom setup.bat
pause
exit /b 1

:have_py
set "DXF=%~1"
if "%DXF%"=="" set "DXF=wynik.dxf"

if not exist "%DXF%" (
    echo [BLAD] Brak pliku DXF: %DXF%
    echo Najpierw uruchom generuj.bat
    pause
    exit /b 1
)

%PY% sprawdz.py "%DXF%"
pause
endlocal
