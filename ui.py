"""Shared TCE / Lumpsum page: one form, one renderer."""
from __future__ import annotations

import datetime as dt
from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (DEFAULT_ASSUMPTIONS, DEFAULT_PORT_COST, DEFAULT_VESSEL, DEFAULT_WS,
                    PORT_COSTS, PORT_OPTIONS, ROUTES, VESSELS, latest_prices)
from export import scenarios_to_dataframe, scenarios_to_excel
from voyage_calculations import (VoyageInputs, breakeven_lumpsum, breakeven_ws,
                                 compute_voyage, default_wait_days, eca_nm_for_leg,
                                 get_distance, get_flat_rate, sensitivity_matrix)

_KEY = {"tce": "saved_tce_results", "lumpsum": "saved_lumpsum_results"}
_VESSEL_KEYS = {"sl": "speed_laden", "sb": "speed_ballast", "cl": "cons_laden",
                "cb": "cons_ballast", "cp": "cons_port", "cargo": "cargo_mt"}


def _ss(mode: str, k: str) -> str:
    return f"{mode}_{k}"


# --------------------------------------------------------------------------- #
# Initial state and callbacks (vessel profile, favourite route, reset)
# --------------------------------------------------------------------------- #
def _apply_vessel(mode: str) -> None:
    v = VESSELS[st.session_state[_ss(mode, "vessel")]]
    for k, field in _VESSEL_KEYS.items():
        st.session_state[_ss(mode, k)] = float(v[field])


def _apply_prices(mode: str) -> None:
    p, d = latest_prices(), DEFAULT_ASSUMPTIONS
    st.session_state.update({
        _ss(mode, "vl"): p["vlsfo"], _ss(mode, "mg"): p["mgo"], _ss(mode, "eua"): p["eua_eur"],
        _ss(mode, "wm"): d.weather_margin * 100, _ss(mode, "ld"): d.load_days,
        _ss(mode, "dd"): d.discharge_days, _ss(mode, "ac"): d.address_commission,
        _ss(mode, "br"): d.brokerage, _ss(mode, "ets"): d.ets_enabled,
    })


def _reset(mode: str) -> None:
    _apply_vessel(mode)
    _apply_prices(mode)


def _apply_route(mode: str) -> None:
    name = st.session_state[_ss(mode, "route")]
    if not name:
        return
    r = ROUTES[name]
    st.session_state[_ss(mode, "bp")] = r["ballast"]
    st.session_state[_ss(mode, "lp")] = r["load"]
    st.session_state[_ss(mode, "dp")] = r["discharge"]
    st.session_state[_ss(mode, "vessel")] = r["vessel"]
    _apply_vessel(mode)


def _init(mode: str) -> None:
    ss = st.session_state
    if ss.get(_ss(mode, "init")):
        return
    ss[_ss(mode, "init")] = True
    ss[_ss(mode, "vessel")] = DEFAULT_VESSEL
    ss[_ss(mode, "route")] = ""
    ss[_ss(mode, "bp")], ss[_ss(mode, "lp")], ss[_ss(mode, "dp")] = "Fujairah", "Ras Tanura", "Singapore"
    _reset(mode)


# --------------------------------------------------------------------------- #
# Formulaire
# --------------------------------------------------------------------------- #
def _distance_input(label: str, a_port: str, b_port: str, key: str) -> float:
    d = get_distance(a_port, b_port)
    if d is None:
        st.warning(f"Distance {a_port} → {b_port} missing from data/distances.csv: enter it manually.")
    return st.number_input(label, min_value=0.0, value=float(d or 0.0), step=50.0,
                           key=f"{key}_{a_port}_{b_port}")


