from dataclasses import dataclass
from pathlib import Path

from config.base import StorageConfig
from config.brokers import KiteConfig


@dataclass(frozen=True)
class FilePathConfig:
    end_date_str: str

    @property
    def base_population(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "base_population.csv"

    @property
    def long_stocks(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "long_stocks.csv"

    @property
    def short_stocks(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "short_stocks.csv"

    @property
    def relative_strength(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "relative_strength.csv"

    @property
    def nse_instruments_list(self) -> Path:
        return (
            StorageConfig().store_root(self.end_date_str)
            / KiteConfig.NSE_INSTRUMENTS_PATH
        )

    @property
    def nse_fno_list(self) -> Path:
        return (
            StorageConfig().store_root(self.end_date_str) / KiteConfig.FNO_STOCKS_PATH
        )

    @property
    def agg_long(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "agg_long.csv"

    @property
    def agg_short(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "agg_short.csv"

    @property
    def industry_data(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "industry_data.csv"

    @property
    def indicator_data(self) -> Path:
        return StorageConfig().store_root(self.end_date_str) / "indicator_data.csv"
