import logging
from datetime import datetime
from functools import reduce

import polars as pl
from dateutil.relativedelta import relativedelta

from config.compute import ScannerConfig

logger = logging.getLogger(__name__)


def run_scanner(
    base_pop_data: pl.DataFrame,
    stock_ohlcv_data: pl.DataFrame,
    fno_stocks: pl.DataFrame,
    end_date: datetime,
    scan_conf: ScannerConfig,
):

    start_date = end_date - relativedelta(months=scan_conf.LOOKBACK_MONTHS)

    logger.info(f"Scanning for stocks between dates: {start_date} : {end_date}")

    logger.info(f"Number of Stocks in Base Population: {base_pop_data.height}")
    logger.info(
        f"OHLCV data available for stocks: {stock_ohlcv_data.select('symbol').unique().height}"
    )

    ind_df = (
        stock_ohlcv_data.lazy()
        .filter(pl.col("symbol").is_in(base_pop_data.get_column("symbol").to_list()))
        .with_columns(pl.col("timestamp").cast(pl.Date()))
        .with_columns(
            # Shift Columns
            [
                pl.col(col)
                .shift(i)
                .over(partition_by="symbol", order_by="timestamp", descending=False)
                .alias(f"{col}_prev_{i}")
                for col in ["close"]
                for i in scan_conf.LOOKBACK_RETURN_PCT
            ]
            # Close SMA expression
            + [
                pl.col("close")
                .rolling_mean(window_size=n)
                .over(partition_by="symbol", order_by="timestamp", descending=False)
                .round(2)
                .alias(f"close_sma_{n}")
                for n in scan_conf.SMA_DAYS
            ]
            # Close EMA Experssion
            + [
                pl.col("close")
                .ewm_mean(alpha=2 / (n + 1))
                .over(partition_by="symbol", order_by="timestamp", descending=False)
                .round(2)
                .alias(f"close_ema_{n}")
                for n in scan_conf.EMA_DAYS
            ]
            # Day Range
            + [(pl.col("high") / pl.col("low")).round(4).alias("day_range")]
        )
        .with_columns(
            # ADR calculation
            [
                (
                    (
                        pl.col("day_range")
                        .rolling_mean(window_size=scan_conf.ADR_DAY)
                        .over(
                            partition_by="symbol",
                            order_by="timestamp",
                            descending=False,
                        )
                        - 1
                    )
                    * 100
                )
                .round(2)
                .alias(f"adr_pct_{scan_conf.ADR_DAY}")
            ]
            # Gains Calculation
            + [
                (
                    (pl.col("close") - pl.col(f"close_prev_{i}"))
                    * 100
                    / pl.col(f"close_prev_{i}")
                )
                .round(4)
                .alias(f"pct_gain_prev_{i}")
                for i in scan_conf.LOOKBACK_RETURN_PCT
            ]
        )
    )

    pct_gain_expr = reduce(
        lambda a, b: a | b,
        [
            pl.col(f"pct_gain_prev_{days}") >= threshold
            for days, threshold in scan_conf.LOOKBACK_DAYS_TO_MIN_RETURN_PCT.items()
        ],
    )

    pct_loss_expr = reduce(
        lambda a, b: a | b,
        [
            pl.col(f"pct_gain_prev_{days}") <= -threshold
            for days, threshold in scan_conf.LOOKBACK_DAYS_TO_MIN_RETURN_PCT.items()
        ],
    )

    long_scan_df = (
        ind_df.filter(pct_gain_expr)
        .filter(
            pl.col("timestamp").is_between(
                lower_bound=start_date, upper_bound=end_date, closed="both"
            )
        )
        .select("symbol")
        .unique()
        .collect()
    )

    short_scan_df = (
        ind_df.filter(pct_loss_expr)
        .filter(
            pl.col("timestamp").is_between(
                lower_bound=start_date, upper_bound=end_date, closed="both"
            )
        )
        .select("symbol")
        .unique()
        .collect()
    )

    logger.info(f"# of stocks in Long Scanner : {long_scan_df.height}")
    logger.info(f"# of stocks in Short Scanner : {short_scan_df.height}")

    long_filter_df = ind_df.filter(
        (pl.col("symbol").is_in(long_scan_df.get_column("symbol").to_list()))
        & (pl.col("timestamp") == end_date)
        & (
            (pl.col("close_ema_9") >= pl.col("close_sma_50"))
            | (pl.col("close_ema_21") >= pl.col("close_sma_50"))
        )
        & (pl.col("adr_pct_20") >= scan_conf.ADR_PCT)
    ).collect()

    short_filter_df = ind_df.filter(
        (pl.col("symbol").is_in(short_scan_df.get_column("symbol").to_list()))
        & (pl.col("timestamp") == end_date)
        & (
            (pl.col("close_ema_9") <= pl.col("close_sma_50"))
            | (pl.col("close_ema_21") <= pl.col("close_sma_50"))
        )
        & (pl.col("adr_pct_20") >= scan_conf.ADR_PCT)
        & (pl.col("symbol").is_in(fno_stocks.get_column("symbol").to_list()))
    ).collect()

    logger.info(f"# of stocks in Long Filter : {long_filter_df.height}")
    logger.info(f"# of stocks in Short Filter : {short_filter_df.height}")

    return long_filter_df, short_filter_df
