"""Prompt optimization utilities for ROMA-DSPy."""

from .config import OptimizationConfig, get_default_config, LMConfig, patch_romaconfig
from .datasets import load_aimo_datasets, load_frames_dataset, load_seal0_dataset, load_simpleqa_verified_dataset
from .solver_setup import create_solver_module
from .judge import ComponentJudge, JudgeSignature
from .metrics import MetricWithFeedback, SearchMetric
from .selectors import (
    SELECTORS,
    planner_only_selector,
    atomizer_only_selector,
    executor_only_selector,
    aggregator_only_selector,
    round_robin_selector,
)
from .optimizer import create_optimizer

__all__ = [
    # Config
    "OptimizationConfig",
    "get_default_config",
    "LMConfig",
    "patch_romaconfig",
    # Dataset
    "load_aimo_datasets",
    "load_frames_dataset",
    "load_seal0_dataset",
    "load_simpleqa_verified_dataset",
    # Solver
    "create_solver_module",
    # Judge
    "ComponentJudge",
    "JudgeSignature",
    # Metrics
    "basic_metric",
    "MetricWithFeedback",
    # Selectors
    "SELECTORS",
    "planner_only_selector",
    "atomizer_only_selector",
    "executor_only_selector",
    "aggregator_only_selector",
    "round_robin_selector",
    # Optimizer
    "create_optimizer",
]
