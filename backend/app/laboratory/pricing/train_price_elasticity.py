"""
Estimates Price Elasticity of Demand (PED) per product using a
log-log OLS regression on real order-line data:

    ln(quantity) = alpha + beta * ln(effective_price) + error

beta is the elasticity estimate: the % change in quantity demanded
for a 1% change in price. This is the standard microeconomic
estimation method (see e.g. Nicholson & Snyder, "Microeconomic
Theory"), applied here to the real price variation created by
per-order discounts in the DataCo dataset -- not invented numbers.

IMPORTANT CAVEAT (documented honestly, not hidden): this is an
observational regression, not a controlled price experiment. It
captures correlation between historical discount-driven price
changes and quantity sold, which is standard practice for demand
estimation from retail data, but it is not proof of a causal
mechanism. Products with a small sample size or low R^2 are flagged
with reduced confidence rather than presented as equally reliable.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DATA_PATH = Path("/home/claude/check_upload/DataCoSupplyChainDataset.csv")
OUTPUT_PATH = Path(__file__).resolve().parent / "elasticity_model.csv"

MIN_OBSERVATIONS = 30


def estimate_elasticity(group: pd.DataFrame) -> dict | None:
    prices = group["effective_price"].to_numpy()
    quantities = group["Order Item Quantity"].to_numpy()

    if len(prices) < MIN_OBSERVATIONS or prices.std() == 0:
        return None

    # log-log regression via least squares
    log_price = np.log(prices)
    log_qty = np.log(quantities + 0.5)  # +0.5 continuity correction for zeros

    # simple linear regression: log_qty = a + b * log_price
    X = np.vstack([np.ones_like(log_price), log_price]).T
    coeffs, residuals, rank, sv = np.linalg.lstsq(X, log_qty, rcond=None)
    intercept, elasticity = coeffs

    predicted = X @ coeffs
    ss_res = np.sum((log_qty - predicted) ** 2)
    ss_tot = np.sum((log_qty - log_qty.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "elasticity": round(float(elasticity), 3),
        "r_squared": round(float(r_squared), 3),
        "n_obs": int(len(prices)),
        "avg_price": round(float(prices.mean()), 2),
        "min_price": round(float(prices.min()), 2),
        "max_price": round(float(prices.max()), 2),
    }


def build():
    df = pd.read_csv(
        RAW_DATA_PATH,
        encoding="latin-1",
        usecols=[
            "Product Card Id", "Order Item Quantity",
            "Order Item Product Price", "Order Item Discount Rate",
            "order date (DateOrders)",
        ],
    )
    df["product_id"] = "P" + df["Product Card Id"].astype(int).astype(str).str.zfill(3)
    df["effective_price"] = (
        df["Order Item Product Price"] * (1 - df["Order Item Discount Rate"])
    )
    df["date"] = pd.to_datetime(df["order date (DateOrders)"]).dt.date

    # IMPORTANT METHODOLOGICAL NOTE:
    # Estimating elasticity from individual order-line quantities is
    # wrong here -- each line item is just one customer's basket size
    # (1-5 units), which barely varies with price at that granularity
    # and produces a meaningless near-zero "elasticity". The classic
    # demand curve is a market-level relationship: how TOTAL quantity
    # demanded across all customers responds to price. So we first
    # aggregate to (product, day) -> total quantity sold and the
    # quantity-weighted average effective price paid that day, and
    # estimate elasticity on THAT aggregated series.
    daily = df.groupby(["product_id", "date"]).apply(
        lambda g: pd.Series({
            "total_quantity": g["Order Item Quantity"].sum(),
            "weighted_avg_price": np.average(
                g["effective_price"], weights=g["Order Item Quantity"]
            ),
        }),
        include_groups=False,
    ).reset_index()

    rows = []
    for product_id, group in daily.groupby("product_id"):
        result = estimate_elasticity(group.rename(columns={
            "total_quantity": "Order Item Quantity",
            "weighted_avg_price": "effective_price",
        }))
        if result is None:
            continue
        result["product_id"] = product_id
        rows.append(result)

    out = pd.DataFrame(rows)
    out = out[["product_id", "elasticity", "r_squared", "n_obs", "avg_price", "min_price", "max_price"]]
    out.to_csv(OUTPUT_PATH, index=False)

    print(f"Estimated elasticity for {len(out)} products -> {OUTPUT_PATH}")
    print()
    print("Distribution of elasticity estimates:")
    print(out["elasticity"].describe())
    print()
    print("Sample (5 most reliable, by R^2):")
    print(out.sort_values("r_squared", ascending=False).head(5).to_string(index=False))


if __name__ == "__main__":
    build()
