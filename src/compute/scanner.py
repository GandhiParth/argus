import logging
from datetime import datetime
from functools import reduce
from typing import Literal

import numpy as np
import polars as pl
import polars.selectors as cs
from dateutil.relativedelta import relativedelta

from config.compute import ScannerConfig
from config.file_paths import FilePathConfig

logger = logging.getLogger(__name__)


def _calculate_slope(arr: pl.Series) -> float:
    y = arr.to_numpy()
    x = np.arange(len(y))

    return float(np.polyfit(x, y, 1)[0])


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
            # 52 week high
            + [
                pl.col("high")
                .rolling_max(window_size=252)
                .over(partition_by="symbol", order_by="timestamp", descending=False)
                .alias("high_52w")
            ]
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
            # Pct off 52 week high
            + [
                ((pl.col("high_52w") - pl.col("close")) * 100 / pl.col("high_52w"))
                .round(2)
                .alias("pct_off_52w_high")
            ]
            # Slope of 200 SMA
            + [
                pl.col("close_sma_200")
                .rolling_map(_calculate_slope, window_size=20, min_samples=20)
                .round(2)
                .over(
                    partition_by="symbol",
                    order_by="timestamp",
                    descending=False,
                )
                .alias("close_sma_200_slope")
            ]
        )
        .with_columns(
            (pl.col("close_sma_200_slope") * 100 / pl.col("close_sma_200"))
            .round(2)
            .alias("close_sma_200_slope_pct")
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

    ind_df = (
        ind_df.filter(pl.col("timestamp") == end_date)
        .select(
            [
                "symbol",
                "timestamp",
                "high_52w",
                "pct_off_52w_high",
                "close_sma_200_slope",
                "close_sma_200_slope_pct",
            ]
        )
        .collect()
    )

    return long_filter_df, short_filter_df, ind_df


def _agg_scan_results_helper(
    scan_data: pl.DataFrame | pl.LazyFrame,
    rs_data: pl.DataFrame | pl.LazyFrame,
    rs_df: pl.DataFrame | pl.LazyFrame,
    fno_data: pl.DataFrame | pl.LazyFrame,
    industry_data: pl.DataFrame | pl.LazyFrame,
    indicator_data: pl.DataFrame | pl.LazyFrame,
    side: Literal["L", "S"],
) -> pl.DataFrame:
    scan_df = scan_data.lazy()
    rs_df = rs_df.lazy()

    indicator_data = indicator_data.lazy()

    symbol_df = (
        pl.concat(
            [scan_df.select("symbol"), rs_df.select("symbol")], how="vertical_relaxed"
        )
        .unique()
        .with_columns(pl.lit(side).alias("scan_type"))
    )

    _select_cols = [
        "symbol",
        "scan_type",
        "scan_flag",
        "rs",
        "rs_prev_week",
        "change_in_rank",
        "rs_flag",
        "fno_flag",
    ]
    _ind_cols = [
        "macro_economic_sector",
        "sector",
        "industry",
        "basic_industry",
    ]

    res = (
        symbol_df.join(scan_df, on="symbol", how="left")
        .join(rs_data, on="symbol", how="left")
        .join(rs_df, on="symbol", how="left")
        .join(fno_data.lazy(), on="symbol", how="left")
        .join(industry_data.lazy(), on="symbol", how="left")
        .with_columns(cs.ends_with("_flag").fill_null(False))
        .select(_select_cols + _ind_cols)
    )
    if side == "L":
        res = res.join(indicator_data, on="symbol", how="left").select(
            _select_cols + ["close_sma_200_flag", "52w_high_flag"] + _ind_cols
        )

    res = res.collect()

    return res


def agg_scan_results(scan_conf: ScannerConfig, file_paths: FilePathConfig):

    long_data = (
        pl.scan_csv(file_paths.long_stocks)
        .select("symbol")
        .with_columns(pl.lit(True).alias("scan_flag"))
    )
    short_data = (
        pl.scan_csv(file_paths.short_stocks)
        .select("symbol")
        .with_columns(pl.lit(True).alias("scan_flag"))
    )
    rs_data = pl.scan_csv(file_paths.relative_strength).select(
        "symbol", "rs", "rs_prev_week", "change_in_rank"
    )
    fno_data = (
        pl.scan_csv(file_paths.nse_fno_list)
        .select("symbol")
        .with_columns(pl.lit(True).alias("fno_flag"))
    )

    rs_long = (
        rs_data.filter(pl.col("rs") >= scan_conf.LONG_RS)
        .with_columns(pl.lit(True).alias("rs_flag"))
        .select("symbol", "rs_flag")
    )

    rs_short = (
        rs_data.filter(pl.col("rs") <= scan_conf.SHORT_RS)
        .with_columns(pl.lit(True).alias("rs_flag"))
        .select("symbol", "rs_flag")
    )

    industry_data = pl.scan_csv(file_paths.industry_data)
    indicator_data = (
        pl.scan_csv(file_paths.indicator_data)
        .select("symbol", "pct_off_52w_high", "close_sma_200_slope_pct")
        .with_columns(
            pl.when(
                (
                    pl.col("pct_off_52w_high").is_not_null()
                    & (pl.col("pct_off_52w_high") <= scan_conf.PCT_OFF_52W_HIGH)
                )
                | (pl.col("pct_off_52w_high").is_null())
            )
            .then(True)
            .otherwise(False)
            .alias("52w_high_flag"),
            pl.when(
                (
                    pl.col("close_sma_200_slope_pct").is_not_null()
                    & (
                        pl.col("close_sma_200_slope_pct")
                        > scan_conf.CLOSE_SMA_200_SLOPE_PCT
                    )
                )
                | (pl.col("close_sma_200_slope_pct").is_null())
            )
            .then(True)
            .otherwise(False)
            .alias("close_sma_200_flag"),
        )
        .select("symbol", "close_sma_200_flag", "52w_high_flag")
    )

    long_df = _agg_scan_results_helper(
        scan_data=long_data,
        rs_data=rs_data,
        rs_df=rs_long,
        fno_data=fno_data,
        industry_data=industry_data,
        indicator_data=indicator_data,
        side="L",
    )

    short_df = _agg_scan_results_helper(
        scan_data=short_data,
        rs_data=rs_data,
        rs_df=rs_short,
        fno_data=fno_data,
        industry_data=industry_data,
        indicator_data=indicator_data,
        side="S",
    )

    logger.info(
        f"Number of Stocks in agg scan for long: {long_df.height} for short scan: {short_df.height}"
    )

    long_df.write_csv(file_paths.agg_long)
    short_df.write_csv(file_paths.agg_short)

    return long_df, short_df
