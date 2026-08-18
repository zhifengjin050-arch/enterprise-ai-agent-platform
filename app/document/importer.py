"""
Document import engine.

Coordinates parsing and Markdown conversion, then submits documents
to the knowledge workflow pipeline. Database / embedding / vectorstore
persistence is intentionally deferred to workflow nodes (Day 3+).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.document.converter import convert_to_markdown
from app.document.parser import DocumentParser, ParsedDocument


class DocumentImporter:
    """Enterprise document importer for the knowledge platform.

    Pipeline (Day 2):
        file -> parser -> ParsedDocument -> Markdown -> workflow.submit

    Downstream nodes (classifier / tagger / quality / embedding / store)
    are orchestrated by ``workflow/knowledge_pipeline.py`` and are not
    tightly coupled here.
    """

    def __init__(self, parser: Optional[DocumentParser] = None) -> None:
        self._parser = parser or DocumentParser()

    async def import_document(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Import a single document file into the knowledge workflow.

        Args:
            path: Path to the source document.

        Returns:
            Dict containing:
                - parsed: ParsedDocument (as dict)
                - markdown: unified Markdown string
                - workflow_result: pipeline execution result (or None)

        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedFormatError: If the format is not supported.
            DocumentParseError: If parsing fails.
        """
        file_path = Path(path)
        parsed = self._parser.parse(file_path)
        markdown = convert_to_markdown(parsed)

        workflow_result = await self._submit_to_workflow(parsed, markdown)

        return {
            "parsed": parsed.model_dump(mode="json"),
            "markdown": markdown,
            "workflow_result": workflow_result,
        }

    async def import_multiple(self, paths: List[Union[str, Path]]) -> List[Dict[str, Any]]:
        """Import multiple documents sequentially.

        Args:
            paths: List of document file paths.

        Returns:
            List of import result dicts (same shape as import_document).
        """
        results = []
        for path in paths:
            results.append(await self.import_document(path))
        return results

    def parse_only(self, path: Union[str, Path]) -> ParsedDocument:
        """Parse a document without submitting to the workflow.

        Useful for preview / validation before ingestion.

        Args:
            path: Path to the source document.

        Returns:
            ParsedDocument instance.
        """
        return self._parser.parse(path)

    async def _submit_to_workflow(
        self,
        parsed: ParsedDocument,
        markdown: str,
    ) -> Optional[Dict[str, Any]]:
        """Submit markdown content to the knowledge processing pipeline.

        Args:
            parsed: Parsed document metadata.
            markdown: Unified Markdown content.

        Returns:
            Workflow result dict, or None if submission is deferred.
        """
        try:
            from app.workflow.orchestrator import WorkflowOrchestrator

            orchestrator = WorkflowOrchestrator()

            # The workflow expects raw_content; we also need document_id
            # as a string for the orchestrator
            result = await orchestrator.process_document(
                document_id=parsed.id,
                raw_content=markdown,
                title=parsed.title,
                metadata={
                    "source": parsed.source,
                    "format": parsed.format,
                    **(parsed.metadata or {}),
                },
            )
            return result
        except Exception as exc:
            # Day 2: do not fail import if workflow is unavailable
            return {
                "status": "deferred",
                "error": str(exc),
                "document_id": parsed.id,
            }


# Module-level convenience instance
document_importer = DocumentImporter()
