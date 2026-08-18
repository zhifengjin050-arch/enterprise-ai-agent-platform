"""Local file system sync engine.

Scans local directories and loads supported document types.
Replaces the old knowledge/local_loader.py with sync capabilities.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.knowledge.base import Document
from app.sync.base import SyncEngine


class LocalSyncEngine(SyncEngine):
    """Sync documents from local file system.

    Args:
        base_dir: Root directory to scan for documents.
        supported_extensions: File extensions to include.
    """

    def __init__(
        self,
        base_dir: str = "./data/knowledge",
        supported_extensions: tuple = (".pdf", ".docx", ".doc", ".md", ".txt", ".markdown"),
    ):
        self.base_dir = Path(base_dir)
        self.supported_extensions = supported_extensions
        self._last_sync_time: Optional[datetime] = None

    def load_documents(self) -> List[Document]:
        """Load all documents from the local directory."""
        return self.sync()

    def get_source_name(self) -> str:
        return f"Local Files ({self.base_dir})"

    def sync(self) -> List[Document]:
        """Scan the directory and load all supported files."""
        if not self.base_dir.exists():
            return []

        documents = []
        for ext in self.supported_extensions:
            for file_path in self.base_dir.rglob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        content = f"[Binary file: {file_path.name}]"

                    documents.append(Document(
                        content=content,
                        source=str(file_path),
                        metadata={
                            "file_path": str(file_path),
                            "extension": ext,
                            "file_size": file_path.stat().st_size,
                            "modified_at": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat(),
                        },
                    ))

        self._last_sync_time = datetime.utcnow()
        return documents

    def incremental_sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync only files modified since the given timestamp."""
        since = since or self._last_sync_time
        if not since:
            return self.sync()

        if not self.base_dir.exists():
            return []

        documents = []
        for ext in self.supported_extensions:
            for file_path in self.base_dir.rglob(f"*{ext}"):
                if file_path.is_file():
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime > since:
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            content = f"[Binary file: {file_path.name}]"

                        documents.append(Document(
                            content=content,
                            source=str(file_path),
                            metadata={
                                "file_path": str(file_path),
                                "extension": ext,
                                "modified_at": mtime.isoformat(),
                            },
                        ))

        return documents

    def get_last_sync_time(self) -> Optional[datetime]:
        return self._last_sync_time
