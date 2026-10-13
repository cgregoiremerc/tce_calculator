"""Moteur de calcul unique pour les pages TCE et Lumpsum."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Optional

from config import DISTANCES, FLAT_RATES, PORTS, Assumptions


# --------------------------------------------------------------------------- #
# Données d'entrée / sortie
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VoyageInputs:
    ballast_port: str
    load_port: str
    discharge_port: str
    cargo_mt: float
    ballast_nm: float
    laden_nm: float
    ws: Optional[float] = None            # mode TCE (Worldscale)
    flat_rate: Optional[float] = None     # USD/t, mode TCE
    lumpsum: Optional[float] = None       # USD, mode Lumpsum
    wait_days_load: float = 0.0
    wait_days_discharge: float = 0.0
    eca_ballast_nm: float = 0.0
    eca_laden_nm: float = 0.0


@dataclass
class VoyageResult:
    freight_gross: float
    commissions: float
    net_freight: float
    bunker_vlsfo_cost: float
    bunker_mgo_cost: float
    ets_cost: float
    port_costs: float
    total_costs: float
    sailing_days: float
    port_days: float
    total_days: float
    tce: float
    vlsfo_tonnes: float
    mgo_tonnes: float
    co2_tonnes: float
    co2_covered_tonnes: float

    @property
    def bunker_cost(self) -> float:
        return self.bunker_vlsfo_cost + self.bunker_mgo_cost

    def cost_breakdown(self) -> dict[str, float]:
        return {
            "Commissions": self.commissions,
            "Bunker VLSFO": self.bunker_vlsfo_cost,
            "Bunker MGO (ECA)": self.bunker_mgo_cost,
            "EU ETS": self.ets_cost,
            "Frais de port": self.port_costs,
        }


# --------------------------------------------------------------------------- #
# Distances et flat rates
# --------------------------------------------------------------------------- #
def fetch_distance_api(a: str, b: str) -> Optional[float]:
    """Branche ici l'API de distances (ex. Atobviac).

    Lit DISTANCE_API_URL et, si besoin, DISTANCE_API_CA_BUNDLE (certificat
    interne). La vérification SSL n'est JAMAIS désactivée. Renvoie None si
    l'API n'est pas configurée ou en cas d'échec.
    """
    url = os.environ.get("DISTANCE_API_URL")
    if not url:
        return None
    try:
        import requests

        verify = os.environ.get("DISTANCE_API_CA_BUNDLE", True)
        r = requests.get(url, params={"from": a, "to": b}, timeout=10, verify=verify)
        r.raise_for_status()
        return float(r.json()["distance_nm"])
    except Exception:
        return None


@lru_cache(maxsize=2048)
def get_distance(a: str, b: str) -> Optional[float]:
    """Distance en nm (0 si même port, None si inconnue). Mise en cache."""
    if a == b:
        return 0.0
    d = DISTANCES.get(frozenset((a, b)))
    if d is not None:
        return d
    return fetch_distance_api(a, b)


def get_flat_rate(load_port: str, discharge_port: str) -> Optional[float]:
    """Flat rate USD/t, ou None si la paire n'existe pas (saisie manuelle)."""
    return FLAT_RATES.get((load_port, discharge_port))


def eca_nm_for_leg(a: str, b: str, leg_nm: float) -> float:
    """Milles en zone ECA sur un tronçon (approche des deux ports, plafonnée)."""
    if leg_nm <= 0:
        return 0.0
    pa, pb = PORTS.get(a, {}), PORTS.get(b, {})
    return float(min(leg_nm, pa.get("eca_nm", 0) + pb.get("eca_nm", 0)))


def default_wait_days(port: str) -> float:
    from config import DEFAULT_WAIT_DAYS

    return DEFAULT_WAIT_DAYS.get(port, 0.0)


# --------------------------------------------------------------------------- #
# Calcul
# --------------------------------------------------------------------------- #
def _leg_ets_coverage(a: str, b: str) -> float:
    ea, eb = PORTS.get(a, {}).get("eu", False), PORTS.get(b, {}).get("eu", False)
    if ea and eb:
        return 1.0
    if ea or eb:
        return 0.5
    return 0.0


def freight_revenue(inp: VoyageInputs) -> float:
    if inp.lumpsum is not None:
        return float(inp.lumpsum)
    if inp.ws is None or inp.flat_rate is None:
        raise ValueError("WS et flat rate requis (ou lumpsum).")
    return inp.flat_rate * inp.ws / 100.0 * inp.cargo_mt


