@echo off
chcp 65001 >nul
REM ============================================================
REM  setup.bat - instalacja zaleznosci generatora DXF
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo === Instalacja zaleznosci (Python) ===
echo.

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
echo [BLAD] Nie znaleziono Pythona. Zainstaluj Python 3.10+ z:
echo        https://www.python.org/downloads/
echo        Przy instalacji zaznacz "Add Python to PATH".
pause
exit /b 1

:have_py
echo Uzywam interpretera: %PY%
%PY% --version

echo.
echo Aktualizacja pip...
%PY% -m pip install --upgrade pip

echo.
echo Instalacja pakietow z requirements.txt...
%PY% -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [BLAD] Instalacja zaleznosci nie powiodla sie.
    pause
    exit /b 1
)

echo.
echo === Gotowe. Mozesz uruchomic generuj.bat ===
pause
endlocal
