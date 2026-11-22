from dataclasses import dataclass
from pathlib import Path

from config.base import StorageConfig


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
