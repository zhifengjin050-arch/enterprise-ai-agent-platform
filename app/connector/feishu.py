"""Feishu/Lark Cloud Document connector.

Fetches documents from Feishu knowledge bases using the Feishu Open API.
Supports token acquisition, knowledge base listing, document listing,
document content reading, and Markdown conversion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability
from app.connector.exceptions import AuthenticationError, ConnectionError, NotFoundError
from app.connector.sync_modes import SyncResult


def _extract_block_text(block: Any, lines: List[str]) -> None:
    """Recursively extract text from a Feishu block structure."""
    if not isinstance(block, dict):
        return
    block_type = block.get("block_type", "")
    text_elements: List[str] = []

    for key in ("text", "title", "heading", "body", "content"):
        val = block.get(key, {})
        if isinstance(val, dict):
            elements = val.get("elements", []) or val.get("text_elements", [])
            for elem in elements if isinstance(elements, list) else [elements]:
                if isinstance(elem, dict):
                    text_run = elem.get("text_run", {}) or elem.get("text", {})
                    if isinstance(text_run, dict):
                        content = text_run.get("content", "")
                        if content:
                            text_elements.append(content)

    if text_elements:
        prefix = ""
        if block_type in ("heading1", "heading2", "heading3"):
            level = block_type[-1]
            prefix = "#" * int(level) + " "
        elif block_type in ("bullet", "ordered"):
            prefix = "- "
        lines.append(f"{prefix}{' '.join(text_elements)}")

    for child in block.get("children", []):
        _extract_block_text(child, lines)


def _convert_to_markdown(raw_content: str, title: str) -> str:
    """Convert Feishu raw content to basic Markdown.

    Args:
        raw_content: Raw content string from Feishu API.
        title: Document title.

    Returns:
        Markdown-formatted content.
    """
    if not raw_content:
        return f"# {title}\n\n*(Empty document)*"

    lines: List[str] = [f"# {title}", ""]
    try:
        import json

        blocks = json.loads(raw_content)
        if isinstance(blocks, dict):
            text = blocks.get("text", "")
            if text:
                lines.append(text)
            else:
                block_list = blocks.get("blocks", [])
                for block in block_list if isinstance(block_list, list) else [block_list]:
                    _extract_block_text(block, lines)
        elif isinstance(blocks, str):
            lines.append(blocks)
        else:
            lines.append(str(raw_content)[:50000])
    except (json.JSONDecodeError, TypeError):
        lines.append(str(raw_content)[:50000])

    return "\n".join(lines)


class FeishuConnector(BaseConnector):
    """Connector for Feishu (Lark) Cloud Documents.

    Requires config:
        - app_id: Feishu Open API App ID.
        - app_secret: Feishu Open API App Secret.
        - base_url: Optional custom base URL (default: https://open.feishu.cn).
    """

    name: str = "Feishu"
    connector_type: str = "feishu"
    version: str = "1.0.0"
    author: str = "Enterprise AI Knowledge Copilot"
    description: str = "Feishu/Lark Cloud Document and Wiki connector"
    capabilities: List[ConnectorCapability] = [
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.SEARCH,
        ConnectorCapability.FULL_SYNC,
        ConnectorCapability.INCREMENTAL_SYNC,
    ]
    features: List[str] = ["document", "wiki", "search"]
    config_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "app_id": {"type": "string", "description": "Feishu Open App ID"},
            "app_secret": {"type": "string", "description": "Feishu Open App Secret"},
            "tenant_key": {"type": "string", "description": "Tenant access token (optional)"},
            "base_url": {"type": "string", "description": "Custom base URL (optional)"},
        },
        "required": ["app_id", "app_secret"],
    }

    FEISHU_BASE_URL = "https://open.feishu.cn"
    AUTH_ENDPOINT = "/open-apis/auth/v3/tenant_access_token/internal"
    KB_LIST_ENDPOINT = "/open-apis/wiki/v2/space"
    DOC_LIST_ENDPOINT = "/open-apis/wiki/v2/space/{space_id}/node"
    DOC_CONTENT_ENDPOINT = "/open-apis/docx/v1/documents/{document_id}/raw_content"

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(config=config)
        self._base_url: str = (self._config or {}).get("base_url", self.FEISHU_BASE_URL)
        self._app_id: str = (self._config or {}).get("app_id", "")
        self._app_secret: str = (self._config or {}).get("app_secret", "")
        self._token: str = ""
        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        """Obtain a tenant access token from Feishu Open API.

        Returns:
            Access token string.

        Raises:
            AuthenticationError: If app_id/app_secret are invalid.
            ConnectionError: If the API is unreachable.
        """
        if self._token and self._token_expires_at > datetime.now(timezone.utc).timestamp():
            return self._token

        if not self._app_id or not self._app_secret:
            raise AuthenticationError(
                source="Feishu",
                detail="app_id and app_secret are required",
            )

        url = f"{self._base_url}{self.AUTH_ENDPOINT}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    json={"app_id": self._app_id, "app_secret": self._app_secret},
                )
                if resp.status_code != 200:
                    raise AuthenticationError(
                        source="Feishu",
                        detail=f"Auth API returned {resp.status_code}: {resp.text[:200]}",
                    )
                data = resp.json()
                if data.get("code") != 0:
                    raise AuthenticationError(
                        source="Feishu",
                        detail=f"Auth failed: {data.get('msg', 'unknown')}",
                    )
                self._token = data.get("tenant_access_token", "")
                expire = data.get("expire", 7200)
                self._token_expires_at = datetime.now(timezone.utc).timestamp() + expire - 60
                return self._token
        except httpx.TimeoutException as exc:
            raise ConnectionError(source="Feishu", detail=f"Timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(source="Feishu", detail=str(exc)) from exc

    async def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Make an authenticated request to the Feishu API.

        Args:
            method: HTTP method.
            path: API path (e.g., /open-apis/wiki/v2/space).
            **kwargs: Additional httpx request params.

        Returns:
            Parsed JSON response.

        Raises:
            ConnectionError: On network error.
            AuthenticationError: On 401.
        """
        token = await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        url = f"{self._base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                if resp.status_code == 401:
                    self._token = ""
                    raise AuthenticationError(source="Feishu", detail="Token expired or invalid")
                if resp.status_code >= 400:
                    raise ConnectionError(
                        source="Feishu",
                        detail=f"API {resp.status_code}: {resp.text[:300]}",
                    )
                data = resp.json()
                if data.get("code") != 0:
                    raise ConnectionError(
                        source="Feishu",
                        detail=f"API error: {data.get('msg', 'unknown')} (code={data.get('code')})",
                    )
                return data
        except httpx.TimeoutException as exc:
            raise ConnectionError(source="Feishu", detail=f"Timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(source="Feishu", detail=str(exc)) from exc

    async def test_connection(self) -> bool:
        """Test connectivity by obtaining an access token.

        Returns:
            True if connection succeeds.
        """
        try:
            await self._get_access_token()
            return True
        except (AuthenticationError, ConnectionError):
            return False

    async def _list_knowledge_bases(self) -> List[Dict[str, Any]]:
        """List all accessible Feishu wiki/knowledge spaces.

        Returns:
            List of space dicts with `space_id` and `name`.
        """
        data = await self._request("GET", self.KB_LIST_ENDPOINT)
        items = data.get("data", {}).get("items", [])
        return [
            {
                "space_id": item.get("space_id", ""),
                "name": item.get("name", ""),
            }
            for item in items
        ]

    async def _list_space_nodes(self, space_id: str) -> List[Dict[str, Any]]:
        """List wiki nodes (documents) in a space.

        Args:
            space_id: The Feishu space ID.

        Returns:
            List of node dicts with `node_token`, `title`, `obj_type`.
        """
        path = self.DOC_LIST_ENDPOINT.format(space_id=space_id)
        all_nodes: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            params: Dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            data = await self._request("GET", path, params=params)
            items = data.get("data", {}).get("items", [])
            for item in items:
                obj_type = item.get("obj_type", "")
                if obj_type in ("doc", "docx"):
                    all_nodes.append(
                        {
                            "node_token": item.get("node_token", ""),
                            "title": item.get("title", "Untitled"),
                            "obj_type": obj_type,
                        }
                    )
            page_token = data.get("data", {}).get("page_token")
            has_more = data.get("data", {}).get("has_more", False)
            if not has_more or not page_token:
                break

        return all_nodes

    async def _fetch_raw_content(self, document_id: str) -> str:
        """Fetch the raw content of a Feishu document.

        Args:
            document_id: The document's token/node_token.

        Returns:
            Raw document content as text.

        Raises:
            NotFoundError: If the document does not exist.
        """
        path = self.DOC_CONTENT_ENDPOINT.format(document_id=document_id)
        try:
            data = await self._request("GET", path)
            return data.get("data", {}).get("content", "")
        except ConnectionError as exc:
            if "404" in str(exc) or "not found" in str(exc).lower():
                raise NotFoundError(resource=f"Document {document_id}", source="Feishu") from exc
            raise

    async def fetch_documents(self) -> List[ConnectorDocument]:
        """Fetch all documents from all accessible Feishu knowledge bases.

        Returns:
            List of ConnectorDocument with metadata (no full content).

        Raises:
            AuthenticationError: If app_id/app_secret are not configured.
        """
        if not self._app_id or not self._app_secret:
            raise AuthenticationError(source="Feishu", detail="app_id and app_secret are required")
        documents: List[ConnectorDocument] = []
        spaces = await self._list_knowledge_bases()

        for space in spaces:
            space_id = space["space_id"]
            try:
                nodes = await self._list_space_nodes(space_id)
            except (ConnectionError, AuthenticationError):
                continue

            host = self._base_url.replace("https://", "").replace("http://", "")
            for node in nodes:
                documents.append(
                    ConnectorDocument(
                        id=node["node_token"],
                        title=node["title"],
                        content="",
                        url=f"https://{host}/wiki/{space_id}/{node['node_token']}",
                        updated_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "space_id": space_id,
                            "space_name": space["name"],
                            "obj_type": node.get("obj_type", "docx"),
                            "connector_type": "feishu",
                        },
                    )
                )

        return documents

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        """Fetch a single Feishu document with full content.

        Args:
            document_id: The node token.

        Returns:
            ConnectorDocument with content, or None.
        """
        try:
            raw_content = await self._fetch_raw_content(document_id)
            title = f"Feishu Document {document_id}"
            markdown = _convert_to_markdown(raw_content, title)
            host = self._base_url.replace("https://", "").replace("http://", "")
            return ConnectorDocument(
                id=document_id,
                title=title,
                content=markdown,
                url=f"https://{host}/wiki/{document_id}",
                updated_at=datetime.now(timezone.utc).isoformat(),
                metadata={"connector_type": "feishu"},
            )
        except (NotFoundError, ConnectionError):
            return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> SyncResult:
        """Sync Feishu documents with optional incremental filtering.

        Args:
            sync_mode: "full" (all documents) or "incremental" (since last cursor).
            cursor: Optional ISO timestamp; documents with updated_at <= cursor are skipped.

        Returns:
            SyncResult with documents and next_cursor checkpoint.
        """
        documents = await self.fetch_documents()
        full_documents: List[ConnectorDocument] = []

        for doc in documents:
            # Incremental: skip documents not newer than cursor
            if sync_mode == "incremental" and cursor and doc.updated_at:
                if doc.updated_at <= cursor:
                    continue
            try:
                raw_content = await self._fetch_raw_content(doc.id)
                markdown = _convert_to_markdown(raw_content, doc.title)
                full_doc = ConnectorDocument(
                    id=doc.id,
                    title=doc.title,
                    content=markdown,
                    url=doc.url,
                    updated_at=doc.updated_at,
                    metadata=doc.metadata,
                )
                full_documents.append(full_doc)
            except (NotFoundError, ConnectionError):
                continue

        # next_cursor = max updated_at among synced docs
        next_cursor: Optional[str] = cursor
        for doc in full_documents:
            if doc.updated_at and (next_cursor is None or doc.updated_at > next_cursor):
                next_cursor = doc.updated_at

        return SyncResult.from_documents(
            full_documents,
            next_cursor=next_cursor,
            has_more=False,
        )
