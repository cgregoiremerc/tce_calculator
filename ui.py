"""Page partagée TCE / Lumpsum : un seul formulaire, un seul rendu."""
from __future__ import annotations

from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (DEFAULT_ASSUMPTIONS, DEFAULT_CARGO_MT, DEFAULT_WS, PORT_OPTIONS)
from export import scenarios_to_dataframe, scenarios_to_excel
from voyage_calculations import (VoyageInputs, breakeven_lumpsum, breakeven_ws,
                                 compute_voyage, default_wait_days, eca_nm_for_leg,
                                 get_distance, get_flat_rate, sensitivity_matrix)

_KEY = {"tce": "saved_tce_results", "lumpsum": "saved_lumpsum_results"}


def _idx(name: str) -> int:
    return PORT_OPTIONS.index(name) if name in PORT_OPTIONS else 0


def _assumptions_editor(mode: str):
    a = st.session_state.get(f"{mode}_assumptions", DEFAULT_ASSUMPTIONS)
    with st.expander("Hypothèses (éditables)"):
        c = st.columns(3)
        a = replace(
            a,
            speed_laden=c[0].number_input("Vitesse laden (kn)", value=a.speed_laden, step=0.1, key=f"{mode}_sl"),
            speed_ballast=c[1].number_input("Vitesse ballast (kn)", value=a.speed_ballast, step=0.1, key=f"{mode}_sb"),
            weather_margin=c[2].number_input("Marge météo (%)", value=a.weather_margin * 100, step=1.0, key=f"{mode}_wm") / 100,
            cons_laden=c[0].number_input("Conso laden (t/j)", value=a.cons_laden, step=0.5, key=f"{mode}_cl"),
            cons_ballast=c[1].number_input("Conso ballast (t/j)", value=a.cons_ballast, step=0.5, key=f"{mode}_cb"),
            cons_port=c[2].number_input("Conso port (t/j)", value=a.cons_port, step=0.5, key=f"{mode}_cp"),
            vlsfo_price=c[0].number_input("VLSFO (USD/t)", value=a.vlsfo_price, step=5.0, key=f"{mode}_vl"),
            mgo_price=c[1].number_input("MGO (USD/t)", value=a.mgo_price, step=5.0, key=f"{mode}_mg"),
            eua_price=c[2].number_input("EUA (EUR/t)", value=a.eua_price, step=1.0, key=f"{mode}_eua"),
            load_days=c[0].number_input("Jours chargement", value=a.load_days, step=0.5, key=f"{mode}_ld"),
            discharge_days=c[1].number_input("Jours déchargement", value=a.discharge_days, step=0.5, key=f"{mode}_dd"),
            ets_enabled=c[2].checkbox("EU ETS actif", value=a.ets_enabled, key=f"{mode}_ets"),
            port_cost_load=c[0].number_input("Frais port load (USD)", value=a.port_cost_load, step=1000.0, key=f"{mode}_pcl"),
            port_cost_discharge=c[1].number_input("Frais port disch. (USD)", value=a.port_cost_discharge, step=1000.0, key=f"{mode}_pcd"),
            address_commission=c[2].number_input("Addcomm + brokerage (%)", value=a.address_commission + a.brokerage, step=0.25, key=f"{mode}_com") - a.brokerage,
        )
    st.session_state[f"{mode}_assumptions"] = a
    return a


def _distance_input(label: str, a_port: str, b_port: str, key: str) -> float:
    d = get_distance(a_port, b_port)
    if d is None:
        st.warning(f"Distance {a_port} → {b_port} inconnue : saisie manuelle.")
    return st.number_input(label, min_value=0.0, value=float(d or 0.0), step=50.0, key=f"{key}_{a_port}_{b_port}")


def _form(mode: str, a):
    c = st.columns(3)
    ballast = c[0].selectbox("Ballast port", PORT_OPTIONS, index=_idx("Fujairah"), key=f"{mode}_bp")
    load = c[1].selectbox("Load port", PORT_OPTIONS, index=_idx("Ras Tanura"), key=f"{mode}_lp")
    disch = c[2].selectbox("Discharge port", PORT_OPTIONS, index=_idx("Singapore"), key=f"{mode}_dp")

    c = st.columns(2)
    bal_nm = _distance_input("Ballast (nm)", ballast, load, f"{mode}_bnm")
    lad_nm = _distance_input("Laden (nm)", load, disch, f"{mode}_lnm")
    with c[0]:
        pass

    c = st.columns(3)
    cargo = c[0].number_input("Cargo (MT)", min_value=1.0, value=float(DEFAULT_CARGO_MT), step=1000.0, key=f"{mode}_cargo")
    ws = flat = lump = None
    if mode == "tce":
        ws = c[1].number_input("WS", min_value=0.0, value=DEFAULT_WS, step=1.0, key=f"{mode}_ws")
        fr = get_flat_rate(load, disch)
        if fr is None:
            st.warning(f"Pas de flat rate pour {load} → {disch} : saisie manuelle.")
        flat = c[2].number_input("Flat rate (USD/t)", min_value=0.0, value=float(fr or 0.0), step=0.1, key=f"{mode}_fr_{load}_{disch}")
    else:
        lump = c[1].number_input("Lumpsum (USD)", min_value=0.0, value=1_500_000.0, step=25_000.0, key=f"{mode}_ls")

    c = st.columns(2)
    wl = c[0].number_input("Wait days load", min_value=0.0, value=default_wait_days(load), step=0.5, key=f"{mode}_wl_{load}")
    wd = c[1].number_input("Wait days discharge", min_value=0.0, value=default_wait_days(disch), step=0.5, key=f"{mode}_wd_{disch}")

    return VoyageInputs(
        ballast_port=ballast, load_port=load, discharge_port=disch, cargo_mt=cargo,
        ballast_nm=bal_nm, laden_nm=lad_nm, ws=ws, flat_rate=flat, lumpsum=lump,
        wait_days_load=wl, wait_days_discharge=wd,
        eca_ballast_nm=eca_nm_for_leg(ballast, load, bal_nm),
        eca_laden_nm=eca_nm_for_leg(load, disch, lad_nm),
    )


