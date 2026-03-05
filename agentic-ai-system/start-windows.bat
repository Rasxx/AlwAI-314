@echo off
REM ============================================================
REM Author: Akter Uddin Rony at Alwajeez Tech
REM Updated on: December 18, 2025
REM ============================================================
REM Model AlwAi 314 - ONE-CLICK WINDOWS LAUNCHER
REM ============================================================
REM Double-click this file to start the complete system
REM ============================================================

title Agentic AI System

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║          AGENTIC AI SYSTEM - STARTING...                     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Configuration
set MODEL_PATH=D:\AI\Uncensored\Aletheia-Llama-3.2-3B-main
set API_PORT=8000
set N8N_PORT=5678

REM Check if Ollama is installed
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Ollama not found. Please install from https://ollama.com
    echo.
    pause
    exit /b 1
)

REM Start Ollama in background
echo [1/4] Starting Ollama server...
start /min cmd /c "ollama serve"
timeout /t 5 /nobreak >nul

REM Check if model exists, if not create it
echo [2/4] Checking model...
ollama list | findstr /i "aletheia-3b" >nul
if %ERRORLEVEL% neq 0 (
    echo      Creating aletheia-3b model...
    cd /d %MODEL_PATH%
    if exist "Modelfile" (
        ollama create aletheia-3b -f Modelfile
    ) else (
        echo      Modelfile not found, using llama3.2:3b
        ollama pull llama3.2:3b
    )
)
echo      Model ready!

REM Start API server
echo [3/4] Starting Agentic API server on port %API_PORT%...
cd /d %~dp0
if exist "api\agentic_server.py" (
    start /min cmd /c "cd api && python -m uvicorn agentic_server:app --host 0.0.0.0 --port %API_PORT%"
) else (
    echo      [!] API server file not found. Skipping...
)
timeout /t 3 /nobreak >nul

REM Check if n8n should be started
echo [4/4] Starting n8n (if available)...
where n8n >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start /min cmd /c "n8n start"
    echo      n8n starting on port %N8N_PORT%
) else (
    echo      [!] n8n not found. Install with: npm install -g n8n
    echo      Or use Docker: docker run -p 5678:5678 n8nio/n8n
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    SYSTEM STARTED!                           ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo   Services:
echo   ---------------------------------------------------------
echo   Ollama API:     http://localhost:11434
echo   Agentic API:    http://localhost:%API_PORT%
echo   n8n Dashboard:  http://localhost:%N8N_PORT%
echo   ---------------------------------------------------------
echo.
echo   API Documentation: http://localhost:%API_PORT%/docs
echo.
echo   Press any key to open the API in your browser...
pause >nul

start http://localhost:%API_PORT%/docs

echo.
echo   System is running. Close this window to keep services running.
echo   To stop all services, run: stop-windows.bat
echo.
pause
