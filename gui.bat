@echo off
chcp 65001 >nul
REM ============================================================
REM  gui.bat - uruchomienie GRAFICZNEGO interfejsu (PySide6)
REM
REM  Okno pozwala: wczytac pliki, wskazac ZAPASY (SZ) i MUFY (ZR)
REM  przy studniach, podejrzec metryke i wygenerowac DXF.
REM
REM  Wymaga PySide6 (instaluje setup.bat). Bez argumentow.
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
echo Uzywam interpretera: %PY%
echo Uruchamiam GUI generatora...
%PY% generuj.py

if errorlevel 1 (
    echo.
    echo [INFO] GUI zakonczone lub wystapil blad.
    echo        Jesli brak PySide6 - uruchom setup.bat.
    pause
)
endlocal
