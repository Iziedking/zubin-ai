from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class Market(BaseModel):
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
    success: bool
    query: str
    count: int
    markets: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class MarketDetails(BaseModel):
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
    success: bool
    user_address: str
    count: int
    total_value: float
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class Holder(BaseModel):
    address: str
    outcome: str
    size: float
    value: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    pnl: Optional[float] = None


class MarketHolder(BaseModel):
    success: bool
    market_id: str
    count: int
    holders: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class Trade(BaseModel):
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
    id: str
    type: str
    market: Optional[str] = None
    user: str
    amount: float
    timestamp: int
    transaction_hash: Optional[str] = None


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    GTC = "GTC"
    FOK = "FOK"
    IOC = "IOC"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class OrderRequest(BaseModel):
    token_id: str
    side: OrderSide
    price: float
    size: float
    order_type: OrderType = OrderType.GTC


class OrderResponse(BaseModel):
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class Balance(BaseModel):
    success: bool
    usdc_balance: float
    allowance: float = 0
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    total_value: float = 0
    error: Optional[str] = None


class TradeAnalysis(BaseModel):
    success: bool
    market_id: str
    market_title: str
    recommendation: str
    confidence: float
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    position_size: Optional[float] = None
    expected_return: Optional[float] = None
    risk_level: str = "MEDIUM"
    analysis: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class RiskMetrics(BaseModel):
    liquidity_score: float
    volume_score: float
    price_stability: float
    market_age_days: int
    holder_count: int
    concentration_risk: float
    overall_risk: str


class PolymarketConfig(BaseModel):
    timeout: int = Field(default=30, description="API timeout in seconds")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    graph_api_key: Optional[str] = Field(default=None, description="The Graph API key")
    
    trading_enabled: bool = Field(default=False, description="Enable trading features")
    private_key: Optional[str] = Field(default=None, description="Ethereum private key")
    api_key: Optional[str] = Field(default=None, description="Polymarket API key")
    api_secret: Optional[str] = Field(default=None, description="Polymarket API secret")
    api_passphrase: Optional[str] = Field(default=None, description="Polymarket API passphrase")
    max_order_size: float = Field(default=1000, description="Maximum order size in USDC")
    max_slippage_percent: float = Field(default=5, description="Maximum allowed slippage %")
    
    class Config:
        extra = "allow"