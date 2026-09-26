"""
Backtest Price Panel — point-in-time GBP daily closes
======================================================
Builds the daily GBP price panel the walk-forward backtest runs on, with every
cleaning step CAUSAL (a value at date d depends only on data dated ≤ d):

  - Pence listings (Yahoo `GBp`) are scaled to GBP.
  - 100× unit glitches are fixed against a TRAILING median of earlier prints.
    `market_data.normalise_quote_units` uses the whole-series median, which
    looks at future prices — fine for the live app, not for a backtest.
  - Foreign-currency lines are converted with the last FX print dated BEFORE
    the price date (forward fill only, never back-filled): Yahoo's daily FX
    close is struck after the 16:30 LSE close, so same-day FX would be a few
    hours in the future.

Prices are TOTAL-RETURN indices rebuilt from raw closes and ex-date dividends,
    TR_t = TR_{t-1} × (Close_t + Div_t) / Close_{t-1},
which is causal (a dividend is known on its ex-date). Yahoo's own adjusted
close is NOT used: for pence-quoted LSE lines (ISF.L, IEEM.L, IWDP.L) it omits
the dividend adjustment, understating e.g. FTSE 100 returns by ~4%/yr.
Raw closes are split-adjusted, so their LEVELS depend on later splits, but
every ratio P(t2)/P(t1) uses only events in (t1, t2] — and the backtest only
uses ratios (returns; units × price against the purchase price).

Pure functions except `download_panel` (network) and save/load (disk).
"""

import datetime
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Yahoo FX symbols quote units of foreign currency per 1 GBP.
FX_SYMBOLS: dict[str, str] = {"USD": "GBPUSD=X", "EUR": "GBPEUR=X", "JPY": "GBPJPY=X"}
UNIT_GLITCH_RATIO: float = 30.0      # a print this far from the trailing median is a 100× unit error
UNIT_GLITCH_WINDOW: int = 20         # trailing prints in the reference median
UNIT_GLITCH_MIN_PERIODS: int = 5


@dataclass(frozen=True)
class PricePanel:
    """Raw inputs: daily closes in quote currency, the currency per ticker, and daily FX."""
    local: pd.DataFrame            # index = date, columns = tickers (NaN = no print)
    currency: dict[str, str]       # ticker -> ISO code after pence scaling (GBP, USD, ...)
    fx: pd.DataFrame               # index = date, columns = ISO codes; units per 1 GBP
    downloaded_at: str = ""


# =============================================================================
# CAUSAL CLEANING
# =============================================================================

def causal_unit_fix(
    close: pd.Series,
    ratio: float = UNIT_GLITCH_RATIO,
    window: int = UNIT_GLITCH_WINDOW,
    min_periods: int = UNIT_GLITCH_MIN_PERIODS,
) -> tuple[pd.Series, int]:
    """
    Rescale prints that are ~100× off the median of the previous `window`
    (already-fixed) prints. Sequential, so a long glitch run cannot drag the
    reference with it, and each decision uses only earlier prints.

    Returns:
        (fixed series with NaNs preserved, number of prints rescaled)
    """
    x = close.dropna()
    vals = x.to_numpy(dtype=float).copy()
    n_fixed = 0
    for i in range(len(vals)):
        if i < min_periods:
            continue
        ref = float(np.median(vals[max(0, i - window):i]))
        if ref <= 0:
            continue
        if vals[i] > ratio * ref:
            vals[i] /= 100.0
            n_fixed += 1
        elif vals[i] < ref / ratio:
            vals[i] *= 100.0
            n_fixed += 1
    out = close.copy()
    out.loc[x.index] = vals
    return out, n_fixed


MAX_DIVIDEND_YIELD_PER_EVENT: float = 0.25   # a larger dividend/price is a pence/pound mix-up


def total_return_index(close: pd.Series, dividends: pd.Series) -> tuple[pd.Series, int]:
    """
    Reinvested-dividend index TR_t = TR_{t-1} × (C_t + D_t) / C_{t-1}, anchored at
    the first close. A dividend dated on a day without a close is applied on the
    next close. A dividend above 25% of the previous close is taken to be in the
    wrong unit (pence vs pounds) and divided by 100 — a per-event, causal check.

    Returns:
        (total-return series on the non-NaN close dates, number of dividends rescaled)
    """
    c = close.dropna()
    if c.empty:
        return c, 0
    d = dividends[dividends > 0].dropna()
    pos = c.index.searchsorted(d.index)          # next close on/after the ex-date
    keep = pos < len(c)
    amounts = np.zeros(len(c))
    np.add.at(amounts, pos[keep], d.to_numpy(dtype=float)[keep])
    div = pd.Series(amounts, index=c.index)

    prev = c.shift(1)
    yld = div / prev
    bad = yld > MAX_DIVIDEND_YIELD_PER_EVENT
    div = div.where(~bad, div / 100.0)
    growth = ((c + div) / prev).fillna(1.0)
    return float(c.iloc[0]) * growth.cumprod(), int(bad.sum())


def fx_for_prices(fx: pd.Series, index: pd.DatetimeIndex, strictly_before: bool = True) -> pd.Series:
    """
    For each price date d, the last FX print dated before d (or on/before d when
    `strictly_before` is False) — a forward fill only. Dates before the first
    usable FX print stay NaN (no back-fill).
    """
    fx = fx.dropna().sort_index()
    pos = fx.index.searchsorted(index, side="left" if strictly_before else "right") - 1
    vals = np.where(pos >= 0, fx.to_numpy(dtype=float)[np.clip(pos, 0, None)], np.nan)
    return pd.Series(vals, index=index)


