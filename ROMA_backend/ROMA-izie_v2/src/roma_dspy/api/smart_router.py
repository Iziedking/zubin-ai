"""
Smart Router for fast-path toolkit execution with conversation context.

Routes simple toolkit queries directly to tools, bypassing orchestration.
Maintains context for follow-up questions.
"""

import re
from typing import Optional, Dict, Any, List
from loguru import logger
from datetime import datetime, timedelta

from roma_dspy.tools.crypto.polymarket.toolkit import PolymarketToolkit


class ConversationContext:
    """Tracks conversation context for follow-up questions"""
    
    def __init__(self, ttl_minutes: int = 10):
        self.ttl_minutes = ttl_minutes
        self.contexts: Dict[str, Dict[str, Any]] = {}
    
    def set(self, client_id: str, context_type: str, data: Any):
        """Store context for a client"""
        self.contexts[client_id] = {
            "type": context_type,
            "data": data,
            "timestamp": datetime.now()
        }
    
    def get(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get context for a client if not expired"""
        if client_id not in self.contexts:
            return None
        
        context = self.contexts[client_id]
        age = datetime.now() - context["timestamp"]
        
        if age > timedelta(minutes=self.ttl_minutes):
            del self.contexts[client_id]
            return None
        
        return context
    
    def clear(self, client_id: str):
        """Clear context for a client"""
        self.contexts.pop(client_id, None)


class SmartRouter:
    """
    Intelligent query router for fast-path execution with context awareness.
    
    Detects simple toolkit queries and executes them directly,
    bypassing the full ROMA orchestration for speed.
    Maintains conversation context for follow-up questions.
    """
    
    def __init__(self):
        self.polymarket_toolkit = None
        self.context = ConversationContext(ttl_minutes=10)
    
    async def route(self, goal: str, client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Attempt to route query to fast-path execution.
        
        Args:
            goal: User's goal/query
            client_id: Optional client identifier for context tracking
            
        Returns:
            Result dict if fast-path succeeded, None to use normal orchestration
        """
        goal_lower = goal.lower()
        logger.info(f"🔍 SmartRouter checking: '{goal}' (polymarket={self._is_polymarket_query(goal_lower)})")
        
        if self._is_polymarket_query(goal_lower):
            logger.info(f"🚀 Fast-path: Direct Polymarket query detected")
            return await self._handle_polymarket(goal_lower, client_id)
        
        if client_id and self._is_followup_query(goal_lower):
            prev_context = self.context.get(client_id)
            if prev_context and prev_context["type"] == "polymarket":
                logger.info(f"🔄 Fast-path: Polymarket follow-up detected")
                return await self._handle_polymarket_followup(goal_lower, prev_context, client_id)
        
        return None
    
    def _is_polymarket_query(self, goal: str) -> bool:
        """Check if query is a simple Polymarket request"""
        keywords = ["polymarket", "prediction market", "betting market"]
        
        if not any(keyword in goal for keyword in keywords):
            return False
        
        patterns = [
            r"trend(ing)?\s+(market|polymarket)",
            r"(top|best)\s+\d*\s*market",
            r"polymarket\s+trend",
            r"get.*polymarket",
            r"show.*polymarket",
            r"liquid.*market",
            r"search.*polymarket",
            r"polymarket.*search",
            r"polymarket.*for",
            r"find.*polymarket"
        ]
        
        return any(re.search(pattern, goal) for pattern in patterns)
    
    def _is_followup_query(self, goal: str) -> bool:
        """
        Detect if query is a follow-up question.
        
        Indicators:
        - Pronouns: these, those, them, this, that, it
        - Comparatives: which, what, more, less, better
        - Short queries without explicit subject
        """
        followup_indicators = [
            r"\b(these|those|them|this|that)\b",
            r"^(which|what|how many|how much)",
            r"\b(more|less|most|least|better|worse)\b",
            r"^(show|get|find|list)\s+(me\s+)?(the\s+)?(?!polymarket)",
        ]
        
        is_short = len(goal.split()) < 8
        has_indicator = any(re.search(pattern, goal, re.IGNORECASE) for pattern in followup_indicators)
        
        return is_short and has_indicator
    
    async def _handle_polymarket(self, goal: str, client_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute Polymarket query directly"""
        try:
            if not self.polymarket_toolkit:
                self.polymarket_toolkit = PolymarketToolkit()
                self.polymarket_toolkit._setup_dependencies()
            
            if re.search(r"trend|top|popular", goal):
                limit = self._extract_number(goal) or 10
                result = await self.polymarket_toolkit.get_trending_markets(limit=limit)
                
                if result.success and client_id:
                    self.context.set(client_id, "polymarket", {
                        "query_type": "trending",
                        "markets": result.markets,
                        "limit": limit
                    })
                
                if result.success:
                    markets_text = self._format_markets(result.markets)
                    return {
                        "success": True,
                        "result": f"Top {len(result.markets)} trending Polymarket markets:\n\n{markets_text}",
                        "data": result.markets,
                        "fast_path": True
                    }
            
            elif re.search(r"liquid|depth", goal):
                limit = self._extract_number(goal) or 10
                result = await self.polymarket_toolkit.get_liquid_markets(limit=limit)
                
                if result.success and client_id:
                    self.context.set(client_id, "polymarket", {
                        "query_type": "liquid",
                        "markets": result.markets,
                        "limit": limit
                    })
                
                if result.success:
                    markets_text = self._format_markets(result.markets)
                    return {
                        "success": True,
                        "result": f"Top {len(result.markets)} most liquid Polymarket markets:\n\n{markets_text}",
                        "data": result.markets,
                        "fast_path": True
                    }
            
            elif re.search(r"search", goal):
                query = self._extract_search_term(goal)
                limit = self._extract_number(goal) or 10
                result = await self.polymarket_toolkit.search_markets(query=query, limit=limit)
                
                if result.success and client_id:
                    self.context.set(client_id, "polymarket", {
                        "query_type": "search",
                        "search_term": query,
                        "markets": result.markets,
                        "limit": limit
                    })
                
                if result.success:
                    markets_text = self._format_markets(result.markets)
                    return {
                        "success": True,
                        "result": f"Search results for '{query}' ({len(result.markets)} markets found):\n\n{markets_text}",
                        "data": result.markets,
                        "fast_path": True
                    }
            
            return {"success": False, "error": "Could not parse Polymarket query"}
            
        except Exception as e:
            logger.error(f"Fast-path Polymarket execution failed: {e}")
            return None
    
    async def _handle_polymarket_followup(
        self, 
        goal: str, 
        prev_context: Dict[str, Any],
        client_id: str
    ) -> Dict[str, Any]:
        """
        Handle follow-up questions about previous Polymarket results.
        
        Examples:
        - "which of these markets have more volume?"
        - "show me the top 3"
        - "what about Bitcoin markets?"
        """
        try:
            markets = prev_context["data"]["markets"]
            
            if re.search(r"(more|most|highest|top).*volume", goal):
                sorted_markets = sorted(
                    markets, 
                    key=lambda x: self._safe_float(x.get("volume_24h", 0)), 
                    reverse=True
                )
                limit = self._extract_number(goal) or min(5, len(sorted_markets))
                top_markets = sorted_markets[:limit]
                
                markets_text = self._format_markets(top_markets)
                return {
                    "success": True,
                    "result": f"Top {len(top_markets)} markets by volume:\n\n{markets_text}",
                    "data": top_markets,
                    "fast_path": True
                }
            
            elif re.search(r"(more|most|highest|top).*liquid", goal):
                sorted_markets = sorted(
                    markets,
                    key=lambda x: self._safe_float(x.get("liquidity", 0)),
                    reverse=True
                )
                limit = self._extract_number(goal) or min(5, len(sorted_markets))
                top_markets = sorted_markets[:limit]
                
                markets_text = self._format_markets(top_markets)
                return {
                    "success": True,
                    "result": f"Top {len(top_markets)} markets by liquidity:\n\n{markets_text}",
                    "data": top_markets,
                    "fast_path": True
                }
            
            elif re.search(r"(show|get|list).*top\s+(\d+)", goal):
                match = re.search(r"top\s+(\d+)", goal)
                limit = int(match.group(1)) if match else 5
                top_markets = markets[:min(limit, len(markets))]
                
                markets_text = self._format_markets(top_markets)
                return {
                    "success": True,
                    "result": f"Top {len(top_markets)} markets:\n\n{markets_text}",
                    "data": top_markets,
                    "fast_path": True
                }
            
            else:
                return {
                    "success": True,
                    "result": f"I have {len(markets)} markets from your previous query. Please specify what you'd like to know (e.g., 'which have more volume?', 'show top 5', 'sort by liquidity')",
                    "data": markets,
                    "fast_path": True
                }
            
        except Exception as e:
            logger.error(f"Follow-up query failed: {e}")
            return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from query (e.g., 'top 5 markets' -> 5)"""
        match = re.search(r'\b(\d+)\b', text)
        return int(match.group(1)) if match else None
    
    def _extract_search_term(self, text: str) -> str:
        """Extract search term from query"""
        patterns = [
            r'search.*?for\s+([a-zA-Z0-9\s]+?)(?:\s+market|\s+on|\s*$)',
            r'search\s+polymarket\s+for\s+([a-zA-Z0-9\s]+)',
            r'polymarket.*?for\s+([a-zA-Z0-9\s]+)',
            r'find.*?([a-zA-Z0-9\s]+)\s+market',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                term = match.group(1).strip()
                if term and len(term) > 2:
                    return term
        
        words = text.split()
        for word in ['search', 'polymarket', 'for', 'markets', 'market', 'find', 'show', 'get']:
            words = [w for w in words if w != word]
        
        if words:
            return ' '.join(words[:3])
        
        return "bitcoin"
    
    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float"""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _format_markets(self, markets: list) -> str:
        """Format markets for display"""
        if not markets:
            return "No markets found."
        
        lines = []
        for i, market in enumerate(markets, 1):
            title = market.get('title', 'Unknown')
            volume = self._safe_float(market.get('volume_24h', 0))
            price_yes = market.get('price_yes')
            liquidity = self._safe_float(market.get('liquidity', 0))
            
            lines.append(f"{i}. {title}")
            lines.append(f"   Volume 24h: ${volume:,.2f}")
            if liquidity > 0:
                lines.append(f"   Liquidity: ${liquidity:,.2f}")
            if price_yes:
                lines.append(f"   Price (YES): {price_yes}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def cleanup(self):
        """Cleanup toolkit resources"""
        if self.polymarket_toolkit:
            await self.polymarket_toolkit.cleanup()
