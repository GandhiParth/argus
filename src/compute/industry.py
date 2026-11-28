import logging

import polars as pl
from nse import NSE

from config.file_paths import FilePathConfig

logger = logging.getLogger(__name__)


def fetch_nse_industry_classification(
    nse_api: NSE, symbol_list: list[str], file_paths: FilePathConfig
) -> tuple[pl.DataFrame, list[str]]:

    n = len(symbol_list)
    logger.info(f"Fetching industry data for {n} symbols")

    def fetch_symbol(sym: str) -> pl.DataFrame:
        res = nse_api.get_detailed_scrip_data(symbol=sym)
        res = res["equityResponse"][0]["secInfo"]

        _keys = [
            "basicIndustry",
            "macro",
            "sector",
            "industryInfo",
        ]
        res = {k: res[k] for k in _keys if k in res}

        out = pl.DataFrame(res).unique()

        if out.height == 0:
            raise ValueError("No Data Fetched")

        out = (
            out.lazy()
            .with_columns(pl.lit(sym).alias("symbol"))
            .select(
                "symbol",
                "basicIndustry",
                "macro",
                "sector",
                "industryInfo",
            )
            .rename(
                {
                    "basicIndustry": "basic_industry",
                    "industryInfo": "industry",
                    "macro": "macro_economic_sector",
                }
            )
            .collect()
        )

        return out

    data = []
    failed_list = []

    # First attempt
    for i, sym in enumerate(symbol_list, start=1):
        try:
            data.append(fetch_symbol(sym))
        except Exception:
            logger.exception(f"Failed industry classification for {sym}")
            failed_list.append(sym)

        if i % 100 == 0:
            logger.info(f"Processed {i}/{n} symbols")

    # Retry failed symbols
    retry_failed = []

    for sym in failed_list:
        try:
            data.append(fetch_symbol(sym))
        except Exception:
            logger.exception(f"Retry failed for industry classification: {sym}")
            retry_failed.append(sym)

    # Combine results
    if data:
        ind_data = pl.concat(data, how="vertical").unique()
    else:
        ind_data = pl.DataFrame(
            schema={
                "symbol": pl.String,
                "basic_industry": pl.String,
                "macro_economic_sector": pl.String,
                "sector": pl.String,
                "industry": pl.String,
            }
        )

    logger.info(
        f"Successfully fetched {ind_data['symbol'].n_unique()} symbols out of {n}"
    )
    logger.info(f"Failed symbols after retry: {len(retry_failed)}")

    ind_data.write_csv(file_paths.industry_data)

    logger.info("Industry data fetching completed")

    return ind_data, retry_failed
