@echo off
chcp 65001 >nul
REM ============================================================
REM  setup.bat - instalacja zaleznosci generatora DXF
REM ============================================================
setlocal

echo.
echo === Instalacja zaleznosci (Python) ===
echo.

REM --- wykryj Python ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [BLAD] Nie znaleziono Pythona. Zainstaluj Python 3.10+ z https://www.python.org/downloads/
    echo        Przy instalacji zaznacz "Add Python to PATH".
    pause
    exit /b 1
)

echo Uzywam: %PY%
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
