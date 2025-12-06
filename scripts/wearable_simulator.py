#!/usr/bin/env python3
"""
Wearable Health Data Simulator for Health Counselor Demo.

Publishes simulated fitness and health data to Solace broker for agents to react to.
Uses the Solace PubSub+ Python SDK for direct messaging.

Usage:
    python scripts/wearable_simulator.py --scenario random --interval 10
    python scripts/wearable_simulator.py --scenario workout --duration 30
    python scripts/wearable_simulator.py --scenario sleep
    python scripts/wearable_simulator.py --once --type heart_rate --value 75
"""

import os
import sys
import json
import time
import uuid
import random
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.topic import Topic
from solace.messaging.publisher.direct_message_publisher import PublishFailureListener
from solace.messaging.config.transport_security_strategy import TLS


# Load environment variables
load_dotenv()

# Wearable device sources
WEARABLE_DEVICES = ["Apple Watch", "Fitbit Charge 5", "Garmin Venu", "Samsung Galaxy Watch"]

# Health data specifications
HEALTH_DATA_SPECS = {
    "heart_rate": {
        "unit": "bpm",
        "normal_range": (60, 100),
        "elevated_range": (100, 120),
        "critical_low": 50,
        "critical_high": 150,
        "resting_range": (55, 75),
        "exercise_range": (100, 160),
    },
    "steps": {
        "unit": "steps",
        "increment_range": (50, 500),  # Steps added per update
        "daily_goal": 10000,
    },
    "sleep": {
        "unit": "hours",
        "quality_range": (1, 100),  # Sleep quality score
        "normal_duration": (6, 9),
        "poor_duration": (3, 5),
    },
    "workout": {
        "types": ["running", "cycling", "strength", "yoga", "swimming", "hiking", "walking"],
        "duration_range": (15, 90),  # minutes
        "calories_per_minute": (5, 15),
    },
    "stress": {
        "unit": "level",
        "scale": (1, 100),  # 1 = relaxed, 100 = highly stressed
        "normal_range": (20, 50),
        "elevated_range": (50, 70),
        "critical_range": (70, 100),
    },
}

# Alert messages by data type and level
ALERT_MESSAGES = {
    "heart_rate": {
        "critical": [
            "Heart rate dangerously high - consider rest",
            "Abnormally low heart rate detected",
            "Irregular heart rhythm pattern detected",
        ],
        "elevated": [
            "Heart rate elevated during rest period",
            "Higher than usual resting heart rate",
            "Heart rate trending above normal",
        ],
        "normal": [
            "Heart rate within normal range",
            "Healthy resting heart rate recorded",
        ],
    },
    "steps": {
        "milestone": [
            "Great progress on your daily step goal!",
            "You're staying active today!",
            "Keep up the movement!",
        ],
        "goal_reached": [
            "Congratulations! Daily step goal achieved!",
            "10,000 steps reached - excellent work!",
        ],
    },
    "sleep": {
        "poor": [
            "Sleep duration below recommended - consider earlier bedtime",
            "Short sleep session detected",
        ],
        "good": [
            "Quality sleep session recorded",
            "Healthy sleep duration achieved",
        ],
    },
    "workout": {
        "started": [
            "Workout session started - stay hydrated!",
            "Activity detected - tracking your workout",
        ],
        "completed": [
            "Great workout! Recovery time recommended",
            "Workout complete - well done!",
        ],
    },
    "stress": {
        "critical": [
            "High stress levels detected - consider relaxation",
            "Stress indicators elevated - take a break",
        ],
        "elevated": [
            "Moderate stress detected - breathing exercise suggested",
            "Stress levels rising - mindfulness recommended",
        ],
        "normal": [
            "Stress levels normal - keep it up!",
            "Relaxed state detected",
        ],
    },
}


class EventPublishFailureListener(PublishFailureListener):
    """Handler for publish failures."""

    def on_failed_publish(self, failed_publish_event):
        print(f"[ERROR] Failed to publish: {failed_publish_event}")


