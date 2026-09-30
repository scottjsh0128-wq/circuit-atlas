@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-ml-launcher.ps1" %*
exit /b %ERRORLEVEL%
