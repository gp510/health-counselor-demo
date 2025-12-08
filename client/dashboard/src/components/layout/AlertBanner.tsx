import type { HealthAlert, AlertLevel } from '../../types/health';

interface AlertBannerProps {
  alerts: HealthAlert[];
  onDismiss?: (alertId: string) => void;
}

const levelStyles: Record<AlertLevel, { bg: string; border: string; icon: string }> = {
  info: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: 'ℹ️',
  },
  warning: {
    bg: 'bg-health-warning/10',
    border: 'border-health-warning/30',
    icon: '⚠️',
  },
  critical: {
    bg: 'bg-health-critical/10',
    border: 'border-health-critical/30',
    icon: '🚨',
  },
};

export function AlertBanner({ alerts, onDismiss }: AlertBannerProps) {
  // Show all non-dismissed alerts (info, warning, critical)
  const activeAlerts = alerts.filter((a) => !a.dismissed);

  if (activeAlerts.length === 0) {
    return null;
  }

  // Show the most critical alert first
  const sortedAlerts = [...activeAlerts].sort((a, b) => {
    const priority = { critical: 0, warning: 1, info: 2 };
    return priority[a.level] - priority[b.level];
  });

  const alert = sortedAlerts[0];
  const style = levelStyles[alert.level];

  return (
    <div
      className={`flex-shrink-0 ${style.bg} border-b ${style.border} px-6 py-3`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg">{style.icon}</span>
          <div>
            <p className="text-sm font-medium text-text-primary">{alert.title}</p>
            <p className="text-xs text-text-secondary">{alert.message}</p>
          </div>
          {sortedAlerts.length > 1 && (
            <span className="ml-2 px-2 py-0.5 bg-bg-hover rounded-full text-xs text-text-muted">
              +{sortedAlerts.length - 1} more
            </span>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={() => onDismiss(alert.id)}
            className="p-1 hover:bg-bg-hover rounded transition-colors text-text-muted hover:text-text-primary"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
