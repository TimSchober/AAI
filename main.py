#!/usr/bin/env python3
"""
Hybrid entry point: RAG API + Job Search Agent in one project
Usage:
  python main.py                    # Start FastAPI server
  python main.py --cli              # Start CLI agent
  python -m mcp_server              # Start MCP server (for agents)
  python -m ingest                  # Ingest documents into ChromaDB
"""

import sys
import logging
import asyncio
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_api():
    """Start FastAPI RAG server"""
    logger.info("🚀 Starting RAG API Server...")
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from api.rag_routes import setup_rag_routes
    import uvicorn
    from config import API_HOST, API_PORT, API_RELOAD
    
    app = FastAPI(
        title="Multimodal RAG Agent + Job Search API",
        description="Combined RAG API and Job Agent Platform"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register RAG routes
    setup_rag_routes(app)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "Multimodal RAG Agent + Job Search",
            "version": "1.0",
            "endpoints": {
                "health": "/health",
                "ingest": "/ingest",
                "query": "/query",
                "documents": "/documents",
                "rebuild_index": "/rebuild-index",
            },
            "docs": "/docs"
        }
    
    logger.info(f"📡 API running on {API_HOST}:{API_PORT}")
    logger.info(f"📖 Docs available at http://{API_HOST}:{API_PORT}/docs")
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD,
        log_level="info"
    )

async def start_cli():
    """Start Job Search Agent CLI"""
    logger.info("🤖 Starting Job Search Agent CLI...")
    
    from rich.console import Console
    from agents.job_search_agent import build_job_search_agent
    
    console = Console()
    
    # Check Ollama
    def _check_ollama() -> tuple[bool, str]:
        try:
            import httpx
            from config import OLLAMA_BASE_URL, OLLAMA_MODEL
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if resp.status_code != 200:
                    return False, f"Ollama responded with status {resp.status_code}"
                names = [m["name"] for m in resp.json().get("models", [])]
                if OLLAMA_MODEL in names:
                    return True, f"Ollama reachable, model '{OLLAMA_MODEL}' loaded."
                return False, f"Ollama reachable but model '{OLLAMA_MODEL}' not loaded."
        except Exception as exc:
            return False, f"Cannot connect to Ollama: {exc}"
    
    def _check_mcp() -> tuple[bool, str]:
        try:
            import httpx
            from config import MCP_URL
            base = MCP_URL.rsplit("/", 1)[0]
            with httpx.Client(timeout=5) as client:
                client.get(base)
            return True, f"MCP server reachable at {MCP_URL}."
        except Exception as exc:
            return False, f"Cannot reach the MCP server: {exc}"
    
    # Check requirements
    console.print("\n[cyan]⏳ Checking requirements...[/cyan]")
    
    ollama_ok, ollama_msg = _check_ollama()
    console.print(f"  Ollama: {'✅' if ollama_ok else '❌'} {ollama_msg}")
    
    mcp_ok, mcp_msg = _check_mcp()
    console.print(f"  MCP:    {'✅' if mcp_ok else '⚠️'} {mcp_msg}")
    
    if not ollama_ok:
        console.print("\n[red]❌ Ollama is required. Please start it:[/red]")
        console.print("   ollama serve")
        return
    
    if not mcp_ok:
        console.print("\n[yellow]⚠️  MCP server not running. Start it in another terminal:[/yellow]")
        console.print("   python -m mcp_server")
        console.print("\n[cyan]Continuing without MCP...[/cyan]\n")
    
    # Build and run agent
    console.print("\n[green]✅ Starting agent CLI...[/green]\n")
    agent = build_job_search_agent()
    
    # Interactive loop
    console.print("[cyan]Type 'exit' or 'quit' to exit[/cyan]\n")
    
    while True:
        try:
            user_input = console.input("[blue]You:[/blue] ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Goodbye! 👋[/yellow]")
                break
            
            if not user_input:
                continue
            
            console.print("[cyan]Agent is thinking...[/cyan]")
            result = await agent.ainvoke({"messages": [user_input]})
            
            if result and "messages" in result:
                agent_msg = result["messages"][-1]
                content = agent_msg.content if hasattr(agent_msg, 'content') else str(agent_msg)
                console.print(f"\n[green]Agent:[/green] {content}\n")
            else:
                console.print(f"\n[green]Agent:[/green] {result}\n")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Goodbye! 👋[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        # Start CLI agent
        asyncio.run(start_cli())
    else:
        # Default: Start FastAPI server
        start_api()

if __name__ == "__main__":
    main()
