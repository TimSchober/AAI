"""
Helpers for connecting agents to the MCP server and loading its tools as LangChain tools.
"""

from __future__ import annotations

from langchain_mcp_adapters.client import MultiServerMCPClient

from config import MCP_URL


def build_mcp_client(url: str = MCP_URL) -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "jobboard": {
                "url": url,
                "transport": "streamable_http",
            }
        }
    )


async def load_mcp_tools(url: str = MCP_URL):
    client = build_mcp_client(url)
    return await client.get_tools()
