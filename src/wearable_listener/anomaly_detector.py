"""
Anomaly Detection Module for Wearable Health Data.

Implements rolling statistics tracking and anomaly detection using
personal baselines. Alerts are triggered when values deviate
significantly (>2 standard deviations) from the user's normal range.
"""

import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Result of an anomaly check."""

    detected: bool
    data_type: str
    value: float
    baseline_mean: float
    baseline_std: float
    deviation_sigma: float  # How many standard deviations from mean
    severity: str  # info, warning, critical
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "detected": self.detected,
            "data_type": self.data_type,
            "value": self.value,
            "baseline_mean": self.baseline_mean,
            "baseline_std": self.baseline_std,
            "deviation_sigma": self.deviation_sigma,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RollingStats:
    """Rolling statistics for a data type."""

    readings: deque  # deque of (timestamp, value) tuples
    mean: float = 0.0
    std_dev: float = 0.0
    min_val: float = float('inf')
    max_val: float = float('-inf')
    count: int = 0


class AnomalyDetector:
    """
    Detects anomalies in wearable health data using rolling statistics.

    Maintains a sliding window of readings for each data type and
    detects when new values deviate significantly from the personal
    baseline.

    Configuration:
        window_hours: Size of rolling window for baseline calculation
        min_readings: Minimum readings required before anomaly detection
        sigma_threshold: Standard deviations for anomaly detection
    """

    # Default thresholds by data type (can be customized)
    DEFAULT_THRESHOLDS = {
        "heart_rate": {
            "sigma_threshold": 2.0,  # 2 std dev
            "critical_high": 120,     # Absolute threshold for critical
            "critical_low": 40,
            "min_readings": 10,
        },
        "steps": {
            "sigma_threshold": 2.5,   # Steps vary more
            "min_readings": 5,
        },
        "sleep": {
            "sigma_threshold": 2.0,
            "critical_low": 4.0,      # Less than 4 hours is critical
            "min_readings": 7,
        },
        "stress": {
            "sigma_threshold": 2.0,
            "critical_high": 9,       # 9+ out of 10 is critical
            "min_readings": 5,
        },
        "workout": {
            "sigma_threshold": 2.5,
            "min_readings": 3,
        },
    }

    def __init__(
        self,
        window_hours: int = 24,
        sigma_threshold: float = 2.0,
        min_readings: int = 5
    ):
        """
        Initialize the anomaly detector.

        Args:
            window_hours: Size of rolling window in hours
            sigma_threshold: Default threshold in standard deviations
            min_readings: Minimum readings needed for baseline
        """
        self.window = timedelta(hours=window_hours)
        self.default_sigma = sigma_threshold
        self.default_min_readings = min_readings

        # Rolling stats by data type
        self._stats: Dict[str, RollingStats] = {}

        # Anomaly history for tracking patterns
        self._anomaly_history: deque = deque(maxlen=100)

        logger.info(
            f"[ANOMALY] Initialized detector: window={window_hours}h, "
            f"sigma={sigma_threshold}, min_readings={min_readings}"
        )

    def add_reading(
        self,
        data_type: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Add a new reading to the rolling statistics.

        Args:
            data_type: Type of data (heart_rate, steps, etc.)
            value: The measured value
            timestamp: When the reading was taken (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Initialize stats for new data types
        if data_type not in self._stats:
            self._stats[data_type] = RollingStats(
                readings=deque(maxlen=1000)  # Keep up to 1000 readings
            )

        stats = self._stats[data_type]

        # Add new reading
        stats.readings.append((timestamp, value))

        # Prune old readings outside window
        self._prune_old_readings(data_type)

        # Recalculate statistics
        self._recalculate_stats(data_type)

        logger.debug(
            f"[ANOMALY] Added {data_type}={value}: "
            f"mean={stats.mean:.2f}, std={stats.std_dev:.2f}, n={stats.count}"
        )

    def _prune_old_readings(self, data_type: str) -> None:
        """Remove readings outside the rolling window."""
        stats = self._stats[data_type]
        cutoff = datetime.now(timezone.utc) - self.window

        # Remove readings older than cutoff
        while stats.readings and stats.readings[0][0] < cutoff:
            stats.readings.popleft()

    def _recalculate_stats(self, data_type: str) -> None:
        """Recalculate rolling statistics for a data type."""
        stats = self._stats[data_type]

        if not stats.readings:
            stats.count = 0
            stats.mean = 0.0
            stats.std_dev = 0.0
            return

        values = [v for _, v in stats.readings]
        stats.count = len(values)
        stats.mean = statistics.mean(values)
        stats.min_val = min(values)
        stats.max_val = max(values)

        # Standard deviation requires at least 2 readings
        if stats.count >= 2:
            stats.std_dev = statistics.stdev(values)
        else:
            stats.std_dev = 0.0

    def check_anomaly(
        self,
        data_type: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> AnomalyResult:
        """
        Check if a value is anomalous compared to the personal baseline.

        Args:
            data_type: Type of data being checked
            value: The value to check
            timestamp: When the reading was taken

        Returns:
            AnomalyResult with detection status and context
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Get thresholds for this data type
        thresholds = self.DEFAULT_THRESHOLDS.get(data_type, {})
        sigma_threshold = thresholds.get("sigma_threshold", self.default_sigma)
        min_readings = thresholds.get("min_readings", self.default_min_readings)
        critical_high = thresholds.get("critical_high")
        critical_low = thresholds.get("critical_low")

        # Check for absolute critical thresholds first
        if critical_high is not None and value >= critical_high:
            return AnomalyResult(
                detected=True,
                data_type=data_type,
                value=value,
                baseline_mean=self._get_mean(data_type),
                baseline_std=self._get_std(data_type),
                deviation_sigma=float('inf'),
                severity="critical",
                message=f"Critical {data_type} value: {value} exceeds threshold {critical_high}",
                timestamp=timestamp,
            )

        if critical_low is not None and value <= critical_low:
            return AnomalyResult(
                detected=True,
                data_type=data_type,
                value=value,
                baseline_mean=self._get_mean(data_type),
                baseline_std=self._get_std(data_type),
                deviation_sigma=float('inf'),
                severity="critical",
                message=f"Critical {data_type} value: {value} below threshold {critical_low}",
                timestamp=timestamp,
            )

        # Check if we have enough baseline data
        stats = self._stats.get(data_type)
        if not stats or stats.count < min_readings:
            logger.debug(
                f"[ANOMALY] Not enough readings for {data_type}: "
                f"{stats.count if stats else 0}/{min_readings}"
            )
            return AnomalyResult(
                detected=False,
                data_type=data_type,
                value=value,
                baseline_mean=stats.mean if stats else 0.0,
                baseline_std=stats.std_dev if stats else 0.0,
                deviation_sigma=0.0,
                severity="info",
                message=f"Insufficient baseline data for {data_type} ({stats.count if stats else 0}/{min_readings} readings)",
                timestamp=timestamp,
            )

        # Can't detect anomalies if std_dev is zero (all same values)
        if stats.std_dev == 0:
            return AnomalyResult(
                detected=False,
                data_type=data_type,
                value=value,
                baseline_mean=stats.mean,
                baseline_std=0.0,
                deviation_sigma=0.0,
                severity="info",
                message=f"No variance in {data_type} baseline",
                timestamp=timestamp,
            )

        # Calculate deviation from baseline
        deviation_sigma = abs(value - stats.mean) / stats.std_dev

        # Determine if anomaly and severity
        if deviation_sigma >= sigma_threshold:
            # Determine direction and severity
            direction = "high" if value > stats.mean else "low"

            if deviation_sigma >= sigma_threshold * 1.5:
                severity = "warning"
            else:
                severity = "info"

            message = (
                f"Anomaly detected: {data_type} is {direction} "
                f"({value:.1f} vs baseline {stats.mean:.1f}, "
                f"{deviation_sigma:.1f} sigma)"
            )

            result = AnomalyResult(
                detected=True,
                data_type=data_type,
                value=value,
                baseline_mean=stats.mean,
                baseline_std=stats.std_dev,
                deviation_sigma=deviation_sigma,
                severity=severity,
                message=message,
                timestamp=timestamp,
            )

            # Track anomaly
            self._anomaly_history.append(result)

            logger.info(f"[ANOMALY DETECTED] {message}")
            return result

        # No anomaly
        return AnomalyResult(
            detected=False,
            data_type=data_type,
            value=value,
            baseline_mean=stats.mean,
            baseline_std=stats.std_dev,
            deviation_sigma=deviation_sigma,
            severity="info",
            message=f"{data_type} is within normal range",
            timestamp=timestamp,
        )

    def _get_mean(self, data_type: str) -> float:
        """Get mean for a data type, or 0 if not available."""
        stats = self._stats.get(data_type)
        return stats.mean if stats else 0.0

    def _get_std(self, data_type: str) -> float:
        """Get std dev for a data type, or 0 if not available."""
        stats = self._stats.get(data_type)
        return stats.std_dev if stats else 0.0

    def get_baseline(self, data_type: str) -> Optional[Dict]:
        """
        Get the current baseline statistics for a data type.

        Returns:
            Dict with mean, std_dev, min, max, count, or None if no data
        """
        stats = self._stats.get(data_type)
        if not stats or stats.count == 0:
            return None

        return {
            "mean": stats.mean,
            "std_dev": stats.std_dev,
            "min": stats.min_val,
            "max": stats.max_val,
            "count": stats.count,
            "window_hours": self.window.total_seconds() / 3600,
        }

    def get_all_baselines(self) -> Dict[str, Dict]:
        """Get baseline statistics for all tracked data types."""
        baselines = {}
        for data_type in self._stats:
            baseline = self.get_baseline(data_type)
            if baseline:
                baselines[data_type] = baseline
        return baselines

    def get_anomaly_history(self, count: int = 10) -> list:
        """Get recent anomaly history."""
        history = list(self._anomaly_history)[-count:]
        return [a.to_dict() for a in history]

    def get_stats(self) -> Dict:
        """Get overall anomaly detector statistics."""
        total_readings = sum(s.count for s in self._stats.values())
        return {
            "data_types_tracked": list(self._stats.keys()),
            "total_readings": total_readings,
            "anomalies_detected": len(self._anomaly_history),
            "window_hours": self.window.total_seconds() / 3600,
            "baselines": self.get_all_baselines(),
        }

    def reset(self, data_type: Optional[str] = None) -> None:
        """
        Reset statistics.

        Args:
            data_type: Specific type to reset, or None for all
        """
        if data_type:
            if data_type in self._stats:
                del self._stats[data_type]
                logger.info(f"[ANOMALY] Reset statistics for {data_type}")
        else:
            self._stats.clear()
            self._anomaly_history.clear()
            logger.info("[ANOMALY] Reset all statistics")


# Global singleton instance
anomaly_detector = AnomalyDetector()


def check_and_track_anomaly(
    data_type: str,
    value: float,
    timestamp: Optional[datetime] = None
) -> Tuple[bool, Optional[AnomalyResult]]:
    """
    Convenience function to add reading and check for anomaly.

    Args:
        data_type: Type of health data
        value: The measured value
        timestamp: When reading was taken

    Returns:
        Tuple of (anomaly_detected, AnomalyResult or None)
    """
    # Add to rolling stats first
    anomaly_detector.add_reading(data_type, value, timestamp)

    # Then check for anomaly
    result = anomaly_detector.check_anomaly(data_type, value, timestamp)

    return (result.detected, result if result.detected else None)
