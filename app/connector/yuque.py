"""Yuque (语雀) Knowledge Base connector.

Fetches documents from Yuque knowledge repositories using the Yuque API.
Supports repository listing, document listing, and Markdown content retrieval.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability
from app.connector.exceptions import AuthenticationError, ConnectionError, NotFoundError
from app.connector.sync_modes import SyncResult


class YuqueConnector(BaseConnector):
    """Connector for Yuque (语雀) Knowledge Repositories.

    Requires config:
        - token: Yuque API token (personal access token).
        - base_url: Optional custom base URL (default: https://www.yuque.com/api/v2).
        - namespace: Optional specific namespace to sync (e.g., "org/repo").
    """

    name: str = "Yuque"
    connector_type: str = "yuque"
    version: str = "1.0.0"
    author: str = "Enterprise AI Knowledge Copilot"
    description: str = "Yuque (语雀) Knowledge Repository connector"
    capabilities: List[ConnectorCapability] = [
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.SEARCH,
        ConnectorCapability.FULL_SYNC,
        ConnectorCapability.INCREMENTAL_SYNC,
    ]
    features: List[str] = ["document", "repository"]

    YUQUE_BASE_URL = "https://www.yuque.com/api/v2"
    USER_ENDPOINT = "/user"
    REPOS_ENDPOINT = "/users/{login}/repos"
    ORG_REPOS_ENDPOINT = "/groups/{group_id}/repos"
    DOCS_ENDPOINT = "/repos/{namespace}/docs"
    DOC_ENDPOINT = "/repos/{namespace}/docs/{slug}"

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(config=config)
        self._base_url: str = (self._config or {}).get("base_url", self.YUQUE_BASE_URL)
        self._token: str = (self._config or {}).get("token", "")
        self._namespace: Optional[str] = (self._config or {}).get("namespace")

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated request to the Yuque API.

        Args:
            method: HTTP method.
            path: API path (e.g., /api/v2/user).
            **kwargs: Additional httpx request params.

        Returns:
            Parsed JSON response data.

        Raises:
            AuthenticationError: On 401.
            ConnectionError: On network or API error.
        """
        if not self._token:
            raise AuthenticationError(source="Yuque", detail="token is required")

        headers = kwargs.pop("headers", {})
        headers["X-Auth-Token"] = self._token
        url = f"{self._base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                if resp.status_code == 401:
                    raise AuthenticationError(source="Yuque", detail="Token invalid or expired")
                if resp.status_code == 404:
                    raise NotFoundError(resource=path, source="Yuque")
                if resp.status_code >= 400:
                    raise ConnectionError(
                        source="Yuque",
                        detail=f"API {resp.status_code}: {resp.text[:300]}",
                    )
                data = resp.json()
                if isinstance(data, dict):
                    return data.get("data", data)
                return data
        except httpx.TimeoutException as exc:
            raise ConnectionError(source="Yuque", detail=f"Timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(source="Yuque", detail=str(exc)) from exc

    async def test_connection(self) -> bool:
        """Test connectivity by calling the user endpoint.

        Returns:
            True if connection succeeds.
        """
        try:
            await self._request("GET", self.USER_ENDPOINT)
            return True
        except (AuthenticationError, ConnectionError):
            return False

    async def _get_user_login(self) -> str:
        """Get the current user's login name.

        Returns:
            Login name string.
        """
        data = await self._request("GET", self.USER_ENDPOINT)
        return data.get("login", "")

    async def _list_repos(self) -> List[Dict[str, Any]]:
        """List all accessible Yuque repositories.

        Returns:
            List of repo dicts with `namespace`, `name`, `id`, `type`.
        """
        if self._namespace:
            # When namespace is specified, treat it as a single repo target
            return [{"namespace": self._namespace, "name": self._namespace.split("/")[-1], "id": "0"}]

        repos: List[Dict[str, Any]] = []
        try:
            login = await self._get_user_login()
            data = await self._request("GET", self.REPOS_ENDPOINT.format(login=login))
            if isinstance(data, list):
                for repo in data:
                    repos.append({
                        "namespace": repo.get("namespace", ""),
                        "name": repo.get("name", ""),
                        "id": str(repo.get("id", "")),
                        "type": repo.get("type", "Book"),
                    })
        except (AuthenticationError, ConnectionError):
            pass

        return repos

    async def _list_docs(self, namespace: str) -> List[Dict[str, Any]]:
        """List documents in a Yuque repository.

        Args:
            namespace: The repo namespace (e.g., "org/repo").

        Returns:
            List of doc dicts with `slug`, `title`, `updated_at`.
        """
        path = self.DOCS_ENDPOINT.format(namespace=namespace)
        all_docs: List[Dict[str, Any]] = []
        offset = 0
        limit = 100

        while True:
            data = await self._request("GET", path, params={"offset": offset, "limit": limit})
            items = data if isinstance(data, list) else []
            if not items:
                break
            for item in items:
                all_docs.append({
                    "slug": item.get("slug", ""),
                    "title": item.get("title", ""),
                    "updated_at": item.get("updated_at"),
                })
            if len(items) < limit:
                break
            offset += limit

        return all_docs

    async def _get_doc_content(self, namespace: str, slug: str) -> Dict[str, Any]:
        """Get a single document's content in Markdown format.

        Args:
            namespace: The repo namespace.
            slug: The document slug.

        Returns:
            Dict with `title`, `body` (markdown), `updated_at`.
        """
        path = self.DOC_ENDPOINT.format(namespace=namespace, slug=slug)
        data = await self._request("GET", path, params={"raw": 1})
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        return {
            "title": data.get("title", ""),
            "body": data.get("body", "") or data.get("body_html", ""),
            "updated_at": data.get("updated_at"),
        }

    async def fetch_documents(self) -> List[ConnectorDocument]:
        """Fetch all documents from all accessible Yuque repos.

        Returns:
            List of ConnectorDocument with metadata (no full content).

        Raises:
            AuthenticationError: If token is not configured.
        """
        if not self._token:
            raise AuthenticationError(source="Yuque", detail="token is required")
        documents: List[ConnectorDocument] = []
        repos = await self._list_repos()

        for repo in repos:
            namespace = repo["namespace"]
            if not namespace:
                continue
            try:
                docs = await self._list_docs(namespace)
            except (ConnectionError, AuthenticationError):
                continue

            for doc in docs:
                documents.append(ConnectorDocument(
                    id=f"{namespace}:{doc['slug']}",
                    title=doc["title"],
                    content="",
                    url=f"https://www.yuque.com/{namespace}/{doc['slug']}",
                    updated_at=doc.get("updated_at"),
                    metadata={
                        "namespace": namespace,
                        "repo_name": repo["name"],
                        "slug": doc["slug"],
                        "connector_type": "yuque",
                    },
                ))

        return documents

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        """Fetch a single Yuque document with full Markdown content.

        Args:
            document_id: In format "namespace:slug".

        Returns:
            ConnectorDocument with content, or None.
        """
        if ":" not in document_id:
            return None
        namespace, slug = document_id.split(":", 1)
        try:
            data = await self._get_doc_content(namespace, slug)
            return ConnectorDocument(
                id=document_id,
                title=data.get("title", slug),
                content=data.get("body", ""),
                url=f"https://www.yuque.com/{namespace}/{slug}",
                updated_at=data.get("updated_at"),
                metadata={"namespace": namespace, "slug": slug, "connector_type": "yuque"},
            )
        except (NotFoundError, ConnectionError):
            return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> SyncResult:
        """Sync Yuque documents with optional incremental filtering.

        Args:
            sync_mode: "full" (all documents) or "incremental" (since last cursor).
            cursor: Optional ISO timestamp; documents with updated_at <= cursor are skipped.

        Returns:
            SyncResult with documents and next_cursor checkpoint.
        """
        documents = await self.fetch_documents()
        full_documents: List[ConnectorDocument] = []

        for doc in documents:
            if sync_mode == "incremental" and cursor and doc.updated_at:
                if doc.updated_at <= cursor:
                    continue
            namespace = doc.metadata.get("namespace", "")
            slug = doc.metadata.get("slug", "")
            if not namespace or not slug:
                continue
            try:
                data = await self._get_doc_content(namespace, slug)
                full_doc = ConnectorDocument(
                    id=doc.id,
                    title=data.get("title", doc.title),
                    content=data.get("body", ""),
                    url=doc.url,
                    updated_at=data.get("updated_at", doc.updated_at),
                    metadata=doc.metadata,
                )
                full_documents.append(full_doc)
            except (NotFoundError, ConnectionError):
                continue

        next_cursor: Optional[str] = cursor
        for doc in full_documents:
            if doc.updated_at and (next_cursor is None or doc.updated_at > next_cursor):
                next_cursor = doc.updated_at

        return SyncResult.from_documents(
            full_documents,
            next_cursor=next_cursor,
            has_more=False,
        )
