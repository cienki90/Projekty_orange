@echo off
chcp 65001 >nul
REM ============================================================
REM  generuj.bat - uruchomienie generatora DXF
REM
REM  Uzycie:
REM    generuj.bat                     (OKNO WYBORU plikow)
REM    generuj.bat --auto              (auto-wykrycie, bez okna)
REM    generuj.bat wspol.xlsx wt.xls out.dxf
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
echo        (zainstaluj Python 3.10+ i zaznacz "Add Python to PATH")
pause
exit /b 1

:have_py
echo Uzywam interpretera: %PY%
echo.
echo === Generator DXF ===
echo Otwieram okno wyboru plikow (lub uzywam podanych argumentow)...
echo.

REM przekazanie wszystkich argumentow do generatora
%PY% generuj.py %*

if errorlevel 1 (
    echo.
    echo [INFO] Zakonczono (blad lub anulowano).
    pause
    exit /b 1
)

echo.
echo === Gotowe ===
echo Mozesz sprawdzic wynik: sprawdz.bat
pause
endlocal
