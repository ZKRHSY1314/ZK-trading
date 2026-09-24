"""Read-only preflight: prove the local Tonghuashun session can actually serve candles.

Run this before the backend, any market-data worker, a full-market refresh, a
candidate scan, a daily decision, a backtest or forecast labelling. Exit code 0
means market data is genuinely coming from the local client; anything else means
it is not, and a run started anyway would be a Sina/Tencent fallback wearing a
Tonghuashun label.

    python scripts/verify_tonghuasun_session.py            # human readable
    python scripts/verify_tonghuasun_session.py --json     # machine readable

It fetches five days of one liquid stock and nothing else. It does not start,
stop or sign in to Voyager, and it never reads or prints the access token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("ENABLE_LIVE_TRADING", "false")

from app.config import settings  # noqa: E402
from app.data.tonghuasun_preflight import verify_market_data  # noqa: E402
from app.data.tonghuasun_provider import TonghuasunMarketDataProvider  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="600519", help="Stock to sample (default 600519).")
    parser.add_argument("--exchange", default="SH", help="Expected exchange for --symbol.")
    parser.add_argument("--adjust", default="qfq", choices=("qfq", "hfq", "none"))
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args(argv)

    product_home = settings.tonghuasun_product_home or None
    provider = TonghuasunMarketDataProvider(
        product_home=product_home,
        timeout=settings.tonghuasun_request_timeout_seconds,
        min_request_interval=settings.tonghuasun_min_request_interval_seconds,
    )
    result = verify_market_data(
        provider=provider,
        symbol=args.symbol,
        expected_exchange=args.exchange,
        adjust=args.adjust,
        product_home=product_home,
    )
    payload = result.as_dict()
    payload["configured_policy"] = settings.daily_bar_source_policy
    payload["product_home"] = str(product_home or "(adapter discovery)")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if result.ready else 1

    print(f"policy       : {payload['configured_policy']}")
    print(f"product home : {payload['product_home']}")
    for check in payload["checks"]:
        print(f"  [{'ok' if check['passed'] else 'FAIL'}] {check['name']}: {check['detail']}")
    for warning in payload["warnings"]:
        print(f"  [warn] {warning}")
    print()
    if result.ready:
        print(f"READY - market data is served by {result.source} ({result.latest_trade_date})")
        return 0
    print("NOT READY - do not start market-data work.")
    print(f"reason: {result.failure_reason}")
    print(
        "\nExit Voyager normally, relaunch it with "
        "scripts\\start_tonghuasun_readonly.ps1, sign in, then run this again."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
