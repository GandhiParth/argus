import logging

import polars as pl

from brokers.kite import KiteHistorical, fetch_instruments
from config.base import StorageConfig
from config.brokers import KiteConfig

logger = logging.getLogger()


def _nse_ins_pop_filter(file_path: str) -> pl.DataFrame:
    """
    file_path : str

    Filter the Instrument List to form the Base population of stocks
    """

    exclude_amc = [
        "DSPAMC",
        "EDELAMC",
        "GROWWAMC",
        "HDFCAMC",
        "MIRAEAMC",
        "SBIAMC",
        "UTIAMC",
        "ZERODHAAMC",
    ]

    exclude_conditions = [
        pl.col("name").str.contains(pattern)
        for pattern in ["%", "GOI TBILL", "ETF", *exclude_amc]
    ] + [pl.col("symbol").str.ends_with("INAV")]

    df = (
        pl.scan_csv(file_path)
        .select("instrument_token", "symbol", "name", "tick_size", "segment")
        .with_columns(
            pl.col("symbol")
            .str.split("-")
            .list.get(1, null_on_oob=True)
            .fill_null("EQ")
            .alias("suffix")
        )
        .filter(
            (pl.col("segment") == "NSE")
            & (pl.col("name").str.len_chars() > 0)
            & (pl.col("suffix") == "EQ")
            & ~pl.any_horizontal(exclude_conditions)
        )
        .select("symbol", "instrument_token")
        .collect()
    )

    return df


def fetch_nse_hist_data(
    kite_conn, start_date: str, end_date: str, frequency: str, save_path: str
):
    """
    start_date: str in YYYY-MM-DD HH:MM:SS
    frequency
    """

    # kite_conn = KiteLogin(credentials_path=KITE_CREDENTIALS_PATH).auto_login()
    ins_df = fetch_instruments(kite=kite_conn, exchange=kite_conn.EXCHANGE_NSE)
    logger.info(f"{ins_df.height} symbols fetched from Kite Instrument List")
    _ins_path = StorageConfig().store_root(save_path) / KiteConfig.NSE_INSTRUMENTS_PATH
    ins_df.write_csv(_ins_path)

    df = _nse_ins_pop_filter(file_path=_ins_path)

    logger.info(f"NSE Data will be fetched for {df.height} symbols")

    kite_hist = KiteHistorical(
        kite_conn,
        instruments_df=df,
        config=KiteConfig,
    )

    _tbl_name = KiteConfig.get_db_tbl(
        data_type=KiteConfig.TYP_STOCKS, frequency=frequency, failed_tbl=False
    )
    _fl_tbl_name = KiteConfig.get_db_tbl(
        data_type=KiteConfig.TYP_STOCKS, frequency=frequency, failed_tbl=True
    )

    kite_hist.get_historical_data(
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        db_conn=KiteConfig.DB_CONN,
        insert_table_name=_tbl_name,
        failed_table_name=_fl_tbl_name,
    )


def fetch_nse_fno_stocks(kite_conn) -> pl.DataFrame:

    ins_df = fetch_instruments(kite=kite_conn, exchange=kite_conn.EXCHANGE_NFO)
    res = (
        ins_df.filter(pl.col("instrument_type") == "FUT")
        .select("name")
        .unique()
        .rename({"name": "symbol"})
    )

    logger.info(f"# of stocks in NSE FnO are: {res.height}")

    return res
