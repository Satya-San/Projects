"""Domain exceptions for the trading bot."""


class ValidationError(Exception):
    """Raised when user input or business rules fail validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error or unexpected response."""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
