# src/roma_dspy/tools/crypto/polymarket/__init__.py
"""
Polymarket Toolkit for ROMA Framework

Provides comprehensive access to Polymarket prediction markets:
- Market search and discovery
- Real-time pricing and volume data
- Position tracking and portfolio analysis
- Holder analysis and whale tracking
- On-chain data via The Graph
"""

from .toolkit import PolymarketToolkit, POLYMARKET_TOOLS
from .client import (
    PolymarketGammaClient,
    PolymarketDataClient,
    PolymarketSubgraphClient
)
from .types import (
    Market,
    MarketSearchResult,
    MarketDetails,
    Position,
    UserPosition,
    Holder,
    MarketHolder,
    Trade,
    Activity,
    PolymarketConfig
)

__all__ = [
    # Main toolkit
    "PolymarketToolkit",
    "POLYMARKET_TOOLS",
    
    # API clients
    "PolymarketGammaClient",
    "PolymarketDataClient",
    "PolymarketSubgraphClient",
    
    # Type definitions
    "Market",
    "MarketSearchResult",
    "MarketDetails",
    "Position",
    "UserPosition",
    "Holder",
    "MarketHolder",
    "Trade",
    "Activity",
    "PolymarketConfig"
]

__version__ = "1.0.0"
__author__ = "ROMA Team"
__description__ = "Polymarket prediction market toolkit for ROMA framework"
