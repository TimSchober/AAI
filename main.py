#!/usr/bin/env python3
"""
CLI entry point: chat with the job-search agent.
"""

from __future__ import annotations

import asyncio

import httpx
from rich.console import Console
from rich.markdown import Markdown

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    MCP_URL,
    JOBSUCHE_API_KEY,
)
from agents.job_search_agent import build_job_search_agent


console = Console()


def _check_ollama() -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code != 200:
                return False, f"Ollama responded with status {resp.status_code}"
            names = [m["name"] for m in resp.json().get("models", [])]
            if OLLAMA_MODEL in names:
                return True, f"Ollama reachable, model '{OLLAMA_MODEL}' loaded."
            return False, f"Ollama reachable but model '{OLLAMA_MODEL}' not loaded."
    except httpx.ConnectError:
        return False, f"Cannot connect to Ollama at {OLLAMA_BASE_URL}."
    except Exception as exc:
        return False, f"Ollama check failed: {exc}"


def _check_mcp() -> tuple[bool, str]:
    base = MCP_URL.rsplit("/", 1)[0]
    try:
        with httpx.Client(timeout=5) as client:
            client.get(base)
        return True, f"MCP server reachable at {MCP_URL}."
    except httpx.ConnectError:
        return False, f"Cannot reach the MCP server at {MCP_URL}."
    except Exception:
        return True, f"MCP server reachable at {MCP_URL}."


async def chat() -> None:
    console.rule("Job-Such-Agent")
    console.print(
        f"LLM: [bold]{OLLAMA_MODEL}[/bold] - MCP: [bold]{MCP_URL}[/bold]\n"
    )

    if not JOBSUCHE_API_KEY:
        console.print("[yellow]Warnung: JOBSUCHE_API_KEY ist leer.[/yellow]")

    ok, msg = _check_ollama()
    console.print(f"[{'green' if ok else 'yellow'}]{msg}[/]")
    ok_mcp, msg_mcp = _check_mcp()
    console.print(f"[{'green' if ok_mcp else 'red'}]{msg_mcp}[/]\n")
    if not ok_mcp:
        console.print("[red]Bitte zuerst den MCP-Server starten.[/red]")
        return

    console.print("[dim]Verbinde mit den MCP-Tools …[/dim]")
    agent = await build_job_search_agent()
    config = {"configurable": {"thread_id": "job-search"}}

    console.print(
        "[dim]Chat gestartet. 'quit' zum Beenden.[/dim]\n"
    )

    while True:
        try:
            user_input = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[green]Auf Wiedersehen![/green]")
            return
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "beenden", "q"):
            console.print("[green]Auf Wiedersehen![/green]")
            return

        console.print("[dim]Agent arbeitet …[/dim]")
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
            )
            answer = result["messages"][-1].content
            console.print()
            console.print(Markdown(answer or "(keine Antwort)"))
            console.print()
        except Exception as exc:
            console.print(f"[red]Fehler: {exc}[/red]\n")


def main() -> None:
    asyncio.run(chat())


if __name__ == "__main__":
    main()
