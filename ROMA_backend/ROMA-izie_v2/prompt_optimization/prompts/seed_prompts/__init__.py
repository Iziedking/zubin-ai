"""Seed prompts and few-shot demos for all ROMA agents.

This package provides instruction prompts and demos for use with DSPy examples
and prompt optimization workflows.
"""

from .aggregator_seed import AGGREGATOR_PROMPT, AGGREGATOR_DEMOS
from .atomizer_seed import ATOMIZER_PROMPT, ATOMIZER_DEMOS
from .executor_seed import EXECUTOR_PROMPT, EXECUTOR_DEMOS
from .planner_seed import PLANNER_PROMPT, PLANNER_DEMOS
from .verifier_seed import VERIFIER_PROMPT, VERIFIER_DEMOS

__all__ = [
    "AGGREGATOR_PROMPT",
    "AGGREGATOR_DEMOS",
    "ATOMIZER_PROMPT",
    "ATOMIZER_DEMOS",
    "EXECUTOR_PROMPT",
    "EXECUTOR_DEMOS",
    "PLANNER_PROMPT",
    "PLANNER_DEMOS",
    "VERIFIER_PROMPT",
    "VERIFIER_DEMOS",
]