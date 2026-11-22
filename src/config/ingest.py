from config.base import StorageConfig


class EditConfig:
    # Paths
    TMP_DATA_PATH = StorageConfig().tmp_root("nse")
    STORE_DATA_PATH = StorageConfig().store_root("nse")
    INDICES_DOWNLOAD_PATH = TMP_DATA_PATH / "indices"
    DB_PATH = STORE_DATA_PATH / "data.db"
    DB_CONN = f"sqlite:///{DB_PATH}"

    # Table ID where Industry Classification is Downloaded
    CLASSIFICATION_TABLE_ID = "industry_classification"


class NSEIndustryConfig(EditConfig):
    # NSE_URL = "https://www.nseindia.com"
    NSE_URL = "https://www.nseindia.com/get-quote/equity/SHAILY/Shaily-Engineering-Plastics-Limited"

    @staticmethod
    def get_db_tbl(tbl_name: str, failed_tbl: bool):
        prefix = "failed_" if failed_tbl else ""
        return f"{prefix}nse_{tbl_name}"
