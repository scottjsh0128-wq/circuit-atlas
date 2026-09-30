@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0claude-ml.ps1" %*
exit /b %ERRORLEVEL%
