import logging

import polars as pl
from nse import NSE

from config.file_paths import FilePathConfig

logger = logging.getLogger(__name__)


def fetch_nse_industry_classification(
    nse_api: NSE, symbol_list: list[str], file_paths: FilePathConfig
) -> pl.DataFrame:

    n = len(symbol_list)
    logger.info(f"Fetching Data for {n} symbols")

    failed_list = []
    ind_data = None
    c = 0
    for sym in symbol_list:
        try:
            res = nse_api.get_detailed_scrip_data(symbol=sym)
            res = res["equityResponse"][0]["secInfo"]
            df = (
                pl.DataFrame(res)
                .lazy()
                .with_columns(pl.lit(sym).alias("symbol"))
                .select("symbol", "basicIndustry", "macro", "sector", "industryInfo")
                .unique()
                .rename(
                    {
                        "basicIndustry": "basic_industry",
                        "industryInfo": "industry",
                        "macro": "macro_economic_sector",
                    }
                )
                .collect()
            )

            if ind_data is None:
                ind_data = df
            else:
                ind_data = ind_data.vstack(df)

            c += 1
            if c % 100 == 0:
                logger.info(f"Fetch Indsutry data for {c}/{n} symbols")

        except Exception:
            logger.error(f"Failed Indsutry Classification for Symbol {sym}")
            failed_list.append(sym)

    for sym in failed_list:
        try:
            res = nse_api.get_detailed_scrip_data(symbol=sym)
            res = res["equityResponse"][0]["secInfo"]
            df = (
                pl.DataFrame(res)
                .lazy()
                .with_columns(pl.lit(sym).alias("symbol"))
                .select("symbol", "basicIndustry", "macro", "sector", "industryInfo")
                .unique()
                .rename(
                    {
                        "basicIndustry": "basic_industry",
                        "industryInfo": "industry",
                        "macro": "macro_economic_sector",
                    }
                )
                .collect()
            )

            if ind_data is None:
                ind_data = df
            else:
                ind_data = ind_data.vstack(df)

            c += 1
            if c % 100 == 0:
                logger.info(f"Fetch Indsutry data for {c}/{n} symbols")

        except Exception:
            logger.error(f"Failed Indsutry Classification for Symbol {sym}")

    logger.info(f"Fetch Indsutry data for {ind_data.height} symbols")

    ind_data.write_csv(file_paths.industry_data)
    logger.info("Industry Data Fetching Completed")

    return failed_list