def compute_voyage(inp: VoyageInputs, a: Assumptions) -> VoyageResult:
    freight = freight_revenue(inp)
    comm_pct = (a.address_commission + a.brokerage) / 100.0
    commissions = freight * comm_pct

    # --- Jours ---
    bal_days_raw = inp.ballast_nm / (a.speed_ballast * 24)
    lad_days_raw = inp.laden_nm / (a.speed_laden * 24)
    bal_days = bal_days_raw * (1 + a.weather_margin)
    lad_days = lad_days_raw * (1 + a.weather_margin)
    sailing_days = bal_days + lad_days
    days_load = a.load_days + inp.wait_days_load
    days_disch = a.discharge_days + inp.wait_days_discharge
    port_days = days_load + days_disch
    total_days = sailing_days + port_days

    # --- Soutes en mer (MGO sur la part ECA, VLSFO sinon) ---
    def leg_fuel(days: float, nm: float, eca_nm: float, cons: float) -> tuple[float, float]:
        share = min(1.0, eca_nm / nm) if nm > 0 else 0.0
        total = days * cons
        return total * (1 - share), total * share  # (vlsfo, mgo)

    v_b, m_b = leg_fuel(bal_days, inp.ballast_nm, inp.eca_ballast_nm, a.cons_ballast)
    v_l, m_l = leg_fuel(lad_days, inp.laden_nm, inp.eca_laden_nm, a.cons_laden)

    # --- Soutes au port (MGO si port en ECA) ---
    def port_fuel(port: str, days: float) -> tuple[float, float]:
        t = days * a.cons_port
        return (0.0, t) if PORTS.get(port, {}).get("eca") else (t, 0.0)

    v_pl, m_pl = port_fuel(inp.load_port, days_load)
    v_pd, m_pd = port_fuel(inp.discharge_port, days_disch)

    vlsfo_t = v_b + v_l + v_pl + v_pd
    mgo_t = m_b + m_l + m_pl + m_pd
    vlsfo_cost = vlsfo_t * a.vlsfo_price
    mgo_cost = mgo_t * a.mgo_price

    # --- EU ETS ---
    co2_total = vlsfo_t * a.co2_factor_vlsfo + mgo_t * a.co2_factor_mgo
    co2_covered = 0.0
    if a.ets_enabled:
        def emis(v: float, m: float) -> float:
            return v * a.co2_factor_vlsfo + m * a.co2_factor_mgo

        co2_covered += emis(v_b, m_b) * _leg_ets_coverage(inp.ballast_port, inp.load_port)
        co2_covered += emis(v_l, m_l) * _leg_ets_coverage(inp.load_port, inp.discharge_port)
        if PORTS.get(inp.load_port, {}).get("eu"):
            co2_covered += emis(v_pl, m_pl)
        if PORTS.get(inp.discharge_port, {}).get("eu"):
            co2_covered += emis(v_pd, m_pd)
    ets_cost = co2_covered * a.ets_phase_in * a.eua_price * a.eur_usd

    port_costs = a.port_cost_load + a.port_cost_discharge
    total_costs = commissions + vlsfo_cost + mgo_cost + ets_cost + port_costs
    net_freight = freight - commissions
    tce = (freight - total_costs) / total_days if total_days > 0 else 0.0

    return VoyageResult(
        freight_gross=freight, commissions=commissions, net_freight=net_freight,
        bunker_vlsfo_cost=vlsfo_cost, bunker_mgo_cost=mgo_cost, ets_cost=ets_cost,
        port_costs=port_costs, total_costs=total_costs, sailing_days=sailing_days,
        port_days=port_days, total_days=total_days, tce=tce, vlsfo_tonnes=vlsfo_t,
        mgo_tonnes=mgo_t, co2_tonnes=co2_total, co2_covered_tonnes=co2_covered,
    )


# --------------------------------------------------------------------------- #
# Analyses
# --------------------------------------------------------------------------- #
def _costs_excl_commission(r: VoyageResult) -> float:
    return r.total_costs - r.commissions


def breakeven_ws(inp: VoyageInputs, a: Assumptions, target_tce: float = 0.0) -> Optional[float]:
    """WS pour atteindre `target_tce` (USD/jour). La TCE est linéaire en WS."""
    if inp.flat_rate is None or inp.lumpsum is not None:
        return None
    r = compute_voyage(inp, a)
    k = 1 - (a.address_commission + a.brokerage) / 100.0
    denom = inp.flat_rate * inp.cargo_mt * k
    if denom <= 0:
        return None
    return (target_tce * r.total_days + _costs_excl_commission(r)) / denom * 100.0


def breakeven_lumpsum(inp: VoyageInputs, a: Assumptions, target_tce: float = 0.0) -> float:
    r = compute_voyage(replace(inp, lumpsum=1.0, ws=None), a)
    k = 1 - (a.address_commission + a.brokerage) / 100.0
    return (target_tce * r.total_days + _costs_excl_commission(r)) / k


def sensitivity_matrix(inp: VoyageInputs, a: Assumptions, ws_values, vlsfo_values):
    """Matrice TCE : lignes = VLSFO, colonnes = WS (mode TCE)."""
    import pandas as pd

    rows = {}
    for p in vlsfo_values:
        rows[p] = [
            compute_voyage(replace(inp, ws=w), replace(a, vlsfo_price=p)).tce for w in ws_values
        ]
    return pd.DataFrame(rows, index=[f"WS {w:g}" for w in ws_values]).T.rename_axis("VLSFO")
