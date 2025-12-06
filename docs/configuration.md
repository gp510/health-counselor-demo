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

# Data Path (absolute path to project)
DATA_PATH=/path/to/health-counselor-demo
```

## Shared Configuration

The `configs/shared_config.yaml` file uses YAML anchors to define reusable settings across all agents.

### Broker Connection

```yaml
broker: &default_broker
  type: solace
  url: ${SOLACE_BROKER_URL}
  vpn: ${SOLACE_BROKER_VPN}
  username: ${SOLACE_BROKER_USERNAME}
  password: ${SOLACE_BROKER_PASSWORD}
```

### LLM Models

```yaml
models:
  planning_model: &planning_model
    type: openai
    name: ${LLM_SERVICE_PLANNING_MODEL_NAME}

  general_model: &general_model
    type: openai
    name: ${LLM_SERVICE_GENERAL_MODEL_NAME}
```

### Services

```yaml
services:
  session: &session_service
    type: builtin

  artifact: &artifact_service
    type: filesystem
    path: /tmp/samv2
    scope: namespace
```

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
