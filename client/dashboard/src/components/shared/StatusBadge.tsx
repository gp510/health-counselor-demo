import type { HealthStatus } from '../../types/health';

interface StatusBadgeProps {
  status: HealthStatus;
  label?: string;
}

const statusColors: Record<HealthStatus, string> = {
  normal: 'bg-health-excellent text-white',
  low: 'bg-health-warning text-white',
  high: 'bg-health-warning text-white',
  critical: 'bg-health-critical text-white',
};

const statusLabels: Record<HealthStatus, string> = {
  normal: 'Normal',
  low: 'Low',
  high: 'High',
  critical: 'Critical',
};

export function StatusBadge({ status, label }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[status]}`}
    >
      {label || statusLabels[status]}
    </span>
  );
}
