"""SynergyKit — Streamlit web UI for M&A synergy analysis."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pydantic import ValidationError

from synergykit import db
from synergykit.engine import run as run_engine
from synergykit.memo import generate as generate_memo
from synergykit.schema import (
    DEFAULT_COST_RAMP,
    DEFAULT_REVENUE_RAMP,
    CostSynergyCategory,
    DealInput,
    IntegrationCostCategory,
    RevenueSynergyCategory,
)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="SynergyKit", page_icon=":chart_with_upwards_trend:", layout="wide")
db.init_db()

# ── Constants ────────────────────────────────────────────────────────────────

COST_CATS = [e.value for e in CostSynergyCategory]
REV_CATS = [e.value for e in RevenueSynergyCategory]
INT_CATS = [e.value for e in IntegrationCostCategory]

RAMP_PRESETS: dict[str, dict] = {
    "Standard IB  (25/50/75/100 | 0/15/40/70)": {
        "cost": None,
        "revenue": None,
    },
    "Aggressive  (50/75/100/100 | 10/30/60/90)": {
        "cost": [0.50, 0.75, 1.00, 1.00],
        "revenue": [0.10, 0.30, 0.60, 0.90],
    },
    "Conservative  (15/30/50/75 | 0/10/25/50)": {
        "cost": [0.15, 0.30, 0.50, 0.75],
        "revenue": [0.00, 0.10, 0.25, 0.50],
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _empty_cost_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"category": pd.Series(dtype="object"),
         "description": pd.Series(dtype="object"),
         "run_rate": pd.Series(dtype="float64")}
    )


def _empty_rev_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"category": pd.Series(dtype="object"),
         "description": pd.Series(dtype="object"),
         "run_rate": pd.Series(dtype="float64")}
    )


def _empty_int_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"category": pd.Series(dtype="object"),
         "description": pd.Series(dtype="object"),
         "amount": pd.Series(dtype="float64"),
         "year": pd.Series(dtype="float64")}
    )


def _safe_str(val: object) -> str:
    """Coerce a cell value to str; NaN / None become empty string."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val)


def _breakeven(schedule: pd.DataFrame) -> int | None:
    for _, row in schedule.iterrows():
        if row["cumulative_net_cf"] > 0:
            return int(row["year"])
    return None


def _build_payload(
    meta: dict,
    terms: dict,
    cost_df: pd.DataFrame,
    rev_df: pd.DataFrame,
    int_df: pd.DataFrame,
    ramp_key: str,
) -> dict:
    """Assemble a DealInput-compatible dict from the current UI state."""
    ramp = RAMP_PRESETS[ramp_key]

    cost_synergies: list[dict] = []
    for _, r in cost_df.iterrows():
        if pd.isna(r.get("category")) or pd.isna(r.get("run_rate")):
            continue
        item: dict = {
            "category": r["category"],
            "description": _safe_str(r.get("description")),
            "run_rate": float(r["run_rate"]),
        }
        if ramp["cost"] is not None:
            item["ramp_up"] = ramp["cost"]
        cost_synergies.append(item)

    rev_synergies: list[dict] = []
    for _, r in rev_df.iterrows():
        if pd.isna(r.get("category")) or pd.isna(r.get("run_rate")):
            continue
        item = {
            "category": r["category"],
            "description": _safe_str(r.get("description")),
            "run_rate": float(r["run_rate"]),
        }
        if ramp["revenue"] is not None:
            item["ramp_up"] = ramp["revenue"]
        rev_synergies.append(item)

    int_costs: list[dict] = []
    for _, r in int_df.iterrows():
        if pd.isna(r.get("category")) or pd.isna(r.get("amount")):
            continue
        yr = r.get("year", 1)
        int_costs.append({
            "category": r["category"],
            "description": _safe_str(r.get("description")),
            "amount": float(r["amount"]),
            "year": 1 if pd.isna(yr) else int(yr),
        })

    return {
        "metadata": meta,
        "deal_terms": terms,
        "cost_synergies": cost_synergies,
        "revenue_synergies": rev_synergies,
        "integration_costs": int_costs,
    }


