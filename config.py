"""Configuration unique : hypothèses, ports, distances et flat rates.

Tout ce qui était dupliqué entre les pages vit ici. Les valeurs de distances
et de flat rates ci-dessous sont ILLUSTRATIVES : remplace-les par tes données
(ou branche l'API de distances, cf. voyage_calculations.fetch_distance_api).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Assumptions:
    # Vitesse (noeuds) et consommation en mer (t/jour)
    speed_laden: float = 13.0
    speed_ballast: float = 13.5
    cons_laden: float = 38.0
    cons_ballast: float = 34.0
    cons_port: float = 6.0           # t/jour au port (y compris attente)
    # Marge météo appliquée aux jours de mer (était un `* 1.1` caché)
    weather_margin: float = 0.10
    # Durées au port (jours)
    load_days: float = 1.5
    discharge_days: float = 2.0
    # Prix soute (USD/t)
    vlsfo_price: float = 600.0
    mgo_price: float = 800.0
    # Frais de port (USD)
    port_cost_load: float = 50_000.0
    port_cost_discharge: float = 50_000.0
    # Commissions (% du fret brut)
    address_commission: float = 3.75
    brokerage: float = 1.25
    # EU ETS
    ets_enabled: bool = True
    eua_price: float = 70.0          # EUR/tCO2 converti en USD ci-dessous
    eur_usd: float = 1.08
    ets_phase_in: float = 1.0        # 40 % en 2024, 70 % en 2025, 100 % dès 2026
    co2_factor_vlsfo: float = 3.114  # tCO2 / t fuel
    co2_factor_mgo: float = 3.206


DEFAULT_ASSUMPTIONS = Assumptions()

# Jours d'attente suggérés par port (était codé en dur : 14 j pour Singapour).
# Valeur par défaut éditable dans l'interface.
DEFAULT_WAIT_DAYS: dict[str, float] = {"Singapore": 14.0}

# Ports : pays, appartenance EU/EEE (ETS), port situé en zone ECA,
# et milles nautiques d'approche dans la zone ECA.
PORTS: dict[str, dict] = {
    "Rotterdam": {"country": "NL", "eu": True, "eca": True, "eca_nm": 300},
    "Antwerp": {"country": "BE", "eu": True, "eca": True, "eca_nm": 250},
    "Marseille (Fos)": {"country": "FR", "eu": True, "eca": False, "eca_nm": 0},
    "Trieste": {"country": "IT", "eu": True, "eca": False, "eca_nm": 0},
    "Primorsk": {"country": "RU", "eu": False, "eca": True, "eca_nm": 450},
    "Ceyhan": {"country": "TR", "eu": False, "eca": False, "eca_nm": 0},
    "Houston": {"country": "US", "eu": False, "eca": True, "eca_nm": 200},
    "Fujairah": {"country": "AE", "eu": False, "eca": False, "eca_nm": 0},
    "Ras Tanura": {"country": "SA", "eu": False, "eca": False, "eca_nm": 0},
    "Jubail": {"country": "SA", "eu": False, "eca": False, "eca_nm": 0},
    "Luanda": {"country": "AO", "eu": False, "eca": False, "eca_nm": 0},
    "Sikka": {"country": "IN", "eu": False, "eca": False, "eca_nm": 0},
    "Singapore": {"country": "SG", "eu": False, "eca": False, "eca_nm": 0},
    "Ulsan": {"country": "KR", "eu": False, "eca": False, "eca_nm": 0},
}
PORT_OPTIONS: list[str] = sorted(PORTS)

# Distances en milles nautiques (symétriques). ILLUSTRATIF.
_DISTANCES = {
    ("Rotterdam", "Antwerp"): 100,
    ("Rotterdam", "Houston"): 4900,
    ("Rotterdam", "Fujairah"): 6350,
    ("Rotterdam", "Ras Tanura"): 6700,
    ("Rotterdam", "Singapore"): 8300,
    ("Rotterdam", "Primorsk"): 1150,
    ("Rotterdam", "Marseille (Fos)"): 1900,
    ("Rotterdam", "Ceyhan"): 3500,
    ("Marseille (Fos)", "Ceyhan"): 1600,
    ("Marseille (Fos)", "Fujairah"): 4500,
    ("Marseille (Fos)", "Houston"): 5800,
    ("Trieste", "Ceyhan"): 1450,
    ("Houston", "Fujairah"): 12300,
    ("Houston", "Singapore"): 15300,
    ("Fujairah", "Singapore"): 3300,
    ("Fujairah", "Sikka"): 900,
    ("Fujairah", "Ras Tanura"): 420,
    ("Fujairah", "Ulsan"): 6000,
    ("Ras Tanura", "Singapore"): 3750,
    ("Ras Tanura", "Sikka"): 1100,
    ("Ras Tanura", "Ulsan"): 6400,
    ("Singapore", "Ulsan"): 2900,
    ("Sikka", "Singapore"): 2600,
}
DISTANCES: dict[frozenset, float] = {frozenset(k): float(v) for k, v in _DISTANCES.items()}

# Flat rates (USD/t). ILLUSTRATIF. Les paires absentes (Luanda, Jubail...) renvoient
# None : l'interface demande alors une saisie manuelle au lieu de planter.
_FLAT_RATES = {
    ("Fujairah", "Singapore"): 12.5,
    ("Ras Tanura", "Singapore"): 14.0,
    ("Ras Tanura", "Ulsan"): 17.5,
    ("Fujairah", "Sikka"): 7.5,
    ("Rotterdam", "Houston"): 18.0,
    ("Houston", "Rotterdam"): 17.0,
    ("Primorsk", "Rotterdam"): 9.5,
    ("Ceyhan", "Marseille (Fos)"): 9.0,
    ("Ceyhan", "Trieste"): 8.5,
}
FLAT_RATES: dict[tuple, float] = dict(_FLAT_RATES)

DEFAULT_CARGO_MT = 100_000
DEFAULT_WS = 100.0
