# Deployment Guide

This guide covers production deployment of the Health Counselor Assistant using Docker Compose, with security hardening, monitoring, and scaling considerations.

## Overview

### Architecture

```
                                    +------------------+
                                    |   Load Balancer  |
                                    |   (Optional)     |
                                    +--------+---------+
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
           +--------v--------+      +--------v--------+      +--------v--------+
           |  WebUI Gateway  |      | Dashboard API   |      | Dashboard UI    |
           |  (Port 8000)    |      | (Port 8082)     |      | (Port 3000)     |
           +--------+--------+      +--------+--------+      +-----------------+
                    |                        |
                    +------------------------+
                                |
                    +-----------v-----------+
                    |    Solace Broker      |
                    |  (Ports 8008, 8080)   |
                    +-----------+-----------+
                                |
        +-----------------------+-----------------------+
        |           |           |           |           |
   +----v----+ +----v----+ +----v----+ +----v----+ +----v----+
   | Health  | |Biomarker| | Fitness | |  Diet   | | Mental  |
   | Orch.   | | Agent   | | Agent   | | Agent   | |Wellness |
   +---------+ +---------+ +---------+ +---------+ +---------+
                                |
                    +-----------v-----------+
                    |  Wearable Listener    |
                    |   (Real-time Data)    |
                    +-----------------------+
```

### Component Summary

| Component | Role | Database | Port |
|-----------|------|----------|------|
| Health Orchestrator | Coordinates agent workflows | orchestrator.db | - |
| Biomarker Agent | Lab results, vital signs | biomarker.db | - |
| Fitness Agent | Activity, sleep, heart rate | fitness.db | - |
| Diet Agent | Nutrition, meals, hydration | diet.db | - |
| Mental Wellness Agent | Mood, stress, energy | mental_wellness.db | - |
| Wearable Listener | Real-time streaming data | - | - |
| WebUI Gateway | HTTP/SSE user interface | webui_gateway.db | 8000 |
| Dashboard API | REST API for analytics | - | 8082 |
| Dashboard UI | React frontend | - | 3000 |
| Solace Broker | Event mesh communication | - | 8008, 8080 |

### Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| Broker | Local Docker | Solace Cloud or HA cluster |
| Database | SQLite files | SQLite or PostgreSQL |
| Session Storage | In-memory | SQL-based |
| Artifact Storage | `/tmp/samv2` | S3 or persistent volume |
| TLS | Disabled | Required |
| Credentials | Environment variables | Secrets manager |
| Monitoring | Console logs | Centralized logging |

> **Security Notice**: This guide contains separate configurations for development and production environments. Pay close attention to the security warnings throughout this document. Never use `.env` files or plaintext environment variables for secrets in production deployments.

---

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **Docker**: 20.10+ with Docker Compose v2
- **Memory**: 4GB minimum (8GB recommended)
- **Disk**: 10GB for containers and data
- **Node.js**: 18+ (optional, for dashboard frontend)

### Solace Broker