def _form(mode: str) -> VoyageInputs:
    p = latest_prices()
    age = (dt.date.today() - p["date"]).days
    msg = (f"Prices as of {p['date']:%d/%m/%Y}: VLSFO {p['vlsfo']:,.0f} · MGO {p['mgo']:,.0f} · "
           f"EUA {p['eua_eur']:,.0f} EUR (data/prices.csv)")
    (st.warning if age > 3 else st.caption)(msg + (f" — {age} days old, please update" if age > 3 else ""))

    c = st.columns([2, 1])
    c[0].selectbox("Favourite route", [""] + list(ROUTES), key=_ss(mode, "route"),
                   format_func=lambda x: "—" if not x else x,
                   on_change=_apply_route, args=(mode,))
    c[1].selectbox("Vessel type", list(VESSELS), key=_ss(mode, "vessel"),
                   on_change=_apply_vessel, args=(mode,))

    c = st.columns(3)
    ballast = c[0].selectbox("Ballast port", PORT_OPTIONS, key=_ss(mode, "bp"))
    load = c[1].selectbox("Load port", PORT_OPTIONS, key=_ss(mode, "lp"))
    disch = c[2].selectbox("Discharge port", PORT_OPTIONS, key=_ss(mode, "dp"))

    c = st.columns(2)
    with c[0]:
        bal_nm = _distance_input("Ballast (nm)", ballast, load, _ss(mode, "bnm"))
    with c[1]:
        lad_nm = _distance_input("Laden (nm)", load, disch, _ss(mode, "lnm"))

    c = st.columns(3)
    cargo = c[0].number_input("Cargo (MT)", min_value=1.0, step=1000.0, key=_ss(mode, "cargo"))
    ws = flat = lump = None
    if mode == "tce":
        ws = c[1].number_input("WS", min_value=0.0, value=DEFAULT_WS, step=1.0, key=_ss(mode, "ws"))
        fr = get_flat_rate(load, disch)
        if fr is None:
            st.warning(f"Flat rate {load} → {disch} missing from data/flat_rates.csv: enter it manually.")
        flat = c[2].number_input("Flat rate (USD/t)", min_value=0.0, value=float(fr or 0.0), step=0.1,
                                 key=f"{_ss(mode, 'fr')}_{load}_{disch}")
    else:
        lump = c[1].number_input("Lumpsum (USD)", min_value=0.0, value=1_500_000.0, step=25_000.0,
                                 key=_ss(mode, "ls"))

    return VoyageInputs(
        ballast_port=ballast, load_port=load, discharge_port=disch, cargo_mt=cargo,
        ballast_nm=bal_nm, laden_nm=lad_nm, ws=ws, flat_rate=flat, lumpsum=lump,
        eca_ballast_nm=eca_nm_for_leg(ballast, load, bal_nm),
        eca_laden_nm=eca_nm_for_leg(load, disch, lad_nm),
    )


def _assumptions(mode: str, inp: VoyageInputs):
    """Pre-filled assumptions (vessel, prices, ports): open only to adjust."""
    k = lambda s: _ss(mode, s)  # noqa: E731
    with st.expander("Assumptions (pre-filled, adjustable)"):
        c = st.columns(3)
        sl = c[0].number_input("Speed laden (kn)", step=0.1, key=k("sl"))
        sb = c[1].number_input("Speed ballast (kn)", step=0.1, key=k("sb"))
        wm = c[2].number_input("Weather margin (%)", step=1.0, key=k("wm"))
        cl = c[0].number_input("Consumption laden (t/d)", step=0.5, key=k("cl"))
        cb = c[1].number_input("Consumption ballast (t/d)", step=0.5, key=k("cb"))
        cp = c[2].number_input("Consumption port (t/d)", step=0.5, key=k("cp"))
        vl = c[0].number_input("VLSFO (USD/t)", step=5.0, key=k("vl"))
        mg = c[1].number_input("MGO (USD/t)", step=5.0, key=k("mg"))
        eua = c[2].number_input("EUA (EUR/t)", step=1.0, key=k("eua"))
        ld = c[0].number_input("Load days", step=0.5, key=k("ld"))
        dd = c[1].number_input("Discharge days", step=0.5, key=k("dd"))
        ets = c[2].checkbox("EU ETS actif", key=k("ets"))
        pcl = c[0].number_input("Load port costs (USD)", step=1000.0,
                                value=float(PORT_COSTS.get(inp.load_port, DEFAULT_PORT_COST)),
                                key=f"{k('pcl')}_{inp.load_port}")
        pcd = c[1].number_input("Discharge port costs (USD)", step=1000.0,
                                value=float(PORT_COSTS.get(inp.discharge_port, DEFAULT_PORT_COST)),
                                key=f"{k('pcd')}_{inp.discharge_port}")
        wl = c[2].number_input("Wait days load", min_value=0.0, step=0.5,
                               value=default_wait_days(inp.load_port), key=f"{k('wl')}_{inp.load_port}")
        wd = c[0].number_input("Wait days discharge", min_value=0.0, step=0.5,
                               value=default_wait_days(inp.discharge_port),
                               key=f"{k('wd')}_{inp.discharge_port}")
        ac = c[1].number_input("Address commission (%)", step=0.25, key=k("ac"))
        br = c[2].number_input("Brokerage (%)", step=0.25, key=k("br"))
        st.button("Reset (vessel, prices, assumptions)", on_click=_reset, args=(mode,),
                  key=k("reset"))
    a = replace(DEFAULT_ASSUMPTIONS, speed_laden=sl, speed_ballast=sb, weather_margin=wm / 100,
                cons_laden=cl, cons_ballast=cb, cons_port=cp, vlsfo_price=vl, mgo_price=mg,
                eua_price=eua, load_days=ld, discharge_days=dd, ets_enabled=ets,
                port_cost_load=pcl, port_cost_discharge=pcd, address_commission=ac, brokerage=br)
    return a, replace(inp, wait_days_load=wl, wait_days_discharge=wd)


