"""M2a R1 - source, adjustment and unit metadata DERIVED from a validated path.

The defect this closes
----------------------
`app/data/akshare_provider.py:114` stamps

    frame.attrs["adjustment_mode"] = "qfq" if adjust == "qfq" else "unknown"
    frame.attrs["volume_unit"] = "hand"

The basis is inferred from the *argument we passed*, and the unit is a constant. Neither
is evidence about what came back. Relabelling those `unknown` rows as `none` to satisfy
`--pricing-basis none` would defeat the very gate that exists to catch it.

What is derived here instead
----------------------------
1. **Source** - the exact set of URLs actually requested, recorded by the transport.
2. **Adjustment** - `none` only when the observed URL set is EXACTLY the expected raw set
   for that instrument class. Any missing URL, any extra URL (a factor endpoint, a
   redirect target, a retry to something else) yields `unknown`.
3. **Unit** - measured from the response itself. With raw prices and a raw CNY amount the
   implied VWAP `amount / (volume * k)` must land inside the day's low/high band. `k=1`
   means the volume is in shares, `k=100` means hands. The series must be consistent one
   way and inconsistent the other; anything ambiguous is `unknown`.

Everything fails closed. `unknown` is never promoted, and a caller asking for a basis the
evidence does not support is refused rather than accommodated.

Stock and benchmark routing stay distinct: an index has no amount series, so its unit is
`unknown` by construction and it is excluded from unit gates rather than given a
manufactured value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNKNOWN = "unknown"
RAW = "none"

STOCK_HIST = "https://finance.sina.com.cn/realstock/company/{sym}/hisdata_klc2/klc_kl.js"
STOCK_AMOUNT = ("https://stock.finance.sina.com.cn/stock/api/jsonp.php/"
                "var%20KKE_ShareAmount_{sym}=/StockService.getAmountBySymbol"
                "?_=20&symbol={sym}")
INDEX_HIST = "https://finance.sina.com.cn/realstock/company/{sym}/hisdata_klc2/klc_kl.js"

RAW_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")
INDEX_COLUMNS = ("date", "open", "high", "low", "close", "volume")

#: A unit is accepted only on an overwhelming, one-sided majority.
UNIT_CONSISTENT_MIN = 0.95
UNIT_CONTRADICTION_MAX = 0.05
BAND_LOW, BAND_HIGH = 0.98, 1.02


class ProvenanceError(Exception):
    """The evidence does not support the claim being made."""


@dataclass
class Provenance:
    source: str
    adjustment_mode: str
    volume_unit: str
    instrument_class: str
    observed_urls: tuple
    evidence: dict = field(default_factory=dict)

    def require_basis(self, declared: str) -> None:
        """Refuse to serve a basis the observed path does not establish."""
        if self.adjustment_mode == UNKNOWN:
            raise ProvenanceError(
                "adjustment basis is UNKNOWN for %s: %s. It must not be relabelled %r."
                % (self.source, self.evidence.get("adjustment_reason"), declared))
        if self.adjustment_mode != declared:
            raise ProvenanceError(
                "declared basis %r does not match the derived basis %r for %s"
                % (declared, self.adjustment_mode, self.source))


def expected_urls(symbol: str, instrument_class: str) -> tuple:
    if instrument_class == "stock":
        return (STOCK_HIST.format(sym=symbol), STOCK_AMOUNT.format(sym=symbol))
    if instrument_class == "benchmark":
        return (INDEX_HIST.format(sym=symbol),)
    raise ProvenanceError("unknown instrument class %r" % instrument_class)


def derive_adjustment(symbol, instrument_class, observed_urls):
    """`none` only when the observed path is exactly the expected raw path."""
    want = set(expected_urls(symbol, instrument_class))
    got = set(observed_urls)
    if got == want:
        return RAW, "observed URL set is exactly the expected raw path"
    missing = sorted(want - got)
    extra = sorted(got - want)
    return UNKNOWN, ("observed path is not the validated raw path; missing=%s extra=%s"
                     % (missing[:2], extra[:2]))


def derive_unit(rows):
    """Measure the volume unit from price/amount agreement. Never assume it."""
    usable = [r for r in rows
              if r.get("amount") not in (None, 0)
              and r.get("volume") not in (None, 0)
              and r.get("low") is not None and r.get("high") is not None
              and float(r["volume"]) > 0 and float(r["amount"]) > 0]
    if not usable:
        return UNKNOWN, {"unit_reason": "no row carries both a positive amount and volume",
                         "usable_rows": 0}

    scores = {}
    for name, k in (("share", 1.0), ("hand", 100.0)):
        hits = 0
        for r in usable:
            implied = float(r["amount"]) / (float(r["volume"]) * k)
            if float(r["low"]) * BAND_LOW <= implied <= float(r["high"]) * BAND_HIGH:
                hits += 1
        scores[name] = hits / len(usable)

    evidence = {"usable_rows": len(usable),
                "share_consistency": round(scores["share"], 4),
                "hand_consistency": round(scores["hand"], 4)}

    winners = [n for n, s in scores.items() if s >= UNIT_CONSISTENT_MIN]
    losers = [n for n, s in scores.items() if s <= UNIT_CONTRADICTION_MAX]
    if len(winners) == 1 and len(losers) == 1 and winners[0] != losers[0]:
        evidence["unit_reason"] = "one-sided agreement between amount and the price band"
        return winners[0], evidence
    if not winners:
        evidence["unit_reason"] = "no candidate unit agrees with the price band"
    else:
        evidence["unit_reason"] = "more than one candidate unit is consistent; ambiguous"
    return UNKNOWN, evidence


def derive(symbol, instrument_class, observed_urls, rows, source, declared_basis=None):
    """Full provenance for one fetched series. Fails closed on shape problems.

    Two independent statements about the basis must agree: the observed URL PATH (did we
    call the raw endpoints and nothing else?) and the basis the decoded RESPONSE declares.
    Either alone is weak - a path can be right while the payload is adjusted, and a
    payload can claim anything. Disagreement yields UNKNOWN.
    """
    required = RAW_COLUMNS if instrument_class == "stock" else INDEX_COLUMNS
    if rows:
        missing_cols = [c for c in required if c not in rows[0]]
    else:
        missing_cols = list(required)

    adjustment, reason = derive_adjustment(symbol, instrument_class, observed_urls)
    if missing_cols:
        adjustment = UNKNOWN
        reason = "response is missing required columns %s" % missing_cols

    if instrument_class == "benchmark":
        # An index reports no traded amount, so no unit evidence can exist. That is a
        # property of the instrument, not a gap to paper over: it stays unknown and the
        # benchmark is excluded from unit gates rather than given a fabricated value.
        unit, unit_evidence = UNKNOWN, {
            "unit_reason": "index carries no amount series; unit is not derivable",
            "usable_rows": 0}
    else:
        unit, unit_evidence = derive_unit(rows)

    if adjustment != UNKNOWN and declared_basis is not None:
        if str(declared_basis).strip() != adjustment:
            adjustment = UNKNOWN
            reason = ("the observed raw path and the response's declared basis %r "
                      "disagree" % declared_basis)
        else:
            reason += "; the decoded response declares the same basis"
    elif adjustment != UNKNOWN and declared_basis is None:
        adjustment = UNKNOWN
        reason = "no decoded response basis to corroborate the observed path"

    evidence = {"adjustment_reason": reason, "rows": len(rows),
                "declared_basis": declared_basis}
    evidence.update(unit_evidence)
    return Provenance(source=source, adjustment_mode=adjustment, volume_unit=unit,
                      instrument_class=instrument_class,
                      observed_urls=tuple(observed_urls), evidence=evidence)
