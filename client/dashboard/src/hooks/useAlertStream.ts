/**
 * Hook for receiving real-time automation alerts via Server-Sent Events.
 *
 * Connects to /api/health/alerts/stream and receives alerts from:
 * - Anomaly detection (heart rate, sleep, etc.)
 * - Goal achievements (steps, active minutes)
 * - Critical health alerts
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import type { HealthAlert, AlertLevel } from '../types/health';

/**
 * SSE alert format from the backend AutomationAlert.to_dict()
 */
interface SSEAlert {
  id: string;
  alert_type: string;
  title: string;
  message: string;
  timestamp: string;
  severity: string;
  domain: string;
  data_type?: string;
  value?: number;
  baseline?: number;
  deviation?: number;
  goal_name?: string;
  goal_target?: number;
}

interface UseAlertStreamReturn {
  /** Real-time alerts from SSE stream */
  sseAlerts: HealthAlert[];
  /** Whether SSE connection is active */
  connected: boolean;
  /** Remove an alert from the list */
  clearAlert: (id: string) => void;
  /** Clear all SSE alerts */
  clearAll: () => void;
}

/**
 * Hook that connects to the SSE alert stream for real-time notifications.
 *
 * @param enabled - Whether to enable the SSE connection (default: true)
 * @returns Object with alerts, connection status, and clear functions
 */
// Valid alert levels for type safety
const VALID_LEVELS: AlertLevel[] = ['info', 'warning', 'critical'];

export function useAlertStream(enabled: boolean = true): UseAlertStreamReturn {
  const [sseAlerts, setSSEAlerts] = useState<HealthAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptRef = useRef(0);

  // Track enabled state in ref to avoid recreating connect callback
  const enabledRef = useRef(enabled);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  /**
   * Map SSE alert format to HealthAlert type.
   * Main difference: severity -> level (with validation)
   */
  const mapSSEToHealthAlert = useCallback((sse: SSEAlert): HealthAlert => {
    // Validate severity level with fallback to 'info'
    const level = VALID_LEVELS.includes(sse.severity as AlertLevel)
      ? (sse.severity as AlertLevel)
      : 'info';

    return {
      id: sse.id,
      level,
      title: sse.title,
      message: sse.message,
      domain: sse.domain,
      timestamp: sse.timestamp,
      dismissed: false,
    };
  }, []);

  /**
   * Connect to the SSE stream.
   */
  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Include history to catch any recent alerts
    const eventSource = new EventSource('/api/health/alerts/stream?include_history=true&history_count=10');
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnected(true);
      reconnectAttemptRef.current = 0; // Reset backoff on successful connection
      // Clear any pending reconnect
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    eventSource.onerror = () => {
      setConnected(false);
      eventSource.close();
      eventSourceRef.current = null;

      // Exponential backoff with jitter: 1s, 2s, 4s, 8s, 16s, max 30s
      if (!reconnectTimeoutRef.current) {
        const backoffMs = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 30000);
        const jitter = Math.random() * 1000;

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          reconnectAttemptRef.current++;
          if (enabledRef.current) {
            connect();
          }
        }, backoffMs + jitter);
      }
    };

    // Listen for 'alert' events (the backend sends: event: alert\ndata: {...})
    eventSource.addEventListener('alert', (event) => {
      try {
        const alert = JSON.parse(event.data) as SSEAlert;
        setSSEAlerts(prev => {
          // Don't add duplicates
          const exists = prev.some(a => a.id === alert.id);
          if (exists) return prev;

          // Add new alert at the beginning, limit to 50
          const healthAlert = mapSSEToHealthAlert(alert);
          return [healthAlert, ...prev].slice(0, 50);
        });
      } catch (error) {
        // Log parse errors in development for debugging
        if (import.meta.env.DEV) {
          console.warn('[useAlertStream] Failed to parse SSE alert:', error);
        }
      }
    });
  }, [mapSSEToHealthAlert]); // Note: enabled tracked via enabledRef to prevent reconnection loops

  /**
   * Effect to manage connection lifecycle.
   */
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      setConnected(false);
    };
  }, [enabled, connect]);

  /**
   * Clear a specific alert by ID.
   */
  const clearAlert = useCallback((id: string) => {
    setSSEAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  /**
   * Clear all SSE alerts.
   */
  const clearAll = useCallback(() => {
    setSSEAlerts([]);
  }, []);

  return { sseAlerts, connected, clearAlert, clearAll };
}
