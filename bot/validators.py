import re
from typing import Any, Dict, Optional, Tuple

from bot.exceptions import ValidationError


def validate_symbol(symbol: str) -> str:
    """Validates the trading symbol (e.g. BTCUSDT, ETHUSDT).
    
    Args:
        symbol (str): The trading pair symbol.
        
    Returns:
        str: The sanitized, uppercase symbol.
        
    Raises:
        ValidationError: If the symbol is invalid.
    """
    if not symbol:
        raise ValidationError("Symbol is required.")
        
    sanitized = symbol.strip().upper()
    # Binance symbols are alphanumeric, usually between 5 and 15 characters
    if not re.match(r"^[A-Z0-9]{5,15}$", sanitized):
        raise ValidationError(
            f"Invalid symbol format: '{symbol}'. Must be alphanumeric between 5 and 15 characters (e.g., BTCUSDT)."
        )
    return sanitized


def validate_side(side: str) -> str:
    """Validates the order side (BUY or SELL).
    
    Args:
        side (str): The order side.
        
    Returns:
        str: The sanitized, uppercase side.
        
    Raises:
        ValidationError: If the side is invalid.
    """
    if not side:
        raise ValidationError("Order side is required.")
        
    sanitized = side.strip().upper()
    if sanitized not in ("BUY", "SELL"):
        raise ValidationError(f"Invalid order side: '{side}'. Must be either 'BUY' or 'SELL'.")
    return sanitized


def validate_order_type(order_type: str) -> str:
    """Validates the order type.
    
    Args:
        order_type (str): The order type (MARKET, LIMIT, STOP_MARKET, STOP).
        
    Returns:
        str: The sanitized, uppercase order type.
        
    Raises:
        ValidationError: If the order type is invalid.
    """
    if not order_type:
        raise ValidationError("Order type is required.")
        
    sanitized = order_type.strip().upper()
    # Standard: MARKET, LIMIT. Bonus types: STOP_MARKET, STOP (Stop-Limit).
    valid_types = ("MARKET", "LIMIT", "STOP_MARKET", "STOP")
    if sanitized not in valid_types:
        raise ValidationError(
            f"Invalid order type: '{order_type}'. Supported types: {', '.join(valid_types)}."
        )
    return sanitized


def validate_quantity(quantity: Any) -> float:
    """Validates the order quantity.
    
    Args:
        quantity: The quantity to buy or sell.
        
    Returns:
        float: The validated float quantity.
        
    Raises:
        ValidationError: If the quantity is invalid.
    """
    if quantity is None:
        raise ValidationError("Quantity is required.")
        
    try:
        val = float(quantity)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid quantity: '{quantity}'. Must be a valid number.")
        
    if val <= 0:
        raise ValidationError(f"Invalid quantity: {val}. Quantity must be strictly greater than 0.")
    return val


def validate_price(price: Any, required: bool = False) -> Optional[float]:
    """Validates the order price.
    
    Args:
        price: The order price.
        required (bool): Whether the price is strictly required.
        
    Returns:
        Optional[float]: The validated price or None if not required.
        
    Raises:
        ValidationError: If the price is invalid or missing when required.
    """
    if price is None or str(price).strip() == "":
        if required:
            raise ValidationError("Price is required for LIMIT and STOP (Stop-Limit) orders.")
        return None
        
    try:
        val = float(price)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid price: '{price}'. Must be a valid number.")
        
    if val <= 0:
        raise ValidationError(f"Invalid price: {val}. Price must be strictly greater than 0.")
    return val


def validate_stop_price(stop_price: Any, required: bool = False) -> Optional[float]:
    """Validates the trigger/stop price for conditional orders.
    
    Args:
        stop_price: The stop price.
        required (bool): Whether the stop price is strictly required.
        
    Returns:
        Optional[float]: The validated stop price or None.
        
    Raises:
        ValidationError: If the stop price is invalid.
    """
    if stop_price is None or str(stop_price).strip() == "":
        if required:
            raise ValidationError("Stop price (stopPrice) is required for STOP_MARKET and STOP orders.")
        return None
        
    try:
        val = float(stop_price)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid stop price: '{stop_price}'. Must be a valid number.")
        
    if val <= 0:
        raise ValidationError(f"Invalid stop price: {val}. Stop price must be strictly greater than 0.")
    return val


def validate_order_inputs(
    symbol: str,
    side: str,
    order_type: str,
    quantity: Any,
    price: Optional[Any] = None,
    stop_price: Optional[Any] = None
) -> Dict[str, Any]:
    """Performs comprehensive validation of all order parameters together.
    
    Args:
        symbol (str): e.g. 'BTCUSDT'
        side (str): 'BUY' or 'SELL'
        order_type (str): 'MARKET', 'LIMIT', 'STOP_MARKET', 'STOP'
        quantity (Any): Quantity of contracts
        price (Optional[Any]): Limit price
        stop_price (Optional[Any]): Stop trigger price
        
    Returns:
        dict: A dictionary of sanitized and validated arguments.
        
    Raises:
        ValidationError: If any individual parameter or overall combination is invalid.
    """
    clean_symbol = validate_symbol(symbol)
    clean_side = validate_side(side)
    clean_type = validate_order_type(order_type)
    clean_qty = validate_quantity(quantity)
    
    # Contextual price requirements
    is_price_req = clean_type in ("LIMIT", "STOP")
    clean_price = validate_price(price, required=is_price_req)
    
    # Contextual stop price requirements
    is_stop_req = clean_type in ("STOP_MARKET", "STOP")
    clean_stop = validate_stop_price(stop_price, required=is_stop_req)

    sanitized_inputs = {
        "symbol": clean_symbol,
        "side": clean_side,
        "type": clean_type,
        "quantity": clean_qty
    }
    
    if clean_price is not None:
        sanitized_inputs["price"] = clean_price
    if clean_stop is not None:
        sanitized_inputs["stopPrice"] = clean_stop
        
    return sanitized_inputs
