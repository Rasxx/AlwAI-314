# AlwAI-314
This repository contains an Agentic AI server built with FastAPI as part of the AlwAI-314 framework. The project explores how AI agents can reason, use tools, and interact with external systems through a ReAct-based architecture. It is designed to simulate real-world AI engineering environments and focuses on building scalable and extensible AI.

<!--
============================================================
Author: Akter Uddin Rony at Alwajeez Tech
Updated on: January 5, 2026
============================================================
-->

# Agentic AI System

Model: AlwAi 314 - A fully automated Agentic AI system powered by Llama 3.2, Ollama, and n8n workflow automation.

## Overview

This system provides:

- **ReAct Agent**: Reasoning + Acting loop for complex task solving
- **Tool Calling**: Built-in tools for web search, calculations, file operations, HTTP requests, and ZATCA compliance
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI API
- **n8n Integration**: Workflow automation with pre-built templates
- **ZATCA Compliance**: Saudi Arabia e-invoicing compliance tools

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER/CLIENT                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     n8n WORKFLOW ENGINE                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │Webhooks │  │Schedule │  │ Triggers│  │  Logic  │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       └────────────┴────────────┴────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC API SERVER                            │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                    ReAct Agent Loop                     │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │     │
│  │  │ THOUGHT  │→ │  ACTION  │→ │OBSERVATION│→ ... → END │     │
│  │  └──────────┘  └──────────┘  └──────────┘             │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                    TOOL EXECUTOR                        │     │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │     │
│  │  │ Search │ │  Calc  │ │  File  │ │  HTTP  │ ...      │     │
│  │  └────────┘ └────────┘ └────────┘ └────────┘          │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OLLAMA LLM BACKEND                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Llama 3.2 3B / Aletheia Model                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Automated Setup (Recommended)

**Windows (PowerShell):**
```powershell
.\setup.ps1 -ModelPath "D:\AI\Uncensored\Aletheia-Llama-3.2-3B-main"
```

**Linux/WSL:**
```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Docker Compose

```bash
docker compose up -d
```

### Option 3: Manual Setup

1. **Start Ollama:**
   ```bash
   ollama serve
   ollama pull llama3.2:3b
   ```

2. **Start API Server:**
   ```bash
   cd api
   pip install -r requirements.txt
   python -m uvicorn agentic_server:app --host 0.0.0.0 --port 8000
   ```

3. **Start n8n:**
   ```bash
   n8n start
   # Or: docker run -p 5678:5678 n8nio/n8n
   ```

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/models` | GET | List available models |
| `/v1/chat/completions` | POST | Chat completion (OpenAI-compatible) |
| `/v1/agent/run` | POST | Run ReAct agent |
| `/v1/tools` | GET | List available tools |
| `/v1/tools/{name}/execute` | POST | Execute specific tool |
| `/webhook/n8n` | POST | Receive n8n webhooks |

### Chat Completion

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of Saudi Arabia?"}
    ],
    "model": "aletheia-3b",
    "temperature": 0.7
  }'
```

### Run Agent Task

```bash
curl -X POST http://localhost:8000/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Calculate the total with 15% VAT for items: 100 SAR, 250 SAR, 75 SAR",
    "tools": ["calculator"],
    "max_iterations": 5
  }'
```

### Agent with Multiple Tools

```bash
curl -X POST http://localhost:8000/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Get current time in Riyadh, then calculate how many hours until midnight",
    "tools": ["get_current_time", "calculator"],
    "context": {"timezone": "Asia/Riyadh"},
    "max_iterations": 8
  }'
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `calculator` | Mathematical calculations |
| `get_current_time` | Current date/time with timezone |
| `web_search` | Web search (requires API integration) |
| `send_webhook` | Send data to n8n webhooks |
| `file_operations` | Read/write files |
| `http_request` | Make HTTP API calls |
| `zatca_compliance` | ZATCA e-invoice validation |

## n8n Workflows

Pre-built workflows included:

### 1. Agentic AI Workflow (`agentic-ai-workflow.json`)
- `/webhook/ai-task` - Run agent tasks via webhook
- `/webhook/chat` - Simple chat interface
- Daily scheduled agent tasks with notifications

### 2. ZATCA Compliance Workflow (`zatca-compliance-workflow.json`)
- `/webhook/zatca-validate` - Validate invoices
- `/webhook/zatca-generate` - Generate compliant invoices
- `/webhook/erp-invoice` - ERP integration endpoint

### Importing Workflows

1. Open n8n at http://localhost:5678
2. Go to **Workflows** → **Import from File**
3. Select JSON files from `n8n-workflows/` directory

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `MODEL_NAME` | `aletheia-3b` | Default model name |
| `N8N_WEBHOOK_URL` | `http://localhost:5678/webhook` | n8n webhook base URL |
| `MAX_ITERATIONS` | `10` | Max agent iterations |
| `DEFAULT_TEMPERATURE` | `0.7` | LLM temperature |
| `TIMEOUT` | `120` | Request timeout (seconds) |

### Custom `.env` File

```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=aletheia-3b
N8N_WEBHOOK_URL=http://localhost:5678/webhook
MAX_ITERATIONS=10
DEFAULT_TEMPERATURE=0.7
TIMEOUT=120
```

## Adding Custom Tools

Edit `api/agentic_server.py` and add to `BUILTIN_TOOLS`:

```python
BUILTIN_TOOLS["my_custom_tool"] = ToolDefinition(
    name="my_custom_tool",
    description="Description of what the tool does",
    parameters={
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    }
)
```

Then implement in `ToolExecutor.execute()`:

```python
elif tool_name == "my_custom_tool":
    return self._my_custom_tool(arguments.get("param1", ""))
```

## ZATCA Integration

For full ZATCA Phase-2 compliance, implement these in `ToolExecutor._zatca_compliance()`:

1. **Invoice Validation**: Check required fields, VAT calculations, XML structure
2. **XML Generation**: Generate UBL 2.1 compliant XML
3. **QR Code**: Generate TLV-encoded QR data
4. **Digital Signature**: Sign with ZATCA-approved certificates
5. **API Submission**: Submit to ZATCA sandbox/production

## Troubleshooting

### Ollama Connection Failed
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Model Not Found
```bash
# List available models
ollama list

# Pull model
ollama pull llama3.2:3b

# Or create custom model
cd /path/to/model
ollama create aletheia-3b -f Modelfile
```

### n8n Webhook Not Working
1. Ensure n8n is running: `curl http://localhost:5678/healthz`
2. Check webhook URL matches configuration
3. Verify workflow is activated in n8n

## Performance Tips

1. **GPU Acceleration**: Ensure NVIDIA drivers and CUDA are properly configured
2. **Context Size**: Reduce `n_ctx` for lower memory usage
3. **Batch Requests**: Use batch endpoints for multiple requests
4. **Caching**: Enable Redis for response caching

## License

This project is for internal use at Alwajeez Tech. See LICENSE file for details.

## Support

For issues or questions:
- Internal: Contact IT Department
- External: Create GitHub issue
