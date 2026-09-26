"""
Universe and data correctness: core building blocks, ETF fallback within a
class, registry fixes, quote-currency handling and the ETF info endpoint.
"""

import datetime
import re
from collections import Counter

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.config import CORE_UNIVERSE
from backend.engine.asset_universe import (
    get_all_etfs,
    get_etf_by_ticker,
    get_etfs_by_asset_class,
    get_primary_etf_for_class,
    resolve_ticker_map,
    strategic_asset_classes,
)


class TestCoreUniverse:
    def test_core_blocks_do_not_duplicate_an_index(self):
        benchmarks = [get_primary_etf_for_class(ac)["benchmark"] for ac in CORE_UNIVERSE]
        assert len(set(benchmarks)) == len(benchmarks)

    def test_every_core_block_resolves(self):
        for ac in CORE_UNIVERSE:
            assert get_primary_etf_for_class(ac) is not None, ac

    def test_satellites_off_by_default(self):
        assert strategic_asset_classes() == list(CORE_UNIVERSE)

    def test_global_bonds_are_gbp_hedged(self):
        for t in CORE_UNIVERSE["global_bonds"]:
            assert "Hedged" in get_etf_by_ticker(t)["name"]

    def test_europe_block_excludes_uk(self):
        etf = get_primary_etf_for_class("europe_ex_uk_equity")
        assert "ex UK" in etf["benchmark"]


class TestFallback:
    def test_falls_back_to_next_candidate(self):
        tmap, skipped = resolve_ticker_map(["uk_equity"], usable=lambda t: t != "ISF.L")
        assert tmap == {"uk_equity": "VUKE.L"}
        assert skipped == {"uk_equity": ["ISF.L"]}

    def test_class_dropped_only_when_no_candidate_works_and_reported(self):
        tmap, skipped = resolve_ticker_map(["europe_ex_uk_equity"], usable=lambda t: False)
        assert tmap == {}
        assert skipped == {"europe_ex_uk_equity": ["VERX.L"]}

    def test_delisted_fund_never_chosen(self):
        assert "VUKC.L" not in [e["ticker"] for e in get_etfs_by_asset_class("corporate_bonds")]


class TestRegistry:
    def test_isins_unique(self):
        c = Counter(e.get("isin") for e in get_all_etfs() if e.get("isin"))
        assert [k for k, v in c.items() if v > 1] == []

    def test_mislabelled_lines_corrected(self):
        assert get_etf_by_ticker("SGLP.L")["asset_class"] == "commodities_gold"
        assert get_etf_by_ticker("ISPY.L")["asset_class"] != "global_small_cap"
        assert "includes UK" in get_etf_by_ticker("VEUR.L")["name"]
        assert "Ultrashort" in get_etf_by_ticker("ERNS.L")["name"]

    def test_etf_info_endpoint_serves_every_registry_entry(self):
        from backend.main import app
        client = TestClient(app)
        for etf in get_all_etfs():
            r = client.get(f"/api/etf/{etf['ticker']}")
            assert r.status_code == 200, (etf["ticker"], r.text)

    def test_every_core_block_has_a_written_name(self):
        """Pages label holdings with these names; a title-cased id reads "Europe Ex Uk Equity"."""
        from backend.main import app
        classes = {c["id"]: c for c in TestClient(app).get("/api/asset-classes").json()}
        for ac in CORE_UNIVERSE:
            assert ac in classes, ac
            # The untitled fallback has no description, and title-cases acronyms.
            assert classes[ac]["description"], ac
            assert not re.search(r"(Uk|Us|Esg|Reits?)", classes[ac]["name"]), classes[ac]["name"]


class TestQuoteUnits:
    def _df(self, closes):
        idx = pd.bdate_range("2026-01-01", periods=len(closes))
        c = np.array(closes, dtype=float)
        return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1}, index=idx)

    def test_pence_scaled_to_pounds_and_tagged_gbp(self):
        from backend.data.market_data import normalise_quote_units
        out = normalise_quote_units(self._df([7500, 7550, 7600, 7580, 7620, 7700]), "GBp")
        assert out["Close"].iloc[0] == pytest.approx(75.0)
        assert out.attrs["currency"] == "GBP"

    def test_hundredfold_glitch_repaired(self):
        from backend.data.market_data import normalise_quote_units
        out = normalise_quote_units(self._df([75, 76, 7600, 77, 78, 79]), "GBP")
        assert out["Close"].iloc[2] == pytest.approx(76.0)

    def test_detected_currency_beats_registry(self):
        from backend.data.returns import _ticker_currency
        df = self._df([1, 2, 3])
        df.attrs["currency"] = "GBP"
        assert get_etf_by_ticker("EQQQ.L")["currency"] == "USD"  # registry says USD
        assert _ticker_currency("EQQQ.L", df) == "GBP"             # Yahoo says sterling
        assert _ticker_currency("EQQQ.L") == "USD"                  # unknown → registry

    def test_ledger_survives_price_unit_change(self):
        from backend.db.ledger_store import apply_prices
        from backend.db.models import Holding
        h = Holding(ticker="X", quantity=10.0, average_cost=7500.0, current_price=7600.0)
        apply_prices([h], {"X": (76.5, datetime.date(2026, 9, 24))})
        assert h.quantity * h.current_price == pytest.approx(10 * 7600.0, rel=0.01)
