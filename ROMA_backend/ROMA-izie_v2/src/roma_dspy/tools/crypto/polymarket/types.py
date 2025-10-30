# src/roma_dspy/tools/crypto/polymarket/types.py
"""
Type definitions for Polymarket Toolkit

Pydantic models for structured data validation and type safety
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Market(BaseModel):
    """Individual market data"""
    id: str
    title: str
    description: Optional[str] = None
    price_yes: Optional[float] = None
    price_no: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_total: Optional[float] = None
    liquidity: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    active: bool = True
    outcomes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class MarketSearchResult(BaseModel):
    """Result of market search operation"""
    success: bool
    query: str
    count: int
    markets: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class MarketDetails(BaseModel):
    """Detailed market information"""
    success: bool
    market_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    price_yes: Optional[float] = None
    price_no: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_total: Optional[float] = None
    liquidity: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    active: Optional[bool] = None
    outcomes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class Position(BaseModel):
    """Individual position data"""
    market_id: str
    market_title: Optional[str] = None
    outcome: str
    size: float
    value: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None


class UserPosition(BaseModel):
    """User positions result"""
    success: bool
    user_address: str
    count: int
    total_value: float
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class Holder(BaseModel):
    """Individual holder data"""
    address: str
    outcome: str
    size: float
    value: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    pnl: Optional[float] = None


class MarketHolder(BaseModel):
    """Market holders result"""
    success: bool
    market_id: str
    count: int
    holders: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class Trade(BaseModel):
    """Individual trade data"""
    id: str
    market: str
    user: str
    outcome: str
    side: str
    amount: float
    price: float
    timestamp: int
    transaction_hash: Optional[str] = None


class Activity(BaseModel):
    """User activity data"""
    id: str
    type: str
    market: Optional[str] = None
    user: str
    amount: float
    timestamp: int
    transaction_hash: Optional[str] = None


class PolymarketConfig(BaseModel):
    """Configuration for Polymarket Toolkit"""
    timeout: int = Field(default=30, description="API timeout in seconds")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    graph_api_key: Optional[str] = Field(default=None, description="The Graph API key")
    
    class Config:
        extra = "allow"
