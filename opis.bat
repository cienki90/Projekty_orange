@echo off
chcp 65001 >nul
REM ============================================================
REM  opis.bat - generuje OPIS TECHNICZNY (.docx) + DXF
REM
REM  Opis powstaje na podstawie WT (wt.xls) oraz rysunku:
REM  numery studni z mufami/zapasami, zakonczenia, dlugosci.
REM  Rownowazne: generuj.bat --opis ...
REM
REM  Uzycie:
REM    opis.bat                      (auto-wykrycie plikow + opis)
REM    opis.bat wspol.xlsx wt.xls out.dxf
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
echo Generuje DXF + opis techniczny (.docx)...
if "%~1"=="" (
    %PY% generuj.py --auto --opis
) else (
    %PY% generuj.py --opis %*
)

if errorlevel 1 (
    echo.
    echo [INFO] Zakonczono (blad lub anulowano).
    pause
    exit /b 1
)
echo.
echo === Gotowe. Opis zapisany jako *_opis.docx obok DXF ===
pause
endlocal
