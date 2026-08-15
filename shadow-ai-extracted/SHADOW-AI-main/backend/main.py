from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.ai_router import AIRouter
from core.code_validator import CodeValidator
from core.research_engine import ResearchEngine
from core.persona import Persona
from core.memory_client import MemoryClient

app = FastAPI(title="Shadow AI Agent", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai = AIRouter()
research = ResearchEngine()
validator = CodeValidator()
persona = Persona()
memory = MemoryClient()


class HistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[HistoryItem] = Field(default_factory=list)
    deep_search: bool = False
    royal_mode: bool = False
    memory_context: str = ""
    user_id: str = "default"


@app.get("/")
def root():
    return {
        "status": "Shadow AI Agent operational",
        "version": "3.0",
        "ai": ai.status(),
        "research": research.terminal_status(),
        "endpoints": ["/", "/health", "/chat", "/research", "/tools"]
    }


@app.get("/health")
def health():
    return {"status": "ok", "ai": ai.status()}


@app.get("/tools")
def tools():
    return {"terminal_tools": research.terminal_status()}


@app.post("/research")
def research_endpoint(req: Dict):
    query = str(req.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    evidence, sources = research.research(query)
    return {"query": query, "evidence": evidence, "sources": sources}


@app.post("/chat")
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    history = [item.model_dump() for item in req.history[-20:]]
    needs_research = req.deep_search or any(
        token in message.lower()
        for token in ["search", "research", "latest", "current", "compare", "sources", "look up", "find out"]
    )

    evidence = req.memory_context.strip()
    sources = []

    # Long-term memory is optional. The main backend remains fully functional
    # if Backend 2 is offline.
    memories = memory.search(req.user_id, message) if memory.enabled() else []
    if memories:
        memory_text = "\n".join(f"- {m.get('content', '')}" for m in memories[:8])
        evidence = f"LONG-TERM MEMORY:\n{memory_text}\n\n{evidence}".strip()

    if needs_research:
        research_evidence, sources = research.research(message)
        if research_evidence:
            evidence = f"{evidence}\n\n{research_evidence}".strip() if evidence else research_evidence
        domain_data = research.domain_tools(message)
        if domain_data:
            extra = "\n\n".join(
                f"[{x['source']}] {x['title']}\n{x['text']}" for x in domain_data
            )
            evidence = f"{evidence}\n\n{extra}" if evidence else extra
            sources.extend(domain_data)

    result = ai.answer(
        message=message,
        history=history,
        research=evidence,
        royal_mode=req.royal_mode,
        deep_search=needs_research,
    )

    response = result.get("response")
    if not response:
        response = (
            "I can receive your message, but no AI provider is configured or available right now. "
            "Set OPENAI_API_KEY and/or ANTHROPIC_API_KEY on Railway."
        )

    # Validate code blocks without modifying normal prose.
    try:
        response = validator.validate_code_blocks(response)
    except Exception:
        pass

    # Keep the external conversation archive in Backend 2 when configured.
    if memory.enabled():
        memory.save_message(req.user_id, "user", message)
        memory.save_message(req.user_id, "assistant", response)
        lower = message.lower()
        explicit_memory = any(x in lower for x in ["remember that", "remember this", "don't forget", "do not forget", "my goal is", "my favorite is"])
        if explicit_memory:
            memory.save(req.user_id, message, importance=5)

    return {
        "response": response,
        "mode": result.get("mode", "unknown"),
        "providers": result.get("providers", []),
        "sources_count": len(sources),
        "sources": [
            {"title": x.get("title", "Source"), "url": x.get("url", ""), "source": x.get("source", "")}
            for x in sources[:8]
        ],
        "researched": bool(needs_research),
    }
