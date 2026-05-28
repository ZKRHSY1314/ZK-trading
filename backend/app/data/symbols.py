import re


def normalize_a_share_code(symbol: str) -> str:
    match = re.search(r"(\d{6})", symbol)
    if not match:
        raise ValueError(f"无法识别A股代码: {symbol}")
    return match.group(1)


def with_exchange_prefix(symbol: str) -> str:
    code = normalize_a_share_code(symbol)
    if code.startswith(("6", "9")):
        return f"SH{code}"
    return f"SZ{code}"
