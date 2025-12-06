# Health Counselor Dashboard

A web-based health monitoring interface for the Solace Agent Mesh health counselor system.

## Overview

The Health Counselor Dashboard provides real-time visualization and tracking of health metrics across five domains:

| Domain | Description |
|--------|-------------|
| **Biomarkers** | Lab test results, blood tests, vital signs with reference ranges |
| **Fitness** | Activity tracking, sleep patterns, heart rate monitoring from wearables |
| **Diet** | Nutrition tracking, meal logs, macronutrient analysis |
| **Mental Wellness** | Mood, stress, energy, anxiety tracking with journaling |
| **System Status** | Broker connectivity, agent status, last sync time |

## Features

- **Real-time health alerts** - Dismissable banner showing critical health issues
- **Multi-domain summary cards** - Current metrics with weekly trends
- **Interactive trend charts** - Historical data visualization (fitness, diet, wellness)
- **Health Assistant chat panel** - Query health data conversationally via the orchestrator
- **Auto-refresh** - Data updates every 30 seconds
- **Status footer** - Broker and agent connectivity indicators

## Chat Assistant Prerequisites

The Health Assistant chat panel connects to the Solace Agent Mesh via the WebUI Gateway. To use the chat functionality, you need:

**Required Services:**
```bash
# Terminal 1: WebUI Gateway (port 8000)
sam run configs/gateways/webui.yaml

# Terminal 2: Health Orchestrator
sam run configs/agents/health-orchestrator.yaml
```

**Optional (for full functionality):**
```bash
# Terminal 3-6: Health Agents
sam run configs/agents/biomarker-agent.yaml
sam run configs/agents/fitness-agent.yaml
sam run configs/agents/diet-agent.yaml
sam run configs/agents/mental-wellness-agent.yaml
```

The chat uses JSON-RPC 2.0 over HTTP with SSE for streaming responses. Messages are routed to the `HealthCounselorOrchestrator` agent.

## Quick Start

### Prerequisites

- Python 3.10+ with virtual environment
- Node.js 18+
- Health agent databases populated (run health agents first)

### Running the Dashboard

**Terminal 1 - Backend API:**
```bash
# From project root
source venv/bin/activate
DATA_PATH="$(pwd)" uvicorn server.dashboard_api.main:app --port 8082
```

**Terminal 2 - Frontend:**
```bash
cd client/dashboard
npm install  # first time only
npm run dev
```

### Access Points

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8082 |
| API Documentation (Swagger) | http://localhost:8082/docs |

## API Reference

Base URL: `http://localhost:8082/api/health`

### Endpoints

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/summary` | GET | Aggregated health summary across all domains | - |
| `/biomarkers` | GET | Lab test results | `days` (default: 30) |
| `/fitness` | GET | Fitness/activity records | `days` (default: 7) |
| `/diet` | GET | Meal log entries | `days` (default: 7) |
| `/wellness` | GET | Mental wellness entries | `days` (default: 7) |
| `/alerts` | GET | Active health alerts | - |
| `/health` | GET | API health check | - |

### Example Requests

```bash
# Get health summary
curl http://localhost:8082/api/health/summary

# Get last 14 days of fitness data
curl "http://localhost:8082/api/health/fitness?days=14"

# Get active alerts
curl http://localhost:8082/api/health/alerts
```

### Response Models

**HealthSummary** - Aggregated view returned by `/summary`:
```json
{
  "biomarkers": {
    "latest": [...],
    "abnormalCount": 2,
    "lastTestDate": "2024-11-15"
  },
  "fitness": {
    "today": { "steps": 8234, "sleepHours": 7.4, ... },
    "weekAvgSteps": 7488,
    "weekAvgSleep": 7.2,
    "weekAvgHR": 62
  },
  "diet": {
    "todayCalories": 1680,
    "todayProtein": 94,
    "weekAvgCalories": 1767
  },
  "mentalWellness": {
    "latest": { "moodScore": 7, "stressLevel": 4, ... },
    "weekAvgMood": 6.8,
    "weekAvgStress": 4.2
  }
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_PATH` | Path to SQLite database files | Project root |

### Database Files

The API reads from SQLite databases created by health agents:

| Database | Table | Source Agent |
|----------|-------|--------------|
| `biomarker.db` | `biomarker_data` | BiomarkerAgent |
| `fitness.db` | `fitness_data` | FitnessAgent |
| `diet.db` | `diet_logs` | DietAgent |
| `mental_wellness.db` | `mental_wellness` | MentalWellnessAgent |

**Note:** The API uses read-only database connections (`mode=ro`) to avoid conflicts with running agents.

### Vite Proxy Configuration

The frontend dev server proxies API requests:

| Path | Target |
|------|--------|
| `/api/health/*` | `http://localhost:8082` (Dashboard API) |
| `/api/*` | `http://localhost:8081` (WebUI Gateway) |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Browser       │────▶│   Vite Dev      │────▶│   FastAPI       │
│   (React App)   │     │   Server :3000  │     │   API :8082     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        │                                │                                │
                        ▼                                ▼                                ▼
                ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
                │ biomarker.db  │              │  fitness.db   │              │   diet.db     │
                └───────────────┘              └───────────────┘              └───────────────┘
```

## Technology Stack

### Frontend
- React 19
- TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Recharts (charting)

### Backend
- FastAPI (Python web framework)
- SQLite3 (read-only database access)
- Uvicorn (ASGI server)
- Pydantic (data validation)

## Development

### Frontend Development

```bash
cd client/dashboard

# Install dependencies
npm install

# Start dev server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Backend Development

```bash
# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
DATA_PATH="$(pwd)" uvicorn server.dashboard_api.main:app --port 8082 --reload
```

## Troubleshooting

### No data displayed

1. Ensure health agents have run and created database files
2. Check `DATA_PATH` environment variable points to correct directory
3. Verify databases exist: `ls *.db` in project root

### API connection errors

1. Confirm API server is running on port 8082
2. Check browser console for CORS errors
3. Verify Vite proxy configuration in `vite.config.ts`

### Stale data

- Dashboard auto-refreshes every 30 seconds
- Click refresh button in header for immediate update
- Data is relative to latest dates in database (for demo data)
