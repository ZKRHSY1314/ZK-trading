from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "trading_local.sqlite3"


class Settings(BaseSettings):
    app_name: str = "A股AI交易驾驶舱"
    app_env: str = "local"
    database_path: Path = DEFAULT_DATABASE_PATH
    # Resolved against backend/ by the importer, so one "..", not two: the old
    # value pointed at D:\数据集1 and the import silently degraded to seed data.
    legacy_data_dir: Path = Path("../数据集1")
    enable_live_trading: bool = False
    default_cash: float = 200_000
    min_order_lot: int = 100
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.0005
    slippage_rate: float = 0.0005
    backtest_max_participation_rate: float = 0.005
    backtest_default_partial_fill_ratio: float = 0.5
    backtest_default_benchmark_symbol: str = "SH000300"
    # 2026-09-03: the opt-in condition above is now met, so this defaults to the
    # local client. A real candle sample was checked against an independent
    # source over 2,260 overlapping days on 40 symbols: qfq closes agree with a
    # median relative difference of 0, amounts likewise, and the only divergence
    # (Beijing 92xxxx) resolved in the local client's favour against Tencent as
    # a third source. Volume is 股 upstream and is normalized to 手 by the
    # adapter. The chain still falls back to Sina then Tencent, which matters:
    # the plugin answers with an EMPTY frame rather than an error once it
    # throttles, so a fallback that carries 成交额 must sit behind it.
    daily_bar_source_policy: str = "tonghuasun_first"
    # Empty means "let the adapter discover it" (TONGHUASUN_AGENT_HOME, then
    # %LOCALAPPDATA%\TonghuasunCodex). Set it when the plugin lives elsewhere;
    # run_stack.ps1 exports the env var, but nothing else does.
    tonghuasun_product_home: str = ""
    # A 500-bar history request costs the local host a few seconds, and it is
    # served by the desktop client rather than a web API. The 5s realtime quote
    # timeout below is too tight for it and produced spurious failures.
    tonghuasun_request_timeout_seconds: float = 30.0
    # The host serializes internally and degrades into returning empty frames
    # when pushed; callers keep their own concurrency and queue behind this.
    tonghuasun_min_request_interval_seconds: float = 1.0
    realtime_provider: str = "disabled"
    asharehub_api_key: str | None = None
    asharehub_base_url: str = "https://asharehub.com/api"
    realtime_request_timeout_seconds: float = 5.0
    screen_capture_provider: str = "disabled"
    screen_capture_allow_real_capture: bool = False
    screen_capture_allowed_windows: str = ""
    screen_capture_block_broker_windows: bool = True
    screen_capture_broker_window_terms: str = "broker,trading,交易,证券,券商,委托,买入,卖出,持仓,资金,同花顺,东方财富,通达信"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def _resolve_project_relative_path(value: Path) -> Path:
    if str(value) == ":memory:" or value.is_absolute():
        return value
    return (PROJECT_ROOT / value).resolve()


settings = Settings()
settings.database_path = _resolve_project_relative_path(settings.database_path)
