# SynergyKit

## The Problem
Deal teams (Corp Dev / IB / PE) spend hours rebuilding the same synergy model in Excel for every deal. There is no standardized, repeatable CLI tool to estimate synergies, model integration ramp-up, and produce a clean deal memo from structured inputs.

## Success Looks Like
A deal team member drops a JSON file with synergy assumptions and deal terms, runs one command, and gets CSV tables (synergy schedule, net cash flows) plus a polished Markdown deal memo ready for review.

## Building On
- **numpy-financial** — NPV calculation
- **pandas** — Tabular schedule generation, CSV export
- **Pydantic** — Input validation and schema enforcement
- **Standard IB phase-in conventions** — Cost: 25/50/75/100%, Revenue: 0/15/40/70%
- **Koller/McKinsey synergy taxonomy** — Cost synergies, revenue synergies, integration costs

## The Unique Part
- Consulting-grade synergy taxonomy built into the JSON input schema
- IB-style ramp-up curves applied per synergy category
- Annual net synergy cash flow schedule with NPV at a single discount rate
- Auto-generated Markdown deal memo (executive summary, synergy breakdown, timeline, NPV conclusion)

## Tech Stack
- **Runtime:** Python 3.10+
- **CLI:** argparse
- **Validation:** Pydantic v2
- **Calculations:** numpy-financial, pandas
- **Output:** CSV files + Markdown deal memo
- **Input:** JSON

## Scope (v1 MVP)
Included:
- Cost synergies (procurement, SG&A reduction)
- Revenue synergies (cross-sell uplift)
- One-time integration costs
- Standard IB ramp-up curves
- Annual net synergy cash flows
- NPV at a single discount rate
- Markdown deal memo

Excluded (future):
- Probability-weighted NPV
- Accretion/dilution analysis
- Damodaran V(C) - V(A) - V(T)
- Full sensitivity tables
- UI / external data feeds

## Open Questions
- None at this stage