def create_messaging_service():
    """Create and connect to Solace broker messaging service."""
    broker_url = os.getenv("SOLACE_BROKER_URL", "ws://localhost:8008")
    vpn_name = os.getenv("SOLACE_BROKER_VPN", "default")
    username = os.getenv("SOLACE_BROKER_USERNAME", "default")
    password = os.getenv("SOLACE_BROKER_PASSWORD", "default")

    print(f"[INFO] Connecting to Solace broker: {broker_url}")
    print(f"[INFO] VPN: {vpn_name}, Username: {username}")

    # Build broker properties
    broker_props = {
        "solace.messaging.transport.host": broker_url,
        "solace.messaging.service.vpn-name": vpn_name,
        "solace.messaging.authentication.scheme.basic.username": username,
        "solace.messaging.authentication.scheme.basic.password": password,
    }

    # Create messaging service builder
    builder = MessagingService.builder().from_properties(broker_props)

    # For Solace Cloud (wss://), configure TLS
    if broker_url.startswith("wss://"):
        tls_strategy = TLS.create().without_certificate_validation()
        builder = builder.with_transport_security_strategy(tls_strategy)
        print("[INFO] TLS enabled (development mode)")

    # Create messaging service
    messaging_service = builder.build()

    # Connect
    messaging_service.connect()
    print("[INFO] Connected to Solace broker successfully!")

    return messaging_service


def determine_alert_level(data_type: str, value: float) -> str:
    """Determine alert level based on data type and value."""
    specs = HEALTH_DATA_SPECS.get(data_type, {})

    if data_type == "heart_rate":
        if value < specs.get("critical_low", 50) or value > specs.get("critical_high", 150):
            return "critical"
        elif value > specs.get("elevated_range", (100, 120))[0]:
            return "elevated"
        return "normal"

    elif data_type == "stress":
        if value >= specs.get("critical_range", (70, 100))[0]:
            return "critical"
        elif value >= specs.get("elevated_range", (50, 70))[0]:
            return "elevated"
        return "normal"

    elif data_type == "sleep":
        if value < 5:
            return "elevated"  # Poor sleep
        return "normal"

    return "normal"


def get_alert_message(data_type: str, alert_level: str, context: str = None) -> str:
    """Get an appropriate alert message."""
    messages = ALERT_MESSAGES.get(data_type, {})

    if context and context in messages:
        return random.choice(messages[context])

    if alert_level in messages:
        return random.choice(messages[alert_level])

    return f"{data_type.replace('_', ' ').title()} reading recorded"


def create_health_event(
    data_type: str,
    value: float,
    unit: str = None,
    alert_level: str = None,
    source_device: str = None,
    metadata: dict = None,
) -> dict:
    """Create a health data event."""

    if unit is None:
        unit = HEALTH_DATA_SPECS.get(data_type, {}).get("unit", "")

    if alert_level is None:
        alert_level = determine_alert_level(data_type, value)

    if source_device is None:
        source_device = random.choice(WEARABLE_DEVICES)

    message = get_alert_message(data_type, alert_level)

    event = {
        "event_id": f"WRB-{uuid.uuid4().hex[:8].upper()}",
        "event_type": "wearable_data",
        "data_type": data_type,
        "value": value,
        "unit": unit,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "alert_level": alert_level,
        "message": message,
        "source_device": source_device,
        "source": "simulator",
    }

    if metadata:
        event["metadata"] = metadata

    return event


def publish_event(publisher, event: dict, topic_prefix: str = "health/events"):
    """Publish an event to the appropriate topic."""
    data_type = event["data_type"]
    topic_string = f"{topic_prefix}/wearable/{data_type}/update"
    topic = Topic.of(topic_string)

    message_body = json.dumps(event, indent=2)

    print(f"\n[PUBLISH] Topic: {topic_string}")
    print(f"[PAYLOAD] {message_body}")

    publisher.publish(destination=topic, message=message_body)

    return topic_string


