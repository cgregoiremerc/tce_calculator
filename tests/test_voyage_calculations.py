import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from dataclasses import replace
from config import DEFAULT_ASSUMPTIONS as A
from voyage_calculations import (VoyageInputs, compute_voyage, breakeven_ws, breakeven_lumpsum,
                                 get_flat_rate, get_distance, sensitivity_matrix)

BASE = VoyageInputs("Fujairah", "Ras Tanura", "Singapore", 100_000, 420, 3750, ws=100, flat_rate=14.0)
NO_ETS = replace(A, ets_enabled=False)


def test_freight_and_days():
    r = compute_voyage(BASE, NO_ETS)
    assert r.freight_gross == pytest.approx(1_400_000)
    expected_sail = (420 / (13.5 * 24) + 3750 / (13 * 24)) * 1.1
    assert r.sailing_days == pytest.approx(expected_sail)
    assert r.port_days == pytest.approx(3.5)
    assert r.tce == pytest.approx((r.freight_gross - r.total_costs) / r.total_days)


def test_breakeven_ws_gives_target_tce():
    ws = breakeven_ws(BASE, NO_ETS, 15_000)
    r = compute_voyage(replace(BASE, ws=ws), NO_ETS)
    assert r.tce == pytest.approx(15_000, rel=1e-9)


def test_breakeven_lumpsum():
    ls = breakeven_lumpsum(BASE, NO_ETS, 10_000)
    r = compute_voyage(replace(BASE, ws=None, flat_rate=None, lumpsum=ls), NO_ETS)
    assert r.tce == pytest.approx(10_000, rel=1e-9)


def test_missing_flat_rate_returns_none_not_crash():
    assert get_flat_rate("Luanda", "Singapore") is None
    assert get_distance("Luanda", "Singapore") is None


def test_eca_uses_mgo():
    inp = replace(BASE, eca_laden_nm=1000)
    assert compute_voyage(inp, NO_ETS).mgo_tonnes > compute_voyage(BASE, NO_ETS).mgo_tonnes


def test_ets_coverage():
    eu = VoyageInputs("Rotterdam", "Antwerp", "Rotterdam", 50_000, 100, 100, ws=100, flat_rate=10)
    assert compute_voyage(eu, A).ets_cost > 0
    assert compute_voyage(BASE, A).ets_cost == 0
    half = VoyageInputs("Fujairah", "Fujairah", "Marseille (Fos)", 50_000, 0, 4500, ws=100, flat_rate=10)
    assert 0 < compute_voyage(half, A).co2_covered_tonnes < compute_voyage(half, A).co2_tonnes


def test_sensitivity_shape():
    df = sensitivity_matrix(BASE, NO_ETS, [80, 100, 120], [500, 600])
    assert df.shape == (2, 3)
    assert df.iloc[0, 2] > df.iloc[0, 0]      # WS plus haut -> TCE plus haute
    assert df.iloc[0, 1] > df.iloc[1, 1]      # VLSFO plus bas -> TCE plus haute
