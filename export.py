"""Export Excel des scénarios sauvegardés."""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def scenarios_to_dataframe(saved: list[dict]) -> pd.DataFrame:
    rows = []
    for s in saved:
        r = s["result"]
        inp = s["inputs"]
        rows.append({
            "Scénario": s["label"],
            "Cargo (MT)": inp.cargo_mt,
            "WS": inp.ws,
            "Lumpsum (USD)": inp.lumpsum,
            "Fret brut (USD)": r.freight_gross,
            "Commissions": r.commissions,
            "Bunker (USD)": r.bunker_cost,
            "EU ETS": r.ets_cost,
            "Frais de port": r.port_costs,
            "Jours mer": r.sailing_days,
            "Jours port": r.port_days,
            "Jours total": r.total_days,
            "TCE (USD/j)": r.tce,
        })
    return pd.DataFrame(rows)


def scenarios_to_excel(saved: list[dict]) -> bytes:
    df = scenarios_to_dataframe(saved)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Scénarios", index=False)
        ws = xw.sheets["Scénarios"]
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2
            ws.column_dimensions[col[0].column_letter].width = min(width, 40)
    return buf.getvalue()
