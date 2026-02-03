# Roadmap

Building on: numpy-financial, pandas, Pydantic v2, standard IB ramp-up conventions

## Sections

### 1. Input Schema
Pydantic models defining the JSON input contract: deal metadata, cost synergies (procurement, SG&A), revenue synergies (cross-sell), one-time integration costs, deal terms (discount rate, projection years), and default IB ramp-up curves.

### 2. Synergy Engine
Core calculations: apply ramp-up curves to cost/revenue synergies by year, subtract integration costs, produce annual net synergy cash flows, compute NPV at a single discount rate. Output results to CSV.

### 3. Deal Memo Generator
Auto-generate a consulting-style Markdown deal memo from computed results: executive summary, synergy breakdown by category, integration timeline, annual net cash flow schedule, NPV conclusion, and key caveats.

### 4. CLI Wrapper
Thin argparse entry point: `python run.py input.json --output-dir ./output`. Validates input via schema, runs engine, generates CSV + memo to output directory.

### 5. Example Data + README
Realistic sample_deal.json (hypothetical industrial acquisition), expected outputs, and README with usage instructions, input schema reference, and methodology notes. GitHub-ready.
