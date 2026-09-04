import os
import tempfile

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Override config before importing app. SQLiteStore opens a new connection for
# each operation, so plain `:memory:` would discard the schema after init().
os.environ["ENABLE_LIVE_TRADING"] = "false"
_bootstrap_database: Path | None = None
_configured_database = os.environ.get("DATABASE_PATH")
if not _configured_database or _configured_database == ":memory:":
    _bootstrap_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
    _bootstrap_handle.close()
    _bootstrap_database = Path(_bootstrap_handle.name)
    _configured_database = str(_bootstrap_database)
os.environ["DATABASE_PATH"] = _configured_database

collect_ignore = []
if os.getenv("RUN_LEGACY_DATASET2_READINESS_TESTS") != "1":
    collect_ignore.append("test_dataset2_readiness.py")
if os.getenv("RUN_LEGACY_REVIEW_TESTS") != "1":
    collect_ignore.extend(
        [
            "test_screen_monitoring.py",
            "test_trade_execution_gateway.py",
        ]
    )


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    if _bootstrap_database is not None:
        try:
            _bootstrap_database.unlink(missing_ok=True)
        except OSError:
            pass


from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
from app.storage.sqlite_store import SQLiteStore  # noqa: E402
from app.data.akshare_provider import MarketDataProvider  # noqa: E402


class MockProvider(MarketDataProvider):
    def get_a_share_spot(self) -> pd.DataFrame:
        return pd.DataFrame()

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame:
        return pd.DataFrame()

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        if symbol == "000000":
            raise Exception("Mock error for testing fallback")
        return pd.DataFrame(
            {
                "日期": ["2026-05-27", "2026-05-28"],
                "开盘": [10.0, 10.1],
                "收盘": [10.1, 10.5],
                "最高": [10.2, 10.6],
                "最低": [9.9, 10.0],
                "成交量": [10000, 15000],
                "成交额": [100000, 150000],
                "涨跌幅": [1.0, 3.96],
            }
        )


@pytest.fixture(autouse=True)
def _never_reach_the_local_tonghuashun_client(monkeypatch):
    """Keep the suite off the live 同花顺 client.

    DAILY_BAR_SOURCE_POLICY now defaults to ``tonghuasun_first``, and the
    adapter talks to a real desktop client on loopback. Any test that exercises
    a source chain without pinning a policy would therefore reach it and get
    live bars: that is how this fixture came to exist - four source-chain tests
    started asserting stub dates against today's real quotes.

    Tests that mean to exercise the local adapter pass ``source_policy``
    explicitly, which overrides this default and is unaffected.
    """

    monkeypatch.setattr(settings, "daily_bar_source_policy", "akshare_first")


@pytest.fixture(scope="session")
def test_db():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
    temp_db.close()

    settings.database_path = Path(temp_db.name)
    store = SQLiteStore(settings.database_path)
    store.init()

    yield store

    try:
        os.unlink(temp_db.name)
    except OSError:
        pass


@pytest.fixture
def client(test_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_provider():
    return MockProvider()
