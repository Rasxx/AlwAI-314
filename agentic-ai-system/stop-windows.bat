@echo off
REM ============================================================
REM Author: Akter Uddin Rony at Alwajeez Tech
REM Updated on: December 18, 2025
REM ============================================================
REM AGENTIC AI SYSTEM - STOP ALL SERVICES
REM ============================================================

title Stopping Agentic AI System

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║          AGENTIC AI SYSTEM - STOPPING SERVICES               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo [1/3] Stopping Ollama...
taskkill /f /im ollama.exe >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo      Ollama stopped.
) else (
    echo      Ollama was not running.
)

echo [2/3] Stopping Python/Uvicorn...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo      Python processes stopped.

echo [3/3] Stopping n8n...
taskkill /f /im node.exe >nul 2>&1
echo      Node processes stopped.

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                  ALL SERVICES STOPPED                        ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
