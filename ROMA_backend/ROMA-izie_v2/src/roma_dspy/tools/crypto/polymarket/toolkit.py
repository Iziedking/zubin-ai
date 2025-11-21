from typing import Dict, List, Any, Optional, TYPE_CHECKING
import asyncio
import logging
import os
from datetime import datetime, timezone
import dspy

from roma_dspy.tools.base import BaseToolkit

from .client import (
    PolymarketGammaClient,
    PolymarketDataClient,
    PolymarketSubgraphClient
)
from .types import (
    MarketSearchResult,
    MarketDetails,
    UserPosition,
    MarketHolder,
    OrderResponse,
    Balance
)

if TYPE_CHECKING:
    from roma_dspy.core.storage.file_storage import FileStorage

logger = logging.getLogger(__name__)


POLYMARKET_TOOLS = [
    "search_markets",
    "get_trending_markets",
    "get_liquid_markets",
    "get_market_details",
    "get_user_positions",
    "get_market_holders",
    "place_order",
    "get_balance",
    "cancel_order"
]


class PolymarketToolkit(BaseToolkit):
    
    CATEGORY_KEYWORDS = {
        "politics": ["election", "president", "congress", "senate", "vote", "political", "government", "biden", "trump"],
        "crypto": ["bitcoin", "ethereum", "crypto", "btc", "eth", "blockchain", "defi"],
        "sports": ["nba", "nfl", "soccer", "football", "basketball", "baseball", "championship", "playoffs"],
        "business": ["stock", "company", "ceo", "merger", "earnings", "revenue", "ipo"],
        "science": ["covid", "climate", "vaccine", "research", "study", "discovery"],
        "entertainment": ["movie", "oscar", "emmy", "grammy", "album", "film", "show"]
    }
    
    def __init__(
        self,
        timeout: int = 30,
        cache_ttl: int = 300,
        graph_api_key: Optional[str] = None,
        trading_enabled: bool = False,
        private_key: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        max_order_size: float = 1000,
        max_slippage_percent: float = 5,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.graph_api_key = graph_api_key or os.getenv("THE_GRAPH_API_KEY")
        
        self.trading_enabled = trading_enabled or os.getenv("POLYMARKET_TRADING_ENABLED", "false").lower() == "true"
        self.private_key = private_key or os.getenv("POLYMARKET_PRIVATE_KEY")
        self.api_key = api_key or os.getenv("POLYMARKET_API_KEY")
        self.api_secret = api_secret or os.getenv("POLYMARKET_SECRET")
        self.api_passphrase = api_passphrase or os.getenv("POLYMARKET_PASSPHRASE")
        self.max_order_size = max_order_size
        self.max_slippage_percent = max_slippage_percent
        
        self.gamma_client = None
        self.data_client = None
        self.subgraph_client = None
        self.trading_client = None
        self.risk_manager = None
        
        logger.info(f"PolymarketToolkit initialized (trading={'enabled' if self.trading_enabled else 'disabled'})")
    
    def _setup_dependencies(self):
        logger.info("PolymarketToolkit dependencies setup complete")
    
    def _initialize_tools(self) -> List[dspy.Tool]:
        tools = []
        
        tools.append(dspy.Tool(func=self.search_markets, name="search_markets"))
        tools.append(dspy.Tool(func=self.get_trending_markets, name="get_trending_markets"))
        tools.append(dspy.Tool(func=self.get_liquid_markets, name="get_liquid_markets"))
        tools.append(dspy.Tool(func=self.get_market_details, name="get_market_details"))
        tools.append(dspy.Tool(func=self.get_user_positions, name="get_user_positions"))
        tools.append(dspy.Tool(func=self.get_market_holders, name="get_market_holders"))
        
        if self.trading_enabled:
            tools.append(dspy.Tool(func=self.place_order, name="place_order"))
            tools.append(dspy.Tool(func=self.get_balance, name="get_balance"))
            tools.append(dspy.Tool(func=self.cancel_order, name="cancel_order"))
            logger.info("Trading tools enabled")
        
        logger.info(f"Initialized {len(tools)} Polymarket tools")
        return tools
    
    async def _ensure_clients(self):
        if not self.gamma_client:
            self.gamma_client = PolymarketGammaClient(timeout=self.timeout)
            await self.gamma_client.__aenter__()
        
        if not self.data_client:
            self.data_client = PolymarketDataClient(timeout=self.timeout)
            await self.data_client.__aenter__()
        
        if not self.subgraph_client and self.graph_api_key:
            self.subgraph_client = PolymarketSubgraphClient(
                api_key=self.graph_api_key,
                timeout=self.timeout
            )
            await self.subgraph_client.__aenter__()
    
    async def _ensure_trading_client(self):
        if not self.trading_enabled:
            raise ValueError("Trading is not enabled")
        
        if not self.trading_client:
            from .trading_client import PolymarketTradingClient
            from .risk import RiskManager
            
            if not all([self.private_key, self.api_key, self.api_secret, self.api_passphrase]):
                raise ValueError("Missing trading credentials")
            
            self.trading_client = PolymarketTradingClient(
                private_key=self.private_key,
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase
            )
            
            self.risk_manager = RiskManager(
                max_order_size=self.max_order_size,
                max_slippage_percent=self.max_slippage_percent
            )
            
            await self.trading_client.__aenter__()
            logger.info("Trading client initialized")
    
    async def cleanup(self):
        if self.gamma_client:
            await self.gamma_client.__aexit__(None, None, None)
        if self.data_client:
            await self.data_client.__aexit__(None, None, None)
        if self.subgraph_client:
            await self.subgraph_client.__aexit__(None, None, None)
        if self.trading_client:
            await self.trading_client.__aexit__(None, None, None)
    
    def _detect_category(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                logger.info(f"Detected category '{category}' for query: {query}")
                return category
        
        return None
    
    def _filter_active_markets(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        active_markets = []
        
        for market in markets:
            end_date_str = market.get("endDate")
            if not end_date_str:
                active_markets.append(market)
                continue
            
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                
                if end_date > now:
                    active_markets.append(market)
                else:
                    logger.debug(f"Filtered out expired market: {market.get('question')}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse end date '{end_date_str}': {e}")
                active_markets.append(market)
        
        return active_markets
    
    async def search_markets(self, query: str, limit: int = 20) -> MarketSearchResult:
        await self._ensure_clients()
        
        try:
            category = self._detect_category(query)
            
            if category:
                markets = await self.gamma_client.get_markets_by_category(category, limit=limit * 2)
            else:
                markets = await self.gamma_client.search_markets(query, limit=limit * 2)
            
            if not markets:
                return MarketSearchResult(
                    success=True,
                    query=query,
                    count=0,
                    markets=[]
                )
            
            active_markets = self._filter_active_markets(markets)
            sorted_markets = sorted(active_markets, key=lambda x: x.get("volume", 0), reverse=True)
            top_markets = sorted_markets[:limit]
            
            return MarketSearchResult(
                success=True,
                query=query,
                count=len(top_markets),
                markets=top_markets
            )
            
        except Exception as e:
            logger.error(f"Error searching markets: {e}")
            return MarketSearchResult(
                success=False,
                query=query,
                count=0,
                error=str(e)
            )
    
    async def get_trending_markets(self, limit: int = 10) -> MarketSearchResult:
        await self._ensure_clients()
        
        try:
            markets = await self.gamma_client.get_trending_markets(limit=limit * 2)
            
            if not markets:
                return MarketSearchResult(
                    success=True,
                    query="trending",
                    count=0,
                    markets=[]
                )
            
            active_markets = self._filter_active_markets(markets)
            top_markets = active_markets[:limit]
            
            return MarketSearchResult(
                success=True,
                query="trending",
                count=len(top_markets),
                markets=top_markets
            )
            
        except Exception as e:
            logger.error(f"Error getting trending markets: {e}")
            return MarketSearchResult(
                success=False,
                query="trending",
                count=0,
                error=str(e)
            )
    
    async def get_liquid_markets(self, limit: int = 10, min_liquidity: float = 1000) -> MarketSearchResult:
        await self._ensure_clients()
        
        try:
            markets = await self.gamma_client.get_markets(limit=limit * 3)
            
            liquid_markets = [
                m for m in markets
                if m.get("liquidity", 0) >= min_liquidity
            ]
            
            active_markets = self._filter_active_markets(liquid_markets)
            sorted_markets = sorted(active_markets, key=lambda x: x.get("liquidity", 0), reverse=True)
            top_markets = sorted_markets[:limit]
            
            return MarketSearchResult(
                success=True,
                query=f"liquid_markets_min_{min_liquidity}",
                count=len(top_markets),
                markets=top_markets
            )
            
        except Exception as e:
            logger.error(f"Error getting liquid markets: {e}")
            return MarketSearchResult(
                success=False,
                query="liquid_markets",
                count=0,
                error=str(e)
            )
    
    async def get_market_details(self, market_id: str) -> MarketDetails:
        await self._ensure_clients()
        
        try:
            market = await self.gamma_client.get_market(market_id)
            
            if not market:
                return MarketDetails(
                    success=False,
                    error="Market not found",
                    market_id=market_id
                )
            
            return MarketDetails(
                success=True,
                market_id=market.get("id"),
                title=market.get("question"),
                description=market.get("description"),
                price_yes=market.get("outcomePrices", [None, None])[1],
                price_no=market.get("outcomePrices", [None, None])[0],
                volume_24h=market.get("volume24hr"),
                volume_total=market.get("volume"),
                liquidity=market.get("liquidity"),
                start_date=market.get("startDate"),
                end_date=market.get("endDate"),
                active=market.get("active", True),
                outcomes=market.get("outcomes", []),
                tags=market.get("tags", [])
            )
            
        except Exception as e:
            logger.error(f"Error getting market details: {e}")
            return MarketDetails(
                success=False,
                error=str(e),
                market_id=market_id
            )
    
    async def get_user_positions(self, user_address: str, min_value: float = 0) -> UserPosition:
        await self._ensure_clients()
        
        try:
            positions = await self.data_client.get_user_positions(user_address)
            
            if not positions:
                return UserPosition(
                    success=True,
                    user_address=user_address,
                    count=0,
                    total_value=0,
                    positions=[]
                )
            
            filtered_positions = [p for p in positions if p.get("value", 0) >= min_value]
            total_value = sum(p.get("value", 0) for p in filtered_positions)
            
            return UserPosition(
                success=True,
                user_address=user_address,
                count=len(filtered_positions),
                total_value=total_value,
                positions=filtered_positions
            )
            
        except Exception as e:
            logger.error(f"Error getting user positions: {e}")
            return UserPosition(
                success=False,
                user_address=user_address,
                count=0,
                total_value=0,
                error=str(e)
            )
    
    async def get_market_holders(self, market_id: str, min_position_size: float = 10) -> MarketHolder:
        await self._ensure_clients()
        
        try:
            holders = await self.data_client.get_market_holders(market_id)
            
            if not holders:
                return MarketHolder(
                    success=True,
                    market_id=market_id,
                    count=0,
                    holders=[]
                )
            
            filtered_holders = [h for h in holders if h.get("size", 0) >= min_position_size]
            sorted_holders = sorted(filtered_holders, key=lambda x: x.get("size", 0), reverse=True)
            
            return MarketHolder(
                success=True,
                market_id=market_id,
                count=len(sorted_holders),
                holders=sorted_holders
            )
            
        except Exception as e:
            logger.error(f"Error getting market holders: {e}")
            return MarketHolder(
                success=False,
                market_id=market_id,
                count=0,
                error=str(e)
            )
    
    async def place_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC"
    ) -> OrderResponse:
        
        if not self.trading_enabled:
            return OrderResponse(
                success=False,
                error="Trading is not enabled"
            )
        
        try:
            await self._ensure_trading_client()
            
            market_details = await self.get_market_details(token_id)
            current_price = market_details.price_yes if market_details.success else None
            liquidity = market_details.liquidity if market_details.success else None
            
            cost = size * price
            validation = self.risk_manager.validate_order(
                size=cost,
                price=price,
                current_price=current_price,
                liquidity=liquidity
            )
            
            if not validation["valid"]:
                return OrderResponse(
                    success=False,
                    error=f"Risk validation failed: {', '.join(validation['errors'])}"
                )
            
            if validation["warnings"]:
                logger.warning(f"Order warnings: {', '.join(validation['warnings'])}")
            
            result = await self.trading_client.place_limit_order(
                token_id=token_id,
                side=side,
                price=price,
                size=size,
                order_type=order_type
            )
            
            return OrderResponse(
                success=result["success"],
                order_id=result.get("order_id"),
                status=result.get("status"),
                error=result.get("error"),
                details=result.get("details", {})
            )
            
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return OrderResponse(
                success=False,
                error=str(e)
            )
    
    async def get_balance(self) -> Balance:
        
        if not self.trading_enabled:
            return Balance(
                success=False,
                usdc_balance=0,
                error="Trading is not enabled"
            )
        
        try:
            await self._ensure_trading_client()
            
            result = await self.trading_client.get_balance()
            
            return Balance(
                success=result["success"],
                usdc_balance=result.get("usdc_balance", 0),
                positions=result.get("positions", []),
                error=result.get("error")
            )
            
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            return Balance(
                success=False,
                usdc_balance=0,
                error=str(e)
            )
    
    async def cancel_order(self, order_id: str) -> OrderResponse:
        
        if not self.trading_enabled:
            return OrderResponse(
                success=False,
                error="Trading is not enabled"
            )
        
        try:
            await self._ensure_trading_client()
            
            result = await self.trading_client.cancel_order(order_id)
            
            return OrderResponse(
                success=result["success"],
                order_id=order_id,
                status=result.get("status"),
                error=result.get("error"),
                details=result.get("details", {})
            )
            
        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return OrderResponse(
                success=False,
                error=str(e)
            )