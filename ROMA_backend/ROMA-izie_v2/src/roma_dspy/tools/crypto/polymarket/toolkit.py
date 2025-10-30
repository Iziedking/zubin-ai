"""
Polymarket Toolkit for ROMA Framework

Provides tools for accessing Polymarket prediction market data:
- Market search and discovery
- Price and volume data
- Position tracking
- Holder analysis
- On-chain data via The Graph
"""

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
    MarketHolder
)


if TYPE_CHECKING:
    from roma_dspy.core.storage.file_storage import FileStorage

logger = logging.getLogger(__name__)

class PolymarketToolkit(BaseToolkit):
    """
    Polymarket Toolkit for accessing prediction market data
    
    Provides comprehensive access to Polymarket markets, prices, positions,
    and on-chain data through multiple API endpoints.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        include_tools: Optional[List[str]] = None,
        exclude_tools: Optional[List[str]] = None,
        file_storage: Optional["FileStorage"] = None,
        **config
    ):
        """
        Initialize Polymarket Toolkit
        
        Args:
            enabled: Whether toolkit is enabled (from BaseToolkit)
            include_tools: List of specific tools to include (from BaseToolkit)
            exclude_tools: List of tools to exclude (from BaseToolkit)
            file_storage: FileStorage instance if needed (from BaseToolkit)
            **config: Additional configuration:
                - timeout: API timeout in seconds (default: 30)
                - cache_ttl: Cache TTL in seconds (default: 300)
                - graph_api_key: The Graph API key for on-chain data
        """
        # Call BaseToolkit.__init__ with required parameters
        super().__init__(
            enabled=enabled,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            file_storage=file_storage,
            **config
        )
        
        # Get Polymarket-specific configuration
        self.timeout = config.get("timeout", 30)
        self.cache_ttl = config.get("cache_ttl", 300)
        self.graph_api_key = config.get("graph_api_key") or os.getenv("GRAPH_API_KEY")
        
        # Initialize clients as None (will be set up in _setup_dependencies)
        self.gamma_client = None
        self.data_client = None
        self.subgraph_client = None
        
        # Cache for API responses
        self._cache = {}
        
        logger.info(f"Initialized PolymarketToolkit with timeout={self.timeout}")
    
    def _setup_dependencies(self) -> None:
        """
        Setup dependencies for the toolkit.
        Required abstract method from BaseToolkit.
        
        Note: Actual client initialization is deferred to _ensure_clients()
        to support async context managers properly.
        """
        # Clients will be initialized lazily in _ensure_clients() due to async requirements
        logger.info("PolymarketToolkit dependencies setup complete (lazy initialization)")
    
    def _initialize_tools(self) -> List[dspy.Tool]:
        """
        Initialize and return all available tools.
        Required abstract method from BaseToolkit.
        
        Wrap each method with dspy.Tool to register them properly.
        
        Returns:
            List of dspy.Tool objects for all Polymarket tools
        """
        tools = []
        
        # Search and discovery tools
        tools.append(dspy.Tool(
            func=self.search_markets,
            name="search_markets"
        ))
        
        tools.append(dspy.Tool(
            func=self.get_trending_markets,
            name="get_trending_markets"
        ))
        
        tools.append(dspy.Tool(
            func=self.get_liquid_markets,
            name="get_liquid_markets"
        ))
        
        # Market details
        tools.append(dspy.Tool(
            func=self.get_market_details,
            name="get_market_details"
        ))
        
        # User and holder tracking
        tools.append(dspy.Tool(
            func=self.get_user_positions,
            name="get_user_positions"
        ))
        
        tools.append(dspy.Tool(
            func=self.get_market_holders,
            name="get_market_holders"
        ))
        
        logger.info(f"Initialized {len(tools)} Polymarket tools")
        return tools
    
    async def _ensure_clients(self):
        """Ensure API clients are initialized (lazy initialization for async clients)"""
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
    
    async def cleanup(self):
        """Cleanup API clients"""
        if self.gamma_client:
            await self.gamma_client.__aexit__(None, None, None)
        if self.data_client:
            await self.data_client.__aexit__(None, None, None)
        if self.subgraph_client:
            await self.subgraph_client.__aexit__(None, None, None)
    
    def _filter_active_markets(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out markets that have already ended
        
        Args:
            markets: List of market dictionaries
            
        Returns:
            List of markets with future end dates
        """
        now = datetime.now(timezone.utc)
        active_markets = []
        
        for market in markets:
            end_date_str = market.get("endDate")
            if not end_date_str:
                # If no end date, include it
                active_markets.append(market)
                continue
            
            try:
                # Parse ISO format date (e.g., "2025-12-31T12:00:00Z")
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                
                # Only include if end date is in the future
                if end_date > now:
                    active_markets.append(market)
                else:
                    logger.debug(f"Filtered out expired market: {market.get('question')} (ended {end_date_str})")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse end date '{end_date_str}': {e}")
                # Include market if we can't parse the date (safer to include)
                active_markets.append(market)
        
        return active_markets
    
    async def search_markets(
        self,
        query: str,
        limit: int = 20
    ) -> MarketSearchResult:
        """
        Search for Polymarket markets by title or description
        
        Args:
            query: Search term (e.g., "bitcoin", "election", "AI")
            limit: Maximum number of results (default: 20, max: 100)
        
        Returns:
            MarketSearchResult with list of matching markets
        """
        await self._ensure_clients()
        
        try:
            markets = await self.gamma_client.search_markets(query)
            
            # Filter out expired markets
            markets = self._filter_active_markets(markets)
            
            # Limit results
            markets = markets[:min(limit, len(markets))]
            
            # Format markets
            formatted_markets = []
            for market in markets:
                formatted_markets.append({
                    "id": market.get("id"),
                    "title": market.get("question"),
                    "description": market.get("description"),
                    "price_yes": market.get("outcomePrices", [None, None])[1],
                    "price_no": market.get("outcomePrices", [None, None])[0],
                    "volume_24h": market.get("volume24hr"),
                    "liquidity": market.get("liquidity"),
                    "end_date": market.get("endDate"),
                    "active": market.get("active", True)
                })
            
            return MarketSearchResult(
                success=True,
                query=query,
                count=len(formatted_markets),
                markets=formatted_markets
            )
            
        except Exception as e:
            logger.error(f"Error searching markets: {e}")
            return MarketSearchResult(
                success=False,
                error=str(e),
                query=query,
                count=0,
                markets=[]
            )
    
    async def get_trending_markets(
        self,
        limit: int = 20
    ) -> MarketSearchResult:
        """
        Get trending markets sorted by 24h volume (only active/future markets)
        
        Args:
            limit: Number of markets to return (default: 20, max: 100)
        
        Returns:
            MarketSearchResult with list of trending markets
        """
        await self._ensure_clients()
        
        try:
            # Request more markets to account for filtering
            markets = await self.gamma_client.get_trending_markets(limit=limit * 2)
            
            # Filter out expired markets
            markets = self._filter_active_markets(markets)
            
            # Limit to requested amount after filtering
            markets = markets[:limit]
            
            formatted_markets = []
            for market in markets:
                formatted_markets.append({
                    "id": market.get("id"),
                    "title": market.get("question"),
                    "price_yes": market.get("outcomePrices", [None, None])[1],
                    "volume_24h": market.get("volume24hr"),
                    "liquidity": market.get("liquidity"),
                    "end_date": market.get("endDate")
                })
            
            return MarketSearchResult(
                success=True,
                query="trending",
                count=len(formatted_markets),
                markets=formatted_markets
            )
            
        except Exception as e:
            logger.error(f"Error getting trending markets: {e}")
            return MarketSearchResult(
                success=False,
                error=str(e),
                query="trending",
                count=0,
                markets=[]
            )
    
    async def get_market_details(
        self,
        market_id: str
    ) -> MarketDetails:
        """
        Get detailed information about a specific market
        
        Args:
            market_id: Polymarket market ID
        
        Returns:
            MarketDetails with comprehensive market information
        """
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
    
    async def get_user_positions(
        self,
        user_address: str,
        min_value: float = 0
    ) -> UserPosition:
        """
        Get user positions (holdings) on Polymarket
        
        Args:
            user_address: Ethereum wallet address (0x...)
            min_value: Minimum position value to include (default: 0)
        
        Returns:
            UserPosition with list of user's positions
        """
        await self._ensure_clients()
        
        try:
            positions = await self.data_client.get_positions(
                user=user_address,
                size_threshold=int(min_value)
            )
            
            formatted_positions = []
            total_value = 0
            
            for pos in positions:
                value = pos.get("value", 0)
                total_value += value
                
                formatted_positions.append({
                    "market_id": pos.get("market"),
                    "market_title": pos.get("marketQuestion"),
                    "outcome": pos.get("outcome"),
                    "size": pos.get("size"),
                    "value": value,
                    "entry_price": pos.get("entryPrice"),
                    "current_price": pos.get("currentPrice"),
                    "pnl": pos.get("pnl"),
                    "pnl_percentage": pos.get("pnlPercentage")
                })
            
            return UserPosition(
                success=True,
                user_address=user_address,
                count=len(formatted_positions),
                total_value=total_value,
                positions=formatted_positions
            )
            
        except Exception as e:
            logger.error(f"Error getting user positions: {e}")
            return UserPosition(
                success=False,
                error=str(e),
                user_address=user_address,
                count=0,
                total_value=0,
                positions=[]
            )
    
    async def get_market_holders(
        self,
        market_id: str,
        limit: int = 50
    ) -> MarketHolder:
        """
        Get top holders of a specific market
        
        Args:
            market_id: Polymarket market ID
            limit: Number of holders to return (default: 50)
        
        Returns:
            MarketHolder with list of top holders
        """
        await self._ensure_clients()
        
        try:
            holders = await self.data_client.get_holders(
                market=market_id,
                sort_by="size",
                limit=limit
            )
            
            formatted_holders = []
            for holder in holders:
                formatted_holders.append({
                    "address": holder.get("user"),
                    "outcome": holder.get("outcome"),
                    "size": holder.get("size"),
                    "value": holder.get("value"),
                    "entry_price": holder.get("avgEntryPrice"),
                    "current_price": holder.get("currentPrice"),
                    "pnl": holder.get("pnl")
                })
            
            return MarketHolder(
                success=True,
                market_id=market_id,
                count=len(formatted_holders),
                holders=formatted_holders
            )
            
        except Exception as e:
            logger.error(f"Error getting market holders: {e}")
            return MarketHolder(
                success=False,
                error=str(e),
                market_id=market_id,
                count=0,
                holders=[]
            )
    
    async def get_liquid_markets(
        self,
        limit: int = 20
    ) -> MarketSearchResult:
        """
        Get most liquid markets (highest liquidity, only active/future markets)
        
        Args:
            limit: Number of markets to return (default: 20)
        
        Returns:
            MarketSearchResult with list of most liquid markets
        """
        await self._ensure_clients()
        
        try:
            # Request more markets to account for filtering
            markets = await self.gamma_client.get_liquidity_leaders(limit=limit * 2)
            
            # Filter out expired markets
            markets = self._filter_active_markets(markets)
            
            # Limit to requested amount after filtering
            markets = markets[:limit]
            
            formatted_markets = []
            for market in markets:
                formatted_markets.append({
                    "id": market.get("id"),
                    "title": market.get("question"),
                    "liquidity": market.get("liquidity"),
                    "price_yes": market.get("outcomePrices", [None, None])[1],
                    "volume_24h": market.get("volume24hr")
                })
            
            return MarketSearchResult(
                success=True,
                query="liquidity_leaders",
                count=len(formatted_markets),
                markets=formatted_markets
            )
            
        except Exception as e:
            logger.error(f"Error getting liquid markets: {e}")
            return MarketSearchResult(
                success=False,
                error=str(e),
                query="liquidity_leaders",
                count=0,
                markets=[]
            )