**Recommended: Solace Cloud** (production)
1. Create free account at [solace.com](https://solace.com)
2. Create a Developer tier messaging service
3. Get connection credentials from Connect tab

**Alternative: Local Docker** (development only)
```bash
docker run -d --name solace \
  -p 8008:8008 -p 8080:8080 -p 55555:55555 \
  --shm-size=1g \
  solace/solace-pubsub-standard:latest
```

### LLM API Access

Supports OpenAI, Anthropic, or any OpenAI-compatible endpoint:
- OpenAI: `https://api.openai.com/v1`
- Anthropic: Via LiteLLM compatibility
- Azure OpenAI: Custom endpoint URL
- Local LLMs: Ollama, vLLM, etc.

### SAM Plugins

```bash
# Install required SQL database plugin
sam plugin install sam-sql-database
```

---

## Production Deployment with Docker Compose

### Directory Structure

```
health-counselor-demo/
├── docker-compose.yml          # Main compose file
├── docker-compose.override.yml # Local development overrides
├── .env                        # Environment configuration
├── configs/                    # Agent YAML configurations
├── CSV_Data/                   # Initial health data
├── data/                       # Persistent database storage
└── logs/                       # Log file output
```

### Docker Compose Configuration

> **Security Note**: The configuration below mounts the entire project directory (`.:/app`) for development convenience. For production, use more restrictive volume mounts to prevent exposing sensitive files. See [Secure Volume Mounts](#secure-volume-mounts) in the Security Hardening section.

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # =============================================================================
  # Solace Event Broker (Optional - use Solace Cloud for production)
  # =============================================================================
  solace:
    image: solace/solace-pubsub-standard:latest
    container_name: health-solace
    hostname: solace
    shm_size: 1g
    ulimits:
      core: -1
      nofile:
        soft: 2448
        hard: 38048
    ports:
      - "8008:8008"   # WebSocket
      - "8080:8080"   # SEMP Management
      - "55555:55555" # SMF
    environment:
      - username_admin_globalaccesslevel=admin
      - username_admin_password=${SOLACE_ADMIN_PASSWORD:-admin}
    volumes:
      - solace-data:/var/lib/solace
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health-check/guaranteed-active"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    profiles:
      - with-broker  # Only start with: docker compose --profile with-broker up

  # =============================================================================
  # Health Orchestrator - Central Coordinator
  # =============================================================================
  health-orchestrator:
    image: python:3.11-slim
    container_name: health-orchestrator
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_PLANNING_MODEL_NAME=${LLM_SERVICE_PLANNING_MODEL_NAME}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/health-orchestrator.yaml"
    depends_on:
      solace:
        condition: service_healthy
        required: false
    restart: unless-stopped

  # =============================================================================
  # Biomarker Agent - Lab Results & Vital Signs
  # =============================================================================
  biomarker-agent:
    image: python:3.11-slim
    container_name: biomarker-agent
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
      - BIOMARKER_AGENT_DB_NAME=/app/data/biomarker.db
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/biomarker-agent.yaml"
    depends_on:
      - health-orchestrator
    restart: unless-stopped

  # =============================================================================
  # Fitness Agent - Activity & Sleep Tracking
  # =============================================================================
  fitness-agent:
    image: python:3.11-slim
    container_name: fitness-agent
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
      - FITNESS_AGENT_DB_NAME=/app/data/fitness.db
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/fitness-agent.yaml"
    depends_on:
      - health-orchestrator
    restart: unless-stopped

  # =============================================================================
  # Diet Agent - Nutrition Tracking
  # =============================================================================
  diet-agent:
    image: python:3.11-slim
    container_name: diet-agent
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
      - DIET_AGENT_DB_NAME=/app/data/diet.db
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/diet-agent.yaml"
    depends_on:
      - health-orchestrator
    restart: unless-stopped

  # =============================================================================
  # Mental Wellness Agent - Mood & Stress Tracking
  # =============================================================================
  mental-wellness-agent:
    image: python:3.11-slim
    container_name: mental-wellness-agent
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
      - MENTAL_WELLNESS_AGENT_DB_NAME=/app/data/mental_wellness.db
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/mental-wellness-agent.yaml"
    depends_on:
      - health-orchestrator
    restart: unless-stopped

  # =============================================================================
  # Wearable Listener - Real-time Data Streaming
  # =============================================================================
  wearable-listener:
    image: python:3.11-slim
    container_name: wearable-listener
    working_dir: /app
    volumes:
      - .:/app
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - DATA_PATH=/app
      - EVENT_TOPIC_PREFIX=${EVENT_TOPIC_PREFIX:-health/events}
    command: >
      bash -c "pip install -r requirements.txt &&
               sam plugin install sam-sql-database &&
               sam run configs/agents/wearable-listener-agent.yaml"
    depends_on:
      - fitness-agent
    restart: unless-stopped

  # =============================================================================
  # WebUI Gateway - User Interface
  # =============================================================================
  webui-gateway:
    image: python:3.11-slim
    container_name: webui-gateway
    working_dir: /app
    ports:
      - "${FASTAPI_PORT:-8000}:8000"
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - SOLACE_BROKER_URL=${SOLACE_BROKER_URL}
      - SOLACE_BROKER_VPN=${SOLACE_BROKER_VPN}
      - SOLACE_BROKER_USERNAME=${SOLACE_BROKER_USERNAME}
      - SOLACE_BROKER_PASSWORD=${SOLACE_BROKER_PASSWORD}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_PLANNING_MODEL_NAME=${LLM_SERVICE_PLANNING_MODEL_NAME}
      - NAMESPACE=${NAMESPACE:-workshop/}
      - FASTAPI_HOST=0.0.0.0
      - FASTAPI_PORT=8000
      - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
    command: >
      bash -c "pip install -r requirements.txt &&
               sam run configs/gateways/webui.yaml"
    depends_on:
      - health-orchestrator
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # =============================================================================
  # Dashboard API - Analytics Backend
  # =============================================================================
  dashboard-api:
    image: python:3.11-slim
    container_name: dashboard-api
    working_dir: /app
    ports:
      - "8082:8082"
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - DATA_PATH=/app
    command: >
      bash -c "pip install -r requirements.txt &&
               uvicorn server.dashboard_api.main:app --host 0.0.0.0 --port 8082"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8082/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # =============================================================================
  # Dashboard UI - React Frontend (Optional)
  # =============================================================================
  dashboard-ui:
    image: node:18-alpine
    container_name: dashboard-ui
    working_dir: /app/client/dashboard
    ports:
      - "3000:3000"
    volumes:
      - ./client/dashboard:/app/client/dashboard
    command: sh -c "npm install && npm run dev -- --host 0.0.0.0"
    depends_on:
      - dashboard-api
      - webui-gateway
    restart: unless-stopped
    profiles:
      - with-ui  # Only start with: docker compose --profile with-ui up

volumes:
  solace-data:
    driver: local

networks:
  default:
    name: health-counselor-network
```

### Environment Configuration

#### Development Environment (.env file)

> **Warning**: `.env` files are for **LOCAL DEVELOPMENT ONLY**. They store secrets in plaintext, can be accidentally committed to version control, and are readable by any process with file access. For production, see [Production Secrets Management](#production-secrets-management) below.

Create `.env` for local development:

```env
# =============================================================================
# LOCAL DEVELOPMENT CONFIGURATION ONLY
# DO NOT USE IN PRODUCTION - See Production Secrets Management section
# =============================================================================

# LLM Configuration
LLM_SERVICE_ENDPOINT=https://api.openai.com/v1
LLM_SERVICE_API_KEY=sk-your-dev-key
LLM_SERVICE_PLANNING_MODEL_NAME=openai/gpt-4o
LLM_SERVICE_GENERAL_MODEL_NAME=openai/gpt-4o-mini

# Local Solace Broker (development)
SOLACE_BROKER_URL=ws://localhost:8008
SOLACE_BROKER_VPN=default
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default

# Agent Configuration
NAMESPACE=workshop/
EVENT_TOPIC_PREFIX=health/events

# Gateway Configuration
FASTAPI_PORT=8000
SESSION_SECRET_KEY=dev-only-not-for-production

# Data Paths (inside container)
DATA_PATH=/app
```

**Secure your development .env file**:
```bash
# Restrict file permissions (owner read/write only)
chmod 600 .env
chown $USER:$USER .env

# Ensure .env is in .gitignore
echo ".env" >> .gitignore
```

#### Production Secrets Management

For production deployments, use one of these secure alternatives:

**Option 1: Docker Compose with Secrets Files**

Create a `secrets/` directory with restricted permissions:
```bash
mkdir -p secrets
chmod 700 secrets

# Create secret files
echo "sk-your-production-api-key" > secrets/llm_api_key
echo "your-solace-password" > secrets/solace_password
echo "$(openssl rand -hex 32)" > secrets/session_secret

# Restrict permissions
chmod 600 secrets/*
```

Update `docker-compose.yml` to use secrets:
```yaml
secrets:
  llm_api_key:
    file: ./secrets/llm_api_key
  solace_password:
    file: ./secrets/solace_password
  session_secret:
    file: ./secrets/session_secret

services:
  health-orchestrator:
    secrets:
      - llm_api_key
      - solace_password
    environment:
      # Non-sensitive configuration only
      - SOLACE_BROKER_URL=wss://your-service.messaging.solace.cloud:443
      - SOLACE_BROKER_VPN=your-vpn-name
      - SOLACE_BROKER_USERNAME=solace-cloud-client
      - LLM_SERVICE_ENDPOINT=https://api.openai.com/v1
      - NAMESPACE=health-prod/
      # Reference secrets via files
      - LLM_SERVICE_API_KEY_FILE=/run/secrets/llm_api_key
      - SOLACE_BROKER_PASSWORD_FILE=/run/secrets/solace_password
```

> **Note**: This requires modifying the application to read secrets from files. A common pattern is to check for `*_FILE` environment variables and read the secret from that path.

**Option 2: Docker Swarm Secrets** (for Swarm deployments)

```bash
# Create secrets in Swarm
echo "sk-your-production-api-key" | docker secret create llm_api_key -
echo "your-solace-password" | docker secret create solace_password -
docker secret create session_secret <(openssl rand -hex 32)
```

```yaml
secrets:
  llm_api_key:
    external: true
  solace_password:
    external: true
  session_secret:
    external: true

services:
  health-orchestrator:
    secrets:
      - llm_api_key
      - solace_password
```

**Option 3: HashiCorp Vault**

For enterprise deployments, integrate with Vault using an agent sidecar:
```yaml
services:
  vault-agent:
    image: hashicorp/vault:latest
    command: agent -config=/vault/config/agent.hcl
    volumes:
      - ./vault-config:/vault/config:ro
      - vault-secrets:/vault/secrets

  health-orchestrator:
    depends_on:
      - vault-agent
    volumes:
      - vault-secrets:/secrets:ro
    environment:
      - LLM_SERVICE_API_KEY_FILE=/secrets/llm_api_key
      - SOLACE_BROKER_PASSWORD_FILE=/secrets/solace_password
```

**Option 4: Cloud-Native Secrets Managers**

- **AWS**: Use AWS Secrets Manager with IAM roles
- **Azure**: Use Azure Key Vault with managed identities
- **GCP**: Use Secret Manager with workload identity

Example with AWS ECS:
```yaml
services:
  health-orchestrator:
    environment:
      - LLM_SERVICE_API_KEY=arn:aws:secretsmanager:us-east-1:123456789:secret:llm-api-key
    # ECS will inject the secret value at runtime
```

### Deployment Commands

```bash
# Create data directories
mkdir -p data logs

# Start all services (with Solace Cloud)
docker compose up -d

# Start with local broker (development)
docker compose --profile with-broker up -d

# Start with dashboard UI
docker compose --profile with-ui up -d

# Start everything
docker compose --profile with-broker --profile with-ui up -d

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f health-orchestrator

# Stop all services
docker compose down

# Stop and remove volumes (clean start)
docker compose down -v
```

### Verify Deployment

```bash
# Check service health
docker compose ps

# Test WebUI Gateway
curl http://localhost:8000/health

# Test Dashboard API
curl http://localhost:8082/health

# Check broker connection (if using local)
curl http://localhost:8080/health-check/guaranteed-active
```

---

## Security Hardening

### TLS/HTTPS Configuration

For production, enable HTTPS on the WebUI Gateway:

1. Generate or obtain SSL certificates:
```bash
# Self-signed (testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem

# Production: Use Let's Encrypt or your CA
```

2. Update environment:
```env
FASTAPI_HTTPS_PORT=8443
SSL_KEYFILE=/app/certs/key.pem
SSL_CERTFILE=/app/certs/cert.pem
```

3. Update docker-compose.yml:
```yaml
webui-gateway:
  ports:
    - "8443:8443"
  volumes:
    - ./certs:/app/certs:ro
```

### Credential Management

> **Critical**: Never store secrets in `.env` files, environment variables, or docker-compose.yml for production deployments. See [Production Secrets Management](#production-secrets-management) for detailed implementation options including Docker Secrets, HashiCorp Vault, and cloud-native solutions.

**Quick Reference - Secrets Management Options**:

| Option | Best For | Complexity |
|--------|----------|------------|
| Docker Compose Secrets Files | Single-host Docker Compose | Low |
| Docker Swarm Secrets | Swarm clusters | Medium |
| HashiCorp Vault | Enterprise, multi-environment | High |
| AWS Secrets Manager | AWS deployments | Medium |
| Azure Key Vault | Azure deployments | Medium |
| GCP Secret Manager | GCP deployments | Medium |

### Secure Volume Mounts

The development docker-compose.yml mounts the entire project directory (`.:/app`) which can expose:
- `.env` files with secrets
- `.git` directory with repository history
- Other sensitive configuration files

**For production, use explicit, read-only mounts**:

```yaml
services:
  health-orchestrator:
    volumes:
      # Mount only required directories, read-only where possible
      - ./configs:/app/configs:ro
      - ./CSV_Data:/app/CSV_Data:ro
      - ./src:/app/src:ro
      - ./requirements.txt:/app/requirements.txt:ro
      # Writable volumes for data persistence
      - ./data:/app/data
      - ./logs:/app/logs
      # Never mount: .env, .git, secrets/, or project root

  webui-gateway:
    volumes:
      - ./configs:/app/configs:ro
      - ./data:/app/data
      # Mount only static assets needed for serving
      - ./client/dashboard/dist:/app/static:ro
```

**Additional volume security measures**:
```bash
# Set restrictive permissions on data directories
chmod 750 data logs
chown -R 1000:1000 data logs  # Match container user

# Ensure sensitive files are not in mounted directories
ls -la configs/  # Verify no secrets in config files
```

### Network Isolation

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  webui-gateway:
    networks:
      - frontend
      - backend

  health-orchestrator:
    networks:
      - backend  # Not exposed externally
```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 8000/tcp   # WebUI Gateway
ufw allow 8443/tcp   # WebUI Gateway (HTTPS)
ufw allow 3000/tcp   # Dashboard UI (if needed)
ufw deny 8008/tcp    # Block direct broker access
ufw deny 8080/tcp    # Block broker management
```

### Health Data Compliance (HIPAA/GDPR)

For handling protected health information (PHI):

1. **Encryption at Rest**: Enable database encryption
2. **Encryption in Transit**: Enforce TLS for all connections
3. **Access Logging**: Enable audit logs for all data access
4. **Data Retention**: Implement automated data purging policies
5. **Access Control**: Implement role-based access (not included in demo)
6. **BAA**: Ensure Solace Cloud BAA if using cloud broker

```yaml
# Example: Add audit logging volume
volumes:
  - ./audit-logs:/app/audit-logs

environment:
  - ENABLE_AUDIT_LOGGING=true
```

---

## Infrastructure Considerations

### Solace Broker Options

| Option | Use Case | Cost | HA |
|--------|----------|------|-----|
| Solace Cloud (Developer) | Development, small demos | Free | No |
| Solace Cloud (Enterprise) | Production | Paid | Yes |
| Self-hosted (Standard) | On-premise, testing | Free | No |
| Self-hosted (Enterprise) | On-premise production | License | Yes |

**Solace Cloud Setup** (recommended):
1. Create account at [console.solace.cloud](https://console.solace.cloud)
2. Create new service (Developer tier is free)
3. Go to Connect tab > Solace Messaging
4. Copy WebSocket Secured URL, Message VPN, Username, Password

### Database Migration Path

**SQLite (Default)** → **PostgreSQL (Production)**

For high-volume production, migrate to PostgreSQL:

1. Update shared_config.yaml:
```yaml
session_service: &default_session_service
  type: "sql"
  connection_string: "postgresql://user:pass@postgres:5432/health_counselor"
```

2. Add PostgreSQL to docker-compose.yml:
```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: health_counselor
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

### Artifact Storage

**Filesystem (Default)** → **S3 (Production)**

For distributed deployments, use S3:

```yaml
artifact_service: &default_artifact_service
  type: "s3"
  bucket_name: "${S3_BUCKET_NAME}"
  endpoint_url: "${S3_ENDPOINT_URL}"
  region: "${S3_REGION:-us-east-1}"
```

### High Availability

For HA deployments:
1. Use Solace Cloud Enterprise with built-in HA
2. Run multiple gateway instances behind a load balancer
3. Use PostgreSQL with replication for session storage
4. Use S3 or distributed filesystem for artifacts

---

## Startup and Shutdown

### Startup Sequence

Services should start in this order:

1. **Solace Broker** (if self-hosted)
2. **Health Orchestrator** (central coordinator)
3. **Specialized Agents** (Biomarker, Fitness, Diet, Mental Wellness)
4. **Wearable Listener** (depends on Fitness Agent)
5. **WebUI Gateway** (user-facing)
6. **Dashboard API/UI** (optional analytics)

Docker Compose handles dependencies automatically via `depends_on`.

### Health Checks

All services should implement health endpoints:

| Service | Health Endpoint | Expected Response |
|---------|-----------------|-------------------|
| WebUI Gateway | `GET /health` | `{"status": "healthy"}` |
| Dashboard API | `GET /health` | `{"status": "ok"}` |
| Solace Broker | `GET :8080/health-check/guaranteed-active` | HTTP 200 |

### Graceful Shutdown

Solace broker requires up to 20 minutes for graceful shutdown:

```yaml
solace:
  stop_grace_period: 1200s  # 20 minutes
```

For agents:
```bash
# Graceful shutdown (SIGTERM)
docker compose stop

# Force shutdown (SIGKILL) - use only if stuck
docker compose kill
```

### Recovery Procedures

**Agent Crash Recovery**:
```bash
# Restart single agent
docker compose restart biomarker-agent

# View crash logs
docker compose logs biomarker-agent --tail=100
```

**Broker Connection Loss**:
Agents will automatically reconnect when broker becomes available.

**Database Corruption**:
```bash
# Re-initialize from CSV data
docker compose exec health-orchestrator python scripts/populate_databases.py
```

---

## Monitoring and Observability

### Logging Configuration

Configure via `configs/logging_config.yaml`:

```yaml
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
loggers:
  solace_ai_connector:
    level: ${LOGGING_SAC_LEVEL:-INFO}
  solace_agent_mesh:
    level: ${LOGGING_SAM_LEVEL:-INFO}
  sam_trace:
    level: ${LOGGING_SAM_TRACE_LEVEL:-INFO}
```

Environment variables:
```env
LOGGING_SAC_LEVEL=INFO
LOGGING_SAM_LEVEL=INFO
LOGGING_SAM_TRACE_LEVEL=DEBUG  # Detailed request tracing
LOGGING_ROOT_LEVEL=WARNING
```

### Log Aggregation

For production, forward logs to a centralized system:

```yaml
# Docker logging driver
services:
  health-orchestrator:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

# Or use fluentd/logstash
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "localhost:24224"
        tag: "health-counselor.{{.Name}}"
```

### Key Metrics

Monitor these metrics:

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| Agent response time | >5s | >30s |
| Broker queue depth | >1000 | >10000 |
| Memory usage | >80% | >95% |
| Error rate | >1% | >5% |
| LLM API latency | >3s | >10s |

### Health Check Endpoints

```bash
# Create monitoring script
#!/bin/bash
curl -sf http://localhost:8000/health || echo "WebUI Gateway DOWN"
curl -sf http://localhost:8082/health || echo "Dashboard API DOWN"
curl -sf http://localhost:8080/health-check/guaranteed-active || echo "Broker DOWN"
```

### Alerting

Integrate with monitoring systems:
- **Prometheus**: Expose `/metrics` endpoint (requires custom implementation)
- **DataDog**: Use Docker integration
- **CloudWatch**: Use AWS logging driver
- **PagerDuty**: Configure webhook alerts

---

## Scaling and Performance

### Horizontal Scaling

**Gateway Scaling**:
```yaml
webui-gateway:
  deploy:
    replicas: 3
```

Use a load balancer (nginx, HAProxy, or cloud LB) in front of gateways.

**Agent Replication**:
Agents are stateless and can be replicated for throughput:
```yaml
biomarker-agent:
  deploy:
    replicas: 2
```

### Broker Capacity Planning

| Connections | Required IOPS | Memory |
|-------------|---------------|--------|
| 100 | 300 | 2GB |
| 1,000 | 3,000 | 4GB |
| 10,000 | 30,000 | 8GB |

For high-volume deployments, use Solace Cloud Enterprise.

### Performance Tuning

**LLM Caching**:
```yaml
# In shared_config.yaml
planning: &planning_model
  cache_strategy: "5m"  # Cache responses for 5 minutes
```

**Database Optimization**:
```yaml
data_tools_config: &default_data_tools_config
  sqlite_memory_threshold_mb: 100
  max_result_preview_rows: 50
  max_result_preview_bytes: 4096
```

---

## Local Development (Quick Reference)

For development without Docker:

```bash
# 1. Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sam plugin install sam-sql-database

# 2. Start local broker
docker run -d --name solace -p 8008:8008 -p 8080:8080 \
  --shm-size=1g solace/solace-pubsub-standard:latest

# 3. Configure .env with local broker settings
# SOLACE_BROKER_URL=ws://localhost:8008

# 4. Start agents (each in separate terminal)
sam run configs/agents/health-orchestrator.yaml
sam run configs/agents/biomarker-agent.yaml
sam run configs/agents/fitness-agent.yaml
sam run configs/agents/diet-agent.yaml
sam run configs/agents/mental-wellness-agent.yaml
sam run configs/agents/wearable-listener-agent.yaml

# 5. Start gateway
sam run configs/gateways/webui.yaml

# 6. Access UI
open http://localhost:8000
```

See [configuration.md](./configuration.md) for detailed environment setup.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Agents not discovering each other | Wrong namespace | Verify `NAMESPACE` matches across all configs |
| Broker connection refused | Broker not running | Check `docker compose ps solace` |
| LLM timeout | API rate limiting | Implement retry logic or upgrade API tier |
| Database locked | Concurrent writes | Use PostgreSQL for production |
| Memory exhaustion | Too many agents | Increase container memory limits |

### Connection Failures

```bash
# Test broker connectivity
docker compose exec health-orchestrator python -c "
from solace.messaging.messaging_service import MessagingService
# Test connection code here
"

# Check broker logs
docker compose logs solace --tail=50
```

### Agent Discovery Problems

```bash
# Verify agent registration
# Check broker queue subscriptions via SEMP API
curl -u admin:admin http://localhost:8080/SEMP/v2/config/msgVpns/default/queues
```

### Database Initialization Errors

```bash
# Re-run database population
docker compose exec health-orchestrator python scripts/populate_databases.py

# Check CSV data files exist
ls -la CSV_Data/
```

### Debug Commands

```bash
# Interactive shell in container
docker compose exec health-orchestrator bash

# Python debug
docker compose exec health-orchestrator python -c "
import os
print('DATA_PATH:', os.getenv('DATA_PATH'))
print('NAMESPACE:', os.getenv('NAMESPACE'))
"

# Tail all logs
docker compose logs -f --tail=100

# Resource usage
docker stats
```

---

## Reference

### Complete Startup Command Reference

| Command | Purpose |
|---------|---------|
| `docker compose up -d` | Start all services (background) |
| `docker compose --profile with-broker up -d` | Include local Solace broker |
| `docker compose --profile with-ui up -d` | Include dashboard UI |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop and remove volumes |
| `docker compose restart <service>` | Restart specific service |
| `docker compose logs -f <service>` | Follow service logs |
| `docker compose exec <service> bash` | Shell into container |

### Environment Variables Reference

> **Security Note**: Variables marked with indicate sensitive data that should be managed via secrets management in production (see [Production Secrets Management](#production-secrets-management)).

| Variable | Required | Sensitive | Default | Description |
|----------|----------|-----------|---------|-------------|
| `LLM_SERVICE_ENDPOINT` | Yes | No | - | LLM API base URL |
| `LLM_SERVICE_API_KEY` | Yes | **Yes** | - | LLM API authentication key |
| `LLM_SERVICE_PLANNING_MODEL_NAME` | Yes | No | - | Model for orchestrator |
| `LLM_SERVICE_GENERAL_MODEL_NAME` | Yes | No | - | Model for agents |
| `SOLACE_BROKER_URL` | Yes | No | `ws://localhost:8008` | Broker WebSocket URL |
| `SOLACE_BROKER_VPN` | Yes | No | `default` | Message VPN name |
| `SOLACE_BROKER_USERNAME` | Yes | No | `default` | Broker username |
| `SOLACE_BROKER_PASSWORD` | Yes | **Yes** | `default` | Broker password |
| `NAMESPACE` | No | No | `workshop/` | Agent discovery namespace |
| `EVENT_TOPIC_PREFIX` | No | No | `health/events` | Wearable event topic prefix |
| `FASTAPI_HOST` | No | No | `127.0.0.1` | Gateway bind host |
| `FASTAPI_PORT` | No | No | `8000` | Gateway port |
| `SESSION_SECRET_KEY` | Yes | **Yes** | - | Session encryption key |
| `DATA_PATH` | No | No | `.` | Path to data directory |

**Handling Sensitive Variables in Production**:
```bash
# Instead of: LLM_SERVICE_API_KEY=sk-xxx
# Use: LLM_SERVICE_API_KEY_FILE=/run/secrets/llm_api_key

# The application should check for *_FILE variants and read from that path
```

### Port Mappings

| Port | Service | Protocol |
|------|---------|----------|
| 8000 | WebUI Gateway | HTTP/SSE |
| 8443 | WebUI Gateway | HTTPS (optional) |
| 8082 | Dashboard API | HTTP |
| 3000 | Dashboard UI | HTTP |
| 8008 | Solace Broker | WebSocket |
| 8080 | Solace SEMP | HTTP |
| 55555 | Solace SMF | TCP |

### Related Documentation

- [Configuration Reference](./configuration.md) - Environment variables and shared config
- [Data Model](./data-model.md) - Database schemas and CSV formats
- [Dashboard Guide](./DASHBOARD.md) - Analytics dashboard setup
- [Development Guide](./development.md) - Extending the system
- [Simulation Demo](./simulation-demo.md) - Wearable data streaming
