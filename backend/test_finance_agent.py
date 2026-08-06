from app.laboratory.context.enterprise_knowledge_hub import EnterpriseKnowledgeHub
from app.laboratory.context.decision_context_builder import DecisionContextBuilder
from app.laboratory.agents.finance_agent import FinanceAgent

# Load company data
hub = EnterpriseKnowledgeHub()

# Build Decision Context
builder = DecisionContextBuilder(hub)
decision_context = builder.build()

# Run Finance Agent
agent = FinanceAgent()
result = agent.analyze(decision_context)

print(result)