def generate_heart_rate(context: str = "resting") -> dict:
    """Generate a heart rate reading."""
    specs = HEALTH_DATA_SPECS["heart_rate"]

    if context == "resting":
        value = random.randint(*specs["resting_range"])
    elif context == "exercise":
        value = random.randint(*specs["exercise_range"])
    elif context == "elevated":
        value = random.randint(*specs["elevated_range"])
    elif context == "critical_high":
        value = random.randint(specs["critical_high"], specs["critical_high"] + 20)
    elif context == "critical_low":
        value = random.randint(specs["critical_low"] - 10, specs["critical_low"])
    else:
        value = random.randint(*specs["normal_range"])

    return create_health_event("heart_rate", value, metadata={"context": context})


def generate_steps_update(current_total: int = 0) -> dict:
    """Generate a steps update."""
    specs = HEALTH_DATA_SPECS["steps"]
    increment = random.randint(*specs["increment_range"])
    new_total = current_total + increment

    context = None
    if new_total >= specs["daily_goal"]:
        context = "goal_reached"
    elif new_total >= specs["daily_goal"] * 0.5:
        context = "milestone"

    message = get_alert_message("steps", "normal", context)

    return create_health_event(
        "steps",
        new_total,
        alert_level="normal",
        metadata={"increment": increment, "daily_goal": specs["daily_goal"]},
    )


def generate_stress_reading() -> dict:
    """Generate a stress level reading."""
    specs = HEALTH_DATA_SPECS["stress"]

    # Weighted random - more likely to be normal
    weights = [0.6, 0.3, 0.1]  # normal, elevated, critical
    ranges = [specs["normal_range"], specs["elevated_range"], specs["critical_range"]]
    selected_range = random.choices(ranges, weights=weights)[0]

    value = random.randint(*selected_range)
    return create_health_event("stress", value)


def generate_sleep_event(hours: float = None, quality: int = None) -> dict:
    """Generate a sleep session event."""
    specs = HEALTH_DATA_SPECS["sleep"]

    if hours is None:
        # Weighted towards normal sleep
        if random.random() < 0.8:
            hours = round(random.uniform(*specs["normal_duration"]), 1)
        else:
            hours = round(random.uniform(*specs["poor_duration"]), 1)

    if quality is None:
        quality = random.randint(*specs["quality_range"])

    alert_level = "elevated" if hours < 5 else "normal"
    context = "poor" if hours < 5 else "good"

    return create_health_event(
        "sleep",
        hours,
        alert_level=alert_level,
        metadata={"quality_score": quality, "context": context},
    )


def generate_workout_event(
    workout_type: str = None,
    duration: int = None,
    event_type: str = "completed",
) -> dict:
    """Generate a workout event."""
    specs = HEALTH_DATA_SPECS["workout"]

    if workout_type is None:
        workout_type = random.choice(specs["types"])

    if duration is None:
        duration = random.randint(*specs["duration_range"])

    calories = duration * random.randint(*specs["calories_per_minute"])

    message = get_alert_message("workout", "normal", event_type)

    return create_health_event(
        "workout",
        duration,
        unit="minutes",
        alert_level="normal",
        metadata={
            "workout_type": workout_type,
            "calories_burned": calories,
            "event_type": event_type,
        },
    )


def run_random_scenario(publisher, interval: float, count: int = None):
    """Generate random health data at specified interval."""
    print(f"\n[SCENARIO] Random health data every {interval} seconds")
    if count:
        print(f"[SCENARIO] Will send {count} events")
    else:
        print("[SCENARIO] Running continuously (Ctrl+C to stop)")

    data_generators = [
        ("heart_rate", lambda: generate_heart_rate("resting")),
        ("heart_rate", lambda: generate_heart_rate("normal")),
        ("stress", generate_stress_reading),
    ]

    step_total = random.randint(2000, 5000)  # Start with some steps
    events_sent = 0

    try:
        while count is None or events_sent < count:
            # Weighted selection - heart rate most common
            weights = [0.4, 0.3, 0.3]
            generator_name, generator = random.choices(data_generators, weights=weights)[0]

            # Occasionally add steps
            if random.random() < 0.3:
                step_total += random.randint(50, 300)
                event = generate_steps_update(step_total - random.randint(50, 300))
                event["value"] = step_total
            else:
                event = generator()

            publish_event(publisher, event)
            events_sent += 1

            if count is None or events_sent < count:
                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[INFO] Stopped after {events_sent} events")


