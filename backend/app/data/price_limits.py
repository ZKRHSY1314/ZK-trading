"""A-share board inference and configurable price-limit thresholds.

The values here are conservative signal thresholds, not exchange rule text.
Keep them centralized so future rule-effective-date changes can be handled
without burying board logic inside strategy code.
"""
from __future__ import annotations


def infer_board_type(code: str, name: str | None = None) -> str:
    """
    Infer the board type from a 6-digit A-share code and stock name.
    """
    code = code.upper().replace("SH", "").replace("SZ", "").replace("BJ", "")
    normalized_name = (name or "").upper().replace(" ", "")
    if normalized_name.startswith(("*ST", "ST", "S*ST", "SST")):
        return "st"
    
    if code.startswith("300") or code.startswith("301"):
        return "chinext"
    
    if code.startswith("688"):
        return "star"
        
    if code.startswith(("8", "4", "9")):
        return "bse"
        
    return "main"


DEFAULT_LIMIT_UP_THRESHOLDS = {
    "main": 9.8,
    "st": 4.8,
    "chinext": 19.5,
    "star": 19.5,
    "bse": 29.0,
}


def limit_up_threshold(board_type: str, overrides: dict[str, float] | None = None) -> float:
    """
    Return the conservative percentage threshold for a limit-up judgment.
    """
    mapping = DEFAULT_LIMIT_UP_THRESHOLDS | (overrides or {})
    return mapping.get(board_type, 9.8)
