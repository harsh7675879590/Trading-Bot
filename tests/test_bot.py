import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Inject parent directory into PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.exceptions import ValidationError
from bot.validators import (
    validate_order_inputs,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)
from bot.orders import OrderRequest, OrderManager, OrderResponse


class TestValidators(unittest.TestCase):
    """Tests for the input validation layer."""

    def test_validate_symbol(self):
        # Valid cases (should auto-uppercase)
        self.assertEqual(validate_symbol("btcusdt"), "BTCUSDT")
        self.assertEqual(validate_symbol("ETHUSDT"), "ETHUSDT")
        self.assertEqual(validate_symbol(" solusdt "), "SOLUSDT")

        # Invalid cases
        with self.assertRaises(ValidationError):
            validate_symbol("")
        with self.assertRaises(ValidationError):
            validate_symbol("BTC-USDT")  # invalid character
        with self.assertRaises(ValidationError):
            validate_symbol("BTC")  # too short

    def test_validate_side(self):
        # Valid cases (should auto-uppercase)
        self.assertEqual(validate_side("buy"), "BUY")
        self.assertEqual(validate_side("SELL"), "SELL")
        self.assertEqual(validate_side(" buy "), "BUY")

        # Invalid cases
        with self.assertRaises(ValidationError):
            validate_side("")
        with self.assertRaises(ValidationError):
            validate_side("HOLD")

    def test_validate_order_type(self):
        # Valid cases
        self.assertEqual(validate_order_type("market"), "MARKET")
        self.assertEqual(validate_order_type("LIMIT"), "LIMIT")
        self.assertEqual(validate_order_type("stop_market"), "STOP_MARKET")
        self.assertEqual(validate_order_type("stop"), "STOP")

        # Invalid cases
        with self.assertRaises(ValidationError):
            validate_order_type("TRAILING_STOP")

    def test_validate_quantity(self):
        # Valid cases
        self.assertEqual(validate_quantity("0.05"), 0.05)
        self.assertEqual(validate_quantity(1.5), 1.5)

        # Invalid cases
        with self.assertRaises(ValidationError):
            validate_quantity("-0.05")
        with self.assertRaises(ValidationError):
            validate_quantity("abc")
        with self.assertRaises(ValidationError):
            validate_quantity(0)

    def test_validate_price(self):
        # Not required (optional)
        self.assertIsNone(validate_price(None, required=False))
        self.assertIsNone(validate_price("", required=False))

        # Valid cases
        self.assertEqual(validate_price("91000.5", required=True), 91000.5)

        # Invalid cases
        with self.assertRaises(ValidationError):
            validate_price(None, required=True)
        with self.assertRaises(ValidationError):
            validate_price("-100")

    def test_validate_stop_price(self):
        self.assertIsNone(validate_stop_price(None, required=False))
        self.assertEqual(validate_stop_price("85000", required=True), 85000.0)

        with self.assertRaises(ValidationError):
            validate_stop_price(None, required=True)

    def test_validate_order_inputs_combinations(self):
        # 1. Market order (no price or stop price needed)
        res = validate_order_inputs("btcusdt", "buy", "market", 0.1)
        self.assertEqual(res["symbol"], "BTCUSDT")
        self.assertEqual(res["side"], "BUY")
        self.assertEqual(res["type"], "MARKET")
        self.assertEqual(res["quantity"], 0.1)
        self.assertNotIn("price", res)
        self.assertNotIn("stopPrice", res)

        # 2. Limit order (price required)
        res = validate_order_inputs("ethusdt", "sell", "limit", 1.5, price=3100.5)
        self.assertEqual(res["price"], 3100.5)

        # Missing price for Limit
        with self.assertRaises(ValidationError):
            validate_order_inputs("ethusdt", "sell", "limit", 1.5)

        # 3. Stop Market order (stopPrice required)
        res = validate_order_inputs("solusdt", "buy", "stop_market", 10.0, stop_price=140.0)
        self.assertEqual(res["stopPrice"], 140.0)

        # Missing stop price for Stop Market
        with self.assertRaises(ValidationError):
            validate_order_inputs("solusdt", "buy", "stop_market", 10.0)


class TestSignatureAndClient(unittest.TestCase):
    """Tests hmac signature generation in client."""

    @patch("bot.client.requests.Session")
    def test_client_signature(self, mock_session):
        # Mock requests.Session
        mock_instance = MagicMock()
        mock_session.return_value = mock_instance
        
        # Mock the get call to /fapi/v1/time
        mock_time_res = MagicMock()
        mock_time_res.status_code = 200
        mock_time_res.json.return_value = {"serverTime": 1700000000000}
        mock_instance.get.return_value = mock_time_res

        from bot.client import BinanceFuturesClient
        client = BinanceFuturesClient(api_key="my_key", api_secret="my_secret")
        
        # Test signature generation
        query_str = "symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=0.01&price=90000&timestamp=1700000000000"
        sig = client._sign(query_str)
        
        # Expected HMAC-SHA256 signature using my_secret
        import hmac
        import hashlib
        expected_sig = hmac.new(
            b"my_secret",
            query_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        self.assertEqual(sig, expected_sig)


if __name__ == "__main__":
    unittest.main()