def run_workout_scenario(publisher, workout_type: str = None, duration: int = 30, interval: float = 5):
    """Simulate a workout session with heart rate updates."""
    if workout_type is None:
        workout_type = random.choice(HEALTH_DATA_SPECS["workout"]["types"])

    print(f"\n[SCENARIO] Simulating {duration} minute {workout_type} workout")

    # Workout start
    event = generate_workout_event(workout_type, duration, "started")
    publish_event(publisher, event)
    time.sleep(interval)

    # Heart rate during workout
    workout_updates = duration // 5  # Update every 5 simulated minutes
    for i in range(workout_updates):
        hr_event = generate_heart_rate("exercise")
        hr_event["metadata"]["workout_context"] = workout_type
        hr_event["metadata"]["elapsed_minutes"] = (i + 1) * 5
        publish_event(publisher, hr_event)
        time.sleep(interval)

    # Workout complete
    event = generate_workout_event(workout_type, duration, "completed")
    publish_event(publisher, event)

    # Recovery heart rate
    time.sleep(interval)
    recovery_event = generate_heart_rate("elevated")
    recovery_event["metadata"]["context"] = "post_workout_recovery"
    publish_event(publisher, recovery_event)

    print(f"\n[SCENARIO] Workout simulation complete")


def run_sleep_scenario(publisher, hours: float = None):
    """Simulate a sleep session."""
    specs = HEALTH_DATA_SPECS["sleep"]

    if hours is None:
        hours = round(random.uniform(*specs["normal_duration"]), 1)

    print(f"\n[SCENARIO] Simulating {hours} hour sleep session")

    quality = random.randint(60, 95)
    event = generate_sleep_event(hours, quality)
    publish_event(publisher, event)

    # Morning resting heart rate
    time.sleep(2)
    hr_event = generate_heart_rate("resting")
    hr_event["metadata"]["context"] = "morning_resting"
    publish_event(publisher, hr_event)

    print(f"\n[SCENARIO] Sleep simulation complete")


def run_stress_scenario(publisher, interval: float = 5):
    """Simulate increasing then decreasing stress levels."""
    print(f"\n[SCENARIO] Simulating stress escalation and recovery")

    # Escalation
    levels = [30, 45, 60, 75, 85]
    for level in levels:
        event = create_health_event("stress", level)
        publish_event(publisher, event)
        time.sleep(interval)

    # Recovery
    levels = [70, 55, 40, 30]
    for level in levels:
        event = create_health_event("stress", level)
        event["message"] = "Stress levels decreasing - relaxation helping"
        publish_event(publisher, event)
        time.sleep(interval)

    print(f"\n[SCENARIO] Stress simulation complete")


def run_elevated_hr_scenario(publisher, interval: float = 5):
    """Simulate elevated heart rate during rest (potential health concern)."""
    print(f"\n[SCENARIO] Simulating elevated resting heart rate")

    # Normal baseline
    event = generate_heart_rate("resting")
    publish_event(publisher, event)
    time.sleep(interval)

    # Gradually elevating
    for hr in [85, 95, 105, 115, 125]:
        event = create_health_event("heart_rate", hr)
        if hr >= 120:
            event["alert_level"] = "critical"
            event["message"] = "Heart rate dangerously elevated at rest - medical attention may be needed"
        elif hr >= 100:
            event["alert_level"] = "elevated"
            event["message"] = "Elevated heart rate during rest period - monitor closely"
        publish_event(publisher, event)
        time.sleep(interval)

    # Recovery
    for hr in [110, 95, 80, 72]:
        event = create_health_event("heart_rate", hr)
        event["message"] = "Heart rate returning to normal"
        publish_event(publisher, event)
        time.sleep(interval)

    print(f"\n[SCENARIO] Heart rate simulation complete")


