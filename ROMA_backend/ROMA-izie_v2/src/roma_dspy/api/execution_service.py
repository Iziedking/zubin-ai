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
            metadata=merged_metadata
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
            
            logger.info(f"Fast-path result stored for {execution_id}")
            return execution_id

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
                enable_checkpoints=True,
                execution_id=execution_id
            )

            logger.info(f"Executing {execution_id}")
            result = await solver.async_solve(goal, depth=0)

            await asyncio.sleep(2)

            task_stats = await self._get_task_stats_with_statistics(execution_id)
            
            if task_stats['total_tasks'] == 0 and result:
                task_stats['total_tasks'] = 1
                task_stats['completed_tasks'] = 1 if self._is_successful_result(result) else 0
                task_stats['failed_tasks'] = 0 if self._is_successful_result(result) else 1
                logger.info(f"Execution {execution_id}: No checkpoint data, using fallback stats")

            execution_status = self._determine_execution_status(result, task_stats)

            await self.storage.update_execution(
                execution_id=execution_id,
                status=execution_status,
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
                f"Execution {execution_id} {execution_status}: "
                f"{task_stats['completed_tasks']}/{task_stats['total_tasks']} completed, "
                f"{task_stats['failed_tasks']} failed"
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

    def _is_successful_result(self, result: Any) -> bool:
        """Check if result indicates success."""
        if not result:
            return False
        
        result_str = str(result.result).lower() if result.result else ""
        
        failure_indicators = [
            "could not",
            "failed",
            "unable to",
            "no access",
            "error",
            "unsuccessful",
            "did not succeed",
            "incomplete"
        ]
        
        return not any(indicator in result_str for indicator in failure_indicators)

    def _determine_execution_status(self, result: Any, task_stats: Dict[str, int]) -> str:
        """Determine execution status based on result and task stats."""
        if not result:
            return ExecutionStatus.FAILED.value
        
        if task_stats['failed_tasks'] > 0:
            return ExecutionStatus.FAILED.value
        
        if not self._is_successful_result(result):
            return ExecutionStatus.FAILED.value
        
        if task_stats['completed_tasks'] == task_stats['total_tasks'] and task_stats['total_tasks'] > 0:
            return ExecutionStatus.COMPLETED.value
        
        return ExecutionStatus.COMPLETED.value

    async def _load_checkpoint_from_file(self, checkpoint_path: Path) -> Optional[CheckpointData]:
        """Load checkpoint directly from file."""
        try:
            if checkpoint_path.suffix == ".gz":
                with gzip.open(checkpoint_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            return CheckpointData.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint from {checkpoint_path}: {e}")
            return None

    async def _find_latest_checkpoint_file(self, execution_id: str) -> Optional[Path]:
        """Find the latest checkpoint file for an execution."""
        if not self.checkpoint_path.exists():
            return None
        
        checkpoint_files = list(self.checkpoint_path.glob("checkpoint_*.json*"))
        
        valid_checkpoints = []
        for checkpoint_file in checkpoint_files:
            checkpoint_data = await self._load_checkpoint_from_file(checkpoint_file)
            if checkpoint_data and checkpoint_data.execution_id == execution_id:
                valid_checkpoints.append((checkpoint_file, checkpoint_data.created_at))
        
        if not valid_checkpoints:
            return None
        
        valid_checkpoints.sort(key=lambda x: x[1], reverse=True)
        return valid_checkpoints[0][0]

    async def _get_task_stats_with_statistics(self, execution_id: str) -> Dict[str, Any]:
        """Extract task statistics from the latest checkpoint with file fallback."""
        default_stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'statistics': None
        }
        
        try:
            checkpoint = await self.storage.get_latest_checkpoint(execution_id, valid_only=True)
            
            if not checkpoint:
                logger.debug(f"No checkpoint in Postgres for {execution_id}, trying file system")
                checkpoint_file = await self._find_latest_checkpoint_file(execution_id)
                
                if checkpoint_file:
                    checkpoint = await self._load_checkpoint_from_file(checkpoint_file)
                    logger.info(f"Loaded checkpoint from file: {checkpoint_file.name}")
                else:
                    logger.debug(f"No checkpoint files found for {execution_id}")
                    return default_stats
            
            if not checkpoint or not checkpoint.root_dag:
                logger.debug(f"No DAG in checkpoint for {execution_id}")
                return default_stats
            
            dag_data = checkpoint.root_dag
            if hasattr(dag_data, 'model_dump'):
                dag_data = dag_data.model_dump(mode="python")
            
            if not dag_data or 'tasks' not in dag_data:
                logger.debug(f"Invalid DAG data in checkpoint for {execution_id}")
                return default_stats
            
            dag = TaskDAG.from_dict(dag_data)
            
            from roma_dspy.types import TaskStatus
            all_tasks = dag.get_all_tasks()
            
            if not all_tasks:
                logger.debug(f"No tasks in DAG for {execution_id}")
                return default_stats
            
            stats = {
                'total_tasks': len(all_tasks),
                'completed_tasks': len([t for t in all_tasks if t.status == TaskStatus.COMPLETED]),
                'failed_tasks': len([t for t in all_tasks if t.status == TaskStatus.FAILED]),
                'statistics': dag.get_statistics() if hasattr(dag, 'get_statistics') else None
            }
            
            logger.info(f"Task stats for {execution_id}: {stats['total_tasks']} total, {stats['completed_tasks']} completed, {stats['failed_tasks']} failed")
            return stats
            
        except Exception as e:
            logger.warning(f"Failed to get task stats from checkpoint for {execution_id}: {e}")
            return default_stats

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

        await self.smart_router.cleanup()
        self.cache.clear()
        logger.info("ExecutionService shutdown complete")
