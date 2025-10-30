"""
Polymarket API Client

Interfaces with Polymarket's public APIs:
- Gamma Markets API: Market data, metadata, pricing
- Data API: Positions, trades, activity, holders
- Subgraph: On-chain data via The Graph
"""

import httpx
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class PolymarketGammaClient:
    """Interface with Polymarket's Gamma Markets API"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        order_by: str = "volume_24h",
        sort_by: str = "desc",
        closed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets from Gamma API
        
        Args:
            limit: Number of markets to fetch
            offset: Pagination offset
            search: Search term for market title
            order_by: Field to sort by (volume_24h, liquidity, end_date_iso)
            sort_by: Sort direction (asc, desc)
            closed: Include closed markets (default: False - only open markets)
        """
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "order_by": order_by,
                "sort_by": sort_by,
                "closed": "true" if closed else "false"
            }
            if search:
                params["search_term"] = search
            
            response = await self.client.get(
                f"{self.BASE_URL}/markets",
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    async def get_market(self, market_id: str) -> Dict[str, Any]:
        """Fetch a specific market by ID"""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/markets/{market_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return {}
    
    async def search_markets(self, query: str, closed: bool = False) -> List[Dict[str, Any]]:
        """Search for markets by title or description"""
        return await self.get_markets(search=query, limit=50, closed=closed)
    
    async def get_markets_by_category(self, category: str, closed: bool = False) -> List[Dict[str, Any]]:
        """Fetch markets in a specific category"""
        try:
            params = {
                "category": category,
                "limit": 100,
                "closed": "true" if closed else "false"
            }
            response = await self.client.get(
                f"{self.BASE_URL}/markets",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching {category} markets: {e}")
            return []
    
    async def get_trending_markets(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending markets (highest volume 24h) - only open markets"""
        return await self.get_markets(
            limit=limit,
            order_by="volume_24h",
            sort_by="desc",
            closed=False  # Only open markets
        )
    
    async def get_liquidity_leaders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most liquid markets - only open markets"""
        return await self.get_markets(
            limit=limit,
            order_by="liquidity",
            sort_by="desc",
            closed=False  # Only open markets
        )


class PolymarketDataClient:
    """Interface with Polymarket's Data API"""
    
    BASE_URL = "https://data-api.polymarket.com"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get_positions(
        self,
        user: str,
        size_threshold: int = 0,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get user positions (holdings)
        
        Args:
            user: Ethereum address
            size_threshold: Minimum position size in tokens
            limit: Max results
        """
        try:
            params = {
                "user": user,
                "sizeThreshold": size_threshold,
                "limit": limit
            }
            response = await self.client.get(
                f"{self.BASE_URL}/positions",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching positions for {user}: {e}")
            return []
    
    async def get_trades(
        self,
        user: Optional[str] = None,
        market: Optional[str] = None,
        side: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get user trades
        
        Args:
            user: Ethereum address
            market: Market ID
            side: BUY or SELL
            limit: Max results
        """
        try:
            params = {"limit": limit}
            if user:
                params["user"] = user
            if market:
                params["market"] = market
            if side:
                params["side"] = side
            
            response = await self.client.get(
                f"{self.BASE_URL}/trades",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    async def get_activity(
        self,
        user: Optional[str] = None,
        market: Optional[str] = None,
        activity_type: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get user activity (trades, merges, splits, etc.)
        
        Args:
            user: Ethereum address
            market: Market ID
            activity_type: TRADE, SPLIT, MERGE, REDEEM, REWARD, CONVERSION
            start: Start timestamp (seconds)
            end: End timestamp (seconds)
            limit: Max results
        """
        try:
            params = {"limit": limit}
            if user:
                params["user"] = user
            if market:
                params["market"] = market
            if activity_type:
                params["type"] = activity_type
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            
            response = await self.client.get(
                f"{self.BASE_URL}/activity",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching activity: {e}")
            return []
    
    async def get_holders(
        self,
        market: str,
        sort_by: str = "size",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get top holders of a market
        
        Args:
            market: Market ID
            sort_by: TOKENS, CURRENT, INITIAL, CASHPNL, PERCENTPNL, PRICE
            limit: Max results
        """
        try:
            params = {
                "market": market,
                "sortBy": sort_by,
                "limit": limit
            }
            response = await self.client.get(
                f"{self.BASE_URL}/holders",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching holders: {e}")
            return []


class PolymarketSubgraphClient:
    """Interface with Polymarket's Subgraph (The Graph)"""
    
    SUBGRAPH_URL = "https://gateway-arbitrum.network.thegraph.com/api/{api_key}/subgraphs/id/GH9qfCWevZu27LHmPcNNzhKGbMkJXZHBxo8e6jjSfQFj"
    
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout
        self.client = None
        self.url = self.SUBGRAPH_URL.format(api_key=api_key)
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def query(self, graphql_query: str) -> Dict[str, Any]:
        """Execute a GraphQL query"""
        try:
            response = await self.client.post(
                self.url,
                json={"query": graphql_query}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error executing subgraph query: {e}")
            return {}
    
    async def get_market_trades(
        self,
        market_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get on-chain trades for a market"""
        query = f"""
        {{
            trades(
                where: {{ market: "{market_id}" }}
                first: {limit}
                orderBy: timestamp
                orderDirection: desc
            ) {{
                id
                market
                user
                outcome
                amount
                price
                timestamp
                transactionHash
            }}
        }}
        """
        result = await self.query(query)
        return result.get("data", {}).get("trades", [])
    
    async def get_user_positions_onchain(
        self,
        user_address: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get on-chain positions for a user"""
        query = f"""
        {{
            positions(
                where: {{ user: "{user_address.lower()}" }}
                first: {limit}
            ) {{
                id
                market
                user
                outcome
                balance
                totalBought
                totalSold
                averageBuyPrice
                averageSellPrice
            }}
        }}
        """
        result = await self.query(query)
        return result.get("data", {}).get("positions", [])