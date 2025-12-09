# Development Guide

This guide covers extending and customizing the Health Counselor demo.

## Project Structure

```
health-counselor-demo/
├── configs/
│   ├── shared_config.yaml          # Shared broker, model, service configs
│   ├── logging_config.yaml         # Logging configuration
│   ├── agents/                     # Agent configurations
│   │   ├── health-orchestrator.yaml
│   │   ├── wearable-listener-agent.yaml
│   │   ├── biomarker-agent.yaml
│   │   ├── fitness-agent.yaml
│   │   ├── diet-agent.yaml
│   │   └── mental-wellness-agent.yaml
│   └── gateways/
│       └── webui.yaml              # HTTP/SSE gateway
├── src/
│   ├── wearable_listener/          # Wearable listener lifecycle and tools
│   │   ├── lifecycle.py            # Solace subscription management
│   │   ├── tools.py                # Data processing tools
│   │   ├── anomaly_detector.py     # Anomaly detection logic
│   │   └── goal_tracker.py         # Goal tracking logic
│   └── automation/
│       └── scheduler.py            # Scheduled automation
├── server/
│   └── dashboard_api/              # FastAPI backend
│       ├── main.py
│       ├── database.py
│       └── models/
├── client/
│   └── dashboard/                  # React frontend
│       ├── src/
│       └── public/
├── scripts/
│   ├── wearable_simulator.py       # Wearable data simulator
│   └── populate_databases.py       # Database initialization
├── tests/                          # Test suite
├── CSV_Data/                       # Source data files
└── *.db                            # SQLite databases
```

## Adding a New Health Agent

### 1. Create Agent Configuration

Create a new YAML file in `configs/agents/`:

```yaml
---
log_config: !include ../logging_config.yaml
shared_config: !include ../shared_config.yaml

name: my-health-agent

agents:
  - name: MyHealthAgent
    broker: *default_broker
    model: *general_model
    instruction: |
      You are a specialized health agent for [your domain].

      Your capabilities include:
      - [Capability 1]
      - [Capability 2]

      When queried, provide clear, actionable health insights.

    tools:
      - name: builtin-group:data_analysis
      - name: sam_sql_database:execute_sql_query
        config:
          database_path: ${DATA_PATH}/my_health.db

    agent_card:
      description: "Agent for [health domain] analysis"
      skills:
        - name: my-health-skill
          description: "Analyzes [specific health data]"

    inter_agent_communication:
      allow_list: ["*"]
```

### 2. Create Data Source (Optional)

If your agent needs a database:

1. Create a CSV file in `CSV_Data/my_health_data.csv`
2. Add initialization function to load data
3. Configure `agent_init_function` in the agent YAML

### 3. Start the Agent

```bash
sam run configs/agents/my-health-agent.yaml
```

The orchestrator will automatically discover the new agent via its agent card.

## Modifying Agent Behavior

### Changing Agent Instructions

Edit the `instruction` field in the agent's YAML config:

```yaml
instruction: |
  You are a specialized agent for...

  Guidelines:
  - Be concise and actionable
  - Cite specific data points
  - Suggest follow-up actions
```

### Adding Custom Tools

Create a Python module with tool definitions:

```python
# src/my_agent/tools.py
from solace_agent_mesh.tools import tool

@tool
def my_custom_tool(param1: str, param2: int) -> str:
    """Description of what this tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value
    """
    # Implementation
    return result
```

Then reference in agent config:

```yaml
tools:
  - name: src.my_agent.tools:my_custom_tool
```

## Connecting to Different Data Sources

### External Databases

Modify the SQL plugin configuration:

```yaml
tools:
  - name: sam_sql_database:execute_sql_query
    config:
      database_type: postgresql  # or mysql, sqlite
      connection_string: ${DATABASE_URL}
```

### API Data Sources

Create custom tools that fetch from external APIs:

```python
@tool
def fetch_external_data(query: str) -> dict:
    """Fetch data from external health API."""
    response = requests.get(f"{API_URL}/data", params={"q": query})
    return response.json()
```

## Testing

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
DATA_PATH="$(pwd)" pytest tests/ -v

# Run specific test file
DATA_PATH="$(pwd)" pytest tests/test_health_queries.py -v

# Run with coverage
DATA_PATH="$(pwd)" pytest tests/ --cov=src
```

### Running Evaluations (Agent Mesh)

With agents running, you can sanity-check demo flows via the evaluation suite:

```bash
pip install solace-agent-mesh
# Required for sam eval
pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"
sam eval configs/evaluations/demo-scenarios.json
```

- Scenario 3 requires the wearable listener plus the simulator: `python scripts/wearable_simulator.py --scenario workout --duration 60`.

### Writing Tests

```python
# tests/test_my_agent.py
import pytest

def test_my_agent_query():
    """Test that agent responds correctly to queries."""
    # Setup
    # Execute
    # Assert
```

## Dashboard Development

### Backend API

```bash
# Run with auto-reload
source venv/bin/activate
DATA_PATH="$(pwd)" uvicorn server.dashboard_api.main:app --port 8082 --reload
```

API documentation: http://localhost:8082/docs

### Frontend

```bash
cd client/dashboard

# Install dependencies
npm install

# Development server with hot reload
npm run dev

# Production build
npm run build
```

Frontend: http://localhost:3000

## Privacy & Security Considerations

For production deployment:

- Implement proper authentication and authorization
- Encrypt data at rest and in transit
- Follow HIPAA/GDPR compliance requirements
- Use secure credential management (e.g., HashiCorp Vault)
- Implement audit logging for data access
- Consider data anonymization for analytics
