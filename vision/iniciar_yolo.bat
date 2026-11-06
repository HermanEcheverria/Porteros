@echo off
cd /d "%~dp0"
set PY=py -3
where py >nul 2>nul || set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
echo Instalando librerias (la primera vez tarda varios minutos, descarga ~300 MB)...
%PY% -m pip install --quiet ultralytics opencv-python
%PY% vision_yolo.py
pause
