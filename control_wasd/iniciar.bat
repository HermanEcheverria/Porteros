@echo off
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
if not defined PY for /d %%D in ("C:\Program Files\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY="%USERPROFILE%\anaconda3\python.exe""
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY="%USERPROFILE%\miniconda3\python.exe""
if not defined PY (
  echo No encontre Python en esta computadora.
  echo Instalalo desde python.org y marca "Add Python to PATH" en el instalador.
  pause
  exit /b
)
echo Usando: %PY%
echo Instalando librerias (solo tarda la primera vez)...
%PY% -m pip install --quiet pyserial pynput
%PY% control.py %*
pause
