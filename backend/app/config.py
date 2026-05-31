from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A股AI交易驾驶舱"
    app_env: str = "local"
    database_path: Path = Path("./trading_local.sqlite3")
    legacy_data_dir: Path = Path("../../数据集1")
    enable_live_trading: bool = False
    default_cash: float = 100_000
    min_order_lot: int = 100
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.0005
    slippage_rate: float = 0.0005
    backtest_max_participation_rate: float = 0.005
    backtest_default_partial_fill_ratio: float = 0.5
    backtest_default_benchmark_symbol: str = "SH000300"
    realtime_provider: str = "disabled"
    asharehub_api_key: str | None = None
    asharehub_base_url: str = "https://asharehub.com/api"
    realtime_request_timeout_seconds: float = 5.0
    screen_capture_provider: str = "disabled"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
