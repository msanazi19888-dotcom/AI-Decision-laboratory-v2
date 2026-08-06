from app.laboratory.loaders.demo_data_loader import DemoDataLoader

loader = DemoDataLoader()

data = loader.load()

print("\nProducts")
print(data["products"].head())

print("\nSales")
print(data["sales"].head())

print("\nInventory")
print(data["inventory"].head())

print("\nFinance")
print(data["finance"].head())

print("\nSuppliers")
print(data["suppliers"].head())

print("\nPolicies")
print(data["policies"])