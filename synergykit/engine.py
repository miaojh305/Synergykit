"""Synergy engine — core calculations for SynergyKit."""

from __future__ import annotations

from dataclasses import dataclass

import numpy_financial as npf
import pandas as pd

from synergykit.schema import (
    DEFAULT_COST_RAMP,
    DEFAULT_REVENUE_RAMP,
    DealInput,
)


@dataclass
class EngineResult:
    """Container for all computed outputs."""

    synergy_schedule: pd.DataFrame   # Year-by-year synergy breakdown
    summary: dict                    # Scalar summary metrics


def _expand_ramp(ramp: list[float], years: int) -> list[float]:
    """Expand a ramp-up curve to cover the full projection period.

    If the ramp is shorter than projection_years, the last value is
    carried forward (i.e. run-rate is sustained). If longer, it is
    truncated to match.
    """
    if len(ramp) >= years:
        return ramp[:years]
    return ramp + [ramp[-1]] * (years - len(ramp))


def run(deal: DealInput) -> EngineResult:
    """Execute the synergy model and return computed results."""

    years = deal.deal_terms.projection_years
    year_labels = list(range(1, years + 1))

    # ------------------------------------------------------------------
    # 1. Build gross synergy rows by category
    # ------------------------------------------------------------------

    rows: list[dict] = []

    for item in deal.cost_synergies:
        ramp = _expand_ramp(item.ramp_up or DEFAULT_COST_RAMP, years)
        for y_idx, yr in enumerate(year_labels):
            rows.append({
                "year": yr,
                "type": "cost",
                "category": item.category.value,
                "description": item.description,
                "run_rate": item.run_rate,
                "ramp_pct": ramp[y_idx],
                "realized": item.run_rate * ramp[y_idx],
            })

    for item in deal.revenue_synergies:
        ramp = _expand_ramp(item.ramp_up or DEFAULT_REVENUE_RAMP, years)
        for y_idx, yr in enumerate(year_labels):
            rows.append({
                "year": yr,
                "type": "revenue",
                "category": item.category.value,
                "description": item.description,
                "run_rate": item.run_rate,
                "ramp_pct": ramp[y_idx],
                "realized": item.run_rate * ramp[y_idx],
            })

    detail = pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 2. Aggregate to annual schedule
    # ------------------------------------------------------------------

    # Gross synergies per year (cost + revenue combined)
    gross_by_year = detail.groupby("year")["realized"].sum()

    # Gross by type per year
    cost_by_year = (
        detail[detail["type"] == "cost"]
        .groupby("year")["realized"]
        .sum()
        .reindex(year_labels, fill_value=0.0)
    )
    revenue_by_year = (
        detail[detail["type"] == "revenue"]
        .groupby("year")["realized"]
        .sum()
        .reindex(year_labels, fill_value=0.0)
    )

    # Integration costs per year
    ic_by_year = pd.Series(0.0, index=year_labels)
    for ic in deal.integration_costs:
        ic_by_year[ic.year] += ic.amount

    # Net synergy cash flow
    net_cf = gross_by_year.reindex(year_labels, fill_value=0.0) - ic_by_year

    # Cumulative net cash flow
    cumulative_cf = net_cf.cumsum()

    # ------------------------------------------------------------------
    # 3. Build the schedule DataFrame
    # ------------------------------------------------------------------

    schedule = pd.DataFrame({
        "year": year_labels,
        "gross_cost_synergies": cost_by_year.values,
        "gross_revenue_synergies": revenue_by_year.values,
        "gross_total_synergies": (cost_by_year + revenue_by_year).values,
        "integration_costs": ic_by_year.values,
        "net_synergy_cf": net_cf.values,
        "cumulative_net_cf": cumulative_cf.values,
    })

    # ------------------------------------------------------------------
    # 4. NPV of net synergy cash flows
    # ------------------------------------------------------------------

    r = deal.deal_terms.discount_rate
    npv = float(npf.npv(r, [0.0] + list(net_cf.values)))  # year-0 = 0

    # ------------------------------------------------------------------
    # 5. Summary metrics
    # ------------------------------------------------------------------

    total_integration = float(ic_by_year.sum())
    total_run_rate = (
        sum(s.run_rate for s in deal.cost_synergies)
        + sum(s.run_rate for s in deal.revenue_synergies)
    )

    summary = {
        "deal_name": deal.metadata.deal_name,
        "acquirer": deal.metadata.acquirer,
        "target": deal.metadata.target,
        "enterprise_value": deal.deal_terms.enterprise_value,
        "discount_rate": r,
        "projection_years": years,
        "total_run_rate_synergies": total_run_rate,
        "total_cost_synergy_run_rate": sum(
            s.run_rate for s in deal.cost_synergies
        ),
        "total_revenue_synergy_run_rate": sum(
            s.run_rate for s in deal.revenue_synergies
        ),
        "total_integration_costs": total_integration,
        "npv_net_synergies": round(npv, 2),
        "synergy_npv_as_pct_ev": round(npv / deal.deal_terms.enterprise_value * 100, 2),
    }

    return EngineResult(synergy_schedule=schedule, summary=summary)
