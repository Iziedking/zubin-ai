"""Execution management endpoints."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from roma_dspy.api.schemas import (
    SolveRequest,
    ExecutionResponse,
    ExecutionDetailResponse,
    ExecutionListResponse,
    StatusPollingResponse,
    ExecutionDataResponse,
    ErrorResponse,
)
from roma_dspy.api.helpers import (
    execution_to_response,
    execution_to_detail_response,
    calculate_progress,
)
from roma_dspy.api.dependencies import (
    get_storage,
    verify_execution_exists,
    validate_pagination,
    verify_api_key,
)
from roma_dspy.core.storage.postgres_storage import PostgresStorage
from roma_dspy.core.engine.dag import TaskDAG
from roma_dspy.types import TaskStatus

router = APIRouter()


@router.post("/executions", response_model=ExecutionResponse, status_code=202)
async def create_execution(
    request: Request,
    solve_request: SolveRequest,
    client_name: str = Depends(verify_api_key)
) -> ExecutionResponse:
    """Start a new task execution."""
    app_state = request.app.state.app_state

    if not app_state.execution_service:
        raise HTTPException(
            status_code=503,
            detail="ExecutionService not available (storage may be disabled)"
        )

    try:
        execution_id = await app_state.execution_service.start_execution(
            goal=solve_request.goal,
            max_depth=solve_request.max_depth,
            metadata=solve_request.metadata,
            client_name=client_name
        )

        storage = app_state.storage
        execution = await storage.get_execution(execution_id)

        if not execution:
            raise HTTPException(
                status_code=500,
                detail="Failed to create execution record"
            )

        return execution_to_response(execution)

    except Exception as e:
        logger.error(f"Failed to create execution: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create execution: {str(e)}"
        )


@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    storage: PostgresStorage = Depends(get_storage),
    status: Optional[str] = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
) -> ExecutionListResponse:
    """List all executions with optional filtering."""
    try:
        executions = await storage.list_executions(
            status=status,
            offset=offset,
            limit=limit
        )

        total = await storage.count_executions(status=status)

        return ExecutionListResponse(
            executions=[execution_to_response(ex) for ex in executions],
            total=total,
            offset=offset,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Failed to list executions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list executions: {str(e)}"
        )


@router.get("/executions/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution_details(
    execution_id: str = Depends(verify_execution_exists),
    storage: PostgresStorage = Depends(get_storage),
    include_statistics: bool = Query(True, description="Include DAG statistics")
) -> ExecutionDetailResponse:
    """Get detailed execution information."""
    try:
        execution = await storage.get_execution(execution_id)

        if not execution:
            raise HTTPException(
                status_code=404,
                detail=f"Execution {execution_id} not found"
            )

        return await execution_to_detail_response(
            execution=execution,
            storage=storage if include_statistics else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get execution details: {str(e)}"
        )


@router.get("/executions/{execution_id}/status", response_model=StatusPollingResponse)
async def get_execution_status(
    request: Request,
    execution_id: str = Depends(verify_execution_exists)
) -> StatusPollingResponse:
    """Get current execution status for polling."""
    app_state = request.app.state.app_state

    if not app_state.execution_service:
        raise HTTPException(
            status_code=503,
            detail="ExecutionService not available"
        )

    try:
        status_data = await app_state.execution_service.get_execution_status(execution_id)

        if not status_data:
            raise HTTPException(
                status_code=404,
                detail=f"Execution {execution_id} not found"
            )

        progress = calculate_progress(
            status=status_data["status"],
            total_tasks=status_data.get("total_tasks", 0),
            completed_tasks=status_data.get("completed_tasks", 0)
        )

        return StatusPollingResponse(
            execution_id=execution_id,
            status=status_data["status"],
            progress=progress,
            total_tasks=status_data.get("total_tasks", 0),
            completed_tasks=status_data.get("completed_tasks", 0),
            failed_tasks=status_data.get("failed_tasks", 0),
            final_result=status_data.get("final_result")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get execution status: {str(e)}"
        )


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    request: Request,
    execution_id: str = Depends(verify_execution_exists),
    client_name: str = Depends(verify_api_key)
) -> dict:
    """Cancel a running execution."""
    app_state = request.app.state.app_state

    if not app_state.execution_service:
        raise HTTPException(
            status_code=503,
            detail="ExecutionService not available"
        )

    try:
        success = await app_state.execution_service.cancel_execution(execution_id)

        return {
            "message": f"Execution {execution_id} cancelled successfully",
            "execution_id": execution_id,
            "cancelled": success
        }

    except Exception as e:
        logger.error(f"Failed to cancel execution: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel execution: {str(e)}"
        )