def _render_result(mode: str, inp: VoyageInputs, a):
    r = compute_voyage(inp, a)
    m = st.columns(4)
    m[0].metric("TCE (USD/jour)", f"{r.tce:,.0f}")
    m[1].metric("Fret brut", f"{r.freight_gross:,.0f}")
    m[2].metric("Durée totale (j)", f"{r.total_days:.1f}", f"mer {r.sailing_days:.1f} / port {r.port_days:.1f}", delta_color="off")
    m[3].metric("Coûts totaux", f"{r.total_costs:,.0f}")

    m = st.columns(4)
    m[0].metric("VLSFO (t)", f"{r.vlsfo_tonnes:,.0f}")
    m[1].metric("MGO (t)", f"{r.mgo_tonnes:,.0f}")
    m[2].metric("CO2 (t)", f"{r.co2_tonnes:,.0f}")
    m[3].metric("CO2 couvert ETS (t)", f"{r.co2_covered_tonnes:,.0f}")

    cb = pd.DataFrame({"Poste": list(r.cost_breakdown()), "USD": list(r.cost_breakdown().values())})
    left, right = st.columns([1, 1])
    left.dataframe(cb.style.format({"USD": "{:,.0f}"}), hide_index=True, width="stretch")
    right.plotly_chart(px.pie(cb, names="Poste", values="USD", hole=0.5), width="stretch")

    if mode == "tce":
        be = breakeven_ws(inp, a, 0.0)
        if be is not None:
            st.info(f"WS break-even (TCE = 0) : **{be:.1f}**")
        target = st.number_input("TCE cible (USD/j)", value=20_000.0, step=1000.0, key="tce_target")
        bt = breakeven_ws(inp, a, target)
        if bt is not None:
            st.info(f"WS requis pour TCE = {target:,.0f} USD/j : **{bt:.1f}**")
        _sensitivity(inp, a)
    else:
        target = st.number_input("TCE cible (USD/j)", value=20_000.0, step=1000.0, key="lumpsum_target")
        st.info(f"Lumpsum break-even : **{breakeven_lumpsum(inp, a, 0.0):,.0f}** USD  |  "
                f"pour TCE = {target:,.0f} : **{breakeven_lumpsum(inp, a, target):,.0f}** USD")
    return r


def _sensitivity(inp, a):
    st.subheader("Sensibilité WS × VLSFO")
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
    st.subheader("Scénarios sauvegardés")
    if not saved:
        st.caption("Aucun scénario sauvegardé.")
        return
    df = scenarios_to_dataframe(saved).sort_values("TCE (USD/j)", ascending=False)
    st.dataframe(df.style.format({c: "{:,.0f}" for c in df.columns if df[c].dtype.kind == "f"}),
                 hide_index=True, width="stretch")
    st.plotly_chart(px.bar(df, x="Scénario", y="TCE (USD/j)"), width="stretch")
    c = st.columns([1, 1, 2])
    c[0].download_button("Export Excel", scenarios_to_excel(saved), "scenarios_tce.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    to_del = c[2].selectbox("Supprimer", [None] + [s["label"] for s in saved], key=f"{mode}_del_sel",
                            format_func=lambda x: "—" if x is None else x)
    if c[1].button("Delete This Result", key=f"{mode}_del_btn") and to_del is not None:
        # Corrige le bug d'origine : on supprime dans la liste de CETTE page.
        st.session_state[key] = [s for s in saved if s["label"] != to_del]
        st.rerun()


def run_page(mode: str):
    title = "TCE Calculator" if mode == "tce" else "Lumpsum Calculator"
    st.title(title)
    a = _assumptions_editor(mode)
    inp = _form(mode, a)
    if st.button("Calculate", type="primary", key=f"{mode}_calc"):
        st.session_state[f"{mode}_last"] = inp
    last = st.session_state.get(f"{mode}_last")
    if last is not None:
        r = _render_result(mode, last, a)
        name = st.text_input("Nom du scénario", value=f"{last.load_port}→{last.discharge_port}", key=f"{mode}_name")
        if st.button("Sauvegarder", key=f"{mode}_save"):
            saved = st.session_state.setdefault(_KEY[mode], [])
            label, n = name, 2
            while any(s["label"] == label for s in saved):
                label, n = f"{name} ({n})", n + 1
            saved.append({"label": label, "inputs": last, "result": r})
            st.rerun()
    _saved_section(mode)
