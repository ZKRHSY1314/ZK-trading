import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Override config before importing app
os.environ["ENABLE_LIVE_TRADING"] = "false"
os.environ["DATABASE_PATH"] = ":memory:"

from app.main import app
from app.config import settings
from app.storage.sqlite_store import SQLiteStore
from app.data.akshare_provider import MarketDataProvider
import pandas as pd

class MockProvider(MarketDataProvider):
    def get_a_share_spot(self) -> pd.DataFrame:
        return pd.DataFrame()

    def get_minute_bars(self, symbol: str, period: str = "1") -> pd.DataFrame:
        return pd.DataFrame()

    def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
        if symbol == "000000":
            raise Exception("Mock error for testing fallback")
        return pd.DataFrame({
            "日期": ["2026-05-27", "2026-05-28"],
            "开盘": [10.0, 10.1],
            "收盘": [10.1, 10.5],
            "最高": [10.2, 10.6],
            "最低": [9.9, 10.0],
            "成交量": [10000, 15000],
            "成交额": [100000, 150000],
            "涨跌幅": [1.0, 3.96]
        })

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
