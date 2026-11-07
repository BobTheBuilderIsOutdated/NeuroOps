@echo off
cd /d "%~dp0"
python webcam.py
if errorlevel 1 pause
