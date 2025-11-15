"""
Smart Router for fast-path toolkit execution.

Routes simple toolkit queries directly to tools, bypassing orchestration.
"""

import re
from typing import Optional, Dict, Any
from loguru import logger

from roma_dspy.tools.crypto.polymarket.toolkit import PolymarketToolkit


class SmartRouter:
    """
    Intelligent query router for fast-path execution.
    
    Detects simple toolkit queries and executes them directly,
    bypassing the full ROMA orchestration for speed.
    """
    
    def __init__(self):
        self.polymarket_toolkit = None
    
    async def route(self, goal: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to route query to fast-path execution.
        
        Args:
            goal: User's goal/query
            
        Returns:
            Result dict if fast-path succeeded, None to use normal orchestration
        """
        goal_lower = goal.lower()
        
        if self._is_polymarket_query(goal_lower):
            logger.info(f"🚀 Fast-path: Routing Polymarket query directly")
            return await self._handle_polymarket(goal_lower)
        
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
            r"polymarket.*search"
        ]
        
        return any(re.search(pattern, goal) for pattern in patterns)
    
    async def _handle_polymarket(self, goal: str) -> Dict[str, Any]:
        """Execute Polymarket query directly"""
        try:
            if not self.polymarket_toolkit:
                self.polymarket_toolkit = PolymarketToolkit()
                self.polymarket_toolkit._setup_dependencies()
            
            if re.search(r"trend|top|popular", goal):
                limit = self._extract_number(goal) or 10
                result = await self.polymarket_toolkit.get_trending_markets(limit=limit)
                
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
    
    def _format_markets(self, markets: list) -> str:
        """Format markets for display"""
        if not markets:
            return "No markets found."
        
        lines = []
        for i, market in enumerate(markets, 1):
            title = market.get('title', 'Unknown')
            volume = market.get('volume_24h', 0)
            price_yes = market.get('price_yes')
            
            lines.append(f"{i}. {title}")
            lines.append(f"   Volume 24h: ${volume:,.2f}")
            if price_yes:
                lines.append(f"   Price (YES): {price_yes}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def cleanup(self):
        """Cleanup toolkit resources"""
        if self.polymarket_toolkit:
            await self.polymarket_toolkit.cleanup()
