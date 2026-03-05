#!/bin/bash

# ============================================================
# Author: Akter Uddin Rony at Alwajeez Tech
# Updated on: December 10, 2025
# ============================================================
# AGENTIC AI SYSTEM - LINUX/WSL SETUP SCRIPT
# ============================================================
# Model: AlwAi 314
# Purpose: Fully automated Agentic AI with n8n integration
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
MODEL_PATH="${MODEL_PATH:-/mnt/d/AI/Uncensored/Aletheia-Llama-3.2-3B-main}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)/agentic-system}"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          AGENTIC AI SYSTEM - AUTOMATED SETUP                 ║"
echo "║          Powered by Llama 3.2 + Ollama + n8n                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ------------------------------------------------------------
# FUNCTION: Check command exists
# ------------------------------------------------------------
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${YELLOW}!${NC} $1 not found"
        return 1
    fi
}

# ------------------------------------------------------------
# 1. CHECK PREREQUISITES
# ------------------------------------------------------------
echo -e "\n${YELLOW}[1/7] Checking prerequisites...${NC}"

check_command python3 || { echo -e "${RED}Python3 is required${NC}"; exit 1; }
check_command pip3 || check_command pip
check_command curl

DOCKER_AVAILABLE=false
if check_command docker; then
    DOCKER_AVAILABLE=true
fi

OLLAMA_AVAILABLE=false
if check_command ollama; then
    OLLAMA_AVAILABLE=true
fi

# ------------------------------------------------------------
# 2. CREATE DIRECTORY STRUCTURE
# ------------------------------------------------------------
echo -e "\n${YELLOW}[2/7] Creating directory structure...${NC}"

mkdir -p "$INSTALL_DIR"/{api,config,tools,n8n-workflows,data,output,logs}
cd "$INSTALL_DIR"

echo -e "  ${GREEN}✓${NC} Created $INSTALL_DIR"

# ------------------------------------------------------------
# 3. INSTALL OLLAMA (if needed)
# ------------------------------------------------------------
echo -e "\n${YELLOW}[3/7] Setting up Ollama...${NC}"

if [ "$OLLAMA_AVAILABLE" = false ]; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "  ${GREEN}✓${NC} Ollama installed"
else
    echo -e "  ${GREEN}✓${NC} Ollama already installed"
fi

# Start Ollama service
if ! pgrep -x "ollama" > /dev/null; then
    echo "  Starting Ollama service..."
    ollama serve &
    sleep 5
fi

# Pull base model
echo "  Pulling llama3.2:3b model (this may take a while)..."
ollama pull llama3.2:3b || echo -e "  ${YELLOW}!${NC} Model pull failed, will try later"

# ------------------------------------------------------------
# 4. SETUP PYTHON ENVIRONMENT
# ------------------------------------------------------------
echo -e "\n${YELLOW}[4/7] Setting up Python environment...${NC}"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip --quiet
pip install \
    fastapi uvicorn pydantic httpx \
    langchain langchain-community langgraph \
    huggingface_hub llama-cpp-python \
    redis aiohttp python-dotenv pytz \
    --quiet

echo -e "  ${GREEN}✓${NC} Python environment ready"

# ------------------------------------------------------------
# 5. COPY/CREATE APPLICATION FILES
# ------------------------------------------------------------
echo -e "\n${YELLOW}[5/7] Setting up application files...${NC}"

# Copy files from the setup directory if they exist
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

if [ -f "$SCRIPT_DIR/api/agentic_server.py" ]; then
    cp -r "$SCRIPT_DIR/api/"* "$INSTALL_DIR/api/"
    cp -r "$SCRIPT_DIR/n8n-workflows/"* "$INSTALL_DIR/n8n-workflows/"
    echo -e "  ${GREEN}✓${NC} Application files copied"
else
    echo -e "  ${YELLOW}!${NC} Application files not found, will need manual setup"
fi

# ------------------------------------------------------------
# 6. CREATE OLLAMA MODEL (if GGUF exists)
# ------------------------------------------------------------
echo -e "\n${YELLOW}[6/7] Setting up custom model...${NC}"

