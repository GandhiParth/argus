from typing import ClassVar

from config.base import StorageConfig


class EditConfig:
    DATA_PATH = StorageConfig().tmp_root("kite")
    DB_PATH = DATA_PATH / "data.db"
    DB_CONN = f"sqlite:///{DB_PATH}"


class KiteConfig(EditConfig):
    NAME = "KITE"

    HISTORICAL_DATA_LIMIT_DAYS: ClassVar[dict[str, int]] = {
        "minute": 30,
        "3minute": 90,
        "5minute": 90,
        "10minute": 90,
        "15minute": 180,
        "30minute": 180,
        "60minute": 365,
        "day": 2000,
    }

    API_RATE_LIMIT_SECONDS: ClassVar[dict[str, int]] = {
        "quote": 1,
        "historical": 3,
        "order": 10,
        "others": 10,
    }

    TICKER_LIMIT: ClassVar[dict[str, int]] = {"max_tokens": 3000}

    TYP_INDICES = "indices"
    TYP_STOCKS = "stocks"

    FNO_STOCKS_PATH = "fno_stocks.csv"
    NSE_INSTRUMENTS_PATH = "nse_instruments.csv"

    @staticmethod
    def get_db_tbl(data_type: str, frequency: str, failed_tbl: bool):
        prefix = "failed_" if failed_tbl else ""
        return f"{prefix}kite_{data_type}_ohlcv_{frequency}"
