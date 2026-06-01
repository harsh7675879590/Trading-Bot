import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from bot.client import BinanceFuturesClient
from bot.validators import validate_order_inputs

logger = logging.getLogger("trading_bot.orders")


@dataclass
class OrderRequest:
    """Represents an order request prior to execution."""
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"


@dataclass
class OrderResponse:
    """Represents the standardized response from an executed order."""
    order_id: int
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    executed_qty: float
    orig_qty: float
    price: float
    avg_price: float
    stop_price: Optional[float] = None
    time_in_force: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


class OrderManager:
    """Manages high-level order operations utilizing the Binance Futures Client."""

    def __init__(self, client: BinanceFuturesClient):
        """Initializes the OrderManager.
        
        Args:
            client (BinanceFuturesClient): An authenticated Binance Futures API client.
        """
        self.client = client

    def place_order(self, request: OrderRequest) -> OrderResponse:
        """Validates and executes an order on the Binance Futures Testnet.
        
        Args:
            request (OrderRequest): The order request details.
            
        Returns:
            OrderResponse: The parsed execution results of the order.
            
        Raises:
            ValidationError: If inputs are structurally invalid.
            BinanceAPIError: If the API rejects the order.
            NetworkError: If there's an underlying network failure.
        """
        # 1. Validate inputs (this throws ValidationError on failure)
        sanitized = validate_order_inputs(
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price
        )

        logger.info(
            f"Preparing to place {sanitized['type']} {sanitized['side']} order "
            f"for {sanitized['quantity']} {sanitized['symbol']}"
        )

        # 2. Build parameter payload for Binance
        # Maps user-facing names to Binance Futures API parameter names
        payload: Dict[str, Any] = {
            "symbol": sanitized["symbol"],
            "side": sanitized["side"],
            "type": sanitized["type"],
            "quantity": str(sanitized["quantity"])
        }

        # Handle Price for Limit and Stop (Stop-Limit)
        if "price" in sanitized:
            payload["price"] = str(sanitized["price"])
            # GTC is the standard default for Futures Limit orders
            payload["timeInForce"] = request.time_in_force

        # Handle Stop Price for conditional orders
        if "stopPrice" in sanitized:
            payload["stopPrice"] = str(sanitized["stopPrice"])

        # Log order request summary
        logger.info(f"Sending order request: {payload}")

        # 3. Call private/signed API endpoint
        raw_res = self.client.request(
            method="POST",
            path="/fapi/v1/order",
            params=payload,
            signed=True
        )

        # 4. Standardize response parsing
        try:
            # Parse response fields
            order_id = int(raw_res["orderId"])
            client_order_id = raw_res.get("clientOrderId", "")
            symbol = raw_res["symbol"]
            side = raw_res["side"]
            order_type = raw_res["type"]
            status = raw_res["status"]
            
            # Numeric conversions
            executed_qty = float(raw_res.get("executedQty", 0.0))
            orig_qty = float(raw_res.get("origQty", 0.0))
            price = float(raw_res.get("price", 0.0))
            avg_price = float(raw_res.get("avgPrice", 0.0))
            
            stop_price = raw_res.get("stopPrice")
            stop_price_val = float(stop_price) if stop_price is not None and float(stop_price) > 0 else None
            
            time_in_force = raw_res.get("timeInForce")

            response = OrderResponse(
                order_id=order_id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                status=status,
                executed_qty=executed_qty,
                orig_qty=orig_qty,
                price=price,
                avg_price=avg_price,
                stop_price=stop_price_val,
                time_in_force=time_in_force,
                raw_response=raw_res
            )
            
            logger.info(
                f"Successfully placed order! ID: {response.order_id} | "
                f"Status: {response.status} | ExecQty: {response.executed_qty} | AvgPrice: {response.avg_price}"
            )
            return response
            
        except KeyError as e:
            logger.error(f"Response format mismatch. Missing key: {e}. Raw response: {raw_res}")
            # Fallback parsing or raise API error
            raise ValueError(f"Server response lacks expected parameters. Missing: {e}")
