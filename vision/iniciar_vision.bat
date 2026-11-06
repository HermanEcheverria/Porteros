@echo off
cd /d "%~dp0"
echo Instalando librerias (solo tarda la primera vez)...
py -3 -m pip install --quiet opencv-python numpy
py -3 vision_bola.py
pause
