from pathlib import Path
import pandas as pd
import json


class DemoDataLoader:
    def __init__(self, company_name="smart_distribution"):
        self.base_path = (
            Path(__file__)
            .resolve()
            .parents[2]
            / "demo_data"
            / company_name
        )

    def load(self):
        return {
            "products": pd.read_csv(self.base_path / "products.csv"),
            "sales": pd.read_csv(self.base_path / "sales.csv"),
            "inventory": pd.read_csv(self.base_path / "inventory.csv"),
            "finance": pd.read_csv(self.base_path / "finance.csv"),
            "suppliers": pd.read_csv(self.base_path / "suppliers.csv"),
            "policies": json.load(
                open(
                    self.base_path / "policies.json",
                    encoding="utf-8",
                )
            ),
        }