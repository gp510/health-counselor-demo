# Wearable Simulation Demo

This guide walks through simulating wearable fitness data and observing how agents react in real-time.

## Prerequisites

1. **Solace Cloud credentials** configured in `.env`:
   ```env
   SOLACE_BROKER_URL="wss://your-service.messaging.solace.cloud:443"
   SOLACE_BROKER_VPN="your-vpn"
   SOLACE_BROKER_USERNAME="solace-cloud-client"
   SOLACE_BROKER_PASSWORD="your-password"
   ```

2. **Virtual environment activated**:
   ```bash
   source venv/bin/activate
   ```

3. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Option 1: Run Everything Together (Recommended)

Start all agents and the web UI:

```bash
# Terminal 1: Start the health orchestrator
sam run configs/agents/health-orchestrator.yaml

# Terminal 2: Start the health agents
sam run configs/agents/biomarker-agent.yaml \
        configs/agents/fitness-agent.yaml \
        configs/agents/diet-agent.yaml \
        configs/agents/mental-wellness-agent.yaml

# Terminal 3: Start the wearable listener
sam run configs/agents/wearable-listener-agent.yaml

# Terminal 4: Start the Web UI
sam run configs/gateways/webui.yaml

# Terminal 5: Run the simulator
python scripts/wearable_simulator.py --scenario random --interval 10
```

### Option 2: Run Agents Separately (For Debugging)

Running agents in separate terminals provides isolated logs for each component:

```bash
# Terminal 1: Orchestrator
sam run configs/agents/health-orchestrator.yaml

# Terminal 2: Fitness Agent
sam run configs/agents/fitness-agent.yaml

# Terminal 3: Wearable Listener Agent
sam run configs/agents/wearable-listener-agent.yaml

# Terminal 4: Web UI
sam run configs/gateways/webui.yaml

# Terminal 5: Simulator
python scripts/wearable_simulator.py --scenario workout --workout-type running
```

## Wearable Simulator Usage

The wearable simulator (`scripts/wearable_simulator.py`) publishes fitness data events to Solace Cloud.

### Basic Commands

```bash
# Send a single heart rate reading
python scripts/wearable_simulator.py --once --type heart_rate --value 72

# Random fitness data every 10 seconds (runs until Ctrl+C)
python scripts/wearable_simulator.py --scenario random --interval 10

# Random data with a limit
python scripts/wearable_simulator.py --scenario random --count 5 --interval 3
```

### Scenario Types

#### 1. Random Data
Generates random wearable data at the specified interval:
```bash
python scripts/wearable_simulator.py --scenario random --interval 10
```

Data types include: heart_rate, steps, sleep, workout, stress

#### 2. Workout Scenario
Simulates a workout session with elevated heart rate and calorie burn:
```bash
python scripts/wearable_simulator.py --scenario workout --workout-type running --duration 30
```

Output sequence:
1. Workout started: Heart rate rising
2. Active zone: Sustained elevated heart rate (120-160 bpm)
3. Peak effort: Maximum heart rate reached
4. Cool down: Heart rate returning to normal
5. Workout complete: Summary with calories burned

#### 3. Elevated Heart Rate Scenario
Simulates concerning heart rate readings that trigger alerts:
```bash
python scripts/wearable_simulator.py --scenario elevated-hr --interval 5
```

Output sequence:
1. Normal: Resting heart rate (60-75 bpm)
2. Elevated: Heart rate increasing (90-100 bpm)
3. High: Concerning heart rate (110-130 bpm)
4. Alert: Abnormal resting heart rate notification

#### 4. Sleep Tracking Scenario
Simulates a full night of sleep data:
```bash
python scripts/wearable_simulator.py --scenario sleep --duration 480
```

Tracks sleep stages: light, deep, REM, and awake periods.

#### 5. Stress Monitoring Scenario
Simulates stress level readings based on HRV (Heart Rate Variability):
```bash
python scripts/wearable_simulator.py --scenario stress --interval 5
```

### Data Types

| Type | Description | Unit | Normal Range |
|------|-------------|------|--------------|
| heart_rate | Current heart rate | bpm | 60-100 (resting) |
| steps | Step count | steps | 0-30000/day |
| sleep | Sleep duration/quality | hours | 7-9 |
| workout | Exercise session data | minutes | varies |
| stress | Stress level from HRV | 1-100 | 20-50 |

### Alert Levels

- `normal` - Data within expected ranges
- `elevated` - Slightly outside normal, monitoring
- `high` - Concerning levels, attention recommended
- `critical` - Immediate attention needed

## Event Message Format

Events are published to topics: `health/events/wearable/{data_type}/update`

Example payload:
```json
{
  "event_id": "WRB-A1B2C3D4",
  "event_type": "wearable_data",
  "data_type": "heart_rate",
  "timestamp": "2024-12-03T15:30:00Z",
  "value": 72,
  "unit": "bpm",
  "source_device": "smartwatch",
  "alert_level": "normal",
  "message": "Heart rate reading: 72 bpm"
}
```

## Observing the Demo

### 1. Watch the Wearable Listener Agent
When running agents separately, watch the Wearable Listener Agent terminal for incoming events:
```
[EVENT RECEIVED] Topic: health/events/wearable/heart_rate/update
[PROCESSING] heart_rate -> 72 bpm (normal)
[DB UPDATE] Fitness database updated with new reading
```

### 2. Query Health Status via Web UI
Open http://localhost:8000 and ask:
- "What is my current heart rate?"
- "Show my recent fitness data"
- "Any health alerts I should know about?"
- "How many steps have I taken today?"

### 3. Verify Database Updates
Check that fitness data was updated:
```bash
sqlite3 fitness.db "SELECT date, steps, resting_heart_rate, sleep_hours FROM fitness_data ORDER BY date DESC LIMIT 5;"
```

## Troubleshooting

### TLS Connection Errors
If you see certificate errors, verify your Solace Cloud URL uses `wss://` and port `443`:
```env
SOLACE_BROKER_URL="wss://mr-connection-xxxxx.messaging.solace.cloud:443"
```

### Events Not Being Received
1. Verify the Wearable Listener Agent is running and connected
2. Check the topic subscription matches: `health/events/wearable/>/update`
3. Ensure all agents use the same Solace Cloud credentials

### Agent Discovery Issues
Ensure all agents use the same `NAMESPACE` value in `.env`:
```env
NAMESPACE="health/"
```

### Database Not Updating
1. Check that `FITNESS_AGENT_DB_NAME` is set correctly in `.env`
2. Verify the Fitness Agent has write permissions to the database path
3. Check agent logs for any SQL errors
