from typing import Dict, List, Any, Optional
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    GTC = "GTC"
    FOK = "FOK"
    IOC = "IOC"


class PolymarketTradingClient:
    
    def __init__(
        self,
        private_key: str,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        chain_id: int = 137,
        host: str = "https://clob.polymarket.com"
    ):
        self.private_key = private_key
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.chain_id = chain_id
        self.host = host
        self.client = None
        self.api_creds = None
        
        if not all([private_key, api_key, api_secret, api_passphrase]):
            raise ValueError("Missing required credentials")
    
    async def __aenter__(self):
        await self._initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
    
    async def _initialize(self):
        if self.client is not None:
            return
        
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            
            self.api_creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase
            )
            
            self.client = ClobClient(
                host=self.host,
                chain_id=self.chain_id,
                key=self.private_key,
                creds=self.api_creds
            )
            
            logger.info("Trading client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize trading client: {e}")
            raise
    
    async def close(self):
        if self.client:
            self.client = None
            self.api_creds = None
            logger.info("Trading client closed")
    
    async def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC"
    ) -> Dict[str, Any]:
        
        await self._initialize()
        
        try:
            from py_clob_client.order_builder.constants import BUY, SELL
            from py_clob_client.clob_types import OrderArgs, OrderType as ClobOrderType
            
            side_constant = BUY if side.upper() == "BUY" else SELL
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side_constant
            )
            
            signed_order = self.client.create_order(order_args)
            
            order_type_enum = getattr(ClobOrderType, order_type.upper())
            
            response = self.client.post_order(signed_order, order_type_enum)
            
            return {
                "success": True,
                "order_id": response.get("orderID"),
                "status": response.get("status"),
                "details": {
                    "token_id": token_id,
                    "side": side,
                    "price": price,
                    "size": size,
                    "order_type": order_type
                }
            }
            
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return {
                "success": False,
                "order_id": None,
                "status": "FAILED",
                "error": str(e)
            }
    
    async def place_market_order(
        self,
        token_id: str,
        side: str,
        budget: float
    ) -> Dict[str, Any]:
        
        await self._initialize()
        
        try:
            from py_clob_client.order_builder.constants import BUY, SELL
            
            side_constant = BUY if side.upper() == "BUY" else SELL
            
            market_price = await self._get_market_price(token_id, side)
            
            if not market_price:
                return {
                    "success": False,
                    "error": "Could not determine market price"
                }
            
            size = budget / market_price
            
            slippage_price = market_price * 1.02 if side.upper() == "BUY" else market_price * 0.98
            
            from py_clob_client.clob_types import OrderArgs, OrderType as ClobOrderType
            
            order_args = OrderArgs(
                token_id=token_id,
                price=slippage_price,
                size=size,
                side=side_constant
            )
            
            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, ClobOrderType.FOK)
            
            return {
                "success": True,
                "order_id": response.get("orderID"),
                "status": response.get("status"),
                "details": {
                    "token_id": token_id,
                    "side": side,
                    "budget": budget,
                    "execution_price": market_price,
                    "size": size
                }
            }
            
        except Exception as e:
            logger.error(f"Market order failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        
        await self._initialize()
        
        try:
            response = self.client.cancel_order(order_id)
            
            return {
                "success": response.get("success", False),
                "order_id": order_id,
                "status": response.get("status", "UNKNOWN"),
                "details": response
            }
            
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_balance(self) -> Dict[str, Any]:
        
        await self._initialize()
        
        try:
            balance = self.client.get_balance()
            
            return {
                "success": True,
                "usdc_balance": float(balance),
                "positions": []
            }
            
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_open_orders(self) -> Dict[str, Any]:
        
        await self._initialize()
        
        try:
            orders = self.client.get_orders()
            
            return {
                "success": True,
                "orders": orders,
                "count": len(orders)
            }
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_market_price(self, token_id: str, side: str) -> Optional[float]:
        
        try:
            book = self.client.get_order_book(token_id)
            
            if side.upper() == "BUY":
                asks = book.get("asks", [])
                if asks:
                    return float(asks[0]["price"])
            else:
                bids = book.get("bids", [])
                if bids:
                    return float(bids[0]["price"])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get market price: {e}")
            return None