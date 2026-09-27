@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Circuit-Tools.ps1"
if errorlevel 1 pause
