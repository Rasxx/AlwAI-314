# ============================================================
# Author: Akter Uddin Rony at Alwajeez Tech
# Updated on: November 25, 2025
# ============================================================
# AGENTIC AI SYSTEM - COMPLETE AUTOMATED SETUP
# For Windows with WSL2 / Native Windows
# ============================================================
# Author: Generated for Alwajeez Tech
# Purpose: Fully automated Agentic AI with n8n integration
# ============================================================

param(
    [switch]$SkipOllama,
    [switch]$SkipN8N,
    [switch]$SkipPython,
    [string]$ModelPath = "D:\AI\Uncensored\Aletheia-Llama-3.2-3B-main"
)

$ErrorActionPreference = "Stop"

Write-Host @"
╔══════════════════════════════════════════════════════════════╗
║          AGENTIC AI SYSTEM - AUTOMATED SETUP                 ║
║          Powered by Llama 3.2 + Ollama + n8n                 ║
╚══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# ------------------------------------------------------------
# 1. CHECK PREREQUISITES
# ------------------------------------------------------------
Write-Host "`n[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Check if Ollama is installed
$ollamaInstalled = $false
try {
    $ollamaVersion = ollama --version 2>&1
    $ollamaInstalled = $true
    Write-Host "  ✓ Ollama found: $ollamaVersion" -ForegroundColor Green
} catch {
    Write-Host "  ! Ollama not found. Will install..." -ForegroundColor Yellow
}

# Check Node.js for n8n
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  ✓ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ! Node.js not found. Will install n8n via Docker instead." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 2. INSTALL OLLAMA (if needed)
# ------------------------------------------------------------
if (-not $SkipOllama -and -not $ollamaInstalled) {
    Write-Host "`n[2/6] Installing Ollama..." -ForegroundColor Yellow
    
    # Download Ollama installer
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    
    Write-Host "  Downloading Ollama installer..."
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $installerPath
    
    Write-Host "  Running installer (follow the prompts)..."
    Start-Process -FilePath $installerPath -Wait
    
    Write-Host "  ✓ Ollama installed" -ForegroundColor Green
} else {
    Write-Host "`n[2/6] Skipping Ollama installation" -ForegroundColor Gray
}

# ------------------------------------------------------------
# 3. SETUP PYTHON ENVIRONMENT
# ------------------------------------------------------------
if (-not $SkipPython) {
    Write-Host "`n[3/6] Setting up Python environment..." -ForegroundColor Yellow
    
    # Create virtual environment
    $venvPath = "$ModelPath\agentic-venv"
    if (-not (Test-Path $venvPath)) {
        python -m venv $venvPath
        Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
    }
    
    # Activate and install packages
    & "$venvPath\Scripts\Activate.ps1"
    
    Write-Host "  Installing Python packages..."
    pip install --upgrade pip --quiet
    pip install llama-cpp-python[server] fastapi uvicorn pydantic requests huggingface_hub --quiet
    pip install langchain langchain-community langgraph --quiet
    
    Write-Host "  ✓ Python packages installed" -ForegroundColor Green
} else {
    Write-Host "`n[3/6] Skipping Python setup" -ForegroundColor Gray
}

# ------------------------------------------------------------
# 4. CREATE OLLAMA MODEL
# ------------------------------------------------------------
Write-Host "`n[4/6] Setting up Ollama model..." -ForegroundColor Yellow

$modelFile = "$ModelPath\Modelfile"
if (Test-Path $modelFile) {
    Push-Location $ModelPath
    
    # Check if model exists
    $existingModels = ollama list 2>&1
    if ($existingModels -match "aletheia-3b") {
        Write-Host "  Model 'aletheia-3b' already exists" -ForegroundColor Gray
    } else {
        # Check if GGUF file exists
        $ggufFile = Get-ChildItem -Path $ModelPath -Filter "*.gguf" | Select-Object -First 1
        if ($ggufFile) {
            Write-Host "  Creating Ollama model from $($ggufFile.Name)..."
            ollama create aletheia-3b -f Modelfile
            Write-Host "  ✓ Ollama model created" -ForegroundColor Green
        } else {
            Write-Host "  ! No GGUF file found. Run GGUF-chat.py first to download." -ForegroundColor Yellow
        }
    }
    
    Pop-Location
} else {
    Write-Host "  ! Modelfile not found at $modelFile" -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 5. CREATE API SERVER AND TOOLS
# ------------------------------------------------------------
Write-Host "`n[5/6] Creating API server and agent tools..." -ForegroundColor Yellow

# Create the agentic system directory
$agenticDir = "$ModelPath\agentic-system"
New-Item -ItemType Directory -Path $agenticDir -Force | Out-Null
New-Item -ItemType Directory -Path "$agenticDir\tools" -Force | Out-Null

Write-Host "  ✓ Agentic system files created at $agenticDir" -ForegroundColor Green

# ------------------------------------------------------------
# 6. SETUP N8N
# ------------------------------------------------------------
if (-not $SkipN8N) {
    Write-Host "`n[6/6] Setting up n8n..." -ForegroundColor Yellow
    
    # Check if Docker is available
    $dockerAvailable = $false
    try {
        docker --version 2>&1 | Out-Null
        $dockerAvailable = $true
    } catch {}
    
    if ($dockerAvailable) {
        Write-Host "  Starting n8n via Docker..."
        
        # Create n8n docker-compose
        $n8nCompose = @"
version: '3.8'
services:
  n8n:
    image: n8nio/n8n
    container_name: n8n-agentic
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=agentic123
      - GENERIC_TIMEZONE=Asia/Riyadh
    volumes:
      - n8n_data:/home/node/.n8n
    restart: unless-stopped

volumes:
  n8n_data:
"@
        $n8nCompose | Out-File -FilePath "$agenticDir\docker-compose.n8n.yml" -Encoding UTF8
        
        Write-Host "  ✓ n8n docker-compose created" -ForegroundColor Green
        Write-Host "  Run: docker compose -f docker-compose.n8n.yml up -d" -ForegroundColor Cyan
    } else {
        Write-Host "  Installing n8n globally via npm..."
        npm install -g n8n
        Write-Host "  ✓ n8n installed. Run 'n8n start' to launch." -ForegroundColor Green
    }
} else {
    Write-Host "`n[6/6] Skipping n8n setup" -ForegroundColor Gray
}

# ------------------------------------------------------------
# FINAL INSTRUCTIONS
# ------------------------------------------------------------
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                    SETUP COMPLETE!                           ║
╚══════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Green

Write-Host @"

NEXT STEPS:
-----------

1. START OLLAMA SERVER:
   ollama serve

2. START THE AGENTIC API SERVER:
   cd $agenticDir
   python agentic_server.py

3. START N8N:
   Option A (Docker): docker compose -f docker-compose.n8n.yml up -d
   Option B (NPM):    n8n start

4. ACCESS SERVICES:
   - Ollama API:    http://localhost:11434
   - Agentic API:   http://localhost:8000
   - n8n Dashboard: http://localhost:5678 (admin/agentic123)

5. IMPORT N8N WORKFLOW:
   Import the workflow JSON from: $agenticDir\n8n-workflows\

"@ -ForegroundColor White

Write-Host "Documentation: $agenticDir\docs\README.md" -ForegroundColor Cyan