# ── Handle deal loading (runs before any tab renders) ────────────────────────

if "load_deal_payload" in st.session_state:
    p = st.session_state.pop("load_deal_payload")
    m = p["metadata"]
    st.session_state.update({
        "_deal_name": m["deal_name"],
        "_acquirer": m["acquirer"],
        "_target": m["target"],
        "_date": m["date"],
        "_analyst": m.get("analyst", ""),
        "_ev": float(p["deal_terms"]["enterprise_value"]),
        "_dr": float(p["deal_terms"]["discount_rate"]),
        "_years": int(p["deal_terms"]["projection_years"]),
        "_cost_df": (
            pd.DataFrame([
                {"category": s["category"], "description": s["description"], "run_rate": s["run_rate"]}
                for s in p["cost_synergies"]
            ]) if p.get("cost_synergies") else _empty_cost_df()
        ),
        "_rev_df": (
            pd.DataFrame([
                {"category": s["category"], "description": s["description"], "run_rate": s["run_rate"]}
                for s in p["revenue_synergies"]
            ]) if p.get("revenue_synergies") else _empty_rev_df()
        ),
        "_int_df": (
            pd.DataFrame([
                {"category": s["category"], "description": s["description"],
                 "amount": s["amount"], "year": s["year"]}
                for s in p["integration_costs"]
            ]) if p.get("integration_costs") else _empty_int_df()
        ),
        "_loaded_msg": f"Loaded deal: {m['deal_name']}",
    })
    # Clear widget & result keys so they reinitialise on next render
    for k in ("cost_editor", "rev_editor", "int_editor",
              "_result", "_memo_md", "_deal", "_payload", "_sens_df"):
        st.session_state.pop(k, None)
    st.rerun()

# ── Session-state defaults ───────────────────────────────────────────────────

for key, factory in [("_cost_df", _empty_cost_df),
                     ("_rev_df", _empty_rev_df),
                     ("_int_df", _empty_int_df)]:
    if key not in st.session_state:
        st.session_state[key] = factory()

# ── Layout ───────────────────────────────────────────────────────────────────

st.title("SynergyKit")
st.caption("M&A Synergy Analysis")

tab_builder, tab_library = st.tabs(["Deal Builder", "Deal Library"])

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — DEAL BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

