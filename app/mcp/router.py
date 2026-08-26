"""REST API for MCP tool status and discovery.

Exposes endpoints for the frontend / monitoring to inspect which MCP
servers are registered and which tools have been discovered.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.mcp.registry import get_mcp_adapter_registry

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/tools")
async def list_mcp_tools():
    """List all discovered MCP tools across all registered servers."""
    registry = get_mcp_adapter_registry()
    names = registry.list_adapter_names()
    return {"tools": names, "count": len(names)}


@router.get("/servers")
async def list_mcp_servers():
    """List registered MCP server names."""
    registry = get_mcp_adapter_registry()
    return {"servers": list(registry._clients.keys())}