# Tool descriptions for ROMA's tool selector
POLYMARKET_TOOLS = {
    "search_markets": {
        "description": "Search for prediction markets by keyword or topic",
        "use_cases": ["find markets", "search predictions", "market discovery"],
        "returns": "List of matching markets with prices and volume"
    },
    "get_trending_markets": {
        "description": "Get trending markets by 24h volume",
        "use_cases": ["trending markets", "popular predictions", "high volume"],
        "returns": "Top markets sorted by 24h trading volume"
    },
    "get_market_details": {
        "description": "Get detailed information about a specific market",
        "use_cases": ["market analysis", "price check", "market info"],
        "returns": "Comprehensive market data including prices, volume, liquidity"
    },
    "get_user_positions": {
        "description": "Get user's positions and portfolio",
        "use_cases": ["portfolio", "my positions", "user holdings"],
        "returns": "User's positions with PnL and market details"
    },
    "get_market_holders": {
        "description": "Get top holders of a market",
        "use_cases": ["whale tracking", "top holders", "market concentration"],
        "returns": "Top holders with position sizes and entry prices"
    },
    "get_liquid_markets": {
        "description": "Get most liquid markets",
        "use_cases": ["liquidity", "tradable markets", "depth"],
        "returns": "Markets sorted by liquidity depth"
    }
}