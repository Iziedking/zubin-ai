"""ExecutionService for managing solver lifecycle and background tasks."""

import asyncio
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any
from uuid import uuid4

from loguru import logger

from roma_dspy.core.engine.solve import RecursiveSolver
from roma_dspy.core.storage.postgres_storage import PostgresStorage
from roma_dspy.core.engine.dag import TaskDAG
from roma_dspy.config.manager import ConfigManager
from roma_dspy.types import ExecutionStatus
from roma_dspy.types.checkpoint_models import CheckpointData
from roma_dspy.api.smart_router import SmartRouter


class ExecutionCache:
    """In-memory cache for execution status with TTL."""

    def __init__(self, ttl_seconds: int = 5):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}

    def get(self, execution_id: str) -> Optional[Dict[str, Any]]:
        if execution_id not in self._cache:
            return None

        timestamp = self._timestamps[execution_id]
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()

        if age > self.ttl_seconds:
            del self._cache[execution_id]
            del self._timestamps[execution_id]
            return None

        return self._cache[execution_id]

    def set(self, execution_id: str, data: Dict[str, Any]) -> None:
        self._cache[execution_id] = data
        self._timestamps[execution_id] = datetime.now(timezone.utc)

    def invalidate(self, execution_id: str) -> None:
        self._cache.pop(execution_id, None)
        self._timestamps.pop(execution_id, None)

    def clear(self) -> None:
        self._cache.clear()
        self._timestamps.clear()

    def size(self) -> int:
        return len(self._cache)


class ExecutionService:
    """Manages execution lifecycle for RecursiveSolver."""

    def __init__(
        self,
        storage: PostgresStorage,
        config_manager: ConfigManager,
        cache_ttl_seconds: int = 5,
        checkpoint_path: Optional[Path] = None
    ):
        self.storage = storage
        self.config_manager = config_manager
        self.cache = ExecutionCache(ttl_seconds=cache_ttl_seconds)
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self.checkpoint_path = checkpoint_path or Path("/app/.checkpoints")
        self.smart_router = SmartRouter()
        logger.info("ExecutionService initialized")

    async def start_execution(
        self,
        goal: str,
        max_depth: int = 2,
        metadata: Optional[Dict[str, Any]] = None,
        client_name: Optional[str] = None
    ) -> str:
        execution_id = str(uuid4())
        config = self.config_manager.load_config()

        merged_metadata = metadata or {}
        if client_name:
            merged_metadata['client_name'] = client_name

        await self.storage.create_execution(
            execution_id=execution_id,
            initial_goal=goal,
            max_depth=max_depth,
            config={},
            metadata=merged_metadata,
            client_name=client_name
        )

        fast_result = await self.smart_router.route(goal, client_id=client_name)
        if fast_result and fast_result.get("success"):
            logger.info(f"⚡ Fast-path execution completed for {execution_id} in ~2s")
            
            await self.storage.update_execution(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED.value,
                total_tasks=1,
                completed_tasks=1,
                failed_tasks=0,
                final_result={
                    "result": fast_result["result"],
                    "status": "COMPLETED",
                    "fast_path": True
                }
            )
            self.cache.invalidate(execution_id)
            return execution_id

        task = asyncio.create_task(
            self._execute_background(
                execution_id=execution_id,
                goal=goal,
                max_depth=max_depth,
                config=config
            )
        )
        self._background_tasks[execution_id] = task
        
        return execution_id

    async def _execute_background(
        self,
        execution_id: str,
        goal: str,
        max_depth: int,
        config: Any
    ):
        try:
            await self.storage.update_execution(
                execution_id=execution_id,
                status=ExecutionStatus.RUNNING.value
            )
            self.cache.invalidate(execution_id)

            solver = RecursiveSolver(
                config=config,
                max_depth=max_depth,
                enable_logging=True,
                enable_checkpoints=True
            )

            logger.info(f"Executing {execution_id}")
            result = await solver.async_solve(goal, depth=0)

            await self.storage.update_execution(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED.value,
                final_result={
                    "result": result.result if result else None,
                    "status": result.status.value if result else "UNKNOWN"
                }
            )
            self.cache.invalidate(execution_id)

            logger.info(f"Execution {execution_id} completed successfully")

        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")

            try:
                execution = await self.storage.get_execution(execution_id)

                existing_metadata = {}
                if execution and hasattr(execution, 'execution_metadata') and execution.execution_metadata:
                    existing_metadata = execution.execution_metadata if isinstance(execution.execution_metadata, dict) else {}

                merged_metadata = {
                    **existing_metadata,
                    "error": str(e),
                    "error_type": type(e).__name__
                }

                await self.storage.update_execution(
                    execution_id=execution_id,
                    status=ExecutionStatus.FAILED.value,
                    execution_metadata=merged_metadata,
                    final_result={
                        "result": None,
                        "status": "FAILED",
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                self.cache.invalidate(execution_id)
            except Exception as storage_error:
                logger.error(f"Failed to update execution {execution_id} status: {storage_error}")

        finally:
            self._background_tasks.pop(execution_id, None)
            if len(self._background_tasks) > 100:
                await self.cleanup_completed_tasks()

    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        cached = self.cache.get(execution_id)
        if cached:
            return cached

        execution = await self.storage.get_execution(execution_id)
        if not execution:
            return None

        status_data = {
            "execution_id": execution.execution_id,
            "status": execution.status,
            "initial_goal": execution.initial_goal,
            "total_tasks": execution.total_tasks,
            "completed_tasks": execution.completed_tasks,
            "failed_tasks": execution.failed_tasks,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
            "final_result": execution.final_result
        }

        if execution.status in [ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value]:
            self.cache.set(execution_id, status_data)

        return status_data

    async def cancel_execution(self, execution_id: str) -> bool:
        task = self._background_tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await self.storage.update_execution(
            execution_id=execution_id,
            status=ExecutionStatus.FAILED.value,
            final_result={
                "result": None,
                "status": "CANCELLED",
                "error": "Execution cancelled by user"
            }
        )
        self.cache.invalidate(execution_id)

        return True

    def get_active_executions(self) -> list:
        return [
            exec_id for exec_id, task in self._background_tasks.items()
            if not task.done()
        ]

    async def cleanup_completed_tasks(self):
        completed = [
            eid for eid, task in self._background_tasks.items()
            if task.done()
        ]
        for eid in completed:
            del self._background_tasks[eid]

    async def shutdown(self):
        for task in self._background_tasks.values():
            if not task.done():
                task.cancel()
        
        await self.smart_router.cleanup()
        self.cache.clear()