def to_gbp(local: pd.Series, currency: str, fx: pd.DataFrame, strictly_before: bool = True) -> pd.Series:
    """Local-currency closes → GBP. Unknown FX leaves the prices NaN rather than guessing."""
    ccy = (currency or "GBP").upper()
    if ccy == "GBP":
        return local
    if ccy not in fx.columns:
        logger.warning(f"No FX series for {ccy}; {local.name} excluded (all NaN)")
        return local * np.nan
    return local / fx_for_prices(fx[ccy], local.index, strictly_before)


def gbp_prices(panel: PricePanel, fx_strictly_before: bool = True) -> pd.DataFrame:
    """Daily GBP closes for every ticker in the panel (NaN where no print)."""
    cols = {}
    for t in panel.local.columns:
        cols[t] = to_gbp(panel.local[t], panel.currency.get(t, "GBP"), panel.fx, fx_strictly_before)
    return pd.DataFrame(cols).sort_index()


def trading_calendar(gbp: pd.DataFrame, min_share: float = 0.5) -> pd.DatetimeIndex:
    """Days on which at least `min_share` of tickers that have started trading printed a price."""
    started = gbp.notna().cummax()
    printed = gbp.notna().sum(axis=1)
    live = started.sum(axis=1).clip(lower=1)
    return gbp.index[(printed / live) >= min_share]


# =============================================================================
# DOWNLOAD / STORAGE
# =============================================================================

def _scale_pence(close: pd.Series, currency: Optional[str]) -> tuple[pd.Series, str]:
    from backend.data.market_data import _PENCE_CODES
    if currency in _PENCE_CODES:
        return close / 100.0, "GBP"
    return close, (currency or "GBP").upper()


def clean_ticker(close: pd.Series, dividends: pd.Series, currency: Optional[str]) -> tuple[pd.Series, str]:
    """
    Raw Yahoo close + dividends → causal total-return index in whole currency
    units: unit-glitch fix, dividend reinvestment, then pence scaling.

    Returns:
        (total-return series, ISO currency after pence scaling)
    """
    name = close.name
    close, n_fixed = causal_unit_fix(close)
    if n_fixed:
        logger.warning(f"{name}: rescaled {n_fixed} prints with a 100× unit glitch (causal check)")
    tr, n_div_fixed = total_return_index(close, dividends)
    if n_div_fixed:
        logger.warning(f"{name}: {n_div_fixed} dividends looked like the wrong unit and were ÷100")
    return _scale_pence(tr.rename(name), currency)


def download_panel(tickers: list[str]) -> PricePanel:
    """
    Full daily history for each ticker and the FX it needs, from Yahoo Finance.
    Quote currency is Yahoo's (registry as fallback). Tickers without data are
    left out and logged.
    """
    import yfinance as yf
    from backend.data.market_data import _yahoo_quote_currency
    from backend.engine.asset_universe import get_etf_by_ticker

    closes, currency = {}, {}
    for t in tickers:
        df = yf.download(t, period="max", interval="1d", progress=False,
                         auto_adjust=False, actions=True)
        if df is None or df.empty:
            logger.warning(f"{t}: no data from Yahoo — left out of the panel")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        close = df["Close"].astype(float).rename(t)
        divs = df["Dividends"].astype(float) if "Dividends" in df.columns else close * 0.0
        ccy = _yahoo_quote_currency(t) or (get_etf_by_ticker(t) or {}).get("currency") or "GBP"
        closes[t], currency[t] = clean_ticker(close, divs, ccy)
        logger.info(f"{t}: {close.notna().sum()} prints {close.index.min():%Y-%m-%d}..{close.index.max():%Y-%m-%d} {ccy}")

    fx = {}
    for ccy in sorted({c for c in currency.values() if c != "GBP"}):
        sym = FX_SYMBOLS.get(ccy)
        if sym is None:
            logger.warning(f"No FX symbol for {ccy}")
            continue
        df = yf.download(sym, period="max", interval="1d", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        s = df["Close"].astype(float)
        s.index = pd.to_datetime(s.index).tz_localize(None)
        fx[ccy] = s[~s.index.duplicated(keep="last")].sort_index()

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    return PricePanel(pd.DataFrame(closes).sort_index(), currency, pd.DataFrame(fx).sort_index(), stamp)


def save_panel(panel: PricePanel, directory: str) -> None:
    os.makedirs(directory, exist_ok=True)
    panel.local.to_parquet(os.path.join(directory, "closes_local.parquet"))
    panel.fx.to_parquet(os.path.join(directory, "fx.parquet"))
    with open(os.path.join(directory, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"currency": panel.currency, "downloaded_at": panel.downloaded_at}, f, indent=2)


def load_panel(directory: str) -> Optional[PricePanel]:
    """The saved panel, or None if the directory has no complete snapshot."""
    paths = [os.path.join(directory, p) for p in ("closes_local.parquet", "fx.parquet", "meta.json")]
    if not all(os.path.exists(p) for p in paths):
        return None
    with open(paths[2], encoding="utf-8") as f:
        meta = json.load(f)
    return PricePanel(pd.read_parquet(paths[0]), meta["currency"], pd.read_parquet(paths[1]),
                      meta.get("downloaded_at", ""))
