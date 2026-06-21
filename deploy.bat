@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo   A-Share Trading Deploy
echo ========================================
echo.
python deploy.py
echo.
pause
