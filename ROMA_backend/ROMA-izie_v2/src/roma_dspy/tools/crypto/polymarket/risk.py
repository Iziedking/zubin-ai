from typing import Dict, Any, Optional
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class RiskManager:
    
    def __init__(
        self,
        max_order_size: float = 1000,
        max_slippage_percent: float = 5,
        min_liquidity: float = 1000,
        max_price_deviation_percent: float = 10
    ):
        self.max_order_size = max_order_size
        self.max_slippage_percent = max_slippage_percent
        self.min_liquidity = min_liquidity
        self.max_price_deviation_percent = max_price_deviation_percent
        
        logger.info(
            f"RiskManager initialized: "
            f"max_order_size=${max_order_size}, "
            f"max_slippage={max_slippage_percent}%, "
            f"min_liquidity=${min_liquidity}"
        )
    
    def validate_order(
        self,
        size: float,
        price: float,
        current_price: Optional[float] = None,
        liquidity: Optional[float] = None
    ) -> Dict[str, Any]:
        
        warnings = []
        errors = []
        risk_score = 0
        
        if size > self.max_order_size:
            errors.append(f"Order size ${size:.2f} exceeds max ${self.max_order_size}")
            risk_score += 30
        
        if price < 0.01 or price > 0.99:
            errors.append(f"Price {price} out of valid range [0.01, 0.99]")
            risk_score += 20
        
        if current_price:
            slippage = abs(price - current_price) / current_price * 100
            
            if slippage > self.max_slippage_percent:
                errors.append(
                    f"Slippage {slippage:.2f}% exceeds max {self.max_slippage_percent}%"
                )
                risk_score += 25
            elif slippage > self.max_slippage_percent * 0.5:
                warnings.append(f"High slippage: {slippage:.2f}%")
                risk_score += 10
            
            price_deviation = abs(price - current_price) / current_price * 100
            if price_deviation > self.max_price_deviation_percent:
                warnings.append(
                    f"Price deviation {price_deviation:.2f}% is significant"
                )
                risk_score += 15
        
        if liquidity is not None:
            if liquidity < self.min_liquidity:
                errors.append(
                    f"Liquidity ${liquidity:.2f} below minimum ${self.min_liquidity}"
                )
                risk_score += 20
            elif liquidity < self.min_liquidity * 2:
                warnings.append(f"Low liquidity: ${liquidity:.2f}")
                risk_score += 10
        
        is_valid = len(errors) == 0
        
        risk_level = "LOW"
        if risk_score > 50:
            risk_level = "HIGH"
        elif risk_score > 25:
            risk_level = "MEDIUM"
        
        return {
            "valid": is_valid,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "warnings": warnings,
            "errors": errors,
            "checks": {
                "size_check": size <= self.max_order_size,
                "price_check": 0.01 <= price <= 0.99,
                "slippage_check": not current_price or (
                    abs(price - current_price) / current_price * 100 
                    <= self.max_slippage_percent
                ),
                "liquidity_check": not liquidity or liquidity >= self.min_liquidity
            }
        }
    
    def calculate_position_size(
        self,
        budget: float,
        price: float,
        risk_percent: float = 2
    ) -> Dict[str, Any]:
        
        if price <= 0:
            return {
                "success": False,
                "error": "Invalid price"
            }
        
        if risk_percent <= 0 or risk_percent > 100:
            risk_percent = 2
        
        risk_amount = budget * (risk_percent / 100)
        
        position_size = min(risk_amount, self.max_order_size)
        
        tokens = position_size / price
        
        return {
            "success": True,
            "position_size_usd": position_size,
            "tokens": tokens,
            "price": price,
            "risk_percent": risk_percent,
            "max_loss": position_size * (1 - price) if price < 0.5 else position_size * price
        }
    
    def assess_market_risk(
        self,
        liquidity: float,
        volume_24h: float,
        price: float,
        volatility: Optional[float] = None
    ) -> Dict[str, Any]:
        
        risk_score = 0
        factors = []
        
        if liquidity < 5000:
            risk_score += 30
            factors.append("Very low liquidity")
        elif liquidity < 10000:
            risk_score += 15
            factors.append("Low liquidity")
        
        if volume_24h < 1000:
            risk_score += 25
            factors.append("Low trading volume")
        elif volume_24h < 5000:
            risk_score += 10
            factors.append("Moderate volume")
        
        if price < 0.1 or price > 0.9:
            risk_score += 20
            factors.append("Extreme price position")
        elif price < 0.2 or price > 0.8:
            risk_score += 10
            factors.append("High confidence price")
        
        if volatility:
            if volatility > 20:
                risk_score += 25
                factors.append("High volatility")
            elif volatility > 10:
                risk_score += 10
                factors.append("Moderate volatility")
        
        risk_level = "LOW"
        if risk_score > 50:
            risk_level = "HIGH"
        elif risk_score > 30:
            risk_level = "MEDIUM"
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": factors,
            "recommended_max_position": self.max_order_size * (1 - risk_score / 100)
        }
    
    def validate_market_order(
        self,
        budget: float,
        market_price: float,
        slippage_tolerance: float = 2
    ) -> Dict[str, Any]:
        
        if budget > self.max_order_size:
            return {
                "valid": False,
                "error": f"Budget ${budget:.2f} exceeds max order size ${self.max_order_size}"
            }
        
        tokens = budget / market_price
        max_price = market_price * (1 + slippage_tolerance / 100)
        min_price = market_price * (1 - slippage_tolerance / 100)
        
        return {
            "valid": True,
            "budget": budget,
            "market_price": market_price,
            "estimated_tokens": tokens,
            "max_acceptable_price": max_price,
            "min_acceptable_price": min_price,
            "slippage_tolerance_percent": slippage_tolerance
        }