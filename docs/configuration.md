# Configuration Reference

This document covers all configuration options for the Health Counselor demo.

## Environment Variables

Create a `.env` file in the project root with these settings:

### LLM Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_SERVICE_ENDPOINT` | LLM API endpoint | `https://api.openai.com/v1` |
| `LLM_SERVICE_API_KEY` | API key for LLM | `sk-your-api-key-here` |
| `LLM_SERVICE_PLANNING_MODEL_NAME` | Model for orchestration | `openai/gpt-4o-mini` |
| `LLM_SERVICE_GENERAL_MODEL_NAME` | Model for agents | `openai/gpt-4o-mini` |

### Solace Broker Connection

| Variable | Description | Example |
|----------|-------------|---------|
| `SOLACE_BROKER_URL` | Broker WebSocket URL | `wss://mr-xxx.messaging.solace.cloud:443` |
| `SOLACE_BROKER_USERNAME` | Broker username | `solace-cloud-client` |
| `SOLACE_BROKER_PASSWORD` | Broker password | `your-password` |
| `SOLACE_BROKER_VPN` | Message VPN name | `your-service-name` |
| `USE_TEMPORARY_QUEUES` | Enable temporary queues (dev) | `true` |

> **Note:** Use `wss://` with port `443` for Solace Cloud. Local Docker uses `ws://` with port `8008`.

### Agent Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NAMESPACE` | Topic namespace for agent discovery | `health/` |
| `DATA_PATH` | Path to data directory (CSV files, databases) | Project root |

### WebUI Gateway

| Variable | Description | Default |
|----------|-------------|---------|
| `FASTAPI_HOST` | Gateway bind host | `127.0.0.1` |
| `FASTAPI_PORT` | Gateway port | `8000` |
| `SESSION_SECRET_KEY` | Session encryption key | Generate a secure random string |
| `WEBUI_GATEWAY_ID` | Unique gateway ID | `gdk-gateway-dev` |
| `WEBUI_STATUS_TOPIC` | Status topic for task updates | `${NAMESPACE}/a2a/v1/gateway/status/${WEBUI_GATEWAY_ID}` |
| `WEB_UI_GATEWAY_DATABASE_URL` | Session DB URL (if using SQL sessions) | `sqlite:///webui_gateway.db` |

### Wearable Streaming

| Variable | Description | Default |
|----------|-------------|---------|
| `WEARABLE_TOPIC_PREFIX` | Topic prefix for wearable events | `health/events` |

## Example .env File

```env
# LLM Configuration
LLM_SERVICE_ENDPOINT=https://api.openai.com/v1
LLM_SERVICE_API_KEY=sk-your-api-key-here
LLM_SERVICE_PLANNING_MODEL_NAME=openai/gpt-4o-mini
LLM_SERVICE_GENERAL_MODEL_NAME=openai/gpt-4o-mini

# Solace Cloud Connection
SOLACE_BROKER_URL=wss://mr-connection-xxxxx.messaging.solace.cloud:443
SOLACE_BROKER_VPN=your-service-name
SOLACE_BROKER_USERNAME=solace-cloud-client
SOLACE_BROKER_PASSWORD=your-password-here

# Agent Namespace
NAMESPACE=health/

# WebUI Gateway
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
SESSION_SECRET_KEY=your-secret-key-here
WEBUI_GATEWAY_ID=gdk-gateway-dev
WEBUI_STATUS_TOPIC=health/a2a/v1/gateway/status/gdk-gateway-dev
WEB_UI_GATEWAY_DATABASE_URL=sqlite:///webui_gateway.db

# Data Path (absolute path to project)
DATA_PATH=/path/to/health-counselor-demo
```

## Shared Configuration (mirrors `configs/shared_config.yaml`)

### Broker Connection (anchors)

```yaml
broker_connection: &broker_connection
  dev_mode: ${SOLACE_DEV_MODE, false}
  broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
  broker_username: ${SOLACE_BROKER_USERNAME, default}
  broker_password: ${SOLACE_BROKER_PASSWORD, default}
  broker_vpn: ${SOLACE_BROKER_VPN, default}
  temporary_queue: ${USE_TEMPORARY_QUEUES, true}
```

### LLM Models (LiteLLM-style config)

```yaml
models:
  planning: &planning_model
    model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
    api_base: ${LLM_SERVICE_ENDPOINT}
    api_key: ${LLM_SERVICE_API_KEY}
    parallel_tool_calls: true
    cache_strategy: "5m"

  general: &general_model
    model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
    api_base: ${LLM_SERVICE_ENDPOINT}
    api_key: ${LLM_SERVICE_API_KEY}
    cache_strategy: "5m"

  # Optional models
  image_gen: &image_generation_model
    model: ${IMAGE_MODEL_NAME}
    api_base: ${IMAGE_SERVICE_ENDPOINT}
    api_key: ${IMAGE_SERVICE_API_KEY}

  report_gen: &report_generation_model
    model: ${LLM_REPORT_MODEL_NAME}
    api_base: ${LLM_SERVICE_ENDPOINT}
    api_key: ${LLM_SERVICE_API_KEY}
```

### Services

```yaml
services:
  session_service: &default_session_service
    type: "memory"
    default_behavior: "PERSISTENT"

  artifact_service: &default_artifact_service
    type: "filesystem"
    base_path: "/tmp/samv2"
    artifact_scope: namespace

  data_tools_config: &default_data_tools_config
    sqlite_memory_threshold_mb: 100
    max_result_preview_rows: 50
    max_result_preview_bytes: 4096
```

## Production .env Notes

Use the development template above as a base and adjust:

- Set `SOLACE_BROKER_URL`/VPN/user/pass to your production broker.
- Use strong `SESSION_SECRET_KEY`.
- Consider SQL-backed session services: set `WEB_UI_GATEWAY_DATABASE_URL` (gateway) and `ORCHESTRATOR_DATABASE_URL` (orchestrator) to production-grade databases.
- Set `WEBUI_STATUS_TOPIC` to a namespaced, non-dev value to keep orchestrator status logs clean.

## Agent Configuration Structure

Each agent YAML in `configs/agents/` includes:

```yaml
name: agent-name
agents:
  - name: AgentName
    broker: *default_broker          # Connection settings
    model: *general_model            # LLM model
    instruction: |                   # System prompt
      You are a specialized agent...
    tools:                           # Available tools
      - name: builtin-group:data_analysis
    agent_card:                      # Discovery metadata
      description: "What this agent does"
      skills:
        - name: skill-name
          description: "Skill description"
    inter_agent_communication:       # Peer access control
      allow_list: ["*"]
```

## Solace Cloud Setup

### 1. Create Account

1. Go to [solace.com](https://solace.com) → "Start Free"
2. Create account and verify email
3. Log in to [Solace Cloud Console](https://console.solace.cloud)

### 2. Create Messaging Service

1. Click **"Cluster Manager"** → **"Create Service"**
2. Select **"Developer"** tier (free)
3. Choose cloud provider and region
4. Name it (e.g., "health-counselor-demo")
5. Wait ~2 minutes for provisioning

### 3. Get Credentials

1. Click your service → **"Connect"** tab
2. Expand **"Solace Messaging"**
3. Copy: Host, Message VPN, Username, Password

### 4. Local Docker Alternative

For local development without Solace Cloud:

```bash
docker run -d -p 8008:8008 -p 8080:8080 \
  --name solace \
  solace/solace-pubsub-standard:latest
```

Then use:
```env
SOLACE_BROKER_URL=ws://localhost:8008
SOLACE_BROKER_VPN=default
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default
```