if [ -d "$MODEL_PATH" ]; then
    GGUF_FILE=$(find "$MODEL_PATH" -name "*.gguf" -type f | head -1)
    
    if [ -n "$GGUF_FILE" ] && [ -f "$MODEL_PATH/Modelfile" ]; then
        echo "  Found GGUF model: $GGUF_FILE"
        cd "$MODEL_PATH"
        
        # Check if model already exists
        if ollama list | grep -q "aletheia-3b"; then
            echo -e "  ${GREEN}✓${NC} Model 'aletheia-3b' already exists"
        else
            echo "  Creating Ollama model..."
            ollama create aletheia-3b -f Modelfile
            echo -e "  ${GREEN}✓${NC} Model 'aletheia-3b' created"
        fi
        
        cd "$INSTALL_DIR"
    else
        echo -e "  ${YELLOW}!${NC} GGUF file or Modelfile not found in $MODEL_PATH"
    fi
else
    echo -e "  ${YELLOW}!${NC} Model path not found: $MODEL_PATH"
fi

# ------------------------------------------------------------
# 7. CREATE STARTUP SCRIPTS
# ------------------------------------------------------------
echo -e "\n${YELLOW}[7/7] Creating startup scripts...${NC}"

# Create start script
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

echo "Starting Agentic AI System..."

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 5
fi

# Activate virtual environment
source venv/bin/activate

# Start API server
echo "Starting Agentic API server on port 8000..."
cd api
python -m uvicorn agentic_server:app --host 0.0.0.0 --port 8000 --reload &

echo ""
echo "Services started!"
echo "  - Ollama API:    http://localhost:11434"
echo "  - Agentic API:   http://localhost:8000"
echo ""
echo "To start n8n, run: n8n start (or use Docker)"
EOF
chmod +x "$INSTALL_DIR/start.sh"

# Create stop script
cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
echo "Stopping Agentic AI System..."
pkill -f "uvicorn agentic_server"
pkill -f "ollama serve"
echo "Services stopped."
EOF
chmod +x "$INSTALL_DIR/stop.sh"

# Create test script
cat > "$INSTALL_DIR/test.sh" << 'EOF'
#!/bin/bash
echo "Testing Agentic AI System..."

# Test Ollama
echo -n "Ollama API: "
curl -s http://localhost:11434/api/tags > /dev/null && echo "✓ OK" || echo "✗ FAIL"

# Test Agentic API
echo -n "Agentic API: "
curl -s http://localhost:8000/health > /dev/null && echo "✓ OK" || echo "✗ FAIL"

# Test chat
echo ""
echo "Testing chat completion..."
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Say hello!"}], "model": "aletheia-3b"}' | jq .
EOF
chmod +x "$INSTALL_DIR/test.sh"

# Create environment file
cat > "$INSTALL_DIR/.env" << EOF
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=aletheia-3b
N8N_WEBHOOK_URL=http://localhost:5678/webhook
MAX_ITERATIONS=10
DEFAULT_TEMPERATURE=0.7
TIMEOUT=120
EOF

echo -e "  ${GREEN}✓${NC} Startup scripts created"

# ------------------------------------------------------------
# FINAL SUMMARY
# ------------------------------------------------------------
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE!                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "
${CYAN}INSTALLATION DIRECTORY:${NC} $INSTALL_DIR

${CYAN}NEXT STEPS:${NC}

1. ${YELLOW}Start the system:${NC}
   cd $INSTALL_DIR
   ./start.sh

2. ${YELLOW}Test the system:${NC}
   ./test.sh

3. ${YELLOW}Start n8n (choose one):${NC}
   Option A: npm install -g n8n && n8n start
   Option B: docker run -p 5678:5678 n8nio/n8n

4. ${YELLOW}Import n8n workflows:${NC}
   - Open http://localhost:5678
   - Import JSON files from: $INSTALL_DIR/n8n-workflows/

${CYAN}API ENDPOINTS:${NC}
   - Ollama:      http://localhost:11434
   - Agentic API: http://localhost:8000
   - n8n:         http://localhost:5678

${CYAN}EXAMPLE USAGE:${NC}

# Simple chat
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'

# Run agent task
curl -X POST http://localhost:8000/v1/agent/run \\
  -H 'Content-Type: application/json' \\
  -d '{\"task\": \"What is the current time in Riyadh?\", \"tools\": [\"get_current_time\"]}'
"
