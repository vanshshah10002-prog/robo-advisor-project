"""
Construction — what a portfolio was built from, and reusing a preview
======================================================================
`build_optimised_portfolio` is expensive (prices, estimation, several
solves) and depends only on the risk score and the day's data, not on the
amount invested. So:

- `ConstructionCache` keeps one result per risk score for a few hours. A
  preview and the later "open this portfolio" then use the SAME construction:
  the investor gets exactly the mix they were shown.
- `snapshot_from_result` distils a result into the record stored with a
  portfolio: weights, per-fund estimates, correlations, policy, frontier.
  It is what the portfolio page shows under "how it was built", and it never
  changes after the portfolio is opened.

Pure apart from the cache's clock.
"""

import datetime
import threading
import time
from typing import Callable, Optional

from backend.config import CONSTRUCTION_CACHE_TTL_SECONDS, VOL_CALIBRATION_MULTIPLIER
from backend.engine.policy import sleeve_of

SNAPSHOT_VERSION = 1


class ConstructionCache:
    """
    One construction per risk score (rounded to 0.01), valid for `ttl` seconds.
    Thread-safe; a failed build is not cached.
    """

    def __init__(self, ttl: float = CONSTRUCTION_CACHE_TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._items: dict[float, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(risk_score: float) -> float:
        return round(float(risk_score), 2)

    def get(self, risk_score: float) -> Optional[dict]:
        with self._lock:
            item = self._items.get(self.key(risk_score))
            if item is None:
                return None
            built_at, result = item
            if self._clock() - built_at > self._ttl:
                del self._items[self.key(risk_score)]
                return None
            return result

    def get_or_build(self, risk_score: float, build: Callable[[], dict]) -> tuple[dict, bool]:
        """
        Returns:
            (result, reused): `reused` is True when the result came from the cache.
        """
        cached = self.get(risk_score)
        if cached is not None:
            return cached, True
        result = build()
        with self._lock:
            self._items[self.key(risk_score)] = (self._clock(), result)
        return result, False

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


construction_cache = ConstructionCache()


def scaled_allocations(result: dict, amount_gbp: float) -> list[dict]:
    """The result's allocations with GBP amounts for this investment, largest first."""
    out = []
    for a in result.get("allocations", []):
        out.append({**a, "amount_gbp": round(float(a["weight"]) * amount_gbp, 2)})
    return sorted(out, key=lambda a: a["weight"], reverse=True)


def policy_summary(result: dict) -> Optional[dict]:
    """The policy figures, rounded (the growth target is 0.1 × risk in floating point)."""
    policy = result.get("policy")
    if not policy:
        return None
    return {k: ([round(float(x), 4) for x in v] if isinstance(v, (list, tuple)) else round(float(v), 4))
            for k, v in policy.items()}


def _frontier_points(result: dict) -> list[dict]:
    """
    Frontier (return, volatility) pairs on the same volatility scale as the
    portfolio: the optimiser's frontier uses model volatility, the portfolio
    reports calibrated volatility, so the frontier is calibrated here too.
    """
    points = []
    for p in result.get("frontier") or []:
        points.append({
            "expected_return": round(float(p["expected_return"]), 6),
            "volatility": round(float(p["volatility"]) * VOL_CALIBRATION_MULTIPLIER, 6),
        })
    return sorted(points, key=lambda p: p["volatility"])


def snapshot_from_result(result: dict, risk_score: float, as_of: Optional[datetime.date] = None) -> dict:
    """
    The permanent record of how a portfolio was built.

    Tolerates results without estimation inputs (older optimiser versions,
    test doubles): those fields are then empty rather than invented.
    """
    inputs = result.get("inputs") or {}
    mu = inputs.get("expected_returns") or {}
    vol = inputs.get("volatilities") or {}
    corr = inputs.get("correlation") or {"tickers": [], "matrix": []}
    perf = result.get("performance") or {}

    holdings = []
    for a in result.get("allocations", []):
        t, ac = a["ticker"], a["asset_class"]
        holdings.append({
            "ticker": t,
            "asset_class": ac,
            "sleeve": sleeve_of(ac),
            "weight": round(float(a["weight"]), 6),
            "expense_ratio": a.get("expense_ratio"),
            "expected_return": mu.get(t),
            "volatility": vol.get(t),
        })
    holdings.sort(key=lambda h: h["weight"], reverse=True)

    return {
        "version": SNAPSHOT_VERSION,
        "as_of": (as_of or datetime.date.today()).isoformat(),
        "risk_score": round(float(risk_score), 4),
        "risk_free_rate": result.get("risk_free_rate"),
        "expected_return": perf.get("expected_return"),
        "expected_volatility": perf.get("volatility"),
        "sharpe_ratio": perf.get("sharpe_ratio"),
        "total_expense_ratio": result.get("total_expense_ratio"),
        "policy": policy_summary(result),
        "holdings": holdings,
        "correlation": {"tickers": list(corr.get("tickers", [])), "matrix": corr.get("matrix", [])},
        "frontier": _frontier_points(result),
        "etf_fallbacks": result.get("etf_fallbacks") or {},
        "crisis_regime": bool(result.get("crisis_regime", False)),
        "vol_calibration": inputs.get("vol_calibration", VOL_CALIBRATION_MULTIPLIER),
    }
