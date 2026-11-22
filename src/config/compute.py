from typing import ClassVar


class NSEBasePopConfig:
    ADDV = 50
    IPO_ADDV = 2_50_00_000
    STOCKS_ADDV = 5_00_00_000


class ScannerConfig:
    LOOKBACK_RETURN_PCT: ClassVar[dict[int, str]] = {
        1: "1D",
        5: "1W",
        21: "1M",
        63: "3M",
        120: "6M",
    }
    LOOKBACK_DAYS_TO_MIN_RETURN_PCT: ClassVar[dict[int, str]] = {
        1: 4.99,  # close today ≥ close 1 day ago * 1.05
        5: 10,  # close today ≥ close 5 day ago * 1.075
        21: 25,  # close today ≥ close 21 days ago * 1.10
        63: 50,  # close today ≥ close 63 days ago * 1.22
        120: 100,
    }

    SMA_DAYS: ClassVar[list[int]] = [50]
    EMA_DAYS: ClassVar[list[int]] = [9, 21]

    ADR_DAY = 20
    ADR_PCT = 3
    ATR_DAY = 20  # for RS calculation

    LOOKBACK_MONTHS = 3

    LONG_RS = 70
    SHORT_RS = 40
