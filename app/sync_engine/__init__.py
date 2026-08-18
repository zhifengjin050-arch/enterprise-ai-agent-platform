"""Enterprise Sync Engine.

Provides durable, resumable synchronisation of documents from external
knowledge sources into the DocumentPipeline.

Architecture:
    Connector → SyncJob → SyncEngine → Checkpoint → SyncEvent → DocumentPipeline

Modules:
    models:       SyncJob, SyncCheckpoint, SyncEventRecord ORM models
    events:       SyncEvent / SyncEventType (CREATE, UPDATE, DELETE)
    checkpoint:   SyncCheckpointManager for cursor persistence
    job_manager:  SyncJobManager for job CRUD and lifecycle
    sync_engine:  SyncEngine core orchestration
    worker:       SyncWorker for background job execution
    scheduler:    SyncEngineScheduler for periodic sync
"""

from app.sync_engine.checkpoint import SyncCheckpointManager
from app.sync_engine.events import SyncEvent, SyncEventType
from app.sync_engine.job_manager import SyncJobManager
from app.sync_engine.models import (
    SyncCheckpoint,
    SyncEventRecord,
    SyncJob,
    SyncJobStatus,
)
from app.sync_engine.scheduler import SyncEngineScheduler, sync_engine_scheduler
from app.sync_engine.sync_engine import SyncEngine
from app.sync_engine.worker import SyncWorker, sync_worker

__all__ = [
    "SyncCheckpoint",
    "SyncCheckpointManager",
    "SyncEngine",
    "SyncEngineScheduler",
    "SyncEvent",
    "SyncEventRecord",
    "SyncEventType",
    "SyncJob",
    "SyncJobManager",
    "SyncJobStatus",
    "SyncWorker",
    "sync_engine_scheduler",
    "sync_worker",
]
