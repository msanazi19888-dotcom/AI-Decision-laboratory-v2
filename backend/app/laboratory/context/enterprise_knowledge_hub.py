from app.laboratory.loaders.demo_data_loader import DemoDataLoader


class EnterpriseKnowledgeHub:
    def __init__(self, company_name="smart_distribution"):
        self.loader = DemoDataLoader(company_name)
        self.data = self.loader.load()

    def get_dataset(self, dataset_name):
        return self.data.get(dataset_name)

    def get_all(self):
        return self.data