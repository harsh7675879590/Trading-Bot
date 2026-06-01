import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from bot.exceptions import BinanceAPIError, NetworkError

logger = logging.getLogger("trading_bot.client")


class BinanceFuturesClient:
    """A highly robust and signed client for the Binance Futures Testnet (USDT-M)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = "https://testnet.binancefuture.com",
        dry_run: bool = False
    ):
        """Initializes the Binance Futures Testnet Client.
        
        Args:
            api_key (str): The Binance Testnet API key.
            api_secret (str): The Binance Testnet API secret.
            base_url (str): The base URL for the Futures API.
            dry_run (bool): If True, runs in simulated offline mode.
        """
        self.dry_run = dry_run
        
        if not self.dry_run and (not api_key or not api_secret):
            raise ValueError("Both API Key and API Secret must be provided unless running in dry_run mode.")
            
        self.api_key = api_key or "MOCK_API_KEY"
        self.api_secret = api_secret or "MOCK_API_SECRET"
        self.base_url = base_url.rstrip("/")
        
        # Session setup with advanced retry mechanism for 429/5xx status codes
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AntigravityTradingBot/1.0.0"
        })
        
        # Setup retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s...
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Time synchronization offset (server_time - local_time) in ms
        self.time_offset = 0
        self.sync_server_time()

    def sync_server_time(self) -> None:
        """Synchronizes system time with the Binance server time to prevent -1021 timestamp errors."""
        try:
            logger.info("Synchronizing system time with Binance Futures Testnet...")
            url = f"{self.base_url}/fapi/v1/time"
            
            start_local = int(time.time() * 1000)
            response = self.session.get(url, timeout=10)
            end_local = int(time.time() * 1000)
            
            if response.status_code != 200:
                logger.warning(
                    f"Failed to fetch server time (HTTP {response.status_code}). Using local system time."
                )
                return

            server_time = response.json()["serverTime"]
            # Estimate one-way network latency
            latency = (end_local - start_local) // 2
            # Compute time offset: server_time - (local_time_at_request + latency)
            self.time_offset = server_time - (start_local + latency)
            logger.info(
                f"Time sync complete. Network Latency: {latency}ms. "
                f"Server-to-Local Offset: {self.time_offset}ms."
            )
        except Exception as e:
            logger.warning(f"Error synchronizing server time: {e}. Defaulting to system time.")

    def _get_timestamp(self) -> int:
        """Returns the synchronized current time in milliseconds."""
        return int(time.time() * 1000) + self.time_offset

    def _sign(self, query_string: str) -> str:
        """Generates an HMAC-SHA256 signature for a query string using the API Secret."""
        secret = self.api_secret or "MOCK_API_SECRET"
        return hmac.new(
            secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        """Makes an HTTP request to the Binance Futures Testnet API.
        
        Args:
            method (str): HTTP method (GET, POST, DELETE, etc.).
            path (str): Endpoint API path (e.g., '/fapi/v1/order').
            params (dict): Request parameters.
            signed (bool): True if the endpoint requires signing.
            
        Returns:
            dict: The parsed JSON response.
            
        Raises:
            NetworkError: If a connection error or timeout occurs.
            BinanceAPIError: If the Binance API returns a failure code.
        """
        url = f"{self.base_url}{path}"
        req_params = params.copy() if params else {}

        # Intercept order creation in dry-run mode
        if self.dry_run and path == "/fapi/v1/order":
            import random
            symbol = req_params.get("symbol", "BTCUSDT").upper()
            side = req_params.get("side", "BUY").upper()
            order_type = req_params.get("type", "MARKET").upper()
            qty = req_params.get("quantity", "0.01")
            price = req_params.get("price", "0.0")
            stop_price = req_params.get("stopPrice", "0.0")

            # Determine price or general market approximation
            avg_price = float(price) if float(price) > 0 else (92500.0 if "BTC" in symbol else 3150.0)
            if order_type == "MARKET":
                # Add slight random fluctuation for realism
                avg_price *= random.uniform(0.998, 1.002)

            order_id = random.randint(22500000, 99900000)
            
            mock_res = {
                "orderId": order_id,
                "symbol": symbol,
                "status": "FILLED" if order_type in ("MARKET", "LIMIT") else "NEW",
                "clientOrderId": f"mock_{order_id}",
                "price": str(price),
                "avgPrice": f"{avg_price:.2f}",
                "origQty": str(qty),
                "executedQty": str(qty) if order_type in ("MARKET", "LIMIT") else "0.0",
                "side": side,
                "type": order_type,
                "timeInForce": req_params.get("timeInForce", "GTC"),
                "stopPrice": str(stop_price),
                "updateTime": int(time.time() * 1000)
            }
            logger.info(f"[DRY-RUN] Generated Mock Order Confirmation for {symbol}")
            logger.debug(f"[DRY-RUN] Full response payload: {mock_res}")
            return mock_res

        if signed:
            req_params["timestamp"] = self._get_timestamp()
            # Standardize order of parameters to ensure query string consistency
            query_str = urllib.parse.urlencode(req_params)
            signature = self._sign(query_str)
            query_str += f"&signature={signature}"
        else:
            query_str = urllib.parse.urlencode(req_params)

        # Build full URL with query string for debugging logs
        masked_query = query_str
        if "signature" in masked_query:
            # Mask API signature and other private elements for security in logs
            parsed_query = urllib.parse.parse_qs(query_str)
            if "signature" in parsed_query:
                parsed_query["signature"] = ["*****"]
            masked_query = urllib.parse.urlencode(parsed_query, doseq=True)

        logger.debug(f"API Request: {method} {url} | Params: {masked_query}")

        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=query_str, timeout=15)
            elif method.upper() == "POST":
                response = self.session.post(url, data=query_str, timeout=15)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, data=query_str, timeout=15)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except requests.RequestException as e:
            logger.error(f"Network exception calling {url}: {e}")
            raise NetworkError(f"Failed to communicate with Binance Testnet API: {e}")

        logger.debug(f"API Response Code: {response.status_code} | Body: {response.text}")

        # Parse response
        try:
            response_json = response.json()
        except ValueError:
            logger.error(f"Invalid JSON returned from server: {response.text}")
            raise NetworkError(f"Received invalid JSON response from Binance (HTTP {response.status_code})")

        # Handle API Errors
        if response.status_code != 200:
            error_code = response_json.get("code", 0)
            error_msg = response_json.get("msg", "Unknown API error occurred")
            logger.error(f"Binance API returned error {error_code}: {error_msg}")
            
            # Special case for timestamp synchronization errors
            if error_code == -1021:
                logger.warning("Received timestamp out of sync error. Resynchronizing...")
                self.sync_server_time()
                
            raise BinanceAPIError(
                status_code=response.status_code,
                code=error_code,
                message=error_msg
            )

        return response_json