with tab_builder:

    # Show load confirmation if present
    if "_loaded_msg" in st.session_state:
        st.success(st.session_state.pop("_loaded_msg"))

    # ── Metadata ─────────────────────────────────────────────────────────────
    st.subheader("Deal Metadata")
    mc1, mc2, mc3 = st.columns(3)
    deal_name = mc1.text_input("Deal Name", value=st.session_state.get("_deal_name", ""))
    acquirer  = mc2.text_input("Acquirer",  value=st.session_state.get("_acquirer", ""))
    target    = mc3.text_input("Target",    value=st.session_state.get("_target", ""))
    mc4, mc5 = st.columns(2)
    deal_date = mc4.text_input("Date (YYYY-MM-DD)", value=st.session_state.get("_date", str(date.today())))
    analyst   = mc5.text_input("Analyst", value=st.session_state.get("_analyst", ""))

    # ── Deal terms ───────────────────────────────────────────────────────────
    st.subheader("Deal Terms")
    tc1, tc2, tc3 = st.columns(3)
    ev    = tc1.number_input("Enterprise Value ($M)", min_value=0.1,
                             value=st.session_state.get("_ev", 500.0), step=10.0)
    dr    = tc2.number_input("Discount Rate (e.g. 0.10 = 10%)", min_value=0.01,
                             max_value=0.99,
                             value=st.session_state.get("_dr", 0.10),
                             step=0.01, format="%.2f")
    years = tc3.number_input("Projection Years", min_value=1, max_value=10,
                             value=st.session_state.get("_years", 5), step=1)

    # ── Ramp-up preset ───────────────────────────────────────────────────────
    st.subheader("Ramp-Up Schedule")
    ramp_key = st.selectbox("Preset", list(RAMP_PRESETS.keys()))
    ramp = RAMP_PRESETS[ramp_key]
    rc1, rc2 = st.columns(2)
    rc1.caption(
        "Cost ramp: "
        + ", ".join(f"{x:.0%}" for x in (ramp["cost"] or DEFAULT_COST_RAMP))
    )
    rc2.caption(
        "Revenue ramp: "
        + ", ".join(f"{x:.0%}" for x in (ramp["revenue"] or DEFAULT_REVENUE_RAMP))
    )

    # ── Synergy tables ───────────────────────────────────────────────────────
    st.subheader("Cost Synergies")
    cost_df = st.data_editor(
        st.session_state["_cost_df"],
        num_rows="dynamic",
        key="cost_editor",
        column_config={
            "category": st.column_config.SelectboxColumn(
                "Category", options=COST_CATS, required=True,
            ),
            "description": st.column_config.TextColumn("Description", required=True),
            "run_rate": st.column_config.NumberColumn(
                "Run Rate ($M)", min_value=0.01, format="%.1f", required=True,
            ),
        },
        use_container_width=True,
    )

    st.subheader("Revenue Synergies")
    rev_df = st.data_editor(
        st.session_state["_rev_df"],
        num_rows="dynamic",
        key="rev_editor",
        column_config={
            "category": st.column_config.SelectboxColumn(
                "Category", options=REV_CATS, required=True,
            ),
            "description": st.column_config.TextColumn("Description", required=True),
            "run_rate": st.column_config.NumberColumn(
                "Run Rate ($M)", min_value=0.01, format="%.1f", required=True,
            ),
        },
        use_container_width=True,
    )

    st.subheader("Integration Costs")
    int_df = st.data_editor(
        st.session_state["_int_df"],
        num_rows="dynamic",
        key="int_editor",
        column_config={
            "category": st.column_config.SelectboxColumn(
                "Category", options=INT_CATS, required=True,
            ),
            "description": st.column_config.TextColumn("Description", required=True),
            "amount": st.column_config.NumberColumn(
                "Amount ($M)", min_value=0.01, format="%.1f", required=True,
            ),
            "year": st.column_config.NumberColumn(
                "Year", min_value=1, max_value=10, step=1, required=True,
            ),
        },
        use_container_width=True,
    )

    # ── Action buttons ───────────────────────────────────────────────────────
    st.divider()
    act1, act2 = st.columns(2)
    run_clicked = act1.button("Run Analysis", type="primary", use_container_width=True)

    with act2:
        sc1, sc2 = st.columns([3, 1])
        save_name = sc1.text_input(
            "version", value=deal_name or "Untitled",
            label_visibility="collapsed", placeholder="Version name...",
        )
        save_clicked = sc2.button("Save Deal", use_container_width=True)

    if save_clicked:
        meta  = {"deal_name": deal_name, "acquirer": acquirer, "target": target,
                 "date": deal_date, "analyst": analyst}
        terms = {"enterprise_value": ev, "discount_rate": dr, "projection_years": years}
        payload = _build_payload(meta, terms, cost_df, rev_df, int_df, ramp_key)
        did = db.save_deal(payload, save_name or deal_name or "Untitled")
        st.success(f"Saved as **{save_name}** (ID {did})")

    # ── Run analysis ─────────────────────────────────────────────────────────
    if run_clicked:
        # Clear stale results
        for k in ("_result", "_memo_md", "_deal", "_payload", "_sens_df"):
            st.session_state.pop(k, None)

        meta  = {"deal_name": deal_name, "acquirer": acquirer, "target": target,
                 "date": deal_date, "analyst": analyst}
        terms = {"enterprise_value": ev, "discount_rate": dr, "projection_years": years}
        payload = _build_payload(meta, terms, cost_df, rev_df, int_df, ramp_key)

        try:
            deal_obj = DealInput(**payload)
        except ValidationError as e:
            st.error("**Validation Error**")
            for err in e.errors():
                loc = " > ".join(str(x) for x in err["loc"])
                st.error(f"`{loc}`: {err['msg']}")
            deal_obj = None

        if deal_obj is not None:
            with st.spinner("Running engine..."):
                result  = run_engine(deal_obj)
                memo_md = generate_memo(deal_obj, result)
            st.session_state.update({
                "_result": result,
                "_memo_md": memo_md,
                "_deal": deal_obj,
                "_payload": payload,
            })

    # ── Display results (persisted in session state) ─────────────────────────
    if "_result" in st.session_state:
        result   = st.session_state["_result"]
        memo_md  = st.session_state["_memo_md"]
        deal_obj = st.session_state["_deal"]
        schedule = result.synergy_schedule
        summary  = result.summary
        be       = _breakeven(schedule)

        st.divider()
        st.subheader("Results")

        # ── Warnings ─────────────────────────────────────────────────────────
        for _, row in schedule.iterrows():
            yr = int(row["year"])
            if yr <= 2 and row["integration_costs"] > row["gross_total_synergies"]:
                st.warning(
                    f"Year {yr}: integration costs "
                    f"(${row['integration_costs']:.1f}M) exceed gross synergies "
                    f"(${row['gross_total_synergies']:.1f}M)"
                )
        if be is None or be > deal_obj.deal_terms.projection_years:
            st.warning(
                f"Cumulative net CF does not break even within the "
                f"{deal_obj.deal_terms.projection_years}-year projection period"
            )

        # ── KPI cards ────────────────────────────────────────────────────────
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("NPV",               f"${summary['npv_net_synergies']:.1f}M")
        k2.metric("NPV % EV",          f"{summary['synergy_npv_as_pct_ev']:.1f}%")
        k3.metric("Run-Rate Synergies", f"${summary['total_run_rate_synergies']:.1f}M")
        k4.metric("Integration Costs",  f"${summary['total_integration_costs']:.1f}M")
        k5.metric("Breakeven",          f"Year {be}" if be else "N/A")

        # ── Schedule table ───────────────────────────────────────────────────
        st.subheader("Synergy Schedule ($M)")
        fmt = {"year": "{:.0f}"}
        for c in schedule.columns:
            if c != "year":
                fmt[c] = "${:,.1f}"
        st.dataframe(schedule.style.format(fmt), use_container_width=True, hide_index=True)

        # ── Charts ───────────────────────────────────────────────────────────
        st.subheader("Visuals")
        ch1, ch2 = st.columns(2)

        with ch1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=schedule["year"], y=schedule["net_synergy_cf"],
                mode="lines+markers", name="Net Synergy CF",
                line=dict(width=2.5, color="#2c3e50"),
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
            fig.update_layout(
                title="Annual Net Synergy Cash Flow",
                xaxis_title="Year", yaxis_title="$M",
                height=360, margin=dict(t=40, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=schedule["year"], y=schedule["cumulative_net_cf"],
                mode="lines+markers", fill="tozeroy",
                name="Cumulative Net CF",
                line=dict(width=2.5, color="#2980b9"),
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
            fig.update_layout(
                title="Cumulative Net Synergy Cash Flow",
                xaxis_title="Year", yaxis_title="$M",
                height=360, margin=dict(t=40, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Stacked bar — full width
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=schedule["year"], y=schedule["gross_cost_synergies"],
            name="Cost Synergies", marker_color="#2ecc71",
        ))
        fig.add_trace(go.Bar(
            x=schedule["year"], y=schedule["gross_revenue_synergies"],
            name="Revenue Synergies", marker_color="#3498db",
        ))
        fig.add_trace(go.Bar(
            x=schedule["year"], y=-schedule["integration_costs"],
            name="Integration Costs", marker_color="#e74c3c",
        ))
        fig.update_layout(
            barmode="relative",
            title="Annual Synergy Breakdown by Category",
            xaxis_title="Year", yaxis_title="$M",
            height=360, margin=dict(t=40, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Memo ─────────────────────────────────────────────────────────────
        with st.expander("Deal Memo (Markdown)"):
            st.markdown(memo_md)
            st.code(memo_md, language="markdown")

        # ── Downloads ────────────────────────────────────────────────────────
        st.subheader("Downloads")
        dl1, dl2, dl3 = st.columns(3)
        dl1.download_button(
            "synergy_schedule.csv",
            schedule.to_csv(index=False),
            file_name="synergy_schedule.csv",
            mime="text/csv",
        )
        dl2.download_button(
            "summary.json",
            json.dumps(summary, indent=2),
            file_name="summary.json",
            mime="application/json",
        )
        dl3.download_button(
            "deal_memo.md",
            memo_md,
            file_name="deal_memo.md",
            mime="text/markdown",
        )

        # ── Quick Sensitivity ────────────────────────────────────────────────
        st.divider()
        st.subheader("Quick Sensitivity")
        sens1, sens2 = st.columns(2)
        dr_pct = sens1.slider(
            "Discount Rate Range (%)", min_value=4, max_value=20,
            value=(8, 12), step=1, format="%d%%",
        )
        mult_range = sens2.slider(
            "Run-Rate Multiplier", min_value=0.5, max_value=1.5,
            value=(0.8, 1.2), step=0.1, format="%.1fx",
        )

        if st.button("Compute Sensitivity Table"):
            base_payload = st.session_state["_payload"]
            dr_vals = np.linspace(dr_pct[0] / 100.0, dr_pct[1] / 100.0, 5)
            m_vals  = np.linspace(mult_range[0], mult_range[1], 5)

            rows: dict[str, dict] = {}
            with st.spinner("Computing sensitivity grid..."):
                for m in m_vals:
                    row: dict[str, float] = {}
                    for d in dr_vals:
                        adj = json.loads(json.dumps(base_payload))
                        adj["deal_terms"]["discount_rate"] = round(float(d), 4)
                        for s in adj.get("cost_synergies", []):
                            s["run_rate"] = round(s["run_rate"] * float(m), 4)
                        for s in adj.get("revenue_synergies", []):
                            s["run_rate"] = round(s["run_rate"] * float(m), 4)
                        try:
                            adj_result = run_engine(DealInput(**adj))
                            row[f"{d:.0%}"] = adj_result.summary["npv_net_synergies"]
                        except Exception:
                            row[f"{d:.0%}"] = float("nan")
                    rows[f"{m:.1f}x"] = row

            sens_df = pd.DataFrame(rows).T
            sens_df.index.name = "Multiplier \\ Rate"
            st.session_state["_sens_df"] = sens_df

        if "_sens_df" in st.session_state:
            st.caption("NPV of Net Synergies ($M)")
            st.dataframe(
                st.session_state["_sens_df"]
                .style
                .format("${:.1f}M", na_rep="\u2014")
                .background_gradient(cmap="RdYlGn", axis=None),
                use_container_width=True,
            )

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — DEAL LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

with tab_library:
    st.subheader("Saved Deals")
    deals = db.list_deals()

    if not deals:
        st.info("No saved deals yet. Use the Deal Builder tab to create and save one.")
    else:
        # Header row
        hc1, hc2, hc3, hc4 = st.columns([4, 2, 2, 3])
        hc1.markdown("**Name**")
        hc2.markdown("**Created**")
        hc3.markdown("**Updated**")
        hc4.markdown("**Actions**")

        for d in deals:
            c1, c2, c3, c4 = st.columns([4, 2, 2, 3])
            c1.write(d["name"])
            c2.caption(d["created_at"][:16])
            c3.caption(d["updated_at"][:16])

            bc1, bc2, bc3 = c4.columns(3)
            if bc1.button("Load", key=f"load_{d['id']}", use_container_width=True):
                loaded = db.load_deal(d["id"])
                if loaded:
                    st.session_state["load_deal_payload"] = loaded["payload"]
                    st.rerun()
            if bc2.button("Copy", key=f"dup_{d['id']}", use_container_width=True):
                loaded = db.load_deal(d["id"])
                if loaded:
                    db.save_deal(loaded["payload"], f"{d['name']} (copy)")
                    st.rerun()
            if bc3.button("Delete", key=f"del_{d['id']}", use_container_width=True):
                db.delete_deal(d["id"])
                st.rerun()
