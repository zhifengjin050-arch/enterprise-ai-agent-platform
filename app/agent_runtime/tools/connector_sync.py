"""ConnectorSyncTool — trigger connector sync via SyncWorker."""

from __future__ import annotations

from typing import Any, Dict

from app.agent_runtime.tools.base import BaseTool, ToolContext, ToolResult


class ConnectorSyncTool(BaseTool):
    name = "connector_sync"
    description = "Trigger a connector sync job (full or incremental)"
    permissions = ["connector.sync"]

    async def execute(self, input: Dict[str, Any], context: ToolContext) -> ToolResult:
        connector_id = str(input.get("connector_id") or "").strip()
        connector_type = str(input.get("connector_type") or "").strip()
        sync_mode = str(input.get("sync_mode") or "full")

        if not connector_id:
            return ToolResult(success=False, error="connector_id is required")

        try:
            if context.session is not None and not connector_type:
                from app.connector.repository import ConnectorConfigRepository

                repo = ConnectorConfigRepository(context.session)
                cfg = await repo.get(connector_id)
                if cfg is None:
                    return ToolResult(
                        success=False,
                        error=f"Connector '{connector_id}' not found",
                    )
                connector_type = cfg.type
                config = cfg.config_json or {}
                tenant_id = cfg.tenant_id
            else:
                config = dict(input.get("config") or {})
                tenant_id = context.tenant_id

            if not connector_type:
                return ToolResult(success=False, error="connector_type is required")

            from app.sync_engine.worker import sync_worker

            job_id = await sync_worker.submit(
                connector_id=connector_id,
                connector_type=connector_type,
                config=config,
                sync_mode=sync_mode,
                tenant_id=tenant_id,
                resume=bool(input.get("resume", True)),
            )
            return ToolResult(
                success=True,
                data={"sync_job_id": job_id, "sync_mode": sync_mode},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
