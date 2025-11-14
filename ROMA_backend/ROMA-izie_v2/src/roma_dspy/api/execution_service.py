"""ExecutionService for managing solver lifecycle and background tasks."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from uuid import uuid4

from loguru import logger

from roma_dspy.core.engine.solve import RecursiveSolver
from roma_dspy.core.storage.postgres_storage import PostgresStorage
from roma_dspy.core.engine.dag import TaskDAG
from roma_dspy.config.manager import ConfigManager
from roma_dspy.types import ExecutionStatus


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
        cache_ttl_seconds: int = 5
    ):
        self.storage = storage
        self.config_manager = config_manager
        self.cache = ExecutionCache(ttl_seconds=cache_ttl_seconds)
        self._background_tasks: Dict[str, asyncio.Task] = {}
        logger.info("ExecutionService initialized")

    async def start_execution(
        self,
        goal: str,
        max_depth: int = 2,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        execution_id = str(uuid4())
        config = self.config_manager.load_config()

        await self.storage.create_execution(
            execution_id=execution_id,
            initial_goal=goal,
            max_depth=max_depth,
            config={},
            metadata=metadata or {}
        )

        task = asyncio.create_task(
            self._run_execution(execution_id, goal, max_depth, config)
        )
        self._background_tasks[execution_id] = task

        logger.info(f"Started execution {execution_id} for goal: {goal[:100]}")
        return execution_id

    async def _run_execution(
        self,
        execution_id: str,
        goal: str,
        max_depth: int,
        config: Any
    ) -> None:
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

            dag = solver.last_dag
            task_stats = self._calculate_task_stats(dag)

            await self.storage.update_execution(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED.value,
                total_tasks=task_stats['total_tasks'],
                completed_tasks=task_stats['completed_tasks'],
                failed_tasks=task_stats['failed_tasks'],
                final_result={
                    "result": result.result if result else None,
                    "status": result.status.value if result else "UNKNOWN"
                }
            )
            self.cache.invalidate(execution_id)

            logger.info(
                f"Execution {execution_id} completed: "
                f"{task_stats['completed_tasks']}/{task_stats['total_tasks']} tasks"
            )

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
                    execution_metadata=merged_metadata
                )
                self.cache.invalidate(execution_id)
            except Exception as storage_error:
                logger.error(f"Failed to update execution {execution_id} status: {storage_error}")

        finally:
            self._background_tasks.pop(execution_id, None)
            if len(self._background_tasks) > 100:
                await self.cleanup_completed_tasks()

    def _calculate_task_stats(self, dag: Optional[TaskDAG]) -> Dict[str, int]:
        if not dag:
            return {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0
            }

        try:
            from roma_dspy.types import TaskStatus
            all_tasks = dag.get_all_tasks()
            
            return {
                'total_tasks': len(all_tasks),
                'completed_tasks': len([t for t in all_tasks if t.status == TaskStatus.COMPLETED]),
                'failed_tasks': len([t for t in all_tasks if t.status == TaskStatus.FAILED])
            }
        except Exception as e:
            logger.warning(f"Failed to calculate task stats: {e}")
            return {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0
            }

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
            "created_at": execution.created_at.isoformat(),
            "updated_at": execution.updated_at.isoformat(),
        }

        self.cache.set(execution_id, status_data)
        return status_data

    async def cancel_execution(self, execution_id: str) -> bool:
        task = self._background_tasks.get(execution_id)
        if not task:
            logger.warning(f"No running task found for execution {execution_id}")
            return False

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Execution {execution_id} cancelled")

        await self.storage.update_execution(
            execution_id=execution_id,
            status=ExecutionStatus.CANCELLED.value
        )
        self.cache.invalidate(execution_id)
        self._background_tasks.pop(execution_id, None)

        return True

    def is_running(self, execution_id: str) -> bool:
        task = self._background_tasks.get(execution_id)
        return task is not None and not task.done()

    def get_active_executions(self) -> list[str]:
        return [
            exec_id
            for exec_id, task in self._background_tasks.items()
            if not task.done()
        ]

    async def cleanup_completed_tasks(self) -> int:
        completed = [
            exec_id
            for exec_id, task in self._background_tasks.items()
            if task.done()
        ]

        for exec_id in completed:
            self._background_tasks.pop(exec_id)

        return len(completed)

    async def shutdown(self) -> None:
        logger.info("Shutting down ExecutionService")

        for exec_id, task in list(self._background_tasks.items()):
            if not task.done():
                logger.info(f"Cancelling execution {exec_id}")
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.cache.clear()
        logger.info("ExecutionService shutdown complete")
