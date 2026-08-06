class DecisionContext:
    def __init__(
        self,
        decision_type,
        business_objective,
        priority,
        product_id,
        requested_quantity,
        company_data,
    ):
        self.decision_type = decision_type
        self.business_objective = business_objective
        self.priority = priority
        self.product_id = product_id
        self.requested_quantity = requested_quantity
        self.company_data = company_data

    def to_dict(self):
        return {
            "decision_type": self.decision_type,
            "business_objective": self.business_objective,
            "priority": self.priority,
            "product_id": self.product_id,
            "requested_quantity": self.requested_quantity,
            "company_data": self.company_data,
        }