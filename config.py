"""Configuration: default assumptions + loading of the CSV tables in data/.

To update the data, just edit the CSV files (Excel opens them fine), then
`git add . && git commit && git push`. The values shipped are ILLUSTRATIVE.

  data/ports.csv       country, EU/ECA flags, ECA miles, port costs, default wait days
  data/distances.csv   distances between ports (nm, symmetric)
  data/flat_rates.csv  Worldscale flat rates (USD/t) per load -> discharge pair
  data/vessels.csv     vessel profiles (MR / LR1 / LR2)
  data/prices.csv      bunker and EUA prices (latest row by date is used)
  data/routes.csv      favourite routes (ports + vessel)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Assumptions:
    # Speed (knots) and sea consumption (t/day): overridden by the vessel profile
    speed_laden: float = 13.0
    speed_ballast: float = 13.5
    cons_laden: float = 40.0
    cons_ballast: float = 36.0
    cons_port: float = 8.0           # t/day in port (incl. waiting)
    weather_margin: float = 0.10     # weather margin on sea days
    load_days: float = 1.5
    discharge_days: float = 2.0
    vlsfo_price: float = 600.0       # USD/t
    mgo_price: float = 800.0         # USD/t
    port_cost_load: float = 50_000.0
    port_cost_discharge: float = 50_000.0
    address_commission: float = 3.75  # % of gross freight
    brokerage: float = 1.25           # % of gross freight
    ets_enabled: bool = True
    eua_price: float = 70.0           # EUR/tCO2
    eur_usd: float = 1.08
    ets_phase_in: float = 1.0         # 100% from 2026
    co2_factor_vlsfo: float = 3.114   # tCO2 / t fuel
    co2_factor_mgo: float = 3.206


DEFAULT_ASSUMPTIONS = Assumptions()
DEFAULT_WS = 100.0
DEFAULT_VESSEL = "LR2"
DEFAULT_PORT_COST = 50_000.0


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, skipinitialspace=True).dropna(how="all")


# --- Ports -------------------------------------------------------------------
_ports = _csv("ports.csv")
PORTS: dict[str, dict] = {
    r.port: {"country": r.country, "eu": bool(int(r.eu)), "eca": bool(int(r.eca)),
             "eca_nm": float(r.eca_nm)}
    for r in _ports.itertuples()
}
PORT_OPTIONS: list[str] = sorted(PORTS)
PORT_COSTS: dict[str, float] = {r.port: float(r.port_cost) for r in _ports.itertuples()}
DEFAULT_WAIT_DAYS: dict[str, float] = {
    r.port: float(r.wait_days) for r in _ports.itertuples() if float(r.wait_days) > 0
}

# --- Distances / flat rates --------------------------------------------------
DISTANCES: dict[frozenset, float] = {
    frozenset((r.port_a, r.port_b)): float(r.nm) for r in _csv("distances.csv").itertuples()
}
FLAT_RATES: dict[tuple, float] = {
    (r.load_port, r.discharge_port): float(r.flat_rate) for r in _csv("flat_rates.csv").itertuples()
}

# --- Vessels / routes --------------------------------------------------------
VESSELS: dict[str, dict] = {
    r.vessel: {"cargo_mt": float(r.cargo_mt), "speed_laden": float(r.speed_laden),
               "speed_ballast": float(r.speed_ballast), "cons_laden": float(r.cons_laden),
               "cons_ballast": float(r.cons_ballast), "cons_port": float(r.cons_port)}
    for r in _csv("vessels.csv").itertuples()
}
ROUTES: dict[str, dict] = {
    r.name: {"ballast": r.ballast, "load": r.load, "discharge": r.discharge, "vessel": r.vessel}
    for r in _csv("routes.csv").itertuples()
}


def latest_prices() -> dict:
    """Latest dated row of prices.csv : {date, vlsfo, mgo, eua_eur}."""
    df = _csv("prices.csv")
    df["date"] = pd.to_datetime(df["date"])
    row = df.sort_values("date").iloc[-1]
    return {"date": row["date"].date(), "vlsfo": float(row["vlsfo"]),
            "mgo": float(row["mgo"]), "eua_eur": float(row["eua_eur"])}
