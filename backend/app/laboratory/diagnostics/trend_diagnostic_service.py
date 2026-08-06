"""
Diagnoses whether a product's recent sales change is a genuine trend
or normal seasonal/weekly fluctuation, and reports which observable
factors (discount level, delivery performance, category-wide demand)
are statistically CORRELATED with that change.

Method:
1. STL decomposition (Cleveland et al., 1990 -- the standard classical
   method for splitting a time series into trend, seasonal, and
   residual components) separates genuine trend movement from
   ordinary weekly seasonality, so a "decline" that's actually just a
   predictable weekly dip isn't misread as a real problem.
2. Pearson correlation between the trend component and each candidate
   factor (discount rate, late-delivery rate) over the product's full
   history quantifies how strongly that factor moves together with
   demand.
3. The same recent-vs-prior-period comparison is run at the category
   level: if sibling products in the same category show the same
   directional shift, that points to a market-wide or seasonal cause
   rather than something specific to this one product.

IMPORTANT: correlation is not causation. All output is phrased as
"associated with" / "correlated with", never "caused by". This is
stated explicitly in the API response, not just in code comments.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from statsmodels.tsa.seasonal import STL

BASE_DIR = Path(__file__).resolve().parents[2]
SALES_PATH = BASE_DIR / "demo_data" / "smart_distribution" / "sales.csv"
FACTORS_PATH = BASE_DIR / "demo_data" / "smart_distribution" / "sales_factors.csv"
PRODUCTS_PATH = BASE_DIR / "demo_data" / "smart_distribution" / "products.csv"

RECENT_WINDOW_DAYS = 30
MIN_HISTORY_DAYS = 60


class TrendDiagnosticService:
    def __init__(self):
        self._sales = None
        self._factors = None
        self._products = None

    def _load(self):
        if self._sales is None:
            self._sales = pd.read_csv(SALES_PATH, parse_dates=["date"])
            self._factors = pd.read_csv(FACTORS_PATH, parse_dates=["date"])
            self._products = pd.read_csv(PRODUCTS_PATH)
        return self._sales, self._factors, self._products

    def _daily_series(self, product_id: str) -> pd.Series:
        sales, _, _ = self._load()
        product_sales = sales[sales["product_id"] == product_id]
        if product_sales.empty:
            raise ValueError(f"No sales history for product_id: {product_id}")

        # Reindex to a continuous daily calendar, filling gaps with 0.
        # Unlike individual purchase records, a missing day in the
        # AGGREGATE market-level series is a real "zero demand that
        # day" for a low-volume product, not a missing observation.
        product_sales = (
            product_sales.groupby("date")["quantity_sold"].sum().reset_index()
        )
        full_range = pd.date_range(
            product_sales["date"].min(), product_sales["date"].max(), freq="D"
        )
        series = (
            product_sales.set_index("date")["quantity_sold"]
            .reindex(full_range, fill_value=0)
        )
        return series

    def _decompose(self, series: pd.Series):
        stl = STL(series, period=7, robust=True)
        return stl.fit()

    def diagnose(self, product_id: str) -> dict:
        sales, factors, products = self._load()
        series = self._daily_series(product_id)

        if len(series) < MIN_HISTORY_DAYS:
            return {
                "product_id": product_id,
                "available": False,
                "reason": (
                    f"Only {len(series)} days of history for this product -- "
                    f"need at least {MIN_HISTORY_DAYS} for a reliable trend "
                    f"decomposition."
                ),
            }

        result = self._decompose(series)
        trend = result.trend

        recent = trend[-RECENT_WINDOW_DAYS:]
        prior = trend[-2 * RECENT_WINDOW_DAYS:-RECENT_WINDOW_DAYS]

        raw_recent_avg = series[-RECENT_WINDOW_DAYS:].mean()
        raw_prior_avg = series[-2 * RECENT_WINDOW_DAYS:-RECENT_WINDOW_DAYS].mean()
        raw_change_pct = (
            (raw_recent_avg - raw_prior_avg) / raw_prior_avg * 100
            if raw_prior_avg > 0 else 0.0
        )

        trend_change_pct = (
            (recent.mean() - prior.mean()) / prior.mean() * 100
            if prior.mean() > 0 else 0.0
        )

        direction = (
            "increasing" if trend_change_pct > 5
            else "decreasing" if trend_change_pct < -5
            else "stable"
        )

        # --- Category-wide comparison ---
        category_row = products[products["product_id"] == product_id]
        category = category_row.iloc[0]["category"] if not category_row.empty else None
        category_verdict = None
        category_change_pct = None

        if category:
            category_products = products[products["category"] == category]["product_id"]
            category_sales = sales[sales["product_id"].isin(category_products)]
            category_daily = category_sales.groupby("date")["quantity_sold"].sum()
            category_daily = category_daily.reindex(
                pd.date_range(category_daily.index.min(), category_daily.index.max(), freq="D"),
                fill_value=0,
            )
            if len(category_daily) >= MIN_HISTORY_DAYS:
                cat_recent = category_daily[-RECENT_WINDOW_DAYS:].mean()
                cat_prior = category_daily[-2 * RECENT_WINDOW_DAYS:-RECENT_WINDOW_DAYS].mean()
                category_change_pct = (
                    (cat_recent - cat_prior) / cat_prior * 100 if cat_prior > 0 else 0.0
                )
                same_direction = (
                    (trend_change_pct > 5 and category_change_pct > 5) or
                    (trend_change_pct < -5 and category_change_pct < -5)
                )
                category_verdict = (
                    "category_wide" if same_direction else "product_specific"
                )

        # --- Correlated factors (discount, delivery performance) ---
        product_factors = factors[factors["product_id"] == product_id]
        product_factors = (
            product_factors.groupby("date")[["avg_discount_rate", "late_delivery_rate"]]
            .mean()
        )
        merged = pd.DataFrame({"quantity": series}).join(
            product_factors, how="left"
        )

        correlated_factors = []
        for col, label in [
            ("avg_discount_rate", "Discount level"),
            ("late_delivery_rate", "Late delivery rate"),
        ]:
            valid = merged.dropna(subset=[col])
            if len(valid) >= 20 and valid[col].std() > 0 and valid["quantity"].std() > 0:
                corr, p_value = pearsonr(valid[col], valid["quantity"])
                if abs(corr) >= 0.15:
                    correlated_factors.append({
                        "factor": label,
                        "correlation": round(float(corr), 3),
                        "p_value": round(float(p_value), 4),
                        "direction": "positive" if corr > 0 else "negative",
                        "significant": bool(p_value < 0.05),
                    })

        correlated_factors.sort(key=lambda f: abs(f["correlation"]), reverse=True)

        return {
            "product_id": product_id,
            "available": True,
            "raw_change_pct": round(float(raw_change_pct), 1),
            "underlying_trend_change_pct": round(float(trend_change_pct), 1),
            "direction": direction,
            "category": category,
            "category_change_pct": (
                round(float(category_change_pct), 1) if category_change_pct is not None else None
            ),
            "category_verdict": category_verdict,
            "correlated_factors": correlated_factors,
            "methodology_note": (
                "Trend is isolated from normal weekly seasonality using STL "
                "decomposition. All listed factors are statistically "
                "correlated with demand -- this is observational evidence "
                "of association, not proof that any factor caused the "
                "change."
            ),
        }
