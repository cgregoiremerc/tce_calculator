"""Excel export of saved scenarios."""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def scenarios_to_dataframe(saved: list[dict]) -> pd.DataFrame:
    rows = []
    for s in saved:
        r = s["result"]
        inp = s["inputs"]
        rows.append({
            "Scenario": s["label"],
            "Cargo (MT)": inp.cargo_mt,
            "WS": inp.ws,
            "Lumpsum (USD)": inp.lumpsum,
            "Gross freight (USD)": r.freight_gross,
            "Commissions": r.commissions,
            "Bunker (USD)": r.bunker_cost,
            "EU ETS": r.ets_cost,
            "Port costs": r.port_costs,
            "Sea days": r.sailing_days,
            "Port days": r.port_days,
            "Total days": r.total_days,
            "TCE (USD/day)": r.tce,
        })
    return pd.DataFrame(rows)


def scenarios_to_excel(saved: list[dict]) -> bytes:
    df = scenarios_to_dataframe(saved)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Scenarios", index=False)
        ws = xw.sheets["Scenarios"]
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2
            ws.column_dimensions[col[0].column_letter].width = min(width, 40)
    return buf.getvalue()
