"""
Serves price elasticity estimates and simulates the effect of a
proposed price change on demand and revenue.

Confidence is tied directly to the regression's R^2 (how much of the
real historical variance in demand the price actually explained) --
not a hardcoded number. Low-R^2 estimates are flagged explicitly
rather than presented with false confidence, and economically
atypical results (positive elasticity, i.e. demand rising with price)
are called out rather than silently reported.
"""

from pathlib import Path

import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "elasticity_model.csv"


class PriceElasticityService:
    def __init__(self):
        self.table = pd.read_csv(MODEL_PATH).set_index("product_id")

    def simulate(
        self,
        product_id: str,
        price_change_pct: float,
        baseline_expected_demand_during_lead_time: float | None = None,
        baseline_safety_stock: float | None = None,
        baseline_available_stock: float | None = None,
        baseline_requested_quantity: float | None = None,
    ) -> dict:
        if product_id not in self.table.index:
            return {
                "product_id": product_id,
                "available": False,
                "reason": (
                    "Not enough historical price variation for this product "
                    "to estimate elasticity reliably (fewer than 30 days of "
                    "aggregated sales data with varying price)."
                ),
            }

        row = self.table.loc[product_id]
        elasticity = float(row["elasticity"])
        r_squared = float(row["r_squared"])
        n_obs = int(row["n_obs"])
        avg_price = float(row["avg_price"])

        predicted_qty_change_pct = elasticity * price_change_pct
        new_price = avg_price * (1 + price_change_pct / 100)

        # Revenue impact combines both effects: price per unit changes,
        # AND predicted quantity changes in response.
        revenue_index_before = avg_price * 100  # arbitrary base quantity = 100
        new_qty_index = 100 * (1 + predicted_qty_change_pct / 100)
        revenue_index_after = new_price * new_qty_index
        revenue_change_pct = (
            (revenue_index_after - revenue_index_before) / revenue_index_before * 100
        )

        confidence = round(min(0.95, max(0.15, r_squared)), 2)

        # Explicit reliability tier, not just a numeric confidence --
        # makes it possible for the frontend (or a future filter) to
        # separate estimates worth acting on from exploratory-only ones.
        if r_squared >= 0.15:
            reliability = "reliable"
        elif r_squared >= 0.05:
            reliability = "low_reliability"
        else:
            reliability = "exploratory_only"

        caveats = [
            "This is an observational estimate from historical discount-driven "
            "price variation, not a controlled price experiment -- treat as "
            "directional evidence, not a guarantee."
        ]
        if r_squared < 0.15:
            caveats.append(
                f"R\u00b2 is low ({r_squared}), meaning price explains only a "
                f"small share of this product's historical demand variation. "
                f"Confidence in this specific estimate is limited."
            )
        if elasticity > 0 and r_squared < 0.2:
            caveats.append(
                "The estimated elasticity is positive (demand appears to rise "
                "with price), which is economically atypical for most goods "
                "and, given the low R\u00b2, is more likely statistical noise "
                "than a real effect."
            )

        result = {
            "product_id": product_id,
            "available": True,
            "elasticity": elasticity,
            "r_squared": r_squared,
            "n_obs": n_obs,
            "confidence": confidence,
            "reliability": reliability,
            "current_avg_price": round(avg_price, 2),
            "proposed_price": round(new_price, 2),
            "price_change_pct": price_change_pct,
            "predicted_quantity_change_pct": round(predicted_qty_change_pct, 2),
            "predicted_revenue_change_pct": round(revenue_change_pct, 2),
            "caveats": caveats,
        }

        # Close the loop with the actual reorder decision: at this
        # hypothetical price, how many units would you actually need
        # to order? Without this, the panel answers "what happens to
        # revenue" but not "does this change what I should buy" --
        # which is the question that makes a price simulation useful
        # to someone about to place a purchase order.
        if (
            baseline_expected_demand_during_lead_time is not None
            and baseline_safety_stock is not None
            and baseline_available_stock is not None
        ):
            adjusted_demand_during_lead_time = (
                baseline_expected_demand_during_lead_time
                * (1 + predicted_qty_change_pct / 100)
            )
            adjusted_target_stock_level = (
                adjusted_demand_during_lead_time + baseline_safety_stock
            )
            adjusted_requested_quantity = max(
                0, round(adjusted_target_stock_level - baseline_available_stock)
            )
            result["baseline_requested_quantity"] = (
                round(baseline_requested_quantity)
                if baseline_requested_quantity is not None else None
            )
            result["adjusted_requested_quantity"] = adjusted_requested_quantity
            result["quantity_change"] = (
                adjusted_requested_quantity - round(baseline_requested_quantity)
                if baseline_requested_quantity is not None else None
            )

        return result
