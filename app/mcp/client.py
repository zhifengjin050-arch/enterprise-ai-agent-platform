"""HTTP client for remote MCP tool servers.

Communicates with any MCP-compatible HTTP API (e.g. the Enterprise DevOps MCP server)
to discover and invoke remote infrastructure tools (Docker, K8s, SSH, health, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Async HTTP client for a remote MCP tool server.

    Usage:
        client = MCPClient("http://mcp.internal:8080", api_key="...")
        tools = await client.list_tools()
        result = await client.execute_tool("k8s_get_pods", {"namespace": "default"})
        await client.close()
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """GET /tools -> list of {name, description, input_schema}.

        Returns an empty list on any error (connection, timeout, HTTP error)
        so the caller can gracefully skip unavailable servers.
        """
        headers = self._get_headers()
        try:
            resp = await self._client.get(f"{self.base_url}/tools", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            # The server may return a list directly or wrap it in {"tools": [...]}
            if isinstance(data, list):
                return data
            return data.get("tools", []) if isinstance(data, dict) else []
        except httpx.TimeoutException:
            logger.warning("MCP list_tools timed out for %s", self.base_url)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                "MCP list_tools HTTP %s from %s",
                e.response.status_code,
                self.base_url,
            )
            return []
        except Exception as e:
            logger.warning("MCP list_tools failed for %s: %s", self.base_url, e)
            return []

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /tools/{name}/execute -> result dict.

        Returns a dict with either the result payload or an ``error`` key
        on failure so the caller does not have to catch exceptions from
        the HTTP layer.
        """
        headers = self._get_headers()
        if identity:
            if identity.get("tenant_id"):
                headers["X-Tenant-ID"] = str(identity["tenant_id"])
            if identity.get("user_id"):
                headers["X-User-ID"] = str(identity["user_id"])
                headers["X-Employee-ID"] = str(identity["user_id"])
            if identity.get("organization_id"):
                headers["X-Organization-ID"] = str(identity["organization_id"])
        url = f"{self.base_url}/tools/{name}/execute"
        try:
            resp = await self._client.post(url, json=arguments, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.warning("MCP execute_tool timed out: %s/%s", self.base_url, name)
            return {"error": f"Request timed out for tool '{name}'"}
        except httpx.HTTPStatusError as e:
            logger.warning(
                "MCP execute_tool HTTP %s: %s/%s",
                e.response.status_code,
                self.base_url,
                name,
            )
            detail: Dict[str, Any] = {}
            try:
                detail = e.response.json()
            except Exception:
                detail = {"status_code": e.response.status_code}
            return {"error": f"HTTP {e.response.status_code}", "detail": detail}
        except Exception as e:
            logger.warning("MCP execute_tool failed: %s/%s: %s", self.base_url, name, e)
            return {"error": str(e)}

    async def health(self) -> bool:
        """GET /health -> True if the server responds with 200."""
        try:
            resp = await self._client.get(f"{self.base_url}/health", headers=self._get_headers())
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
