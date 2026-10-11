@echo off
chcp 65001 >nul
REM ============================================================
REM  plan.bat - generuje PLAN ORIENTACYJNY (mapa poglądowa) + DXF
REM
REM  Plan orientacyjny: A3, skala 1:10 000 lub 1:25 000, KOLOROWY
REM  podkład OSM, trasa jako czerwona linia, uklad jak przebieg trasy.
REM  Rownowazne: generuj.bat --orientacja ...
REM
REM  Uzycie:
REM    plan.bat                       (auto-wykrycie + plan)
REM    plan.bat wspol.xlsx wt.xls out.dxf
REM ============================================================
setlocal
cd /d "%~dp0"

set "PY="
py -3 --version >nul 2>nul
if %errorlevel%==0 ( set "PY=py -3" & goto :have_py )
python --version >nul 2>nul
if %errorlevel%==0 ( set "PY=python" & goto :have_py )
echo [BLAD] Nie znaleziono Pythona. Najpierw uruchom setup.bat
pause
exit /b 1

:have_py
echo Uzywam interpretera: %PY%
echo Generuje DXF + plan orientacyjny (kolorowy OSM)...
if "%~1"=="" (
    %PY% generuj.py --auto --orientacja
) else (
    %PY% generuj.py --orientacja %*
)

if errorlevel 1 (
    echo.
    echo [INFO] Zakonczono (blad lub anulowano).
    pause
    exit /b 1
)
echo.
echo === Gotowe. Plan: *_orientacja.dxf (+ *_orientacja_podklad.jpg) ===
pause
endlocal
