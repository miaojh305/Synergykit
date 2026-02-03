"""Pydantic models defining the SynergyKit JSON input contract."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Default IB-style ramp-up curves (% of run-rate realized each year)
# ---------------------------------------------------------------------------

DEFAULT_COST_RAMP = [0.25, 0.50, 0.75, 1.00]      # Year 1-4
DEFAULT_REVENUE_RAMP = [0.00, 0.15, 0.40, 0.70]    # Year 1-4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CostSynergyCategory(str, Enum):
    procurement = "procurement"
    sga = "sga"


class RevenueSynergyCategory(str, Enum):
    cross_sell = "cross_sell"


class IntegrationCostCategory(str, Enum):
    severance = "severance"
    it_integration = "it_integration"
    rebranding = "rebranding"
    advisory_fees = "advisory_fees"
    restructuring = "restructuring"
    other = "other"


# ---------------------------------------------------------------------------
# Synergy line items
# ---------------------------------------------------------------------------

class CostSynergy(BaseModel):
    """A single cost-synergy line item."""

    category: CostSynergyCategory
    description: str = Field(..., min_length=1)
    run_rate: float = Field(
        ...,
        gt=0,
        description="Annual run-rate value in $M once fully realized.",
    )
    ramp_up: Optional[list[float]] = Field(
        default=None,
        description=(
            "Custom ramp-up curve as list of fractions (0-1) per year. "
            "If omitted, the standard IB cost ramp is used."
        ),
    )


class RevenueSynergy(BaseModel):
    """A single revenue-synergy line item."""

    category: RevenueSynergyCategory
    description: str = Field(..., min_length=1)
    run_rate: float = Field(
        ...,
        gt=0,
        description="Annual run-rate value in $M once fully realized.",
    )
    ramp_up: Optional[list[float]] = Field(
        default=None,
        description=(
            "Custom ramp-up curve as list of fractions (0-1) per year. "
            "If omitted, the standard IB revenue ramp is used."
        ),
    )


class IntegrationCost(BaseModel):
    """A one-time integration cost item."""

    category: IntegrationCostCategory
    description: str = Field(..., min_length=1)
    amount: float = Field(
        ...,
        gt=0,
        description="Total one-time cost in $M.",
    )
    year: int = Field(
        ...,
        ge=1,
        description="Year in which the cost is incurred (1-indexed).",
    )


# ---------------------------------------------------------------------------
# Deal-level input
# ---------------------------------------------------------------------------

class DealTerms(BaseModel):
    """Core deal parameters."""

    enterprise_value: float = Field(
        ...,
        gt=0,
        description="Total enterprise value / purchase price in $M.",
    )
    discount_rate: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Discount rate for NPV as a decimal (e.g. 0.10 for 10%).",
    )
    projection_years: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of years to project synergy cash flows.",
    )


class DealMetadata(BaseModel):
    """Descriptive information for the deal memo header."""

    deal_name: str = Field(..., min_length=1)
    acquirer: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    date: str = Field(
        ...,
        description="Analysis date in YYYY-MM-DD format.",
    )
    analyst: str = Field(default="")


class DealInput(BaseModel):
    """Top-level input model — the full JSON contract."""

    metadata: DealMetadata
    deal_terms: DealTerms
    cost_synergies: list[CostSynergy] = Field(default_factory=list)
    revenue_synergies: list[RevenueSynergy] = Field(default_factory=list)
    integration_costs: list[IntegrationCost] = Field(default_factory=list)

    @model_validator(mode="after")
    def must_have_at_least_one_synergy(self) -> DealInput:
        if not self.cost_synergies and not self.revenue_synergies:
            raise ValueError(
                "At least one cost synergy or revenue synergy must be provided."
            )
        return self

    @model_validator(mode="after")
    def integration_costs_within_projection(self) -> DealInput:
        years = self.deal_terms.projection_years
        for ic in self.integration_costs:
            if ic.year > years:
                raise ValueError(
                    f"Integration cost '{ic.description}' is in year {ic.year}, "
                    f"but projection_years is {years}."
                )
        return self
