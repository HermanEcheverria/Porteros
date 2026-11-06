@echo off
cd /d "%~dp0"
set PY=py -3
where py >nul 2>nul || set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
%PY% -m pip install --quiet numpy
%PY% analizar_registro.py --todas
pause
