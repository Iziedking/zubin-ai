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
    
    CATEGORY_KEYWORDS = {
        "crypto": [
            "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
            "solana", "sol", "cardano", "ada", "xrp", "ripple", "dogecoin",
            "doge", "polygon", "matic", "avalanche", "avax", "chainlink",
            "link", "polkadot", "dot", "litecoin", "ltc", "monero", "xmr",
            "tether", "usdt", "usdc", "stablecoin", "defi", "nft", "web3",
            "blockchain", "altcoin", "token", "coin", "binance", "bnb",
            "cosmos", "atom", "algorand", "algo", "stellar", "xlm", "tron",
            "trx", "eos", "dash", "zcash", "tezos", "xtz", "compound",
            "aave", "uniswap", "uni", "pancakeswap", "cake", "sushi",
            "maker", "mkr", "dai", "curve", "yearn", "yfi"
        ],
        "politics": [
            "election", "president", "congress", "senate", "vote", "poll",
            "democrat", "republican", "biden", "trump", "government", "policy",
            "legislation", "campaign", "candidate", "governor", "mayor",
            "political", "parliament", "minister", "supreme court", "scotus",
            "impeachment", "cabinet", "federal", "state", "local", "ballot",
            "primary", "caucus", "nomination", "party", "liberal", "conservative",
            "progressive", "moderate", "gop", "dnc", "rnc"
        ],
        "sports": [
            "nfl", "nba", "mlb", "nhl", "football", "basketball", "baseball",
            "hockey", "soccer", "tennis", "golf", "olympics", "championship",
            "playoffs", "superbowl", "super bowl", "world cup", "worldcup",
            "game", "match", "team", "player", "athlete", "coach", "mvp",
            "finals", "semifinal", "quarterback", "touchdown", "goal", "score",
            "league", "division", "conference", "fifa", "uefa", "ncaa",
            "march madness", "world series", "stanley cup", "messi", "ronaldo",
            "lebron", "curry", "mahomes", "formula 1", "f1", "nascar", "ufc",
            "boxing", "wrestling", "mma", "premier league", "la liga"
        ],
        "finance": [
            "stock", "market", "fed", "federal reserve", "interest", "rate",
            "recession", "gdp", "inflation", "economy", "nasdaq", "dow",
            "s&p", "s&p 500", "sp500", "forex", "bond", "treasury", "yield",
            "commodities", "oil", "gold", "silver", "copper", "crude",
            "brent", "wti", "futures", "options", "derivatives", "etf",
            "mutual fund", "hedge fund", "investment", "portfolio", "bull",
            "bear", "rally", "crash", "correction", "volatility", "vix",
            "earnings", "revenue", "profit", "loss", "dividend", "ipo",
            "merger", "acquisition", "bankruptcy", "credit", "debt", "loan"
        ],
        "geopolitics": [
            "war", "conflict", "military", "defense", "nato", "un",
            "united nations", "sanction", "diplomacy", "treaty", "alliance",
            "invasion", "occupation", "ceasefire", "peace", "negotiation",
            "russia", "ukraine", "china", "taiwan", "israel", "palestine",
            "iran", "north korea", "syria", "afghanistan", "iraq", "yemen",
            "nuclear", "weapons", "missile", "drone", "cyber", "espionage",
            "intelligence", "cia", "fbi", "nsa", "trade war", "tariff",
            "embargo", "blockade", "regime", "coup", "uprising", "revolution"
        ],
        "tech": [
            "ai", "artificial intelligence", "machine learning", "llm",
            "chatgpt", "openai", "anthropic", "claude", "gpt", "google",
            "microsoft", "apple", "meta", "facebook", "amazon", "tesla",
            "nvidia", "amd", "intel", "qualcomm", "samsung", "spacex",
            "starlink", "robot", "automation", "quantum", "5g", "6g",
            "cloud", "aws", "azure", "gcp", "saas", "software", "hardware",
            "chip", "semiconductor", "processor", "gpu", "cpu", "twitter",
            "x", "instagram", "tiktok", "youtube", "netflix", "spotify",
            "uber", "lyft", "airbnb", "doordash", "zoom", "slack"
        ],
        "culture": [
            "movie", "film", "tv", "television", "series", "show", "actor",
            "actress", "director", "oscar", "academy", "emmy", "golden globe",
            "netflix", "disney", "hbo", "streaming", "music", "album",
            "song", "artist", "singer", "rapper", "grammy", "billboard",
            "concert", "tour", "festival", "coachella", "celebrity", "fame",
            "viral", "trend", "meme", "influencer", "youtube", "tiktok",
            "instagram", "social media", "fashion", "style", "art", "artist",
            "painting", "sculpture", "museum", "gallery", "book", "author",
            "novel", "bestseller", "award", "prize", "pulitzer", "nobel"
        ],
        "world": [
            "global", "international", "country", "nation", "continent",
            "europe", "asia", "africa", "america", "australia", "uk",
            "france", "germany", "italy", "spain", "japan", "india",
            "brazil", "mexico", "canada", "australia", "south korea",
            "climate", "environment", "weather", "hurricane", "earthquake",
            "tsunami", "flood", "wildfire", "drought", "pandemic", "epidemic",
            "disease", "virus", "covid", "who", "health", "migration",
            "refugee", "border", "immigration", "visa", "passport"
        ],
        "economy": [
            "gdp", "growth", "recession", "unemployment", "jobs", "employment",
            "labor", "wage", "salary", "minimum wage", "income", "poverty",
            "wealth", "inequality", "tax", "fiscal", "monetary", "budget",
            "deficit", "surplus", "spending", "revenue", "export", "import",
            "trade", "manufacturing", "industrial", "production", "consumer",
            "retail", "housing", "real estate", "mortgage", "rent", "cpi",
            "ppi", "inflation rate", "deflation", "stagflation", "boom",
            "bust", "cycle", "recovery", "stimulus", "bailout", "subsidy"
        ],
        "elections": [
            "vote", "voting", "ballot", "poll", "polling", "election day",
            "midterm", "general election", "runoff", "recount", "swing state",
            "battleground", "electoral", "electoral college", "popular vote",
            "turnout", "voter", "electorate", "district", "gerrymandering",
            "campaign", "debate", "candidate", "incumbent", "challenger",
            "primary", "caucus", "convention", "delegate", "nomination",
            "endorsement", "fundraising", "pac", "super pac", "ad",
            "commercial", "rally", "town hall", "stump", "canvass"
        ]
    }
    
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
        
        super().__init__(
            enabled=enabled,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            file_storage=file_storage,
            **config
        )
        
        self.timeout = config.get("timeout", 30)
        self.cache_ttl = config.get("cache_ttl", 300)
        self.graph_api_key = config.get("graph_api_key") or os.getenv("GRAPH_API_KEY")
        
        self.gamma_client = None
        self.data_client = None
        self.subgraph_client = None
        
        self._cache = {}
        
        logger.info(f"Initialized PolymarketToolkit with timeout={self.timeout}")
    
    def _setup_dependencies(self) -> None:
        """
        Setup dependencies for the toolkit.
        Required abstract method from BaseToolkit.
        """
        logger.info("PolymarketToolkit dependencies setup complete (lazy initialization)")
    
    def _initialize_tools(self) -> List[dspy.Tool]:
        """
        Initialize and return all available tools.
        Required abstract method from BaseToolkit.
        """
        tools = []
        
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
        
        tools.append(dspy.Tool(
            func=self.get_market_details,
            name="get_market_details"
        ))
        
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
    
    def _detect_category(self, query: str) -> Optional[str]:
        """
        Detect category from query using keyword matching.
        
        Args:
            query: Search query
            
        Returns:
            Category name or None if no match
        """
        query_lower = query.lower()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                logger.info(f"Detected category '{category}' for query: {query}")
                return category
        
        return None
    
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
                active_markets.append(market)
                continue
            
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                
                if end_date > now:
                    active_markets.append(market)
                else:
                    logger.debug(f"Filtered out expired market: {market.get('question')} (ended {end_date_str})")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse end date '{end_date_str}': {e}")
                active_markets.append(market)
        
        return active_markets
    
    async def search_markets(
        self,
        query: str,
        limit: int = 20
    ) -> MarketSearchResult:
        """
        Search for Polymarket markets by title or description.
        Automatically detects category and uses category-based search for better results.
        
        Args:
            query: Search term (e.g., "bitcoin", "election", "AI")
            limit: Maximum number of results (default: 20, max: 100)
        
        Returns:
            MarketSearchResult with list of matching markets
        """
        await self._ensure_clients()
        
        try:
            category = self._detect_category(query)
            
            if category:
                logger.info(f"Using category-based search for '{category}'")
                markets = await self.gamma_client.search_in_category(
                    query=query,
                    category=category,
                    limit=limit * 2
                )
            else:
                logger.info(f"Using general search")
                markets = await self.gamma_client.search_markets(query)
            
            markets = self._filter_active_markets(markets)
            
            if not markets and category:
                logger.info(f"No results in category '{category}', trying general search")
                markets = await self.gamma_client.search_markets(query)
                markets = self._filter_active_markets(markets)
            
            markets = markets[:min(limit, len(markets))]
            
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
            markets = await self.gamma_client.get_trending_markets(limit=limit * 2)
            markets = self._filter_active_markets(markets)
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
            markets = await self.gamma_client.get_liquidity_leaders(limit=limit * 2)
            markets = self._filter_active_markets(markets)
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
