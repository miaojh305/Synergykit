"""Deal memo generator — produces a consulting-style Markdown memo."""

from __future__ import annotations

from synergykit.engine import EngineResult
from synergykit.schema import DealInput


def _fmt(value: float, decimals: int = 1) -> str:
    """Format a number with commas and fixed decimals."""
    return f"{value:,.{decimals}f}"


def _pct(value: float) -> str:
    """Format a decimal as a percentage string."""
    return f"{value * 100:.0f}%"


def _build_schedule_table(result: EngineResult) -> str:
    """Render the synergy schedule as a Markdown table."""
    df = result.synergy_schedule
    lines = [
        "| Year | Cost Synergies | Revenue Synergies | Gross Total | Integration Costs | Net Synergy CF | Cumulative CF |",
        "|-----:|---------------:|------------------:|------------:|------------------:|---------------:|--------------:|",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"| {int(row['year'])} "
            f"| {_fmt(row['gross_cost_synergies'])} "
            f"| {_fmt(row['gross_revenue_synergies'])} "
            f"| {_fmt(row['gross_total_synergies'])} "
            f"| {_fmt(row['integration_costs'])} "
            f"| {_fmt(row['net_synergy_cf'])} "
            f"| {_fmt(row['cumulative_net_cf'])} |"
        )
    return "\n".join(lines)


_CATEGORY_LABELS = {
    "procurement": "Procurement",
    "sga": "SG&A",
    "cross_sell": "Cross-Sell",
    "severance": "Severance",
    "it_integration": "IT Integration",
    "rebranding": "Rebranding",
    "advisory_fees": "Advisory Fees",
    "restructuring": "Restructuring",
    "other": "Other",
}


def _label(category_value: str) -> str:
    return _CATEGORY_LABELS.get(category_value, category_value.replace("_", " ").title())


def _build_cost_synergy_detail(deal: DealInput) -> str:
    """List cost synergy line items."""
    if not deal.cost_synergies:
        return "_None._"
    lines = []
    for item in deal.cost_synergies:
        lines.append(
            f"- **{_label(item.category.value)}** — "
            f"{item.description}: ${_fmt(item.run_rate)}M run-rate"
        )
    return "\n".join(lines)


def _build_revenue_synergy_detail(deal: DealInput) -> str:
    """List revenue synergy line items."""
    if not deal.revenue_synergies:
        return "_None._"
    lines = []
    for item in deal.revenue_synergies:
        lines.append(
            f"- **{_label(item.category.value)}** — "
            f"{item.description}: ${_fmt(item.run_rate)}M run-rate"
        )
    return "\n".join(lines)


def _build_integration_cost_detail(deal: DealInput) -> str:
    """List integration cost line items."""
    if not deal.integration_costs:
        return "_None._"
    lines = []
    for item in deal.integration_costs:
        lines.append(
            f"- **{_label(item.category.value)}** — "
            f"{item.description}: ${_fmt(item.amount)}M (Year {item.year})"
        )
    return "\n".join(lines)


def generate(deal: DealInput, result: EngineResult) -> str:
    """Generate a Markdown deal memo from inputs and engine results."""

    s = result.summary
    ev = s["enterprise_value"]
    npv = s["npv_net_synergies"]
    pct_ev = s["synergy_npv_as_pct_ev"]
    total_rr = s["total_run_rate_synergies"]
    cost_rr = s["total_cost_synergy_run_rate"]
    rev_rr = s["total_revenue_synergy_run_rate"]
    total_ic = s["total_integration_costs"]
    years = s["projection_years"]
    rate = s["discount_rate"]

    # Determine breakeven year from the schedule
    schedule = result.synergy_schedule
    breakeven_year = None
    for _, row in schedule.iterrows():
        if row["cumulative_net_cf"] > 0:
            breakeven_year = int(row["year"])
            break

    breakeven_text = (
        f"Year {breakeven_year}" if breakeven_year
        else f"beyond Year {years} (not reached within projection)"
    )

    memo = f"""# Deal Memo: {s['deal_name']}

**Acquirer:** {s['acquirer']}
**Target:** {s['target']}
**Date:** {deal.metadata.date}
**Analyst:** {deal.metadata.analyst or 'N/A'}

---

## Executive Summary

This memo presents the estimated synergy potential for the proposed acquisition of
{s['target']} by {s['acquirer']} at an enterprise value of ${_fmt(ev)}M.

The analysis identifies **${_fmt(total_rr)}M in total run-rate synergies**
(${_fmt(cost_rr)}M cost, ${_fmt(rev_rr)}M revenue), partially offset by
**${_fmt(total_ic)}M in one-time integration costs**. Over a {years}-year
projection, the net present value of synergy cash flows is **${_fmt(npv)}M**
(discounted at {_pct(rate)}), representing **{pct_ev}% of enterprise value**.

Cumulative net cash flow turns positive in **{breakeven_text}**.

---

## Synergy Breakdown

### Cost Synergies — ${_fmt(cost_rr)}M Run-Rate

{_build_cost_synergy_detail(deal)}

Cost synergies follow a standard ramp-up schedule, reaching full run-rate by
Year {min(4, years)}.

### Revenue Synergies — ${_fmt(rev_rr)}M Run-Rate

{_build_revenue_synergy_detail(deal)}

Revenue synergies are phased more conservatively, reflecting the execution
risk inherent in cross-sell and market expansion initiatives.

---

## Integration Costs — ${_fmt(total_ic)}M Total

{_build_integration_cost_detail(deal)}

---

## Annual Net Synergy Cash Flow Schedule ($M)

{_build_schedule_table(result)}

---

## NPV Analysis

| Metric | Value |
|:-------|------:|
| Total Run-Rate Synergies | ${_fmt(total_rr)}M |
| Total Integration Costs | ${_fmt(total_ic)}M |
| Discount Rate | {_pct(rate)} |
| Projection Period | {years} years |
| **NPV of Net Synergies** | **${_fmt(npv)}M** |
| NPV as % of EV | {pct_ev}% |
| Cumulative Breakeven | {breakeven_text} |

---

## Key Caveats

1. **Cost synergies** are generally higher-confidence than revenue synergies.
   Actual realization depends on integration execution quality and timeline.
2. **Revenue synergies** assume successful cross-sell execution and no
   material customer attrition. These are subject to higher execution risk.
3. **Integration costs** are estimated based on initial scoping; actual costs
   may vary depending on systems complexity and organizational alignment.
4. This analysis uses a **single discount rate** ({_pct(rate)}) applied
   uniformly. A risk-adjusted approach (lower rate for cost synergies,
   higher for revenue) would provide additional precision.
5. The model does **not** include accretion/dilution analysis, tax effects,
   or financing structure impacts.

---

*Generated by SynergyKit v0.1.0*
"""
    return memo.strip() + "\n"
