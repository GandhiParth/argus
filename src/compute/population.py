import logging

import polars as pl
from config.compute import NSEBasePopConfig

logger = logging.getLogger(__name__)


def gen_nse_base_population(
    data: pl.DataFrame | pl.LazyFrame,
) -> pl.DataFrame:

    _max_timestamp = (
        data.lazy()
        .with_columns(pl.col("timestamp").cast(pl.Date()))
        .select("timestamp")
        .max()
        .collect()
        .item(0, 0)
    )

    logger.info(
        f"Generating Base Population of Stocks for NSE for date: {_max_timestamp}"
    )

    df = (
        data.lazy()
        .with_columns(pl.col("timestamp").cast(pl.Date()))
        .with_columns(
            # Dollar Volume
            [
                (
                    (pl.col("close") * pl.col("volume")).rolling_mean(
                        window_size=NSEBasePopConfig.ADDV
                    )
                )
                .round(2)
                .over(
                    partition_by="symbol",
                    order_by="timestamp",
                    descending=False,
                )
                .alias(f"dollar_volume_sma_{NSEBasePopConfig.ADDV}")
            ]
        )
    )

    ipo_stocks_list = (
        df.filter(
            pl.col(f"dollar_volume_sma_{NSEBasePopConfig.ADDV}").is_null()
            & (pl.col("timestamp") == _max_timestamp)
        )
        .sort("symbol")
        .collect()
        .get_column("symbol")
        .to_list()
    )

    ipo_stocks_df = (
        df.filter(pl.col("symbol").is_in(ipo_stocks_list))
        .group_by("symbol")
        .agg(
            pl.col("timestamp").max().alias("timestamp"),
            (pl.col("close") * pl.col("volume"))
            .mean()
            .round(2)
            .alias("avg_dollar_volume"),
            pl.col("timestamp").len().alias("days_since_ipo"),
        )
        .filter(pl.col("avg_dollar_volume") >= NSEBasePopConfig.IPO_ADDV)
        .with_columns(pl.lit(True).alias("ipo_pop_flag"))
        .sort("symbol")
        .collect()
    )

    base_pop_df = (
        df.filter(
            (pl.col("timestamp") == _max_timestamp)
            & (
                pl.col(f"dollar_volume_sma_{NSEBasePopConfig.ADDV}")
                >= NSEBasePopConfig.STOCKS_ADDV
            )
        )
        .rename({f"dollar_volume_sma_{NSEBasePopConfig.ADDV}": "avg_dollar_volume"})
        .select("symbol", "timestamp", "avg_dollar_volume")
        .with_columns(
            pl.lit(None).alias("days_since_ipo"), pl.lit(False).alias("ipo_pop_flag")
        )
        .collect()
    )

    logger.info(f"Number of stocks in NSE Base Population: {base_pop_df.height}")
    logger.info(f"Number of stocks in NSE IPO Population: {ipo_stocks_df.height}")

    res = ipo_stocks_df.vstack(base_pop_df).sort("symbol")

    return res
