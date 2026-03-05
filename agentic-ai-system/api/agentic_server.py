# ============================================================
# Author: Akter Uddin Rony at Alwajeez Tech
# Updated on: December 15, 2025
# ============================================================

"""
============================================================
AGENTIC AI SERVER
============================================================
A FastAPI-based agentic AI server with:
- OpenAI-compatible API endpoints
- Tool/Function calling support
- ReAct agent loop
- n8n webhook integration
- Multiple backend support (Ollama, llama.cpp)

Author: Generated for Alwajeez Tech
============================================================
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import uvicorn
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import os
import shutil

# LangChain / LangGraph imports
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgenticServer")

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2:3b")
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
    DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
    TIMEOUT = int(os.getenv("TIMEOUT", "120"))
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
    RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ToolParameter(BaseModel):
    type: str
    description: str
    enum: Optional[List[str]] = None
    required: Optional[bool] = True


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class Message(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None  # For tool messages
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = Config.MODEL_NAME
    temperature: Optional[float] = Config.DEFAULT_TEMPERATURE
    max_tokens: Optional[int] = 2048
    tools: Optional[List[ToolDefinition]] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class AgentTask(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None
    tools: Optional[List[str]] = None
    max_iterations: Optional[int] = Config.MAX_ITERATIONS


class AgentResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[str] = None
    steps: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    total_iterations: int


class WebhookPayload(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None

# RAG request/response models
class RagIngestRequest(BaseModel):
    file_path: str
    chunk_size: int = Config.RAG_CHUNK_SIZE
    chunk_overlap: int = Config.RAG_CHUNK_OVERLAP

class RagIngestResponse(BaseModel):
    status: str
    file_path: str
    chunks_added: int
    total_documents: int

class FinetuneRequest(BaseModel):
    dataset_path: str = "training_data.jsonl"
    base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    learning_rate: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    output_dir: str = "./alwajeez-finetuned-model"

class FinetuneResponse(BaseModel):
    status: str
    job_id: str
    message: str

class AlignRequest(BaseModel):
    dataset_path: str
    base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    beta: float = 0.1
    learning_rate: float = 5e-5
    epochs: int = 3

class AlignResponse(BaseModel):
    status: str
    job_id: str
    message: str

class RagQueryRequest(BaseModel):
    question: str
    k: int = 4

class RagQueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]
    event: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None


# ============================================================
# BUILT-IN TOOLS
# ============================================================

BUILTIN_TOOLS: Dict[str, ToolDefinition] = {
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the web for current information. Use for real-time data, news, or facts.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    ),
    "calculator": ToolDefinition(
        name="calculator",
        description="Perform mathematical calculations. Supports basic arithmetic and common functions.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2 + 2 * 3')"
                }
            },
            "required": ["expression"]
        }
    ),
    "get_current_time": ToolDefinition(
        name="get_current_time",
        description="Get the current date and time",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone (e.g., 'Asia/Riyadh', 'UTC')",
                    "default": "Asia/Riyadh"
                }
            },
            "required": []
        }
    ),
    "send_webhook": ToolDefinition(
        name="send_webhook",
        description="Send data to an n8n webhook for workflow automation",
        parameters={
            "type": "object",
            "properties": {
                "webhook_name": {
                    "type": "string",
                    "description": "Name/path of the webhook endpoint"
                },
                "payload": {
                    "type": "object",
                    "description": "JSON payload to send"
                }
            },
            "required": ["webhook_name", "payload"]
        }
    ),
    "file_operations": ToolDefinition(
        name="file_operations",
        description="Read or write files. Use for document processing.",
        parameters={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list"],
                    "description": "Operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)"
                }
            },
            "required": ["operation", "path"]
        }
    ),
    "http_request": ToolDefinition(
        name="http_request",
        description="Make HTTP requests to external APIs",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method"
                },
                "url": {
                    "type": "string",
                    "description": "URL to request"
                },
                "headers": {
                    "type": "object",
                    "description": "Request headers"
                },
                "body": {
                    "type": "object",
                    "description": "Request body (for POST/PUT)"
                }
            },
            "required": ["method", "url"]
        }
    ),
    "zatca_compliance": ToolDefinition(
        name="zatca_compliance",
        description="Check ZATCA e-invoice compliance or generate compliant invoices",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["validate", "generate", "check_status"],
                    "description": "Action to perform"
                },
                "invoice_data": {
                    "type": "object",
                    "description": "Invoice data for validation or generation"
                }
            },
            "required": ["action"]
        }
    )
}


# ============================================================
# TOOL EXECUTOR
# ============================================================

class ToolExecutor:
    """Executes tools and returns results"""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result as a string"""
        try:
            if tool_name == "calculator":
                return self._calculator(arguments.get("expression", ""))
            
            elif tool_name == "get_current_time":
                return self._get_current_time(arguments.get("timezone", "Asia/Riyadh"))
            
            elif tool_name == "web_search":
                return await self._web_search(arguments.get("query", ""))
            
            elif tool_name == "send_webhook":
                return await self._send_webhook(
                    arguments.get("webhook_name", ""),
                    arguments.get("payload", {})
                )
            
            elif tool_name == "file_operations":
                return self._file_operations(
                    arguments.get("operation", "read"),
                    arguments.get("path", ""),
                    arguments.get("content", "")
                )
            
            elif tool_name == "http_request":
                return await self._http_request(
                    arguments.get("method", "GET"),
                    arguments.get("url", ""),
                    arguments.get("headers", {}),
                    arguments.get("body", {})
                )
            
            elif tool_name == "zatca_compliance":
                return self._zatca_compliance(
                    arguments.get("action", "validate"),
                    arguments.get("invoice_data", {})
                )
            
            else:
                return f"Unknown tool: {tool_name}"
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Error executing {tool_name}: {str(e)}"
    
    def _calculator(self, expression: str) -> str:
        """Safe mathematical expression evaluator"""
        try:
            # Only allow safe characters
            allowed = set("0123456789+-*/.() ")
            if not all(c in allowed for c in expression):
                return "Error: Invalid characters in expression"
            
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Calculation error: {str(e)}"
    
    def _get_current_time(self, timezone: str) -> str:
        """Get current time"""
        from datetime import datetime
        try:
            import pytz
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
        except:
            now = datetime.now()
        
        return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    
    async def _web_search(self, query: str) -> str:
        """Placeholder for web search - integrate with your preferred search API"""
        # TODO: Integrate with SerpAPI, Bing, or custom search
        return f"Web search for '{query}': [Implement search API integration]"
    
    async def _send_webhook(self, webhook_name: str, payload: Dict) -> str:
        """Send data to n8n webhook"""
        try:
            url = f"{Config.N8N_WEBHOOK_URL}/{webhook_name}"
            response = await self.http_client.post(url, json=payload)
            return f"Webhook sent successfully. Status: {response.status_code}"
        except Exception as e:
            return f"Webhook error: {str(e)}"
    
    def _file_operations(self, operation: str, path: str, content: str = "") -> str:
        """File operations with safety checks"""
        try:
            # Safety: Only allow operations in specific directories
            allowed_dirs = ["./data", "./output", "./temp"]
            if not any(path.startswith(d) for d in allowed_dirs):
                return f"Error: Path must be in {allowed_dirs}"
            
            if operation == "read":
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()[:5000]  # Limit response size
            
            elif operation == "write":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"File written: {path}"
            
            elif operation == "list":
                files = os.listdir(path)
                return f"Files in {path}: {', '.join(files[:50])}"
            
            return f"Unknown operation: {operation}"
        except Exception as e:
            return f"File error: {str(e)}"
    
    async def _http_request(self, method: str, url: str, headers: Dict, body: Dict) -> str:
        """Make HTTP request"""
        try:
            if method == "GET":
                response = await self.http_client.get(url, headers=headers)
            elif method == "POST":
                response = await self.http_client.post(url, headers=headers, json=body)
            elif method == "PUT":
                response = await self.http_client.put(url, headers=headers, json=body)
            elif method == "DELETE":
                response = await self.http_client.delete(url, headers=headers)
            else:
                return f"Unsupported method: {method}"
            
            return f"Status: {response.status_code}\nBody: {response.text[:2000]}"
        except Exception as e:
            return f"HTTP error: {str(e)}"
    
    def _zatca_compliance(self, action: str, invoice_data: Dict) -> str:
        """ZATCA compliance operations - placeholder for your implementation"""
        if action == "validate":
            return "ZATCA validation: [Implement with your ZATCA integration]"
        elif action == "generate":
            return "ZATCA invoice generation: [Implement with your ZATCA integration]"
        elif action == "check_status":
            return "ZATCA status check: [Implement with your ZATCA integration]"
        return f"Unknown ZATCA action: {action}"

