"""
Helpers for connecting agents to the MCP server and loading its tools as LangChain tools.
"""

from __future__ import annotations

from langchain_mcp_adapters.client import MultiServerMCPClient

import config


def build_mcp_client(url: str = "") -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "jobboard": {
                "url": url or config.MCP_URL,
                "transport": "streamable_http",
            }
        }
    )


async def load_mcp_tools(url: str = ""):
    client = build_mcp_client(url)
    return await client.get_tools()
