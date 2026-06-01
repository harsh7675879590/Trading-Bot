class TradingBotError(Exception):
    """Base exception class for all errors in the trading bot application."""
    pass


class ValidationError(TradingBotError):
    """Exception raised when input validation fails."""
    pass


class NetworkError(TradingBotError):
    """Exception raised when a network-level or connection error occurs."""
    pass


class BinanceAPIError(TradingBotError):
    """Exception raised when the Binance API returns an error response.
    
    Attributes:
        status_code (int): The HTTP status code of the response.
        code (int): The Binance-specific error code (e.g., -1021, -2019).
        message (str): The descriptive error message from the API.
    """
    def __init__(self, status_code: int, code: int, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error {code} (HTTP {status_code}): {message}")
