import logging
from datetime import datetime

import polars as pl
import polars.selectors as cs

from config.compute import ScannerConfig

logger = logging.getLogger(__name__)


def _cal_atr(
    data: pl.DataFrame | pl.LazyFrame, scan_conf: ScannerConfig
) -> pl.LazyFrame:

    res = (
        data.lazy()
        .with_columns(pl.col("timestamp").cast(pl.Date()))
        .with_columns(
            pl.col("close")
            .shift(1)
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .alias("close_prev_1")
        )
        .with_columns(
            pl.max_horizontal(
                pl.col("high") - pl.col("low"),
                (pl.col("high") - pl.col("close_prev_1")).abs(),
                (pl.col("low") - pl.col("close_prev_1")).abs(),
            ).alias("true_range")
        )
        .with_columns(
            pl.col("true_range")
            .ewm_mean(alpha=2 / (scan_conf.ATR_DAY + 1))
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .round(2)
            .alias(f"atr_{scan_conf.ATR_DAY}")
        )
        .select("symbol", "timestamp", "close", f"atr_{scan_conf.ATR_DAY}")
    )

    return res


def cal_stocks_rs(
    indices_df: pl.DataFrame | pl.LazyFrame,
    stocks_df: pl.DataFrame | pl.LazyFrame,
    end_date: datetime,
    scan_conf: ScannerConfig = ScannerConfig,
) -> pl.LazyFrame:

    index_atr = (
        _cal_atr(data=indices_df, scan_conf=scan_conf)
        .rename({f"atr_{scan_conf.ATR_DAY}": f"index_atr_{scan_conf.ATR_DAY}"})
        .with_columns(
            pl.col("close")
            .shift(1)
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .alias("close_prev_1")
        )
        .with_columns((pl.col("close") - pl.col("close_prev_1")).alias("price_change"))
        .with_columns(
            (pl.col("price_change") / pl.col(f"index_atr_{scan_conf.ATR_DAY}")).alias(
                "spi"
            )
        )
        .select("timestamp", "spi")
    )
    stocks_atr = (
        _cal_atr(data=stocks_df, scan_conf=scan_conf)
        .rename({f"atr_{scan_conf.ATR_DAY}": f"stock_atr_{scan_conf.ATR_DAY}"})
        .drop("close")
    )

    res = (
        stocks_df.lazy()
        .with_columns(pl.col("timestamp").cast(pl.Date()))
        .with_columns(
            pl.col("close")
            .shift(1)
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .alias("close_prev_1")
        )
        .with_columns((pl.col("close") - pl.col("close_prev_1")).alias("price_change"))
        .join(stocks_atr, on=["symbol", "timestamp"])
        .join(index_atr, on="timestamp", how="left")
        .with_columns(
            (pl.col("spi") * pl.col(f"stock_atr_{scan_conf.ATR_DAY}")).alias(
                "expected_change"
            )
        )
        .with_columns(
            (pl.col("price_change") - pl.col("expected_change")).alias("excess_move")
        )
        .with_columns(
            (pl.col("excess_move") / pl.col(f"stock_atr_{scan_conf.ATR_DAY}")).alias(
                f"rss_{scan_conf.ATR_DAY}"
            )
        )
        .with_columns(
            pl.col(f"rss_{scan_conf.ATR_DAY}")
            .rolling_mean(scan_conf.ATR_DAY)
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .alias("rolling RSS")
        )
        .select("symbol", "timestamp", f"rss_{scan_conf.ATR_DAY}", "rolling RSS")
        .with_columns(
            pl.col("rolling RSS")
            .rank(method="dense")
            .over("timestamp", descending=False)
            .alias("rank")
        )
        .with_columns(
            ((pl.col("rank") - 1) / (pl.len().over("timestamp") - 1) * 100)
            .round(0)
            .alias("rss_score")
        )
        .with_columns(
            pl.col(col)
            .shift(7)
            .over(partition_by="symbol", order_by="timestamp", descending=False)
            .alias(f"{col}_prev_week")
            for col in ["rss_score", "timestamp"]
        )
        .with_columns(
            (pl.col("rss_score") - pl.col("rss_score_prev_week")).alias(
                "change_in_rank"
            )
        )
        .filter((pl.col("timestamp") == end_date) & pl.col("rss_score").is_not_null())
        .sort("rss_score", "rank", descending=[True, True])
        .with_columns(cs.float().round(4))
        .collect()
    )

    return res
