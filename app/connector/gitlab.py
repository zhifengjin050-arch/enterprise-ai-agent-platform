"""GitLab Wiki connector.

Fetches documents from GitLab Wiki pages and repository README files
using the GitLab API. Supports Wiki page listing, Markdown content retrieval,
and README fetching.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability
from app.connector.exceptions import AuthenticationError, ConnectionError, NotFoundError
from app.connector.sync_modes import SyncResult


class GitLabConnector(BaseConnector):
    """Connector for GitLab Wiki Pages and README.

    Requires config:
        - url: GitLab instance URL (e.g., "https://gitlab.com").
        - token: GitLab Personal Access Token.
        - project_id: The GitLab project ID (numeric).
        - wiki_enabled: Whether to sync Wiki pages (default: True).
        - readme_enabled: Whether to sync the project README (default: True).
    """

    name: str = "GitLab"
    connector_type: str = "gitlab"
    version: str = "1.0.0"
    author: str = "Enterprise AI Knowledge Copilot"
    description: str = "GitLab Wiki and README connector"
    capabilities: List[ConnectorCapability] = [
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.WEBHOOK,
        ConnectorCapability.FULL_SYNC,
        ConnectorCapability.INCREMENTAL_SYNC,
    ]
    features: List[str] = ["wiki", "readme"]

    WIKI_ENDPOINT = "/api/v4/projects/{project_id}/wikis"
    WIKI_PAGE_ENDPOINT = "/api/v4/projects/{project_id}/wikis/{slug}"
    README_ENDPOINT = "/api/v4/projects/{project_id}/readme"

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(config=config)
        cfg = self._config or {}
        self._base_url: str = cfg.get("url", "https://gitlab.com").rstrip("/")
        self._token: str = cfg.get("token", "")
        self._project_id: str = str(cfg.get("project_id", ""))
        self._wiki_enabled: bool = cfg.get("wiki_enabled", True)
        self._readme_enabled: bool = cfg.get("readme_enabled", True)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated request to the GitLab API.

        Args:
            method: HTTP method.
            path: API path (e.g., /api/v4/projects/{id}/wikis).
            **kwargs: Additional httpx request params.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401.
            ConnectionError: On network or API error.
        """
        if not self._token:
            raise AuthenticationError(source="GitLab", detail="token is required")
        if not self._project_id:
            raise AuthenticationError(source="GitLab", detail="project_id is required")

        headers = kwargs.pop("headers", {})
        headers["PRIVATE-TOKEN"] = self._token
        url = f"{self._base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                if resp.status_code == 401:
                    raise AuthenticationError(source="GitLab", detail="Token invalid or expired")
                if resp.status_code == 404:
                    raise NotFoundError(resource=path, source="GitLab")
                if resp.status_code >= 400:
                    raise ConnectionError(
                        source="GitLab",
                        detail=f"API {resp.status_code}: {resp.text[:300]}",
                    )
                return resp.json()
        except httpx.TimeoutException as exc:
            raise ConnectionError(source="GitLab", detail=f"Timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(source="GitLab", detail=str(exc)) from exc

    async def test_connection(self) -> bool:
        """Test connectivity by fetching the project info.

        Returns:
            True if connection succeeds.
        """
        try:
            await self._request("GET", f"/api/v4/projects/{self._project_id}")
            return True
        except (AuthenticationError, ConnectionError):
            return False

    async def _list_wiki_pages(self) -> List[Dict[str, Any]]:
        """List all Wiki pages for the project.

        Returns:
            List of wiki page dicts with `slug`, `title`, `format`.
        """
        path = self.WIKI_ENDPOINT.format(project_id=self._project_id)
        all_pages: List[Dict[str, Any]] = []
        page = 1
        per_page = 50

        while True:
            data = await self._request("GET", path, params={"page": page, "per_page": per_page})
            items = data if isinstance(data, list) else []
            if not items:
                break
            for item in items:
                all_pages.append({
                    "slug": item.get("slug", ""),
                    "title": item.get("title", ""),
                    "format": item.get("format", "markdown"),
                })
            if len(items) < per_page:
                break
            page += 1

        return all_pages

    async def _get_wiki_page_content(self, slug: str) -> Dict[str, Any]:
        """Get a single Wiki page with its content.

        Args:
            slug: The Wiki page slug (URL-encoded).

        Returns:
            Dict with `title`, `content`, `format`.
        """
        from urllib.parse import quote

        path = self.WIKI_PAGE_ENDPOINT.format(
            project_id=self._project_id,
            slug=quote(slug, safe=""),
        )
        data = await self._request("GET", path)
        return {
            "title": data.get("title", slug),
            "content": data.get("content", ""),
            "format": data.get("format", "markdown"),
        }

    async def _get_readme(self) -> Optional[Dict[str, Any]]:
        """Get the project README content.

        Returns:
            Dict with `title`, `content`, `file_name`, or None.
        """
        path = self.README_ENDPOINT.format(project_id=self._project_id)
        try:
            data = await self._request("GET", path)
            return {
                "title": "README",
                "content": data.get("content", ""),
                "file_name": data.get("file_name", "README.md"),
            }
        except (NotFoundError, ConnectionError):
            return None

    async def fetch_documents(self) -> List[ConnectorDocument]:
        """Fetch list of all documents from GitLab (Wiki + README).

        Returns:
            List of ConnectorDocument with metadata (no full content).

        Raises:
            AuthenticationError: If token or project_id is missing.
        """
        if not self._token:
            raise AuthenticationError(source="GitLab", detail="token is required")
        if not self._project_id:
            raise AuthenticationError(source="GitLab", detail="project_id is required")

        documents: List[ConnectorDocument] = []

        # Wiki pages
        if self._wiki_enabled:
            try:
                pages = await self._list_wiki_pages()
            except (ConnectionError, AuthenticationError):
                pages = []

            for page in pages:
                slug = page["slug"]
                documents.append(ConnectorDocument(
                    id=f"wiki:{slug}",
                    title=page["title"],
                    content="",
                    url=f"{self._base_url}/{self._project_id}/wikis/{slug}",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "slug": slug,
                        "format": page.get("format", "markdown"),
                        "source": "wiki",
                        "project_id": self._project_id,
                        "connector_type": "gitlab",
                    },
                ))

        # README
        if self._readme_enabled:
            try:
                readme = await self._get_readme()
                if readme:
                    documents.append(ConnectorDocument(
                        id="readme",
                        title=readme["title"],
                        content="",
                        url=f"{self._base_url}/{self._project_id}",
                        updated_at=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "source": "readme",
                            "file_name": readme.get("file_name", "README.md"),
                            "project_id": self._project_id,
                            "connector_type": "gitlab",
                        },
                    ))
            except (ConnectionError, AuthenticationError):
                pass

        return documents

    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        """Fetch a single GitLab document with full content.

        Args:
            document_id: "wiki:<slug>" or "readme".

        Returns:
            ConnectorDocument or None.
        """
        if document_id == "readme":
            readme = await self._get_readme()
            if not readme:
                return None
            return ConnectorDocument(
                id="readme",
                title=readme["title"],
                content=readme["content"],
                url=f"{self._base_url}/{self._project_id}",
                updated_at=datetime.now(timezone.utc).isoformat(),
                metadata={"source": "readme", "project_id": self._project_id, "connector_type": "gitlab"},
            )

        if document_id.startswith("wiki:"):
            slug = document_id[5:]
            try:
                data = await self._get_wiki_page_content(slug)
                return ConnectorDocument(
                    id=document_id,
                    title=data.get("title", slug),
                    content=data.get("content", ""),
                    url=f"{self._base_url}/{self._project_id}/wikis/{slug}",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    metadata={"slug": slug, "source": "wiki", "project_id": self._project_id, "connector_type": "gitlab"},
                )
            except (NotFoundError, ConnectionError):
                return None

        return None

    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> SyncResult:
        """Sync GitLab documents with optional incremental filtering.

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
            try:
                full = await self.get_document(doc.id)
                if full:
                    full_documents.append(full)
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