def run_single_event(publisher, data_type: str, value: float, unit: str = None):
    """Publish a single health event."""
    print(f"\n[SCENARIO] Single event: {data_type} = {value}")

    event = create_health_event(data_type, value, unit)
    publish_event(publisher, event)


def main():
    parser = argparse.ArgumentParser(
        description="Wearable Health Data Simulator for Health Counselor Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Random health data every 10 seconds
  python scripts/wearable_simulator.py --scenario random --interval 10

  # Simulate a 30-minute running workout
  python scripts/wearable_simulator.py --scenario workout --workout-type running --duration 30

  # Simulate a sleep session
  python scripts/wearable_simulator.py --scenario sleep --hours 7.5

  # Simulate stress escalation and recovery
  python scripts/wearable_simulator.py --scenario stress

  # Simulate elevated heart rate concern
  python scripts/wearable_simulator.py --scenario elevated-hr

  # Single heart rate reading
  python scripts/wearable_simulator.py --once --type heart_rate --value 75

  # Random events, limited count
  python scripts/wearable_simulator.py --scenario random --count 5 --interval 5
        """,
    )

    parser.add_argument(
        "--scenario",
        choices=["random", "workout", "sleep", "stress", "elevated-hr"],
        default="random",
        help="Scenario to run (default: random)",
    )
    parser.add_argument(
        "--type",
        choices=["heart_rate", "steps", "sleep", "workout", "stress"],
        help="Data type for single event (use with --once)",
    )
    parser.add_argument(
        "--value",
        type=float,
        help="Value for single event (use with --once)",
    )
    parser.add_argument(
        "--unit",
        help="Unit for single event (optional, auto-detected from type)",
    )
    parser.add_argument(
        "--workout-type",
        choices=HEALTH_DATA_SPECS["workout"]["types"],
        help="Workout type for workout scenario",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in minutes for workout scenario (default: 30)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        help="Hours of sleep for sleep scenario",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Interval between events in seconds (default: 10)",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Number of events to send (default: unlimited for random)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send a single event and exit",
    )
    parser.add_argument(
        "--topic-prefix",
        default="health/events",
        help="Topic prefix for events (default: health/events)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.once and not args.type:
        parser.error("--once requires --type")
    if args.once and args.value is None:
        parser.error("--once requires --value")

    print("=" * 60)
    print("Wearable Health Data Simulator")
    print("=" * 60)

    # Connect to Solace
    messaging_service = None
    publisher = None

    try:
        messaging_service = create_messaging_service()

        # Create publisher
        publisher = (
            messaging_service.create_direct_message_publisher_builder()
            .on_back_pressure_reject(buffer_capacity=100)
            .build()
        )

        publisher.set_publish_failure_listener(EventPublishFailureListener())
        publisher.start()

        print("[INFO] Publisher started")

        # Run scenario
        if args.once:
            run_single_event(publisher, args.type, args.value, args.unit)
        elif args.scenario == "random":
            run_random_scenario(publisher, args.interval, args.count)
        elif args.scenario == "workout":
            run_workout_scenario(
                publisher, args.workout_type, args.duration, args.interval
            )
        elif args.scenario == "sleep":
            run_sleep_scenario(publisher, args.hours)
        elif args.scenario == "stress":
            run_stress_scenario(publisher, args.interval)
        elif args.scenario == "elevated-hr":
            run_elevated_hr_scenario(publisher, args.interval)

        print("\n[INFO] Simulation complete")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if publisher:
            publisher.terminate()
            print("[INFO] Publisher terminated")
        if messaging_service:
            messaging_service.disconnect()
            print("[INFO] Disconnected from Solace broker")


if __name__ == "__main__":
    main()