# Helper functions for RAG

def _load_and_chunk(file_path: str, chunk_size: int = Config.RAG_CHUNK_SIZE, chunk_overlap: int = Config.RAG_CHUNK_OVERLAP):
    """Load a file (text or PDF) and split into chunks using RecursiveCharacterTextSplitter."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_path.lower().endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

def _format_docs(docs):
    """Join document chunks into a single string for the LLM prompt."""
    return "\n\n".join(doc.page_content for doc in docs)


# ============================================================
# OLLAMA CLIENT
# ============================================================

class OllamaClient:
    """Client for Ollama API"""
    
    def __init__(self):
        self.base_url = Config.OLLAMA_BASE_URL
        self.client = httpx.AsyncClient(timeout=Config.TIMEOUT)
    
    async def chat(self, messages: List[Dict], model: str, temperature: float, 
                   tools: Optional[List[Dict]] = None) -> Dict:
        """Send chat request to Ollama"""
        
        # Format messages for Ollama
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.get("role"),
                "content": msg.get("content", "")
            })
        
        payload = {
            "model": model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        # Add tools if provided (for models that support it)
        if tools:
            payload["tools"] = tools
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")


# ============================================================
# REACT AGENT
# ============================================================

class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent
    Implements the thought-action-observation loop
    """
    
    SYSTEM_PROMPT = """You are an intelligent AI agent with access to tools. 
Use the ReAct framework to solve tasks:

1. THOUGHT: Analyze the task and decide what to do
2. ACTION: Call a tool if needed (format: ACTION: tool_name({{"param": "value"}}))
3. OBSERVATION: Analyze the tool result
4. Repeat until task is complete
5. FINAL ANSWER: Provide the complete answer

Available tools:
{tools_description}

Always think step by step. When you have enough information, provide FINAL ANSWER.
Format your response as:
THOUGHT: [your reasoning]
ACTION: tool_name({{"param": "value"}})

Or when complete:
THOUGHT: [your reasoning]
FINAL ANSWER: [your complete answer]"""
    
    def __init__(self):
        self.ollama = OllamaClient()
        self.tool_executor = ToolExecutor()
    
    def _get_tools_description(self, tool_names: Optional[List[str]] = None) -> str:
        """Get formatted description of available tools"""
        tools = BUILTIN_TOOLS
        if tool_names:
            tools = {k: v for k, v in tools.items() if k in tool_names}
        
        descriptions = []
        for name, tool in tools.items():
            params = json.dumps(tool.parameters, indent=2)
            descriptions.append(f"- {name}: {tool.description}\n  Parameters: {params}")
        
        return "\n".join(descriptions)
    
    def _parse_action(self, response: str) -> Optional[tuple]:
        """Parse ACTION from response"""
        import re
        
        # Look for ACTION: tool_name({"param": "value"})
        pattern = r'ACTION:\s*(\w+)\s*\((.+?)\)'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            tool_name = match.group(1)
            try:
                # Try to parse arguments as JSON
                args_str = match.group(2).strip()
                arguments = json.loads(args_str)
                return (tool_name, arguments)
            except json.JSONDecodeError:
                # Try to extract key-value pairs
                return (tool_name, {"raw": match.group(2)})
        
        return None
    
    def _check_final_answer(self, response: str) -> Optional[str]:
        """Check if response contains FINAL ANSWER"""
        if "FINAL ANSWER:" in response:
            parts = response.split("FINAL ANSWER:")
            if len(parts) > 1:
                return parts[1].strip()
        return None
    
    async def run(self, task: AgentTask) -> AgentResponse:
        """Run the ReAct agent loop"""
        import uuid

        task_id = str(uuid.uuid4())[:8]
        steps = []
        tool_calls = []

        # Build system prompt with available tools
        tools_desc = self._get_tools_description(task.tools)
        system_prompt = self.SYSTEM_PROMPT.format(tools_description=tools_desc)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task.task}"}
        ]

        if task.context:
            messages.append({
                "role": "user",
                "content": f"Additional context: {json.dumps(task.context)}"
            })

        iteration = 0
        final_answer = None
        max_iter = task.max_iterations if task.max_iterations else Config.MAX_ITERATIONS

        logger.info(f"Starting agent run: task_id={task_id}, max_iterations={max_iter}")

        while iteration < max_iter:
            iteration += 1
            logger.info(f"Agent iteration {iteration}/{max_iter}")
            
            # Get LLM response
            response = await self.ollama.chat(
                messages=messages,
                model=Config.MODEL_NAME,
                temperature=Config.DEFAULT_TEMPERATURE
            )
            
            assistant_message = response.get("message", {}).get("content", "")
            steps.append({
                "iteration": iteration,
                "type": "thought",
                "content": assistant_message
            })
            
            messages.append({"role": "assistant", "content": assistant_message})
            
            # Check for final answer
            final_answer = self._check_final_answer(assistant_message)
            if final_answer:
                logger.info("Agent reached final answer")
                break
            
            # Check for action
            action = self._parse_action(assistant_message)
            if action:
                tool_name, arguments = action
                logger.info(f"Executing tool: {tool_name}")
                
                # Execute the tool
                result = await self.tool_executor.execute(tool_name, arguments)
                
                tool_calls.append({
                    "iteration": iteration,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                steps.append({
                    "iteration": iteration,
                    "type": "observation",
                    "content": f"Tool '{tool_name}' returned: {result}"
                })
                
                # Add observation to messages
                messages.append({
                    "role": "user",
                    "content": f"OBSERVATION: {result}"
                })
            else:
                # No action and no final answer - prompt to continue
                messages.append({
                    "role": "user",
                    "content": "Continue with your analysis. Use a tool or provide FINAL ANSWER."
                })
        
        return AgentResponse(
            task_id=task_id,
            status="completed" if final_answer else "max_iterations_reached",
            result=final_answer,
            steps=steps,
            tool_calls=tool_calls,
            total_iterations=iteration
        )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Agentic AI Server",
    description="OpenAI-compatible API with agentic capabilities",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
ollama_client = OllamaClient()
react_agent = ReActAgent()
tool_executor = ToolExecutor()

# Initialize RAG components
# Using a hybrid approach due to local model crashes: alwajeez-finetuned for embeddings, gpt-oss for chat
rag_embeddings = OllamaEmbeddings(
    model="nomic-embed-text", 
    base_url=Config.OLLAMA_BASE_URL
)
rag_vectorstore = Chroma(
    persist_directory=Config.CHROMA_PERSIST_DIR,
    embedding_function=rag_embeddings,
    collection_name="alwajeez_docs",
)
rag_llm = ChatOllama(
    model="gpt-oss:20b-cloud", 
    base_url=Config.OLLAMA_BASE_URL, 
    temperature=0.3
)

# ============================================================
# LANGCHAIN BUILD OUT
# ============================================================

# Wrapping existing ToolExecutor functionalities as LangChain @tools
@tool
def lc_calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Supports basic arithmetic and common functions."""
    return tool_executor._calculator(expression)

@tool
def lc_get_current_time(timezone: str = "Asia/Riyadh") -> str:
    """Get the current date and time for a given timezone."""
    return tool_executor._get_current_time(timezone)

@tool
async def lc_web_search(query: str) -> str:
    """Search the web for current information. Use for real-time data, news, or facts."""
    return await tool_executor._web_search(query)

@tool
async def lc_send_webhook(webhook_name: str, payload: Dict) -> str:
    """Send data to an n8n webhook for workflow automation."""
    return await tool_executor._send_webhook(webhook_name, payload)

@tool
def lc_file_operations(operation: str, path: str, content: str = "") -> str:
    """Read or write files. operation can be 'read', 'write', or 'list'."""
    return tool_executor._file_operations(operation, path, content)

@tool
async def lc_http_request(method: str, url: str, headers: Dict, body: Dict) -> str:
    """Make HTTP requests to external APIs."""
    return await tool_executor._http_request(method, url, headers, body)

@tool
def lc_zatca_compliance(action: str, invoice_data: Dict) -> str:
    """Check ZATCA e-invoice compliance or generate compliant invoices. action can be 'validate', 'generate', 'check_status'."""
    return tool_executor._zatca_compliance(action, invoice_data)

langchain_tools = [
    lc_calculator, lc_get_current_time, lc_web_search, 
    lc_send_webhook, lc_file_operations, lc_http_request, lc_zatca_compliance
]

langchain_llm = ChatOllama(
    model=Config.MODEL_NAME,
    base_url=Config.OLLAMA_BASE_URL,
    temperature=Config.DEFAULT_TEMPERATURE,
)

# Instantiate the ReAct agent with the LangChain tools
langchain_agent = create_react_agent(model=langchain_llm, tools=langchain_tools)

# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Agentic AI Server",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "agent": "/v1/agent/run",
            "langchain_agent": "/v1/langchain/agent/run",
            "tools": "/v1/tools",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{Config.OLLAMA_BASE_URL}/api/tags")
            ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        ollama_status = "unreachable"
    # RAG vector store status
    try:
        rag_status = rag_vectorstore._collection.count()
    except Exception:
        rag_status = 0
    return {
        "status": "healthy",
        "ollama": ollama_status,
        "model": Config.MODEL_NAME,
        "rag_documents": rag_status,
        "timestamp": datetime.now().isoformat()
    }
    """Health check endpoint"""
    try:
        # Check Ollama connection
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{Config.OLLAMA_BASE_URL}/api/tags")
            ollama_status = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        ollama_status = "unreachable"
    
    return {
        "status": "healthy",
        "ollama": ollama_status,
        "model": Config.MODEL_NAME,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{Config.OLLAMA_BASE_URL}/api/tags")
            models = response.json().get("models", [])
            
            return {
                "object": "list",
                "data": [
                    {
                        "id": m["name"],
                        "object": "model",
                        "created": int(datetime.now().timestamp()),
                        "owned_by": "local"
                    }
                    for m in models
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/models/finetune", response_model=FinetuneResponse)
async def finetune_model(request: FinetuneRequest, background_tasks: BackgroundTasks):
    """
    Start a background QLoRA fine-tuning job on the specified base model.
    """
    import uuid
    job_id = str(uuid.uuid4())[:8]
    
    if not os.path.exists(request.dataset_path):
        raise HTTPException(status_code=404, detail=f"Dataset not found: {request.dataset_path}")

    # Queue the fine-tuning job to run in the background
    background_tasks.add_task(run_qlora_finetuning, request, job_id)

    return FinetuneResponse(
        status="accepted",
        job_id=job_id,
        message=f"Fine-tuning job started in the background. Job ID: {job_id}"
    )

@app.post("/v1/models/align", response_model=AlignResponse)
async def align_model(request: AlignRequest, background_tasks: BackgroundTasks):
    """
    Start a background DPO alignment job on the specified base model using preference data.
    """
    import uuid
    job_id = str(uuid.uuid4())[:8]
    
    if not os.path.exists(request.dataset_path):
        raise HTTPException(status_code=404, detail=f"Dataset not found: {request.dataset_path}")

    # Queue the alignment job to run in the background
    background_tasks.add_task(run_dpo_alignment, request, job_id)

    return AlignResponse(
        status="accepted",
        job_id=job_id,
        message=f"DPO alignment job started in the background. Job ID: {job_id}"
    )

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint"""
    
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    response = await ollama_client.chat(
        messages=messages,
        model=request.model,
        temperature=request.temperature
    )
    
    return ChatResponse(
        id=f"chatcmpl-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        created=int(datetime.now().timestamp()),
        model=request.model,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response.get("message", {}).get("content", "")
            },
            "finish_reason": "stop"
        }],
        usage={
            "prompt_tokens": response.get("prompt_eval_count", 0),
            "completion_tokens": response.get("eval_count", 0),
            "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0)
        }
    )