# --------------------------------------------------------------------------- #
# Rendu
# --------------------------------------------------------------------------- #
def _render_result(mode: str, inp: VoyageInputs, a):
    r = compute_voyage(inp, a)
    m = st.columns(4)
    m[0].metric("TCE (USD/day)", f"{r.tce:,.0f}")
    m[1].metric("Gross freight", f"{r.freight_gross:,.0f}")
    m[2].metric("Total duration (days)", f"{r.total_days:.1f}", f"sea {r.sailing_days:.1f} / port {r.port_days:.1f}",
                delta_color="off")
    m[3].metric("Total costs", f"{r.total_costs:,.0f}")

    m = st.columns(4)
    m[0].metric("VLSFO (t)", f"{r.vlsfo_tonnes:,.0f}")
    m[1].metric("MGO (t)", f"{r.mgo_tonnes:,.0f}")
    m[2].metric("CO2 (t)", f"{r.co2_tonnes:,.0f}")
    m[3].metric("ETS-covered CO2 (t)", f"{r.co2_covered_tonnes:,.0f}")

    cb = pd.DataFrame({"Poste": list(r.cost_breakdown()), "USD": list(r.cost_breakdown().values())})
    left, right = st.columns([1, 1])
    left.dataframe(cb.style.format({"USD": "{:,.0f}"}), hide_index=True, width="stretch")
    right.plotly_chart(px.pie(cb, names="Poste", values="USD", hole=0.5), width="stretch")

    if mode == "tce":
        be = breakeven_ws(inp, a, 0.0)
        if be is not None:
            st.info(f"WS break-even (TCE = 0): **{be:.1f}**")
        target = st.number_input("Target TCE (USD/day)", value=20_000.0, step=1000.0, key="tce_target")
        bt = breakeven_ws(inp, a, target)
        if bt is not None:
            st.info(f"WS required for TCE = {target:,.0f} USD/day : **{bt:.1f}**")
        _sensitivity(inp, a)
    else:
        target = st.number_input("Target TCE (USD/day)", value=20_000.0, step=1000.0, key="lumpsum_target")
        st.info(f"Lumpsum break-even: **{breakeven_lumpsum(inp, a, 0.0):,.0f}** USD  |  "
                f"for TCE = {target:,.0f}: **{breakeven_lumpsum(inp, a, target):,.0f}** USD")
    return r


def _sensitivity(inp, a):
    st.subheader("Sensitivity WS × VLSFO")
    ws0 = inp.ws or 100.0
    ws_vals = [round(ws0 + d, 1) for d in (-20, -10, 0, 10, 20)]
    vl_vals = [round(a.vlsfo_price + d) for d in (-100, -50, 0, 50, 100)]
    df = sensitivity_matrix(inp, a, ws_vals, vl_vals)
    fig = go.Figure(go.Heatmap(z=df.values, x=list(df.columns), y=[f"{i:,.0f}" for i in df.index],
                               colorscale="RdYlGn", zmid=0, text=df.round(0).values,
                               texttemplate="%{text:,.0f}", colorbar_title="TCE"))
    fig.update_layout(yaxis_title="VLSFO (USD/t)", height=380, margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")


def _saved_section(mode: str):
    key = _KEY[mode]
    saved = st.session_state.setdefault(key, [])
    st.subheader("Saved scenarios")
    if not saved:
        st.caption("No saved scenarios.")
        return
    df = scenarios_to_dataframe(saved).sort_values("TCE (USD/day)", ascending=False)
    st.dataframe(df.style.format({c: "{:,.0f}" for c in df.columns if df[c].dtype.kind == "f"}),
                 hide_index=True, width="stretch")
    st.plotly_chart(px.bar(df, x="Scenario", y="TCE (USD/day)"), width="stretch")
    c = st.columns([1, 1, 2])
    c[0].download_button("Export to Excel", scenarios_to_excel(saved), "scenarios_tce.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    to_del = c[2].selectbox("Remove", [None] + [s["label"] for s in saved], key=f"{mode}_del_sel",
                            format_func=lambda x: "—" if x is None else x)
    if c[1].button("Delete This Result", key=f"{mode}_del_btn") and to_del is not None:
        st.session_state[key] = [s for s in saved if s["label"] != to_del]
        st.rerun()


def run_page(mode: str):
    st.title("TCE Calculator" if mode == "tce" else "Lumpsum Calculator")
    _init(mode)
    inp = _form(mode)
    a, inp = _assumptions(mode, inp)
    if st.button("Calculate", type="primary", key=f"{mode}_calc"):
        st.session_state[f"{mode}_last"] = inp
    last = st.session_state.get(f"{mode}_last")
    if last is not None:
        r = _render_result(mode, last, a)
        name = st.text_input("Scenario name", value=f"{last.load_port}→{last.discharge_port}",
                             key=f"{mode}_name")
        if st.button("Save", key=f"{mode}_save"):
            saved = st.session_state.setdefault(_KEY[mode], [])
            label, n = name, 2
            while any(s["label"] == label for s in saved):
                label, n = f"{name} ({n})", n + 1
            saved.append({"label": label, "inputs": last, "result": r})
            st.rerun()
    _saved_section(mode)
