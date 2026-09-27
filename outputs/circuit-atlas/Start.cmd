@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required. Install Node.js then try again.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:4173"
node server.mjs
pause