@app.get("/v1/agent/test")
async def test_agent():
    """Test endpoint to verify server is picking up changes"""
    return {"status": "code_updated", "timestamp": datetime.now().isoformat()}


@app.post("/v1/agent/run")
async def run_agent(task: AgentTask):
    """Run the custom ReAct agent on a task"""
    try:
        logger.info(f"Received agent task: {task.task}")
        result = await react_agent.run(task)
        logger.info(f"Agent completed: {result.status}")
        return result
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Agent run error: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}\n{error_trace}")


@app.post("/v1/langchain/agent/run")
async def langchain_agent_run(task: AgentTask):
    """Run a task using the LangChain ReAct agent."""
    import uuid
    task_id = str(uuid.uuid4())[:8]

    try:
        # Note: Depending on the specific usage of the `lc_` tools 
        # that are async, we might need aync invocation support depending
        # on how the agent wraps it natively. Usually invoke handles this for 
        # standard agents, but `.ainvoke()` is the proper async way.
        result = await langchain_agent.ainvoke(
            {"messages": [HumanMessage(content=task.task)]}
        )

        tool_calls_log = []
        steps_log = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # msg.tool_calls is a list of ToolCall dictionaries in LangChain
                for tc in msg.tool_calls:
                    tool_calls_log.append({
                        "tool": tc.get("name", ""),
                        "arguments": tc.get("args", {}),
                    })
            steps_log.append({
                "type": msg.__class__.__name__,
                "content": getattr(msg, "content", "")[:500],
            })

        final_answer = ""
        if result["messages"]:
             final_answer = result["messages"][-1].content
             if not isinstance(final_answer, str):
                 final_answer = str(final_answer)

        return AgentResponse(
            task_id=task_id,
            status="completed",
            result=final_answer,
            steps=steps_log,
            tool_calls=tool_calls_log,
            total_iterations=len(steps_log)
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"LangChain Agent run error: {error_trace}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/tools")
async def list_tools():
    """List available tools"""
    return {
        "tools": [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for name, tool in BUILTIN_TOOLS.items()
        ]
    }


