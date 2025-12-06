# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Health Counselor Assistant** - a Solace Agent Mesh demo application that implements a multi-agent AI system for holistic health management. The system uses Solace's event mesh for inter-agent communication and an orchestrator pattern where a central agent coordinates multiple specialized health agents.

The focus areas are:
- **Biomarkers** - Lab results, blood tests, vital signs tracking
- **Fitness** - Wearable data: steps, heart rate, sleep, workouts
- **Diet** - Nutrition tracking, meal logs, dietary patterns
- **Mental Wellness** - Self-reported mood, stress, journaling

## Commands

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run the orchestrator (main coordinator)
sam run configs/agents/health-orchestrator.yaml

# Run the web UI gateway
sam run configs/gateways/webui.yaml

# Run specialized health agents (in separate terminals)
sam run configs/agents/biomarker-agent.yaml
sam run configs/agents/fitness-agent.yaml
sam run configs/agents/diet-agent.yaml
sam run configs/agents/mental-wellness-agent.yaml

# Run the wearable listener for real-time data (optional)
sam run configs/agents/wearable-listener-agent.yaml

# Simulate wearable data events
python scripts/wearable_simulator.py --scenario random --interval 10
python scripts/wearable_simulator.py --scenario workout --workout-type running
python scripts/wearable_simulator.py --scenario elevated-hr
```

### Dependencies

```bash
pip install -r requirements.txt  # Installs solace-agent-mesh

# Install required plugins (from SolaceLabs core plugins repo)
sam plugin install sam-sql-database      # For SQL-based health agents
```

## Architecture

### Agent Mesh Pattern

The system implements a hub-and-spoke architecture with:

1. **HealthCounselorOrchestrator** (`configs/agents/health-orchestrator.yaml`) - Central coordinator that:
   - Receives health queries from the WebUI gateway
   - Analyzes requests and determines which health agents to consult
   - Coordinates multi-agent workflows for holistic health analysis
   - Provides personalized health recommendations

2. **Specialized Health Agents** - Domain-specific agents that communicate via Solace broker:
   - **BiomarkerAgent** - Lab results, blood tests, vital signs (loads `CSV_Data/biomarker_data.csv`)
   - **FitnessAgent** - Activity, sleep, heart rate, workouts (loads `CSV_Data/fitness_data.csv`)
   - **DietAgent** - Nutrition, meals, macros, hydration (loads `CSV_Data/diet_logs.csv`)
   - **MentalWellnessAgent** - Mood, stress, energy, journaling (loads `CSV_Data/mental_wellness.csv`)
   - **WearableListenerAgent** - Real-time streaming from fitness wearables

3. **WebUI Gateway** (`configs/gateways/webui.yaml`) - HTTP/SSE gateway for user interaction

### Communication Flow

```
User <-> WebUI Gateway <-> Solace Broker <-> HealthCounselorOrchestrator <-> Health Agents
                                    ^
                                    |
                          WearableListenerAgent (real-time events)
```

### Real-Time Wearable Data Flow

```
Wearable Device -> Simulator -> Solace Topic -> WearableListenerAgent -> FitnessAgent (DB update)
                                                         |
                                                         v
                                              health_notifications.log (alerts)
```

Topic pattern: `health/events/wearable/{data_type}/update`
Data types: `heart_rate`, `steps`, `sleep`, `workout`, `stress`

### Key Configuration Structure

- `configs/shared_config.yaml` - Shared broker connection, LLM models, and service configs
- `configs/agents/*.yaml` - Individual agent configurations with tools, instructions, and agent cards
- `configs/gateways/webui.yaml` - Gateway config including speech (STT/TTS) settings

### Agent Configuration Patterns

Each agent config includes:
- `broker:` - Solace connection using YAML anchors from shared_config
- `model:` - LLM model reference (planning or general model)
- `instruction:` - System prompt defining agent behavior and health expertise
- `tools:` - Available tools (builtin, builtin-group, or python modules)
- `agent_card:` - Description and skills for agent discovery
- `inter_agent_communication:` - Allow/deny lists for agent-to-agent calls

SQL-based agents (Biomarker, Fitness, Diet, MentalWellness) use:
- `agent_init_function` - Initializes SQLite database and loads CSV data
- `agent_cleanup_function` - Cleans up resources on shutdown
- `execute_sql_query` tool - Query health data with natural language

### Environment Variables

Required in `.env`:
- `LLM_SERVICE_ENDPOINT` - LLM API endpoint
- `LLM_SERVICE_API_KEY` - API key for LLM
- `LLM_SERVICE_PLANNING_MODEL_NAME` / `LLM_SERVICE_GENERAL_MODEL_NAME` - Model identifiers
- `SOLACE_BROKER_URL` - Broker WebSocket URL (default: ws://localhost:8008)
- `NAMESPACE` - Topic namespace for agent discovery
- `FASTAPI_HOST` / `FASTAPI_PORT` - WebUI gateway binding
- `DATA_PATH` - Path to data directory (for CSV files)
- `WEARABLE_TOPIC_PREFIX` - Topic prefix for wearable events (default: health/events)

### Data Files

Located in `CSV_Data/`:
- `biomarker_data.csv` - Lab test results with reference ranges
- `fitness_data.csv` - Daily activity metrics from wearables
- `diet_logs.csv` - Meal logs with nutrition information
- `mental_wellness.csv` - Self-reported mood and wellness data

### Plugin System

SQL agents use the `sam_sql_database` plugin with lifecycle functions:
- `agent_init_function` - Initializes database connections, imports CSV data
- `agent_cleanup_function` - Cleans up resources on shutdown

### Wearable Listener

The WearableListenerAgent uses custom lifecycle code in `src/wearable_listener/`:
- `lifecycle.py` - Manages Solace subscription to wearable topics
- `tools.py` - Tools for checking pending events and formatting alerts

### Artifact Management

Agents share files through an artifact service:
- Type: filesystem (default path: `/tmp/samv2`)
- Scope: namespace (shared across agents in same namespace)
- Handling modes: "reference" or "embed"

## Example Health Queries

- "How has my sleep been this week?"
- "What's my average resting heart rate trend?"
- "Am I meeting my protein goals?"
- "Show me my mood patterns and what activities correlate with good moods"
- "What are my latest cholesterol results compared to last time?"
- "Why am I always tired in the afternoons?"
- "Give me a comprehensive health summary for the past month"
