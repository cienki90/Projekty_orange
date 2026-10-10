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

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [BLAD] Nie znaleziono Pythona. Najpierw uruchom setup.bat
    pause
    exit /b 1
)

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