@app.post("/v1/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, arguments: Dict[str, Any]):
    """Execute a specific tool"""
    if tool_name not in BUILTIN_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    result = await tool_executor.execute(tool_name, arguments)
    return {"tool": tool_name, "result": result}


@app.post("/webhook/n8n")
async def n8n_webhook(payload: WebhookPayload):
    """Receive webhooks from n8n"""
    logger.info(f"Received n8n webhook: {payload.event}")
    
    # Process based on event type
    if payload.event == "agent_task":
        task = AgentTask(
            task=payload.data.get("task", ""),
            context=payload.data.get("context"),
            tools=payload.data.get("tools")
        )
        result = await react_agent.run(task)
        return {"status": "processed", "result": result}
    
    return {"status": "received", "event": payload.event}


# ============================================================
# FINE-TUNING SERVICE
# ============================================================

def run_qlora_finetuning(request: FinetuneRequest, job_id: str):
    """
    Background task to run the QLoRA fine-tuning process.
    Loads dataset, configs 4-bit quantization, targets LoRA modules, and runs SFTTrainer.
    """
    print(f"======================= BACKGROUND QLORA START: {job_id} =======================", flush=True)
    logger.info(f"Starting fine-tuning job {job_id} on dataset: {request.dataset_path}")
    try:
        print("Importing torch...", flush=True)
        import torch
        print("Importing datasets...", flush=True)
        from datasets import load_dataset
        print("Importing transformers...", flush=True)
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, prepare_model_for_kbit_training, get_peft_model
        from trl import SFTTrainer, SFTConfig

        # 1. Load and format dataset
        dataset = load_dataset("json", data_files={"train": request.dataset_path})
        
        def format_instruction(example):
            system_msg = (
                "You are Alwajeez AI, a helpful assistant specialized in "
                "ZATCA compliance, Saudi VAT regulations, and the Agentic AI System."
            )
            if example.get("input", ""):
                text = (
                    f"<|system|>\n{system_msg}</s>\n"
                    f"<|user|>\n{example['instruction']}\n{example['input']}</s>\n"
                    f"<|assistant|>\n{example['output']}</s>"
                )
            else:
                text = (
                    f"<|system|>\n{system_msg}</s>\n"
                    f"<|user|>\n{example['instruction']}</s>\n"
                    f"<|assistant|>\n{example['output']}</s>"
                )
            return {"text": text}

        dataset = dataset.map(format_instruction)

        # 2. Configure 4-bit Quantization
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        # 3. Load Base Model
        model = AutoModelForCausalLM.from_pretrained(
            request.base_model,
            quantization_config=bnb_config,
            device_map="auto",
        )
        
        tokenizer = AutoTokenizer.from_pretrained(request.base_model)
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"

        # 4. Prepare for LoRA
        model = prepare_model_for_kbit_training(model)
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)

        # 5. Training Args
        training_args = SFTConfig(
            output_dir=f"./results-{job_id}",
            num_train_epochs=request.epochs,
            per_device_train_batch_size=request.batch_size,
            gradient_accumulation_steps=4,
            learning_rate=request.learning_rate,
            lr_scheduler_type="cosine",
            warmup_ratio=0.1,
            fp16=True,
            logging_steps=5,
            save_strategy="epoch",
            max_seq_length=512,
            dataset_text_field="text",
            report_to="none",
        )

        # 6. Initialize Trainer and Train
        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            tokenizer=tokenizer,
        )
        
        logger.info(f"[{job_id}] SFTTrainer initialized. Starting training...")
        trainer.train()

        # 7. Save Adapter and Merge
        adapter_path = f"./adapter-{job_id}"
        trainer.save_model(adapter_path)
        tokenizer.save_pretrained(adapter_path)
        
        # Free memory and reload for merging
        del model
        del trainer
        torch.cuda.empty_cache()
        
        from peft import AutoPeftModelForCausalLM
        
        logger.info(f"[{job_id}] Merging LoRA adapter with base model...")
        peft_model = AutoPeftModelForCausalLM.from_pretrained(
            adapter_path,
            device_map="auto",
            torch_dtype=torch.float16,
        )
        merged_model = peft_model.merge_and_unload()
        merged_model.save_pretrained(request.output_dir)
        tokenizer.save_pretrained(request.output_dir)
        
        # Clean up temporary adapter if desired
        try:
             import shutil
             shutil.rmtree(adapter_path)
             shutil.rmtree(f"./results-{job_id}")
        except Exception as e:
             logger.warning(f"Could not clean up temporary directories: {e}")

        logger.info(f"[{job_id}] Fine-tuning complete. Merged model saved to {request.output_dir}")

    except Exception as e:
        logger.error(f"[{job_id}] Fine-tuning failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def run_dpo_alignment(request: AlignRequest, job_id: str):
    """
    Background task to run the DPO alignment process.
    Loads preference dataset, configs 4-bit, targets LoRA modules, and runs DPOTrainer.
    """
    print(f"======================= BACKGROUND DPO START: {job_id} =======================", flush=True)
    logger.info(f"Starting DPO alignment job {job_id} on dataset: {request.dataset_path}")
    try:
        print("Importing torch...", flush=True)
        import torch
        print("Importing datasets...", flush=True)
        from datasets import load_dataset
        print("Importing transformers...", flush=True)
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, prepare_model_for_kbit_training
        from trl import DPOTrainer, DPOConfig
        
        # 1. Load and format dataset
        dataset = load_dataset("json", data_files={"train": request.dataset_path})
        
        def format_for_dpo(example):
            formatted_prompt = (
                f"<|system|>\n"
                f"You are Alwajeez AI, a helpful assistant for Alwajeez Tech's Agentic AI System. "
                f"You provide accurate, specific, and well-structured answers about ZATCA compliance, "
                f"VAT regulations, and the system's technical architecture.</s>\n"
                f"<|user|>\n"
                f"{example['prompt']}</s>\n"
                f"<|assistant|>\n"
            )
            return {
                "prompt": formatted_prompt,
                "chosen": example["chosen"],
                "rejected": example["rejected"],
            }
        
        dpo_dataset = dataset.map(format_for_dpo)
        train_dataset = dpo_dataset["train"]

        # 2. Configure 4-bit Quantization
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        # 3. Load Model (Policy) - DPOTrainer automatically uses base weights as Reference Model for PEFT
        model = AutoModelForCausalLM.from_pretrained(
            request.base_model,
            quantization_config=bnb_config,
            device_map="auto",
        )
        
        tokenizer = AutoTokenizer.from_pretrained(request.base_model)
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "left" # DPO prefers left-padding

        # 4. Prepare for LoRA
        model = prepare_model_for_kbit_training(model)
        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )

        # 5. Training Args
        dpo_config = DPOConfig(
            output_dir=f"./dpo-results-{job_id}",
            num_train_epochs=request.epochs,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=request.learning_rate,
            lr_scheduler_type="cosine",
            warmup_ratio=0.1,
            fp16=True,
            logging_steps=2,
            save_strategy="epoch",
            beta=request.beta,
            max_length=512,
            max_prompt_length=256,
            remove_unused_columns=False,
            report_to="none",
        )

        # 6. Initialize Trainer and Train
        dpo_trainer = DPOTrainer(
            model=model,
            args=dpo_config,
            train_dataset=train_dataset,
            tokenizer=tokenizer,
            peft_config=peft_config,
        )
        
        logger.info(f"[{job_id}] DPOTrainer initialized. Starting DPO training...")
        dpo_trainer.train()

        # 7. Save Adapter
        adapter_path = f"./dpo-adapter-{job_id}"
        dpo_trainer.save_model(adapter_path)
        tokenizer.save_pretrained(adapter_path)
        
        # Clean up temporary results if desired
        try:
             import shutil
             shutil.rmtree(f"./dpo-results-{job_id}")
        except Exception as e:
             logger.warning(f"Could not clean up temporary directories: {e}")

        logger.info(f"[{job_id}] DPO alignment complete. LoRA adapter saved to {adapter_path}")

    except Exception as e:
        logger.error(f"[{job_id}] DPO alignment failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

# ============================================================
# RAG ENDPOINTS
# ============================================================

@app.post("/rag/ingest", response_model=RagIngestResponse)
async def rag_ingest(request: RagIngestRequest):
    """Ingest a document: load, chunk, embed, and store in ChromaDB."""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    try:
        chunks = _load_and_chunk(
            request.file_path, 
            chunk_size=request.chunk_size, 
            chunk_overlap=request.chunk_overlap
        )
        
        # Add chunks one by one to prevent Ollama batch processing crashes
        for i, chunk in enumerate(chunks):
            rag_vectorstore.add_documents([chunk])
            logger.info(f"Ingested chunk {i+1}/{len(chunks)}")
        
        return RagIngestResponse(
            status="success",
            file_path=request.file_path,
            chunks_added=len(chunks),
            total_documents=rag_vectorstore._collection.count(),
        )
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/query", response_model=RagQueryResponse)
async def rag_query(request: RagQueryRequest):
    """Query the RAG pipeline: retrieve relevant chunks and generate answer."""
    try:
        # We need to gracefully handle if collection is empty
        if rag_vectorstore._collection.count() == 0:
             raise HTTPException(
                status_code=400,
                detail="No documents in the knowledge base. Ingest documents first.",
            )
            
        retriever = rag_vectorstore.as_retriever(search_kwargs={"k": request.k})
        
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant for Alwajeez Tech. Answer the question based only
on the provided context. If the context does not contain enough information,
say "I don't have enough information to answer that."

Context:
{context}

Question: {question}

Answer:"""
        )

        chain = (
            {"context": retriever | _format_docs, "question": RunnablePassthrough()}
            | prompt
            | rag_llm
            | StrOutputParser()
        )

        answer = chain.invoke(request.question)

        # Retrieve source documents for transparency
        source_docs = retriever.invoke(request.question)
        sources = [
            {
                "content": doc.page_content[:200],
                "source": doc.metadata.get("source", "unknown"),
            }
            for doc in source_docs
        ]

        return RagQueryResponse(
            question=request.question,
            answer=answer,
            sources=sources,
            event="query",
            data={"status": "success"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║              AGENTIC AI SERVER STARTING                      ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "agentic_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
