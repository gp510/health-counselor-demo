interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  color?: string;
}

const trendIcons = {
  up: '↑',
  down: '↓',
  stable: '→',
};

const trendColors = {
  up: 'text-health-excellent',
  down: 'text-health-critical',
  stable: 'text-text-secondary',
};

export function MetricCard({
  label,
  value,
  unit,
  icon,
  trend,
  trendValue,
  color,
}: MetricCardProps) {
  return (
    <div className="flex items-center gap-3">
      {icon && (
        <div
          className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-xl"
          style={{ backgroundColor: color ? `${color}20` : undefined }}
        >
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-text-secondary truncate">{label}</p>
        <div className="flex items-baseline gap-1">
          <span className="text-lg font-semibold text-text-primary">{value}</span>
          {unit && <span className="text-sm text-text-muted">{unit}</span>}
          {trend && (
            <span className={`text-xs ${trendColors[trend]} ml-1`}>
              {trendIcons[trend]} {trendValue}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
