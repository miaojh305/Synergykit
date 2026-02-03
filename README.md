# SynergyKit

CLI tool for M&A synergy analysis. Estimates cost and revenue synergies, models integration ramp-up, computes NPV, and generates a consulting-style deal memo.

Designed for Corp Dev / IB / PE deal teams who need fast, repeatable synergy analysis from structured inputs.

## Quick Start

### CLI

```bash
pip install -r requirements.txt
python run.py examples/sample_deal.json --output-dir output
```

Outputs:
- `synergy_schedule.csv` — annual synergy cash flow schedule
- `summary.csv` — scalar summary metrics (NPV, totals, etc.)
- `deal_memo.md` — Markdown deal memo ready for review

### Web UI

```bash
pip install -r requirements.txt
streamlit run app.py
```

The Streamlit app provides:
- **Deal Builder** — form-based inputs, interactive synergy tables, Plotly visuals, sensitivity analysis, and downloadable outputs
- **Deal Library** — save, load, duplicate, and delete deal configurations (stored in `synergykit.db`)

Saved deals are persisted in a SQLite database (`synergykit.db`) created automatically in the repo root.

## Input Format

The input is a JSON file with this structure:

```json
{
  "metadata": {
    "deal_name": "Acquirer / Target",
    "acquirer": "Acquirer Corp",
    "target": "Target Inc",
    "date": "2025-06-15",
    "analyst": "Name"
  },
  "deal_terms": {
    "enterprise_value": 500.0,
    "discount_rate": 0.10,
    "projection_years": 5
  },
  "cost_synergies": [
    {
      "category": "procurement",
      "description": "Vendor consolidation",
      "run_rate": 15.0,
      "ramp_up": [0.25, 0.50, 0.75, 1.00]
    }
  ],
  "revenue_synergies": [
    {
      "category": "cross_sell",
      "description": "Cross-sell into target channels",
      "run_rate": 8.0
    }
  ],
  "integration_costs": [
    {
      "category": "severance",
      "description": "Workforce reduction",
      "amount": 12.0,
      "year": 1
    }
  ]
}
```

### Field Reference

**metadata** (required)
| Field | Type | Description |
|-------|------|-------------|
| `deal_name` | string | Name of the deal |
| `acquirer` | string | Acquiring company |
| `target` | string | Target company |
| `date` | string | Analysis date (YYYY-MM-DD) |
| `analyst` | string | Analyst name (optional, defaults to empty) |

**deal_terms** (required)
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enterprise_value` | float | — | Purchase price in $M |
| `discount_rate` | float | — | Discount rate as decimal (e.g. 0.10) |
| `projection_years` | int | 5 | Years to project (1-10) |

**cost_synergies** (list)
| Field | Type | Description |
|-------|------|-------------|
| `category` | enum | `procurement` or `sga` |
| `description` | string | What this synergy is |
| `run_rate` | float | Annual run-rate in $M at full realization |
| `ramp_up` | list[float] | Optional custom ramp-up curve (fractions 0-1 per year) |

**revenue_synergies** (list)
| Field | Type | Description |
|-------|------|-------------|
| `category` | enum | `cross_sell` |
| `description` | string | What this synergy is |
| `run_rate` | float | Annual run-rate in $M at full realization |
| `ramp_up` | list[float] | Optional custom ramp-up curve |

**integration_costs** (list)
| Field | Type | Description |
|-------|------|-------------|
| `category` | enum | `severance`, `it_integration`, `rebranding`, `advisory_fees`, `restructuring`, `other` |
| `description` | string | What this cost covers |
| `amount` | float | One-time cost in $M |
| `year` | int | Year incurred (must be within projection_years) |

### Default Ramp-Up Curves

If `ramp_up` is omitted, standard IB conventions apply:

| Type | Year 1 | Year 2 | Year 3 | Year 4+ |
|------|--------|--------|--------|---------|
| Cost synergies | 25% | 50% | 75% | 100% |
| Revenue synergies | 0% | 15% | 40% | 70% |

Custom curves are specified as a list of fractions. If shorter than `projection_years`, the last value carries forward.

## Methodology

1. **Gross synergies** are computed per line item by applying the ramp-up curve to the run-rate for each projection year.
2. **Integration costs** are one-time amounts allocated to their specified year.
3. **Net synergy cash flow** = gross synergies minus integration costs, per year.
4. **NPV** is calculated on the net cash flow stream using the specified discount rate.

Based on standard investment banking synergy modeling conventions and the Koller/McKinsey valuation framework.

## Requirements

- Python 3.10+
- pydantic >= 2.0
- pandas >= 2.0
- numpy-financial >= 1.0
- streamlit >= 1.30
- plotly >= 5.0

## Project Structure

```
synergykit/
  synergykit/
    __init__.py       # Package init
    schema.py         # Pydantic input models
    engine.py         # Synergy calculations
    memo.py           # Deal memo generator
    db.py             # SQLite persistence layer
  app.py              # Streamlit web UI
  run.py              # CLI entry point
  examples/
    sample_deal.json  # Example input
  output/             # Default output directory
  synergykit.db       # SQLite database (auto-created)
  requirements.txt
```

## License

MIT
