@echo off
chcp 65001 >nul
REM ============================================================
REM  generuj.bat - uruchomienie generatora DXF
REM
REM  Uzycie:
REM    generuj.bat                         (domyslne pliki + wynik.dxf)
REM    generuj.bat wspol.xlsx wt.xls out.dxf
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- wykryj Python ---
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

REM --- argumenty: domyslne nazwy plikow jesli brak ---
set "WSPOL=%~1"
set "WT=%~2"
set "OUT=%~3"
if "%WSPOL%"=="" set "WSPOL=współrzędne.xlsx"
if "%WT%"==""    set "WT=wt.xls"
if "%OUT%"==""   set "OUT=wynik.dxf"

echo.
echo === Generowanie DXF ===
echo   Wspolrzedne : %WSPOL%
echo   Warunki tech: %WT%
echo   Wyjscie     : %OUT%
echo.

if not exist "%WSPOL%" (
    echo [BLAD] Brak pliku wspolrzednych: %WSPOL%
    pause
    exit /b 1
)
if not exist "%WT%" (
    echo [BLAD] Brak pliku warunkow technicznych: %WT%
    pause
    exit /b 1
)

%PY% generuj.py "%WSPOL%" "%WT%" "%OUT%"

if errorlevel 1 (
    echo.
    echo [BLAD] Generowanie nie powiodlo sie.
    pause
    exit /b 1
)

echo.
echo === Gotowe. Plik: %OUT% ===
echo Mozesz sprawdzic wynik: sprawdz.bat "%OUT%"
pause
endlocal
