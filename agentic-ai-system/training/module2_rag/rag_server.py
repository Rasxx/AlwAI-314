"""RAG Server -- Standalone FastAPI endpoint for RAG queries.

Run with: uvicorn rag_server:app --port 8001 --reload
"""

import os
import shutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


# --- Configuration ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
COLLECTION_NAME = "alwajeez_docs"

# --- Initialize components ---
embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.3)

# Load or create vector store
vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)

# --- Pydantic models ---
class IngestRequest(BaseModel):
    file_path: str
    chunk_size: int = 500
    chunk_overlap: int = 100


class IngestResponse(BaseModel):
    status: str
    file_path: str
    chunks_added: int
    total_documents: int


class QueryRequest(BaseModel):
    question: str
    k: int = 4


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]


# --- Helper functions ---
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


# --- FastAPI app ---
app = FastAPI(
    title="RAG Server",
    description="Retrieval-Augmented Generation API for Alwajeez Tech",
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model": OLLAMA_MODEL,
        "documents": vectorstore._collection.count(),
    }


@app.post("/rag/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Ingest a document: load, chunk, embed, and store in ChromaDB."""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    # Choose loader based on file extension
    if request.file_path.endswith(".pdf"):
        loader = PyPDFLoader(request.file_path)
    else:
        loader = TextLoader(request.file_path, encoding="utf-8")

    documents = loader.load()

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
    chunks = splitter.split_documents(documents)

    # Add to vector store
    vectorstore.add_documents(chunks)

    return IngestResponse(
        status="success",
        file_path=request.file_path,
        chunks_added=len(chunks),
        total_documents=vectorstore._collection.count(),
    )


@app.post("/rag/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Query the RAG pipeline: retrieve relevant chunks and generate answer."""
    if vectorstore._collection.count() == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents in the knowledge base. Ingest documents first.",
        )

    # Build the chain
    retriever = vectorstore.as_retriever(search_kwargs={"k": request.k})

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
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    answer = chain.invoke(request.question)

    # Also retrieve source documents for transparency
    source_docs = retriever.invoke(request.question)
    sources = [
        {
            "content": doc.page_content[:200],
            "source": doc.metadata.get("source", "unknown"),
        }
        for doc in source_docs
    ]

    return QueryResponse(
        question=request.question,
        answer=answer,
        sources=sources,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rag_server:app", host="0.0.0.0", port=8001, reload=True)
